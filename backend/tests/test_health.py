from fastapi.testclient import TestClient

from app.core.config import Settings
from tests.conftest import ClientFactory


def test_health_reports_backend_running(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "status": "ok",
        "service": "agenthub-backend",
        "version": "0.6.0",
        "message": "AgentHub backend is running.",
    }


def test_health_does_not_expose_configuration(client: TestClient) -> None:
    body = client.get("/api/v1/health").json()

    assert set(body) == {"status", "service", "version", "message"}


def test_health_rejects_unsupported_methods(client: TestClient) -> None:
    assert client.post("/api/v1/health").status_code == 405


def test_unknown_route_returns_404(client: TestClient) -> None:
    assert client.get("/api/v1/does-not-exist").status_code == 404


def test_api_docs_disabled_outside_development(client: TestClient) -> None:
    assert client.get("/api/docs").status_code == 404
    assert client.get("/api/openapi.json").status_code == 404


def test_api_docs_disabled_in_production(make_client: ClientFactory) -> None:
    with make_client("production") as production_client:
        assert production_client.get("/api/docs").status_code == 404
        assert production_client.get("/api/openapi.json").status_code == 404


def test_api_docs_enabled_in_development(make_client: ClientFactory) -> None:
    with make_client("development") as development_client:
        assert development_client.get("/api/openapi.json").status_code == 200


def test_settings_default_to_production() -> None:
    # Production also demands DATABASE_URL, so supply a throwaway one to read the default.
    settings = Settings(
        _env_file=None, database_url="postgresql+asyncpg://user@db.invalid/agenthub"
    )

    assert settings.environment == "production"
