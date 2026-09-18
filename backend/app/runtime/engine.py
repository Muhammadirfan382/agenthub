"""The execution engine: one run, one step at a time.

Every run starts the same way: the kill switch, cancellation and budget are
checked before each step, and the first step gives the run a sandbox (Phase 6)
and decides how it will be driven:

* **model** - the agent's tier routes to a configured provider, so a real model
  answers through the model gateway and asks for tools through the tool
  gateway (`agent_loop.py`);
* **simulated** - no provider is configured, so the scripted plan derived from
  the agent's declaration is recorded instead, and says so at every step.

In neither mode is a tool executed: none has an implementation until the
egress protections of Phase 8 exist. Nothing runs inside the sandbox either.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.time import ensure_utc, now_utc
from app.db.models import (
    Agent,
    Execution,
    ExecutionApproval,
    Organization,
)
from app.llm.gateway import get_gateway
from app.runtime.agent_loop import model_step
from app.runtime.plan import Step, build_plan
from app.runtime.records import ExecutionRecorder, StepOutcome, new_id
from app.runtime.records import decided_approval as _decided_approval
from app.runtime.records import fail as _fail
from app.runtime.records import finish as _finish
from app.runtime.sandbox import get_sandbox
from app.sandbox import build_spec

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


async def plan_for(session: AsyncSession, execution: Execution) -> list[Step]:
    """The agent's current declaration, used as the shape of the run."""
    agent = await session.get(Agent, execution.agent_id)
    if agent is None:
        return [Step(kind="finish", label="Summarise the outcome")]
    return build_plan(tools=list(agent.tools), permissions=agent.permissions, model=execution.model)


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
        detail=(
            f"{reason} Nothing runs in a container for this run, and it executes nothing "
            "on this machine: model calls go through the gateway and tools are not run."
        ),
    )
    await recorder.log("warn", f"Running without a sandbox: {reason}")
    return None


async def choose_mode(
    session: AsyncSession, execution: Execution, recorder: ExecutionRecorder, settings: Settings
) -> None:
    """Decides whether a real model drives this run, and records the decision."""
    gateway = get_gateway(settings)
    route = gateway.route(execution.model)
    if route is not None and gateway.available_for(execution.model):
        execution.mode = "model"
        execution.model_route = str(route)
        await recorder.event(
            "lifecycle",
            f"Model gateway: {route}",
            detail=f"The {execution.model} tier routes to {route}. Tools are checked, not run.",
        )
        return

    execution.mode = "simulated"
    why = (
        f"The {execution.model} tier routes to {route}, whose provider has no credentials."
        if route is not None
        else f"No route is configured for the {execution.model} tier."
    )
    await recorder.event(
        "lifecycle",
        "No model provider configured",
        detail=f"{why} This run is simulated: no model is called.",
    )
    await recorder.log("warn", f"Simulated run: {why}")


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

    if execution.mode == "model" and execution.step_index >= 1:
        agent = await session.get(Agent, execution.agent_id)
        if agent is None:
            return await _fail(
                recorder,
                execution,
                status="FAILED",
                code="agent_missing",
                message="The agent behind this run no longer exists.",
            )
        resolved = settings or get_settings()
        return await model_step(
            session,
            recorder,
            execution,
            agent=agent,
            gateway=get_gateway(resolved),
            settings=resolved,
        )

    plan = await plan_for(session, execution)
    if execution.step_index >= len(plan):
        _finish(execution, "COMPLETED", summary=execution.result_summary)
        return StepOutcome(status="COMPLETED", finished=True)

    step = plan[execution.step_index]

    if step.kind == "prepare":
        execution.status = "STARTING"
        await recorder.event("lifecycle", "Execution started")

        resolved = settings or get_settings()
        refused = await prepare_sandbox(session, execution, recorder, resolved)
        if refused is not None:
            return refused
        await choose_mode(session, execution, recorder, resolved)

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
    """Advances until the run finishes, pauses for approval, or hits max_steps.

    Each step is committed as soon as it is done, so progress is durable and
    visible to the API, the event stream and other workers - a run that loses
    its worker resumes from the last committed step, not from the beginning.
    """
    outcome = StepOutcome(status=execution.status, finished=False)  # type: ignore[arg-type]
    for _ in range(max_steps):
        outcome = await advance(session, execution, settings=settings)
        await session.commit()
        if outcome.finished or outcome.paused:
            return outcome
    logger.warning("execution %s did not finish within %s steps", execution.id, max_steps)
    return outcome


def stale_before(seconds: int) -> datetime:
    """Heartbeat cut-off: older than this and the worker is assumed gone."""
    return now_utc() - timedelta(seconds=seconds)
