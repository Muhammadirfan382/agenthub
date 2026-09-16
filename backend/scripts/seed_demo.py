"""Insert a demonstration organization, accounts, agents and executions.

    .venv/Scripts/python.exe -m scripts.seed_demo

Everything written here is fictional and exists so the API and UI have
something to show. Execution rows are records only: no agent has run, because
the runtime does not exist yet. Existing rows are skipped, so the script is
safe to run twice.

The demo accounts get randomly generated passwords, printed once when they are
created. They are for local development only: never seed them into an
environment that anyone else can reach.
"""

import asyncio
import secrets
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.time import now_utc
from app.db.models import Agent, Execution, User
from app.db.session import create_engine, create_session_factory
from app.repositories import identity_repository
from app.schemas.enums import CAPABILITY_KEYS, Role
from app.services import auth_service
from app.services.agent_service import (
    INITIAL_SECURITY_CHECKS,
    new_agent_id,
    new_execution_id,
)
from app.services.risk import derive_risk, permission_risk

ORGANIZATION_NAME = "Demo Workspace"

# Addresses in example.com are reserved for documentation and cannot receive mail.
DEMO_ACCOUNTS: list[tuple[str, str, Role]] = [
    ("owner@example.com", "Demo Owner", "owner"),
    ("member@example.com", "Demo Member", "member"),
    ("viewer@example.com", "Demo Viewer", "viewer"),
]

NOW = now_utc()


def permissions(**granted: dict[str, Any]) -> list[dict[str, Any]]:
    """Deny everything, then apply the granted capabilities."""
    result: list[dict[str, Any]] = []
    for capability in CAPABILITY_KEYS:
        override = granted.get(capability)
        if override is None:
            result.append(
                {
                    "capability": capability,
                    "level": "denied",
                    "requiresApproval": False,
                    "scope": "Not granted",
                    "risk": "low",
                }
            )
            continue
        level = str(override["level"])
        result.append(
            {
                "capability": capability,
                "level": level,
                "requiresApproval": bool(override.get("requiresApproval", False)),
                "scope": str(override["scope"]),
                "risk": permission_risk(capability, level),  # type: ignore[arg-type]
            }
        )
    return result


