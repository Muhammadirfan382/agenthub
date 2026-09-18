"""The execution engine: one run, one step at a time.

What is real here: the state machine, the budget, the approval pauses, the
cancellation checks, the kill switch, the sandbox the run is given, and the
record of everything that happened.

What is still *not* real is the work itself. A run now starts a genuinely
isolated container (Phase 6) and refuses to continue if that container does not
hold — but nothing is executed inside it, because no agent program exists until
the model gateway arrives (Phase 7). Tool calls are therefore recorded as
`simulated` rather than `succeeded`, and `runtime` says which of the two
happened: `sandbox` when a verified container was created for the run,
`simulation` when none was available.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.time import ensure_utc, now_utc
from app.db.models import (
    Agent,
    Execution,
    ExecutionApproval,
    ExecutionEvent,
    ExecutionLog,
    ExecutionToolCall,
    Organization,
)
from app.runtime.plan import Step, build_plan
from app.runtime.sandbox import get_sandbox
from app.sandbox import build_spec
from app.schemas.enums import ExecutionStatus, LogLevel, TimelineKind

logger = logging.getLogger(__name__)

RUNTIME_NAME = "simulation"
SIMULATION_NOTE = "Simulated: no agent code, model or tool was actually run."

# Token figures a simulated step reports. They are invented, and labelled as
# such wherever they are shown; they exist so budget enforcement has something
# to count.
SIMULATED_PROMPT_TOKENS = 850
SIMULATED_OUTPUT_TOKENS = 240
SIMULATED_TOOL_TOKENS = 120
SIMULATED_STEP_MS = 60


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


async def plan_for(session: AsyncSession, execution: Execution) -> list[Step]:
    """The agent's current declaration, used as the shape of the run."""
    agent = await session.get(Agent, execution.agent_id)
    if agent is None:
        return [Step(kind="finish", label="Summarise the outcome")]
    return build_plan(tools=list(agent.tools), permissions=agent.permissions, model=execution.model)


def _finish(execution: Execution, status: ExecutionStatus, *, summary: str | None = None) -> None:
    now = now_utc()
    execution.status = status
    execution.ended_at = now
    execution.duration_ms = int((now - ensure_utc(execution.started_at)).total_seconds() * 1000)
    execution.claimed_by = None
    execution.heartbeat_at = None
    if summary is not None:
        execution.result_summary = summary


