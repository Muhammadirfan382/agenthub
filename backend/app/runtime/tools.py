"""The tool gateway: every tool call a model asks for passes through here.

A model's tool call is untrusted output. Before anything happens to it, the
gateway checks, in order:

1. the tool is one this agent declared **and** was offered this run (a denied
   capability is never offered, and a model naming an unoffered tool is refused);
2. the arguments were well-formed JSON and match the tool's schema exactly -
   unknown fields are rejected, not ignored;
3. the agent's grant for the tool's capability, and whether a person must
   approve the call first.

What happens after that is honest about this release: **no tool is executed.**
Every tool that would need the network, the file system or a database needs the
SSRF and egress protection planned for Phase 8, so an approved call is recorded
as ``unavailable`` and the model is told plainly that nothing was done.
"""

import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.llm.types import ToolCall, ToolSpec
from app.runtime.plan import Step


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class WebSearchInput(_Input):
    query: str = Field(min_length=1, max_length=400, description="What to search for.")
    max_results: int = Field(default=5, ge=1, le=10)


class DocumentReaderInput(_Input):
    document_id: str = Field(
        min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$", description="Document id."
    )


class SqlReadonlyInput(_Input):
    query: str = Field(min_length=1, max_length=4000, description="A single read-only query.")


class ApiRequestInput(_Input):
    method: Literal["GET", "POST"]
    url: str = Field(min_length=1, max_length=2000, description="An https URL.")
    body: str | None = Field(default=None, max_length=8000)


class CodeSandboxInput(_Input):
    language: Literal["python"]
    code: str = Field(min_length=1, max_length=20_000)


class EmailDraftInput(_Input):
    to: list[str] = Field(min_length=1, max_length=10)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)


class ChartPoint(_Input):
    label: str = Field(min_length=1, max_length=100)
    value: float


class ChartRendererInput(_Input):
    chart_type: Literal["bar", "line", "pie"]
    title: str = Field(min_length=1, max_length=200)
    points: list[ChartPoint] = Field(min_length=1, max_length=100)


@dataclass(frozen=True)
class ToolDefinition:
    description: str
    schema: type[_Input]


#: Every tool in the catalog, what it would do, and what it accepts.
TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    "web_search": ToolDefinition("Search the public web.", WebSearchInput),
    "document_reader": ToolDefinition("Read a document by its id.", DocumentReaderInput),
    "sql_readonly": ToolDefinition("Run one read-only SQL query.", SqlReadonlyInput),
    "api_request": ToolDefinition("Call an allow-listed HTTPS API.", ApiRequestInput),
    "code_sandbox": ToolDefinition("Run Python code in an isolated sandbox.", CodeSandboxInput),
    "email_draft": ToolDefinition("Draft an email for a person to review.", EmailDraftInput),
    "chart_renderer": ToolDefinition("Render a simple chart.", ChartRendererInput),
}

NOT_EXECUTED = (
    "Not executed: {tool} has no implementation in this AgentHub release, so no action "
    "was taken and there is no result. Do not assume one; continue without it or say "
    "what you would need."
)

DecisionKind = Literal["refused", "invalid", "allowed"]


@dataclass(frozen=True)
class Decision:
    kind: DecisionKind
    #: What the model is told when the call does not go ahead.
    message: str
    policy: Step | None = None
    arguments: dict[str, Any] | None = None


def offered_tools(policies: dict[str, Step]) -> list[ToolSpec]:
    """The tools the model may see: declared, in the catalog, and not denied."""
    specs: list[ToolSpec] = []
    for tool, policy in sorted(policies.items()):
        definition = TOOL_DEFINITIONS.get(tool)
        if definition is None or policy.capability is None or policy.level == "denied":
            continue
        specs.append(
            ToolSpec(
                name=tool,
                description=definition.description,
                input_schema=definition.schema.model_json_schema(),
            )
        )
    return specs


def _validation_summary(error: ValidationError) -> str:
    problems = []
    for issue in error.errors()[:5]:
        where = ".".join(str(part) for part in issue.get("loc", ())) or "arguments"
        problems.append(f"{where}: {issue.get('msg', 'invalid')}")
    return "; ".join(problems)


def evaluate(call: ToolCall, policies: dict[str, Step]) -> Decision:
    """Decides whether a model's tool call may go ahead. Never runs anything."""
    policy = policies.get(call.name)
    definition = TOOL_DEFINITIONS.get(call.name)
    if (
        policy is None
        or definition is None
        or policy.capability is None
        or policy.level == "denied"
    ):
        return Decision(
            "refused",
            f"Refused: {call.name!r} is not a tool this agent may use.",
            policy=policy,
        )

    if call.malformed:
        return Decision("invalid", "Invalid arguments: they were not a JSON object.", policy=policy)

    try:
        validated = definition.schema.model_validate(call.arguments)
    except ValidationError as error:
        return Decision(
            "invalid", f"Invalid arguments: {_validation_summary(error)}.", policy=policy
        )

    return Decision("allowed", "", policy=policy, arguments=validated.model_dump(mode="json"))


def summarise_arguments(arguments: dict[str, Any], limit: int = 500) -> str:
    """A bounded, printable record of what the model asked for. Stored, never run."""
    text = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= limit else text[: limit - 1] + "…"
