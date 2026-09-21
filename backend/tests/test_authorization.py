"""Negative access-control tests.

Most of these assert what a caller *cannot* do: the wrong role, the wrong
organization, or no session at all.
"""

from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import Harness
from tests.factories import agent_payload

# Routes that are reachable without a session, and why.
PUBLIC_PATHS = {
    ("GET", "/api/v1/health"),  # liveness probe
    ("GET", "/api/v1/health/ready"),  # readiness probe: one database check, no details
    # Scraped by Prometheus, not a person: closed by METRICS_TOKEN, which
    # production requires (tests/test_observability.py covers both).
    ("GET", "/api/v1/metrics"),
    ("POST", "/api/v1/auth/login"),  # how a session is obtained
}


def create_agent(client: TestClient, name: str) -> dict[str, Any]:
    response = client.post("/api/v1/agents", json=agent_payload(name=name))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def activate(client: TestClient, agent_id: str) -> None:
    response = client.patch(f"/api/v1/agents/{agent_id}/status", json={"status": "active"})
    assert response.status_code == 200, response.text


class TestAuthenticationIsRequired:
    def test_every_route_needs_a_session_unless_it_is_public(self, harness: Harness) -> None:
        """Deny by default: a new route is protected unless it is listed above."""
        client = harness.app_client()
        # The schema is the route table: a route added later shows up here.
        paths: dict[str, dict[str, object]] = cast(FastAPI, client.app).openapi()["paths"]
        checked = 0

        for path, operations in paths.items():
            if not path.startswith("/api/v1"):
                continue
            for method in operations:
                verb = method.upper()
                if (verb, path) in PUBLIC_PATHS:
                    continue
                # Ids that do not exist: an unauthenticated caller must be
                # stopped before anything is looked up.
                url = (
                    path.replace("{agent_id}", "agt_x")
                    .replace("{execution_id}", "exe_x")
                    .replace("{membership_id}", "mem_x")
                )
                response = client.request(verb, url, json={})
                assert response.status_code == 401, f"{verb} {url} returned {response.status_code}"
                checked += 1

        assert checked >= 10

    def test_reads_and_writes_are_both_refused(self, anonymous_client: TestClient) -> None:
        assert anonymous_client.get("/api/v1/agents").status_code == 401
        assert anonymous_client.post("/api/v1/agents", json=agent_payload()).status_code == 401
        assert anonymous_client.get("/api/v1/executions").status_code == 401
        assert anonymous_client.get("/api/v1/members").status_code == 401


