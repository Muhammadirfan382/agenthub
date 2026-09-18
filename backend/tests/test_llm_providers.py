"""The provider adapters: what they send, and how they read what comes back.

Responses are built from each SDK's own types, and the SDK client is replaced by
a recorder, so nothing here touches a network - but the translation code under
test is exactly what runs against the real APIs.
"""

import asyncio
from typing import Any

import anthropic
import httpx2
import openai
import pytest
from anthropic.types import Message as ClaudeMessage
from anthropic.types.beta import BetaMessage
from openai.types.chat import ChatCompletion

from app.llm.errors import ModelError
from app.llm.providers import claude, openai_chat
from app.llm.types import Message, ModelRequest, ToolCall, ToolResult, ToolSpec

TOOL = ToolSpec(
    name="web_search",
    description="Search the public web.",
    input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
)


def request(*messages: Message, model: str = "claude-sonnet-5") -> ModelRequest:
    return ModelRequest(
        model=model,
        system="You are a test agent.",
        messages=list(messages) or [Message(role="user", text="Hello")],
        tools=[TOOL],
        max_output_tokens=1024,
    )


def claude_message(**overrides: Any) -> Any:
    payload: dict[str, Any] = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5",
        "content": [{"type": "text", "text": "Hello."}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    payload.update(overrides)
    return ClaudeMessage.model_validate(payload)


def completion(**message: Any) -> Any:
    finish = message.pop("finish_reason", "stop")
    usage = message.pop("usage", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    return ChatCompletion.model_validate(
        {
            "id": "chatcmpl_1",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-test",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": finish,
                    "message": {"role": "assistant", "content": None, **message},
                }
            ],
            "usage": usage,
        }
    )


def http_response(status: int) -> httpx2.Response:
    return httpx2.Response(status, request=httpx2.Request("POST", "https://api.example.test"))


# --- Claude ------------------------------------------------------------------


class TestClaudeRequests:
    def test_no_sampling_parameters_are_sent(self) -> None:
        params = claude.build_params(request())

        assert "temperature" not in params
        assert "top_p" not in params

    def test_the_stable_prefix_is_cached(self) -> None:
        assert claude.build_params(request())["cache_control"] == {"type": "ephemeral"}

    def test_tools_use_the_messages_api_shape(self) -> None:
        tools = claude.build_params(request())["tools"]

        assert tools == [
            {
                "name": "web_search",
                "description": "Search the public web.",
                "input_schema": TOOL.input_schema,
            }
        ]

    def test_tool_results_go_back_as_one_user_turn(self) -> None:
        results = Message(
            role="user",
            tool_results=[
                ToolResult(call_id="t1", content="Not executed", is_error=True),
                ToolResult(call_id="t2", content="Not executed", is_error=True),
            ],
        )

        wire = claude.to_wire_messages([results])

        assert wire == [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": "Not executed",
                        "is_error": True,
                    },
                    {
                        "type": "tool_result",
                        "tool_use_id": "t2",
                        "content": "Not executed",
                        "is_error": True,
                    },
                ],
            }
        ]

    def test_an_assistant_turn_is_replayed_exactly_as_claude_wrote_it(self) -> None:
        native = [
            {"type": "thinking", "thinking": "", "signature": "sig"},
            {"type": "tool_use", "id": "t1", "name": "web_search", "input": {"query": "x"}},
        ]
        turn = Message(role="assistant", text="ignored", native=native)

        assert claude.to_wire_messages([turn]) == [{"role": "assistant", "content": native}]


class TestClaudeResponses:
    def test_text_and_usage_are_read(self) -> None:
        response = claude.from_wire_message(
            claude_message(
                usage={
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "cache_read_input_tokens": 100,
                    "cache_creation_input_tokens": 7,
                }
            )
        )

        assert response.stop == "end"
        assert response.message.text == "Hello."
        assert (response.usage.cache_read_tokens, response.usage.cache_write_tokens) == (100, 7)

    def test_tool_calls_are_read_as_requests(self) -> None:
        response = claude.from_wire_message(
            claude_message(
                stop_reason="tool_use",
                content=[
                    {"type": "text", "text": "Let me look."},
                    {"type": "tool_use", "id": "t1", "name": "web_search", "input": {"query": "x"}},
                ],
            )
        )

        assert response.stop == "tool_calls"
        assert response.message.tool_calls == [
            ToolCall(id="t1", name="web_search", arguments={"query": "x"})
        ]

    def test_a_refusal_is_recognised_with_its_reason(self) -> None:
        response = claude.from_wire_message(
            claude_message(
                stop_reason="refusal",
                content=[],
                stop_details={"type": "refusal", "category": "cyber", "explanation": "declined"},
            )
        )

        assert response.stop == "refusal"
        assert response.refusal_detail == "cyber, declined"

    def test_an_unknown_stop_reason_is_not_mistaken_for_success(self) -> None:
        response = claude.from_wire_message(claude_message(stop_reason="pause_turn"))

        assert response.stop == "other"

    def test_the_model_that_answered_is_recorded(self) -> None:
        response = claude.from_wire_message(claude_message(model="claude-opus-4-8"))

        assert response.served_by == "claude-opus-4-8"


