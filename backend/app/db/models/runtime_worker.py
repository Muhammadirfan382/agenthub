"""Runtime workers: what each worker process can do, as it last reported.

In production the API and the worker are separate processes on different
footing: the worker holds the provider keys and talks to the container
runtime, the API holds neither. The API reads this table to say what the
runtime can do instead of judging from its own, deliberately empty,
configuration.

Platform-wide, not organization-scoped: one worker serves every organization.
Only capabilities are recorded, never credentials.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.agent import JsonDocument


class RuntimeWorker(Base):
    __tablename__ = "runtime_workers"

    #: host:pid:random, as the worker names itself. Never returned by the API.
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    #: Whether its container runtime answered at the last report.
    sandbox_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Provider names with credentials configured. Names only.
    providers: Mapped[list[str]] = mapped_column(JsonDocument, nullable=False, default=list)
    #: Tiers a real model would answer right now.
    live_tiers: Mapped[list[str]] = mapped_column(JsonDocument, nullable=False, default=list)
