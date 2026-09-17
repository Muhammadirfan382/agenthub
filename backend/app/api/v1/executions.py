"""Execution endpoints: reading runs, controlling them, and watching them.

The runtime orchestrates but executes nothing yet, so every response carries
`runtime` and the trace it returns is a record of orchestration, not of work an
agent performed.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import AuthDep
from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.db.models import Execution
from app.db.session import SessionDep
from app.repositories import execution_repository, runtime_repository
from app.schemas.enums import TERMINAL_STATUSES, ExecutionStatus
from app.schemas.execution import (
    ApprovalDecisionRequest,
    ApprovalRead,
    ExecutionDetailRead,
    ExecutionRead,
)
from app.services import authorization, execution_service, runtime_service
from app.services.auth_service import AuthContext
from app.services.mappers import to_approval_read, to_execution_detail, to_execution_read

router = APIRouter(prefix="/executions", tags=["executions"])

#: How often the stream checks for new events: short enough to feel live, long
#: enough not to hammer the database.
STREAM_POLL_SECONDS = 1.0
STREAM_MAX_SECONDS = 600


async def _detail(session: AsyncSession, execution: Execution) -> ExecutionDetailRead:
    return to_execution_detail(
        execution,
        events=await runtime_repository.events(session, execution.id),
        logs=await runtime_repository.logs(session, execution.id),
        tool_calls=await runtime_repository.tool_calls(session, execution.id),
        approvals=await runtime_repository.approvals(session, execution.id),
    )


@router.get("", response_model=Page[ExecutionRead], summary="List executions")
async def list_executions(
    session: SessionDep,
    auth: AuthDep,
    page: Annotated[PageParams, Depends(page_params)],
    status_filter: Annotated[ExecutionStatus | None, Query(alias="status")] = None,
    agent_id: Annotated[str | None, Query(alias="agentId", max_length=64)] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
) -> Page[ExecutionRead]:
    authorization.require(auth.role, "execution:read")
    executions, total = await execution_repository.list_executions(
        session,
        organization_id=auth.organization_id,
        status=status_filter,
        agent_id=agent_id,
        search=search,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=[to_execution_read(execution) for execution in executions],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/approvals", response_model=Page[ApprovalRead], summary="Approvals waiting for a decision"
)
async def list_pending_approvals(
    session: SessionDep, auth: AuthDep, page: Annotated[PageParams, Depends(page_params)]
) -> Page[ApprovalRead]:
    authorization.require(auth.role, "execution:read")
    rows, total = await runtime_repository.pending_approvals(
        session, auth.organization_id, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[to_approval_read(approval, execution.agent_name) for approval, execution in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/{execution_id}",
    response_model=ExecutionDetailRead,
    summary="Get one execution",
    description="Includes everything the runtime recorded: timeline, logs, tool calls, approvals.",
)
async def get_execution(
    session: SessionDep, auth: AuthDep, execution_id: str
) -> ExecutionDetailRead:
    execution = await execution_service.get_execution(session, execution_id, context=auth)
    return await _detail(session, execution)


@router.post(
    "/{execution_id}/cancel",
    response_model=ExecutionDetailRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ask a running execution to stop",
    description="The runtime stops it at the next step boundary.",
)
async def cancel_execution(
    session: SessionDep, auth: AuthDep, execution_id: str
) -> ExecutionDetailRead:
    execution = await runtime_service.cancel(session, execution_id, context=auth)
    return await _detail(session, execution)


@router.post(
    "/{execution_id}/approvals/{approval_id}",
    response_model=ExecutionDetailRead,
    summary="Approve or refuse a paused step",
)
async def decide_approval(
    session: SessionDep,
    auth: AuthDep,
    execution_id: str,
    approval_id: str,
    body: ApprovalDecisionRequest,
) -> ExecutionDetailRead:
    approval = await runtime_service.decide_approval(
        session, approval_id, decision=body.decision, note=body.note, context=auth
    )
    if approval.execution_id != execution_id:
        raise NotFoundError("No approval request with this id.")
    execution = await execution_service.get_execution(session, execution_id, context=auth)
    return await _detail(session, execution)


async def _event_stream(
    session_factory: async_sessionmaker[AsyncSession],
    execution_id: str,
    context: AuthContext,
    request: Request,
) -> AsyncIterator[str]:
    """Server-sent events: status changes and new timeline entries.

    Each tick opens its own short session, so watching a run never holds a
    database connection open between polls.
    """
    last_sequence = 0
    last_status = ""
    elapsed = 0.0

    while elapsed < STREAM_MAX_SECONDS:
        if await request.is_disconnected():
            return

        async with session_factory() as session:
            execution = await execution_service.get_execution(
                session, execution_id, context=context
            )
            events = await runtime_repository.events(session, execution_id)
            new_events = [event for event in events if event.sequence > last_sequence]
            finished = execution.status in TERMINAL_STATUSES
            status_changed = execution.status != last_status
            last_status = execution.status

        for event in new_events:
            last_sequence = event.sequence
            payload = {
                "id": event.id,
                "at": event.at.isoformat(),
                "kind": event.kind,
                "label": event.label,
                "detail": event.detail,
            }
            yield f"event: timeline\ndata: {json.dumps(payload)}\n\n"

        if status_changed or new_events:
            yield f"event: status\ndata: {json.dumps({'status': last_status})}\n\n"

        if finished:
            yield f"event: finished\ndata: {json.dumps({'status': last_status})}\n\n"
            return

        await asyncio.sleep(STREAM_POLL_SECONDS)
        elapsed += STREAM_POLL_SECONDS

    yield 'event: timeout\ndata: {"reason": "stream_expired"}\n\n'


@router.get(
    "/{execution_id}/stream",
    summary="Watch an execution as it runs",
    description="Server-sent events. Ends when the execution finishes.",
    response_class=StreamingResponse,
)
async def stream_execution(
    request: Request, session: SessionDep, auth: AuthDep, execution_id: str
) -> StreamingResponse:
    # Access is proven before the stream opens, so an unauthorised watcher gets
    # a normal error instead of an empty stream.
    await execution_service.get_execution(session, execution_id, context=auth)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory

    return StreamingResponse(
        _event_stream(session_factory, execution_id, auth, request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
