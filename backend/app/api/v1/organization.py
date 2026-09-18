"""Organization-wide runtime controls.

One switch, deliberately blunt: when it is on, nothing new starts and anything
running is asked to stop. Any administrator can engage it; only the owner can
release it.
"""

import uuid

from fastapi import APIRouter

from app.api.deps import AuthDep, SettingsDep
from app.core.config import Settings
from app.core.time import ensure_utc
from app.db.models import Organization
from app.db.session import SessionDep
from app.runtime.sandbox import get_sandbox
from app.sandbox import build_spec
from app.schemas.execution import (
    KillSwitchRead,
    KillSwitchUpdate,
    SandboxCheckResult,
    SandboxStatus,
)
from app.services import authorization, runtime_service

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


def _sandbox_status(settings: Settings, *, available: bool, detail: str) -> dict[str, object]:
    return {
        "enabled": settings.sandbox_enabled,
        "available": available,
        "command": settings.sandbox_command,
        "image": settings.sandbox_image,
        "memoryMb": settings.sandbox_memory_mb,
        "cpus": settings.sandbox_cpus,
        "pidsLimit": settings.sandbox_pids_limit,
        "tmpfsMb": settings.sandbox_tmpfs_mb,
        "timeoutSeconds": settings.sandbox_timeout_seconds,
        "required": settings.require_sandbox,
        "detail": detail,
    }


@router.get("/sandbox", response_model=SandboxStatus, summary="Sandbox configuration")
async def get_sandbox_status(auth: AuthDep, settings: SettingsDep) -> SandboxStatus:
    """Reports the configuration and whether a runtime answers. Starts nothing."""
    authorization.require(auth.role, "execution:read")
    sandbox = get_sandbox(settings)
    available = await sandbox.available()
    detail = (
        "A container runtime is available."
        if available
        else f"`{settings.sandbox_command}` is not available, so runs are recorded, not isolated."
    )
    return SandboxStatus.model_validate(
        _sandbox_status(settings, available=available, detail=detail)
    )


@router.post(
    "/sandbox/check",
    response_model=SandboxCheckResult,
    summary="Start a sandbox and check what it can do",
    description="Runs one throwaway container and reports each isolation guarantee.",
)
async def check_sandbox(auth: AuthDep, settings: SettingsDep) -> SandboxCheckResult:
    # Starting containers is an administrative action, not a read.
    authorization.require(auth.role, "runtime:pause")
    sandbox = get_sandbox(settings)
    spec = build_spec(
        image=settings.sandbox_image,
        execution_id=f"check-{uuid.uuid4().hex[:8]}",
        organization_id=auth.organization_id,
        memory_mb=settings.sandbox_memory_mb,
        cpus=settings.sandbox_cpus,
        pids_limit=settings.sandbox_pids_limit,
        tmpfs_mb=settings.sandbox_tmpfs_mb,
        timeout_seconds=settings.sandbox_timeout_seconds,
    )
    result = await sandbox.probe(spec)
    detail = result.error or result.report.summary()
    payload = _sandbox_status(settings, available=result.started, detail=detail)
    payload["report"] = result.report.as_dict()
    return SandboxCheckResult.model_validate(payload)
