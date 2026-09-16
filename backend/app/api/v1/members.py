"""Organization membership.

Accounts are created out of band (`scripts/create_user.py`); this adds an
existing account to an organization and sets its role. There is no email
delivery yet, so there are no invitations to accept.
"""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import AuthDep
from app.core.errors import ForbiddenError, NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.db.models import Membership, User
from app.db.session import SessionDep
from app.repositories import identity_repository
from app.schemas.auth import MemberAddRequest, MemberRead, MemberRoleUpdate
from app.schemas.enums import Role
from app.services import auth_service, authorization
from app.services.auth_service import AuthContext
from app.services.mappers import to_member_read

router = APIRouter(prefix="/members", tags=["members"])


async def _member_in_organization(
    db: SessionDep, membership_id: str, context: AuthContext
) -> tuple[Membership, User]:
    membership = await identity_repository.get_membership_by_id(db, membership_id)
    # Membership ids from another organization must look like they do not exist.
    if membership is None or membership.organization_id != context.organization_id:
        raise NotFoundError("No member with this id.")
    user = await identity_repository.get_user(db, membership.user_id)
    if user is None:
        raise NotFoundError("No member with this id.")
    return membership, user


@router.get("", response_model=Page[MemberRead], summary="List members")
async def list_members(
    db: SessionDep,
    auth: AuthDep,
    page: Annotated[PageParams, Depends(page_params)],
) -> Page[MemberRead]:
    authorization.require(auth.role, "member:read")
    rows, total = await identity_repository.list_members(
        db, auth.organization_id, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[to_member_read(membership, user) for membership, user in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an existing account to this organization",
)
async def add_member(db: SessionDep, auth: AuthDep, body: MemberAddRequest) -> MemberRead:
    authorization.require(auth.role, "member:manage")
    authorization.require_assignable_role(auth.role, body.role)

    user = await identity_repository.get_user_by_email(db, body.email)
    if user is None:
        # Says nothing about whether the account exists elsewhere on the platform.
        raise NotFoundError("No AgentHub account uses this email address.")

    membership = await auth_service.add_member(
        db, organization=auth.organization, user=user, role=body.role
    )
    return to_member_read(membership, user)


@router.patch("/{membership_id}", response_model=MemberRead, summary="Change a member's role")
async def set_member_role(
    db: SessionDep, auth: AuthDep, membership_id: str, body: MemberRoleUpdate
) -> MemberRead:
    authorization.require(auth.role, "member:manage")
    membership, user = await _member_in_organization(db, membership_id, auth)

    if membership.user_id == auth.user_id:
        raise ForbiddenError("You cannot change your own role.")
    authorization.require_can_manage_member(auth.role, cast(Role, membership.role))
    authorization.require_assignable_role(auth.role, body.role)

    updated = await auth_service.set_member_role(db, membership=membership, role=body.role)
    return to_member_read(updated, user)


@router.delete(
    "/{membership_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a member"
)
async def remove_member(db: SessionDep, auth: AuthDep, membership_id: str) -> Response:
    authorization.require(auth.role, "member:manage")
    membership, _ = await _member_in_organization(db, membership_id, auth)

    if membership.user_id == auth.user_id:
        raise ForbiddenError("You cannot remove yourself from the organization.")
    authorization.require_can_manage_member(auth.role, cast(Role, membership.role))

    await auth_service.remove_member(db, membership=membership)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
