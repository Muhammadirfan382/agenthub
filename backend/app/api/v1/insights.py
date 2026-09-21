"""The security and analytics views, from real rows.

Until now these screens were drawn from demonstration data even against the
backend. Everything here is counted from what the platform actually recorded:
agents and their grants, executions, the audit log and the usage ledger.

Where a number would be invented, it is not returned at all.
"""

from collections import Counter as Tally
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import AuthDep
from app.core.time import ensure_utc, now_utc
from app.db.models import Agent, Alert, AuditEvent, Execution, ModelUsage
from app.db.session import SessionDep
from app.schemas.common import CamelModel
from app.schemas.enums import CapabilityKey, RiskLevel, SecurityCheckStatus
from app.services import authorization

router = APIRouter(tags=["insights"])

#: Audit actions that belong on a security screen, and how to describe them.
SECURITY_ACTIONS: dict[str, tuple[RiskLevel, str]] = {
    "policy.denied": ("high", "Tool call refused by policy"),
    "egress.blocked": ("high", "Outbound request blocked"),
    "auth.login_failed": ("medium", "Failed sign-in"),
    "sandbox.checked": ("critical", "Sandbox verification"),
    "runtime.kill_switch_engaged": ("critical", "Kill switch engaged"),
    "runtime.kill_switch_released": ("medium", "Kill switch released"),
    "member.role_changed": ("medium", "Member role changed"),
    "alert.resolved": ("low", "Alert resolved by hand"),
}
DEFAULT_DAYS = 14


class PermissionOverviewRow(CamelModel):
    capability: CapabilityKey
    allowed: int
    restricted: int
    requires_approval: int
    denied: int


class SecurityOverview(CamelModel):
    risk_distribution: dict[RiskLevel, int]
    checks: dict[SecurityCheckStatus, int]
    permissions: list[PermissionOverviewRow]
    open_alerts: int


class SecurityEventRead(CamelModel):
    id: str
    severity: RiskLevel
    type: str
    agent_id: str | None
    agent_name: str
    description: str
    detected_at: datetime
    status: str


class DailyPoint(CamelModel):
    date: date
    value: int


class TopAgent(CamelModel):
    agent_id: str
    name: str
    executions: int


class AnalyticsSummary(CamelModel):
    executions_per_day: list[DailyPoint]
    tokens_per_day: list[DailyPoint]
    #: Of runs that finished; 0 when none did.
    success_rate: float
    average_duration_ms: int
    top_agents: list[TopAgent]
    status_breakdown: dict[str, int]
    #: Estimated spend over the window, in US dollars.
    estimated_cost_usd: float


@router.get(
    "/security/overview",
    response_model=SecurityOverview,
    summary="Risk, checks and grants across this organization's agents",
)
async def security_overview(session: SessionDep, auth: AuthDep) -> SecurityOverview:
    authorization.require(auth.role, "agent:read")
    agents = list(
        await session.scalars(select(Agent).where(Agent.organization_id == auth.organization_id))
    )

    risks: Tally[str] = Tally({"low": 0, "medium": 0, "high": 0, "critical": 0})
    checks: Tally[str] = Tally({"passed": 0, "warning": 0, "failed": 0, "not_run": 0})
    rows: dict[str, PermissionOverviewRow] = {}
    for agent in agents:
        risks[agent.risk_level] += 1
        for check in agent.security_checks or []:
            status = str(check.get("status", "not_run"))
            if status in checks:
                checks[status] += 1
        for permission in agent.permissions or []:
            capability = str(permission.get("capability", ""))
            if not capability:
                continue
            row = rows.setdefault(
                capability,
                PermissionOverviewRow.model_validate(
                    {
                        "capability": capability,
                        "allowed": 0,
                        "restricted": 0,
                        "requiresApproval": 0,
                        "denied": 0,
                    }
                ),
            )
            level = str(permission.get("level", "denied"))
            if level == "denied":
                row.denied += 1
            elif level == "allowed":
                row.allowed += 1
            else:
                row.restricted += 1
            if level != "denied" and permission.get("requiresApproval"):
                row.requires_approval += 1

    firing = await session.scalar(
        select(func.count(Alert.id)).where(
            Alert.organization_id == auth.organization_id, Alert.state == "firing"
        )
    )
    return SecurityOverview.model_validate(
        {
            "riskDistribution": dict(risks),
            "checks": dict(checks),
            "permissions": [row.model_dump(by_alias=True) for row in rows.values()],
            "openAlerts": int(firing or 0),
        }
    )


