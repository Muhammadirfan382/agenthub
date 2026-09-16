"""Add organizations, users, memberships and sessions, and scope agents to an organization

Existing agents and executions predate organizations. They are moved into one
"Legacy Workspace" organization so the NOT NULL constraint can be applied
without losing rows; that organization has no members until someone is added
to it, so nothing becomes readable that was not already local development data.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_ORGANIZATION_ID = "org_legacy_workspace"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("slug", name=op.f("uq_organizations_slug")),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    op.create_table(
        "memberships",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_memberships_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_memberships_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_memberships_user_org"),
    )
    op.create_index(
        op.f("ix_memberships_organization_id"), "memberships", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_memberships_user_id"), "memberships", ["user_id"], unique=False)

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_sessions_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)

    # --- scope existing rows -------------------------------------------------
    with op.batch_alter_table("agents") as batch:
        batch.add_column(sa.Column("organization_id", sa.String(length=64), nullable=True))
    with op.batch_alter_table("executions") as batch:
        batch.add_column(sa.Column("organization_id", sa.String(length=64), nullable=True))

    connection = op.get_bind()
    existing_agents = connection.execute(sa.text("SELECT COUNT(*) FROM agents")).scalar() or 0
    existing_executions = (
        connection.execute(sa.text("SELECT COUNT(*) FROM executions")).scalar() or 0
    )
    if existing_agents or existing_executions:
        connection.execute(
            sa.text(
                "INSERT INTO organizations (id, name, slug, created_at) "
                "VALUES (:id, :name, :slug, :created_at)"
            ),
            {
                "id": LEGACY_ORGANIZATION_ID,
                "name": "Legacy Workspace",
                "slug": "legacy-workspace",
                "created_at": datetime.now(UTC),
            },
        )
        connection.execute(
            sa.text("UPDATE agents SET organization_id = :org"), {"org": LEGACY_ORGANIZATION_ID}
        )
        connection.execute(
            sa.text("UPDATE executions SET organization_id = :org"),
            {"org": LEGACY_ORGANIZATION_ID},
        )

    with op.batch_alter_table("agents") as batch:
        batch.alter_column("organization_id", existing_type=sa.String(length=64), nullable=False)
        # Agent names are unique inside an organization, not across the platform.
        batch.drop_constraint(op.f("uq_agents_name"), type_="unique")
        batch.create_unique_constraint(
            "uq_agents_organization_id_name", ["organization_id", "name"]
        )
        batch.create_foreign_key(
            op.f("fk_agents_organization_id_organizations"),
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index(
        op.f("ix_agents_organization_id"), "agents", ["organization_id"], unique=False
    )

    with op.batch_alter_table("executions") as batch:
        batch.alter_column("organization_id", existing_type=sa.String(length=64), nullable=False)
        batch.create_foreign_key(
            op.f("fk_executions_organization_id_organizations"),
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index(
        op.f("ix_executions_organization_id"), "executions", ["organization_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_executions_organization_id"), table_name="executions")
    with op.batch_alter_table("executions") as batch:
        batch.drop_constraint(op.f("fk_executions_organization_id_organizations"), type_="foreignkey")
        batch.drop_column("organization_id")

    op.drop_index(op.f("ix_agents_organization_id"), table_name="agents")
    with op.batch_alter_table("agents") as batch:
        batch.drop_constraint(op.f("fk_agents_organization_id_organizations"), type_="foreignkey")
        batch.drop_constraint("uq_agents_organization_id_name", type_="unique")
        batch.create_unique_constraint(op.f("uq_agents_name"), ["name"])
        batch.drop_column("organization_id")

    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_index(op.f("ix_memberships_user_id"), table_name="memberships")
    op.drop_index(op.f("ix_memberships_organization_id"), table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("organizations")
