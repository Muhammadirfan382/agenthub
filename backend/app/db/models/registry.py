"""Published agent versions and the installations that consume them.

A version is an immutable snapshot of what an agent *asks for*: its model,
tools, required permissions, limits and policy. Publishing one freezes that
manifest, so an organization installing it can see exactly what it agreed to,
even after the source agent changes.

An installation is the other half: what the installing organization actually
*granted*. The two are deliberately separate — a request is not a grant.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.agent import JsonDocument


class AgentVersion(Base):
    """One frozen manifest. Rows are never edited except to change status."""

    __tablename__ = "agent_versions"
    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_id_version"),
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="risk_score_range"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The publishing organization, copied here so marketplace queries need no join.
    organization_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    manifest: Mapped[dict[str, Any]] = mapped_column(JsonDocument, nullable=False)
    changelog: Mapped[list[str]] = mapped_column(JsonDocument, nullable=False, default=list)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_name: Mapped[str] = mapped_column(String(120), nullable=False)


class Installation(Base):
    """What one organization granted to one agent version."""

    __tablename__ = "installations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "agent_id", name="uq_installations_organization_id_agent_id"
        ),
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="risk_score_range"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_version_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False
    )
    # Snapshots, so an uninstalled or renamed source still reads sensibly.
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    publisher_name: Mapped[str] = mapped_column(String(120), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # Deny-by-default: every capability appears, most of them denied.
    grants: Mapped[list[dict[str, Any]]] = mapped_column(JsonDocument, nullable=False, default=list)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    installed_by_id: Mapped[str] = mapped_column(String(64), nullable=False)
    installed_by_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
