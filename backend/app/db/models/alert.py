"""Alerts: something the platform noticed and a person should look at.

One row per firing of a rule in an organization. A rule that keeps matching
updates the same row (`last_seen`, `occurrences`) instead of making noise; when
it stops matching the row is resolved and a later firing starts a new one, so
the history of "when was this wrong" survives.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.agent import JsonDocument


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: The rule that fired, e.g. runs_failing, stalled_runs, sandbox_unverified.
    rule: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    #: info, warning or critical.
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    #: firing or resolved.
    state: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    #: One sentence a person can act on.
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    #: The numbers behind it. Counts and ids only - never content.
    detail: Mapped[dict[str, Any]] = mapped_column(JsonDocument, nullable=False, default=dict)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: Whether the operator webhook was told about this firing.
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
