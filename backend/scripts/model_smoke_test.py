"""Checks that each configured model route really answers. Costs a few cents.

    python -m scripts.model_smoke_test --yes

For every tier whose provider has credentials, it sends two small requests
straight through that provider's adapter: one plain reply, and one that should
make the model ask for a tool (which is then not run, as everywhere else).
It prints the route, the model that answered, the stop reason and the tokens -
never a key, a header or a full response.

It deliberately skips the usage ledger and the per-organization limits: it
checks the adapters and credentials, not the platform around them. Nothing is
written to the database.
"""

import argparse
import asyncio
import sys

from app.core.config import get_settings
from app.llm.errors import ModelError
from app.llm.gateway import build_gateway
from app.llm.pricing import cost_microusd
from app.llm.types import Message, ModelRequest, ModelResponse, ToolSpec
from app.runtime.tools import TOOL_DEFINITIONS

PLAIN = "Reply with exactly: OK"
TOOLING = "Use the web_search tool to look up 'AgentHub status'. Do not answer without it."


def _describe(label: str, response: ModelResponse, provider: str) -> str:
    cost = cost_microusd(provider, response.served_by, response.usage)
    price = f"≈ ${cost / 1_000_000:.5f}" if cost is not None else "cost unknown"
    calls = ", ".join(call.name for call in response.message.tool_calls) or "none"
    return (
        f"  {label}: stop={response.stop} served_by={response.served_by} "
        f"in={response.usage.input_tokens} out={response.usage.output_tokens} "
        f"tool_calls={calls} {price}"
    )


async def main() -> int:
    settings = get_settings()
    gateway = build_gateway(settings)
    if not gateway.providers:
        print(
            "No provider has credentials (AGENTHUB_ANTHROPIC_API_KEY / "
            "AGENTHUB_OPENAI_API_KEY). Nothing to test."
        )
        return 1

    web_search = ToolSpec(
        name="web_search",
        description=TOOL_DEFINITIONS["web_search"].description,
        input_schema=TOOL_DEFINITIONS["web_search"].schema.model_json_schema(),
    )
    failures = 0
    for tier, route in gateway.all_routes().items():
        provider = gateway.providers.get(route.provider)
        if provider is None:
            print(f"{tier} -> {route}: skipped, {route.provider} has no credentials")
            continue
        print(f"{tier} -> {route}")
        for label, prompt, tools in (("plain", PLAIN, []), ("tool", TOOLING, [web_search])):
            request = ModelRequest(
                model=route.model,
                system="You are a connectivity check for AgentHub.",
                messages=[Message(role="user", text=prompt)],
                tools=tools,
                max_output_tokens=512,
            )
            try:
                response = await provider.complete(request)
            except ModelError as error:
                failures += 1
                print(f"  {label}: FAILED ({error.kind}) {error.message}")
                continue
            print(_describe(label, response, route.provider))
            if label == "tool" and not response.message.tool_calls:
                print("  note: the model answered without asking for the tool")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--yes", action="store_true", help="Confirm that real, billed calls are OK."
    )
    if not parser.parse_args().yes:
        print("This sends real, billed requests. Re-run with --yes to confirm.")
        sys.exit(2)
    sys.exit(asyncio.run(main()))
