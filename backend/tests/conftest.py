from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Environment, Settings
from app.db import models  # noqa: F401  (registers tables on the metadata)
from app.db.base import Base
from app.db.session import enable_sqlite_foreign_keys
from app.main import create_app

ClientFactory = Callable[[Environment], TestClient]


def build_settings(environment: Environment = "test") -> Settings:
    # `_env_file=None` keeps a developer's local `.env` from influencing tests.
    return Settings(environment=environment, database_url="sqlite+aiosqlite://", _env_file=None)


def _session_factory(database_path: str) -> async_sessionmaker[AsyncSession]:
    """A fresh SQLite database per test.

    The schema is created with the synchronous driver so it does not depend on
    the event loop the application later runs in.
    """
    sync_engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()

    async_engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}", poolclass=NullPool)
    enable_sqlite_foreign_keys(async_engine)
    return async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)


@pytest.fixture
def make_client(tmp_path: object) -> ClientFactory:
    """Build a client for a specific environment (use as a context manager)."""

    def factory(environment: Environment) -> TestClient:
        database_path = f"{tmp_path}/agenthub-{environment}.db".replace("\\", "/")
        app = create_app(
            build_settings(environment), session_factory=_session_factory(database_path)
        )
        return TestClient(app)

    return factory


@pytest.fixture
def client(make_client: ClientFactory) -> Iterator[TestClient]:
    with make_client("test") as test_client:
        yield test_client