DEMO_AGENTS: list[dict[str, Any]] = [
    {
        "name": "Research Scout",
        "description": (
            "Searches approved sources, reads documents and produces cited research briefs. "
            "Never writes to external systems."
        ),
        "category": "research",
        "tags": ["research", "citations", "summaries"],
        "version": "2.3.1",
        "status": "active",
        "verification": "verified",
        "model": {
            "provider": "Model gateway",
            "model": "balanced-large",
            "temperature": 0.2,
            "maxOutputTokens": 4096,
        },
        "tools": ["web_search", "document_reader"],
        "permissions": permissions(
            web_access={"level": "restricted", "scope": "Allow-listed research domains only"},
            file_access={"level": "read_only", "scope": "Shared research folder"},
            tool_calling={"level": "allowed", "scope": "Declared read-only tools"},
        ),
        "resource_limits": {
            "maxRuntimeSeconds": 600,
            "maxMemoryMb": 512,
            "maxTokensPerRun": 60000,
            "maxToolCalls": 40,
        },
        "security_policy": {
            "sandbox": "strict",
            "networkEgress": "allow_list",
            "allowedDomains": ["arxiv.org", "docs.example.com"],
            "approvalRequiredFor": ["high", "critical"],
            "auditLogging": True,
        },
    },
    {
        "name": "Threat Triage",
        "description": (
            "Reviews security alerts, correlates related events and drafts a triage summary "
            "with recommended containment steps."
        ),
        "category": "security",
        "tags": ["security", "siem", "triage"],
        "version": "1.8.0",
        "status": "active",
        "verification": "verified",
        "model": {
            "provider": "Model gateway",
            "model": "reasoning-large",
            "temperature": 0.1,
            "maxOutputTokens": 8192,
        },
        "tools": ["api_request", "chart_renderer"],
        "permissions": permissions(
            api_access={"level": "restricted", "scope": "SIEM read API and ticketing"},
            database_access={"level": "read_only", "scope": "Alert history (read only)"},
            tool_calling={"level": "allowed", "scope": "Declared triage tools"},
            email_send={
                "level": "restricted",
                "scope": "On-call distribution list",
                "requiresApproval": True,
            },
        ),
        "resource_limits": {
            "maxRuntimeSeconds": 900,
            "maxMemoryMb": 1024,
            "maxTokensPerRun": 120000,
            "maxToolCalls": 80,
        },
        "security_policy": {
            "sandbox": "strict",
            "networkEgress": "allow_list",
            "allowedDomains": ["siem.internal.example"],
            "approvalRequiredFor": ["high", "critical"],
            "auditLogging": True,
        },
    },
    {
        "name": "Code Review Assistant",
        "description": (
            "Reviews pull requests for correctness and security issues, runs tests in a sandbox "
            "and posts review comments."
        ),
        "category": "engineering",
        "tags": ["code-review", "testing", "github"],
        "version": "3.0.2",
        "status": "paused",
        "verification": "verified",
        "model": {
            "provider": "Model gateway",
            "model": "balanced-large",
            "temperature": 0.3,
            "maxOutputTokens": 8192,
        },
        "tools": ["code_sandbox", "document_reader"],
        "permissions": permissions(
            api_access={"level": "restricted", "scope": "Pull request comments only"},
            file_access={"level": "read_only", "scope": "Repository checkout"},
            tool_calling={"level": "allowed", "scope": "Declared review tools"},
            code_execution={
                "level": "restricted",
                "scope": "Test suite inside sandbox",
                "requiresApproval": True,
            },
        ),
        "resource_limits": {
            "maxRuntimeSeconds": 1200,
            "maxMemoryMb": 2048,
            "maxTokensPerRun": 150000,
            "maxToolCalls": 60,
        },
        "security_policy": {
            "sandbox": "strict",
            "networkEgress": "allow_list",
            "allowedDomains": ["api.github.example"],
            "approvalRequiredFor": ["high", "critical"],
            "auditLogging": True,
        },
    },
    {
        "name": "SEO Auditor",
        "description": "Crawls a site you own and lists technical SEO fixes by priority.",
        "category": "marketing",
        "tags": ["seo", "crawler", "audit"],
        "version": "0.3.0",
        "status": "draft",
        "verification": "unverified",
        "model": {
            "provider": "Model gateway",
            "model": "fast-small",
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        },
        "tools": ["web_search"],
        "permissions": permissions(
            web_access={"level": "restricted", "scope": "Verified domains you own"},
            tool_calling={"level": "allowed", "scope": "Declared audit tools"},
        ),
        "resource_limits": {
            "maxRuntimeSeconds": 900,
            "maxMemoryMb": 512,
            "maxTokensPerRun": 40000,
            "maxToolCalls": 200,
        },
        "security_policy": {
            "sandbox": "standard",
            "networkEgress": "allow_list",
            "allowedDomains": ["www.example.com"],
            "approvalRequiredFor": ["high", "critical"],
            "auditLogging": True,
        },
    },
]

# Seeded execution records. Marked as seed data in the result summary.
DEMO_EXECUTIONS: list[dict[str, Any]] = [
    {
        "agent": "Threat Triage",
        "status": "QUEUED",
        "minutes_ago": 2,
        "duration_ms": None,
        "tokens": (0, 0),
        "tool_calls": 0,
        "result": None,
    },
    {
        "agent": "Research Scout",
        "status": "COMPLETED",
        "minutes_ago": 95,
        "duration_ms": 97_000,
        "tokens": (21870, 3380),
        "tool_calls": 3,
        "result": "Brief with 9 cited sources produced (seeded demo record).",
    },
    {
        "agent": "Code Review Assistant",
        "status": "FAILED",
        "minutes_ago": 240,
        "duration_ms": 62_000,
        "tokens": (12040, 890),
        "tool_calls": 2,
        "result": None,
    },
]


