"""The model gateway: the only way anything in AgentHub reaches a language model.

For every request it:

1. resolves the agent's tier to a configured ``provider:model`` route;
2. refuses when that provider has no credentials;
3. enforces this organization's request rate and daily token budget;
4. calls the provider through its adapter;
5. writes a usage row - tokens, estimated cost, outcome - whatever happened.

It never logs a prompt, an answer or a key. Credentials are read from settings
here and handed to the SDK; nothing else in the platform can see them, and they
are never placed in a sandbox or sent to the browser.
"""

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from datetime import time as clock_time

from opentelemetry.trace import SpanKind
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.rate_limit import SlidingWindowLimiter
from app.core.time import now_utc
from app.db.models.usage import ModelUsage
from app.llm.errors import ModelError
from app.llm.pricing import cost_microusd
from app.llm.providers import ModelProvider
from app.llm.routing import Route, route_for, routes
from app.llm.types import Message, ModelRequest, ModelResponse, ToolSpec
from app.observability import tracing
from app.observability.metrics import MODEL_COST, MODEL_DURATION, MODEL_REQUESTS, MODEL_TOKENS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GatewayResult:
    response: ModelResponse
    route: Route
    #: Estimated, in micro-dollars. None when the model that answered is not priced.
    cost_microusd: int | None


def start_of_day(moment: datetime) -> datetime:
    return datetime.combine(moment.date(), clock_time.min, tzinfo=moment.tzinfo)


class ModelGateway:
    def __init__(self, settings: Settings, providers: dict[str, ModelProvider]) -> None:
        self.settings = settings
        self.providers = providers
        self.limiter = SlidingWindowLimiter(
            limit=settings.model_requests_per_minute_per_org, window_seconds=60
        )

    # --- what is possible --------------------------------------------------

    def configured(self, provider: str) -> bool:
        return provider in self.providers

    def route(self, tier: str) -> Route | None:
        return route_for(self.settings, tier)

    def available_for(self, tier: str) -> bool:
        route = self.route(tier)
        return route is not None and self.configured(route.provider)

    def all_routes(self) -> dict[str, Route]:
        return routes(self.settings)

    async def tokens_used_today(self, session: AsyncSession, organization_id: str) -> int:
        since = start_of_day(now_utc())
        used = await session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        ModelUsage.input_tokens
                        + ModelUsage.output_tokens
                        + ModelUsage.cache_read_tokens
                        + ModelUsage.cache_write_tokens
                    ),
                    0,
                )
            ).where(ModelUsage.organization_id == organization_id, ModelUsage.at >= since)
        )
        return int(used or 0)

    async def cost_today(self, session: AsyncSession, organization_id: str) -> int:
        since = start_of_day(now_utc())
        cost = await session.scalar(
            select(func.coalesce(func.sum(ModelUsage.cost_microusd), 0)).where(
                ModelUsage.organization_id == organization_id, ModelUsage.at >= since
            )
        )
        return int(cost or 0)

    # --- the call ----------------------------------------------------------

    async def complete(
        self,
        session: AsyncSession,
        *,
        organization_id: str,
        execution_id: str | None,
        tier: str,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        max_output_tokens: int,
    ) -> GatewayResult:
        route = self.route(tier)
        if route is None:
            raise ModelError("not_configured", f"No model route is configured for {tier}.")
        provider = self.providers.get(route.provider)
        if provider is None:
            raise ModelError(
                "not_configured", f"The {route.provider} provider has no credentials configured."
            )

        if not self.limiter.check(organization_id):
            await self._record(session, organization_id, execution_id, route, "rate_limited")
            raise ModelError(
                "rate_limited",
                "This organization reached its limit of "
                f"{self.settings.model_requests_per_minute_per_org} model requests per minute.",
                retryable=True,
            )

        used = await self.tokens_used_today(session, organization_id)
        if used >= self.settings.model_daily_token_limit_per_org:
            await self._record(session, organization_id, execution_id, route, "budget_exhausted")
            raise ModelError(
                "budget_exhausted",
                "This organization used its daily model budget of "
                f"{self.settings.model_daily_token_limit_per_org} tokens.",
            )

        self.limiter.record(organization_id)
        # Copies: the request is a snapshot, not a view of a conversation that
        # keeps growing after it is sent.
        request = ModelRequest(
            model=route.model,
            system=system,
            messages=list(messages),
            tools=list(tools),
            max_output_tokens=max_output_tokens,
        )
        started = time.monotonic()
        try:
            with tracing.span(
                "model.complete",
                {
                    "gen_ai.system": route.provider,
                    "gen_ai.request.model": route.model,
                    "agenthub.tier": tier,
                },
                kind=SpanKind.CLIENT,
            ):
                response = await provider.complete(request)
        except ModelError as error:
            await self._record(
                session, organization_id, execution_id, route, error.kind, started=started
            )
            MODEL_REQUESTS.labels(
                provider=route.provider, model=route.model, outcome=error.kind
            ).inc()
            logger.warning(
                "model request failed",
                extra={"provider": route.provider, "model": route.model, "kind": error.kind},
            )
            raise

        elapsed = time.monotonic() - started
        cost = cost_microusd(route.provider, response.served_by, response.usage)
        served = response.served_by
        MODEL_REQUESTS.labels(
            provider=route.provider,
            model=served,
            outcome="refused" if response.stop == "refusal" else "ok",
        ).inc()
        MODEL_DURATION.labels(provider=route.provider, model=served).observe(elapsed)
        for kind, count in (
            ("input", response.usage.input_tokens),
            ("output", response.usage.output_tokens),
            ("cache_read", response.usage.cache_read_tokens),
            ("cache_write", response.usage.cache_write_tokens),
        ):
            if count:
                MODEL_TOKENS.labels(provider=route.provider, model=served, kind=kind).inc(count)
        if cost:
            MODEL_COST.labels(provider=route.provider, model=served).inc(cost)
        await self._record(
            session,
            organization_id,
            execution_id,
            route,
            "refused" if response.stop == "refusal" else "ok",
            response=response,
            cost=cost,
            started=started,
        )
        logger.info(
            "model request",
            extra={
                "provider": route.provider,
                "model": response.served_by,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "stop": response.stop,
            },
        )
        return GatewayResult(response=response, route=route, cost_microusd=cost)

    async def _record(
        self,
        session: AsyncSession,
        organization_id: str,
        execution_id: str | None,
        route: Route,
        outcome: str,
        *,
        response: ModelResponse | None = None,
        cost: int | None = None,
        started: float | None = None,
    ) -> None:
        usage = response.usage if response is not None else None
        session.add(
            ModelUsage(
                id=f"use_{uuid.uuid4().hex[:12]}",
                organization_id=organization_id,
                execution_id=execution_id,
                at=now_utc(),
                tier=route.tier,
                provider=route.provider,
                requested_model=route.model,
                served_model=response.served_by if response is not None else None,
                outcome=outcome,
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                cache_read_tokens=usage.cache_read_tokens if usage else 0,
                cache_write_tokens=usage.cache_write_tokens if usage else 0,
                cost_microusd=cost,
                duration_ms=int((time.monotonic() - started) * 1000) if started else 0,
                request_id=response.request_id if response is not None else None,
            )
        )
        await session.flush()


