"""What every kind of step shares: the record it writes and how a run ends.

Used by the scripted engine (`engine.py`) and the model-driven loop
(`agent_loop.py`) alike, so both write the same timeline, logs and tool calls
and end a run the same way.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import ensure_utc, now_utc
from app.db.models import (
    Execution,
    ExecutionApproval,
    ExecutionEvent,
    ExecutionLog,
    ExecutionToolCall,
)
from app.schemas.enums import ExecutionStatus, LogLevel, TimelineKind


@dataclass(frozen=True)
class StepOutcome:
    """What the engine did, so a caller can decide whether to keep going."""

    status: ExecutionStatus
    finished: bool
    paused: bool = False


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ExecutionRecorder:
    """Appends to an execution's timeline, logs and tool calls."""

    def __init__(self, session: AsyncSession, execution: Execution) -> None:
        self.session = session
        self.execution = execution
        self._sequence: int | None = None

    async def _next_sequence(self) -> int:
        if self._sequence is None:
            highest = await self.session.scalar(
                select(func.max(ExecutionEvent.sequence)).where(
                    ExecutionEvent.execution_id == self.execution.id
                )
            )
            self._sequence = int(highest or 0)
        self._sequence += 1
        return self._sequence

    async def event(
        self, kind: TimelineKind, label: str, detail: str | None = None
    ) -> ExecutionEvent:
        event = ExecutionEvent(
            id=new_id("evt"),
            execution_id=self.execution.id,
            organization_id=self.execution.organization_id,
            sequence=await self._next_sequence(),
            at=now_utc(),
            kind=kind,
            label=label,
            detail=detail,
        )
        self.session.add(event)
        return event

    async def log(self, level: LogLevel, message: str) -> None:
        self.session.add(
            ExecutionLog(
                id=new_id("log"),
                execution_id=self.execution.id,
                sequence=await self._next_sequence(),
                at=now_utc(),
                level=level,
                message=message,
            )
        )

    async def tool_call(
        self,
        *,
        tool: str,
        capability: str,
        status: str,
        input_summary: str,
        output_summary: str | None,
        duration_ms: int | None,
    ) -> None:
        self.session.add(
            ExecutionToolCall(
                id=new_id("tcl"),
                execution_id=self.execution.id,
                sequence=await self._next_sequence(),
                tool=tool,
                capability=capability,
                status=status,
                started_at=now_utc(),
                duration_ms=duration_ms,
                input_summary=input_summary,
                output_summary=output_summary,
            )
        )


def finish(execution: Execution, status: ExecutionStatus, *, summary: str | None = None) -> None:
    now = now_utc()
    execution.status = status
    execution.ended_at = now
    execution.duration_ms = int((now - ensure_utc(execution.started_at)).total_seconds() * 1000)
    execution.claimed_by = None
    execution.heartbeat_at = None
    if summary is not None:
        execution.result_summary = summary


async def fail(
    recorder: ExecutionRecorder,
    execution: Execution,
    *,
    status: ExecutionStatus,
    code: str,
    message: str,
) -> StepOutcome:
    execution.error_code = code
    execution.error_message = message
    await recorder.event("error", message, detail=f"Error code: {code}")
    await recorder.log("error", message)
    finish(execution, status)
    return StepOutcome(status=status, finished=True)


async def decided_approval(
    session: AsyncSession, execution: Execution, step_index: int
) -> ExecutionApproval | None:
    approval: ExecutionApproval | None = await session.scalar(
        select(ExecutionApproval).where(
            ExecutionApproval.execution_id == execution.id,
            ExecutionApproval.step_index == step_index,
        )
    )
    return approval
