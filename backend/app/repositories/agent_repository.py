"""Agent queries."""

from typing import Any

from sqlalchemy import Select, UnaryExpression, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Agent
from app.schemas.enums import AgentSort

SORT_CLAUSES: dict[AgentSort, UnaryExpression[Any]] = {
    "updated_desc": Agent.updated_at.desc(),
    "name_asc": Agent.name.asc(),
    "risk_desc": Agent.risk_score.desc(),
    "last_execution_desc": Agent.last_execution_at.desc().nulls_last(),
}


def _filtered(
    search: str | None,
    status: str | None,
    risk: str | None,
    category: str | None,
) -> Select[tuple[Agent]]:
    statement = select(Agent)
    if search:
        pattern = "%" + search.strip().lower() + "%"
        statement = statement.where(
            or_(
                func.lower(Agent.name).like(pattern),
                func.lower(Agent.description).like(pattern),
                func.lower(Agent.creator_name).like(pattern),
            )
        )
    if status and status != "all":
        statement = statement.where(Agent.status == status)
    if risk and risk != "all":
        statement = statement.where(Agent.risk_level == risk)
    if category and category != "all":
        statement = statement.where(Agent.category == category)
    return statement


async def list_agents(
    session: AsyncSession,
    *,
    search: str | None = None,
    status: str | None = None,
    risk: str | None = None,
    category: str | None = None,
    sort: AgentSort = "updated_desc",
    limit: int,
    offset: int,
) -> tuple[list[Agent], int]:
    statement = _filtered(search, status, risk, category)
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = await session.scalars(statement.order_by(SORT_CLAUSES[sort]).limit(limit).offset(offset))
    return list(rows), int(total or 0)


async def get_agent(session: AsyncSession, agent_id: str) -> Agent | None:
    agent: Agent | None = await session.get(Agent, agent_id)
    return agent


async def get_agent_by_name(session: AsyncSession, name: str) -> Agent | None:
    agent: Agent | None = await session.scalar(
        select(Agent).where(func.lower(Agent.name) == name.lower())
    )
    return agent
