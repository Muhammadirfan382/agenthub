from typing import Any

from fastapi.testclient import TestClient

from tests.factories import agent_payload, grant


def create_agent(client: TestClient, **overrides: object) -> dict[str, Any]:
    response = client.post("/api/v1/agents", json=agent_payload(**overrides))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


class TestCreate:
    def test_creates_a_draft_agent_with_server_derived_fields(self, client: TestClient) -> None:
        agent = create_agent(client, name="Research Helper")

        assert agent["id"].startswith("agt_research_helper_")
        # The client cannot choose these: the server decides.
        assert agent["status"] == "draft"
        assert agent["verification"] == "unverified"
        assert agent["riskLevel"] == "low"
        assert agent["riskScore"] == 5
        # Attributed to the signed-in user, not to anything the client sent.
        assert agent["creator"]["name"] == "Admin Person"
        # New agents are private until someone publishes and lists them.
        assert agent["visibility"] == "private"
        assert {check["status"] for check in agent["securityChecks"]} == {"not_run"}
        assert all(permission["scope"] == "Not granted" for permission in agent["permissions"])

    def test_derives_risk_from_granted_permissions(self, client: TestClient) -> None:
        payload = grant(
            agent_payload(name="Risky Agent"),
            "database_access",
            level="allowed",
            scope="Analytics warehouse",
            requiresApproval=True,
        )
        response = client.post("/api/v1/agents", json=payload)

        assert response.status_code == 201
        agent = response.json()
        assert agent["riskLevel"] == "critical"
        assert agent["riskScore"] > 80
        granted = next(p for p in agent["permissions"] if p["capability"] == "database_access")
        assert granted["risk"] == "critical"

    def test_rejects_a_duplicate_name(self, client: TestClient) -> None:
        create_agent(client, name="Only One")
        response = client.post("/api/v1/agents", json=agent_payload(name="Only One"))

        assert response.status_code == 409
        assert response.json()["code"] == "conflict"

    def test_ignores_client_supplied_risk(self, client: TestClient) -> None:
        payload = agent_payload(name="Liar Agent")
        payload["permissions"] = [{**p, "risk": "low"} for p in payload["permissions"]]
        payload = grant(
            payload,
            "code_execution",
            level="restricted",
            scope="Sandbox",
            requiresApproval=True,
            risk="low",
        )

        agent = client.post("/api/v1/agents", json=payload).json()
        code_execution = next(
            p for p in agent["permissions"] if p["capability"] == "code_execution"
        )
        assert code_execution["risk"] == "critical"
        assert agent["riskLevel"] == "critical"


class TestValidation:
    def test_reports_field_errors_with_a_consistent_shape(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/agents", json=agent_payload(name="x", description="too short")
        )

        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "validation_failed"
        fields = {detail["field"] for detail in body["details"]}
        assert {"name", "description"} <= fields

    def test_rejects_a_tool_without_its_capability(self, client: TestClient) -> None:
        response = client.post("/api/v1/agents", json=agent_payload(tools=["web_search"]))

        assert response.status_code == 422
        assert "web_access" in response.text

    def test_requires_approval_for_critical_capabilities(self, client: TestClient) -> None:
        payload = grant(
            agent_payload(), "code_execution", level="restricted", scope="Sandboxed tests"
        )
        response = client.post("/api/v1/agents", json=payload)

        assert response.status_code == 422
        assert "must require human approval" in response.text

    def test_requires_the_strict_sandbox_for_code_execution(self, client: TestClient) -> None:
        payload = grant(
            agent_payload(),
            "code_execution",
            level="restricted",
            scope="Tests",
            requiresApproval=True,
        )
        payload["securityPolicy"] = {**payload["securityPolicy"], "sandbox": "standard"}
        response = client.post("/api/v1/agents", json=payload)

        assert response.status_code == 422
        assert "strict sandbox" in response.text

    def test_requires_an_egress_allow_list_for_web_access(self, client: TestClient) -> None:
        payload = grant(agent_payload(), "web_access", level="restricted", scope="Docs only")
        response = client.post("/api/v1/agents", json=payload)
        assert response.status_code == 422
        assert "egress allow-list" in response.text

        payload["securityPolicy"] = {
            **payload["securityPolicy"],
            "networkEgress": "allow_list",
            "allowedDomains": ["https://*.example.com"],
        }
        response = client.post("/api/v1/agents", json=payload)
        assert response.status_code == 422
        assert "Invalid domain" in response.text

        payload["securityPolicy"] = {
            **payload["securityPolicy"],
            "allowedDomains": ["docs.example.com"],
        }
        assert client.post("/api/v1/agents", json=payload).status_code == 201

    def test_rejects_unknown_fields(self, client: TestClient) -> None:
        response = client.post("/api/v1/agents", json=agent_payload(isAdmin=True))
        assert response.status_code == 422

    def test_requires_every_capability_to_be_listed(self, client: TestClient) -> None:
        payload = agent_payload()
        payload["permissions"] = payload["permissions"][:3]
        response = client.post("/api/v1/agents", json=payload)

        assert response.status_code == 422
        assert "every capability" in response.text


