"""Agent endpoints.

Every route requires a session (`AuthDep`) and works only inside that session's
organization. The permission checks themselves live in the service layer.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import AuthDep
from app.core.pagination import Page, PageParams, page_params
from app.db.session import SessionDep
from app.repositories import agent_repository
from app.schemas.agent import AgentDraft, AgentRead, AgentStatusUpdate
from app.schemas.enums import AgentCategory, AgentSort, AgentStatus, RiskLevel
from app.schemas.execution import ExecutionRead, ExecutionRequest
from app.services import agent_service, authorization
from app.services.mappers import to_agent_read, to_execution_read

router = APIRouter(prefix="/agents", tags=["agents"])

SearchQuery = Annotated[
    str | None, Query(max_length=120, description="Matches name, description or creator.")
]


@router.get("", response_model=Page[AgentRead], summary="List agents")
async def list_agents(
    session: SessionDep,
    auth: AuthDep,
    page: Annotated[PageParams, Depends(page_params)],
    search: SearchQuery = None,
    status_filter: Annotated[AgentStatus | None, Query(alias="status")] = None,
    risk: RiskLevel | None = None,
    category: AgentCategory | None = None,
    sort: AgentSort = "updated_desc",
) -> Page[AgentRead]:
    authorization.require(auth.role, "agent:read")
    agents, total = await agent_repository.list_agents(
        session,
        organization_id=auth.organization_id,
        search=search,
        status=status_filter,
        risk=risk,
        category=category,
        sort=sort,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(
        items=[to_agent_read(agent) for agent in agents],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "", response_model=AgentRead, status_code=status.HTTP_201_CREATED, summary="Create an agent"
)
async def create_agent(session: SessionDep, auth: AuthDep, draft: AgentDraft) -> AgentRead:
    return to_agent_read(await agent_service.create_agent(session, draft, context=auth))


@router.get("/{agent_id}", response_model=AgentRead, summary="Get one agent")
async def get_agent(session: SessionDep, auth: AuthDep, agent_id: str) -> AgentRead:
    return to_agent_read(await agent_service.get_agent(session, agent_id, context=auth))


@router.put("/{agent_id}", response_model=AgentRead, summary="Replace an agent configuration")
async def update_agent(
    session: SessionDep, auth: AuthDep, agent_id: str, draft: AgentDraft
) -> AgentRead:
    return to_agent_read(await agent_service.update_agent(session, agent_id, draft, context=auth))


@router.patch("/{agent_id}/status", response_model=AgentRead, summary="Change agent status")
async def set_agent_status(
    session: SessionDep, auth: AuthDep, agent_id: str, update: AgentStatusUpdate
) -> AgentRead:
    return to_agent_read(
        await agent_service.set_status(session, agent_id, update.status, context=auth)
    )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an agent")
async def delete_agent(session: SessionDep, auth: AuthDep, agent_id: str) -> Response:
    await agent_service.delete_agent(session, agent_id, context=auth)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{agent_id}/executions",
    response_model=ExecutionRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request an execution",
    description=(
        "Queues a run. With a model provider configured, a real model drives it through "
        "the model gateway; tools are checked but never executed."
    ),
)
async def request_execution(
    session: SessionDep, auth: AuthDep, agent_id: str, body: ExecutionRequest | None = None
) -> ExecutionRead:
    trigger = body.trigger if body else "manual"
    return to_execution_read(
        await agent_service.request_execution(
            session,
            agent_id,
            trigger,
            context=auth,
            input_text=body.input if body else None,
        )
    )