class TestFallbackEcho:
    """What may be sent back after Claude fell back to another model mid-answer."""

    def test_model_internal_blocks_before_the_boundary_are_dropped(self) -> None:
        blocks: list[dict[str, Any]] = [
            {"type": "thinking", "thinking": "", "signature": "a"},
            {"type": "text", "text": "Partial "},
            {"type": "tool_use", "id": "t0", "name": "web_search", "input": {}},
            {"type": "fallback", "from": {"model": "x"}, "to": {"model": "y"}},
            {"type": "thinking", "thinking": "", "signature": "b"},
            {"type": "text", "text": "answer."},
        ]

        kept = claude.echoable_content(blocks)

        assert kept == [
            {"type": "text", "text": "Partial "},
            {"type": "thinking", "thinking": "", "signature": "b"},
            {"type": "text", "text": "answer."},
        ]

    def test_a_turn_without_a_fallback_is_echoed_whole(self) -> None:
        blocks: list[dict[str, Any]] = [
            {"type": "thinking", "thinking": "", "signature": "a"},
            {"type": "tool_use", "id": "t0", "name": "web_search", "input": {}},
        ]

        assert claude.echoable_content(blocks) == blocks

    def test_a_dropped_tool_call_is_not_acted_on(self) -> None:
        # Opus 5 requests go through the beta API, whose messages carry the
        # fallback block. A tool call from the model that declined is not the answer.
        message = BetaMessage.model_validate(
            {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "claude-opus-4-8",
                "content": [
                    {"type": "tool_use", "id": "t0", "name": "web_search", "input": {"q": "x"}},
                    {
                        "type": "fallback",
                        "from": {"model": "claude-opus-5"},
                        "to": {"model": "claude-opus-4-8"},
                        "trigger": {"type": "refusal", "category": "cyber"},
                    },
                    {"type": "text", "text": "Done."},
                ],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )

        response = claude.from_wire_message(message)

        assert response.message.tool_calls == []
        assert response.message.text == "Done."
        assert response.served_by == "claude-opus-4-8"
        assert response.message.native == [{"type": "text", "text": "Done."}]


class _Stream:
    def __init__(self, message: Any, calls: list[dict[str, Any]], **kwargs: Any) -> None:
        calls.append(kwargs)
        self.message = message

    async def __aenter__(self) -> "_Stream":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get_final_message(self) -> Any:
        return self.message


class _RecordingClaudeClient:
    """Stands in for AsyncAnthropic: records each stream() call's arguments."""

    def __init__(self, reply: Any = None, error: Exception | None = None) -> None:
        self.plain: list[dict[str, Any]] = []
        self.beta_calls: list[dict[str, Any]] = []
        reply = reply if reply is not None else claude_message()

        def stream(calls: list[dict[str, Any]]) -> Any:
            def open_stream(**kwargs: Any) -> _Stream:
                if error is not None:
                    raise error
                return _Stream(reply, calls, **kwargs)

            return open_stream

        self.messages = type("Messages", (), {"stream": staticmethod(stream(self.plain))})()
        beta_messages = type("Messages", (), {"stream": staticmethod(stream(self.beta_calls))})()
        self.beta = type("Beta", (), {"messages": beta_messages})()


def claude_provider(client: _RecordingClaudeClient) -> claude.ClaudeProvider:
    provider = claude.ClaudeProvider("placeholder-not-a-key", timeout_seconds=5)
    provider._client = client  # type: ignore[assignment]
    return provider


class TestClaudeCalls:
    def test_opus_5_opts_into_server_side_refusal_fallback(self) -> None:
        client = _RecordingClaudeClient()

        asyncio.run(claude_provider(client).complete(request(model="claude-opus-5")))

        assert client.plain == []
        assert client.beta_calls[0]["fallbacks"] == "default"
        assert client.beta_calls[0]["betas"] == ["server-side-fallback-2026-07-01"]

    @pytest.mark.parametrize("model", ["claude-sonnet-5", "claude-haiku-4-5"])
    def test_other_models_use_the_plain_messages_api(self, model: str) -> None:
        client = _RecordingClaudeClient()

        asyncio.run(claude_provider(client).complete(request(model=model)))

        assert client.beta_calls == []
        assert client.plain[0]["model"] == model

    @pytest.mark.parametrize(
        ("error", "kind", "retryable"),
        [
            (anthropic.AuthenticationError("x", response=http_response(401), body=None),
             "authentication", False),
            (anthropic.RateLimitError("x", response=http_response(429), body=None),
             "rate_limited", True),
            (anthropic.BadRequestError("x", response=http_response(400), body=None),
             "bad_request", False),
            (anthropic.InternalServerError("x", response=http_response(500), body=None),
             "unavailable", True),
            (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://a.test")),
             "unavailable", True),
            (anthropic.APITimeoutError(request=httpx2.Request("POST", "https://a.test")),
             "unavailable", True),
        ],
    )  # fmt: skip
    def test_sdk_errors_become_platform_errors(
        self, error: Exception, kind: str, retryable: bool
    ) -> None:
        client = _RecordingClaudeClient(error=error)

        with pytest.raises(ModelError) as raised:
            asyncio.run(claude_provider(client).complete(request()))

        assert raised.value.kind == kind
        assert raised.value.retryable is retryable
        # The SDK exception - which can carry the request - is not chained.
        assert raised.value.__cause__ is None


# --- OpenAI ------------------------------------------------------------------


class TestOpenAIRequests:
    def test_the_system_prompt_comes_first(self) -> None:
        wire = openai_chat.build_params(request())["messages"]

        assert wire[0] == {"role": "system", "content": "You are a test agent."}

    def test_no_sampling_parameters_are_sent_and_output_is_capped(self) -> None:
        params = openai_chat.build_params(request())

        assert "temperature" not in params
        assert params["max_completion_tokens"] == 1024

    def test_tools_use_the_function_shape(self) -> None:
        tools = openai_chat.build_params(request())["tools"]

        assert tools == [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the public web.",
                    "parameters": TOOL.input_schema,
                },
            }
        ]

    def test_a_tool_round_trip_uses_tool_messages(self) -> None:
        wire = openai_chat.to_wire_messages(
            "sys",
            [
                Message(role="user", text="Go."),
                Message(
                    role="assistant",
                    tool_calls=[ToolCall(id="c1", name="web_search", arguments={"query": "x"})],
                ),
                Message(
                    role="user",
                    tool_results=[ToolResult(call_id="c1", content="Not executed", is_error=True)],
                ),
            ],
        )

        assert wire[2]["tool_calls"][0]["function"] == {
            "name": "web_search",
            "arguments": '{"query": "x"}',
        }
        assert wire[3] == {"role": "tool", "tool_call_id": "c1", "content": "Error: Not executed"}
        assert len(wire) == 4


