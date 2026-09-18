"""Which real model answers for each tier an agent can choose.

Agents never name a vendor model. They pick a tier - ``fast-small``,
``balanced-large`` or ``reasoning-large`` - and the deployment decides what
that means, through ``MODEL_ROUTE_*`` settings of the form ``provider:model``.
Changing a route changes every agent on that tier, without touching any agent.
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.core.config import Settings

ProviderName = Literal["anthropic", "openai"]
PROVIDERS: tuple[ProviderName, ...] = ("anthropic", "openai")

#: provider, a colon, then a model id with no spaces, slashes or shell-ish characters.
ROUTE_PATTERN = r"^(anthropic|openai):[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_ROUTE = re.compile(ROUTE_PATTERN)


@dataclass(frozen=True)
class Route:
    tier: str
    provider: ProviderName
    model: str

    def __str__(self) -> str:
        return f"{self.provider}:{self.model}"


def parse_route(tier: str, value: str) -> Route:
    if not _ROUTE.match(value):
        raise ValueError(f"Route for {tier} must look like provider:model, not {value!r}.")
    provider, model = value.split(":", 1)
    return Route(tier=tier, provider=provider, model=model)  # type: ignore[arg-type]


def routes(settings: "Settings") -> dict[str, Route]:
    """Every tier's route, as configured."""
    return {
        "fast-small": parse_route("fast-small", settings.model_route_fast_small),
        "balanced-large": parse_route("balanced-large", settings.model_route_balanced_large),
        "reasoning-large": parse_route("reasoning-large", settings.model_route_reasoning_large),
    }


def route_for(settings: "Settings", tier: str) -> Route | None:
    return routes(settings).get(tier)
