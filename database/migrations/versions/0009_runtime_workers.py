"""Add runtime_workers

Workers report what they can do (container runtime, providers, live tiers) so
an API process that holds neither can still say so truthfully. Nothing to
backfill: a running worker reports within one alert interval.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "runtime_workers",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sandbox_available", sa.Boolean(), nullable=False),
        sa.Column("providers", JSON_DOCUMENT, nullable=False),
        sa.Column("live_tiers", JSON_DOCUMENT, nullable=False),
    )
    op.create_index("ix_runtime_workers_seen_at", "runtime_workers", ["seen_at"])


def downgrade() -> None:
    op.drop_index("ix_runtime_workers_seen_at", table_name="runtime_workers")
    op.drop_table("runtime_workers")
