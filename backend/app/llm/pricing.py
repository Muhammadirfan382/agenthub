"""What a model call cost, in micro-dollars (millionths of a US dollar).

Prices are Anthropic's published first-party rates per million tokens as of
2026-06. They are an estimate for budgeting and display, not an invoice: the
provider's bill is authoritative, and prices change. A model with no entry -
every OpenAI model, deliberately, because this code does not guess prices -
is recorded with an unknown cost rather than a made-up one.

Cache writes are priced at 1.25x input (five-minute cache) and cache reads at
0.1x input, per Anthropic's pricing.
"""

from app.llm.types import Usage

#: (provider, model) -> (input, output) in US dollars per million tokens.
PRICES_PER_MILLION: dict[tuple[str, str], tuple[float, float]] = {
    ("anthropic", "claude-fable-5-1"): (10.00, 50.00),
    ("anthropic", "claude-opus-5"): (5.00, 25.00),
    ("anthropic", "claude-opus-4-8"): (5.00, 25.00),
    ("anthropic", "claude-sonnet-5"): (2.00, 10.00),
    ("anthropic", "claude-haiku-4-5"): (1.00, 5.00),
}

CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10


def cost_microusd(provider: str, model: str, usage: Usage) -> int | None:
    """The estimated cost of one request, or None when the model is not priced."""
    price = PRICES_PER_MILLION.get((provider, model))
    if price is None:
        return None
    input_price, output_price = price
    # Dollars per million tokens is exactly micro-dollars per token.
    total = (
        usage.input_tokens * input_price
        + usage.output_tokens * output_price
        + usage.cache_write_tokens * input_price * CACHE_WRITE_MULTIPLIER
        + usage.cache_read_tokens * input_price * CACHE_READ_MULTIPLIER
    )
    return round(total)
