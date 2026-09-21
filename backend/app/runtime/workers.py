"""What the runtime workers can do, reported by them and read by the API.

The worker calls `report` at start and every alert interval. The API calls
`capabilities`, which combines what a recently-seen worker reported with the
API process's own view, so a single-process development setup (worker inside
the API) and a split production setup both answer truthfully.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import SERVICE_VERSION, Settings
from app.core.time import ensure_utc, now_utc
from app.db.models import RuntimeWorker
from app.llm.gateway import get_gateway
from app.llm.routing import PROVIDERS
from app.runtime.sandbox import get_sandbox

#: A worker not heard from for this long no longer speaks for the runtime.
#: Three default alert intervals: one missed report is not an outage.
FRESH_SECONDS = 180
#: Rows older than this are removed, so restarts do not accumulate forever.
FORGET_AFTER = timedelta(days=1)


@dataclass(frozen=True)
class Capabilities:
    sandbox_available: bool
    providers: frozenset[str] = field(default_factory=frozenset)
    live_tiers: frozenset[str] = field(default_factory=frozenset)
    #: When the freshest worker last reported; None if none is fresh.
    worker_seen_at: datetime | None = None


async def local_capabilities(settings: Settings) -> Capabilities:
    """What this process itself can do."""
    gateway = get_gateway(settings)
    return Capabilities(
        sandbox_available=await get_sandbox(settings).available(),
        providers=frozenset(name for name in PROVIDERS if gateway.configured(name)),
        live_tiers=frozenset(tier for tier in gateway.all_routes() if gateway.available_for(tier)),
    )


async def report(
    session: AsyncSession, settings: Settings, *, worker: str, started_at: datetime
) -> None:
    """Records this worker's capabilities. The caller commits."""
    now = now_utc()
    local = await local_capabilities(settings)
    row = await session.get(RuntimeWorker, worker)
    if row is None:
        row = RuntimeWorker(id=worker, started_at=started_at)
        session.add(row)
    row.version = SERVICE_VERSION
    row.seen_at = now
    row.sandbox_available = local.sandbox_available
    row.providers = sorted(local.providers)
    row.live_tiers = sorted(local.live_tiers)
    await session.execute(delete(RuntimeWorker).where(RuntimeWorker.seen_at < now - FORGET_AFTER))


async def capabilities(session: AsyncSession, settings: Settings) -> Capabilities:
    """What the runtime can do: fresh workers' reports, plus this process."""
    local = await local_capabilities(settings)
    cutoff = now_utc() - timedelta(seconds=FRESH_SECONDS)
    fresh = (
        await session.scalars(select(RuntimeWorker).where(RuntimeWorker.seen_at >= cutoff))
    ).all()
    if not fresh:
        return local
    return Capabilities(
        sandbox_available=local.sandbox_available or any(w.sandbox_available for w in fresh),
        providers=local.providers.union(*(frozenset(w.providers) for w in fresh)),
        live_tiers=local.live_tiers.union(*(frozenset(w.live_tiers) for w in fresh)),
        worker_seen_at=max(ensure_utc(w.seen_at) for w in fresh),
    )
