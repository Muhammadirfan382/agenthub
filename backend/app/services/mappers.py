"""ORM rows to API models.

Nested value objects are stored as JSON documents with camelCase keys, which is
what the schemas expect, so they validate directly.
"""

from typing import TYPE_CHECKING

from app.core.time import ensure_utc
from app.db.models import (
    Agent,
    AgentVersion,
    Execution,
    ExecutionApproval,
    ExecutionEvent,
    ExecutionLog,
    ExecutionToolCall,
    Installation,
    Membership,
    Organization,
    User,
)
from app.schemas.agent import AgentRead
from app.schemas.auth import (
    MemberRead,
    OrganizationMembershipRead,
    OrganizationRead,
    SessionRead,
    UserRead,
)
from app.schemas.execution import ApprovalRead, ExecutionDetailRead, ExecutionRead
from app.schemas.registry import (
    AgentVersionRead,
    InstallationDetail,
    InstallationRead,
    MarketplaceListing,
    MarketplaceListingDetail,
)
from app.services import registry_service

if TYPE_CHECKING:
    from app.services.auth_service import AuthContext


def to_agent_read(agent: Agent) -> AgentRead:
    return AgentRead.model_validate(
        {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "category": agent.category,
            "tags": agent.tags,
            "version": agent.version,
            "status": agent.status,
            "verification": agent.verification,
            "visibility": agent.visibility,
            "riskLevel": agent.risk_level,
            "riskScore": agent.risk_score,
            "creator": {"id": agent.creator_id, "name": agent.creator_name},
            "owner": {"id": agent.owner_id, "name": agent.owner_name},
            "createdAt": ensure_utc(agent.created_at),
            "updatedAt": ensure_utc(agent.updated_at),
            "lastExecutionAt": ensure_utc(agent.last_execution_at)
            if agent.last_execution_at
            else None,
            "model": agent.model,
            "tools": agent.tools,
            "permissions": agent.permissions,
            "resourceLimits": agent.resource_limits,
            "securityPolicy": agent.security_policy,
            "securityChecks": agent.security_checks,
        }
    )


def _execution_payload(execution: Execution, *, pending_approvals: int = 0) -> dict[str, object]:
    return {
        "id": execution.id,
        "agentId": execution.agent_id,
        "agentName": execution.agent_name,
        "status": execution.status,
        "trigger": execution.trigger,
        "runtime": execution.runtime,
        "startedAt": ensure_utc(execution.started_at),
        "endedAt": ensure_utc(execution.ended_at) if execution.ended_at else None,
        "durationMs": execution.duration_ms,
        "model": execution.model,
        "tokenUsage": {"input": execution.token_input, "output": execution.token_output},
        "toolCallCount": execution.tool_call_count,
        "resultSummary": execution.result_summary,
        "requestedBy": execution.requested_by_name,
        "budget": {
            "maxRuntimeSeconds": execution.max_runtime_seconds,
            "maxTokens": execution.max_tokens,
            "maxToolCalls": execution.max_tool_calls,
        },
        "cancelRequested": execution.cancel_requested_at is not None,
        "pendingApprovals": pending_approvals,
    }


def to_execution_read(execution: Execution, *, pending_approvals: int = 0) -> ExecutionRead:
    return ExecutionRead.model_validate(
        _execution_payload(execution, pending_approvals=pending_approvals)
    )


def to_approval_read(approval: ExecutionApproval, agent_name: str) -> ApprovalRead:
    return ApprovalRead.model_validate(
        {
            "id": approval.id,
            "executionId": approval.execution_id,
            "agentName": agent_name,
            "capability": approval.capability,
            "tool": approval.tool,
            "reason": approval.reason,
            "riskLevel": approval.risk_level,
            "status": approval.status,
            "requestedAt": ensure_utc(approval.requested_at),
            "decidedAt": ensure_utc(approval.decided_at) if approval.decided_at else None,
            "decidedBy": approval.decided_by_name,
            "note": approval.note,
            "automatic": approval.automatic,
        }
    )


def to_execution_detail(
    execution: Execution,
    *,
    events: list[ExecutionEvent],
    logs: list[ExecutionLog],
    tool_calls: list[ExecutionToolCall],
    approvals: list[ExecutionApproval],
) -> ExecutionDetailRead:
    pending = sum(1 for approval in approvals if approval.status == "pending")
    payload = _execution_payload(execution, pending_approvals=pending)
    payload["timeline"] = [
        {
            "id": event.id,
            "at": ensure_utc(event.at),
            "kind": event.kind,
            "label": event.label,
            "detail": event.detail,
        }
        for event in events
    ]
    payload["logs"] = [
        {
            "id": entry.id,
            "at": ensure_utc(entry.at),
            "level": entry.level,
            "message": entry.message,
        }
        for entry in logs
    ]
    payload["toolCalls"] = [
        {
            "id": call.id,
            "tool": call.tool,
            "capability": call.capability,
            "status": call.status,
            "startedAt": ensure_utc(call.started_at),
            "durationMs": call.duration_ms,
            "inputSummary": call.input_summary,
            "outputSummary": call.output_summary,
        }
        for call in tool_calls
    ]
    payload["approvals"] = [
        to_approval_read(approval, execution.agent_name).model_dump(by_alias=True)
        for approval in approvals
    ]
    payload["error"] = (
        {"code": execution.error_code, "message": execution.error_message}
        if execution.error_code
        else None
    )
    payload["result"] = execution.result_summary
    return ExecutionDetailRead.model_validate(payload)


