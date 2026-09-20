"""The audit log table. Append only: nothing in the platform updates or deletes it."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.agent import JsonDocument


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    #: user, agent or system.
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: A snapshot, so the record stays readable after the actor is renamed or removed.
    actor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    #: Dotted and stable, e.g. auth.login, member.role_changed, policy.denied.
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: success, failure, denied or allowed.
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Small, bounded, key-filtered facts. Never secrets or content.
    detail: Mapped[dict[str, Any]] = mapped_column(JsonDocument, nullable=False, default=dict)
