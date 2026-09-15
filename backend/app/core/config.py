"""Environment-based configuration.

Values come from environment variables and, optionally, a `.env` file in the
repository root. Unknown variables are ignored, so settings for later phases
(for example `DATABASE_URL` or `LLM_API_KEY`) are never loaded until code that
needs them declares them explicitly.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

API_V1_PREFIX = "/api/v1"
SERVICE_NAME = "agenthub-backend"
SERVICE_VERSION = "0.1.0"

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

    @property
    def api_docs_enabled(self) -> bool:
        """Interactive API docs and the OpenAPI schema are development-only."""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
