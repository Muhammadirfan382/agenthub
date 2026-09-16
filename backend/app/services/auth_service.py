"""Identity, sessions and membership rules.

Sessions are opaque random tokens stored as fingerprints and checked against
the database on every request, so signing out, disabling a user or removing a
membership takes effect immediately — a stolen token stops working the moment
the row is revoked.
"""

import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import timedelta

from anyio import to_thread
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import (
    hash_password,
    hash_token,
    new_csrf_token,
    new_session_token,
    spend_dummy_hash,
    tokens_match,
    verify_password,
)
from app.core.time import ensure_utc, now_utc
from app.db.models import Membership, Organization, Session, User
from app.repositories import identity_repository
from app.schemas.enums import Role

# Only refresh the activity timestamp once a minute, so a busy tab does not
# write a row on every request.
SESSION_TOUCH_SECONDS = 60

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


@dataclass(frozen=True)
class AuthContext:
    """Who is making this request, and in which organization."""

    user: User
    organization: Organization
    membership: Membership
    session: Session

    @property
    def role(self) -> Role:
        role: Role = self.membership.role  # type: ignore[assignment]
        return role

    @property
    def organization_id(self) -> str:
        return self.organization.id

    @property
    def user_id(self) -> str:
        return self.user.id


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug[:48] or "organization"


def normalise_email(email: str) -> str:
    return email.strip().lower()


