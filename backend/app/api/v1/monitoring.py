"""Readiness, metrics, component status and alerts.

Three of these are for operators and one is for the application:

* `GET /health/ready` - for an orchestrator. Says whether this process can
  serve traffic, and nothing about how it is configured.
* `GET /metrics` - for a scraper, in Prometheus' format. Counts only.
* `GET /system/status` - for the people using AgentHub: which parts are working.
* `GET /alerts` - what the platform noticed, per organization.

Readiness and metrics are unauthenticated, because probes and scrapers usually
cannot sign in. Readiness answers `ready` or `not ready` with check names only,
and metrics can be closed with `METRICS_TOKEN`. The two that carry an
organization's data require a session like everything else.
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select, text

from app.api.deps import AuthDep, SettingsDep
from app.core.config import SERVICE_NAME, SERVICE_VERSION
from app.core.errors import ForbiddenError, NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.core.time import ensure_utc, now_utc
from app.db.models import Alert, Execution
from app.db.session import SessionDep
from app.llm.gateway import get_gateway
from app.observability import alerts as alert_rules
from app.observability.metrics import REGISTRY
from app.observability.worker_metrics import authorized
from app.runtime import workers
from app.runtime.worker import STALE_CLAIM_SECONDS
from app.schemas.common import CamelModel
from app.security import audit
from app.services import authorization

router = APIRouter(tags=["monitoring"])

ComponentState = Literal["operational", "degraded", "outage"]


class ReadyCheck(CamelModel):
    name: str
    ok: bool


class ReadyResponse(CamelModel):
    status: Literal["ready", "not_ready"]
    service: str
    version: str
    checks: list[ReadyCheck]


class ComponentStatus(CamelModel):
    id: str
    name: str
    state: ComponentState
    detail: str


class SystemStatus(CamelModel):
    state: ComponentState
    components: list[ComponentStatus]
    checked_at: datetime


class AlertRead(CamelModel):
    id: str
    rule: str
    severity: str
    state: str
    summary: str
    detail: dict[str, Any]
    first_seen: datetime
    last_seen: datetime
    resolved_at: datetime | None
    occurrences: int


async def _database_ok(session: SessionDep) -> bool:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


@router.get(
    "/health/ready",
    response_model=ReadyResponse,
    summary="Readiness check",
    description="Whether this process can serve requests. Names checks, never configuration.",
)
async def ready(session: SessionDep, response: Response) -> ReadyResponse:
    checks = [ReadyCheck(name="database", ok=await _database_ok(session))]
    healthy = all(check.ok for check in checks)
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(
        status="ready" if healthy else "not_ready",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        checks=checks,
    )


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Counts, durations and gauges. No organization ids, no content, nothing personal.",
    response_class=Response,
)
async def metrics(
    settings: SettingsDep,
    authorization_header: Annotated[str | None, Header(alias="Authorization")] = None,
) -> Response:
    if not settings.metrics_enabled:
        raise NotFoundError("Metrics are not enabled.")
    expected = settings.metrics_token
    if not authorized(authorization_header, expected.get_secret_value() if expected else None):
        raise ForbiddenError("A valid metrics token is required.")
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


def _worker_state(
    latest_heartbeat: datetime | None, queued: int, worker_seen_at: datetime | None = None
) -> tuple[ComponentState, str]:
    if worker_seen_at is not None:
        # A worker reported in recently (see app/runtime/workers.py).
        waiting = f" {queued} runs are waiting." if queued else ""
        return "operational", "A worker is running and reporting." + waiting
    if latest_heartbeat is not None:
        age = (now_utc() - ensure_utc(latest_heartbeat)).total_seconds()
        if age <= STALE_CLAIM_SECONDS:
            return "operational", "A worker is claiming and advancing runs."
        if queued:
            return "outage", f"No worker has been heard from for {int(age)}s and work is waiting."
        return "degraded", f"No worker has been heard from for {int(age)}s."
    if queued:
        return "outage", f"{queued} runs are waiting and no worker has claimed them."
    return "operational", "Idle: nothing is waiting."


@router.get(
    "/system/status",
    response_model=SystemStatus,
    summary="What is working right now",
    description="Component states derived from live checks, not from a fixture.",
)
async def system_status(session: SessionDep, auth: AuthDep, settings: SettingsDep) -> SystemStatus:
    authorization.require(auth.role, "execution:read")
    now = now_utc()

    database_ok = await _database_ok(session)
    queued = int(
        await session.scalar(
            select(func.count(Execution.id)).where(
                Execution.organization_id == auth.organization_id,
                Execution.status == "QUEUED",
            )
        )
        or 0
    )
    latest_heartbeat = await session.scalar(
        select(func.max(Execution.heartbeat_at)).where(
            Execution.organization_id == auth.organization_id
        )
    )
    gateway = get_gateway(settings)
    # In production the worker, not this process, holds provider keys and the
    # container runtime: ask what the runtime as a whole can do.
    runtime = await workers.capabilities(session, settings)
    worker_state, worker_detail = _worker_state(latest_heartbeat, queued, runtime.worker_seen_at)
    live_tiers = [tier for tier in gateway.all_routes() if tier in runtime.live_tiers]
    sandbox_available = runtime.sandbox_available
    firing = int(
        await session.scalar(
            select(func.count(Alert.id)).where(
                Alert.organization_id == auth.organization_id, Alert.state == "firing"
            )
        )
        or 0
    )

    components = [
        ComponentStatus(
            id="api",
            name="API",
            state="operational",
            detail="Answering requests.",
        ),
        ComponentStatus(
            id="database",
            name="Database",
            state="operational" if database_ok else "outage",
            detail="Reachable." if database_ok else "Not reachable.",
        ),
        ComponentStatus(
            id="runtime", name="Execution runtime", state=worker_state, detail=worker_detail
        ),
        ComponentStatus(
            id="models",
            name="Model gateway",
            state="operational" if live_tiers else "degraded",
            detail=(
                f"{len(live_tiers)} of {len(gateway.all_routes())} tiers answer with a real model."
                if live_tiers
                else "No provider is configured: runs are simulated."
            ),
        ),
        ComponentStatus(
            id="sandbox",
            name="Sandbox",
            state="operational" if sandbox_available else "degraded",
            detail=(
                "A container runtime is available."
                if sandbox_available
                else "No container runtime: runs are not isolated."
            ),
        ),
        ComponentStatus(
            id="security",
            name="Security",
            state="operational" if firing == 0 else "degraded",
            detail=("No alerts are firing." if firing == 0 else f"{firing} alerts are firing."),
        ),
    ]
    worst: ComponentState = "operational"
    for component in components:
        if component.state == "outage":
            worst = "outage"
            break
        if component.state == "degraded":
            worst = "degraded"
    return SystemStatus(state=worst, components=components, checked_at=now)


def _alert_read(alert: Alert) -> AlertRead:
    return AlertRead.model_validate(
        {
            "id": alert.id,
            "rule": alert.rule,
            "severity": alert.severity,
            "state": alert.state,
            "summary": alert.summary,
            "detail": alert.detail or {},
            "firstSeen": ensure_utc(alert.first_seen),
            "lastSeen": ensure_utc(alert.last_seen),
            "resolvedAt": ensure_utc(alert.resolved_at) if alert.resolved_at else None,
            "occurrences": alert.occurrences,
        }
    )


@router.get(
    "/alerts",
    response_model=Page[AlertRead],
    summary="Alerts this organization has",
    description="Firing first, newest first. Raised by the rules in app/observability/alerts.py.",
)
async def list_alerts(
    session: SessionDep,
    auth: AuthDep,
    page: Annotated[PageParams, Depends(page_params)],
    state: Annotated[str | None, Query(pattern=r"^(firing|resolved)$")] = None,
) -> Page[AlertRead]:
    authorization.require(auth.role, "execution:read")
    filters = [Alert.organization_id == auth.organization_id]
    if state:
        filters.append(Alert.state == state)
    total = await session.scalar(select(func.count(Alert.id)).where(*filters))
    rows = await session.scalars(
        select(Alert)
        .where(*filters)
        .order_by(Alert.state.desc(), Alert.last_seen.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    return Page(
        items=[_alert_read(alert) for alert in rows],
        total=int(total or 0),
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/alerts/{alert_id}/resolve",
    response_model=AlertRead,
    summary="Resolve an alert by hand",
    description="It fires again at the next evaluation if the rule still matches.",
)
async def resolve_alert(session: SessionDep, auth: AuthDep, alert_id: str) -> AlertRead:
    authorization.require(auth.role, "runtime:pause")
    alert = await session.scalar(
        select(Alert).where(Alert.id == alert_id, Alert.organization_id == auth.organization_id)
    )
    if alert is None:
        raise NotFoundError("No alert with this id.")
    await alert_rules.resolve(session, alert)
    await audit.record(
        session,
        organization_id=auth.organization_id,
        action="alert.resolved",
        actor=audit.user_actor(auth),
        target=("alert", alert.id),
        detail={"rule": alert.rule},
    )
    return _alert_read(alert)