@router.get(
    "/security/events",
    response_model=list[SecurityEventRead],
    summary="Security-relevant events, newest first",
    description="Drawn from the audit log. These are records of what happened, not a triage queue.",
)
async def security_events(
    session: SessionDep,
    auth: AuthDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[SecurityEventRead]:
    authorization.require(auth.role, "execution:read")
    rows = await session.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.organization_id == auth.organization_id,
            AuditEvent.action.in_(list(SECURITY_ACTIONS)),
        )
        .order_by(AuditEvent.at.desc(), AuditEvent.id.desc())
        .limit(limit)
    )
    events: list[SecurityEventRead] = []
    for row in rows:
        severity, label = SECURITY_ACTIONS[row.action]
        detail: dict[str, Any] = row.detail or {}
        if row.action == "sandbox.checked" and row.outcome != "failure":
            continue
        described = ", ".join(f"{key}: {value}" for key, value in detail.items())
        events.append(
            SecurityEventRead.model_validate(
                {
                    "id": row.id,
                    "severity": severity,
                    "type": label,
                    "agentId": row.actor_id if row.actor_type == "agent" else None,
                    "agentName": row.actor_name,
                    "description": described or label,
                    "detectedAt": ensure_utc(row.at),
                    "status": "open",
                }
            )
        )
    return events


@router.get(
    "/analytics/summary",
    response_model=AnalyticsSummary,
    summary="Executions, tokens and spend over the last days",
)
async def analytics_summary(
    session: SessionDep,
    auth: AuthDep,
    days: Annotated[int, Query(ge=1, le=90)] = DEFAULT_DAYS,
) -> AnalyticsSummary:
    authorization.require(auth.role, "execution:read")
    since = now_utc() - timedelta(days=days)
    organization = auth.organization_id

    executions = list(
        await session.scalars(
            select(Execution).where(
                Execution.organization_id == organization, Execution.started_at >= since
            )
        )
    )

    per_day: Tally[date] = Tally()
    statuses: Tally[str] = Tally()
    agents: dict[str, TopAgent] = {}
    finished = 0
    completed = 0
    total_duration = 0
    for execution in executions:
        per_day[ensure_utc(execution.started_at).date()] += 1
        statuses[execution.status] += 1
        agent = agents.setdefault(
            execution.agent_id,
            TopAgent.model_validate(
                {"agentId": execution.agent_id, "name": execution.agent_name, "executions": 0}
            ),
        )
        agent.executions += 1
        if execution.ended_at is not None:
            finished += 1
            total_duration += execution.duration_ms or 0
            if execution.status == "COMPLETED":
                completed += 1

    usage = await session.execute(
        select(
            ModelUsage.at,
            ModelUsage.input_tokens
            + ModelUsage.output_tokens
            + ModelUsage.cache_read_tokens
            + ModelUsage.cache_write_tokens,
            ModelUsage.cost_microusd,
        ).where(ModelUsage.organization_id == organization, ModelUsage.at >= since)
    )
    tokens_per_day: Tally[date] = Tally()
    cost = 0
    for at, tokens, row_cost in usage:
        tokens_per_day[ensure_utc(at).date()] += int(tokens or 0)
        cost += int(row_cost or 0)

    span = [(since + timedelta(days=offset)).date() for offset in range(days + 1)]
    return AnalyticsSummary.model_validate(
        {
            "executionsPerDay": [{"date": day, "value": per_day.get(day, 0)} for day in span],
            "tokensPerDay": [{"date": day, "value": tokens_per_day.get(day, 0)} for day in span],
            "successRate": round(completed / finished, 4) if finished else 0.0,
            "averageDurationMs": int(total_duration / finished) if finished else 0,
            "topAgents": [
                agent.model_dump(by_alias=True)
                for agent in sorted(agents.values(), key=lambda a: a.executions, reverse=True)[:5]
            ],
            "statusBreakdown": dict(statuses),
            "estimatedCostUsd": round(cost / 1_000_000, 6),
        }
    )
