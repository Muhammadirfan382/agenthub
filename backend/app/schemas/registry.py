"""Manifests, published versions, marketplace listings and installations.

A manifest says what an agent *needs*. An installation says what an
organization *granted*. Keeping the two apart is the point of the registry:
installing something never silently accepts everything it asked for.
"""

from datetime import datetime
from typing import Annotated

from pydantic import Field

from app.schemas.agent import AgentPermission, ModelConfig, ResourceLimits, SecurityPolicy
from app.schemas.common import CamelModel
from app.schemas.enums import (
    AgentCategory,
    CapabilityKey,
    InstallationStatus,
    PermissionLevel,
    RiskLevel,
    VerificationStatus,
    VersionStatus,
    Visibility,
)

MAX_CHANGELOG_ENTRIES = 20


class AgentManifest(CamelModel):
    """The frozen description of one published version."""

    name: str
    description: str
    category: AgentCategory
    tags: list[str]
    version: str
    model: ModelConfig
    tools: list[str]
    # Requests, not grants: an installing organization decides what to allow.
    required_permissions: list[AgentPermission]
    resource_limits: ResourceLimits
    security_policy: SecurityPolicy


class PublishRequest(CamelModel):
    changelog: Annotated[
        list[Annotated[str, Field(min_length=3, max_length=200)]],
        Field(default_factory=list, max_length=MAX_CHANGELOG_ENTRIES),
    ]
    visibility: Visibility | None = None


class VersionStatusUpdate(CamelModel):
    status: VersionStatus


class VisibilityUpdate(CamelModel):
    visibility: Visibility


class AgentVersionRead(CamelModel):
    id: str
    agent_id: str
    version: str
    status: VersionStatus
    risk_level: RiskLevel
    risk_score: int
    changelog: list[str]
    manifest: AgentManifest
    created_at: datetime
    published_at: datetime | None
    deprecated_at: datetime | None
    created_by: str


class MarketplaceListing(CamelModel):
    """A published version as seen from the marketplace."""

    id: str
    agent_id: str
    name: str
    summary: str
    category: AgentCategory
    tags: list[str]
    version: str
    publisher: str
    verification: VerificationStatus
    visibility: Visibility
    risk_level: RiskLevel
    risk_score: int
    tools: list[str]
    published_at: datetime
    # Whether the caller's organization already installed this agent.
    installed: bool
    installation_id: str | None
    # True when the listing comes from the caller's own organization.
    own: bool


class MarketplaceListingDetail(MarketplaceListing):
    manifest: AgentManifest
    changelog: list[str]


class PermissionGrant(CamelModel):
    """One capability an organization allows an installed agent to use."""

    capability: CapabilityKey
    level: PermissionLevel
    requires_approval: bool = False
    scope: str = Field(default="", max_length=120)
    # Derived server-side; anything sent here is replaced.
    risk: RiskLevel = "low"


class InstallationCreate(CamelModel):
    agent_version_id: str = Field(max_length=64)
    # Capabilities left out are denied. Nothing is granted implicitly.
    grants: Annotated[list[PermissionGrant], Field(default_factory=list, max_length=20)]
    note: Annotated[str | None, Field(default=None, max_length=500)] = None


class InstallationUpdate(CamelModel):
    grants: Annotated[list[PermissionGrant] | None, Field(default=None, max_length=20)] = None
    status: InstallationStatus | None = None
    note: Annotated[str | None, Field(default=None, max_length=500)] = None


class InstallationRead(CamelModel):
    id: str
    agent_id: str
    agent_version_id: str
    agent_name: str
    publisher: str
    version: str
    status: InstallationStatus
    grants: list[PermissionGrant]
    risk_level: RiskLevel
    risk_score: int
    note: str | None
    installed_by: str
    created_at: datetime
    updated_at: datetime
    # Manifest tools whose capability was not granted: they cannot work.
    unusable_tools: list[str]
    # True when a newer published version exists for this agent.
    update_available: bool


class InstallationDetail(InstallationRead):
    manifest: AgentManifest
