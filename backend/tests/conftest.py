"""Test fixtures.

Each test gets its own SQLite file, its own application instance and a freshly
seeded workspace: one organization with an account per role, plus a second
organization used to prove that data never crosses between them.

Clients sign in through the real login endpoint, so sessions, cookies and CSRF
tokens are exercised the same way a browser exercises them.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session as SyncSession
from sqlalchemy.pool import NullPool

from app.core.config import CSRF_COOKIE, CSRF_HEADER, Environment, Settings
from app.core.security import (
    MIN_PRODUCTION_COST_EXPONENT,
    configure_password_cost,
    hash_password,
)
from app.core.time import now_utc
from app.db import models  # noqa: F401  (registers tables on the metadata)
from app.db.base import Base
from app.db.models import Membership, Organization, User
from app.db.session import enable_sqlite_foreign_keys
from app.llm.gateway import ModelGateway, use_gateway
from app.main import create_app
from app.runtime.sandbox import use_sandbox
from app.sandbox import UnavailableSandbox
from app.schemas.enums import ROLES, Role
from app.security.egress import EgressBlocked, EgressGateway, use_egress

ClientFactory = Callable[[Environment], TestClient]


def runtime_settings(**overrides: Any) -> Settings:
    """Configuration for driving the engine directly in a test.

    The engine falls back to `get_settings()`, which reads the environment and
    — quite rightly — refuses to start a production deployment without a
    database URL. Tests say what they mean instead of relying on that fallback.
    """
    # Provider keys are read only under their namespaced names, from the
    # environment and from arguments alike.
    values = {_KEY_ALIASES.get(name, name): value for name, value in overrides.items()}
    return Settings(environment="development", **values)


_KEY_ALIASES = {
    "anthropic_api_key": "AGENTHUB_ANTHROPIC_API_KEY",
    "openai_api_key": "AGENTHUB_OPENAI_API_KEY",
}


# Throwaway credentials for a database that lives for one test.
TEST_PASSWORD = "correct-horse-battery-staple"
# scrypt at production strength would dominate the runtime of this suite.
TEST_COST_EXPONENT = 8


@dataclass(frozen=True)
class Account:
    user_id: str
    membership_id: str
    email: str
    role: Role


@dataclass(frozen=True)
class Workspace:
    """One organization and the accounts that can act in it."""

    organization_id: str
    accounts: dict[Role, Account]

    def account(self, role: Role) -> Account:
        return self.accounts[role]


def build_settings(environment: Environment = "test", **overrides: Any) -> Settings:
    # `_env_file=None` keeps a developer's local `.env` from influencing tests.
    # Production refuses a weak password cost and an open metrics endpoint, so
    # those settings meet both requirements.
    production = environment == "production"
    cost = MIN_PRODUCTION_COST_EXPONENT if production else TEST_COST_EXPONENT
    if production:
        overrides.setdefault("metrics_token", "a-test-scrape-token")
    return Settings(
        environment=environment,
        database_url="sqlite+aiosqlite://",
        password_hash_cost_exponent=cost,
        _env_file=None,
        **overrides,
    )


def _seed_workspace(sync_session: SyncSession, *, slug: str, password_hash: str) -> Workspace:
    now = now_utc()
    organization = Organization(
        id=f"org_{slug}", name=slug.replace("-", " ").title(), slug=slug, created_at=now
    )
    sync_session.add(organization)
    # These models have no relationships, so the unit of work does not order
    # the inserts for us: flush each level before the one that references it.
    sync_session.flush()

    accounts: dict[Role, Account] = {}
    for role in ROLES:
        user = User(
            id=f"usr_{slug}_{role}",
            email=f"{role}@{slug}.example.com",
            name=f"{role.title()} Person",
            password_hash=password_hash,
            status="active",
            timezone="UTC",
            created_at=now,
            updated_at=now,
        )
        membership = Membership(
            id=f"mem_{slug}_{role}",
            user_id=user.id,
            organization_id=organization.id,
            role=role,
            created_at=now,
        )
        sync_session.add(user)
        sync_session.flush()
        sync_session.add(membership)
        sync_session.flush()
        accounts[role] = Account(
            user_id=user.id, membership_id=membership.id, email=user.email, role=role
        )

    return Workspace(organization_id=organization.id, accounts=accounts)


@dataclass
class Harness:
    """Everything a test needs: application instances, workspaces and sign-in."""

    session_factory: async_sessionmaker[AsyncSession]
    workspace: Workspace
    other_workspace: Workspace
    clients: list[TestClient] = field(default_factory=list)

    def app_client(self, environment: Environment = "test", **settings: Any) -> TestClient:
        client = TestClient(
            create_app(build_settings(environment, **settings), self.session_factory)
        )
        self.clients.append(client)
        return client

    def sign_in(self, role: Role = "admin", *, workspace: Workspace | None = None) -> TestClient:
        """A signed-in client, with the CSRF token already echoed in a header."""
        target = workspace or self.workspace
        client = self.app_client()
        response = client.post(
            "/api/v1/auth/login",
            json={"email": target.account(role).email, "password": TEST_PASSWORD},
        )
        assert response.status_code == 200, response.text
        client.headers[CSRF_HEADER] = client.cookies[CSRF_COOKIE]
        return client


@pytest.fixture(autouse=True)
def sandbox_is_never_the_host_s() -> Iterator[None]:
    """No test starts a container on the machine running the suite.

    Without this, a developer or CI runner that happens to have Docker
    installed would quietly start real containers for every execution test,
    and the suite would behave differently depending on the host. Tests that
    care about sandbox behaviour substitute their own.
    """
    use_sandbox(UnavailableSandbox("Tests do not use the host's container runtime."))
    try:
        yield
    finally:
        use_sandbox(None)


@pytest.fixture(autouse=True)
def no_real_model_provider() -> Iterator[None]:
    """No test ever reaches a real model provider, whatever keys the host has.

    The default gateway has no providers, so runs are simulated. Tests that
    exercise model-driven runs substitute a gateway with a scripted provider.
    """
    use_gateway(ModelGateway(runtime_settings(), providers={}))
    try:
        yield
    finally:
        use_gateway(None)


async def _no_network(host: str) -> list[str]:
    raise EgressBlocked("resolution", f"Tests do not resolve {host}.")


@pytest.fixture(autouse=True)
def no_real_egress() -> Iterator[None]:
    """No test makes a real outbound request: names never resolve."""
    use_egress(EgressGateway(resolver=_no_network))
    try:
        yield
    finally:
        use_egress(None)


@pytest.fixture
def harness(tmp_path: object) -> Iterator[Harness]:
    configure_password_cost(TEST_COST_EXPONENT)
    database_path = f"{tmp_path}/agenthub-test.db".replace("\\", "/")

    # The schema is created with the synchronous driver so it does not depend
    # on the event loop the application later runs in.
    sync_engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    enable_sqlite_foreign_keys(sync_engine)
    Base.metadata.create_all(sync_engine)

    password_hash = hash_password(TEST_PASSWORD)
    with SyncSession(sync_engine) as sync_session:
        workspace = _seed_workspace(
            sync_session, slug="test-workspace", password_hash=password_hash
        )
        other = _seed_workspace(sync_session, slug="other-workspace", password_hash=password_hash)
        sync_session.commit()
    sync_engine.dispose()

    async_engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}", poolclass=NullPool)
    enable_sqlite_foreign_keys(async_engine)
    harness = Harness(
        session_factory=async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False),
        workspace=workspace,
        other_workspace=other,
    )
    try:
        yield harness
    finally:
        for client in harness.clients:
            client.close()


@pytest.fixture
def make_client(harness: Harness) -> ClientFactory:
    """An anonymous client for a specific environment."""
    return harness.app_client


@pytest.fixture
def anonymous_client(harness: Harness) -> TestClient:
    return harness.app_client()


@pytest.fixture
def client(harness: Harness) -> TestClient:
    """The default client for feature tests: signed in as an administrator."""
    return harness.sign_in("admin")


@pytest.fixture
def workspace(harness: Harness) -> Workspace:
    return harness.workspace
