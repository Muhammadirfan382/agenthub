"""Sign in, sign out and the current session.

The session lives in an HttpOnly cookie, so browser JavaScript — and anything
injected into the page — cannot read it. A second, readable cookie carries the
CSRF token that every state-changing request must echo back in a header.
"""

from fastapi import APIRouter, Request, Response, status

from app.api.deps import AuthDep, SettingsDep
from app.core.config import CSRF_COOKIE, SESSION_COOKIE, Settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.db.session import SessionDep
from app.repositories import identity_repository
from app.schemas.auth import (
    LoginRequest,
    OrganizationSwitch,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    SessionRead,
    UserRead,
)
from app.services import auth_service
from app.services.auth_service import AuthContext
from app.services.login_guard import LoginGuard, client_address
from app.services.mappers import to_session_read, to_user_read

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookies(
    response: Response, settings: Settings, token: str, csrf_token: str
) -> None:
    max_age = settings.session_lifetime_minutes * 60
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        # Strict: the browser never sends these cookies on a cross-site request,
        # which removes the whole class of cross-site request attacks.
        samesite="strict",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=max_age,
        path="/",
        # Readable on purpose: the app echoes it in the X-CSRF-Token header.
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
    )


def _clear_session_cookies(response: Response, settings: Settings) -> None:
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, samesite="strict")


# Login itself carries no CSRF token: there is no session to tie one to. It is
# protected by requiring a JSON body, which a cross-site form cannot send without
# a CORS preflight that this API never answers.
@router.post("/login", response_model=SessionRead, summary="Sign in")
async def login(
    request: Request,
    response: Response,
    db: SessionDep,
    settings: SettingsDep,
    body: LoginRequest,
) -> SessionRead:
    guard: LoginGuard = request.app.state.login_guard
    address = client_address(request)
    guard.check(email=body.email, address=address)

    try:
        user = await auth_service.authenticate(db, email=body.email, password=body.password)
    except UnauthorizedError:
        guard.record_failure(email=body.email, address=address)
        raise
    guard.record_success(email=body.email)

    memberships = await identity_repository.list_memberships_for_user(db, user.id)
    if not memberships:
        # Authentication succeeded, but there is nothing this account may reach.
        raise ForbiddenError(
            "This account is not a member of any organization. Ask an administrator to add you."
        )

    # A new sign-in never continues an old session.
    existing_token = request.cookies.get(SESSION_COOKIE, "")
    if existing_token:
        previous = await auth_service.resolve_session(db, settings=settings, token=existing_token)
        if previous is not None:
            await auth_service.revoke_session(db, previous.session)

    membership, organization = memberships[0]
    row, token, csrf_token = await auth_service.start_session(
        db, settings=settings, user=user, organization_id=organization.id
    )
    _set_session_cookies(response, settings, token, csrf_token)

    context = AuthContext(user=user, organization=organization, membership=membership, session=row)
    return to_session_read(context, memberships)


@router.get("/session", response_model=SessionRead, summary="The current session")
async def read_session(db: SessionDep, auth: AuthDep) -> SessionRead:
    memberships = await identity_repository.list_memberships_for_user(db, auth.user_id)
    return to_session_read(auth, memberships)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sign out")
async def logout(db: SessionDep, settings: SettingsDep, auth: AuthDep) -> Response:
    await auth_service.revoke_session(db, auth.session)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_session_cookies(response, settings)
    return response


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT, summary="Change your password")
async def change_password(db: SessionDep, auth: AuthDep, body: PasswordChangeRequest) -> Response:
    await auth_service.change_password(
        db,
        user=auth.user,
        current_password=body.current_password,
        new_password=body.new_password,
        keep_session_id=auth.session.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/profile", response_model=UserRead, summary="Update your profile")
async def update_profile(db: SessionDep, auth: AuthDep, body: ProfileUpdateRequest) -> UserRead:
    user = await auth_service.update_profile(
        db, user=auth.user, name=body.name, timezone=body.timezone
    )
    return to_user_read(user)


@router.post("/organization", response_model=SessionRead, summary="Switch the active organization")
async def switch_organization(
    db: SessionDep, auth: AuthDep, body: OrganizationSwitch
) -> SessionRead:
    membership, organization = await auth_service.switch_organization(
        db, context=auth, organization_id=body.organization_id
    )
    context = AuthContext(
        user=auth.user, organization=organization, membership=membership, session=auth.session
    )
    memberships = await identity_repository.list_memberships_for_user(db, auth.user_id)
    return to_session_read(context, memberships)
