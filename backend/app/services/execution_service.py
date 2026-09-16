"""Execution reads."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import Execution
from app.repositories import execution_repository
from app.services import authorization
from app.services.auth_service import AuthContext


async def get_execution(
    session: AsyncSession, execution_id: str, *, context: AuthContext
) -> Execution:
    """Scoped to the caller's organization: anything else is a 404."""
    authorization.require(context.role, "execution:read")
    execution = await execution_repository.get_execution(
        session, execution_id, context.organization_id
    )
    if execution is None:
        raise NotFoundError("No execution with this id.")
    return execution
