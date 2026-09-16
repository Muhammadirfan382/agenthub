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
VersionStatus = Literal["current", "previous", "deprecated", "draft"]
SecurityCheckStatus = Literal["passed", "warning", "failed", "not_run"]
SandboxMode = Literal["strict", "standard"]
NetworkEgress = Literal["none", "allow_list"]
ExecutionStatus = Literal[
    "QUEUED",
    "STARTING",
    "RUNNING",
    "WAITING_FOR_TOOL",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "TIMEOUT",
]
ExecutionTrigger = Literal["manual", "schedule", "api"]
AgentSort = Literal["updated_desc", "name_asc", "risk_desc", "last_execution_desc"]

# Organization roles, least privileged first.
Role = Literal["viewer", "member", "admin", "owner"]
UserStatus = Literal["active", "disabled"]

RISK_LEVELS: tuple[RiskLevel, ...] = get_args(RiskLevel)
CAPABILITY_KEYS: tuple[CapabilityKey, ...] = get_args(CapabilityKey)
EXECUTION_STATUSES: tuple[ExecutionStatus, ...] = get_args(ExecutionStatus)

RISK_RANK: dict[str, int] = {level: index for index, level in enumerate(RISK_LEVELS)}

ROLES: tuple[Role, ...] = get_args(Role)
ROLE_RANK: dict[str, int] = {role: index for index, role in enumerate(ROLES)}
