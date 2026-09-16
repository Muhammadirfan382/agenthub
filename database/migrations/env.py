"""Alembic environment.

The database URL comes from application settings, so migrations and the
application always agree. Override it for one run with:

    python -m alembic -x db_url=postgresql+asyncpg://... upgrade head
"""

import asyncio
from collections.abc import Iterable

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.db import models  # noqa: F401  (imported so tables register on the metadata)
from app.db.base import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    overrides: dict[str, str] = context.get_x_argument(as_dictionary=True)
    return overrides.get("db_url") or get_settings().resolved_database_url


def _configure(connection: Connection | None = None, url: str | None = None) -> None:
    context.configure(
        connection=connection,
        url=url,
        target_metadata=target_metadata,
        compare_type=True,
        # SQLite cannot ALTER most things in place; batch mode rewrites tables.
        render_as_batch=True,
    )


def run_migrations_offline() -> None:
    _configure(url=_database_url())
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online_async() -> None:
    engine = create_async_engine(_database_url(), future=True)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run)
            await connection.commit()
    finally:
        await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_migrations_online_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


__all__: Iterable[str] = ()
