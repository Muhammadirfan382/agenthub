"""Test doubles for the model gateway.

`ScriptedProvider` is a stand-in model: it answers with whatever a test queued
and remembers every request it was sent. It lives in the test package on
purpose - no setting can select it, so it can never answer a real run.
"""

from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings
from app.llm.errors import ModelError
from app.llm.gateway import ModelGateway
from app.llm.types import (
    Message,
    ModelRequest,
    ModelResponse,
    StopReason,
    ToolCall,
    Usage,
)


def answer(
    text: str = "",
    *,
    stop: StopReason = "end",
    tool_calls: list[ToolCall] | None = None,
    input_tokens: int = 100,
    output_tokens: int = 20,
    served_by: str = "claude-sonnet-5",
    refusal_detail: str | None = None,
) -> ModelResponse:
    return ModelResponse(
        message=Message(role="assistant", text=text, tool_calls=list(tool_calls or [])),
        stop=stop,
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
        served_by=served_by,
        request_id="req_test",
        refusal_detail=refusal_detail,
    )


def call(name: str, arguments: dict[str, Any] | None = None, *, id: str = "call_1") -> ToolCall:
    return ToolCall(id=id, name=name, arguments=arguments or {})


@dataclass
class ScriptedProvider:
    """Answers from a queue. An empty queue is a test bug and says so."""

    replies: list[ModelResponse | ModelError] = field(default_factory=list)
    requests: list[ModelRequest] = field(default_factory=list)
    name: str = "anthropic"

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if not self.replies:
            raise AssertionError("ScriptedProvider was asked for more turns than scripted.")
        reply = self.replies.pop(0)
        if isinstance(reply, ModelError):
            raise reply
        return reply


def scripted_gateway(
    settings: Settings, *replies: ModelResponse | ModelError, provider: str = "anthropic"
) -> tuple[ModelGateway, ScriptedProvider]:
    scripted = ScriptedProvider(replies=list(replies), name=provider)
    return ModelGateway(settings, {provider: scripted}), scripted
