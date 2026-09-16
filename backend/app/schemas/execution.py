"""Execution request and response models.

Phase 2 stores the request and its metadata only. Timeline, logs, tool calls
and results come from the agent runtime in a later phase; they are returned as
empty collections so the shape is stable for clients.
"""

from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel
from app.schemas.enums import ExecutionStatus, ExecutionTrigger


class TokenUsage(CamelModel):
    input: int = 0
    output: int = 0


class ExecutionRead(CamelModel):
    id: str
    agent_id: str
    agent_name: str
    status: ExecutionStatus
    trigger: ExecutionTrigger
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    model: str
    token_usage: TokenUsage
    tool_call_count: int
    result_summary: str | None


class TimelineEvent(CamelModel):
    id: str
    at: datetime
    kind: str
    label: str
    detail: str | None = None


class LogEntry(CamelModel):
    id: str
    at: datetime
    level: str
    message: str


class ToolCall(CamelModel):
    id: str
    tool: str
    status: str
    started_at: datetime
    duration_ms: int | None
    input_summary: str
    output_summary: str | None


class ExecutionError(CamelModel):
    code: str
    message: str


class ExecutionDetailRead(ExecutionRead):
    """Execution with its (not yet recorded) trace."""

    timeline: list[TimelineEvent] = Field(default_factory=list)
    logs: list[LogEntry] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    error: ExecutionError | None = None
    result: str | None = None


class ExecutionRequest(CamelModel):
    """Optional body when requesting an execution."""

    trigger: ExecutionTrigger = "manual"
