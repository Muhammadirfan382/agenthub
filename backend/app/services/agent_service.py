"""Agent rules and the authorization that goes with them.

Every function takes the caller's `AuthContext`: agents are read and written
only inside the caller's organization, and each action is checked against the
permission matrix in `authorization.py` before anything happens. A member may
act on an agent they own; changing anyone else's agent needs admin or owner.
"""

import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.core.time import now_utc
from app.db.models import Agent, Execution, Organization
from app.repositories import agent_repository
from app.runtime.engine import RUNTIME_NAME
from app.schemas.agent import AgentDraft
from app.schemas.enums import AgentStatus, ExecutionTrigger
from app.services import authorization
from app.services.auth_service import AuthContext
from app.services.risk import derive_risk

INITIAL_SECURITY_CHECKS: list[dict[str, Any]] = [
    {
        "id": "chk_dependencies",
        "name": "Dependency vulnerability scan",
        "status": "not_run",
        "detail": "Not yet evaluated.",
    },
    {
        "id": "chk_secrets",
        "name": "Embedded secret detection",
        "status": "not_run",
        "detail": "Not yet evaluated.",
    },
    {
        "id": "chk_permissions",
        "name": "Permission minimisation",
        "status": "not_run",
        "detail": "Not yet evaluated.",
    },
    {
        "id": "chk_injection",
        "name": "Prompt-injection evaluation",
        "status": "not_run",
        "detail": "Not yet evaluated.",
    },
    {
        "id": "chk_egress",
        "name": "Network egress policy",
        "status": "not_run",
        "detail": "Not yet evaluated.",
    },
]


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "agent"


def new_agent_id(name: str) -> str:
    return "agt_" + _slug(name)[:32] + "_" + uuid.uuid4().hex[:8]


def new_execution_id() -> str:
    return "exe_" + uuid.uuid4().hex[:12]


def _draft_documents(draft: AgentDraft) -> dict[str, Any]:
    return {
        "model": draft.model.model_dump(by_alias=True),
        "tools": list(draft.tools),
        "permissions": draft.normalised_permissions(),
        "resource_limits": draft.resource_limits.model_dump(by_alias=True),
        "security_policy": draft.security_policy.model_dump(by_alias=True),
    }


async def create_agent(session: AsyncSession, draft: AgentDraft, *, context: AuthContext) -> Agent:
    authorization.require(context.role, "agent:create")

    if await agent_repository.get_agent_by_name(session, draft.name, context.organization_id):
        raise ConflictError("An agent with this name already exists.")

    documents = _draft_documents(draft)
    level, score = derive_risk(documents["permissions"])
    now = now_utc()

    agent = Agent(
        id=new_agent_id(draft.name),
        organization_id=context.organization_id,
        name=draft.name,
        description=draft.description,
        category=draft.category,
        tags=list(draft.tags),
        version=draft.version,
        # New agents start as unverified drafts. Verification is a review
        # process that does not exist yet.
        status="draft",
        verification="unverified",
        risk_level=level,
        risk_score=score,
        creator_id=context.user_id,
        creator_name=context.user.name,
        owner_id=context.user_id,
        owner_name=context.user.name,
        created_at=now,
        updated_at=now,
        last_execution_at=None,
        visibility="private",
        security_checks=INITIAL_SECURITY_CHECKS,
        **documents,
    )
    session.add(agent)
    await session.flush()
    return agent


async def get_agent(session: AsyncSession, agent_id: str, *, context: AuthContext) -> Agent:
    """Reads are organization-scoped: another organization's id is a 404."""
    authorization.require(context.role, "agent:read")
    agent = await agent_repository.get_agent(session, agent_id, context.organization_id)
    if agent is None:
        raise NotFoundError("No agent with this id.")
    return agent


async def _agent_for_change(
    session: AsyncSession, agent_id: str, *, context: AuthContext, action: authorization.Action
) -> Agent:
    agent = await get_agent(session, agent_id, context=context)
    authorization.require(context.role, action, owns_resource=agent.owner_id == context.user_id)
    return agent


async def update_agent(
    session: AsyncSession, agent_id: str, draft: AgentDraft, *, context: AuthContext
) -> Agent:
    agent = await _agent_for_change(session, agent_id, context=context, action="agent:update")

    clash = await agent_repository.get_agent_by_name(session, draft.name, context.organization_id)
    if clash is not None and clash.id != agent.id:
        raise ConflictError("An agent with this name already exists.")

    documents = _draft_documents(draft)
    level, score = derive_risk(documents["permissions"])
    now = now_utc()

    agent.name = draft.name
    agent.description = draft.description
    agent.category = draft.category
    agent.tags = list(draft.tags)
    agent.version = draft.version
    agent.risk_level = level
    agent.risk_score = score
    agent.updated_at = now
    for field, value in documents.items():
        setattr(agent, field, value)

    await session.flush()
    return agent


async def delete_agent(session: AsyncSession, agent_id: str, *, context: AuthContext) -> None:
    agent = await _agent_for_change(session, agent_id, context=context, action="agent:delete")
    await session.delete(agent)


async def set_status(
    session: AsyncSession, agent_id: str, status: AgentStatus, *, context: AuthContext
) -> Agent:
    agent = await _agent_for_change(session, agent_id, context=context, action="agent:update")

    if status == "active":
        if agent.verification == "rejected":
            raise UnprocessableError(
                "A rejected agent cannot be activated. Resolve the review findings first."
            )
        failed = [check for check in agent.security_checks if check.get("status") == "failed"]
        if failed:
            raise UnprocessableError("An agent with a failed security check cannot be activated.")

    agent.status = status
    agent.updated_at = now_utc()
    await session.flush()
    return agent


async def request_execution(
    session: AsyncSession,
    agent_id: str,
    trigger: ExecutionTrigger = "manual",
    *,
    context: AuthContext,
    input_text: str | None = None,
) -> Execution:
    """Queues a run for the runtime to pick up.

    The runtime decides when it starts whether a real model drives the run or
    the scripted plan is recorded (see app/runtime/engine.py). `input_text` is
    what the requester asked for; it reaches the model as the user's message.
    """
    agent = await _agent_for_change(session, agent_id, context=context, action="agent:execute")
    if agent.status != "active":
        raise UnprocessableError(
            "Only active agents can be executed. This agent is " + agent.status + "."
        )

    organization = await session.get(Organization, agent.organization_id)
    if organization is not None and organization.executions_paused:
        reason = organization.executions_paused_reason or "No reason given."
        raise UnprocessableError(
            "Executions are paused for this organization by the kill switch. " + reason
        )

    limits = agent.resource_limits
    now = now_utc()
    execution = Execution(
        id=new_execution_id(),
        organization_id=agent.organization_id,
        agent_id=agent.id,
        agent_name=agent.name,
        status="QUEUED",
        trigger=trigger,
        runtime=RUNTIME_NAME,
        mode="simulated",
        input_text=input_text or None,
        requested_by_id=context.user_id,
        requested_by_name=context.user.name,
        started_at=now,
        model=str(agent.model.get("model", "unknown")),
        max_runtime_seconds=int(limits.get("maxRuntimeSeconds", 300)),
        max_tokens=int(limits.get("maxTokensPerRun", 50_000)),
        max_tool_calls=int(limits.get("maxToolCalls", 20)),
    )
    agent.last_execution_at = now
    session.add(execution)
    await session.flush()
    return execution
