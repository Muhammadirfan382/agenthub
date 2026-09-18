"""Claude, through the official Anthropic Python SDK.

Choices made here, and why:

* **Streaming.** Every request streams and waits for the final message, so a
  long answer cannot hit an HTTP timeout. Nothing is shown token by token yet.
* **No temperature.** Current Claude models reject sampling parameters, so an
  agent's temperature setting is not sent. Depth is left to adaptive thinking,
  which these models apply by default.
* **Prompt caching.** The system prompt and tool list do not change within a
  run, so automatic caching makes every turn after the first cheaper.
* **Refusal fallback.** For Claude Opus 5 and Claude Fable 5.1 the request
  opts into server-side fallback (``fallbacks="default"``): when the model's
  safety system declines, Anthropic re-runs the request on its recommended
  fallback model instead of returning a refusal. The model that actually
  answered is recorded.
* **Faithful replay.** An assistant turn is sent back exactly as Claude
  produced it - thinking blocks included - except what Anthropic's rules say
  to drop after a mid-answer fallback.
"""

from typing import Any

import anthropic
from anthropic import AsyncAnthropic

from app.llm.errors import ModelError
from app.llm.types import (
    Message,
    ModelRequest,
    ModelResponse,
    StopReason,
    ToolCall,
    Usage,
)

NAME = "anthropic"
#: Pinned, so an ambient ANTHROPIC_BASE_URL can never send prompts - or the key -
#: to another host.
API_URL = "https://api.anthropic.com"

#: Models that opt into server-side refusal fallback, and the beta that gates it.
FALLBACK_MODELS = frozenset({"claude-opus-5", "claude-fable-5-1"})
FALLBACK_BETA = "server-side-fallback-2026-07-01"

#: Blocks that may not be echoed when they precede a fallback boundary. Text is
#: kept; everything model-internal before the boundary is dropped.
_DROP_BEFORE_FALLBACK = frozenset(
    {"thinking", "redacted_thinking", "tool_use", "server_tool_use", "fallback"}
)
_KNOWN_ECHOABLE = frozenset({"text", "thinking", "redacted_thinking", "tool_use"})

_STOP_REASONS: dict[str, StopReason] = {
    "end_turn": "end",
    "stop_sequence": "end",
    "tool_use": "tool_calls",
    "max_tokens": "max_tokens",
    "refusal": "refusal",
}


