"""Queries for published versions, marketplace listings and installations."""

from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models import Agent, AgentVersion, Installation, Organization

# One row per marketplace listing: the version, its agent, and the publisher.
Listing = tuple[AgentVersion, Agent, Organization]

# An alias is what makes the subquery below correlate with the outer row. Using
# the same entity on both sides would compare the table with itself, which is
# always true, and would collapse every agent onto one global maximum.
_Candidate = aliased(AgentVersion)


def _newest_published_id() -> Any:
    """The id of an agent's newest published version, per outer row.

    Ordering by id as well keeps the answer stable when two versions share a
    timestamp, which happens easily on a fast machine.
    """
    return (
        select(_Candidate.id)
        .where(_Candidate.agent_id == AgentVersion.agent_id, _Candidate.status == "published")
        .order_by(_Candidate.published_at.desc(), _Candidate.id.desc())
        .limit(1)
        .scalar_subquery()
    )


async def get_version(session: AsyncSession, version_id: str) -> AgentVersion | None:
    version: AgentVersion | None = await session.get(AgentVersion, version_id)
    return version


async def get_version_by_number(
    session: AsyncSession, agent_id: str, version: str
) -> AgentVersion | None:
    row: AgentVersion | None = await session.scalar(
        select(AgentVersion).where(
            AgentVersion.agent_id == agent_id, AgentVersion.version == version
        )
    )
    return row


async def latest_published_version(session: AsyncSession, agent_id: str) -> AgentVersion | None:
    row: AgentVersion | None = await session.scalar(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent_id, AgentVersion.status == "published")
        .order_by(AgentVersion.published_at.desc())
        .limit(1)
    )
    return row


async def count_published_versions(session: AsyncSession, agent_id: str) -> int:
    total = await session.scalar(
        select(func.count())
        .select_from(AgentVersion)
        .where(AgentVersion.agent_id == agent_id, AgentVersion.status == "published")
    )
    return int(total or 0)


async def list_versions(
    session: AsyncSession, agent_id: str, *, limit: int, offset: int
) -> tuple[list[AgentVersion], int]:
    condition = AgentVersion.agent_id == agent_id
    total = await session.scalar(select(func.count()).select_from(AgentVersion).where(condition))
    rows = await session.scalars(
        select(AgentVersion)
        .where(condition)
        .order_by(AgentVersion.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), int(total or 0)


def _visible_listings(organization_id: str) -> Select[Listing]:
    """Public listings from anywhere, plus this organization's own shared ones.

    A private agent is never listed, not even to its own organization: sharing
    is something someone has to choose.
    """
    return (
        select(AgentVersion, Agent, Organization)
        .join(Agent, Agent.id == AgentVersion.agent_id)
        .join(Organization, Organization.id == AgentVersion.organization_id)
        .where(
            AgentVersion.status == "published",
            AgentVersion.id == _newest_published_id(),
            or_(
                Agent.visibility == "public",
                and_(
                    Agent.organization_id == organization_id,
                    Agent.visibility == "organization",
                ),
            ),
        )
    )


async def list_marketplace(
    session: AsyncSession,
    *,
    organization_id: str,
    search: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    verified_only: bool = False,
    limit: int,
    offset: int,
) -> tuple[list[Listing], int]:
    statement = _visible_listings(organization_id)

    if search:
        pattern = "%" + search.strip().lower() + "%"
        statement = statement.where(
            or_(
                func.lower(Agent.name).like(pattern),
                func.lower(Agent.description).like(pattern),
                func.lower(Organization.name).like(pattern),
            )
        )
    if category and category != "all":
        statement = statement.where(Agent.category == category)
    if verified_only:
        statement = statement.where(Agent.verification == "verified")

    rows = list(await session.execute(statement.order_by(AgentVersion.published_at.desc())))
    # Tags are a JSON document, so this filter cannot be pushed into SQL portably.
    if tag:
        wanted = tag.strip().lower()
        rows = [row for row in rows if wanted in [str(t).lower() for t in row[1].tags]]

    total = len(rows)
    page = rows[offset : offset + limit]
    return [(version, agent, organization) for version, agent, organization in page], total


async def marketplace_tags(session: AsyncSession, *, organization_id: str) -> list[str]:
    rows = await session.execute(_visible_listings(organization_id))
    tags = {str(tag).lower() for _, agent, _ in rows for tag in agent.tags}
    return sorted(tags)


async def get_installation(
    session: AsyncSession, installation_id: str, organization_id: str
) -> Installation | None:
    row: Installation | None = await session.scalar(
        select(Installation).where(
            Installation.id == installation_id,
            Installation.organization_id == organization_id,
        )
    )
    return row


async def get_installation_for_agent(
    session: AsyncSession, organization_id: str, agent_id: str
) -> Installation | None:
    row: Installation | None = await session.scalar(
        select(Installation).where(
            Installation.organization_id == organization_id, Installation.agent_id == agent_id
        )
    )
    return row


async def list_installations(
    session: AsyncSession, organization_id: str, *, limit: int, offset: int
) -> tuple[list[Installation], int]:
    condition = Installation.organization_id == organization_id
    total = await session.scalar(select(func.count()).select_from(Installation).where(condition))
    rows = await session.scalars(
        select(Installation)
        .where(condition)
        .order_by(Installation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), int(total or 0)


async def installations_by_agent(
    session: AsyncSession, organization_id: str, agent_ids: list[str]
) -> dict[str, Installation]:
    """Used to mark listings as already installed, in one query."""
    if not agent_ids:
        return {}
    rows = await session.scalars(
        select(Installation).where(
            Installation.organization_id == organization_id,
            Installation.agent_id.in_(agent_ids),
        )
    )
    return {installation.agent_id: installation for installation in rows}
