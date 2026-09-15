"""AgentHub FastAPI application.

Run locally with:
    python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import API_V1_PREFIX, SERVICE_VERSION, Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Tests pass explicit settings."""
    resolved = settings if settings is not None else get_settings()
    docs_enabled = resolved.api_docs_enabled

    app = FastAPI(
        title=f"{resolved.app_name} API",
        version=SERVICE_VERSION,
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
    )
    app.state.settings = resolved
    app.include_router(api_router, prefix=API_V1_PREFIX)
    return app


app = create_app()
