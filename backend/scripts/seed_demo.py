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
from app.db.models import Agent, AgentVersion, Execution, Installation, User
from app.db.session import create_engine, create_session_factory
from app.repositories import identity_repository
from app.schemas.enums import CAPABILITY_KEYS, Role
from app.schemas.registry import PermissionGrant
from app.services import auth_service, registry_service
from app.services.agent_service import (
    INITIAL_SECURITY_CHECKS,
    new_agent_id,
    new_execution_id,
)
from app.services.risk import derive_risk, permission_risk

ORGANIZATION_NAME = "Demo Workspace"
# A second organization exists so the marketplace has something to install that
# does not already belong to you.
PARTNER_NAME = "Partner Studio"
PARTNER_ACCOUNT = ("partner@example.com", "Partner Owner")

# How each demo agent is shared once it has a published version.
VISIBILITY = {
    "Research Scout": "public",
    "Threat Triage": "organization",
    "Code Review Assistant": "public",
}

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


def publish(agent: Agent, user: User, changelog: list[str]) -> AgentVersion:
    """Freeze the agent's configuration as a published version."""
    level, score = derive_risk(agent.permissions)
    return AgentVersion(
        id=registry_service.new_version_id(),
        agent_id=agent.id,
        organization_id=agent.organization_id,
        version=agent.version,
        status="published",
        manifest=registry_service.build_manifest(agent),
        changelog=changelog,
        risk_level=level,
        risk_score=score,
        created_at=NOW - timedelta(days=2),
        published_at=NOW - timedelta(days=2),
        created_by_id=user.id,
        created_by_name=user.name,
    )


PARTNER_AGENT: dict[str, Any] = {
    "name": "Contract Summariser",
    "description": (
        "Reads contract documents and produces a clause-by-clause summary with the "
        "obligations and dates it found."
    ),
    "category": "operations",
    "tags": ["contracts", "summaries", "legal"],
    "version": "1.2.0",
    "model": {
        "provider": "Model gateway",
        "model": "reasoning-large",
        "temperature": 0.1,
        "maxOutputTokens": 8192,
    },
    "tools": ["document_reader"],
    "resource_limits": {
        "maxRuntimeSeconds": 600,
        "maxMemoryMb": 1024,
        "maxTokensPerRun": 90000,
        "maxToolCalls": 30,
    },
    "security_policy": {
        "sandbox": "strict",
        "networkEgress": "none",
        "allowedDomains": [],
        "approvalRequiredFor": ["high", "critical"],
        "auditLogging": True,
    },
}


async def seed() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    created_agents = 0
    created_executions = 0

    created_accounts: list[tuple[str, str]] = []
    published_versions = 0
    created_installations = 0

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
                    # History comes from published versions now, not a JSON blob.
                    security_checks=INITIAL_SECURITY_CHECKS,
                )
                session.add(agent)
                by_name[spec["name"]] = agent
                created_agents += 1

            await session.flush()

            for name, visibility in VISIBILITY.items():
                listed = by_name.get(name)
                if listed is None or listed.visibility != "private":
                    continue
                session.add(publish(listed, owner, ["Published for the AgentHub demo."]))
                listed.visibility = visibility
                published_versions += 1
            await session.flush()

            created_installations += await seed_partner_organization(session)

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

    print(
        f"Seed complete: {created_agents} agents, {published_versions} published versions, "
        f"{created_installations} installations and {created_executions} executions added."
    )
    print(f"Database: {settings.safe_database_url}")
    if created_accounts:
        print()
        print("Demonstration accounts (development only; shown once):")
        for email, password in created_accounts:
            print(f"  {email}  {password}")
        print("Change or delete them before exposing this instance to anyone else.")


async def seed_partner_organization(session: Any) -> int:
    """A second organization publishing one agent, installed by the demo workspace.

    The install is deliberately narrower than the manifest asks for, so the UI
    shows the difference between what an agent requests and what it was given.
    """
    demo_org = await identity_repository.get_organization_by_slug(
        session, auth_service.slugify(ORGANIZATION_NAME)
    )
    partner = await identity_repository.get_organization_by_slug(
        session, auth_service.slugify(PARTNER_NAME)
    )
    if partner is not None or demo_org is None:
        return 0

    partner = await auth_service.create_organization(session, name=PARTNER_NAME)
    email, name = PARTNER_ACCOUNT
    user = await identity_repository.get_user_by_email(session, email)
    if user is None:
        user = await auth_service.create_user(
            session, email=email, name=name, password=secrets.token_urlsafe(16)
        )
    await auth_service.add_member(session, organization=partner, user=user, role="owner")

    granted_permissions = permissions(
        file_access={"level": "read_only", "scope": "Contract folder you choose"},
        tool_calling={"level": "allowed", "scope": "Declared reading tools"},
    )
    level, score = derive_risk(granted_permissions)
    agent = Agent(
        id=new_agent_id(PARTNER_AGENT["name"]),
        organization_id=partner.id,
        name=PARTNER_AGENT["name"],
        description=PARTNER_AGENT["description"],
        category=PARTNER_AGENT["category"],
        tags=PARTNER_AGENT["tags"],
        version=PARTNER_AGENT["version"],
        status="active",
        verification="verified",
        visibility="public",
        risk_level=level,
        risk_score=score,
        creator_id=user.id,
        creator_name=user.name,
        owner_id=user.id,
        owner_name=user.name,
        created_at=NOW - timedelta(days=45),
        updated_at=NOW - timedelta(days=5),
        last_execution_at=None,
        model=PARTNER_AGENT["model"],
        tools=PARTNER_AGENT["tools"],
        permissions=granted_permissions,
        resource_limits=PARTNER_AGENT["resource_limits"],
        security_policy=PARTNER_AGENT["security_policy"],
        security_checks=INITIAL_SECURITY_CHECKS,
    )
    session.add(agent)
    await session.flush()

    version = publish(agent, user, ["Clause summaries and obligation extraction."])
    session.add(version)
    await session.flush()

    # The demo workspace grants less than the manifest asks for.
    grants = registry_service.normalise_grants(
        version.manifest,
        [
            PermissionGrant(
                capability="file_access",
                level="read_only",
                scope="Shared contracts folder (read only)",
            )
        ],
    )
    granted_level, granted_score = derive_risk(grants)
    installer = await identity_repository.get_user_by_email(session, DEMO_ACCOUNTS[0][0])
    session.add(
        Installation(
            id=registry_service.new_installation_id(),
            organization_id=demo_org.id,
            agent_id=agent.id,
            agent_version_id=version.id,
            agent_name=agent.name,
            publisher_name=partner.name,
            status="active",
            grants=grants,
            risk_level=granted_level,
            risk_score=granted_score,
            note="Trial install: reading only, no tool calling.",
            installed_by_id=installer.id if installer else user.id,
            installed_by_name=installer.name if installer else user.name,
            created_at=NOW - timedelta(days=3),
            updated_at=NOW - timedelta(days=3),
        )
    )
    await session.flush()
    return 1


if __name__ == "__main__":
    asyncio.run(seed())
