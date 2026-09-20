"""The audit log, read-only. There is no endpoint that changes or deletes an event."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import AuthDep
from app.core.pagination import Page, PageParams, page_params
from app.core.time import ensure_utc
from app.db.models import AuditEvent
from app.db.session import SessionDep
from app.schemas.common import CamelModel
from app.services import authorization

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEventRead(CamelModel):
    id: str
    at: datetime
    actor_type: str
    actor_id: str | None
    actor_name: str
    action: str
    target_type: str | None
    target_id: str | None
    outcome: str
    detail: dict[str, Any]


@router.get(
    "",
    response_model=Page[AuditEventRead],
    summary="The organization's audit log",
    description="Newest first. Filter by action prefix (e.g. `policy.`) or outcome.",
)
async def list_audit_events(
    db: SessionDep,
    auth: AuthDep,
    page: Annotated[PageParams, Depends(page_params)],
    action: Annotated[
        str | None, Query(max_length=64, pattern=r"^[a-z_.]+$", description="Action prefix.")
    ] = None,
    outcome: Annotated[str | None, Query(pattern=r"^(success|failure|denied|allowed)$")] = None,
) -> Page[AuditEventRead]:
    authorization.require(auth.role, "audit:read")
    filters = [AuditEvent.organization_id == auth.organization_id]
    if action:
        filters.append(AuditEvent.action.startswith(action, autoescape=True))
    if outcome:
        filters.append(AuditEvent.outcome == outcome)

    total = await db.scalar(select(func.count(AuditEvent.id)).where(*filters))
    rows = await db.scalars(
        select(AuditEvent)
        .where(*filters)
        .order_by(AuditEvent.at.desc(), AuditEvent.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    return Page(
        items=[
            AuditEventRead.model_validate(
                {
                    "id": row.id,
                    "at": ensure_utc(row.at),
                    "actorType": row.actor_type,
                    "actorId": row.actor_id,
                    "actorName": row.actor_name,
                    "action": row.action,
                    "targetType": row.target_type,
                    "targetId": row.target_id,
                    "outcome": row.outcome,
                    "detail": row.detail or {},
                }
            )
            for row in rows
        ],
        total=int(total or 0),
        limit=page.limit,
        offset=page.offset,
    )