async def _fail(
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
    _finish(execution, status)
    return StepOutcome(status=status, finished=True)


async def _budget_exceeded(recorder: ExecutionRecorder, execution: Execution) -> StepOutcome | None:
    """Stops the run when it has used more than it was allowed."""
    elapsed = (now_utc() - ensure_utc(execution.started_at)).total_seconds()
    if elapsed > execution.max_runtime_seconds:
        return await _fail(
            recorder,
            execution,
            status="TIMEOUT",
            code="runtime_limit",
            message=(
                f"Stopped at the {execution.max_runtime_seconds}s runtime limit "
                f"after {int(elapsed)}s."
            ),
        )

    used = execution.token_input + execution.token_output
    if used > execution.max_tokens:
        return await _fail(
            recorder,
            execution,
            status="FAILED",
            code="token_budget",
            message=f"Stopped at the {execution.max_tokens} token budget ({used} used).",
        )
    return None


async def _cancelled(recorder: ExecutionRecorder, execution: Execution) -> StepOutcome | None:
    if execution.cancel_requested_at is None:
        return None
    who = execution.cancel_requested_by or "someone"
    await recorder.event("lifecycle", "Cancelled", detail=f"Cancelled by {who}.")
    await recorder.log("warn", f"Execution cancelled by {who}.")
    execution.error_code = "cancelled"
    execution.error_message = f"Cancelled by {who}."
    _finish(execution, "CANCELLED")
    return StepOutcome(status="CANCELLED", finished=True)


async def _organization_paused(session: AsyncSession, execution: Execution) -> Organization | None:
    organization = await session.get(Organization, execution.organization_id)
    if organization is not None and organization.executions_paused:
        return organization
    return None


async def _decided_approval(
    session: AsyncSession, execution: Execution, step_index: int
) -> ExecutionApproval | None:
    approval: ExecutionApproval | None = await session.scalar(
        select(ExecutionApproval).where(
            ExecutionApproval.execution_id == execution.id,
            ExecutionApproval.step_index == step_index,
        )
    )
    return approval


async def _run_tool_step(
    session: AsyncSession,
    recorder: ExecutionRecorder,
    execution: Execution,
    step: Step,
) -> StepOutcome:
    tool = step.tool or "unknown tool"

    if step.capability is None or step.level == "denied":
        reason = (
            f"{tool} needs the {step.capability} capability, which is not granted."
            if step.capability
            else f"{tool} is not in the tool catalogue."
        )
        await recorder.event("policy", f"Refused {tool}", detail=reason)
        await recorder.log("warn", reason)
        await recorder.tool_call(
            tool=tool,
            capability=step.capability or "unknown",
            status="denied",
            input_summary=f"Requested {tool}",
            output_summary=reason,
            duration_ms=None,
        )
        execution.step_index += 1
        return StepOutcome(status="RUNNING", finished=False)

    if execution.tool_call_count >= execution.max_tool_calls:
        return await _fail(
            recorder,
            execution,
            status="FAILED",
            code="tool_call_budget",
            message=f"Stopped at the {execution.max_tool_calls} tool call limit.",
        )

    if step.requires_approval:
        decided = await _decided_approval(session, execution, execution.step_index)
        if decided is None:
            session.add(
                ExecutionApproval(
                    id=new_id("apr"),
                    execution_id=execution.id,
                    organization_id=execution.organization_id,
                    step_index=execution.step_index,
                    capability=step.capability,
                    tool=tool,
                    reason=(
                        f"{tool} uses {step.capability} ({step.level}), which this agent "
                        "requires a person to approve."
                    ),
                    risk_level=step.risk,
                    status="pending",
                    requested_at=now_utc(),
                )
            )
            await recorder.event(
                "policy",
                f"Waiting for approval to use {tool}",
                detail=f"{step.capability} at {step.level}. Scope: {step.scope or 'unspecified'}.",
            )
            await recorder.log("info", f"Paused: {tool} needs human approval.")
            execution.status = "WAITING_FOR_APPROVAL"
            execution.claimed_by = None
            return StepOutcome(status="WAITING_FOR_APPROVAL", finished=False, paused=True)

        if decided.status == "pending":
            execution.status = "WAITING_FOR_APPROVAL"
            execution.claimed_by = None
            return StepOutcome(status="WAITING_FOR_APPROVAL", finished=False, paused=True)

        if decided.status == "denied":
            who = decided.decided_by_name or "an approver"
            reason = f"{who} did not approve {tool}."
            await recorder.event("policy", f"Refused {tool}", detail=reason)
            await recorder.tool_call(
                tool=tool,
                capability=step.capability,
                status="denied",
                input_summary=f"Requested {tool}",
                output_summary=reason,
                duration_ms=None,
            )
            await recorder.log("warn", reason)
            execution.step_index += 1
            return StepOutcome(status="RUNNING", finished=False)

        await recorder.event(
            "policy",
            f"Approved use of {tool}",
            detail=f"Approved by {decided.decided_by_name or 'an approver'}.",
        )

    # Approved (or no approval needed): record the call as simulated. Nothing
    # is executed; the sandbox that would run it does not exist yet.
    await recorder.event("tool", f"{tool} (simulated)", detail=SIMULATION_NOTE)
    await recorder.tool_call(
        tool=tool,
        capability=step.capability,
        status="simulated",
        input_summary=f"{tool} within scope: {step.scope or 'unspecified'}",
        output_summary=SIMULATION_NOTE,
        duration_ms=SIMULATED_STEP_MS,
    )
    await recorder.log("info", f"{tool} recorded as simulated; no tool was invoked.")
    execution.tool_call_count += 1
    execution.token_output += SIMULATED_TOOL_TOKENS
    execution.step_index += 1
    return StepOutcome(status="RUNNING", finished=False)


async def prepare_sandbox(
    session: AsyncSession, execution: Execution, recorder: ExecutionRecorder, settings: Settings
) -> StepOutcome | None:
    """Creates and checks the box this run would execute in.

    Three outcomes, all recorded rather than assumed:

    * The container starts and every isolation check passes. The run continues
      with `runtime = "sandbox"`.
    * The container starts and something is wrong. The run **fails**: a box
      that does not hold is worse than no box, because it looks like one.
    * No container runtime is available. With `REQUIRE_SANDBOX` on the run
      fails; otherwise it continues as a recorded simulation, and says so.
    """
    sandbox = get_sandbox(settings)
    spec = build_spec(
        image=settings.sandbox_image,
        execution_id=execution.id,
        organization_id=execution.organization_id,
        memory_mb=settings.sandbox_memory_mb,
        cpus=settings.sandbox_cpus,
        pids_limit=settings.sandbox_pids_limit,
        tmpfs_mb=settings.sandbox_tmpfs_mb,
        timeout_seconds=settings.sandbox_timeout_seconds,
    )

    result = await sandbox.probe(spec)
    execution.sandbox_report = result.report.as_dict()

    if result.isolated:
        execution.runtime = "sandbox"
        await recorder.event(
            "lifecycle",
            "Sandbox verified",
            detail=(
                f"{settings.sandbox_image}: {result.report.summary()}. "
                "Nothing ran inside it: no agent program exists yet."
            ),
        )
        await recorder.log("info", f"Sandbox ready: {result.report.summary()}.")
        return None

    if result.started:
        # A container existed and failed its own checks. Do not continue.
        failures = ", ".join(check.label for check in result.report.failures)
        await recorder.event("policy", "Sandbox rejected", detail=failures)
        return await _fail(
            recorder,
            execution,
            status="FAILED",
            code="sandbox_unsafe",
            message=f"The sandbox did not hold: {failures}.",
        )

    reason = result.error or "No container runtime is available."
    if settings.require_sandbox:
        await recorder.event("policy", "Refused to run without a sandbox", detail=reason)
        return await _fail(
            recorder,
            execution,
            status="FAILED",
            code="sandbox_unavailable",
            message=f"REQUIRE_SANDBOX is on and no sandbox could be created: {reason}",
        )

    execution.runtime = RUNTIME_NAME
    await recorder.event(
        "lifecycle",
        "No sandbox available",
        detail=(f"{reason} This run is recorded by the simulation runtime and executes nothing."),
    )
    await recorder.log("warn", f"Running without a sandbox: {reason}")
    return None


async def advance(
    session: AsyncSession, execution: Execution, *, settings: Settings | None = None
) -> StepOutcome:
    """Runs one step of one execution and records what it did."""
    recorder = ExecutionRecorder(session, execution)
    execution.heartbeat_at = now_utc()

    if execution.status in {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"}:
        return StepOutcome(status=execution.status, finished=True)  # type: ignore[arg-type]

    paused_organization = await _organization_paused(session, execution)
    if paused_organization is not None:
        reason = paused_organization.executions_paused_reason or "No reason given."
        await recorder.event("policy", "Stopped by the organization kill switch", detail=reason)
        await recorder.log("warn", f"Kill switch engaged: {reason}")
        execution.error_code = "kill_switch"
        execution.error_message = f"Stopped by the organization kill switch. {reason}"
        _finish(execution, "CANCELLED")
        return StepOutcome(status="CANCELLED", finished=True)

    cancelled = await _cancelled(recorder, execution)
    if cancelled is not None:
        return cancelled

    over_budget = await _budget_exceeded(recorder, execution)
    if over_budget is not None:
        return over_budget

    plan = await plan_for(session, execution)
    if execution.step_index >= len(plan):
        _finish(execution, "COMPLETED", summary=execution.result_summary)
        return StepOutcome(status="COMPLETED", finished=True)

    step = plan[execution.step_index]

    if step.kind == "prepare":
        execution.status = "STARTING"
        await recorder.event("lifecycle", "Execution started")

        refused = await prepare_sandbox(session, execution, recorder, settings or get_settings())
        if refused is not None:
            return refused

        execution.step_index += 1
        execution.status = "RUNNING"
        return StepOutcome(status="RUNNING", finished=False)

    if step.kind == "model":
        execution.status = "RUNNING"
        await recorder.event("model", f"{step.label} (simulated)", detail=SIMULATION_NOTE)
        await recorder.log("info", "Model call recorded as simulated; no provider was contacted.")
        execution.token_input += SIMULATED_PROMPT_TOKENS
        execution.token_output += SIMULATED_OUTPUT_TOKENS
        execution.step_index += 1
        return StepOutcome(status="RUNNING", finished=False)

    if step.is_tool:
        execution.status = "RUNNING"
        return await _run_tool_step(session, recorder, execution, step)

    summary = (
        f"Simulated run finished: {execution.tool_call_count} tool "
        f"{'call' if execution.tool_call_count == 1 else 'calls'} recorded, none executed."
    )
    await recorder.event("result", "Execution finished", detail=summary)
    await recorder.log("info", summary)
    execution.step_index += 1
    _finish(execution, "COMPLETED", summary=summary)
    return StepOutcome(status="COMPLETED", finished=True)


async def run_to_completion(
    session: AsyncSession,
    execution: Execution,
    *,
    max_steps: int = 100,
    settings: Settings | None = None,
) -> StepOutcome:
    """Advances until the run finishes, pauses for approval, or hits max_steps."""
    outcome = StepOutcome(status=execution.status, finished=False)  # type: ignore[arg-type]
    for _ in range(max_steps):
        outcome = await advance(session, execution, settings=settings)
        await session.flush()
        if outcome.finished or outcome.paused:
            return outcome
    logger.warning("execution %s did not finish within %s steps", execution.id, max_steps)
    return outcome


def stale_before(seconds: int) -> datetime:
    """Heartbeat cut-off: older than this and the worker is assumed gone."""
    return now_utc() - timedelta(seconds=seconds)
