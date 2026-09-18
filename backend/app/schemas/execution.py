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
    ExecutionMode,
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
    mode: ExecutionMode
    #: provider:model the run's tier resolved to; null for simulated runs.
    model_route: str | None = None
    #: Estimated model spend in US dollars; null when nothing priced was called.
    estimated_cost_usd: float | None = None
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


class SandboxCheck(CamelModel):
    id: str
    label: str
    passed: bool
    detail: str


class SandboxReport(CamelModel):
    """What the container reported about its own isolation."""

    passed: bool
    summary: str
    checks: list[SandboxCheck]


class SandboxStatus(CamelModel):
    """Whether runs can be isolated here, and how."""

    enabled: bool
    available: bool
    #: The CLI the backend would use: docker, podman, anything compatible.
    command: str
    image: str
    memory_mb: int
    cpus: float
    pids_limit: int
    tmpfs_mb: int
    timeout_seconds: int
    #: When true, a run refuses to start unless it gets a verified sandbox.
    required: bool
    detail: str


class SandboxCheckResult(SandboxStatus):
    """A status plus the result of actually starting a container."""

    report: SandboxReport | None = None


class ExecutionError(CamelModel):
    code: str
    message: str


class ConversationToolCall(CamelModel):
    id: str
    name: str
    #: What the model asked for, as bounded JSON text. Untrusted, never run.
    arguments: str


class ConversationToolResult(CamelModel):
    call_id: str
    content: str
    is_error: bool


class ConversationTurn(CamelModel):
    """One message in a model-driven run. Model text is data: render it as text."""

    role: str
    text: str
    tool_calls: list[ConversationToolCall] = Field(default_factory=list)
    tool_results: list[ConversationToolResult] = Field(default_factory=list)


class ExecutionDetailRead(ExecutionRead):
    """Execution with everything the runtime recorded for it."""

    #: What the requester asked the agent to do.
    input: str | None = None
    conversation: list[ConversationTurn] = Field(default_factory=list)

    timeline: list[TimelineEvent] = Field(default_factory=list)
    logs: list[LogEntry] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    approvals: list[ApprovalRead] = Field(default_factory=list)
    #: Present when a container was created for this run and checked.
    sandbox_report: SandboxReport | None = None
    error: ExecutionError | None = None
    result: str | None = None


class ExecutionRequest(CamelModel):
    """Optional body when requesting an execution."""

    trigger: ExecutionTrigger = "manual"
    #: What the agent should do this time. Untrusted input, passed to the model
    #: as the user's message - never as instructions to the platform.
    input: Annotated[str, StringConstraints(strip_whitespace=True, max_length=8000)] | None = None


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
