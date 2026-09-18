"""Execution tables: the run itself and everything it records.

A run carries two independent facts about how it was produced: `runtime`
(`sandbox` when a verified container was created for it, `simulation` when
none was available) and `mode` (`model` when a real model answered through the
gateway, `simulated` when no provider was configured). No tool is ever executed
in this release, so tool calls are recorded as `unavailable`, `denied` or
`simulated`, never as succeeded.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.agent import JsonDocument

if TYPE_CHECKING:
    from app.db.models.agent import Agent


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Snapshot of the agent name when the execution was requested, so history
    # stays readable after a rename.
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)
    #: What produced this run: `sandbox` (verified container) or `simulation`.
    runtime: Mapped[str] = mapped_column(String(16), nullable=False, default="simulation")
    #: `model` when a real model answered through the gateway, `simulated` when
    #: no provider was configured and the scripted plan was recorded instead.
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="simulated")
    #: The provider:model the run's tier resolved to. Null for simulated runs.
    model_route: Mapped[str | None] = mapped_column(String(160), nullable=True)
    #: What the requester asked the agent to do. Untrusted input, sent to the model.
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Estimated model spend in millionths of a US dollar; null when unpriced.
    cost_microusd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: The model conversation, so a paused or reclaimed run resumes where it was.
    conversation: Mapped[dict[str, Any] | None] = mapped_column(JsonDocument, nullable=True)

    requested_by_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    requested_by_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    model: Mapped[str] = mapped_column(String(64), nullable=False)
    token_input: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_output: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- budget, copied from the agent when the run is requested -------------
    # Copied rather than read live, so editing the agent mid-run cannot move
    # the limits the run is being held to.
    max_runtime_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=50_000)
    max_tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=20)

    # --- orchestration -------------------------------------------------------
    #: Index of the next step in the plan, so a resumed run continues instead
    #: of starting over.
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claimed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Updated while a worker is alive, so a crashed worker's run can be reclaimed.
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_requested_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: What the sandbox reported about itself for this run, check by check.
    sandbox_report: Mapped[dict[str, Any] | None] = mapped_column(JsonDocument, nullable=True)

    agent: Mapped["Agent"] = relationship(back_populates="executions")


class ExecutionEvent(Base):
    """One entry in an execution's timeline, in the order it happened."""

    __tablename__ = "execution_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    execution_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    execution_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    level: Mapped[str] = mapped_column(String(8), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)


class ExecutionToolCall(Base):
    """A tool the run wanted to use, and what happened to that request."""

    __tablename__ = "execution_tool_calls"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    execution_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    tool: Mapped[str] = mapped_column(String(48), nullable=False)
    capability: Mapped[str] = mapped_column(String(32), nullable=False)
    #: simulated, denied, failed or pending. Never "succeeded": nothing ran.
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_summary: Mapped[str] = mapped_column(Text, nullable=False)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExecutionApproval(Base):
    """A pause: a person must decide before the run may continue."""

    __tablename__ = "execution_approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    execution_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    capability: Mapped[str] = mapped_column(String(32), nullable=False)
    tool: Mapped[str | None] = mapped_column(String(48), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    #: pending, approved or denied.
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: True when nobody decided: the kill switch or a policy did.
    automatic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
