"""Identity queries: users, organizations, memberships and sessions."""

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Membership, Organization, Session, User


async def get_user(session: AsyncSession, user_id: str) -> User | None:
    user: User | None = await session.get(User, user_id)
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    user: User | None = await session.scalar(select(User).where(User.email == email.lower()))
    return user


async def get_organization(session: AsyncSession, organization_id: str) -> Organization | None:
    organization: Organization | None = await session.get(Organization, organization_id)
    return organization


async def get_organization_by_slug(session: AsyncSession, slug: str) -> Organization | None:
    organization: Organization | None = await session.scalar(
        select(Organization).where(Organization.slug == slug)
    )
    return organization


async def get_membership(
    session: AsyncSession, user_id: str, organization_id: str
) -> Membership | None:
    membership: Membership | None = await session.scalar(
        select(Membership).where(
            Membership.user_id == user_id, Membership.organization_id == organization_id
        )
    )
    return membership


async def get_membership_by_id(session: AsyncSession, membership_id: str) -> Membership | None:
    membership: Membership | None = await session.get(Membership, membership_id)
    return membership


async def list_memberships_for_user(
    session: AsyncSession, user_id: str
) -> list[tuple[Membership, Organization]]:
    rows = await session.execute(
        select(Membership, Organization)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == user_id)
        .order_by(Organization.name.asc())
    )
    return [(membership, organization) for membership, organization in rows]


async def list_members(
    session: AsyncSession, organization_id: str, *, limit: int, offset: int
) -> tuple[list[tuple[Membership, User]], int]:
    condition = Membership.organization_id == organization_id
    total = await session.scalar(select(func.count()).select_from(Membership).where(condition))
    rows = await session.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(condition)
        .order_by(User.name.asc())
        .limit(limit)
        .offset(offset)
    )
    return [(membership, user) for membership, user in rows], int(total or 0)


async def count_owners(session: AsyncSession, organization_id: str) -> int:
    total = await session.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.organization_id == organization_id, Membership.role == "owner")
    )
    return int(total or 0)


async def revoke_other_sessions(
    session: AsyncSession, *, user_id: str, keep_session_id: str, at: datetime
) -> None:
    """Ends every other live session for this account."""
    await session.execute(
        update(Session)
        .where(
            Session.user_id == user_id,
            Session.id != keep_session_id,
            Session.revoked_at.is_(None),
        )
        .values(revoked_at=at)
    )


async def get_session_by_token_hash(session: AsyncSession, token_hash: str) -> Session | None:
    row: Session | None = await session.scalar(
        select(Session).where(Session.token_hash == token_hash)
    )
    return row
