"""Authentication and authorization for every protected route.

`AuthDep` is the single door: it resolves the session cookie, refuses anything
that is not a live session for an active member, and — because the session
lives in a cookie — checks the CSRF token on every state-changing request.
"""

from typing import Annotated

from fastapi import Depends, Request

from app.core.config import CSRF_HEADER, SESSION_COOKIE, UNSAFE_METHODS, Settings
from app.core.errors import CsrfError, UnauthorizedError
from app.db.session import SessionDep
from app.services import auth_service
from app.services.auth_service import AuthContext


def app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(app_settings)]


async def current_auth(request: Request, db: SessionDep, settings: SettingsDep) -> AuthContext:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        raise UnauthorizedError()

    context = await auth_service.resolve_session(db, settings=settings, token=token)
    if context is None:
        raise UnauthorizedError("Your session is no longer valid. Sign in again.")

    if request.method in UNSAFE_METHODS:
        supplied = request.headers.get(CSRF_HEADER, "")
        if not auth_service.session_csrf_matches(context.session, supplied):
            raise CsrfError()

    return context


AuthDep = Annotated[AuthContext, Depends(current_auth)]
