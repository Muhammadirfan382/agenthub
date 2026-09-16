"""Execution queries."""

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Execution


def _filtered(
    organization_id: str, status: str | None, agent_id: str | None, search: str | None
) -> Select[tuple[Execution]]:
    statement = select(Execution).where(Execution.organization_id == organization_id)
    if status and status != "all":
        statement = statement.where(Execution.status == status)
    if agent_id:
        statement = statement.where(Execution.agent_id == agent_id)
    if search:
        pattern = "%" + search.strip().lower() + "%"
        statement = statement.where(
            or_(
                func.lower(Execution.id).like(pattern),
                func.lower(Execution.agent_name).like(pattern),
            )
        )
    return statement


async def list_executions(
    session: AsyncSession,
    *,
    organization_id: str,
    status: str | None = None,
    agent_id: str | None = None,
    search: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Execution], int]:
    statement = _filtered(organization_id, status, agent_id, search)
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = await session.scalars(
        statement.order_by(Execution.started_at.desc(), Execution.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), int(total or 0)


async def get_execution(
    session: AsyncSession, execution_id: str, organization_id: str
) -> Execution | None:
    execution: Execution | None = await session.scalar(
        select(Execution).where(
            Execution.id == execution_id, Execution.organization_id == organization_id
        )
    )
    return execution
