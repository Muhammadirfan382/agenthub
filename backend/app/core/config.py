"""Environment-based configuration.

Values come from environment variables and, optionally, a .env file in the
repository root. Unknown variables are ignored, so settings for later phases
are never loaded until code that needs them declares them explicitly.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.security import DEFAULT_COST_EXPONENT, MIN_PRODUCTION_COST_EXPONENT
from app.llm.routing import ROUTE_PATTERN

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

API_V1_PREFIX = "/api/v1"
SERVICE_NAME = "agenthub-backend"
SERVICE_VERSION = "0.9.0"

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

    # --- Model gateway (Phase 7) --------------------------------------------
    # Credentials are read here, handed to the provider SDKs by the gateway, and
    # never logged, returned by the API, sent to the browser or placed in a
    # sandbox. Leave a key unset to leave that provider off.
    #
    # The variables are namespaced on purpose. A plain ANTHROPIC_API_KEY or
    # OPENAI_API_KEY is often set machine-wide for other tools; AgentHub must
    # never pick up a credential nobody configured for it.
    models_enabled: bool = True
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias="AGENTHUB_ANTHROPIC_API_KEY"
    )
    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias="AGENTHUB_OPENAI_API_KEY"
    )
    #: Which real model answers for each tier, as provider:model.
    model_route_fast_small: str = Field(default="anthropic:claude-haiku-4-5", pattern=ROUTE_PATTERN)
    model_route_balanced_large: str = Field(
        default="anthropic:claude-sonnet-5", pattern=ROUTE_PATTERN
    )
    model_route_reasoning_large: str = Field(
        default="anthropic:claude-opus-5", pattern=ROUTE_PATTERN
    )
    model_request_timeout_seconds: int = Field(default=180, ge=5, le=900)
    #: Model turns one run may take before it is stopped.
    model_max_turns: int = Field(default=8, ge=1, le=50)
    #: Per organization, per process (see app/core/rate_limit.py).
    model_requests_per_minute_per_org: int = Field(default=30, ge=1)
    #: Per organization per UTC day, across every run, counted from the ledger.
    model_daily_token_limit_per_org: int = Field(default=2_000_000, ge=1_000)

    @field_validator("otlp_endpoint", "alert_webhook_url")
    @classmethod
    def _https_or_unset(cls, value: str) -> str:
        # A collector may sit on plain http inside a cluster; a webhook leaves it.
        value = value.strip()
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("Must be an http(s) URL, or empty.")
        return value

    @field_validator("alert_webhook_url")
    @classmethod
    def _webhook_is_https(cls, value: str) -> str:
        if value and not value.startswith("https://"):
            raise ValueError("ALERT_WEBHOOK_URL must be https.")
        return value

    @field_validator("anthropic_api_key", "openai_api_key", "metrics_token", mode="before")
    @classmethod
    def _blank_key_means_unset(cls, value: object) -> object:
        # `ANTHROPIC_API_KEY=` in a .env file is "not configured", not an empty key.
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    # --- Observability (Phase 9) ---------------------------------------------
    #: Serve /metrics in Prometheus format. The endpoint carries counts only:
    #: no organization ids, no content, nothing personal.
    metrics_enabled: bool = True
    #: When set, /metrics requires `Authorization: Bearer <token>`. Leave unset
    #: on a network where only the scraper can reach the port.
    metrics_token: SecretStr | None = None
    #: An OTLP/HTTP collector for traces. Unset means spans stay in the process
    #: and are only used to correlate logs.
    otlp_endpoint: str = ""
    #: How often the worker evaluates alert rules.
    alert_interval_seconds: int = Field(default=60, ge=10, le=3600)
    #: Failed runs in the last 15 minutes before `runs_failing` fires.
    alert_failed_runs: int = Field(default=3, ge=1)
    #: Policy refusals in the last 15 minutes before `policy_denials` fires.
    alert_policy_denials: int = Field(default=10, ge=1)
    #: A claimed run whose worker has not been heard from for this long is stalled.
    alert_stalled_run_seconds: int = Field(default=300, ge=60)
    #: Optional operator webhook for new alerts: an https URL on a public host.
    #: It is sent alert metadata only, never run content.
    alert_webhook_url: str = ""

    # --- Egress (Phase 8) ----------------------------------------------------
    #: Let `api_request` actually run: HTTPS GET to the agent's allowed domains
    #: only, through app/security/egress.py. Off means every tool is recorded as
    #: not executed, as before.
    egress_enabled: bool = True
    #: How much fetched text a model is given per tool call.
    egress_max_tool_output_chars: int = Field(default=20_000, ge=1_000, le=200_000)

    # --- Runtime ------------------------------------------------------------
    # Run the execution worker inside the API process. Turn it off to run
    # `python -m app.runtime.worker` separately instead.
    runtime_worker_enabled: bool = True

    #: State-changing requests per client per minute (see app/core/middleware.py).
    write_requests_per_minute: int = Field(default=120, ge=10)

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

    @model_validator(mode="after")
    def _require_metrics_token_in_production(self) -> "Settings":
        # The scrape endpoint names no organization or person, but request
        # volumes and failure rates are still operational detail.
        if self.environment == "production" and self.metrics_enabled and not self.metrics_token:
            raise ValueError(
                "METRICS_TOKEN must be set when metrics are enabled and "
                "ENVIRONMENT=production (or set METRICS_ENABLED=false)."
            )
        return self

    @property
    def service_version(self) -> str:
        return SERVICE_VERSION

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
    """Settings from the environment, a .env file and, optionally, secret files.

    ``SECRETS_DIR`` points at a directory of files named after settings - the way
    Docker and Kubernetes mount secrets - e.g. ``AGENTHUB_ANTHROPIC_API_KEY`` or
    ``database_url``, each holding only the value. Environment variables take
    precedence over files. A configured directory that does not exist stops the
    process rather than silently running without its secrets.
    """
    secrets_dir = os.environ.get("SECRETS_DIR", "").strip()
    if not secrets_dir:
        return Settings()
    if not Path(secrets_dir).is_dir():
        raise RuntimeError(f"SECRETS_DIR is set to {secrets_dir!r}, which is not a directory.")
    return Settings(_secrets_dir=secrets_dir)
