"""Execution endpoints. Reads are scoped to the session's organization."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthDep
from app.core.pagination import Page, PageParams, page_params
from app.db.session import SessionDep
from app.repositories import execution_repository
from app.schemas.enums import ExecutionStatus
from app.schemas.execution import ExecutionDetailRead, ExecutionRead
from app.services import authorization, execution_service
from app.services.mappers import to_execution_detail, to_execution_read

router = APIRouter(prefix="/executions", tags=["executions"])


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
    "/{execution_id}",
    response_model=ExecutionDetailRead,
    summary="Get one execution",
    description="Timeline, logs and tool calls are empty until the agent runtime records them.",
)
async def get_execution(
    session: SessionDep, auth: AuthDep, execution_id: str
) -> ExecutionDetailRead:
    return to_execution_detail(
        await execution_service.get_execution(session, execution_id, context=auth)
    )
