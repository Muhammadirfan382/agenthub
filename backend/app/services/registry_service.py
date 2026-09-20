"""Publishing, listing and installing agents.

Two rules shape everything here:

1. A published version is immutable. Editing the agent afterwards does not
   change what an installer agreed to; it changes what the *next* version will
   say.
2. Installing grants nothing by itself. Every capability starts denied, and a
   grant may never exceed what the manifest asked for.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.core.time import now_utc
from app.db.models import Agent, AgentVersion, Installation
from app.repositories import identity_repository, registry_repository
from app.schemas.enums import CAPABILITY_KEYS, LEVEL_RANK, PermissionLevel, Visibility
from app.schemas.registry import (
    InstallationCreate,
    InstallationUpdate,
    PermissionGrant,
    PublishRequest,
    VersionStatusUpdate,
)
from app.security import audit
from app.services import agent_service, authorization
from app.services.auth_service import AuthContext
from app.services.catalog import TOOL_CAPABILITIES
from app.services.risk import derive_risk, permission_risk

MIN_SCOPE_LENGTH = 3


def _granted(installation: Installation) -> list[str]:
    """The capabilities an installation grants, for the audit record."""
    return [
        str(grant.get("capability"))
        for grant in installation.grants
        if grant.get("level") != "denied"
    ]


def new_version_id() -> str:
    return "ver_" + uuid.uuid4().hex[:12]


def new_installation_id() -> str:
    return "ins_" + uuid.uuid4().hex[:12]


def build_manifest(agent: Agent) -> dict[str, Any]:
    """Freezes what the agent asks for, in the shape the API publishes."""
    return {
        "name": agent.name,
        "description": agent.description,
        "category": agent.category,
        "tags": list(agent.tags),
        "version": agent.version,
        "model": agent.model,
        "tools": list(agent.tools),
        "requiredPermissions": agent.permissions,
        "resourceLimits": agent.resource_limits,
        "securityPolicy": agent.security_policy,
    }


def unusable_tools(manifest: dict[str, Any], grants: list[dict[str, Any]]) -> list[str]:
    """Tools whose capability was not granted: they cannot do anything."""
    levels = {str(grant["capability"]): str(grant["level"]) for grant in grants}
    return [
        tool
        for tool in manifest.get("tools", [])
        if levels.get(TOOL_CAPABILITIES[str(tool)], "denied") == "denied"
    ]


async def _agent_for_publishing(
    session: AsyncSession, agent_id: str, *, context: AuthContext
) -> Agent:
    agent = await agent_service.get_agent(session, agent_id, context=context)
    authorization.require(
        context.role, "agent:publish", owns_resource=agent.owner_id == context.user_id
    )
    return agent


async def publish_version(
    session: AsyncSession, agent_id: str, body: PublishRequest, *, context: AuthContext
) -> AgentVersion:
    agent = await _agent_for_publishing(session, agent_id, context=context)

    if agent.verification == "rejected":
        raise UnprocessableError(
            "A rejected agent cannot be published. Resolve the review findings first."
        )
    if any(check.get("status") == "failed" for check in agent.security_checks):
        raise UnprocessableError("An agent with a failed security check cannot be published.")

    existing = await registry_repository.get_version_by_number(session, agent.id, agent.version)
    if existing is not None:
        raise ConflictError(
            f"Version {agent.version} is already published. Raise the version number first."
        )

    manifest = build_manifest(agent)
    level, score = derive_risk(agent.permissions)
    now = now_utc()

    version = AgentVersion(
        id=new_version_id(),
        agent_id=agent.id,
        organization_id=agent.organization_id,
        version=agent.version,
        status="published",
        manifest=manifest,
        changelog=list(body.changelog) or ["Published from the current configuration."],
        risk_level=level,
        risk_score=score,
        created_at=now,
        published_at=now,
        created_by_id=context.user_id,
        created_by_name=context.user.name,
    )
    session.add(version)

    if body.visibility is not None:
        agent.visibility = body.visibility
    agent.updated_at = now
    await audit.record(
        session,
        organization_id=context.organization_id,
        action="version.published",
        actor=audit.user_actor(context),
        outcome="success",
        target=("agent_version", version.id),
        detail={"agent": version.agent_id, "version": version.version},
    )
    await session.flush()
    return version


async def get_version(
    session: AsyncSession, agent_id: str, version_id: str, *, context: AuthContext
) -> AgentVersion:
    await agent_service.get_agent(session, agent_id, context=context)
    version = await registry_repository.get_version(session, version_id)
    if version is None or version.agent_id != agent_id:
        raise NotFoundError("No version with this id.")
    return version


async def set_version_status(
    session: AsyncSession,
    agent_id: str,
    version_id: str,
    body: VersionStatusUpdate,
    *,
    context: AuthContext,
) -> AgentVersion:
    await _agent_for_publishing(session, agent_id, context=context)
    version = await get_version(session, agent_id, version_id, context=context)

    if body.status == "draft":
        raise UnprocessableError("A published version cannot go back to draft.")
    if body.status == "published" and version.status == "deprecated":
        version.deprecated_at = None
    if body.status == "deprecated":
        version.deprecated_at = now_utc()

    version.status = body.status
    await audit.record(
        session,
        organization_id=context.organization_id,
        action="version.status_changed",
        actor=audit.user_actor(context),
        outcome="success",
        target=("agent_version", version.id),
        detail={"status": version.status},
    )
    await session.flush()
    return version


async def set_visibility(
    session: AsyncSession, agent_id: str, visibility: Visibility, *, context: AuthContext
) -> Agent:
    agent = await _agent_for_publishing(session, agent_id, context=context)

    if visibility != "private":
        published = await registry_repository.count_published_versions(session, agent.id)
        if published == 0:
            raise UnprocessableError(
                "Publish a version before listing this agent in the marketplace."
            )

    agent.visibility = visibility
    agent.updated_at = now_utc()
    await audit.record(
        session,
        organization_id=context.organization_id,
        action="agent.visibility_changed",
        actor=audit.user_actor(context),
        outcome="success",
        target=("agent", agent.id),
        detail={"visibility": agent.visibility},
    )
    await session.flush()
    return agent


def _requested_permissions(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(permission["capability"]): permission
        for permission in manifest.get("requiredPermissions", [])
    }


def normalise_grants(
    manifest: dict[str, Any], grants: list[PermissionGrant]
) -> list[dict[str, Any]]:
    """Deny by default, never exceed the request, and re-derive every risk.

    A client cannot grant a capability the manifest did not ask for, cannot
    grant more than it asked for, and cannot drop an approval requirement the
    publisher set.
    """
    requested = _requested_permissions(manifest)
    supplied = {grant.capability: grant for grant in grants}

    if len(supplied) != len(grants):
        raise UnprocessableError("Each capability may appear only once.")

    unknown = set(supplied) - set(requested)
    if unknown:
        raise UnprocessableError("This agent did not ask for: " + ", ".join(sorted(unknown)) + ".")

    result: list[dict[str, Any]] = []
    for capability in CAPABILITY_KEYS:
        request = requested.get(capability, {})
        requested_level = str(request.get("level", "denied"))
        grant = supplied.get(capability)
        level: PermissionLevel = grant.level if grant else "denied"

        if level != "denied" and LEVEL_RANK[level] > LEVEL_RANK[requested_level]:
            raise UnprocessableError(
                f"{capability}: you cannot grant more than the agent asked for ({requested_level})."
            )

        scope = (grant.scope if grant else "").strip()
        requires_approval = bool(grant.requires_approval) if grant else False
        risk = permission_risk(capability, level) if level != "denied" else "low"

        if level == "denied":
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

        if len(scope) < MIN_SCOPE_LENGTH:
            raise UnprocessableError(f"Describe the scope you are granting for {capability}.")
        if request.get("requiresApproval") and not requires_approval:
            raise UnprocessableError(
                f"{capability}: the publisher requires human approval, which cannot be removed."
            )
        if risk == "critical" and not requires_approval:
            raise UnprocessableError(
                f"{capability}: critical-risk grants must require human approval."
            )

        result.append(
            {
                "capability": capability,
                "level": level,
                "requiresApproval": requires_approval,
                "scope": scope,
                "risk": risk,
            }
        )
    return result


async def _installable_version(
    session: AsyncSession, version_id: str, *, context: AuthContext
) -> tuple[AgentVersion, Agent]:
    version = await registry_repository.get_version(session, version_id)
    if version is None:
        raise NotFoundError("No listing with this id.")

    agent = await session.get(Agent, version.agent_id)
    if agent is None:
        raise NotFoundError("No listing with this id.")

    visible = agent.visibility == "public" or (
        agent.organization_id == context.organization_id and agent.visibility == "organization"
    )
    if version.status != "published" or not visible:
        # Anything not listed for this caller is simply not there.
        raise NotFoundError("No listing with this id.")
    return version, agent


async def install(
    session: AsyncSession, body: InstallationCreate, *, context: AuthContext
) -> Installation:
    authorization.require(context.role, "installation:manage")
    version, agent = await _installable_version(session, body.agent_version_id, context=context)

    if agent.organization_id == context.organization_id:
        raise ConflictError(
            "This agent already belongs to your organization; it does not need installing."
        )
    existing = await registry_repository.get_installation_for_agent(
        session, context.organization_id, agent.id
    )
    if existing is not None:
        raise ConflictError("This agent is already installed. Update the installation instead.")

    grants = normalise_grants(version.manifest, body.grants)
    level, score = derive_risk(grants)
    publisher = await identity_repository.get_organization(session, version.organization_id)
    now = now_utc()

    installation = Installation(
        id=new_installation_id(),
        organization_id=context.organization_id,
        agent_id=agent.id,
        agent_version_id=version.id,
        agent_name=str(version.manifest.get("name", agent.name)),
        publisher_name=publisher.name if publisher else "Unknown publisher",
        status="active",
        grants=grants,
        risk_level=level,
        risk_score=score,
        note=body.note,
        installed_by_id=context.user_id,
        installed_by_name=context.user.name,
        created_at=now,
        updated_at=now,
    )
    session.add(installation)
    await audit.record(
        session,
        organization_id=context.organization_id,
        action="installation.created",
        actor=audit.user_actor(context),
        outcome="success",
        target=("installation", installation.id),
        detail={
            "agent": installation.agent_name,
            "grants": _granted(installation),
        },
    )
    await session.flush()
    return installation


async def get_installation(
    session: AsyncSession, installation_id: str, *, context: AuthContext
) -> Installation:
    authorization.require(context.role, "installation:read")
    installation = await registry_repository.get_installation(
        session, installation_id, context.organization_id
    )
    if installation is None:
        raise NotFoundError("No installation with this id.")
    return installation


async def update_installation(
    session: AsyncSession, installation_id: str, body: InstallationUpdate, *, context: AuthContext
) -> Installation:
    authorization.require(context.role, "installation:manage")
    installation = await get_installation(session, installation_id, context=context)
    version = await registry_repository.get_version(session, installation.agent_version_id)
    if version is None:
        raise NotFoundError("The installed version no longer exists.")

    if body.grants is not None:
        grants = normalise_grants(version.manifest, body.grants)
        installation.grants = grants
        installation.risk_level, installation.risk_score = derive_risk(grants)
    if body.status is not None:
        installation.status = body.status
    if body.note is not None:
        installation.note = body.note

    installation.updated_at = now_utc()
    await audit.record(
        session,
        organization_id=context.organization_id,
        action="installation.updated",
        actor=audit.user_actor(context),
        outcome="success",
        target=("installation", installation.id),
        detail={
            "status": installation.status,
            "grants": _granted(installation),
        },
    )
    await session.flush()
    return installation


async def uninstall(session: AsyncSession, installation_id: str, *, context: AuthContext) -> None:
    authorization.require(context.role, "installation:manage")
    installation = await get_installation(session, installation_id, context=context)
    await audit.record(
        session,
        organization_id=context.organization_id,
        action="installation.removed",
        actor=audit.user_actor(context),
        outcome="success",
        target=("installation", installation.id),
        detail={"agent": installation.agent_name},
    )
    await session.delete(installation)
    await session.flush()
