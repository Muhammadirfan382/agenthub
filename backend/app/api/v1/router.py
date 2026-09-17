from fastapi import APIRouter

from app.api.v1 import agents, auth, executions, health, members, organization, registry

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(agents.router)
api_router.include_router(registry.versions_router)
api_router.include_router(executions.router)
api_router.include_router(members.router)
api_router.include_router(organization.router)
api_router.include_router(registry.marketplace_router)
api_router.include_router(registry.installations_router)