def to_user_read(user: User) -> UserRead:
    """Never includes the password hash."""
    return UserRead.model_validate(
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "status": user.status,
            "timezone": user.timezone,
            "createdAt": ensure_utc(user.created_at),
            "lastLoginAt": ensure_utc(user.last_login_at) if user.last_login_at else None,
        }
    )


def to_organization_read(organization: Organization) -> OrganizationRead:
    return OrganizationRead.model_validate(
        {"id": organization.id, "name": organization.name, "slug": organization.slug}
    )


def to_member_read(membership: Membership, user: User) -> MemberRead:
    return MemberRead.model_validate(
        {
            "id": membership.id,
            "userId": user.id,
            "email": user.email,
            "name": user.name,
            "role": membership.role,
            "status": user.status,
            "createdAt": ensure_utc(membership.created_at),
            "lastLoginAt": ensure_utc(user.last_login_at) if user.last_login_at else None,
        }
    )


def to_session_read(
    context: "AuthContext", memberships: list[tuple[Membership, Organization]]
) -> SessionRead:
    """The whole answer to "who am I and what may I do here"."""
    return SessionRead.model_validate(
        {
            "user": to_user_read(context.user).model_dump(by_alias=True),
            "organization": to_organization_read(context.organization).model_dump(by_alias=True),
            "role": context.role,
            "memberships": [
                OrganizationMembershipRead.model_validate(
                    {
                        "organization": to_organization_read(organization).model_dump(
                            by_alias=True
                        ),
                        "role": membership.role,
                    }
                ).model_dump(by_alias=True)
                for membership, organization in memberships
            ],
            "expiresAt": ensure_utc(context.session.expires_at),
        }
    )


def to_version_read(version: AgentVersion) -> AgentVersionRead:
    return AgentVersionRead.model_validate(
        {
            "id": version.id,
            "agentId": version.agent_id,
            "version": version.version,
            "status": version.status,
            "riskLevel": version.risk_level,
            "riskScore": version.risk_score,
            "changelog": version.changelog,
            "manifest": version.manifest,
            "createdAt": ensure_utc(version.created_at),
            "publishedAt": ensure_utc(version.published_at) if version.published_at else None,
            "deprecatedAt": ensure_utc(version.deprecated_at) if version.deprecated_at else None,
            "createdBy": version.created_by_name,
        }
    )


def _listing_payload(
    version: AgentVersion,
    agent: Agent,
    publisher: Organization,
    installation: Installation | None,
    organization_id: str,
) -> dict[str, object]:
    manifest = version.manifest
    return {
        "id": version.id,
        "agentId": agent.id,
        "name": str(manifest.get("name", agent.name)),
        "summary": str(manifest.get("description", agent.description)),
        "category": manifest.get("category", agent.category),
        "tags": manifest.get("tags", agent.tags),
        "version": version.version,
        "publisher": publisher.name,
        "verification": agent.verification,
        "visibility": agent.visibility,
        "riskLevel": version.risk_level,
        "riskScore": version.risk_score,
        "tools": manifest.get("tools", []),
        "publishedAt": ensure_utc(version.published_at) if version.published_at else None,
        "installed": installation is not None,
        "installationId": installation.id if installation else None,
        "own": agent.organization_id == organization_id,
    }


def to_listing(
    version: AgentVersion,
    agent: Agent,
    publisher: Organization,
    installation: Installation | None,
    organization_id: str,
) -> MarketplaceListing:
    return MarketplaceListing.model_validate(
        _listing_payload(version, agent, publisher, installation, organization_id)
    )


def to_listing_detail(
    version: AgentVersion,
    agent: Agent,
    publisher: Organization,
    installation: Installation | None,
    organization_id: str,
) -> MarketplaceListingDetail:
    payload = _listing_payload(version, agent, publisher, installation, organization_id)
    payload["manifest"] = version.manifest
    payload["changelog"] = version.changelog
    return MarketplaceListingDetail.model_validate(payload)


def _installation_payload(
    installation: Installation, version: AgentVersion | None, update_available: bool
) -> dict[str, object]:
    manifest = version.manifest if version else {}
    return {
        "id": installation.id,
        "agentId": installation.agent_id,
        "agentVersionId": installation.agent_version_id,
        "agentName": installation.agent_name,
        "publisher": installation.publisher_name,
        "version": str(manifest.get("version", "")) if version else "",
        "status": installation.status,
        "grants": installation.grants,
        "riskLevel": installation.risk_level,
        "riskScore": installation.risk_score,
        "note": installation.note,
        "installedBy": installation.installed_by_name,
        "createdAt": ensure_utc(installation.created_at),
        "updatedAt": ensure_utc(installation.updated_at),
        "unusableTools": registry_service.unusable_tools(manifest, installation.grants)
        if version
        else [],
        "updateAvailable": update_available,
    }


def to_installation_read(
    installation: Installation, version: AgentVersion | None, *, update_available: bool = False
) -> InstallationRead:
    return InstallationRead.model_validate(
        _installation_payload(installation, version, update_available)
    )


def to_installation_detail(
    installation: Installation, version: AgentVersion, *, update_available: bool = False
) -> InstallationDetail:
    payload = _installation_payload(installation, version, update_available)
    payload["manifest"] = version.manifest
    return InstallationDetail.model_validate(payload)
