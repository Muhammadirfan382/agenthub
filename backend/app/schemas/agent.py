"""Agent request and response models.

The validation here is the authoritative copy: the frontend performs the same
checks for fast feedback, but the server never trusts them.
"""

import re
from datetime import datetime
from typing import Annotated, Any, Self

from pydantic import Field, field_validator, model_validator

from app.schemas.common import CamelModel
from app.schemas.enums import (
    CAPABILITY_KEYS,
    RISK_RANK,
    AgentCategory,
    AgentStatus,
    CapabilityKey,
    NetworkEgress,
    PermissionLevel,
    RiskLevel,
    SandboxMode,
    SecurityCheckStatus,
    VerificationStatus,
    Visibility,
)
from app.services.catalog import MODEL_IDS, MODEL_PROVIDER, TOOL_CAPABILITIES, TOOL_IDS
from app.services.risk import permission_risk

NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]*$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,23}$")
HOSTNAME_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.IGNORECASE
)
MAX_ALLOWED_DOMAINS = 20


class Person(CamelModel):
    id: str = Field(max_length=64)
    name: str = Field(max_length=120)


class ModelConfig(CamelModel):
    provider: str = Field(default=MODEL_PROVIDER, max_length=64)
    model: str
    temperature: float = Field(ge=0, le=2)
    max_output_tokens: int = Field(ge=256, le=32_000)

    @field_validator("model")
    @classmethod
    def _known_model(cls, value: str) -> str:
        if value not in MODEL_IDS:
            raise ValueError("Unknown model. Choose one of: " + ", ".join(MODEL_IDS) + ".")
        return value


class ResourceLimits(CamelModel):
    max_runtime_seconds: int = Field(ge=10, le=3600)
    max_memory_mb: int = Field(ge=128, le=8192)
    max_tokens_per_run: int = Field(ge=1000, le=200_000)
    max_tool_calls: int = Field(ge=0, le=500)


class SecurityPolicy(CamelModel):
    sandbox: SandboxMode
    network_egress: NetworkEgress
    allowed_domains: list[str] = Field(default_factory=list, max_length=MAX_ALLOWED_DOMAINS)
    approval_required_for: list[RiskLevel] = Field(default_factory=list)
    audit_logging: bool

    @field_validator("allowed_domains")
    @classmethod
    def _valid_domains(cls, value: list[str]) -> list[str]:
        for domain in value:
            if not HOSTNAME_PATTERN.match(domain):
                raise ValueError(
                    "Invalid domain: "
                    + domain
                    + ". Use hostnames only, without a scheme, path or wildcard."
                )
        return [domain.lower() for domain in value]


class AgentPermission(CamelModel):
    capability: CapabilityKey
    level: PermissionLevel
    requires_approval: bool = False
    scope: str = Field(default="", max_length=120)
    # Derived server-side from capability and level; any value sent is replaced.
    risk: RiskLevel = "low"


class SecurityCheck(CamelModel):
    id: str
    name: str
    status: SecurityCheckStatus
    detail: str


