"""ORM rows to API models.

Nested value objects are stored as JSON documents with camelCase keys, which is
what the schemas expect, so they validate directly.
"""

from typing import TYPE_CHECKING

from app.core.time import ensure_utc
from app.db.models import Agent, Execution, Membership, Organization, User
from app.schemas.agent import AgentRead
from app.schemas.auth import (
    MemberRead,
    OrganizationMembershipRead,
    OrganizationRead,
    SessionRead,
    UserRead,
)
from app.schemas.execution import ExecutionDetailRead, ExecutionRead

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
            "versions": agent.versions,
            "securityChecks": agent.security_checks,
        }
    )


def _execution_payload(execution: Execution) -> dict[str, object]:
    return {
        "id": execution.id,
        "agentId": execution.agent_id,
        "agentName": execution.agent_name,
        "status": execution.status,
        "trigger": execution.trigger,
        "startedAt": ensure_utc(execution.started_at),
        "endedAt": ensure_utc(execution.ended_at) if execution.ended_at else None,
        "durationMs": execution.duration_ms,
        "model": execution.model,
        "tokenUsage": {"input": execution.token_input, "output": execution.token_output},
        "toolCallCount": execution.tool_call_count,
        "resultSummary": execution.result_summary,
    }


def to_execution_read(execution: Execution) -> ExecutionRead:
    return ExecutionRead.model_validate(_execution_payload(execution))


def to_execution_detail(execution: Execution) -> ExecutionDetailRead:
    # Trace fields stay empty until the agent runtime records them.
    return ExecutionDetailRead.model_validate(_execution_payload(execution))


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
