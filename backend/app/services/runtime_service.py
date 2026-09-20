"""Controls over a run: cancel it, approve a step, or stop everything.

These are the levers a person has over the runtime. They are authorization
decisions first and orchestration second: the engine only ever reads what these
functions wrote.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.core.time import now_utc
from app.db.models import Agent, Execution, ExecutionApproval, Organization
from app.repositories import runtime_repository
from app.schemas.enums import TERMINAL_STATUSES, ApprovalDecision
from app.security import audit
from app.services import authorization, execution_service
from app.services.auth_service import AuthContext


async def _agent_of(session: AsyncSession, execution: Execution) -> Agent | None:
    return await session.get(Agent, execution.agent_id)


async def _require_control(
    session: AsyncSession, execution: Execution, *, context: AuthContext
) -> None:
    """Whoever may run an agent may also stop it, and so may an administrator."""
    agent = await _agent_of(session, execution)
    owns = agent is not None and agent.owner_id == context.user_id
    authorization.require(context.role, "agent:execute", owns_resource=owns)


async def cancel(session: AsyncSession, execution_id: str, *, context: AuthContext) -> Execution:
    execution = await execution_service.get_execution(session, execution_id, context=context)
    await _require_control(session, execution, context=context)

    if execution.status in TERMINAL_STATUSES:
        raise ConflictError(f"This execution already finished as {execution.status.lower()}.")

    execution.cancel_requested_at = now_utc()
    execution.cancel_requested_by = context.user.name
    await audit.record(
        session,
        organization_id=context.organization_id,
        action="execution.cancelled",
        actor=audit.user_actor(context),
        outcome="success",
        target=("execution", execution.id),
        detail={},
    )
    await session.flush()
    return execution


async def decide_approval(
    session: AsyncSession,
    approval_id: str,
    *,
    decision: ApprovalDecision,
    note: str | None,
    context: AuthContext,
) -> ExecutionApproval:
    """Approving is a permission, not a formality: it needs the run permission."""
    approval = await runtime_repository.get_approval(session, approval_id, context.organization_id)
    if approval is None:
        raise NotFoundError("No approval request with this id.")

    execution = await execution_service.get_execution(
        session, approval.execution_id, context=context
    )
    await _require_control(session, execution, context=context)

    if approval.status != "pending":
        raise ConflictError(f"This request was already {approval.status}.")
    if execution.status in TERMINAL_STATUSES:
        raise UnprocessableError("This execution already finished; there is nothing to approve.")

    approval.status = decision
    approval.decided_at = now_utc()
    approval.decided_by_id = context.user_id
    approval.decided_by_name = context.user.name
    approval.note = note

    # Hand the run back to the workers; the engine re-reads the decision.
    execution.status = "RUNNING"
    execution.claimed_by = None
    execution.heartbeat_at = None
    await audit.record(
        session,
        organization_id=context.organization_id,
        action="approval.decided",
        actor=audit.user_actor(context),
        outcome="success",
        target=("execution", execution.id),
        detail={"decision": decision, "tool": approval.tool, "capability": approval.capability},
    )
    await session.flush()
    return approval


async def get_organization_runtime(session: AsyncSession, *, context: AuthContext) -> Organization:
    organization = await session.get(Organization, context.organization_id)
    if organization is None:
        raise NotFoundError("No organization with this id.")
    return organization


async def set_kill_switch(
    session: AsyncSession, *, paused: bool, reason: str | None, context: AuthContext
) -> Organization:
    """Stops or resumes every execution in the organization.

    Engaging it is an emergency action any administrator can take. Releasing it
    is an owner decision: turning protection back off should be harder than
    turning it on.
    """
    if paused:
        authorization.require(context.role, "runtime:pause")
    else:
        authorization.require(context.role, "runtime:resume")

    organization = await get_organization_runtime(session, context=context)
    organization.executions_paused = paused
    organization.executions_paused_at = now_utc() if paused else None
    organization.executions_paused_by = context.user.name if paused else None
    organization.executions_paused_reason = (reason or None) if paused else None

    if paused:
        # Stop what is already running: the engine also checks, but a run that
        # nobody picks up again would otherwise sit claimed forever.
        await session.execute(
            update(Execution)
            .where(
                Execution.organization_id == organization.id,
                Execution.status.not_in(TERMINAL_STATUSES),
            )
            .values(cancel_requested_at=now_utc(), cancel_requested_by="the kill switch")
        )

    await audit.record(
        session,
        organization_id=context.organization_id,
        action="runtime.kill_switch_engaged" if paused else "runtime.kill_switch_released",
        actor=audit.user_actor(context),
        outcome="success",
        target=("organization", organization.id),
        detail={"reason": organization.executions_paused_reason},
    )
    await session.flush()
    return organization


async def pending_approval_count(session: AsyncSession, organization_id: str) -> int:
    rows = await session.scalars(
        select(ExecutionApproval.id).where(
            ExecutionApproval.organization_id == organization_id,
            ExecutionApproval.status == "pending",
        )
    )
    return len(list(rows))
