"""Liveness endpoint.

Reports only that the process is running. It deliberately exposes no
configuration, environment name, host details or dependency information.
"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import SERVICE_NAME, SERVICE_VERSION

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    message: str


@router.get("/health", response_model=HealthResponse, summary="Backend liveness check")
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        message="AgentHub backend is running.",
    )
