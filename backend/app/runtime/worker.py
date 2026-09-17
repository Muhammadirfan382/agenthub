"""The worker that picks up queued executions and walks them.

Durability comes from the database, not from memory: a run is claimed by
writing the claim, and progress is written after every step. If a worker dies,
its heartbeat goes stale and another worker reclaims the run from the step it
reached.

    .venv/Scripts/python.exe -m app.runtime.worker
"""

import asyncio
import contextlib
import logging
import os
import socket
import uuid

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.time import now_utc
from app.db.models import Execution
from app.db.session import create_engine, create_session_factory
from app.runtime.engine import run_to_completion, stale_before

logger = logging.getLogger(__name__)

#: A run whose worker has not been heard from for this long is up for grabs.
STALE_CLAIM_SECONDS = 60
POLL_SECONDS = 1.0


def worker_name() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"


async def claim_next(session: AsyncSession, *, worker: str) -> Execution | None:
    """Takes one runnable execution, if there is one nobody else is running.

    The claim is a conditional UPDATE, so two workers racing for the same row
    cannot both win: the second one updates zero rows and moves on.
    """
    cutoff = stale_before(STALE_CLAIM_SECONDS)
    candidate = await session.scalar(
        select(Execution)
        .where(
            Execution.status.in_(["QUEUED", "STARTING", "RUNNING", "WAITING_FOR_TOOL"]),
            or_(
                Execution.claimed_by.is_(None),
                Execution.heartbeat_at.is_(None),
                Execution.heartbeat_at < cutoff,
            ),
        )
        .order_by(Execution.started_at.asc())
        .limit(1)
    )
    if candidate is None:
        return None

    now = now_utc()
    claimed = await session.execute(
        update(Execution)
        .where(
            Execution.id == candidate.id,
            Execution.status.in_(["QUEUED", "STARTING", "RUNNING", "WAITING_FOR_TOOL"]),
            or_(
                Execution.claimed_by.is_(None),
                Execution.heartbeat_at.is_(None),
                Execution.heartbeat_at < cutoff,
            ),
        )
        .values(
            claimed_by=worker,
            claimed_at=now,
            heartbeat_at=now,
            attempt=Execution.attempt + 1,
        )
    )
    if int(claimed.rowcount or 0) == 0:  # type: ignore[attr-defined]
        return None

    await session.refresh(candidate)
    return candidate


async def run_once(session_factory: async_sessionmaker[AsyncSession], *, worker: str) -> bool:
    """Claims and runs at most one execution. True when there was work."""
    async with session_factory() as session:
        execution = await claim_next(session, worker=worker)
        if execution is None:
            await session.rollback()
            return False

        try:
            outcome = await run_to_completion(session, execution)
            await session.commit()
            logger.info(
                "execution finished",
                extra={"execution_id": execution.id, "status": outcome.status},
            )
        except Exception:
            await session.rollback()
            # Release the claim so another worker can retry rather than leaving
            # the run stuck behind a dead claim.
            async with session_factory() as recovery:
                await recovery.execute(
                    update(Execution)
                    .where(Execution.id == execution.id)
                    .values(claimed_by=None, heartbeat_at=None)
                )
                await recovery.commit()
            logger.exception("execution step failed", extra={"execution_id": execution.id})
        return True


async def work_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    worker: str,
    stop: asyncio.Event,
    poll_seconds: float = POLL_SECONDS,
) -> None:
    logger.info("runtime worker started", extra={"worker": worker})
    while not stop.is_set():
        try:
            did_work = await run_once(session_factory, worker=worker)
        except Exception:
            logger.exception("worker loop error")
            did_work = False

        if not did_work:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
    logger.info("runtime worker stopped", extra={"worker": worker})


async def main(settings: Settings | None = None) -> None:
    configure_logging()
    resolved = settings or get_settings()
    engine = create_engine(resolved)
    stop = asyncio.Event()
    try:
        await work_loop(create_session_factory(engine), worker=worker_name(), stop=stop)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
