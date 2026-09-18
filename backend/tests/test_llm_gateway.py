"""Routing, pricing, building the gateway, and the tool gateway's judgement."""

from typing import Any

import pytest
from openai import Omit

from app.llm.gateway import build_gateway, get_gateway, use_gateway
from app.llm.pricing import cost_microusd
from app.llm.providers.claude import ClaudeProvider
from app.llm.providers.openai_chat import OpenAIChatProvider
from app.llm.routing import parse_route, routes
from app.llm.types import ToolCall, Usage
from app.runtime import tools as tool_gateway
from app.runtime.plan import tool_policies
from tests.conftest import runtime_settings

WEB = {
    "capability": "web_access",
    "level": "restricted",
    "scope": "docs",
    "requiresApproval": False,
}


class TestRouting:
    def test_the_default_tiers_route_to_current_claude_models(self) -> None:
        configured = {tier: str(route) for tier, route in routes(runtime_settings()).items()}

        assert configured == {
            "fast-small": "anthropic:claude-haiku-4-5",
            "balanced-large": "anthropic:claude-sonnet-5",
            "reasoning-large": "anthropic:claude-opus-5",
        }

    def test_a_route_can_name_openai(self) -> None:
        route = parse_route("balanced-large", "openai:gpt-test")

        assert (route.provider, route.model) == ("openai", "gpt-test")

    @pytest.mark.parametrize(
        "value",
        [
            "claude-opus-5",
            "mistral:large",
            "anthropic:",
            "anthropic:claude opus",
            "anthropic:../etc/passwd",
            "anthropic:-flag",
        ],
    )
    def test_a_malformed_route_is_refused(self, value: str) -> None:
        with pytest.raises(ValueError):
            parse_route("balanced-large", value)
        with pytest.raises(ValueError):
            runtime_settings(model_route_balanced_large=value)


class TestPricing:
    def test_input_output_and_cache_tokens_are_priced(self) -> None:
        usage = Usage(
            input_tokens=1_000_000,
            output_tokens=100_000,
            cache_write_tokens=1_000_000,
            cache_read_tokens=1_000_000,
        )

        # Opus 5: $5 in, $25 out; cache writes 1.25x input, reads 0.1x input.
        input_cost, output_cost, write_cost, read_cost = 5_000_000, 2_500_000, 6_250_000, 500_000
        assert cost_microusd("anthropic", "claude-opus-5", usage) == (
            input_cost + output_cost + write_cost + read_cost
        )

    def test_an_unpriced_model_has_an_unknown_cost_not_a_guess(self) -> None:
        assert cost_microusd("openai", "gpt-test", Usage(input_tokens=1000)) is None


class TestBuildingTheGateway:
    def test_without_keys_no_provider_exists(self) -> None:
        gateway = build_gateway(runtime_settings(anthropic_api_key=None, openai_api_key=None))

        assert gateway.providers == {}
        assert not gateway.available_for("balanced-large")

    def test_each_key_enables_exactly_its_provider(self) -> None:
        gateway = build_gateway(
            runtime_settings(anthropic_api_key="placeholder-a", openai_api_key="placeholder-o")
        )

        assert isinstance(gateway.providers["anthropic"], ClaudeProvider)
        assert isinstance(gateway.providers["openai"], OpenAIChatProvider)

    def test_switching_models_off_disables_every_provider(self) -> None:
        gateway = build_gateway(
            runtime_settings(models_enabled=False, anthropic_api_key="placeholder-a")
        )

        assert gateway.providers == {}

    def test_one_gateway_is_reused_per_configuration(self) -> None:
        use_gateway(None)
        settings = runtime_settings(anthropic_api_key="placeholder-a")

        assert get_gateway(settings) is get_gateway(
            runtime_settings(anthropic_api_key="placeholder-a")
        )
        assert get_gateway(settings) is not get_gateway(
            runtime_settings(anthropic_api_key="placeholder-b")
        )

    def test_a_key_never_appears_in_settings_output(self) -> None:
        settings = runtime_settings(anthropic_api_key="not-a-real-key-secret-value")

        assert "not-a-real-key-secret-value" not in repr(settings)
        assert "not-a-real-key-secret-value" not in str(settings.model_dump())


