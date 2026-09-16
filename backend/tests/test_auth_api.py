from fastapi.testclient import TestClient
from httpx2 import Response

from app.core.config import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from tests.conftest import TEST_PASSWORD, Harness


def login(client: TestClient, email: str, password: str = TEST_PASSWORD) -> Response:
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


class TestLogin:
    def test_returns_the_session_and_sets_both_cookies(self, harness: Harness) -> None:
        client = harness.app_client()
        account = harness.workspace.account("admin")

        response = login(client, account.email)

        assert response.status_code == 200
        body = response.json()
        assert body["user"]["email"] == account.email
        assert body["role"] == "admin"
        assert body["organization"]["slug"] == "test-workspace"
        assert [m["organization"]["slug"] for m in body["memberships"]] == ["test-workspace"]

        cookies = response.headers.get_list("set-cookie")
        session_cookie = next(c for c in cookies if c.startswith(f"{SESSION_COOKIE}="))
        csrf_cookie = next(c for c in cookies if c.startswith(f"{CSRF_COOKIE}="))
        assert "HttpOnly" in session_cookie
        assert "SameSite=strict" in session_cookie.replace("SameSite=Strict", "SameSite=strict")
        # The app must be able to read this one to echo it back in a header.
        assert "HttpOnly" not in csrf_cookie

    def test_never_returns_credentials(self, harness: Harness) -> None:
        client = harness.app_client()

        body = login(client, harness.workspace.account("owner").email).text

        assert "password" not in body.lower()
        assert "scrypt" not in body

    def test_rejects_a_wrong_password_and_an_unknown_address_identically(
        self, harness: Harness
    ) -> None:
        client = harness.app_client()
        known = harness.workspace.account("member").email

        wrong = login(client, known, "not-the-password")
        unknown = login(client, "nobody@test-workspace.example.com")

        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json() == unknown.json()
        assert wrong.json()["code"] == "unauthenticated"

    def test_a_failed_login_sets_no_session(self, harness: Harness) -> None:
        client = harness.app_client()

        login(client, harness.workspace.account("admin").email, "wrong")

        assert SESSION_COOKIE not in client.cookies
        assert client.get("/api/v1/agents").status_code == 401

    def test_signing_in_again_replaces_the_session_in_that_browser(self, harness: Harness) -> None:
        """No session fixation: the token from before the sign-in stops working."""
        client = harness.sign_in("admin")
        previous_token = client.cookies[SESSION_COOKIE]

        assert login(client, harness.workspace.account("admin").email).status_code == 200
        assert client.cookies[SESSION_COOKIE] != previous_token

        replay = harness.app_client()
        replay.cookies.set(SESSION_COOKIE, previous_token)
        assert replay.get("/api/v1/agents").status_code == 401

    def test_other_devices_keep_their_own_sessions(self, harness: Harness) -> None:
        laptop = harness.sign_in("admin")

        phone = harness.sign_in("admin")

        assert laptop.get("/api/v1/agents").status_code == 200
        assert phone.get("/api/v1/agents").status_code == 200

    def test_throttles_repeated_failures_and_says_when_to_retry(self, harness: Harness) -> None:
        client = harness.app_client()
        email = harness.workspace.account("admin").email

        statuses = [login(client, email, "wrong").status_code for _ in range(6)]

        assert statuses[:5] == [401] * 5
        assert statuses[5] == 429
        blocked = login(client, email, "wrong")
        assert blocked.json()["code"] == "rate_limited"
        assert int(blocked.headers["Retry-After"]) > 0

    def test_a_correct_password_clears_that_account_s_failures(self, harness: Harness) -> None:
        client = harness.app_client()
        email = harness.workspace.account("admin").email

        for _ in range(4):
            login(client, email, "wrong")
        assert login(client, email).status_code == 200

        # The counter was reset, so four more failures are still allowed.
        assert [login(client, email, "wrong").status_code for _ in range(4)] == [401] * 4


