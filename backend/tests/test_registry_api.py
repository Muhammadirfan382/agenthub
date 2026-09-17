"""The registry: publishing manifests, listing them, and installing with grants."""

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import Harness, Workspace
from tests.factories import agent_payload, grant


def create_agent(client: TestClient, name: str, **overrides: Any) -> dict[str, Any]:
    response = client.post("/api/v1/agents", json=agent_payload(name=name, **overrides))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def publish(client: TestClient, agent_id: str, **body: Any) -> dict[str, Any]:
    response = client.post(f"/api/v1/agents/{agent_id}/versions", json=body)
    assert response.status_code == 201, response.text
    version: dict[str, Any] = response.json()
    return version


def set_visibility(client: TestClient, agent_id: str, visibility: str) -> None:
    response = client.patch(
        f"/api/v1/agents/{agent_id}/visibility", json={"visibility": visibility}
    )
    assert response.status_code == 200, response.text


def a_web_agent(name: str) -> dict[str, Any]:
    """An agent that asks for restricted web access and one tool."""
    payload = agent_payload(
        name=name,
        tools=["web_search"],
        securityPolicy={
            "sandbox": "strict",
            "networkEgress": "allow_list",
            "allowedDomains": ["docs.example.com"],
            "approvalRequiredFor": ["high", "critical"],
            "auditLogging": True,
        },
    )
    return grant(payload, "web_access", level="restricted", scope="Allow-listed documentation")


def publish_public_agent(
    harness: Harness, *, workspace: Workspace, name: str = "Shared Research Agent"
) -> tuple[str, dict[str, Any]]:
    """Publishes a listed agent in one organization and returns (agentId, version)."""
    publisher = harness.sign_in("admin", workspace=workspace)
    response = publisher.post("/api/v1/agents", json=a_web_agent(name))
    assert response.status_code == 201, response.text
    agent = response.json()
    version = publish(publisher, agent["id"], changelog=["First public release."])
    set_visibility(publisher, agent["id"], "public")
    return agent["id"], version


