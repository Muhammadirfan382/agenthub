"""The ways a model call can fail, in words the runtime can act on.

Adapters catch their SDK's own exceptions and raise one of these instead, so
nothing above the adapter ever sees a vendor exception - or the request, the
headers or the key that an SDK exception may carry in its repr.
"""

from typing import Literal

ModelErrorKind = Literal[
    #: No credentials, or the provider is switched off.
    "not_configured",
    #: The provider rejected the credentials.
    "authentication",
    #: The provider (or this platform's own limit) is throttling.
    "rate_limited",
    #: This platform's per-organization token budget is spent.
    "budget_exhausted",
    #: The request itself was invalid; retrying will not help.
    "bad_request",
    #: The provider failed or timed out.
    "unavailable",
]


class ModelError(Exception):
    """A model call that did not produce an answer."""

    def __init__(self, kind: ModelErrorKind, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.kind: ModelErrorKind = kind
        self.message = message
        self.retryable = retryable

    def __repr__(self) -> str:
        return f"ModelError({self.kind!r}, {self.message!r})"
