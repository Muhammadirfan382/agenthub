"""Add the execution runtime: trace tables, budgets, approvals and the kill switch

Existing executions predate the runtime. They keep their status and metadata,
are marked as produced by the `simulation` runtime, and get the default budget;
they have no recorded trace because nothing recorded one.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- executions: how it ran, what it may use, who asked ------------------
    with op.batch_alter_table("executions") as batch:
        batch.add_column(
            sa.Column("runtime", sa.String(length=16), nullable=False, server_default="simulation")
        )
        batch.add_column(
            sa.Column("requested_by_id", sa.String(length=64), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "requested_by_name", sa.String(length=120), nullable=False, server_default=""
            )
        )
        batch.add_column(
            sa.Column("max_runtime_seconds", sa.Integer(), nullable=False, server_default="300")
        )
        batch.add_column(
            sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="50000")
        )
        batch.add_column(
            sa.Column("max_tool_calls", sa.Integer(), nullable=False, server_default="20")
        )
        batch.add_column(sa.Column("step_index", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("claimed_by", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("cancel_requested_by", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("error_code", sa.String(length=48), nullable=True))
        batch.add_column(sa.Column("error_message", sa.Text(), nullable=True))
    op.create_index(
        op.f("ix_executions_heartbeat_at"), "executions", ["heartbeat_at"], unique=False
    )

    # The defaults existed to fill existing rows; new rows are set by the code.
    with op.batch_alter_table("executions") as batch:
        for column in (
            "runtime",
            "requested_by_id",
            "requested_by_name",
            "max_runtime_seconds",
            "max_tokens",
            "max_tool_calls",
            "step_index",
            "attempt",
        ):
            batch.alter_column(column, server_default=None)

    # --- the organization-wide kill switch -----------------------------------
    with op.batch_alter_table("organizations") as batch:
        batch.add_column(
            sa.Column(
                "executions_paused", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch.add_column(
            sa.Column("executions_paused_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("executions_paused_by", sa.String(length=120), nullable=True))
        batch.add_column(
            sa.Column("executions_paused_reason", sa.String(length=200), nullable=True)
        )
    with op.batch_alter_table("organizations") as batch:
        batch.alter_column("executions_paused", server_default=None)

    # --- what a run records --------------------------------------------------
    op.create_table(
        "execution_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_execution_events_execution_id_executions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_execution_events_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_execution_events")),
    )
    op.create_index(
        op.f("ix_execution_events_execution_id"), "execution_events", ["execution_id"], unique=False
    )
    op.create_index(
        op.f("ix_execution_events_organization_id"),
        "execution_events",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "execution_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("level", sa.String(length=8), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_execution_logs_execution_id_executions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_execution_logs")),
    )
    op.create_index(
        op.f("ix_execution_logs_execution_id"), "execution_logs", ["execution_id"], unique=False
    )

    op.create_table(
        "execution_tool_calls",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("tool", sa.String(length=48), nullable=False),
        sa.Column("capability", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_summary", sa.Text(), nullable=False),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_execution_tool_calls_execution_id_executions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_execution_tool_calls")),
    )
    op.create_index(
        op.f("ix_execution_tool_calls_execution_id"),
        "execution_tool_calls",
        ["execution_id"],
        unique=False,
    )

    op.create_table(
        "execution_approvals",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("capability", sa.String(length=32), nullable=False),
        sa.Column("tool", sa.String(length=48), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", sa.String(length=64), nullable=True),
        sa.Column("decided_by_name", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("automatic", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["executions.id"],
            name=op.f("fk_execution_approvals_execution_id_executions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_execution_approvals_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_execution_approvals")),
    )
    op.create_index(
        op.f("ix_execution_approvals_execution_id"),
        "execution_approvals",
        ["execution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_execution_approvals_organization_id"),
        "execution_approvals",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_execution_approvals_status"), "execution_approvals", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_execution_approvals_status"), table_name="execution_approvals")
    op.drop_index(op.f("ix_execution_approvals_organization_id"), table_name="execution_approvals")
    op.drop_index(op.f("ix_execution_approvals_execution_id"), table_name="execution_approvals")
    op.drop_table("execution_approvals")

    op.drop_index(op.f("ix_execution_tool_calls_execution_id"), table_name="execution_tool_calls")
    op.drop_table("execution_tool_calls")

    op.drop_index(op.f("ix_execution_logs_execution_id"), table_name="execution_logs")
    op.drop_table("execution_logs")

    op.drop_index(op.f("ix_execution_events_organization_id"), table_name="execution_events")
    op.drop_index(op.f("ix_execution_events_execution_id"), table_name="execution_events")
    op.drop_table("execution_events")

    with op.batch_alter_table("organizations") as batch:
        batch.drop_column("executions_paused_reason")
        batch.drop_column("executions_paused_by")
        batch.drop_column("executions_paused_at")
        batch.drop_column("executions_paused")

    op.drop_index(op.f("ix_executions_heartbeat_at"), table_name="executions")
    with op.batch_alter_table("executions") as batch:
        for column in (
            "error_message",
            "error_code",
            "cancel_requested_by",
            "cancel_requested_at",
            "heartbeat_at",
            "claimed_at",
            "claimed_by",
            "attempt",
            "step_index",
            "max_tool_calls",
            "max_tokens",
            "max_runtime_seconds",
            "requested_by_name",
            "requested_by_id",
            "runtime",
        ):
            batch.drop_column(column)
