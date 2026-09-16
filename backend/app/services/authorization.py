"""The permission matrix.

Every authorization decision in the API goes through `require`, so the rules
are readable in one place instead of being spread across route handlers.

Roles are ordered: viewer < member < admin < owner. A role includes everything
the roles below it can do.
"""

from typing import Literal

from app.core.errors import ForbiddenError
from app.schemas.enums import ROLE_RANK, Role

Action = Literal[
    "agent:read",
    "agent:create",
    "agent:update",
    "agent:delete",
    "agent:execute",
    "execution:read",
    "member:read",
    "member:manage",
    "organization:manage",
]

#: The lowest role that may perform each action on any resource in the organization.
MINIMUM_ROLE: dict[Action, Role] = {
    "agent:read": "viewer",
    "execution:read": "viewer",
    "member:read": "viewer",
    "agent:create": "member",
    "agent:update": "admin",
    "agent:delete": "admin",
    "agent:execute": "admin",
    "member:manage": "admin",
    "organization:manage": "owner",
}

#: Actions a member may also perform on an agent they own.
OWNER_ACTIONS: frozenset[Action] = frozenset({"agent:update", "agent:delete", "agent:execute"})

_MESSAGES: dict[Action, str] = {
    "agent:create": "Your role does not allow creating agents.",
    "agent:update": "You can only change agents you own.",
    "agent:delete": "You can only delete agents you own.",
    "agent:execute": "You can only run agents you own.",
    "member:manage": "Only administrators and owners can manage members.",
    "organization:manage": "Only the organization owner can do this.",
}


def has_role(role: Role, minimum: Role) -> bool:
    return ROLE_RANK[role] >= ROLE_RANK[minimum]


def can(role: Role, action: Action, *, owns_resource: bool = False) -> bool:
    """`owns_resource` lets a member act on their own agent, and nothing else."""
    if has_role(role, MINIMUM_ROLE[action]):
        return True
    if owns_resource and action in OWNER_ACTIONS:
        return has_role(role, "member")
    return False


def require(role: Role, action: Action, *, owns_resource: bool = False) -> None:
    if not can(role, action, owns_resource=owns_resource):
        raise ForbiddenError(_MESSAGES.get(action, "You do not have permission to do this."))


def require_assignable_role(actor_role: Role, target_role: Role) -> None:
    """Nobody may grant a role above their own, and only an owner creates owners."""
    if target_role == "owner" and actor_role != "owner":
        raise ForbiddenError("Only the organization owner can grant the owner role.")
    if not has_role(actor_role, target_role):
        raise ForbiddenError("You cannot grant a role above your own.")


def require_can_manage_member(actor_role: Role, target_role: Role) -> None:
    """Administrators manage everyone except owners; owners manage everyone."""
    if target_role == "owner" and actor_role != "owner":
        raise ForbiddenError("Only the organization owner can change another owner.")