def policies(**permissions: dict[str, Any]) -> dict[str, Any]:
    return tool_policies(["web_search", "code_sandbox"], list(permissions.values()))


class TestToolGateway:
    def test_denied_and_undeclared_tools_are_not_offered(self) -> None:
        offered = tool_gateway.offered_tools(policies(web=WEB))

        assert [tool.name for tool in offered] == ["web_search"]

    def test_offered_schemas_forbid_unknown_fields(self) -> None:
        for definition in tool_gateway.TOOL_DEFINITIONS.values():
            assert definition.schema.model_json_schema()["additionalProperties"] is False

    def test_a_call_to_an_unoffered_tool_is_refused(self) -> None:
        decision = tool_gateway.evaluate(
            ToolCall(id="c", name="code_sandbox", arguments={"language": "python", "code": "1"}),
            policies(web=WEB),
        )

        assert decision.kind == "refused"

    def test_a_call_to_a_tool_that_does_not_exist_is_refused(self) -> None:
        decision = tool_gateway.evaluate(
            ToolCall(id="c", name="delete_everything", arguments={}), policies(web=WEB)
        )

        assert decision.kind == "refused"

    @pytest.mark.parametrize(
        "arguments",
        [{}, {"query": ""}, {"query": "x", "extra": 1}, {"query": "x", "max_results": 50}],
    )
    def test_arguments_outside_the_schema_are_rejected(self, arguments: dict[str, Any]) -> None:
        decision = tool_gateway.evaluate(
            ToolCall(id="c", name="web_search", arguments=arguments), policies(web=WEB)
        )

        assert decision.kind == "invalid"
        assert decision.message.startswith("Invalid arguments")

    def test_malformed_arguments_are_rejected(self) -> None:
        decision = tool_gateway.evaluate(
            ToolCall(id="c", name="web_search", arguments={}, malformed=True), policies(web=WEB)
        )

        assert decision.kind == "invalid"

    def test_valid_arguments_are_allowed_and_normalised(self) -> None:
        decision = tool_gateway.evaluate(
            ToolCall(id="c", name="web_search", arguments={"query": "  uptime  "}),
            policies(web=WEB),
        )

        assert decision.kind == "allowed"
        assert decision.arguments == {"query": "uptime", "max_results": 5}

    def test_recorded_arguments_are_bounded(self) -> None:
        summary = tool_gateway.summarise_arguments({"query": "x" * 5000})

        assert len(summary) == 500
        assert summary.endswith("…")


class TestNoAmbientCredentials:
    """A key set on the machine for other tools is never AgentHub's key."""

    def test_a_plain_provider_key_in_the_environment_is_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-anthropic-key")
        monkeypatch.setenv("OPENAI_API_KEY", "ambient-openai-key")

        settings = runtime_settings()

        assert settings.anthropic_api_key is None
        assert settings.openai_api_key is None
        assert build_gateway(settings).providers == {}

    def test_only_the_namespaced_key_is_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENTHUB_ANTHROPIC_API_KEY", "configured-for-agenthub")

        settings = runtime_settings()

        assert settings.anthropic_api_key is not None
        assert settings.anthropic_api_key.get_secret_value() == "configured-for-agenthub"

    def test_the_sdks_ignore_ambient_endpoints_and_accounts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://attacker.example.test")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://attacker.example.test/v1")
        monkeypatch.setenv("OPENAI_ORG_ID", "org-ambient")
        monkeypatch.setenv("OPENAI_PROJECT_ID", "proj-ambient")
        monkeypatch.setenv("OPENAI_ADMIN_KEY", "ambient-admin")

        claude_client = ClaudeProvider("placeholder-a", timeout_seconds=5)._client
        openai_client = OpenAIChatProvider("placeholder-o", timeout_seconds=5)._client

        assert str(claude_client.base_url).startswith("https://api.anthropic.com")
        assert str(openai_client.base_url).startswith("https://api.openai.com/v1")
        assert (openai_client.organization, openai_client.project) == (None, None)
        assert openai_client.admin_api_key is None
        # The SDK marks a header it will not send with its Omit sentinel.
        headers = openai_client.default_headers
        assert isinstance(headers.get("OpenAI-Organization", Omit()), Omit)
        assert isinstance(headers.get("OpenAI-Project", Omit()), Omit)
