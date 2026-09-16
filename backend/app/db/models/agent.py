"""Agent table.

Nested value objects (model configuration, permissions, limits, policy,
version history, check results) are stored as JSON documents: they are always
read and written as a whole and are never queried field by field. Columns the
API filters or sorts on are real columns with indexes.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.execution import Execution

# JSONB on PostgreSQL, JSON elsewhere (SQLite in development and tests).
JsonDocument = JSON().with_variant(JSONB(), "postgresql")


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="risk_score_range"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    tags: Mapped[list[str]] = mapped_column(JsonDocument, nullable=False, default=list)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    verification: Mapped[str] = mapped_column(String(16), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)

    creator_id: Mapped[str] = mapped_column(String(64), nullable=False)
    creator_name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(120), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_execution_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    model: Mapped[dict[str, Any]] = mapped_column(JsonDocument, nullable=False)
    tools: Mapped[list[str]] = mapped_column(JsonDocument, nullable=False, default=list)
    permissions: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonDocument, nullable=False, default=list
    )
    resource_limits: Mapped[dict[str, Any]] = mapped_column(JsonDocument, nullable=False)
    security_policy: Mapped[dict[str, Any]] = mapped_column(JsonDocument, nullable=False)
    versions: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonDocument, nullable=False, default=list
    )
    security_checks: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonDocument, nullable=False, default=list
    )

    executions: Mapped[list["Execution"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
