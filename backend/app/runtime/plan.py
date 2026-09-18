"""Turning an agent's configuration into a sequence of steps.

The plan is derived from what the agent declared: which model it uses and which
tools it wants. It is the script a *simulated* run walks through - prepare,
think, request each tool (pausing where a human must approve), finish - when no
model provider is configured. A model-driven run decides for itself what to do
(`agent_loop.py`); `tool_step` here judges its tools the same way.
"""

from dataclasses import dataclass
from typing import Any, Literal

from app.schemas.enums import CapabilityKey, PermissionLevel, RiskLevel
from app.services.catalog import TOOL_CAPABILITIES
from app.services.risk import permission_risk

StepKind = Literal["prepare", "model", "tool", "finish"]


@dataclass(frozen=True)
class Step:
    kind: StepKind
    label: str
    #: Only for tool steps.
    tool: str | None = None
    capability: CapabilityKey | None = None
    level: PermissionLevel = "denied"
    scope: str = ""
    requires_approval: bool = False
    risk: RiskLevel = "low"

    @property
    def is_tool(self) -> bool:
        return self.kind == "tool"


def permission_map(permissions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(entry.get("capability")): entry for entry in permissions}


def tool_step(tool: str, granted: dict[str, dict[str, Any]]) -> Step:
    """What this agent may do with one tool: capability, level, scope, approval, risk.

    Shared by the scripted plan and the model tool gateway, so a tool is judged
    the same way whichever of them asks.
    """
    capability = TOOL_CAPABILITIES.get(tool)
    if capability is None:
        # A tool that is no longer in the catalog: record it and refuse.
        return Step(kind="tool", label=f"Use {tool}", tool=tool, capability=None, level="denied")

    permission = granted.get(capability, {})
    level: PermissionLevel = str(permission.get("level", "denied"))  # type: ignore[assignment]
    risk = permission_risk(capability, level) if level != "denied" else "low"
    return Step(
        kind="tool",
        label=f"Use {tool}",
        tool=tool,
        capability=capability,
        level=level,
        scope=str(permission.get("scope", "")),
        requires_approval=bool(permission.get("requiresApproval", False)),
        risk=risk,
    )


def tool_policies(tools: list[str], permissions: list[dict[str, Any]]) -> dict[str, Step]:
    granted = permission_map(permissions)
    return {tool: tool_step(tool, granted) for tool in tools}


def build_plan(*, tools: list[str], permissions: list[dict[str, Any]], model: str) -> list[Step]:
    """The steps this run will walk through, in order.

    Every declared tool becomes a step even when its capability is denied: the
    run then records the refusal, which is more useful than quietly skipping it.
    """
    granted = permission_map(permissions)
    steps: list[Step] = [
        Step(kind="prepare", label="Prepare the execution environment"),
        Step(kind="model", label=f"Plan the work with {model}"),
    ]

    steps.extend(tool_step(tool, granted) for tool in tools)

    steps.append(Step(kind="finish", label="Summarise the outcome"))
    return steps
