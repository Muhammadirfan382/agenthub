"""Removing secrets and personal data from anything on its way to a log.

Logs are read by more people, kept longer and copied more often than any other
output, so this runs over every message and every structured field. It is a
safety net, not permission to log carelessly: code should not put a secret in a
log line in the first place.

What is removed:

* provider and platform keys by shape (``sk-ant-``, ``sk-``, ``ghp_``, ``AKIA``);
* the value after a secret-ish name (``api_key=``, ``authorization: ...``,
  ``password``, ``token``, ``cookie``, ``secret``);
* ``Bearer``/``Basic`` credentials;
* email addresses, which are personal data;
* query-string values, which carry tokens far more often than anyone expects.

Each match becomes a marker naming what was removed, so a reader can tell the
difference between "nothing was there" and "something was taken out".
"""

import re

REDACTED = "[redacted]"

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Credentials by shape, before anything else can partially match them.
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{6,}"), "[redacted-key]"),
    (re.compile(r"\bsk-[A-Za-z0-9]{16,}"), "[redacted-key]"),
    (re.compile(r"\bghp_[A-Za-z0-9]{16,}"), "[redacted-key]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[redacted-key]"),
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"), r"\1 [redacted]"),
    # A secret-ish name followed by its value, in text or JSON-ish output.
    (
        re.compile(
            r"(?i)\b(api[_-]?key|authorization|password|passwd|secret|token|cookie)"
            r"(\"?\s*[=:]\s*\"?)([^\s,;\"}]{3,})"
        ),
        r"\1\2[redacted]",
    ),
    # Personal data: never in a log.
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[redacted-email]"),
    # Query-string values: ?token=..., &key=...
    (re.compile(r"([?&][A-Za-z0-9_.-]{1,40}=)([^&\s\"]+)"), r"\1[redacted]"),
)


def redact(text: str) -> str:
    """The text with anything secret-shaped or personal replaced by a marker."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_value(value: object, depth: int = 0) -> object:
    """`redact` for a structured field: strings inside dicts and lists too."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict) and depth < 3:
        return {key: redact_value(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list | tuple) and depth < 3:
        return [redact_value(item, depth + 1) for item in value]
    return value
