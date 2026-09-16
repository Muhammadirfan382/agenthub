"""Execution reads."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import Execution
from app.repositories import execution_repository


async def get_execution(session: AsyncSession, execution_id: str) -> Execution:
    execution = await execution_repository.get_execution(session, execution_id)
    if execution is None:
        raise NotFoundError("No execution with this id.")
    return execution
