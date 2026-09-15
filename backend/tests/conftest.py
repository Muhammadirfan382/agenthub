from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Environment, Settings
from app.main import create_app

ClientFactory = Callable[[Environment], TestClient]


def _build_client(environment: Environment) -> TestClient:
    # `_env_file=None` keeps a developer's local `.env` from influencing tests.
    settings = Settings(environment=environment, _env_file=None)
    return TestClient(create_app(settings))


@pytest.fixture
def make_client() -> ClientFactory:
    """Build a client for a specific environment (use as a context manager)."""
    return _build_client


@pytest.fixture
def client() -> Iterator[TestClient]:
    with _build_client("test") as test_client:
        yield test_client
