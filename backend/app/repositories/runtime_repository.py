"""Queries for what an execution recorded, and for approvals."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Execution,
    ExecutionApproval,
    ExecutionEvent,
    ExecutionLog,
    ExecutionToolCall,
)


async def events(session: AsyncSession, execution_id: str) -> list[ExecutionEvent]:
    rows = await session.scalars(
        select(ExecutionEvent)
        .where(ExecutionEvent.execution_id == execution_id)
        .order_by(ExecutionEvent.sequence.asc())
    )
    return list(rows)


async def logs(session: AsyncSession, execution_id: str) -> list[ExecutionLog]:
    rows = await session.scalars(
        select(ExecutionLog)
        .where(ExecutionLog.execution_id == execution_id)
        .order_by(ExecutionLog.sequence.asc())
    )
    return list(rows)


async def tool_calls(session: AsyncSession, execution_id: str) -> list[ExecutionToolCall]:
    rows = await session.scalars(
        select(ExecutionToolCall)
        .where(ExecutionToolCall.execution_id == execution_id)
        .order_by(ExecutionToolCall.sequence.asc())
    )
    return list(rows)


async def approvals(session: AsyncSession, execution_id: str) -> list[ExecutionApproval]:
    rows = await session.scalars(
        select(ExecutionApproval)
        .where(ExecutionApproval.execution_id == execution_id)
        .order_by(ExecutionApproval.requested_at.asc())
    )
    return list(rows)


async def get_approval(
    session: AsyncSession, approval_id: str, organization_id: str
) -> ExecutionApproval | None:
    approval: ExecutionApproval | None = await session.scalar(
        select(ExecutionApproval).where(
            ExecutionApproval.id == approval_id,
            ExecutionApproval.organization_id == organization_id,
        )
    )
    return approval


async def pending_approvals(
    session: AsyncSession, organization_id: str, *, limit: int, offset: int
) -> tuple[list[tuple[ExecutionApproval, Execution]], int]:
    """Everything waiting on a person, newest request first."""
    condition = (
        ExecutionApproval.organization_id == organization_id,
        ExecutionApproval.status == "pending",
    )
    total = await session.scalar(
        select(func.count()).select_from(ExecutionApproval).where(*condition)
    )
    rows = await session.execute(
        select(ExecutionApproval, Execution)
        .join(Execution, Execution.id == ExecutionApproval.execution_id)
        .where(*condition)
        .order_by(ExecutionApproval.requested_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [(approval, execution) for approval, execution in rows], int(total or 0)


async def latest_event_sequence(session: AsyncSession, execution_id: str) -> int:
    highest = await session.scalar(
        select(func.max(ExecutionEvent.sequence)).where(ExecutionEvent.execution_id == execution_id)
    )
    return int(highest or 0)
