from typing import Any

from fastapi.testclient import TestClient

from tests.factories import agent_payload


def active_agent(client: TestClient, name: str) -> dict[str, Any]:
    agent: dict[str, Any] = client.post("/api/v1/agents", json=agent_payload(name=name)).json()
    client.patch(f"/api/v1/agents/{agent['id']}/status", json={"status": "active"})
    return agent


def test_lists_executions_newest_first_with_totals(client: TestClient) -> None:
    first = active_agent(client, "First Agent")
    second = active_agent(client, "Second Agent")
    client.post(f"/api/v1/agents/{first['id']}/executions")
    client.post(f"/api/v1/agents/{second['id']}/executions")

    body = client.get("/api/v1/executions").json()

    assert body["total"] == 2
    assert body["items"][0]["agentName"] in {"First Agent", "Second Agent"}
    assert body["items"][0]["status"] == "QUEUED"


def test_filters_by_agent_and_status(client: TestClient) -> None:
    agent = active_agent(client, "Filtered Agent")
    other = active_agent(client, "Other Agent")
    client.post(f"/api/v1/agents/{agent['id']}/executions")
    client.post(f"/api/v1/agents/{other['id']}/executions")

    assert client.get("/api/v1/executions", params={"agentId": agent["id"]}).json()["total"] == 1
    assert client.get("/api/v1/executions", params={"status": "QUEUED"}).json()["total"] == 2
    assert client.get("/api/v1/executions", params={"status": "COMPLETED"}).json()["total"] == 0
    assert client.get("/api/v1/executions", params={"search": "filtered"}).json()["total"] == 1


def test_rejects_an_unknown_status_filter(client: TestClient) -> None:
    assert client.get("/api/v1/executions", params={"status": "EXPLODED"}).status_code == 422


def test_detail_returns_an_empty_trace_until_the_runtime_exists(client: TestClient) -> None:
    agent = active_agent(client, "Traceable Agent")
    execution = client.post(f"/api/v1/agents/{agent['id']}/executions").json()

    detail = client.get(f"/api/v1/executions/{execution['id']}").json()

    assert detail["id"] == execution["id"]
    assert detail["tokenUsage"] == {"input": 0, "output": 0}
    assert detail["timeline"] == []
    assert detail["logs"] == []
    assert detail["toolCalls"] == []
    assert detail["error"] is None
    assert detail["result"] is None


def test_returns_404_for_an_unknown_execution(client: TestClient) -> None:
    response = client.get("/api/v1/executions/exe_missing")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_deleting_an_agent_removes_its_executions(client: TestClient) -> None:
    agent = active_agent(client, "Doomed Agent")
    execution = client.post(f"/api/v1/agents/{agent['id']}/executions").json()

    assert client.delete(f"/api/v1/agents/{agent['id']}").status_code == 204
    assert client.get(f"/api/v1/executions/{execution['id']}").status_code == 404
    assert client.get("/api/v1/executions").json()["total"] == 0
