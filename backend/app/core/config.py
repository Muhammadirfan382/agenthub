"""Environment-based configuration.

Values come from environment variables and, optionally, a .env file in the
repository root. Unknown variables are ignored, so settings for later phases
are never loaded until code that needs them declares them explicitly.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.security import DEFAULT_COST_EXPONENT, MIN_PRODUCTION_COST_EXPONENT

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

API_V1_PREFIX = "/api/v1"
SERVICE_NAME = "agenthub-backend"
SERVICE_VERSION = "0.6.0"

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

SESSION_COOKIE = "agenthub_session"
CSRF_COOKIE = "agenthub_csrf"
CSRF_HEADER = "X-CSRF-Token"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Local file database so development and tests run without Docker. Production
# must configure PostgreSQL explicitly (validated below).
DEV_DATABASE_URL = "sqlite+aiosqlite:///./agenthub-dev.db"

Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    """Runtime settings. Defaults are the secure choice."""

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # Unset means production: the most restrictive behaviour is the default.
    environment: Environment = "production"
    app_name: str = "AgentHub"

    # SQLAlchemy URL, e.g. postgresql+asyncpg://user:password@host:5432/agenthub
    database_url: str = ""
    db_echo: bool = False

    # --- Sessions -----------------------------------------------------------
    # A session dies at whichever comes first: the absolute lifetime, or the
    # idle timeout since it was last used.
    session_lifetime_minutes: int = 12 * 60
    session_idle_timeout_minutes: int = 60

    # scrypt work factor for new passwords (n = 2 ** exponent). Lowered only
    # in tests; production refuses anything weaker than the minimum.
    password_hash_cost_exponent: int = DEFAULT_COST_EXPONENT

    # --- Sandbox (Phase 6) ---------------------------------------------------
    # Agent execution belongs inside a container. Until one is available the
    # runtime records runs instead of executing anything; see app/sandbox.
    sandbox_enabled: bool = True
    #: The CLI used to start containers: `docker`, or anything compatible.
    sandbox_command: str = "docker"
    #: Always pinned to a tag. See agents/sandbox/Dockerfile.
    #: Must end in a tag or digest; may name a registry with a port. No
    #: whitespace and no leading "-", so it can never be read as a flag.
    sandbox_image: str = Field(
        default="agenthub/sandbox:0.6.0", pattern=r"^[A-Za-z0-9][^\s]*:[^\s:/]+$"
    )
    # The same floors app/sandbox/spec.py enforces, checked at startup: a bad
    # value should stop the process, not fail every run it later picks up.
    sandbox_memory_mb: int = Field(default=512, ge=64)
    sandbox_cpus: float = Field(default=1.0, gt=0)
    sandbox_pids_limit: int = Field(default=128, ge=8)
    sandbox_tmpfs_mb: int = Field(default=64, ge=1)
    sandbox_timeout_seconds: int = Field(default=60, gt=0)
    #: Refuse to run at all when the sandbox cannot be verified. Off by default
    #: so a machine without a container runtime still records runs honestly;
    #: turn it on where nothing may run unless it is provably isolated.
    require_sandbox: bool = False

    # --- Runtime ------------------------------------------------------------
    # Run the execution worker inside the API process. Turn it off to run
    # `python -m app.runtime.worker` separately instead.
    runtime_worker_enabled: bool = True

    # --- Login rate limiting (per process; see app/core/rate_limit.py) -------
    login_max_attempts: int = 5
    login_window_minutes: int = 15
    login_max_attempts_per_ip: int = 20

    @model_validator(mode="after")
    def _require_database_url_in_production(self) -> "Settings":
        if self.environment == "production" and not self.database_url:
            raise ValueError(
                "DATABASE_URL must be set when ENVIRONMENT=production. "
                "Refusing to fall back to a local development database."
            )
        return self

    @model_validator(mode="after")
    def _require_strong_password_hashing_in_production(self) -> "Settings":
        if (
            self.environment == "production"
            and self.password_hash_cost_exponent < MIN_PRODUCTION_COST_EXPONENT
        ):
            raise ValueError(
                "PASSWORD_HASH_COST_EXPONENT must be at least "
                f"{MIN_PRODUCTION_COST_EXPONENT} in production."
            )
        return self

    @property
    def cookie_secure(self) -> bool:
        """HTTPS-only cookies everywhere except local development over http."""
        return self.environment == "production"

    @property
    def api_docs_enabled(self) -> bool:
        """Interactive API docs and the OpenAPI schema are development-only."""
        return self.environment == "development"

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or DEV_DATABASE_URL

    @property
    def is_sqlite(self) -> bool:
        return self.resolved_database_url.startswith("sqlite")

    @property
    def safe_database_url(self) -> str:
        """The database URL with any password removed, for logs and diagnostics."""
        url = self.resolved_database_url
        if "@" not in url or "://" not in url:
            return url
        scheme, rest = url.split("://", 1)
        credentials, host = rest.rsplit("@", 1)
        user = credentials.split(":", 1)[0]
        return f"{scheme}://{user}:***@{host}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
