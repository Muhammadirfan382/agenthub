"""ORM rows to API models.

Nested value objects are stored as JSON documents with camelCase keys, which is
what the schemas expect, so they validate directly.
"""

from app.core.time import ensure_utc
from app.db.models import Agent, Execution
from app.schemas.agent import AgentRead
from app.schemas.execution import ExecutionDetailRead, ExecutionRead


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