class TestPublishing:
    def test_publishes_a_frozen_manifest(self, client: TestClient) -> None:
        agent = create_agent(client, "Publishable Agent")

        version = publish(client, agent["id"], changelog=["First release."])

        assert version["status"] == "published"
        assert version["version"] == "1.0.0"
        assert version["changelog"] == ["First release."]
        assert version["publishedAt"] is not None
        manifest = version["manifest"]
        assert manifest["name"] == "Publishable Agent"
        # Permissions are requests in a manifest, and are named as such.
        assert len(manifest["requiredPermissions"]) == 7
        assert version["createdBy"] == "Admin Person"

    def test_editing_the_agent_does_not_change_a_published_version(
        self, client: TestClient
    ) -> None:
        agent = create_agent(client, "Frozen Agent")
        version = publish(client, agent["id"])

        client.put(
            f"/api/v1/agents/{agent['id']}",
            json=agent_payload(
                name="Renamed Later",
                version="2.0.0",
                description="A completely different description now.",
            ),
        )

        stored = client.get(f"/api/v1/agents/{agent['id']}/versions/{version['id']}").json()
        assert stored["manifest"]["name"] == "Frozen Agent"
        assert stored["manifest"]["version"] == "1.0.0"

    def test_refuses_to_publish_the_same_version_twice(self, client: TestClient) -> None:
        agent = create_agent(client, "Duplicate Version Agent")
        publish(client, agent["id"])

        again = client.post(f"/api/v1/agents/{agent['id']}/versions", json={})

        assert again.status_code == 409
        assert "already published" in again.json()["message"]

    def test_lists_versions_newest_first(self, client: TestClient) -> None:
        agent = create_agent(client, "Historic Agent")
        publish(client, agent["id"])
        client.put(
            f"/api/v1/agents/{agent['id']}",
            json=agent_payload(name="Historic Agent", version="1.1.0"),
        )
        publish(client, agent["id"], changelog=["Second release."])

        body = client.get(f"/api/v1/agents/{agent['id']}/versions").json()

        assert body["total"] == 2
        assert [item["version"] for item in body["items"]] == ["1.1.0", "1.0.0"]

    def test_a_member_publishes_their_own_agent_only(self, harness: Harness) -> None:
        member = harness.sign_in("member")
        admin = harness.sign_in("admin")
        own = create_agent(member, "Member Owned")
        other = create_agent(admin, "Admin Owned")

        assert member.post(f"/api/v1/agents/{own['id']}/versions", json={}).status_code == 201
        refused = member.post(f"/api/v1/agents/{other['id']}/versions", json={})
        assert refused.status_code == 403

    def test_a_viewer_cannot_publish(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        viewer = harness.sign_in("viewer")
        agent = create_agent(admin, "Viewer Test Agent")

        assert viewer.post(f"/api/v1/agents/{agent['id']}/versions", json={}).status_code == 403

    def test_deprecating_a_version_removes_it_from_the_marketplace(self, harness: Harness) -> None:
        publisher = harness.sign_in("admin")
        agent = create_agent(publisher, "Deprecated Agent")
        version = publish(publisher, agent["id"])
        set_visibility(publisher, agent["id"], "organization")
        assert publisher.get("/api/v1/marketplace").json()["total"] == 1

        deprecated = publisher.patch(
            f"/api/v1/agents/{agent['id']}/versions/{version['id']}",
            json={"status": "deprecated"},
        )

        assert deprecated.status_code == 200
        assert deprecated.json()["deprecatedAt"] is not None
        assert publisher.get("/api/v1/marketplace").json()["total"] == 0


class TestVisibility:
    def test_listing_requires_a_published_version(self, client: TestClient) -> None:
        agent = create_agent(client, "Unpublished Agent")

        response = client.patch(
            f"/api/v1/agents/{agent['id']}/visibility", json={"visibility": "public"}
        )

        assert response.status_code == 422
        assert "Publish a version" in response.json()["message"]

    def test_private_agents_are_never_listed(self, client: TestClient) -> None:
        agent = create_agent(client, "Private Agent")
        publish(client, agent["id"])

        assert client.get("/api/v1/agents").json()["total"] == 1
        # Published, but nobody chose to share it.
        assert client.get("/api/v1/marketplace").json()["total"] == 0

    def test_organization_visibility_stays_inside_the_organization(self, harness: Harness) -> None:
        inside = harness.sign_in("admin")
        outside = harness.sign_in("admin", workspace=harness.other_workspace)
        agent = create_agent(inside, "Internal Agent")
        publish(inside, agent["id"])
        set_visibility(inside, agent["id"], "organization")

        assert inside.get("/api/v1/marketplace").json()["total"] == 1
        assert outside.get("/api/v1/marketplace").json()["total"] == 0

    def test_public_agents_are_visible_to_other_organizations(self, harness: Harness) -> None:
        publish_public_agent(harness, workspace=harness.other_workspace)
        reader = harness.sign_in("viewer")

        body = reader.get("/api/v1/marketplace").json()

        assert body["total"] == 1
        listing = body["items"][0]
        assert listing["name"] == "Shared Research Agent"
        assert listing["publisher"] == "Other Workspace"
        assert listing["own"] is False
        assert listing["installed"] is False


class TestMarketplace:
    def test_lists_only_the_newest_published_version(self, harness: Harness) -> None:
        publisher = harness.sign_in("admin")
        agent = create_agent(publisher, "Evolving Agent")
        publish(publisher, agent["id"])
        publisher.put(
            f"/api/v1/agents/{agent['id']}",
            json=agent_payload(name="Evolving Agent", version="2.0.0"),
        )
        publish(publisher, agent["id"])
        set_visibility(publisher, agent["id"], "organization")

        body = publisher.get("/api/v1/marketplace").json()

        assert body["total"] == 1
        assert body["items"][0]["version"] == "2.0.0"

    def test_filters_by_search_category_and_tag(self, harness: Harness) -> None:
        publisher = harness.sign_in("admin")
        first = create_agent(publisher, "Finance Helper", category="data", tags=["finance"])
        second = create_agent(publisher, "Support Helper", category="support", tags=["support"])
        for agent in (first, second):
            publish(publisher, agent["id"])
            set_visibility(publisher, agent["id"], "organization")

        assert publisher.get("/api/v1/marketplace?search=finance").json()["total"] == 1
        assert publisher.get("/api/v1/marketplace?category=support").json()["total"] == 1
        assert publisher.get("/api/v1/marketplace?tag=finance").json()["total"] == 1
        assert publisher.get("/api/v1/marketplace?tag=nothing").json()["total"] == 0
        # Nothing is verified: verification is a review process that does not exist.
        assert publisher.get("/api/v1/marketplace?verified=true").json()["total"] == 0

    def test_reports_the_tags_in_use(self, harness: Harness) -> None:
        publisher = harness.sign_in("admin")
        agent = create_agent(publisher, "Tagged Agent", tags=["alpha", "beta"])
        publish(publisher, agent["id"])
        set_visibility(publisher, agent["id"], "organization")

        assert publisher.get("/api/v1/marketplace/tags").json() == ["alpha", "beta"]

    def test_detail_includes_the_manifest(self, harness: Harness) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        reader = harness.sign_in("member")

        listing = reader.get(f"/api/v1/marketplace/{version['id']}").json()

        assert listing["manifest"]["tools"] == ["web_search"]
        assert listing["changelog"] == ["First public release."]

    def test_an_unlisted_version_is_not_found(self, harness: Harness) -> None:
        publisher = harness.sign_in("admin")
        agent = create_agent(publisher, "Hidden Agent")
        version = publish(publisher, agent["id"])
        outsider = harness.sign_in("admin", workspace=harness.other_workspace)

        assert outsider.get(f"/api/v1/marketplace/{version['id']}").status_code == 404


class TestInstalling:
    def test_grants_nothing_that_was_not_asked_for(self, harness: Harness) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        installer = harness.sign_in("admin")

        response = installer.post(
            "/api/v1/installations",
            json={
                "agentVersionId": version["id"],
                "grants": [
                    {
                        "capability": "web_access",
                        "level": "read_only",
                        "scope": "Public documentation only",
                    }
                ],
            },
        )

        assert response.status_code == 201, response.text
        installation = response.json()
        levels = {grant["capability"]: grant["level"] for grant in installation["grants"]}
        assert levels["web_access"] == "read_only"
        # Everything else is denied without being mentioned.
        assert {level for capability, level in levels.items() if capability != "web_access"} == {
            "denied"
        }
        assert installation["riskLevel"] == "low"
        assert installation["status"] == "active"
        assert installation["unusableTools"] == []

    def test_refuses_to_grant_more_than_the_manifest_asked_for(self, harness: Harness) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        installer = harness.sign_in("admin")

        response = installer.post(
            "/api/v1/installations",
            json={
                "agentVersionId": version["id"],
                "grants": [{"capability": "web_access", "level": "allowed", "scope": "Everything"}],
            },
        )

        assert response.status_code == 422
        assert "more than the agent asked for" in response.json()["message"]

    def test_refuses_a_capability_the_agent_declared_as_denied(self, harness: Harness) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        installer = harness.sign_in("admin")

        response = installer.post(
            "/api/v1/installations",
            json={
                "agentVersionId": version["id"],
                "grants": [
                    {
                        "capability": "code_execution",
                        "level": "restricted",
                        "scope": "Nothing really",
                        "requiresApproval": True,
                    }
                ],
            },
        )

        assert response.status_code == 422
        # The manifest lists code_execution as denied, so nothing can be granted.
        assert "more than the agent asked for (denied)" in response.json()["message"]

    def test_requires_a_scope_for_anything_granted(self, harness: Harness) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        installer = harness.sign_in("admin")

        response = installer.post(
            "/api/v1/installations",
            json={
                "agentVersionId": version["id"],
                "grants": [{"capability": "web_access", "level": "restricted", "scope": ""}],
            },
        )

        assert response.status_code == 422
        assert "scope" in response.json()["message"].lower()

    def test_an_approval_requirement_cannot_be_removed(self, harness: Harness) -> None:
        publisher = harness.sign_in("admin", workspace=harness.other_workspace)
        payload = grant(
            agent_payload(
                name="Approval Agent",
                securityPolicy={
                    "sandbox": "strict",
                    "networkEgress": "allow_list",
                    "allowedDomains": ["api.example.com"],
                    "approvalRequiredFor": ["high", "critical"],
                    "auditLogging": True,
                },
            ),
            "api_access",
            level="restricted",
            scope="Ticketing API",
            requiresApproval=True,
        )
        agent = publisher.post("/api/v1/agents", json=payload).json()
        version = publish(publisher, agent["id"])
        set_visibility(publisher, agent["id"], "public")
        installer = harness.sign_in("admin")

        response = installer.post(
            "/api/v1/installations",
            json={
                "agentVersionId": version["id"],
                "grants": [
                    {
                        "capability": "api_access",
                        "level": "restricted",
                        "scope": "Our ticketing API",
                        "requiresApproval": False,
                    }
                ],
            },
        )

        assert response.status_code == 422
        assert "approval" in response.json()["message"].lower()

    def test_reports_tools_that_cannot_work_with_the_granted_permissions(
        self, harness: Harness
    ) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        installer = harness.sign_in("admin")

        installation = installer.post(
            "/api/v1/installations", json={"agentVersionId": version["id"], "grants": []}
        ).json()

        # Granting nothing is allowed, and the answer says what that costs.
        assert installation["unusableTools"] == ["web_search"]
        assert installation["riskLevel"] == "low"

    def test_only_administrators_install(self, harness: Harness) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        member = harness.sign_in("member")
        viewer = harness.sign_in("viewer")

        for client in (member, viewer):
            response = client.post(
                "/api/v1/installations", json={"agentVersionId": version["id"], "grants": []}
            )
            assert response.status_code == 403

    def test_installing_your_own_agent_is_refused(self, harness: Harness) -> None:
        installer = harness.sign_in("admin")
        agent = create_agent(installer, "Home Agent")
        version = publish(installer, agent["id"])
        set_visibility(installer, agent["id"], "organization")

        response = installer.post(
            "/api/v1/installations", json={"agentVersionId": version["id"], "grants": []}
        )

        assert response.status_code == 409
        assert "already belongs" in response.json()["message"]

    def test_an_agent_is_installed_once(self, harness: Harness) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        installer = harness.sign_in("admin")
        body = {"agentVersionId": version["id"], "grants": []}

        assert installer.post("/api/v1/installations", json=body).status_code == 201
        assert installer.post("/api/v1/installations", json=body).status_code == 409

    def test_installations_belong_to_one_organization(self, harness: Harness) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        installer = harness.sign_in("admin")
        installation = installer.post(
            "/api/v1/installations", json={"agentVersionId": version["id"], "grants": []}
        ).json()

        outsider = harness.sign_in("admin", workspace=harness.other_workspace)

        assert installer.get("/api/v1/installations").json()["total"] == 1
        assert outsider.get("/api/v1/installations").json()["total"] == 0
        assert outsider.get(f"/api/v1/installations/{installation['id']}").status_code == 404
        assert outsider.delete(f"/api/v1/installations/{installation['id']}").status_code == 404

    def test_a_listing_shows_that_it_is_installed(self, harness: Harness) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        installer = harness.sign_in("admin")
        installation = installer.post(
            "/api/v1/installations", json={"agentVersionId": version["id"], "grants": []}
        ).json()

        listing = installer.get("/api/v1/marketplace").json()["items"][0]

        assert listing["installed"] is True
        assert listing["installationId"] == installation["id"]


class TestManagingInstallations:
    def test_changes_grants_and_recomputes_risk(self, harness: Harness) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        installer = harness.sign_in("admin")
        installation = installer.post(
            "/api/v1/installations", json={"agentVersionId": version["id"], "grants": []}
        ).json()

        updated = installer.patch(
            f"/api/v1/installations/{installation['id']}",
            json={
                "grants": [
                    {
                        "capability": "web_access",
                        "level": "restricted",
                        "scope": "Allow-listed docs",
                    }
                ],
                "note": "Narrowed to documentation.",
            },
        )

        assert updated.status_code == 200
        body = updated.json()
        assert body["riskLevel"] == "medium"
        assert body["note"] == "Narrowed to documentation."
        assert body["unusableTools"] == []

    def test_suspends_and_resumes(self, harness: Harness) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        installer = harness.sign_in("admin")
        installation = installer.post(
            "/api/v1/installations", json={"agentVersionId": version["id"], "grants": []}
        ).json()

        suspended = installer.patch(
            f"/api/v1/installations/{installation['id']}", json={"status": "suspended"}
        )
        assert suspended.json()["status"] == "suspended"

        resumed = installer.patch(
            f"/api/v1/installations/{installation['id']}", json={"status": "active"}
        )
        assert resumed.json()["status"] == "active"

    def test_flags_a_newer_published_version(self, harness: Harness) -> None:
        agent_id, version = publish_public_agent(harness, workspace=harness.other_workspace)
        installer = harness.sign_in("admin")
        installation = installer.post(
            "/api/v1/installations", json={"agentVersionId": version["id"], "grants": []}
        ).json()
        assert installation["updateAvailable"] is False

        publisher = harness.sign_in("admin", workspace=harness.other_workspace)
        publisher.put(
            f"/api/v1/agents/{agent_id}",
            json={**a_web_agent("Shared Research Agent"), "version": "1.1.0"},
        )
        publish(publisher, agent_id)

        refreshed = installer.get(f"/api/v1/installations/{installation['id']}").json()
        assert refreshed["updateAvailable"] is True
        # The installation still holds the version it was granted against.
        assert refreshed["version"] == "1.0.0"

    def test_uninstalling_removes_it(self, harness: Harness) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        installer = harness.sign_in("admin")
        installation = installer.post(
            "/api/v1/installations", json={"agentVersionId": version["id"], "grants": []}
        ).json()

        assert installer.delete(f"/api/v1/installations/{installation['id']}").status_code == 204
        assert installer.get("/api/v1/installations").json()["total"] == 0
        assert installer.get("/api/v1/marketplace").json()["items"][0]["installed"] is False

    def test_a_viewer_can_read_but_not_change_installations(self, harness: Harness) -> None:
        _, version = publish_public_agent(harness, workspace=harness.other_workspace)
        installer = harness.sign_in("admin")
        installation = installer.post(
            "/api/v1/installations", json={"agentVersionId": version["id"], "grants": []}
        ).json()
        viewer = harness.sign_in("viewer")

        assert viewer.get("/api/v1/installations").status_code == 200
        assert (
            viewer.patch(
                f"/api/v1/installations/{installation['id']}", json={"status": "suspended"}
            ).status_code
            == 403
        )
        assert viewer.delete(f"/api/v1/installations/{installation['id']}").status_code == 403