def validate_password(password: str, *, email: str) -> None:
    """Length over composition rules, and never the email address itself."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ConflictError(f"The password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ConflictError(f"The password must be at most {MAX_PASSWORD_LENGTH} characters long.")
    local_part = normalise_email(email).split("@", 1)[0]
    if password.strip().lower() in {normalise_email(email), local_part}:
        raise ConflictError("The password must not be your email address.")


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    name: str,
    password: str,
    timezone: str = "UTC",
) -> User:
    address = normalise_email(email)
    if await identity_repository.get_user_by_email(session, address):
        raise ConflictError("An account with this email already exists.")
    validate_password(password, email=address)

    now = now_utc()
    user = User(
        id=new_id("usr"),
        email=address,
        name=name.strip(),
        password_hash=await to_thread.run_sync(hash_password, password),
        status="active",
        timezone=timezone,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    await session.flush()
    return user


async def create_organization(session: AsyncSession, *, name: str) -> Organization:
    base = slugify(name)
    slug = base
    while await identity_repository.get_organization_by_slug(session, slug):
        slug = f"{base}-{uuid.uuid4().hex[:6]}"

    organization = Organization(
        id=new_id("org"), name=name.strip(), slug=slug, created_at=now_utc()
    )
    session.add(organization)
    await session.flush()
    return organization


async def add_member(
    session: AsyncSession, *, organization: Organization, user: User, role: Role
) -> Membership:
    existing = await identity_repository.get_membership(session, user.id, organization.id)
    if existing is not None:
        raise ConflictError("This user is already a member of the organization.")

    membership = Membership(
        id=new_id("mem"),
        user_id=user.id,
        organization_id=organization.id,
        role=role,
        created_at=now_utc(),
    )
    session.add(membership)
    await session.flush()
    return membership


async def set_member_role(
    session: AsyncSession, *, membership: Membership, role: Role
) -> Membership:
    if membership.role == "owner" and role != "owner":
        owners = await identity_repository.count_owners(session, membership.organization_id)
        if owners <= 1:
            raise ForbiddenError("The organization must keep at least one owner.")

    membership.role = role
    await session.flush()
    return membership


async def remove_member(session: AsyncSession, *, membership: Membership) -> None:
    if membership.role == "owner":
        owners = await identity_repository.count_owners(session, membership.organization_id)
        if owners <= 1:
            raise ForbiddenError("The organization must keep at least one owner.")
    await session.delete(membership)
    await session.flush()


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
    """One message for every failure: no account enumeration through login."""
    failure = UnauthorizedError("Incorrect email or password.")
    user = await identity_repository.get_user_by_email(session, normalise_email(email))

    if user is None:
        # Spend comparable time so an unknown address is not obvious from timing.
        await to_thread.run_sync(spend_dummy_hash)
        raise failure
    if not await to_thread.run_sync(verify_password, password, user.password_hash):
        raise failure
    if user.status != "active":
        raise failure
    return user


async def start_session(
    session: AsyncSession, *, settings: Settings, user: User, organization_id: str
) -> tuple[Session, str, str]:
    """Returns the row plus the session and CSRF tokens, which are shown once."""
    token = new_session_token()
    csrf_token = new_csrf_token()
    now = now_utc()

    row = Session(
        id=new_id("ses"),
        user_id=user.id,
        organization_id=organization_id,
        token_hash=hash_token(token),
        csrf_token_hash=hash_token(csrf_token),
        created_at=now,
        expires_at=now + timedelta(minutes=settings.session_lifetime_minutes),
        last_seen_at=now,
    )
    user.last_login_at = now
    session.add(row)
    await session.flush()
    return row, token, csrf_token


async def resolve_session(
    session: AsyncSession, *, settings: Settings, token: str
) -> AuthContext | None:
    """None for anything that is not a live session for an active member."""
    row = await identity_repository.get_session_by_token_hash(session, hash_token(token))
    if row is None or row.revoked_at is not None:
        return None

    now = now_utc()
    if ensure_utc(row.expires_at) <= now:
        return None
    idle_deadline = ensure_utc(row.last_seen_at) + timedelta(
        minutes=settings.session_idle_timeout_minutes
    )
    if idle_deadline <= now:
        return None

    user = await identity_repository.get_user(session, row.user_id)
    if user is None or user.status != "active":
        return None

    # Access follows the membership: removing it ends access immediately.
    membership = await identity_repository.get_membership(session, user.id, row.organization_id)
    if membership is None:
        return None
    organization = await identity_repository.get_organization(session, row.organization_id)
    if organization is None:
        return None

    if (now - ensure_utc(row.last_seen_at)).total_seconds() >= SESSION_TOUCH_SECONDS:
        row.last_seen_at = now

    return AuthContext(user=user, organization=organization, membership=membership, session=row)


def session_csrf_matches(row: Session, supplied: str) -> bool:
    return bool(supplied) and tokens_match(hash_token(supplied), row.csrf_token_hash)


async def revoke_session(session: AsyncSession, row: Session) -> None:
    row.revoked_at = now_utc()
    await session.flush()


async def switch_organization(
    session: AsyncSession, *, context: AuthContext, organization_id: str
) -> tuple[Membership, Organization]:
    """Point an existing session at another organization the user belongs to."""
    membership = await identity_repository.get_membership(session, context.user_id, organization_id)
    organization = await identity_repository.get_organization(session, organization_id)
    if membership is None or organization is None:
        # Same answer whether the organization is unknown or simply not yours.
        raise NotFoundError("You are not a member of this organization.")

    context.session.organization_id = organization_id
    await session.flush()
    return membership, organization


async def change_password(
    session: AsyncSession,
    *,
    user: User,
    current_password: str,
    new_password: str,
    keep_session_id: str,
) -> None:
    """Changes the password and signs the account out everywhere else.

    Someone changing a password may be doing it because another session is not
    theirs, so every other session for this account ends here.
    """
    if not await to_thread.run_sync(verify_password, current_password, user.password_hash):
        raise UnauthorizedError("The current password is incorrect.")
    validate_password(new_password, email=user.email)

    now = now_utc()
    user.password_hash = await to_thread.run_sync(hash_password, new_password)
    user.updated_at = now
    await identity_repository.revoke_other_sessions(
        session, user_id=user.id, keep_session_id=keep_session_id, at=now
    )
    await session.flush()


async def update_profile(session: AsyncSession, *, user: User, name: str, timezone: str) -> User:
    """Name and timezone only. Changing an email needs a verification flow."""
    user.name = name.strip()
    user.timezone = timezone
    user.updated_at = now_utc()
    await session.flush()
    return user
