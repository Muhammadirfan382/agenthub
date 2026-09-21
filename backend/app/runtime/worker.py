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
import time
import uuid
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import SERVICE_VERSION, Settings, get_settings
from app.core.logging import configure_logging
from app.core.time import now_utc
from app.db.models import Execution, ExecutionApproval
from app.db.session import create_engine, create_session_factory
from app.observability import alerts
from app.observability.metrics import (
    APPROVALS_PENDING,
    EXECUTIONS_QUEUED,
    EXECUTIONS_RUNNING,
    record_build,
)
from app.observability.tracing import configure_tracing
from app.observability.worker_metrics import serve as serve_metrics
from app.runtime import workers
from app.runtime.engine import run_to_completion, stale_before

logger = logging.getLogger(__name__)

#: A run whose worker has not been heard from for this long is up for grabs.
STALE_CLAIM_SECONDS = 60
POLL_SECONDS = 1.0
#: How often a busy worker proves it is alive while a step waits on a model.
HEARTBEAT_SECONDS = 15.0
#: Claims a run may take. A run that keeps killing its worker is failed, not retried forever.
MAX_ATTEMPTS = 3
#: How often a worker tells the API what it can do (see app/runtime/workers.py).
REPORT_SECONDS = 60.0


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


async def run_once(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    worker: str,
    settings: Settings | None = None,
) -> bool:
    """Claims and runs at most one execution. True when there was work."""
    async with session_factory() as session:
        execution = await claim_next(session, worker=worker)
        if execution is None:
            await session.rollback()
            return False

        # Held separately: a rollback expires the instance, and reading an
        # attribute back off it would need the very session that just failed.
        execution_id = execution.id

        if execution.attempt > MAX_ATTEMPTS:
            await _give_up(session, execution)
            return True

        # A claim is committed before any work starts, so no other worker takes it.
        await session.commit()
        heartbeat = asyncio.create_task(
            _keep_alive(session_factory, execution_id=execution_id, worker=worker)
        )
        try:
            outcome = await run_to_completion(session, execution, settings=settings)
            await session.commit()
            logger.info(
                "execution finished",
                extra={"execution_id": execution_id, "status": outcome.status},
            )
        except Exception:
            await session.rollback()
            # Release the claim so another worker can retry rather than leaving
            # the run stuck behind a dead claim.
            async with session_factory() as recovery:
                await recovery.execute(
                    update(Execution)
                    .where(Execution.id == execution_id)
                    .values(claimed_by=None, heartbeat_at=None)
                )
                await recovery.commit()
            logger.exception("execution step failed", extra={"execution_id": execution_id})
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
        return True


async def _keep_alive(
    session_factory: async_sessionmaker[AsyncSession], *, execution_id: str, worker: str
) -> None:
    """Refreshes the claim while a step is busy, e.g. waiting minutes on a model.

    Without it a long model call would look like a dead worker, and a second
    worker would reclaim the run and pay for the same call again.
    """
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        try:
            async with session_factory() as beat:
                await beat.execute(
                    update(Execution)
                    .where(Execution.id == execution_id, Execution.claimed_by == worker)
                    .values(heartbeat_at=now_utc())
                )
                await beat.commit()
        except Exception:  # a missed beat is not worth killing the run over
            logger.warning("heartbeat failed", extra={"execution_id": execution_id})


async def _give_up(session: AsyncSession, execution: Execution) -> None:
    """Fails a run that has already cost too many workers."""
    now = now_utc()
    execution.status = "FAILED"
    execution.error_code = "worker_retries"
    execution.error_message = (
        f"Stopped after {MAX_ATTEMPTS} attempts: the run kept failing inside the worker."
    )
    execution.ended_at = now
    execution.claimed_by = None
    execution.heartbeat_at = None
    await session.commit()
    logger.error("execution abandoned", extra={"execution_id": execution.id})


async def work_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    worker: str,
    stop: asyncio.Event,
    poll_seconds: float = POLL_SECONDS,
    settings: Settings | None = None,
) -> None:
    resolved = settings or get_settings()
    logger.info("runtime worker started", extra={"worker": worker})
    started_at = now_utc()
    next_watch = 0.0
    next_report = 0.0
    while not stop.is_set():
        try:
            did_work = await run_once(session_factory, worker=worker, settings=settings)
        except Exception:
            logger.exception("worker loop error")
            did_work = False

        # The worker is the one process that always runs, so it is also the one
        # that publishes queue gauges and evaluates alert rules.
        if time.monotonic() >= next_watch:
            next_watch = time.monotonic() + resolved.alert_interval_seconds
            await watch(session_factory, resolved)

        if time.monotonic() >= next_report:
            next_report = time.monotonic() + REPORT_SECONDS
            await report_capabilities(
                session_factory, resolved, worker=worker, started_at=started_at
            )

        if not did_work:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
    logger.info("runtime worker stopped", extra={"worker": worker})


async def report_capabilities(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    worker: str,
    started_at: datetime,
) -> None:
    """Records what this worker can do, for the API to read. Never raises."""
    try:
        async with session_factory() as session:
            await workers.report(session, settings, worker=worker, started_at=started_at)
            await session.commit()
    except Exception:
        logger.exception("could not report worker capabilities")


async def watch(session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
    """Publishes the queue gauges and evaluates the alert rules.

    Never raises: monitoring that can stop the runtime is worse than no
    monitoring at all.
    """
    try:
        async with session_factory() as session:
            queued = await session.scalar(
                select(func.count(Execution.id)).where(Execution.status == "QUEUED")
            )
            running = await session.scalar(
                select(func.count(Execution.id)).where(
                    Execution.status.in_(["STARTING", "RUNNING"])
                )
            )
            waiting = await session.scalar(
                select(func.count(ExecutionApproval.id)).where(
                    ExecutionApproval.status == "pending"
                )
            )
        EXECUTIONS_QUEUED.set(int(queued or 0))
        EXECUTIONS_RUNNING.set(int(running or 0))
        APPROVALS_PENDING.set(int(waiting or 0))
    except Exception:
        logger.exception("could not publish queue gauges")

    try:
        firing = await alerts.evaluate_all(session_factory, settings)
        logger.debug("alert rules evaluated", extra={"firing": firing})
    except Exception:
        logger.exception("could not evaluate alert rules")


async def main(settings: Settings | None = None) -> None:
    configure_logging()
    resolved = settings or get_settings()
    # A standalone worker is its own process: it needs its own tracing and
    # build metric, or its spans would be no-ops and its logs uncorrelated.
    configure_tracing(resolved)
    record_build(SERVICE_VERSION, resolved.environment)
    metrics_server = serve_metrics(resolved)
    engine = create_engine(resolved)
    stop = asyncio.Event()
    try:
        await work_loop(
            create_session_factory(engine), worker=worker_name(), stop=stop, settings=resolved
        )
    finally:
        if metrics_server is not None:
            metrics_server.shutdown()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
