"""The audit log, security headers, write rate limiting and file-based secrets."""

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.schemas.enums import Role
from app.security.audit import SYSTEM, _clean
from tests.conftest import TEST_PASSWORD, Harness
from tests.test_runtime import active_agent


def audit(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    response = client.get("/api/v1/audit", params=params)
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


def actions(client: TestClient, **params: Any) -> list[str]:
    return [event["action"] for event in audit(client, **params)]


def eventually(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    """Failed sign-ins are recorded after the response, off the request path."""
    deadline = time.monotonic() + 5
    while True:
        events = audit(client, **params)
        if events or time.monotonic() > deadline:
            return events
        time.sleep(0.05)


class TestWhatIsRecorded:
    def test_a_sign_in_is_recorded(self, harness: Harness) -> None:
        client = harness.sign_in("admin")

        event = audit(client, action="auth.login")[0]

        assert event["actorName"] == "Admin Person"
        assert event["outcome"] == "success"

    def test_a_failed_sign_in_to_a_real_account_is_recorded(self, harness: Harness) -> None:
        target = harness.workspace.account("member")
        failed = harness.app_client().post(
            "/api/v1/auth/login", json={"email": target.email, "password": "wrong-password-1"}
        )
        assert failed.status_code == 401

        admin = harness.sign_in("admin")
        event = eventually(admin, action="auth.login_failed")[0]

        assert event["outcome"] == "failure"
        assert event["targetId"] == target.user_id

    def test_a_failed_sign_in_to_an_unknown_address_leaves_no_trace(self, harness: Harness) -> None:
        email = "nobody-at-all@example.com"
        harness.app_client().post(
            "/api/v1/auth/login", json={"email": email, "password": "wrong-password-1"}
        )

        admin = harness.sign_in("admin")
        time.sleep(0.5)  # give a background write, if there were one, time to land
        events = audit(admin, action="auth.login_failed")

        assert events == []
        assert email not in admin.get("/api/v1/audit").text

    def test_a_role_change_records_before_and_after(self, harness: Harness) -> None:
        client = harness.sign_in("owner")
        member = next(
            m for m in client.get("/api/v1/members").json()["items"] if m["role"] == "member"
        )

        changed = client.patch(f"/api/v1/members/{member['id']}", json={"role": "admin"})
        assert changed.status_code == 200, changed.text

        event = audit(client, action="member.role_changed")[0]
        assert (event["detail"]["from"], event["detail"]["to"]) == ("member", "admin")

    def test_the_kill_switch_is_recorded_both_ways(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        owner = harness.sign_in("owner")
        admin.patch(
            "/api/v1/organization/runtime", json={"executionsPaused": True, "reason": "Incident"}
        )
        owner.patch("/api/v1/organization/runtime", json={"executionsPaused": False})

        recorded = actions(owner, action="runtime.")

        assert recorded == ["runtime.kill_switch_released", "runtime.kill_switch_engaged"]

    def test_agent_changes_are_recorded(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Recorded Agent")
        client.delete(f"/api/v1/agents/{agent['id']}")

        recorded = actions(client, action="agent.")

        assert recorded == ["agent.deleted", "agent.status_changed", "agent.created"]

    def test_a_password_change_is_recorded_without_the_password(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        new_password = "an-entirely-new-passphrase"
        changed = client.post(
            "/api/v1/auth/password",
            json={"currentPassword": TEST_PASSWORD, "newPassword": new_password},
        )
        assert changed.status_code == 204, changed.text

        body = client.get("/api/v1/audit").text

        assert "auth.password_changed" in body
        assert new_password not in body
        assert TEST_PASSWORD not in body


class TestReadingTheLog:
    @pytest.mark.parametrize("role", ["viewer", "member"])
    def test_only_administrators_can_read_it(self, harness: Harness, role: Role) -> None:
        assert harness.sign_in(role).get("/api/v1/audit").status_code == 403

    def test_it_requires_a_session(self, harness: Harness) -> None:
        assert harness.app_client().get("/api/v1/audit").status_code == 401

    def test_it_never_crosses_organizations(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        active_agent(client, "Private Agent")

        other = harness.sign_in("admin", workspace=harness.other_workspace)

        assert "agent.created" not in actions(other)

    def test_it_can_be_filtered_by_outcome(self, harness: Harness) -> None:
        harness.app_client().post(
            "/api/v1/auth/login",
            json={"email": harness.workspace.account("member").email, "password": "wrong-1"},
        )
        admin = harness.sign_in("admin")

        assert {event["outcome"] for event in eventually(admin, outcome="failure")} == {"failure"}

    def test_nothing_can_change_or_delete_it(self, harness: Harness) -> None:
        schema = harness.app_client("development").get("/api/openapi.json").json()
        methods = {
            method
            for path, operations in schema["paths"].items()
            if path.startswith("/api/v1/audit")
            for method in operations
        }

        assert methods == {"get"}

    def test_secret_shaped_details_are_dropped(self) -> None:
        cleaned = _clean(
            {
                "password": "x",
                "api_key": "x",
                "Authorization": "x",
                "session_token": "x",
                "note": "y" * 1000,
                "nested": {"cookie": "x", "ok": 1},
            }
        )

        assert set(cleaned) == {"note", "nested"}
        assert cleaned["nested"] == {"ok": 1}
        assert len(cleaned["note"]) == 300
        assert SYSTEM.type == "system"


class TestHeaders:
    def test_api_responses_forbid_loading_framing_and_sniffing(self, harness: Harness) -> None:
        response = harness.app_client().get("/api/v1/health")

        csp = response.headers["content-security-policy"]
        assert "default-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp
        assert response.headers["cross-origin-opener-policy"] == "same-origin"
        assert response.headers["cross-origin-resource-policy"] == "same-origin"
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_hsts_is_sent_only_in_production(self, harness: Harness) -> None:
        production = harness.app_client("production").get("/api/v1/health")
        test = harness.app_client().get("/api/v1/health")

        assert production.headers["strict-transport-security"].startswith("max-age=")
        assert "strict-transport-security" not in test.headers

    def test_errors_carry_the_headers_too(self, harness: Harness) -> None:
        response = harness.app_client().get("/api/v1/agents")

        assert response.status_code == 401
        assert "content-security-policy" in response.headers


class TestWriteRateLimit:
    def test_a_client_changing_too_much_too_fast_is_slowed(self, harness: Harness) -> None:
        client = harness.app_client(write_requests_per_minute=10)
        # Sign-out without a session: rejected, but still a state-changing request.
        # (Sign-in has its own, stricter throttle, which would answer first.)
        statuses = [client.post("/api/v1/auth/logout").status_code for _ in range(11)]

        assert 429 not in statuses[:10]
        assert statuses[-1] == 429

    def test_reads_are_not_limited(self, harness: Harness) -> None:
        client = harness.app_client(write_requests_per_minute=10)

        statuses = {client.get("/api/v1/health").status_code for _ in range(15)}

        assert statuses == {200}


class TestSecretsDirectory:
    def test_secrets_can_come_from_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "AGENTHUB_ANTHROPIC_API_KEY").write_text("from-a-file", encoding="utf-8")
        monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
        monkeypatch.setenv("ENVIRONMENT", "development")
        get_settings.cache_clear()
        try:
            settings = get_settings()
        finally:
            get_settings.cache_clear()

        assert settings.anthropic_api_key is not None
        assert settings.anthropic_api_key.get_secret_value() == "from-a-file"

    def test_a_missing_secrets_directory_stops_the_process(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SECRETS_DIR", str(tmp_path / "not-there"))
        get_settings.cache_clear()
        try:
            with pytest.raises(RuntimeError, match="not a directory"):
                get_settings()
        finally:
            get_settings.cache_clear()
