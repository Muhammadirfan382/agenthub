"""Add published versions and installations, and agent visibility

The version history that lived in an `agents.versions` JSON column becomes a
real table. Existing agents get one row carrying their current configuration as
a manifest, so nothing is lost; the column is then dropped.

Every agent starts `private`: making one visible in the marketplace is a
deliberate act, never a side effect of a migration.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-16
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _as_list(value: object) -> list[object]:
    """JSON columns come back decoded on PostgreSQL and as text on SQLite."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []
    return []


def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return {}


def upgrade() -> None:
    op.create_table(
        "agent_versions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("manifest", JSON_DOCUMENT, nullable=False),
        sa.Column("changelog", JSON_DOCUMENT, nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.String(length=64), nullable=False),
        sa.Column("created_by_name", sa.String(length=120), nullable=False),
        sa.CheckConstraint(
            "risk_score >= 0 AND risk_score <= 100",
            name=op.f("ck_agent_versions_risk_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_agent_versions_agent_id_agents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_agent_versions_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_versions")),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_id_version"),
    )
    op.create_index(
        op.f("ix_agent_versions_agent_id"), "agent_versions", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_agent_versions_organization_id"),
        "agent_versions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_versions_published_at"), "agent_versions", ["published_at"], unique=False
    )
    op.create_index(
        op.f("ix_agent_versions_risk_level"), "agent_versions", ["risk_level"], unique=False
    )
    op.create_index(op.f("ix_agent_versions_status"), "agent_versions", ["status"], unique=False)

    op.create_table(
        "installations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("agent_version_id", sa.String(length=64), nullable=False),
        sa.Column("agent_name", sa.String(length=120), nullable=False),
        sa.Column("publisher_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("grants", JSON_DOCUMENT, nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("installed_by_id", sa.String(length=64), nullable=False),
        sa.Column("installed_by_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "risk_score >= 0 AND risk_score <= 100",
            name=op.f("ck_installations_risk_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name=op.f("fk_installations_agent_id_agents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["agent_version_id"],
            ["agent_versions.id"],
            name=op.f("fk_installations_agent_version_id_agent_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_installations_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_installations")),
        sa.UniqueConstraint(
            "organization_id", "agent_id", name="uq_installations_organization_id_agent_id"
        ),
    )
    op.create_index(
        op.f("ix_installations_agent_id"), "installations", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_installations_organization_id"),
        "installations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(op.f("ix_installations_status"), "installations", ["status"], unique=False)
    op.create_index(
        op.f("ix_installations_updated_at"), "installations", ["updated_at"], unique=False
    )

    with op.batch_alter_table("agents") as batch:
        batch.add_column(
            sa.Column(
                "visibility", sa.String(length=16), nullable=False, server_default="private"
            )
        )

    _migrate_version_history()

    with op.batch_alter_table("agents") as batch:
        # The default existed only to fill the column for existing rows.
        batch.alter_column("visibility", server_default=None)
        batch.drop_column("versions")


def _migrate_version_history() -> None:
    """Turn each agent's current configuration into one draft version row."""
    connection = op.get_bind()
    agents = connection.execute(
        sa.text(
            "SELECT id, organization_id, name, description, category, tags, version, status, "
            "risk_level, risk_score, owner_id, owner_name, created_at, model, tools, "
            "permissions, resource_limits, security_policy, versions FROM agents"
        )
    ).mappings()

    now = datetime.now(UTC)
    for index, agent in enumerate(agents):
        manifest = {
            "name": agent["name"],
            "description": agent["description"],
            "category": agent["category"],
            "tags": _as_list(agent["tags"]),
            "version": agent["version"],
            "model": _as_dict(agent["model"]),
            "tools": _as_list(agent["tools"]),
            "requiredPermissions": _as_list(agent["permissions"]),
            "resourceLimits": _as_dict(agent["resource_limits"]),
            "securityPolicy": _as_dict(agent["security_policy"]),
        }
        # Existing agents keep their history as a changelog note; nothing is
        # marked published, because nobody chose to publish it.
        previous = [str(entry.get("version", "")) for entry in _as_list(agent["versions"])]
        changelog = ["Carried over from the agent's configuration."]
        if previous:
            changelog.append("Earlier recorded versions: " + ", ".join(previous) + ".")

        connection.execute(
            sa.text(
                "INSERT INTO agent_versions (id, agent_id, organization_id, version, status, "
                "manifest, changelog, risk_level, risk_score, created_at, published_at, "
                "deprecated_at, created_by_id, created_by_name) VALUES (:id, :agent_id, :org, "
                ":version, 'draft', :manifest, :changelog, :risk_level, :risk_score, :created_at, "
                "NULL, NULL, :by_id, :by_name)"
            ),
            {
                "id": f"ver_migrated_{index:06d}",
                "agent_id": agent["id"],
                "org": agent["organization_id"],
                "version": agent["version"],
                "manifest": json.dumps(manifest),
                "changelog": json.dumps(changelog),
                "risk_level": agent["risk_level"],
                "risk_score": agent["risk_score"],
                "created_at": agent["created_at"] or now,
                "by_id": agent["owner_id"],
                "by_name": agent["owner_name"],
            },
        )


def downgrade() -> None:
    with op.batch_alter_table("agents") as batch:
        batch.add_column(sa.Column("versions", JSON_DOCUMENT, nullable=True))
    op.execute(sa.text("UPDATE agents SET versions = '[]'"))
    with op.batch_alter_table("agents") as batch:
        batch.alter_column("versions", existing_type=JSON_DOCUMENT, nullable=False)
        batch.drop_column("visibility")

    op.drop_index(op.f("ix_installations_updated_at"), table_name="installations")
    op.drop_index(op.f("ix_installations_status"), table_name="installations")
    op.drop_index(op.f("ix_installations_organization_id"), table_name="installations")
    op.drop_index(op.f("ix_installations_agent_id"), table_name="installations")
    op.drop_table("installations")

    op.drop_index(op.f("ix_agent_versions_status"), table_name="agent_versions")
    op.drop_index(op.f("ix_agent_versions_risk_level"), table_name="agent_versions")
    op.drop_index(op.f("ix_agent_versions_published_at"), table_name="agent_versions")
    op.drop_index(op.f("ix_agent_versions_organization_id"), table_name="agent_versions")
    op.drop_index(op.f("ix_agent_versions_agent_id"), table_name="agent_versions")
    op.drop_table("agent_versions")
