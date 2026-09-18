"""The model usage ledger: one row per model request, answered or not.

It is what per-organization budgets are enforced against and what usage is
reported from. It records counts and costs, never prompts or answers.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelUsage(Base):
    __tablename__ = "model_usage"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Kept when an execution is deleted: spend is spend.
    execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    #: The model asked for, and the one that answered (they differ after a fallback).
    requested_model: Mapped[str] = mapped_column(String(128), nullable=False)
    served_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    #: ok, refused, or the error kind (rate_limited, unavailable, ...).
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Estimated cost in millionths of a US dollar. Null when the model is not priced.
    cost_microusd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: The provider's request id, for support. Not a secret.
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