async def seed() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    created_agents = 0
    created_executions = 0

    created_accounts: list[tuple[str, str]] = []

    try:
        async with factory() as session:
            organization = await identity_repository.get_organization_by_slug(
                session, auth_service.slugify(ORGANIZATION_NAME)
            )
            if organization is None:
                organization = await auth_service.create_organization(
                    session, name=ORGANIZATION_NAME
                )

            owner: User | None = None
            for email, name, role in DEMO_ACCOUNTS:
                user = await identity_repository.get_user_by_email(session, email)
                if user is None:
                    # Printed once, below. Nothing is stored in this file.
                    password = secrets.token_urlsafe(16)
                    user = await auth_service.create_user(
                        session, email=email, name=name, password=password
                    )
                    created_accounts.append((email, password))
                if (
                    await identity_repository.get_membership(session, user.id, organization.id)
                    is None
                ):
                    await auth_service.add_member(
                        session, organization=organization, user=user, role=role
                    )
                if role == "owner":
                    owner = user
            assert owner is not None  # noqa: S101 - the owner is always in DEMO_ACCOUNTS

            by_name: dict[str, Agent] = {}
            for spec in DEMO_AGENTS:
                existing = await session.scalar(
                    select(Agent).where(
                        Agent.organization_id == organization.id, Agent.name == spec["name"]
                    )
                )
                if existing is not None:
                    by_name[spec["name"]] = existing
                    continue

                level, score = derive_risk(spec["permissions"])
                agent = Agent(
                    id=new_agent_id(spec["name"]),
                    organization_id=organization.id,
                    name=spec["name"],
                    description=spec["description"],
                    category=spec["category"],
                    tags=spec["tags"],
                    version=spec["version"],
                    status=spec["status"],
                    verification=spec["verification"],
                    risk_level=level,
                    risk_score=score,
                    creator_id=owner.id,
                    creator_name=owner.name,
                    owner_id=owner.id,
                    owner_name=owner.name,
                    created_at=NOW - timedelta(days=30),
                    updated_at=NOW - timedelta(days=2),
                    last_execution_at=None,
                    model=spec["model"],
                    tools=spec["tools"],
                    permissions=spec["permissions"],
                    resource_limits=spec["resource_limits"],
                    security_policy=spec["security_policy"],
                    versions=[
                        {
                            "version": spec["version"],
                            "releasedAt": (NOW - timedelta(days=2)).isoformat(),
                            "status": "current",
                            "changes": ["Seeded demonstration agent"],
                        }
                    ],
                    security_checks=INITIAL_SECURITY_CHECKS,
                )
                session.add(agent)
                by_name[spec["name"]] = agent
                created_agents += 1

            await session.flush()

            # Timestamps are relative to the current run, so they can never match an
            # earlier row: treat any existing execution as "already seeded" instead.
            already_seeded = await session.scalar(select(func.count()).select_from(Execution))

            for spec in [] if already_seeded else DEMO_EXECUTIONS:
                agent = by_name[spec["agent"]]
                started = NOW - timedelta(minutes=int(spec["minutes_ago"]))
                duration = spec["duration_ms"]
                session.add(
                    Execution(
                        id=new_execution_id(),
                        organization_id=organization.id,
                        agent_id=agent.id,
                        agent_name=agent.name,
                        status=spec["status"],
                        trigger="manual",
                        started_at=started,
                        ended_at=started + timedelta(milliseconds=duration) if duration else None,
                        duration_ms=duration,
                        model=str(agent.model["model"]),
                        token_input=int(spec["tokens"][0]),
                        token_output=int(spec["tokens"][1]),
                        tool_call_count=int(spec["tool_calls"]),
                        result_summary=spec["result"],
                    )
                )
                agent.last_execution_at = started
                created_executions += 1

            await session.commit()
    finally:
        await engine.dispose()

    print(f"Seed complete: {created_agents} agents and {created_executions} executions added.")
    print(f"Database: {settings.safe_database_url}")
    if created_accounts:
        print()
        print("Demonstration accounts (development only; shown once):")
        for email, password in created_accounts:
            print(f"  {email}  {password}")
        print("Change or delete them before exposing this instance to anyone else.")


if __name__ == "__main__":
    asyncio.run(seed())
