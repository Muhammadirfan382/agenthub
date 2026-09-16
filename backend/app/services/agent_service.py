"""Agent rules.

Ownership is a placeholder until authentication exists (Phase 3): every agent
is attributed to the same demo user. Nothing here is an authorization check.
"""

import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.core.time import now_utc
from app.db.models import Agent, Execution
from app.repositories import agent_repository
from app.schemas.agent import AgentDraft
from app.schemas.enums import AgentStatus, ExecutionTrigger
from app.services.risk import derive_risk

PLACEHOLDER_USER_ID = "usr_demo_current"
PLACEHOLDER_USER_NAME = "Demo User"

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


async def create_agent(session: AsyncSession, draft: AgentDraft) -> Agent:
    if await agent_repository.get_agent_by_name(session, draft.name):
        raise ConflictError("An agent with this name already exists.")

    documents = _draft_documents(draft)
    level, score = derive_risk(documents["permissions"])
    now = now_utc()

    agent = Agent(
        id=new_agent_id(draft.name),
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
        creator_id=PLACEHOLDER_USER_ID,
        creator_name=PLACEHOLDER_USER_NAME,
        owner_id=PLACEHOLDER_USER_ID,
        owner_name=PLACEHOLDER_USER_NAME,
        created_at=now,
        updated_at=now,
        last_execution_at=None,
        versions=[
            {
                "version": draft.version,
                "releasedAt": now.isoformat(),
                "status": "draft",
                "changes": ["Created through the AgentHub API"],
            }
        ],
        security_checks=INITIAL_SECURITY_CHECKS,
        **documents,
    )
    session.add(agent)
    await session.flush()
    return agent


async def get_agent(session: AsyncSession, agent_id: str) -> Agent:
    agent = await agent_repository.get_agent(session, agent_id)
    if agent is None:
        raise NotFoundError("No agent with this id.")
    return agent


async def update_agent(session: AsyncSession, agent_id: str, draft: AgentDraft) -> Agent:
    agent = await get_agent(session, agent_id)

    clash = await agent_repository.get_agent_by_name(session, draft.name)
    if clash is not None and clash.id != agent.id:
        raise ConflictError("An agent with this name already exists.")

    documents = _draft_documents(draft)
    level, score = derive_risk(documents["permissions"])
    now = now_utc()

    if draft.version != agent.version:
        history = [
            {**entry, "status": "previous"} if entry.get("status") == "current" else entry
            for entry in agent.versions
        ]
        agent.versions = [
            {
                "version": draft.version,
                "releasedAt": now.isoformat(),
                "status": "current",
                "changes": ["Updated through the AgentHub API"],
            },
            *history,
        ]

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


async def delete_agent(session: AsyncSession, agent_id: str) -> None:
    agent = await get_agent(session, agent_id)
    await session.delete(agent)


async def set_status(session: AsyncSession, agent_id: str, status: AgentStatus) -> Agent:
    agent = await get_agent(session, agent_id)

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
    session: AsyncSession, agent_id: str, trigger: ExecutionTrigger = "manual"
) -> Execution:
    """Records an execution request. Nothing runs: there is no runtime yet."""
    agent = await get_agent(session, agent_id)
    if agent.status != "active":
        raise UnprocessableError(
            "Only active agents can be executed. This agent is " + agent.status + "."
        )

    now = now_utc()
    execution = Execution(
        id=new_execution_id(),
        agent_id=agent.id,
        agent_name=agent.name,
        status="QUEUED",
        trigger=trigger,
        started_at=now,
        model=str(agent.model.get("model", "unknown")),
    )
    agent.last_execution_at = now
    session.add(execution)
    await session.flush()
    return execution
