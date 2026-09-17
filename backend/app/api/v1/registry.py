"""Versions, the marketplace and installations.

Publishing is done from an agent (`/agents/{id}/versions`), browsing is done
from the marketplace, and installing creates a grant record owned by the
installing organization.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthDep
from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.db.models import Agent, AgentVersion
from app.db.session import SessionDep
from app.repositories import identity_repository, registry_repository
from app.schemas.agent import AgentRead
from app.schemas.enums import AgentCategory
from app.schemas.registry import (
    AgentVersionRead,
    InstallationCreate,
    InstallationDetail,
    InstallationRead,
    InstallationUpdate,
    MarketplaceListing,
    MarketplaceListingDetail,
    PublishRequest,
    VersionStatusUpdate,
    VisibilityUpdate,
)
from app.services import agent_service, authorization, registry_service
from app.services.auth_service import AuthContext
from app.services.mappers import (
    to_agent_read,
    to_installation_detail,
    to_installation_read,
    to_listing,
    to_listing_detail,
    to_version_read,
)

versions_router = APIRouter(prefix="/agents", tags=["versions"])
marketplace_router = APIRouter(prefix="/marketplace", tags=["marketplace"])
installations_router = APIRouter(prefix="/installations", tags=["installations"])


# --- versions ---------------------------------------------------------------


@versions_router.get(
    "/{agent_id}/versions", response_model=Page[AgentVersionRead], summary="List agent versions"
)
async def list_versions(
    session: SessionDep,
    auth: AuthDep,
    agent_id: str,
    page: Annotated[PageParams, Depends(page_params)],
) -> Page[AgentVersionRead]:
    await agent_service.get_agent(session, agent_id, context=auth)
    versions, total = await registry_repository.list_versions(
        session, agent_id, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[to_version_read(version) for version in versions],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@versions_router.post(
    "/{agent_id}/versions",
    response_model=AgentVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Publish the current configuration as a version",
    description="Freezes a manifest. Published versions are immutable.",
)
async def publish_version(
    session: SessionDep, auth: AuthDep, agent_id: str, body: PublishRequest
) -> AgentVersionRead:
    return to_version_read(
        await registry_service.publish_version(session, agent_id, body, context=auth)
    )


@versions_router.get(
    "/{agent_id}/versions/{version_id}", response_model=AgentVersionRead, summary="Get one version"
)
async def get_version(
    session: SessionDep, auth: AuthDep, agent_id: str, version_id: str
) -> AgentVersionRead:
    return to_version_read(
        await registry_service.get_version(session, agent_id, version_id, context=auth)
    )


@versions_router.patch(
    "/{agent_id}/versions/{version_id}",
    response_model=AgentVersionRead,
    summary="Deprecate or restore a version",
)
async def set_version_status(
    session: SessionDep, auth: AuthDep, agent_id: str, version_id: str, body: VersionStatusUpdate
) -> AgentVersionRead:
    return to_version_read(
        await registry_service.set_version_status(session, agent_id, version_id, body, context=auth)
    )


@versions_router.patch(
    "/{agent_id}/visibility",
    response_model=AgentRead,
    summary="Choose who can see this agent in the marketplace",
)
async def set_visibility(
    session: SessionDep, auth: AuthDep, agent_id: str, body: VisibilityUpdate
) -> AgentRead:
    return to_agent_read(
        await registry_service.set_visibility(session, agent_id, body.visibility, context=auth)
    )


# --- marketplace ------------------------------------------------------------


@marketplace_router.get("", response_model=Page[MarketplaceListing], summary="Browse listings")
async def list_listings(
    session: SessionDep,
    auth: AuthDep,
    page: Annotated[PageParams, Depends(page_params)],
    search: Annotated[str | None, Query(max_length=120)] = None,
    category: AgentCategory | None = None,
    tag: Annotated[str | None, Query(max_length=32)] = None,
    verified: bool = False,
) -> Page[MarketplaceListing]:
    authorization.require(auth.role, "agent:read")
    rows, total = await registry_repository.list_marketplace(
        session,
        organization_id=auth.organization_id,
        search=search,
        category=category,
        tag=tag,
        verified_only=verified,
        limit=page.limit,
        offset=page.offset,
    )
    installed = await registry_repository.installations_by_agent(
        session, auth.organization_id, [agent.id for _, agent, _ in rows]
    )
    return Page(
        items=[
            to_listing(version, agent, publisher, installed.get(agent.id), auth.organization_id)
            for version, agent, publisher in rows
        ],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@marketplace_router.get("/tags", response_model=list[str], summary="Tags used by listings")
async def list_tags(session: SessionDep, auth: AuthDep) -> list[str]:
    authorization.require(auth.role, "agent:read")
    return await registry_repository.marketplace_tags(session, organization_id=auth.organization_id)


@marketplace_router.get(
    "/{version_id}", response_model=MarketplaceListingDetail, summary="One listing"
)
async def get_listing(
    session: SessionDep, auth: AuthDep, version_id: str
) -> MarketplaceListingDetail:
    authorization.require(auth.role, "agent:read")
    version, agent = await _visible_listing(session, version_id, auth)
    publisher = await identity_repository.get_organization(session, version.organization_id)
    if publisher is None:
        raise NotFoundError("No listing with this id.")
    installation = await registry_repository.get_installation_for_agent(
        session, auth.organization_id, agent.id
    )
    return to_listing_detail(version, agent, publisher, installation, auth.organization_id)


async def _visible_listing(
    session: AsyncSession, version_id: str, auth: AuthContext
) -> tuple[AgentVersion, Agent]:
    version = await registry_repository.get_version(session, version_id)
    agent = await session.get(Agent, version.agent_id) if version else None
    if version is None or agent is None or version.status != "published":
        raise NotFoundError("No listing with this id.")

    visible = agent.visibility == "public" or (
        agent.organization_id == auth.organization_id and agent.visibility == "organization"
    )
    if not visible:
        raise NotFoundError("No listing with this id.")
    return version, agent


# --- installations ----------------------------------------------------------


async def _read(
    session: AsyncSession, installation_id: str, auth: AuthContext
) -> InstallationDetail:
    installation = await registry_service.get_installation(session, installation_id, context=auth)
    version = await registry_repository.get_version(session, installation.agent_version_id)
    if version is None:
        raise NotFoundError("The installed version no longer exists.")
    latest = await registry_repository.latest_published_version(session, installation.agent_id)
    return to_installation_detail(
        installation, version, update_available=bool(latest and latest.id != version.id)
    )


@installations_router.get(
    "", response_model=Page[InstallationRead], summary="Agents installed here"
)
async def list_installations(
    session: SessionDep, auth: AuthDep, page: Annotated[PageParams, Depends(page_params)]
) -> Page[InstallationRead]:
    authorization.require(auth.role, "installation:read")
    installations, total = await registry_repository.list_installations(
        session, auth.organization_id, limit=page.limit, offset=page.offset
    )

    items: list[InstallationRead] = []
    for installation in installations:
        version = await registry_repository.get_version(session, installation.agent_version_id)
        latest = await registry_repository.latest_published_version(session, installation.agent_id)
        items.append(
            to_installation_read(
                installation,
                version,
                update_available=bool(version and latest and latest.id != version.id),
            )
        )
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@installations_router.post(
    "",
    response_model=InstallationDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Install an agent with explicit grants",
    description="Capabilities left out of the request are denied.",
)
async def install(
    session: SessionDep, auth: AuthDep, body: InstallationCreate
) -> InstallationDetail:
    installation = await registry_service.install(session, body, context=auth)
    return await _read(session, installation.id, auth)


@installations_router.get(
    "/{installation_id}", response_model=InstallationDetail, summary="One installation"
)
async def get_installation(
    session: SessionDep, auth: AuthDep, installation_id: str
) -> InstallationDetail:
    return await _read(session, installation_id, auth)


@installations_router.patch(
    "/{installation_id}",
    response_model=InstallationDetail,
    summary="Change grants, suspend or resume",
)
async def update_installation(
    session: SessionDep, auth: AuthDep, installation_id: str, body: InstallationUpdate
) -> InstallationDetail:
    await registry_service.update_installation(session, installation_id, body, context=auth)
    return await _read(session, installation_id, auth)


@installations_router.delete(
    "/{installation_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Uninstall"
)
async def uninstall(session: SessionDep, auth: AuthDep, installation_id: str) -> Response:
    await registry_service.uninstall(session, installation_id, context=auth)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
