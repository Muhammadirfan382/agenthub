"""The audit log: who did what, to what, and what the platform decided.

It records security-relevant decisions - sign-ins, membership and role changes,
the kill switch, approvals, agent and installation changes, policy refusals and
every request that left the server - so that "who allowed this?" has an answer.

Rules this module keeps:

* **Append only.** Nothing in the platform updates or deletes an audit event.
* **No secrets, no content.** Details are small, bounded and key-filtered: a
  password, token, key or cookie is dropped even if a caller passes one. Prompts,
  model answers and fetched content are never recorded here.
* **Not optional.** Security decisions are recorded whatever an agent's
  ``auditLogging`` flag says; the flag cannot switch the platform's own record off.
"""

import re
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import now_utc
from app.db.models.audit import AuditEvent

if TYPE_CHECKING:
    from app.db.models import Agent
    from app.services.auth_service import AuthContext

ActorType = Literal["user", "agent", "system"]
Outcome = Literal["success", "failure", "denied", "allowed"]

MAX_DETAIL_STRING = 300
MAX_DETAIL_KEYS = 20
_SENSITIVE = re.compile(r"pass|secret|token|api_?key|authorization|cookie|credential", re.I)


@dataclass(frozen=True)
class Actor:
    type: ActorType
    id: str | None
    name: str


SYSTEM = Actor("system", None, "AgentHub")


def user_actor(context: "AuthContext") -> Actor:
    return Actor("user", context.user_id, context.user.name)


def agent_actor(agent: "Agent") -> Actor:
    return Actor("agent", agent.id, agent.name)


def _clean(value: Any, depth: int = 0) -> Any:
    if isinstance(value, str):
        return value if len(value) <= MAX_DETAIL_STRING else value[: MAX_DETAIL_STRING - 1] + "…"
    if isinstance(value, bool | int | float) or value is None:
        return value
    if isinstance(value, dict) and depth < 2:
        return {
            str(key)[:64]: _clean(item, depth + 1)
            for key, item in list(value.items())[:MAX_DETAIL_KEYS]
            if not _SENSITIVE.search(str(key))
        }
    if isinstance(value, list | tuple) and depth < 2:
        return [_clean(item, depth + 1) for item in list(value)[:MAX_DETAIL_KEYS]]
    return str(value)[:MAX_DETAIL_STRING]


async def record(
    session: AsyncSession,
    *,
    organization_id: str,
    action: str,
    actor: Actor,
    outcome: Outcome = "success",
    target: tuple[str, str] | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    """Appends one event. Flushed with the caller's transaction, never on its own."""
    event = AuditEvent(
        id=f"aud_{uuid.uuid4().hex[:16]}",
        organization_id=organization_id,
        at=now_utc(),
        actor_type=actor.type,
        actor_id=actor.id,
        actor_name=actor.name[:120],
        action=action[:64],
        target_type=target[0][:32] if target else None,
        target_id=target[1][:64] if target else None,
        outcome=outcome,
        detail=_clean(detail or {}),
    )
    session.add(event)
    await session.flush()
    return event
