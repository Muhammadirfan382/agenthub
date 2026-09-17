"""Turning an agent's configuration into a sequence of steps.

The plan is derived from what the agent declared: which model it uses and which
tools it wants. Nothing here decides *what* an agent would do — that needs a
model (Phase 7). It decides what the orchestrator must walk through: prepare,
think, request each tool (pausing where a human must approve), and finish.
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


def _permission_map(permissions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(entry.get("capability")): entry for entry in permissions}


def build_plan(*, tools: list[str], permissions: list[dict[str, Any]], model: str) -> list[Step]:
    """The steps this run will walk through, in order.

    Every declared tool becomes a step even when its capability is denied: the
    run then records the refusal, which is more useful than quietly skipping it.
    """
    granted = _permission_map(permissions)
    steps: list[Step] = [
        Step(kind="prepare", label="Prepare the execution environment"),
        Step(kind="model", label=f"Plan the work with {model}"),
    ]

    for tool in tools:
        capability = TOOL_CAPABILITIES.get(tool)
        if capability is None:
            # A tool that is no longer in the catalog: record it and refuse.
            steps.append(
                Step(kind="tool", label=f"Use {tool}", tool=tool, capability=None, level="denied")
            )
            continue

        permission = granted.get(capability, {})
        level: PermissionLevel = str(permission.get("level", "denied"))  # type: ignore[assignment]
        risk = permission_risk(capability, level) if level != "denied" else "low"
        steps.append(
            Step(
                kind="tool",
                label=f"Use {tool}",
                tool=tool,
                capability=capability,
                level=level,
                scope=str(permission.get("scope", "")),
                requires_approval=bool(permission.get("requiresApproval", False)),
                risk=risk,
            )
        )

    steps.append(Step(kind="finish", label="Summarise the outcome"))
    return steps
