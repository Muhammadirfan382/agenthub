"""What the runtime says to a model, and what it gets back, in no provider's dialect.

Every provider adapter translates to and from these types, so the runtime,
the tool gateway and the stored conversation never depend on one vendor's
wire format.

One escape hatch exists: `Message.native`. Some providers require an assistant
turn to be sent back exactly as they produced it (Anthropic's thinking blocks
carry signatures, for instance). The adapter that produced a turn may stash its
own wire form there and replay it verbatim; every other reader ignores it.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["user", "assistant"]

#: Why the model stopped, normalised across providers.
#:
#: * ``end`` - it finished its answer.
#: * ``tool_calls`` - it wants one or more tools used before it continues.
#: * ``max_tokens`` - it ran out of output budget mid-answer.
#: * ``refusal`` - the provider's safety system declined the request.
#: * ``other`` - anything the adapter did not recognise. Treated as a stop.
StopReason = Literal["end", "tool_calls", "max_tokens", "refusal", "other"]


@dataclass(frozen=True)
class ToolCall:
    """A tool the model asked for. Its arguments are untrusted model output."""

    id: str
    name: str
    arguments: dict[str, Any]
    #: Set when the provider sent arguments that were not a JSON object. The
    #: call is then refused rather than guessed at.
    malformed: bool = False


@dataclass(frozen=True)
class ToolResult:
    """What the platform told the model about one of its tool calls."""

    call_id: str
    content: str
    is_error: bool = False


@dataclass
class Message:
    role: Role
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    #: The producing adapter's own wire form of this turn, for faithful replay.
    native: Any = None


@dataclass(frozen=True)
class ToolSpec:
    """A tool offered to the model: its name, what it is for, and its input schema."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ModelRequest:
    model: str
    system: str
    messages: list[Message]
    tools: list[ToolSpec]
    max_output_tokens: int


@dataclass(frozen=True)
class Usage:
    """Tokens one request consumed, as the provider reported them."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )


@dataclass(frozen=True)
class ModelResponse:
    message: Message
    stop: StopReason
    usage: Usage
    #: The model that actually answered. It can differ from the one asked for
    #: when a provider falls back to another model server-side.
    served_by: str
    #: The provider's own request id, for support tickets. Never a secret.
    request_id: str | None = None
    #: A short, provider-supplied reason when `stop` is `refusal`.
    refusal_detail: str | None = None