class TestAgentPermissions:
    def test_a_viewer_can_read_but_not_create(self, harness: Harness) -> None:
        viewer = harness.sign_in("viewer")

        assert viewer.get("/api/v1/agents").status_code == 200
        refused = viewer.post("/api/v1/agents", json=agent_payload())
        assert refused.status_code == 403
        assert refused.json()["code"] == "forbidden"

    def test_a_member_may_change_their_own_agent(self, harness: Harness) -> None:
        member = harness.sign_in("member")
        agent = create_agent(member, "Member Owned")

        updated = member.put(
            f"/api/v1/agents/{agent['id']}",
            json=agent_payload(name="Member Owned", version="1.1.0"),
        )

        assert updated.status_code == 200
        assert updated.json()["version"] == "1.1.0"

    def test_a_member_may_not_change_someone_else_s_agent(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        member = harness.sign_in("member")
        agent = create_agent(admin, "Admin Owned")

        refused = member.put(
            f"/api/v1/agents/{agent['id']}", json=agent_payload(name="Admin Owned")
        )
        assert refused.status_code == 403

        assert member.delete(f"/api/v1/agents/{agent['id']}").status_code == 403
        assert (
            member.patch(
                f"/api/v1/agents/{agent['id']}/status", json={"status": "active"}
            ).status_code
            == 403
        )

    def test_an_administrator_may_change_any_agent(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        member = harness.sign_in("member")
        agent = create_agent(member, "Member Owned")

        assert (
            admin.put(
                f"/api/v1/agents/{agent['id']}", json=agent_payload(name="Renamed By Admin")
            ).status_code
            == 200
        )
        assert admin.delete(f"/api/v1/agents/{agent['id']}").status_code == 204

    def test_running_an_agent_follows_the_same_rule_as_changing_it(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        member = harness.sign_in("member")
        owned = create_agent(member, "Member Owned")
        other = create_agent(admin, "Admin Owned")
        activate(admin, owned["id"])
        activate(admin, other["id"])

        assert member.post(f"/api/v1/agents/{owned['id']}/executions").status_code == 202
        assert member.post(f"/api/v1/agents/{other['id']}/executions").status_code == 403
        assert admin.post(f"/api/v1/agents/{other['id']}/executions").status_code == 202

    def test_a_viewer_cannot_run_anything(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        viewer = harness.sign_in("viewer")
        agent = create_agent(admin, "Admin Owned")
        activate(admin, agent["id"])

        assert viewer.post(f"/api/v1/agents/{agent['id']}/executions").status_code == 403


class TestOrganizationIsolation:
    def test_agents_are_invisible_to_another_organization(self, harness: Harness) -> None:
        inside = harness.sign_in("admin")
        outside = harness.sign_in("admin", workspace=harness.other_workspace)
        agent = create_agent(inside, "Private Agent")

        listing = outside.get("/api/v1/agents").json()
        assert listing["total"] == 0
        assert listing["items"] == []

        # An id from another organization must be indistinguishable from a typo.
        assert outside.get(f"/api/v1/agents/{agent['id']}").status_code == 404
        assert (
            outside.put(
                f"/api/v1/agents/{agent['id']}", json=agent_payload(name="Stolen")
            ).status_code
            == 404
        )
        assert outside.delete(f"/api/v1/agents/{agent['id']}").status_code == 404
        assert outside.post(f"/api/v1/agents/{agent['id']}/executions").status_code == 404

    def test_executions_are_invisible_to_another_organization(self, harness: Harness) -> None:
        inside = harness.sign_in("admin")
        outside = harness.sign_in("admin", workspace=harness.other_workspace)
        agent = create_agent(inside, "Private Agent")
        activate(inside, agent["id"])
        execution = inside.post(f"/api/v1/agents/{agent['id']}/executions").json()

        assert outside.get("/api/v1/executions").json()["total"] == 0
        assert outside.get(f"/api/v1/executions/{execution['id']}").status_code == 404

    def test_the_same_agent_name_may_exist_in_both_organizations(self, harness: Harness) -> None:
        inside = harness.sign_in("admin")
        outside = harness.sign_in("admin", workspace=harness.other_workspace)

        create_agent(inside, "Shared Name")
        create_agent(outside, "Shared Name")

    def test_members_of_another_organization_are_not_listed_or_editable(
        self, harness: Harness
    ) -> None:
        inside = harness.sign_in("owner")
        outside = harness.sign_in("owner", workspace=harness.other_workspace)
        foreign_membership = harness.other_workspace.account("member").membership_id

        emails = {item["email"] for item in inside.get("/api/v1/members").json()["items"]}
        assert all(email.endswith("test-workspace.example.com") for email in emails)

        assert (
            inside.patch(
                f"/api/v1/members/{foreign_membership}", json={"role": "admin"}
            ).status_code
            == 404
        )
        assert inside.delete(f"/api/v1/members/{foreign_membership}").status_code == 404
        # The other organization can still manage its own.
        assert (
            outside.patch(
                f"/api/v1/members/{foreign_membership}", json={"role": "admin"}
            ).status_code
            == 200
        )


class TestMemberManagement:
    def test_a_viewer_may_list_members_but_not_change_them(self, harness: Harness) -> None:
        viewer = harness.sign_in("viewer")
        target = harness.workspace.account("member").membership_id

        assert viewer.get("/api/v1/members").status_code == 200
        assert viewer.patch(f"/api/v1/members/{target}", json={"role": "admin"}).status_code == 403
        assert viewer.delete(f"/api/v1/members/{target}").status_code == 403

    def test_an_administrator_cannot_touch_an_owner(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        owner_membership = harness.workspace.account("owner").membership_id

        assert (
            admin.patch(f"/api/v1/members/{owner_membership}", json={"role": "member"}).status_code
            == 403
        )
        assert admin.delete(f"/api/v1/members/{owner_membership}").status_code == 403

    def test_only_an_owner_grants_the_owner_role(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        owner = harness.sign_in("owner")
        target = harness.workspace.account("member").membership_id

        assert admin.patch(f"/api/v1/members/{target}", json={"role": "owner"}).status_code == 403
        assert owner.patch(f"/api/v1/members/{target}", json={"role": "owner"}).status_code == 200

    def test_nobody_edits_their_own_membership(self, harness: Harness) -> None:
        owner = harness.sign_in("owner")
        own_membership = harness.workspace.account("owner").membership_id

        assert (
            owner.patch(f"/api/v1/members/{own_membership}", json={"role": "viewer"}).status_code
            == 403
        )
        assert owner.delete(f"/api/v1/members/{own_membership}").status_code == 403

    def test_the_last_owner_cannot_be_demoted(self, harness: Harness) -> None:
        owner = harness.sign_in("owner")
        promoted = harness.workspace.account("admin").membership_id

        # Promote a second owner, who may then demote the first.
        assert owner.patch(f"/api/v1/members/{promoted}", json={"role": "owner"}).status_code == 200
        second_owner = harness.sign_in("admin")
        first_owner_membership = harness.workspace.account("owner").membership_id
        assert (
            second_owner.patch(
                f"/api/v1/members/{first_owner_membership}", json={"role": "member"}
            ).status_code
            == 200
        )
        # Now the promoted account is the only owner left.
        assert (
            second_owner.patch(f"/api/v1/members/{promoted}", json={"role": "admin"}).status_code
            == 403
        )

    def test_adding_a_member_requires_an_existing_account(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")

        response = admin.post(
            "/api/v1/members", json={"email": "stranger@example.com", "role": "member"}
        )

        assert response.status_code == 404
        assert "account" in response.json()["message"].lower()

    def test_an_account_from_another_organization_can_be_added(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        outsider = harness.other_workspace.account("member").email

        added = admin.post("/api/v1/members", json={"email": outsider, "role": "viewer"})

        assert added.status_code == 201
        assert added.json()["role"] == "viewer"
        assert (
            admin.post("/api/v1/members", json={"email": outsider, "role": "viewer"}).status_code
            == 409
        )


class TestOrganizationSwitching:
    def test_a_user_can_switch_to_another_organization_they_belong_to(
        self, harness: Harness
    ) -> None:
        admin = harness.sign_in("admin")
        outsider_email = harness.other_workspace.account("member").email
        admin.post("/api/v1/members", json={"email": outsider_email, "role": "admin"})

        outsider = harness.sign_in("member", workspace=harness.other_workspace)
        switched = outsider.post(
            "/api/v1/auth/organization", json={"organizationId": harness.workspace.organization_id}
        )

        assert switched.status_code == 200
        assert switched.json()["organization"]["slug"] == "test-workspace"
        assert switched.json()["role"] == "admin"

    def test_switching_to_an_organization_you_do_not_belong_to_is_refused(
        self, harness: Harness
    ) -> None:
        client = harness.sign_in("admin")

        response = client.post(
            "/api/v1/auth/organization",
            json={"organizationId": harness.other_workspace.organization_id},
        )

        assert response.status_code == 404
