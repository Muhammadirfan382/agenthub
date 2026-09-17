"""Organization-wide runtime controls.

One switch, deliberately blunt: when it is on, nothing new starts and anything
running is asked to stop. Any administrator can engage it; only the owner can
release it.
"""

from fastapi import APIRouter

from app.api.deps import AuthDep
from app.core.time import ensure_utc
from app.db.models import Organization
from app.db.session import SessionDep
from app.schemas.execution import KillSwitchRead, KillSwitchUpdate
from app.services import runtime_service

router = APIRouter(prefix="/organization", tags=["organization"])


def _read(organization: Organization, pending_approvals: int) -> KillSwitchRead:
    return KillSwitchRead.model_validate(
        {
            "executionsPaused": organization.executions_paused,
            "pausedAt": ensure_utc(organization.executions_paused_at)
            if organization.executions_paused_at
            else None,
            "pausedBy": organization.executions_paused_by,
            "reason": organization.executions_paused_reason,
            "pendingApprovals": pending_approvals,
        }
    )


@router.get("/runtime", response_model=KillSwitchRead, summary="Runtime state")
async def get_runtime(session: SessionDep, auth: AuthDep) -> KillSwitchRead:
    organization = await runtime_service.get_organization_runtime(session, context=auth)
    pending = await runtime_service.pending_approval_count(session, auth.organization_id)
    return _read(organization, pending)


@router.patch(
    "/runtime",
    response_model=KillSwitchRead,
    summary="Engage or release the kill switch",
    description="Engaging stops every execution in the organization and blocks new ones.",
)
async def set_runtime(session: SessionDep, auth: AuthDep, body: KillSwitchUpdate) -> KillSwitchRead:
    organization = await runtime_service.set_kill_switch(
        session, paused=body.executions_paused, reason=body.reason, context=auth
    )
    pending = await runtime_service.pending_approval_count(session, auth.organization_id)
    return _read(organization, pending)
