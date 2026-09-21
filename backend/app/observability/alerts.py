"""Alert rules: what the platform watches for, and what it does when it sees it.

Rules run over data the platform already keeps - executions, the audit log, the
usage ledger - so an alert can always be traced back to rows a person can read.
They are evaluated by the worker on an interval, per organization.

Each evaluation produces the set of rules that currently match. A rule that
matches again updates its existing alert rather than making a new one; a rule
that stops matching resolves it. Nothing here pages anyone: it records, and
optionally tells an operator webhook once per firing.

Detail carries counts and ids, never content: an alert says "three runs failed",
and the runs themselves say why.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.time import ensure_utc, now_utc
from app.db.models import Alert, AuditEvent, Execution, ModelUsage, Organization
from app.llm.gateway import start_of_day
from app.observability.metrics import ALERTS_ACTIVE

logger = logging.getLogger(__name__)

Severity = Literal["info", "warning", "critical"]

#: How far back the "recent" rules look.
RECENT = timedelta(minutes=15)
SANDBOX_WINDOW = timedelta(hours=1)
#: Share of the daily token budget that counts as nearly spent.
BUDGET_WARNING_SHARE = 0.9


@dataclass(frozen=True)
class Finding:
    """One rule, matching now."""

    rule: str
    severity: Severity
    summary: str
    detail: dict[str, Any] = field(default_factory=dict)


async def _count(session: AsyncSession, statement: Any) -> int:
    return int(await session.scalar(statement) or 0)


async def evaluate(
    session: AsyncSession, settings: Settings, organization: Organization
) -> list[Finding]:
    """Every rule that matches for this organization, right now."""
    now = now_utc()
    recent = now - RECENT
    findings: list[Finding] = []

    failed = await _count(
        session,
        select(func.count(Execution.id)).where(
            Execution.organization_id == organization.id,
            Execution.status == "FAILED",
            Execution.ended_at >= recent,
        ),
    )
    if failed >= settings.alert_failed_runs:
        findings.append(
            Finding(
                "runs_failing",
                "warning",
                f"{failed} runs failed in the last 15 minutes.",
                {"failed": failed, "threshold": settings.alert_failed_runs},
            )
        )

    stalled_before = now - timedelta(seconds=settings.alert_stalled_run_seconds)
    stalled = await _count(
        session,
        select(func.count(Execution.id)).where(
            Execution.organization_id == organization.id,
            Execution.status.in_(["RUNNING", "STARTING"]),
            Execution.claimed_by.is_not(None),
            Execution.heartbeat_at < stalled_before,
        ),
    )
    if stalled:
        findings.append(
            Finding(
                "stalled_runs",
                "warning",
                f"{stalled} runs have been claimed but silent for over "
                f"{settings.alert_stalled_run_seconds // 60} minutes.",
                {"stalled": stalled},
            )
        )

    denials = await _count(
        session,
        select(func.count(AuditEvent.id)).where(
            AuditEvent.organization_id == organization.id,
            AuditEvent.action == "policy.denied",
            AuditEvent.at >= recent,
        ),
    )
    if denials >= settings.alert_policy_denials:
        findings.append(
            Finding(
                "policy_denials",
                "warning",
                f"{denials} tool calls were refused by policy in the last 15 minutes.",
                {"denied": denials, "threshold": settings.alert_policy_denials},
            )
        )

    blocked = await _count(
        session,
        select(func.count(AuditEvent.id)).where(
            AuditEvent.organization_id == organization.id,
            AuditEvent.action == "egress.blocked",
            AuditEvent.at >= recent,
        ),
    )
    if blocked >= settings.alert_policy_denials:
        findings.append(
            Finding(
                "egress_blocked",
                "warning",
                f"{blocked} outbound requests were blocked in the last 15 minutes.",
                {"blocked": blocked},
            )
        )

    unsafe = await _count(
        session,
        select(func.count(Execution.id)).where(
            Execution.organization_id == organization.id,
            Execution.error_code.in_(["sandbox_unsafe", "sandbox_unavailable"]),
            Execution.ended_at >= now - SANDBOX_WINDOW,
        ),
    )
    if unsafe:
        findings.append(
            Finding(
                "sandbox_unverified",
                "critical",
                f"{unsafe} runs stopped in the last hour because the sandbox "
                "could not be verified.",
                {"runs": unsafe},
            )
        )

    model_errors = await _count(
        session,
        select(func.count(ModelUsage.id)).where(
            ModelUsage.organization_id == organization.id,
            ModelUsage.outcome.not_in(["ok", "refused"]),
            ModelUsage.at >= recent,
        ),
    )
    if model_errors >= settings.alert_failed_runs:
        findings.append(
            Finding(
                "model_errors",
                "warning",
                f"{model_errors} model requests failed in the last 15 minutes.",
                {"errors": model_errors},
            )
        )

    used = await _count(
        session,
        select(
            func.coalesce(
                func.sum(
                    ModelUsage.input_tokens
                    + ModelUsage.output_tokens
                    + ModelUsage.cache_read_tokens
                    + ModelUsage.cache_write_tokens
                ),
                0,
            )
        ).where(
            ModelUsage.organization_id == organization.id,
            ModelUsage.at >= start_of_day(now),
        ),
    )
    limit = settings.model_daily_token_limit_per_org
    if used >= limit * BUDGET_WARNING_SHARE:
        spent = used >= limit
        findings.append(
            Finding(
                "model_budget",
                "critical" if spent else "warning",
                (
                    "The daily model budget is spent; runs are being refused."
                    if spent
                    else f"{used} of {limit} daily tokens used."
                ),
                {"used": used, "limit": limit},
            )
        )

    if organization.executions_paused:
        findings.append(
            Finding(
                "kill_switch",
                "info",
                "The kill switch is engaged: no run will start until the owner releases it.",
                {"reason": (organization.executions_paused_reason or "")[:200]},
            )
        )

    return findings


async def apply(
    session: AsyncSession, organization_id: str, findings: list[Finding], *, now: datetime
) -> list[Alert]:
    """Records what matches, resolves what no longer does. Returns new firings."""
    firing = {
        alert.rule: alert
        for alert in await session.scalars(
            select(Alert).where(Alert.organization_id == organization_id, Alert.state == "firing")
        )
    }
    new: list[Alert] = []

    for finding in findings:
        existing = firing.pop(finding.rule, None)
        if existing is not None:
            existing.last_seen = now
            existing.occurrences += 1
            existing.summary = finding.summary
            existing.detail = finding.detail
            existing.severity = finding.severity
            continue
        alert = Alert(
            id=f"alr_{uuid.uuid4().hex[:12]}",
            organization_id=organization_id,
            rule=finding.rule,
            severity=finding.severity,
            state="firing",
            summary=finding.summary,
            detail=finding.detail,
            first_seen=now,
            last_seen=now,
            occurrences=1,
            notified=False,
        )
        session.add(alert)
        new.append(alert)

    # Whatever is still in `firing` no longer matches.
    for stale in firing.values():
        stale.state = "resolved"
        stale.resolved_at = now

    await session.flush()
    return new


async def refresh_gauge(session: AsyncSession) -> None:
    """Republishes the active-alert gauge from the table."""
    counts = await session.execute(
        select(Alert.rule, Alert.severity, func.count(Alert.id))
        .where(Alert.state == "firing")
        .group_by(Alert.rule, Alert.severity)
    )
    ALERTS_ACTIVE.clear()
    for rule, severity, count in counts:
        ALERTS_ACTIVE.labels(rule=rule, severity=severity).set(count)


async def notify(session: AsyncSession, settings: Settings, alerts: list[Alert]) -> None:
    """Tells the operator webhook about new firings, once each.

    Metadata only - rule, severity, summary, counts. Never run content. A
    webhook that fails is logged and the alert stays unnotified rather than
    holding up evaluation.
    """
    if not settings.alert_webhook_url or not alerts:
        return
    from app.security.egress import EgressBlocked, get_egress

    host = settings.alert_webhook_url.split("/")[2]
    for alert in alerts:
        try:
            await get_egress().post_json(
                settings.alert_webhook_url,
                {
                    "source": "agenthub",
                    "rule": alert.rule,
                    "severity": alert.severity,
                    "summary": alert.summary,
                    "detail": alert.detail,
                    "organization": alert.organization_id,
                    "at": ensure_utc(alert.first_seen).isoformat(),
                },
                [host],
            )
            alert.notified = True
        except EgressBlocked as blocked:
            logger.warning(
                "alert webhook refused", extra={"rule": alert.rule, "reason": blocked.rule}
            )
    await session.flush()


async def evaluate_all(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> int:
    """One pass over every organization. Returns how many alerts are firing."""
    now = now_utc()
    async with session_factory() as session:
        organizations = list(await session.scalars(select(Organization)))
        for organization in organizations:
            findings = await evaluate(session, settings, organization)
            new = await apply(session, organization.id, findings, now=now)
            await notify(session, settings, new)
        await session.commit()

        active = await _count(session, select(func.count(Alert.id)).where(Alert.state == "firing"))
        await refresh_gauge(session)
        return active


async def resolve(session: AsyncSession, alert: Alert, *, now: datetime | None = None) -> Alert:
    """Closes an alert by hand. It fires again if the rule still matches."""
    alert.state = "resolved"
    alert.resolved_at = now or now_utc()
    await session.flush()
    return alert