class TestOpenAIResponses:
    def test_text_and_cached_tokens_are_read(self) -> None:
        response = openai_chat.from_wire_completion(
            completion(
                content="Hello.",
                usage={
                    "prompt_tokens": 110,
                    "completion_tokens": 5,
                    "total_tokens": 115,
                    "prompt_tokens_details": {"cached_tokens": 100},
                },
            )
        )

        assert response.message.text == "Hello."
        assert (response.usage.input_tokens, response.usage.cache_read_tokens) == (10, 100)

    def test_tool_call_arguments_are_parsed(self) -> None:
        response = openai_chat.from_wire_completion(
            completion(
                finish_reason="tool_calls",
                tool_calls=[
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "web_search", "arguments": '{"query": "x"}'},
                    }
                ],
            )
        )

        assert response.stop == "tool_calls"
        assert response.message.tool_calls == [
            ToolCall(id="c1", name="web_search", arguments={"query": "x"})
        ]

    @pytest.mark.parametrize("arguments", ["not json", "[1, 2]", '"text"'])
    def test_arguments_that_are_not_an_object_are_marked_malformed(self, arguments: str) -> None:
        response = openai_chat.from_wire_completion(
            completion(
                finish_reason="tool_calls",
                tool_calls=[
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "web_search", "arguments": arguments},
                    }
                ],
            )
        )

        assert response.message.tool_calls[0].malformed

    @pytest.mark.parametrize(
        ("fields", "stop"),
        [
            ({"refusal": "I can't help with that."}, "refusal"),
            ({"finish_reason": "content_filter", "content": ""}, "refusal"),
            ({"finish_reason": "length", "content": "cut"}, "max_tokens"),
        ],
    )
    def test_stops_are_normalised(self, fields: dict[str, Any], stop: str) -> None:
        assert openai_chat.from_wire_completion(completion(**fields)).stop == stop


class TestOpenAIErrors:
    @pytest.mark.parametrize(
        ("error", "kind"),
        [
            (openai.AuthenticationError("x", response=http_response(401), body=None),
             "authentication"),
            (openai.RateLimitError("x", response=http_response(429), body=None), "rate_limited"),
            (openai.NotFoundError("x", response=http_response(404), body=None), "bad_request"),
            (openai.InternalServerError("x", response=http_response(503), body=None),
             "unavailable"),
        ],
    )  # fmt: skip
    def test_sdk_errors_become_platform_errors(self, error: Exception, kind: str) -> None:
        assert openai_chat.translate_error(error).kind == kind
