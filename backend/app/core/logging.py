"""Structured logging: one JSON object per line, correlated and redacted.

Every line carries the request id and, when there is a span, the trace and span
ids - so a log line, a trace and an audit event can be lined up afterwards.
Fields passed as `extra=` are included, which is what makes these logs worth
querying.

Everything written here - the message and every field - goes through
`app.observability.redaction` first. Never log credentials, tokens, whole
request bodies, prompts, model output or personal data; the redaction is a
safety net under that rule, not a replacement for it.
"""

import json
import logging
from contextvars import ContextVar
from typing import Any

from opentelemetry import trace

from app.observability.redaction import redact, redact_value

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

#: Everything the standard library puts on a record; anything else is a field
#: the caller added with `extra=`.
_STANDARD = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


def _trace_ids() -> tuple[str, str]:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return "-", "-"
    return f"{span_context.trace_id:032x}", f"{span_context.span_id:016x}"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        trace_id, span_id = _trace_ids()
        payload: dict[str, Any] = {
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": redact(record.getMessage()),
            "request_id": request_id_var.get(),
            "trace_id": trace_id,
            "span_id": span_id,
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith("_"):
                payload[key] = redact_value(value)
        if record.exc_info:
            # The last line only: a stack trace in a log line is noise, and the
            # lines above it can quote request data.
            payload["error"] = redact(self.formatException(record.exc_info).splitlines()[-1])
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
