"""Environment-based configuration.

Values come from environment variables and, optionally, a .env file in the
repository root. Unknown variables are ignored, so settings for later phases
are never loaded until code that needs them declares them explicitly.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

API_V1_PREFIX = "/api/v1"
SERVICE_NAME = "agenthub-backend"
SERVICE_VERSION = "0.2.0"

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

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

    @model_validator(mode="after")
    def _require_database_url_in_production(self) -> "Settings":
        if self.environment == "production" and not self.database_url:
            raise ValueError(
                "DATABASE_URL must be set when ENVIRONMENT=production. "
                "Refusing to fall back to a local development database."
            )
        return self

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