# --- choosing the gateway ----------------------------------------------------

_override: ModelGateway | None = None
_cache: dict[str, ModelGateway] = {}


def _fingerprint(settings: Settings) -> str:
    """Identifies a configuration without keeping a readable copy of any key."""
    parts = [
        settings.model_route_fast_small,
        settings.model_route_balanced_large,
        settings.model_route_reasoning_large,
        str(settings.model_request_timeout_seconds),
        str(settings.model_requests_per_minute_per_org),
        str(settings.model_daily_token_limit_per_org),
        str(settings.models_enabled),
    ]
    for secret in (settings.anthropic_api_key, settings.openai_api_key):
        parts.append(secret.get_secret_value() if secret is not None else "")
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def build_gateway(settings: Settings) -> ModelGateway:
    providers: dict[str, ModelProvider] = {}
    if settings.models_enabled:
        timeout = float(settings.model_request_timeout_seconds)
        if settings.anthropic_api_key is not None:
            from app.llm.providers.claude import ClaudeProvider

            providers["anthropic"] = ClaudeProvider(
                settings.anthropic_api_key.get_secret_value(), timeout_seconds=timeout
            )
        if settings.openai_api_key is not None:
            from app.llm.providers.openai_chat import OpenAIChatProvider

            providers["openai"] = OpenAIChatProvider(
                settings.openai_api_key.get_secret_value(), timeout_seconds=timeout
            )
    return ModelGateway(settings, providers)


def get_gateway(settings: Settings) -> ModelGateway:
    """One gateway per configuration per process, so SDK clients are reused."""
    if _override is not None:
        return _override
    key = _fingerprint(settings)
    gateway = _cache.get(key)
    if gateway is None:
        gateway = build_gateway(settings)
        _cache[key] = gateway
    return gateway


def use_gateway(gateway: ModelGateway | None) -> None:
    """Substitutes the gateway. Tests use this; nothing else should."""
    global _override
    _override = gateway
