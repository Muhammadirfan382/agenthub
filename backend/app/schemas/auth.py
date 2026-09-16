"""Authentication and membership payloads.

Responses never include password hashes, session tokens or anything else a
client has no business seeing.
"""

from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from app.schemas.common import CamelModel, SecretCamelModel
from app.schemas.enums import Role, UserStatus

# Deliberately permissive: real validity is proven by delivery, not by regex.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$"

EmailField = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=254, pattern=EMAIL_PATTERN)
]
# Login accepts any length: the policy belongs on the way in, not at the door.
PasswordField = Annotated[str, StringConstraints(min_length=1, max_length=256)]
NameField = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
TimezoneField = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]


class LoginRequest(SecretCamelModel):
    email: EmailField
    password: PasswordField


class PasswordChangeRequest(SecretCamelModel):
    current_password: PasswordField
    new_password: PasswordField


class ProfileUpdateRequest(CamelModel):
    name: NameField
    timezone: TimezoneField


class OrganizationRead(CamelModel):
    id: str
    name: str
    slug: str


class UserRead(CamelModel):
    id: str
    email: str
    name: str
    status: UserStatus
    timezone: str
    created_at: datetime
    last_login_at: datetime | None


class OrganizationMembershipRead(CamelModel):
    """One organization a user belongs to, with their role in it."""

    organization: OrganizationRead
    role: Role


class SessionRead(CamelModel):
    user: UserRead
    organization: OrganizationRead
    role: Role
    memberships: list[OrganizationMembershipRead]
    expires_at: datetime


class MemberRead(CamelModel):
    id: str
    user_id: str
    email: str
    name: str
    role: Role
    status: UserStatus
    created_at: datetime
    last_login_at: datetime | None


class MemberAddRequest(CamelModel):
    """Adds an existing account to this organization. Accounts are created out of band."""

    email: EmailField
    role: Role


class MemberRoleUpdate(CamelModel):
    role: Role


class OrganizationSwitch(CamelModel):
    organization_id: str