class TestSession:
    def test_requires_authentication(self, anonymous_client: TestClient) -> None:
        response = anonymous_client.get("/api/v1/auth/session")

        assert response.status_code == 401
        assert response.json()["code"] == "unauthenticated"

    def test_rejects_a_token_that_was_never_issued(self, harness: Harness) -> None:
        client = harness.app_client()
        client.cookies.set(SESSION_COOKIE, "made-up-token")

        assert client.get("/api/v1/auth/session").status_code == 401

    def test_reports_the_role_for_the_active_organization(self, harness: Harness) -> None:
        viewer = harness.sign_in("viewer")

        body = viewer.get("/api/v1/auth/session").json()

        assert body["role"] == "viewer"
        assert body["user"]["email"] == harness.workspace.account("viewer").email

    def test_logout_revokes_the_session_immediately(self, harness: Harness) -> None:
        client = harness.sign_in("admin")

        assert client.post("/api/v1/auth/logout").status_code == 204
        assert client.get("/api/v1/auth/session").status_code == 401
        assert client.get("/api/v1/agents").status_code == 401

    def test_losing_membership_ends_the_session(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        member = harness.sign_in("member")
        assert member.get("/api/v1/agents").status_code == 200

        removed = admin.delete(
            f"/api/v1/members/{harness.workspace.account('member').membership_id}"
        )
        assert removed.status_code == 204

        assert member.get("/api/v1/agents").status_code == 401


class TestPasswordAndProfile:
    def test_changing_a_password_requires_the_current_one(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/password",
            json={"currentPassword": "wrong", "newPassword": "a-much-longer-passphrase"},
        )

        assert response.status_code == 401

    def test_rejects_a_password_that_is_too_short(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/password",
            json={"currentPassword": TEST_PASSWORD, "newPassword": "short"},
        )

        assert response.status_code == 409
        assert "12 characters" in response.json()["message"]

    def test_the_new_password_replaces_the_old_one(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        email = harness.workspace.account("admin").email
        new_password = "a-much-longer-passphrase"

        changed = client.post(
            "/api/v1/auth/password",
            json={"currentPassword": TEST_PASSWORD, "newPassword": new_password},
        )
        assert changed.status_code == 204

        fresh = harness.app_client()
        assert login(fresh, email, TEST_PASSWORD).status_code == 401
        assert login(fresh, email, new_password).status_code == 200

    def test_changing_a_password_signs_out_other_sessions(self, harness: Harness) -> None:
        laptop = harness.sign_in("admin")
        phone = harness.sign_in("admin")

        changed = laptop.post(
            "/api/v1/auth/password",
            json={"currentPassword": TEST_PASSWORD, "newPassword": "a-much-longer-passphrase"},
        )
        assert changed.status_code == 204

        # The session that made the change continues; the other one is over.
        assert laptop.get("/api/v1/agents").status_code == 200
        assert phone.get("/api/v1/agents").status_code == 401

    def test_updates_the_profile_but_not_the_email(self, client: TestClient) -> None:
        response = client.patch(
            "/api/v1/auth/profile", json={"name": "Renamed Person", "timezone": "Europe/Berlin"}
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Renamed Person"
        assert response.json()["timezone"] == "Europe/Berlin"

        rejected = client.patch(
            "/api/v1/auth/profile",
            json={"name": "X", "timezone": "UTC", "email": "new@example.com"},
        )
        assert rejected.status_code == 422


class TestCsrf:
    def test_rejects_a_state_changing_request_without_the_header(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        del client.headers[CSRF_HEADER]

        response = client.post("/api/v1/auth/logout")

        assert response.status_code == 403
        assert response.json()["code"] == "csrf_failed"

    def test_rejects_a_token_that_does_not_belong_to_the_session(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        other = harness.sign_in("owner")
        client.headers[CSRF_HEADER] = other.cookies[CSRF_COOKIE]

        assert client.post("/api/v1/auth/logout").status_code == 403

    def test_reads_do_not_need_a_token(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        del client.headers[CSRF_HEADER]

        assert client.get("/api/v1/agents").status_code == 200
