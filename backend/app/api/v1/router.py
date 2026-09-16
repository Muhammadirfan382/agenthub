from fastapi import APIRouter

from app.api.v1 import agents, auth, executions, health, members

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(agents.router)
api_router.include_router(executions.router)
api_router.include_router(members.router)
