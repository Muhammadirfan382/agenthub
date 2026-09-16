"""Create agents and executions tables

Revision ID: 0001
Revises:
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# JSONB on PostgreSQL, JSON elsewhere, matching the ORM models.
JSON_DOCUMENT = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("tags", JSON_DOCUMENT, nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("verification", sa.String(length=16), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.String(length=64), nullable=False),
        sa.Column("creator_name", sa.String(length=120), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("owner_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_execution_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model", JSON_DOCUMENT, nullable=False),
        sa.Column("tools", JSON_DOCUMENT, nullable=False),
        sa.Column("permissions", JSON_DOCUMENT, nullable=False),
        sa.Column("resource_limits", JSON_DOCUMENT, nullable=False),
        sa.Column("security_policy", JSON_DOCUMENT, nullable=False),
        sa.Column("versions", JSON_DOCUMENT, nullable=False),
        sa.Column("security_checks", JSON_DOCUMENT, nullable=False),
        sa.CheckConstraint("risk_score >= 0 AND risk_score <= 100", name=op.f("ck_agents_risk_score_range")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agents")),
        sa.UniqueConstraint("name", name=op.f("uq_agents_name")),
    )
    op.create_index(op.f("ix_agents_category"), "agents", ["category"], unique=False)
    op.create_index(op.f("ix_agents_risk_level"), "agents", ["risk_level"], unique=False)
    op.create_index(op.f("ix_agents_status"), "agents", ["status"], unique=False)
    op.create_index(op.f("ix_agents_updated_at"), "agents", ["updated_at"], unique=False)

    op.create_table(
        "executions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("agent_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("token_input", sa.Integer(), nullable=False),
        sa.Column("token_output", sa.Integer(), nullable=False),
        sa.Column("tool_call_count", sa.Integer(), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_executions_agent_id_agents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_executions")),
    )
    op.create_index(op.f("ix_executions_agent_id"), "executions", ["agent_id"], unique=False)
    op.create_index(op.f("ix_executions_started_at"), "executions", ["started_at"], unique=False)
    op.create_index(op.f("ix_executions_status"), "executions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_executions_status"), table_name="executions")
    op.drop_index(op.f("ix_executions_started_at"), table_name="executions")
    op.drop_index(op.f("ix_executions_agent_id"), table_name="executions")
    op.drop_table("executions")
    op.drop_index(op.f("ix_agents_updated_at"), table_name="agents")
    op.drop_index(op.f("ix_agents_status"), table_name="agents")
    op.drop_index(op.f("ix_agents_risk_level"), table_name="agents")
    op.drop_index(op.f("ix_agents_category"), table_name="agents")
    op.drop_table("agents")
