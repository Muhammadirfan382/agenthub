from fastapi.testclient import TestClient

from app.core.middleware import REQUEST_ID_HEADER, SECURITY_HEADERS


def test_generates_a_request_id_when_none_is_supplied(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    request_id = response.headers.get(REQUEST_ID_HEADER)
    assert request_id and len(request_id) == 32


def test_echoes_a_safe_client_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={REQUEST_ID_HEADER: "req-123_abc"})

    assert response.headers[REQUEST_ID_HEADER] == "req-123_abc"


def test_replaces_an_unsafe_request_id(client: TestClient) -> None:
    response = client.get(
        "/api/v1/health", headers={REQUEST_ID_HEADER: "../../etc/passwd <script>"}
    )

    assert response.headers[REQUEST_ID_HEADER] != "../../etc/passwd <script>"


def test_sets_security_headers_on_api_responses(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    for header, value in SECURITY_HEADERS.items():
        assert response.headers[header] == value


def test_unknown_routes_use_the_shared_error_shape(client: TestClient) -> None:
    response = client.get("/api/v1/nope")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Not Found"}


def test_method_not_allowed_uses_the_shared_error_shape(client: TestClient) -> None:
    response = client.delete("/api/v1/health")

    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"


def test_malformed_json_is_reported_as_a_validation_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/agents",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"


def test_error_responses_never_leak_internals(client: TestClient) -> None:
    body = client.get("/api/v1/agents/agt_missing").text.lower()

    assert "traceback" not in body
    assert "sqlalchemy" not in body
    assert "sqlite" not in body
