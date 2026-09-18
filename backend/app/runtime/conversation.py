"""A model-driven run's conversation, stored on the execution between steps.

A run can pause for a person's approval, lose its worker, or be resumed by
another process, so the conversation lives in the database rather than in
memory. Besides the messages it holds the tool calls from the model's last turn
that are still being worked through, and the results gathered so far: the next
step always knows exactly where it stands.
"""

from dataclasses import dataclass, field
from typing import Any

from app.llm.types import Message, ToolCall, ToolResult

#: A conversation larger than this is refused rather than stored.
MAX_STORED_MESSAGES = 200


def _call_to_json(call: ToolCall) -> dict[str, Any]:
    return {
        "id": call.id,
        "name": call.name,
        "arguments": call.arguments,
        "malformed": call.malformed,
    }


def _call_from_json(data: dict[str, Any]) -> ToolCall:
    arguments = data.get("arguments")
    return ToolCall(
        id=str(data.get("id", "")),
        name=str(data.get("name", "")),
        arguments=arguments if isinstance(arguments, dict) else {},
        malformed=bool(data.get("malformed", False)),
    )


def _result_to_json(result: ToolResult) -> dict[str, Any]:
    return {"callId": result.call_id, "content": result.content, "isError": result.is_error}


def _result_from_json(data: dict[str, Any]) -> ToolResult:
    return ToolResult(
        call_id=str(data.get("callId", "")),
        content=str(data.get("content", "")),
        is_error=bool(data.get("isError", False)),
    )


def message_to_json(message: Message) -> dict[str, Any]:
    return {
        "role": message.role,
        "text": message.text,
        "toolCalls": [_call_to_json(call) for call in message.tool_calls],
        "toolResults": [_result_to_json(result) for result in message.tool_results],
        "native": message.native,
    }


def message_from_json(data: dict[str, Any]) -> Message:
    role = data.get("role")
    return Message(
        role="assistant" if role == "assistant" else "user",
        text=str(data.get("text", "")),
        tool_calls=[_call_from_json(item) for item in data.get("toolCalls") or []],
        tool_results=[_result_from_json(item) for item in data.get("toolResults") or []],
        native=data.get("native"),
    )


@dataclass
class Conversation:
    messages: list[Message] = field(default_factory=list)
    #: Tool calls from the model's last turn not yet dealt with, in order.
    pending: list[ToolCall] = field(default_factory=list)
    #: Results for this round's tool calls, sent back together once all are done.
    results: list[ToolResult] = field(default_factory=list)
    turns: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "messages": [message_to_json(message) for message in self.messages],
            "pending": [_call_to_json(call) for call in self.pending],
            "results": [_result_to_json(result) for result in self.results],
            "turns": self.turns,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any] | None) -> "Conversation":
        if not data:
            return cls()
        return cls(
            messages=[message_from_json(item) for item in data.get("messages") or []],
            pending=[_call_from_json(item) for item in data.get("pending") or []],
            results=[_result_from_json(item) for item in data.get("results") or []],
            turns=int(data.get("turns", 0)),
        )
