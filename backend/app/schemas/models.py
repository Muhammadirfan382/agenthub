"""What the model gateway can do here. Never includes a credential."""

from app.schemas.common import CamelModel


class ProviderStatus(CamelModel):
    name: str
    #: True when credentials are configured. The credentials themselves are never returned.
    configured: bool


class RouteStatus(CamelModel):
    tier: str
    provider: str
    model: str
    #: True when this tier would be answered by a real model right now.
    available: bool


class ModelLimits(CamelModel):
    requests_per_minute: int
    daily_token_limit: int
    max_turns: int
    timeout_seconds: int


class ModelUsageToday(CamelModel):
    requests: int
    tokens: int
    #: Estimated from published prices; null for providers without a price table.
    estimated_cost_usd: float


class ModelGatewayStatus(CamelModel):
    enabled: bool
    providers: list[ProviderStatus]
    routes: list[RouteStatus]
    limits: ModelLimits
    usage_today: ModelUsageToday
    detail: str