class AgentDraft(CamelModel):
    """Everything a client may set. Server-derived fields are not accepted."""

    name: Annotated[str, Field(min_length=3, max_length=60)]
    description: Annotated[str, Field(min_length=20, max_length=500)]
    category: AgentCategory
    tags: Annotated[list[str], Field(min_length=1, max_length=10)]
    version: str
    model: ModelConfig
    tools: Annotated[list[str], Field(default_factory=list, max_length=10)]
    permissions: list[AgentPermission]
    resource_limits: ResourceLimits
    security_policy: SecurityPolicy

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        if not NAME_PATTERN.match(value):
            raise ValueError("Use letters, numbers, spaces, dots, dashes or underscores.")
        return value

    @field_validator("version")
    @classmethod
    def _valid_version(cls, value: str) -> str:
        if not SEMVER_PATTERN.match(value):
            raise ValueError("Use semantic versioning, for example 1.0.0.")
        return value

    @field_validator("tags")
    @classmethod
    def _valid_tags(cls, value: list[str]) -> list[str]:
        for tag in value:
            if not TAG_PATTERN.match(tag):
                raise ValueError(
                    "Tags use lowercase letters, numbers and dashes (max 24 characters)."
                )
        if len(set(value)) != len(value):
            raise ValueError("Tags must be unique.")
        return value

    @field_validator("tools")
    @classmethod
    def _known_tools(cls, value: list[str]) -> list[str]:
        for tool in value:
            if tool not in TOOL_IDS:
                raise ValueError("Unknown tool: " + tool + ".")
        if len(set(value)) != len(value):
            raise ValueError("Tools must be unique.")
        return value

    @field_validator("permissions")
    @classmethod
    def _complete_permissions(cls, value: list[AgentPermission]) -> list[AgentPermission]:
        capabilities = [permission.capability for permission in value]
        if sorted(capabilities) != sorted(CAPABILITY_KEYS):
            raise ValueError("Provide exactly one entry for every capability.")
        return value

    @model_validator(mode="after")
    def _consistent_configuration(self) -> Self:
        levels: dict[str, PermissionLevel] = {p.capability: p.level for p in self.permissions}

        for tool in self.tools:
            capability = TOOL_CAPABILITIES[tool]
            if levels.get(capability) == "denied":
                raise ValueError(
                    "Tool " + tool + " needs the " + capability + " capability, which is denied."
                )

        for permission in self.permissions:
            if permission.level == "denied":
                continue
            if len(permission.scope) < 3:
                raise ValueError("Describe the scope for " + permission.capability + ".")
            if (
                permission_risk(permission.capability, permission.level) == "critical"
                and not permission.requires_approval
            ):
                raise ValueError("Critical-risk capabilities must require human approval.")

        if (
            levels.get("code_execution", "denied") != "denied"
            and self.security_policy.sandbox != "strict"
        ):
            raise ValueError("Code execution requires the strict sandbox.")

        reaches_network = any(
            levels.get(capability, "denied") != "denied"
            for capability in ("web_access", "api_access")
        )
        if self.security_policy.network_egress == "allow_list":
            if not self.security_policy.allowed_domains:
                raise ValueError("Add at least one allowed domain, or set egress to none.")
        elif reaches_network:
            raise ValueError("Web or API access needs an egress allow-list.")

        grants_high_risk = any(
            permission.level != "denied"
            and RISK_RANK[permission_risk(permission.capability, permission.level)]
            >= RISK_RANK["high"]
            for permission in self.permissions
        )
        if grants_high_risk and not self.security_policy.audit_logging:
            raise ValueError("Audit logging is required when high-risk capabilities are granted.")

        if self.tools and self.resource_limits.max_tool_calls == 0:
            raise ValueError("Allow at least one tool call when tools are selected.")

        if self.resource_limits.max_tokens_per_run < self.model.max_output_tokens:
            raise ValueError("Max tokens per run must be at least the model max output tokens.")

        return self

    def normalised_permissions(self) -> list[dict[str, Any]]:
        """Permissions with server-derived risk and denied entries cleared."""
        result: list[dict[str, Any]] = []
        for permission in self.permissions:
            denied = permission.level == "denied"
            result.append(
                {
                    "capability": permission.capability,
                    "level": permission.level,
                    "requiresApproval": False if denied else permission.requires_approval,
                    "scope": "Not granted" if denied else permission.scope,
                    "risk": permission_risk(permission.capability, permission.level),
                }
            )
        return result


class AgentStatusUpdate(CamelModel):
    status: AgentStatus


class AgentRead(CamelModel):
    id: str
    name: str
    description: str
    category: AgentCategory
    tags: list[str]
    version: str
    status: AgentStatus
    verification: VerificationStatus
    visibility: Visibility
    risk_level: RiskLevel
    risk_score: int
    creator: Person
    owner: Person
    created_at: datetime
    updated_at: datetime
    last_execution_at: datetime | None
    model: ModelConfig
    tools: list[str]
    permissions: list[AgentPermission]
    resource_limits: ResourceLimits
    security_policy: SecurityPolicy
    security_checks: list[SecurityCheck]
