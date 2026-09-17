"""AgentHub FastAPI application.

Run locally with:
    python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.router import api_router
from app.core.config import API_V1_PREFIX, SERVICE_VERSION, Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.security import configure_password_cost
from app.db.session import create_engine, create_session_factory
from app.runtime.worker import work_loop, worker_name
from app.services.login_guard import LoginGuard

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> FastAPI:
    """Build the application. Tests pass explicit settings and a session factory."""
    resolved = settings if settings is not None else get_settings()
    configure_logging()
    configure_password_cost(resolved.password_hash_cost_exponent)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if session_factory is not None:
            app.state.engine = None
            app.state.session_factory = session_factory
            yield
            return

        engine = create_engine(resolved)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        # Credentials are stripped before logging.
        logger.info("database configured: %s", resolved.safe_database_url)

        # The execution worker runs beside the API unless it is deployed
        # separately. It orchestrates runs; it executes no agent code.
        stop = asyncio.Event()
        worker: asyncio.Task[None] | None = None
        if resolved.runtime_worker_enabled:
            worker = asyncio.create_task(
                work_loop(app.state.session_factory, worker=worker_name(), stop=stop)
            )
        try:
            yield
        finally:
            stop.set()
            if worker is not None:
                with contextlib.suppress(asyncio.CancelledError, TimeoutError):
                    await asyncio.wait_for(worker, timeout=5)
            await engine.dispose()

    docs_enabled = resolved.api_docs_enabled
    app = FastAPI(
        title=resolved.app_name + " API",
        version=SERVICE_VERSION,
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = resolved
    # Per-process sign-in throttling; see app/services/login_guard.py.
    app.state.login_guard = LoginGuard(resolved)
    if session_factory is not None:
        # Injected by tests: usable without running the lifespan.
        app.state.engine = None
        app.state.session_factory = session_factory
    # Outermost middleware runs first on the way in and last on the way out.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(api_router, prefix=API_V1_PREFIX)
    return app


_app: FastAPI | None = None


def __getattr__(name: str) -> FastAPI:
    """Build the ASGI app on first access, so `app.main:app` still works.

    Importing this module must not require configuration; starting the server
    does. Without this, importing the package in a shell or a test would fail
    whenever DATABASE_URL is unset.
    """
    if name == "app":
        global _app
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(f"module {__name__} has no attribute {name}")
