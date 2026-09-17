"""Execution request and response models.

An execution carries the runtime that produced it. While that is `simulation`,
every trace it contains was recorded by the orchestrator rather than performed
by an agent, and the API says so in the data rather than only in the docs.
"""

from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from app.schemas.common import CamelModel
from app.schemas.enums import (
    ApprovalDecision,
    ApprovalStatus,
    ExecutionRuntime,
    ExecutionStatus,
    ExecutionTrigger,
    LogLevel,
    RiskLevel,
    TimelineKind,
    ToolCallStatus,
)


class TokenUsage(CamelModel):
    input: int = 0
    output: int = 0


class ExecutionBudget(CamelModel):
    """Copied from the agent when the run was requested, not read live."""

    max_runtime_seconds: int
    max_tokens: int
    max_tool_calls: int


class ExecutionRead(CamelModel):
    id: str
    agent_id: str
    agent_name: str
    status: ExecutionStatus
    trigger: ExecutionTrigger
    runtime: ExecutionRuntime
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    model: str
    token_usage: TokenUsage
    tool_call_count: int
    result_summary: str | None
    requested_by: str
    budget: ExecutionBudget
    cancel_requested: bool
    pending_approvals: int


class TimelineEvent(CamelModel):
    id: str
    at: datetime
    kind: TimelineKind
    label: str
    detail: str | None = None


class LogEntry(CamelModel):
    id: str
    at: datetime
    level: LogLevel
    message: str


class ToolCall(CamelModel):
    id: str
    tool: str
    capability: str
    status: ToolCallStatus
    started_at: datetime
    duration_ms: int | None
    input_summary: str
    output_summary: str | None


class ApprovalRead(CamelModel):
    id: str
    execution_id: str
    agent_name: str
    capability: str
    tool: str | None
    reason: str
    risk_level: RiskLevel
    status: ApprovalStatus
    requested_at: datetime
    decided_at: datetime | None
    decided_by: str | None
    note: str | None
    automatic: bool


class ExecutionError(CamelModel):
    code: str
    message: str


class ExecutionDetailRead(ExecutionRead):
    """Execution with everything the runtime recorded for it."""

    timeline: list[TimelineEvent] = Field(default_factory=list)
    logs: list[LogEntry] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    approvals: list[ApprovalRead] = Field(default_factory=list)
    error: ExecutionError | None = None
    result: str | None = None


class ExecutionRequest(CamelModel):
    """Optional body when requesting an execution."""

    trigger: ExecutionTrigger = "manual"


class ApprovalDecisionRequest(CamelModel):
    decision: ApprovalDecision
    note: Annotated[str | None, Field(default=None, max_length=500)] = None


class KillSwitchRead(CamelModel):
    executions_paused: bool
    paused_at: datetime | None
    paused_by: str | None
    reason: str | None
    pending_approvals: int


class KillSwitchUpdate(CamelModel):
    executions_paused: bool
    reason: Annotated[str | None, StringConstraints(max_length=200)] = None
