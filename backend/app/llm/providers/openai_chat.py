"""OpenAI models, through the official OpenAI Python SDK (Chat Completions).

No OpenAI model is routed by default: a deployment names one explicitly
(``MODEL_ROUTE_*=openai:<model>``), so this code never guesses which models an
account can use. No temperature is sent, for the same reason as the Claude
adapter: reasoning models reject it, and one agent setting should not mean
different things on different routes.

Tool arguments arrive as a JSON string. One that does not parse to an object is
marked malformed and refused by the tool gateway, never repaired.
"""

import json
from typing import Any

import openai
from openai import AsyncOpenAI

from app.llm.errors import ModelError
from app.llm.types import Message, ModelRequest, ModelResponse, StopReason, ToolCall, Usage

NAME = "openai"
#: Pinned, so an ambient OPENAI_BASE_URL can never redirect prompts or the key.
API_URL = "https://api.openai.com/v1"

_STOP_REASONS: dict[str, StopReason] = {
    "stop": "end",
    "tool_calls": "tool_calls",
    "length": "max_tokens",
    "content_filter": "refusal",
}


def to_wire_messages(system: str, messages: list[Message]) -> list[dict[str, Any]]:
    wire: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for message in messages:
        if message.role == "user":
            for result in message.tool_results:
                content = f"Error: {result.content}" if result.is_error else result.content
                wire.append({"role": "tool", "tool_call_id": result.call_id, "content": content})
            if message.text or not message.tool_results:
                wire.append({"role": "user", "content": message.text})
            continue

        entry: dict[str, Any] = {"role": "assistant", "content": message.text or None}
        if message.tool_calls:
            entry["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                }
                for call in message.tool_calls
            ]
        wire.append(entry)
    return wire


def build_params(request: ModelRequest) -> dict[str, Any]:
    params: dict[str, Any] = {
        "model": request.model,
        "messages": to_wire_messages(request.system, request.messages),
        "max_completion_tokens": request.max_output_tokens,
    }
    if request.tools:
        params["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in request.tools
        ]
    return params


def _tool_call(raw: Any) -> ToolCall:
    function = getattr(raw, "function", None)
    if getattr(raw, "type", None) != "function" or function is None:
        # A custom or unknown tool call shape: nothing the gateway offered.
        return ToolCall(
            id=str(getattr(raw, "id", "")), name="(unsupported)", arguments={}, malformed=True
        )
    try:
        arguments = json.loads(function.arguments or "{}")
    except json.JSONDecodeError:
        arguments = None
    return ToolCall(
        id=str(raw.id),
        name=str(function.name),
        arguments=arguments if isinstance(arguments, dict) else {},
        malformed=not isinstance(arguments, dict),
    )


def from_wire_completion(completion: Any) -> ModelResponse:
    choice = completion.choices[0]
    message = choice.message
    stop: StopReason = _STOP_REASONS.get(str(choice.finish_reason), "other")
    refusal = getattr(message, "refusal", None)
    if refusal:
        stop = "refusal"

    usage = completion.usage
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    details = getattr(usage, "prompt_tokens_details", None)
    cached = int(getattr(details, "cached_tokens", 0) or 0) if details is not None else 0

    return ModelResponse(
        message=Message(
            role="assistant",
            text=str(message.content or ""),
            tool_calls=[_tool_call(call) for call in (message.tool_calls or [])],
        ),
        stop=stop,
        usage=Usage(
            input_tokens=max(prompt - cached, 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            cache_read_tokens=cached,
        ),
        served_by=str(completion.model),
        request_id=getattr(completion, "_request_id", None),
        refusal_detail=str(refusal) if refusal else None,
    )


def translate_error(error: Exception) -> ModelError:
    if isinstance(error, openai.AuthenticationError | openai.PermissionDeniedError):
        return ModelError("authentication", "OpenAI rejected the configured credentials.")
    if isinstance(error, openai.RateLimitError):
        return ModelError("rate_limited", "OpenAI is rate limiting requests.", retryable=True)
    if isinstance(error, openai.BadRequestError | openai.NotFoundError):
        status = getattr(error, "status_code", "4xx")
        return ModelError("bad_request", f"OpenAI refused the request as invalid ({status}).")
    if isinstance(error, openai.APITimeoutError):
        return ModelError("unavailable", "OpenAI did not answer in time.", retryable=True)
    if isinstance(error, openai.APIConnectionError):
        return ModelError("unavailable", "OpenAI could not be reached.", retryable=True)
    if isinstance(error, openai.APIStatusError):
        code = int(getattr(error, "status_code", 500) or 500)
        return ModelError(
            "unavailable", f"OpenAI failed to answer ({code}).", retryable=code >= 500
        )
    return ModelError("unavailable", "The OpenAI request failed unexpectedly.")


class OpenAIChatProvider:
    """Talks to the OpenAI Chat Completions API."""

    name = NAME

    def __init__(self, api_key: str, *, timeout_seconds: float, max_retries: int = 2) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key, base_url=API_URL, timeout=timeout_seconds, max_retries=max_retries
        )
        # The SDK also reads OPENAI_ORG_ID, OPENAI_PROJECT_ID and OPENAI_ADMIN_KEY
        # from the environment. None of them was configured for AgentHub, so
        # none of them is used: the headers are built from these on each request.
        self._client.organization = None
        self._client.project = None
        self._client.admin_api_key = None

    async def complete(self, request: ModelRequest) -> ModelResponse:
        try:
            completion = await self._client.chat.completions.create(**build_params(request))
        except openai.APIError as error:
            raise translate_error(error) from None
        return from_wire_completion(completion)
