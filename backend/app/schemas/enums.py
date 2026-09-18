"""Domain vocabularies shared by the API and the frontend.

These literal types mirror frontend/src/types/domain.ts exactly.
"""

from typing import Literal, get_args

RiskLevel = Literal["low", "medium", "high", "critical"]
AgentStatus = Literal["active", "paused", "draft", "disabled"]
VerificationStatus = Literal["verified", "pending", "unverified", "rejected"]
AgentCategory = Literal[
    "research", "security", "engineering", "data", "operations", "support", "marketing"
]
CapabilityKey = Literal[
    "web_access",
    "api_access",
    "file_access",
    "database_access",
    "tool_calling",
    "code_execution",
    "email_send",
]
PermissionLevel = Literal["denied", "read_only", "restricted", "allowed"]
# A published version is immutable; deprecated hides it from the marketplace.
VersionStatus = Literal["draft", "published", "deprecated"]
# How widely an agent is listed. Private is the default.
Visibility = Literal["private", "organization", "public"]
InstallationStatus = Literal["active", "suspended"]
SecurityCheckStatus = Literal["passed", "warning", "failed", "not_run"]
SandboxMode = Literal["strict", "standard"]
NetworkEgress = Literal["none", "allow_list"]
ExecutionStatus = Literal[
    "QUEUED",
    "STARTING",
    "RUNNING",
    "WAITING_FOR_TOOL",
    "WAITING_FOR_APPROVAL",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "TIMEOUT",
]
# Whether a verified container was created for a run.
#   simulation - no container was involved.
#   sandbox    - an isolated container was created and verified for this run.
# Nothing executes inside it in either case.
ExecutionRuntime = Literal["simulation", "sandbox"]
# Who drove a run.
#   model     - a real model answered through the model gateway.
#   simulated - no provider was configured; the scripted plan was recorded.
ExecutionMode = Literal["model", "simulated"]
TimelineKind = Literal["lifecycle", "model", "tool", "policy", "error", "result"]
LogLevel = Literal["debug", "info", "warn", "error"]
#: Never "succeeded": no tool is executed in this release.
#:   unavailable - allowed by every check, but no implementation exists to run it.
#:   simulated   - recorded by the scripted plan of a simulated run.
#:   denied      - refused by policy or by a person.
#:   failed      - rejected, e.g. arguments that did not match the tool's schema.
ToolCallStatus = Literal["pending", "simulated", "unavailable", "denied", "failed"]
ApprovalStatus = Literal["pending", "approved", "denied"]
ApprovalDecision = Literal["approved", "denied"]
ExecutionTrigger = Literal["manual", "schedule", "api"]
AgentSort = Literal["updated_desc", "name_asc", "risk_desc", "last_execution_desc"]

# Organization roles, least privileged first.
Role = Literal["viewer", "member", "admin", "owner"]
UserStatus = Literal["active", "disabled"]

RISK_LEVELS: tuple[RiskLevel, ...] = get_args(RiskLevel)
CAPABILITY_KEYS: tuple[CapabilityKey, ...] = get_args(CapabilityKey)
EXECUTION_STATUSES: tuple[ExecutionStatus, ...] = get_args(ExecutionStatus)
#: Statuses a run can never leave.
TERMINAL_STATUSES: frozenset[str] = frozenset({"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"})
#: Statuses a worker may pick up and continue.
RUNNABLE_STATUSES: frozenset[str] = frozenset({"QUEUED", "STARTING", "RUNNING", "WAITING_FOR_TOOL"})
PERMISSION_LEVELS: tuple[PermissionLevel, ...] = get_args(PermissionLevel)
LEVEL_RANK: dict[str, int] = {level: index for index, level in enumerate(PERMISSION_LEVELS)}

RISK_RANK: dict[str, int] = {level: index for index, level in enumerate(RISK_LEVELS)}

ROLES: tuple[Role, ...] = get_args(Role)
ROLE_RANK: dict[str, int] = {role: index for index, role in enumerate(ROLES)}