class TestListAndRead:
    def test_paginates_and_reports_the_total(self, client: TestClient) -> None:
        for index in range(3):
            create_agent(client, name=f"Agent {index}")

        body = client.get("/api/v1/agents", params={"limit": 2}).json()
        assert body["total"] == 3
        assert len(body["items"]) == 2
        assert body["limit"] == 2
        assert body["offset"] == 0

        second = client.get("/api/v1/agents", params={"limit": 2, "offset": 2}).json()
        assert len(second["items"]) == 1

    def test_rejects_an_oversized_page(self, client: TestClient) -> None:
        assert client.get("/api/v1/agents", params={"limit": 5000}).status_code == 422

    def test_filters_by_search_status_and_category(self, client: TestClient) -> None:
        create_agent(client, name="Threat Triage", category="security")
        create_agent(client, name="Research Scout", category="research")

        assert client.get("/api/v1/agents", params={"search": "threat"}).json()["total"] == 1
        assert client.get("/api/v1/agents", params={"category": "security"}).json()["total"] == 1
        assert client.get("/api/v1/agents", params={"status": "active"}).json()["total"] == 0

    def test_sorts_by_name(self, client: TestClient) -> None:
        create_agent(client, name="Zulu Agent")
        create_agent(client, name="Alpha Agent")

        names = [
            item["name"]
            for item in client.get("/api/v1/agents", params={"sort": "name_asc"}).json()["items"]
        ]
        assert names == ["Alpha Agent", "Zulu Agent"]

    def test_returns_404_for_an_unknown_agent(self, client: TestClient) -> None:
        response = client.get("/api/v1/agents/agt_missing")
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"


class TestUpdateAndDelete:
    def test_updates_the_configuration_in_place(self, client: TestClient) -> None:
        agent = create_agent(client, name="Editable Agent")
        payload = agent_payload(
            name="Renamed Agent", version="1.1.0", description="An updated description for tests."
        )

        updated = client.put(f"/api/v1/agents/{agent['id']}", json=payload).json()

        assert updated["name"] == "Renamed Agent"
        assert updated["version"] == "1.1.0"
        assert updated["updatedAt"] >= agent["updatedAt"]
        # History is not written by editing: it is written by publishing.
        assert client.get(f"/api/v1/agents/{agent['id']}/versions").json()["total"] == 0

    def test_rejects_renaming_onto_an_existing_name(self, client: TestClient) -> None:
        create_agent(client, name="First Agent")
        second = create_agent(client, name="Second Agent")

        response = client.put(
            f"/api/v1/agents/{second['id']}", json=agent_payload(name="First Agent")
        )
        assert response.status_code == 409

    def test_deletes_an_agent(self, client: TestClient) -> None:
        agent = create_agent(client, name="Temporary Agent")

        assert client.delete(f"/api/v1/agents/{agent['id']}").status_code == 204
        assert client.get(f"/api/v1/agents/{agent['id']}").status_code == 404
        assert client.delete(f"/api/v1/agents/{agent['id']}").status_code == 404


class TestStatusAndExecution:
    def test_activates_an_agent_and_queues_an_execution(self, client: TestClient) -> None:
        agent = create_agent(client, name="Runnable Agent")

        activated = client.patch(
            f"/api/v1/agents/{agent['id']}/status", json={"status": "active"}
        ).json()
        assert activated["status"] == "active"

        response = client.post(f"/api/v1/agents/{agent['id']}/executions")
        assert response.status_code == 202
        execution = response.json()
        assert execution["status"] == "QUEUED"
        assert execution["agentName"] == "Runnable Agent"
        assert execution["endedAt"] is None

        refreshed = client.get(f"/api/v1/agents/{agent['id']}").json()
        assert refreshed["lastExecutionAt"] is not None

    def test_refuses_to_execute_an_agent_that_is_not_active(self, client: TestClient) -> None:
        agent = create_agent(client, name="Draft Agent")

        response = client.post(f"/api/v1/agents/{agent['id']}/executions")
        assert response.status_code == 422
        assert response.json()["code"] == "validation_failed"

    def test_rejects_an_unknown_status(self, client: TestClient) -> None:
        agent = create_agent(client, name="Status Agent")
        response = client.patch(f"/api/v1/agents/{agent['id']}/status", json={"status": "deleted"})
        assert response.status_code == 422