def echoable_content(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The part of an assistant turn that may be sent back to Claude.

    After a mid-answer fallback, model-internal blocks produced before the final
    ``fallback`` marker belong to the model that declined; only its text is
    kept. The marker itself is an audit record and is dropped.
    """
    boundary = max(
        (index for index, block in enumerate(blocks) if block.get("type") == "fallback"),
        default=-1,
    )
    kept: list[dict[str, Any]] = []
    for index, block in enumerate(blocks):
        kind = block.get("type")
        if kind == "fallback":
            continue
        if index < boundary and (kind in _DROP_BEFORE_FALLBACK or kind not in _KNOWN_ECHOABLE):
            continue
        kept.append(block)
    return kept


def _user_content(message: Message) -> str | list[dict[str, Any]]:
    if not message.tool_results:
        return message.text
    content: list[dict[str, Any]] = [
        {
            "type": "tool_result",
            "tool_use_id": result.call_id,
            "content": result.content,
            "is_error": result.is_error,
        }
        for result in message.tool_results
    ]
    if message.text:
        content.append({"type": "text", "text": message.text})
    return content


def _assistant_content(message: Message) -> list[dict[str, Any]]:
    if isinstance(message.native, list):
        return list(message.native)
    content: list[dict[str, Any]] = []
    if message.text:
        content.append({"type": "text", "text": message.text})
    for call in message.tool_calls:
        content.append(
            {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
        )
    return content


def to_wire_messages(messages: list[Message]) -> list[dict[str, Any]]:
    wire: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "user":
            wire.append({"role": "user", "content": _user_content(message)})
        else:
            wire.append({"role": "assistant", "content": _assistant_content(message)})
    return wire


def build_params(request: ModelRequest) -> dict[str, Any]:
    params: dict[str, Any] = {
        "model": request.model,
        "max_tokens": request.max_output_tokens,
        "system": request.system,
        "messages": to_wire_messages(request.messages),
        "cache_control": {"type": "ephemeral"},
    }
    if request.tools:
        params["tools"] = [
            {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
            for tool in request.tools
        ]
    return params


def from_wire_message(message: Any) -> ModelResponse:
    """Turns a Claude message into the neutral form. Reads the stop reason first."""
    stop: StopReason = _STOP_REASONS.get(str(message.stop_reason), "other")
    blocks = [block.to_dict(mode="json") for block in message.content]
    echoed = echoable_content(blocks)

    text = "".join(str(block.get("text", "")) for block in echoed if block.get("type") == "text")
    calls: list[ToolCall] = []
    for block in echoed:
        if block.get("type") != "tool_use":
            continue
        arguments = block.get("input")
        calls.append(
            ToolCall(
                id=str(block.get("id")),
                name=str(block.get("name")),
                arguments=arguments if isinstance(arguments, dict) else {},
                malformed=not isinstance(arguments, dict),
            )
        )

    refusal_detail = None
    details = getattr(message, "stop_details", None)
    if stop == "refusal" and details is not None:
        category = getattr(details, "category", None)
        explanation = getattr(details, "explanation", None)
        refusal_detail = ", ".join(str(part) for part in (category, explanation) if part) or None

    usage = message.usage
    return ModelResponse(
        message=Message(role="assistant", text=text, tool_calls=calls, native=echoed),
        stop=stop,
        usage=Usage(
            input_tokens=int(usage.input_tokens or 0),
            output_tokens=int(usage.output_tokens or 0),
            cache_read_tokens=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
            cache_write_tokens=int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
        ),
        served_by=str(message.model),
        request_id=getattr(message, "_request_id", None),
        refusal_detail=refusal_detail,
    )


def translate_error(error: Exception) -> ModelError:
    """Maps SDK exceptions to platform ones, without copying the provider's body."""
    if isinstance(error, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return ModelError("authentication", "Anthropic rejected the configured credentials.")
    if isinstance(error, anthropic.RateLimitError):
        return ModelError("rate_limited", "Anthropic is rate limiting requests.", retryable=True)
    if isinstance(error, anthropic.BadRequestError | anthropic.NotFoundError):
        status = getattr(error, "status_code", "4xx")
        return ModelError("bad_request", f"Anthropic refused the request as invalid ({status}).")
    if isinstance(error, anthropic.APITimeoutError):
        return ModelError("unavailable", "Anthropic did not answer in time.", retryable=True)
    if isinstance(error, anthropic.APIConnectionError):
        return ModelError("unavailable", "Anthropic could not be reached.", retryable=True)
    if isinstance(error, anthropic.APIStatusError):
        code = int(getattr(error, "status_code", 500) or 500)
        return ModelError(
            "unavailable", f"Anthropic failed to answer ({code}).", retryable=code >= 500
        )
    return ModelError("unavailable", "The Anthropic request failed unexpectedly.")


class ClaudeProvider:
    """Talks to the Anthropic Messages API."""

    name = NAME

    def __init__(self, api_key: str, *, timeout_seconds: float, max_retries: int = 2) -> None:
        # The key is handed to the SDK and kept nowhere else on this object. An
        # explicit key also stops the SDK reading ANTHROPIC_AUTH_TOKEN.
        self._client = AsyncAnthropic(
            api_key=api_key, base_url=API_URL, timeout=timeout_seconds, max_retries=max_retries
        )

    async def complete(self, request: ModelRequest) -> ModelResponse:
        params = build_params(request)
        try:
            if request.model in FALLBACK_MODELS:
                async with self._client.beta.messages.stream(
                    **params, betas=[FALLBACK_BETA], fallbacks="default"
                ) as stream:
                    message: Any = await stream.get_final_message()
            else:
                async with self._client.messages.stream(**params) as stream:
                    message = await stream.get_final_message()
        except anthropic.APIError as error:
            raise translate_error(error) from None
        return from_wire_message(message)
