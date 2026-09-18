"""Add the model gateway: how each run was answered, and a usage ledger

Existing executions were never answered by a model, so they are marked
`simulated`, with no route, cost or conversation: nothing is invented about
calls that were never made.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("executions") as batch:
        batch.add_column(
            sa.Column("mode", sa.String(length=16), nullable=False, server_default="simulated")
        )
        batch.add_column(sa.Column("model_route", sa.String(length=160), nullable=True))
        batch.add_column(sa.Column("input_text", sa.Text(), nullable=True))
        batch.add_column(sa.Column("cost_microusd", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("conversation", JSON_DOCUMENT, nullable=True))

    op.create_table(
        "model_usage",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=64),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("execution_id", sa.String(length=64), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("requested_model", sa.String(length=128), nullable=False),
        sa.Column("served_model", sa.String(length=128), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_microusd", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_id", sa.String(length=128), nullable=True),
    )
    op.create_index("ix_model_usage_organization_id", "model_usage", ["organization_id"])
    op.create_index("ix_model_usage_execution_id", "model_usage", ["execution_id"])
    op.create_index("ix_model_usage_at", "model_usage", ["at"])


def downgrade() -> None:
    op.drop_index("ix_model_usage_at", table_name="model_usage")
    op.drop_index("ix_model_usage_execution_id", table_name="model_usage")
    op.drop_index("ix_model_usage_organization_id", table_name="model_usage")
    op.drop_table("model_usage")
    with op.batch_alter_table("executions") as batch:
        batch.drop_column("conversation")
        batch.drop_column("cost_microusd")
        batch.drop_column("input_text")
        batch.drop_column("model_route")
        batch.drop_column("mode")
