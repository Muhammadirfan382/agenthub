from fastapi import APIRouter

from app.api.v1 import agents, executions, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(agents.router)
api_router.include_router(executions.router)
