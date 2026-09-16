"""Engine and session lifecycle.

One engine per application, one session per request. Routes receive a session
through the SessionDep dependency and never build their own.
"""

from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import Engine, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def enable_sqlite_foreign_keys(engine: AsyncEngine | Engine) -> None:
    """Make SQLite enforce foreign keys, which it skips unless asked per connection.

    Without this, ON DELETE CASCADE quietly does nothing on SQLite while it
    works on PostgreSQL, so local runs and tests would disagree with production.
    """
    target = engine.sync_engine if isinstance(engine, AsyncEngine) else engine

    @event.listens_for(target, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_engine(settings: Settings) -> AsyncEngine:
    kwargs: dict[str, object] = {"echo": settings.db_echo, "future": True}
    if not settings.is_sqlite:
        # Verify pooled connections before use so a restarted database does not
        # surface as a request failure.
        kwargs["pool_pre_ping"] = True
    engine = create_async_engine(settings.resolved_database_url, **kwargs)
    if settings.is_sqlite:
        enable_sqlite_foreign_keys(engine)
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]
