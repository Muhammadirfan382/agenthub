"""Throttling for sign-in attempts.

Two limits: one per email address, so guessing one account's password is slow,
and one per client address, so a single host cannot spray many accounts. Both
are per process — see app/core/rate_limit.py.

The client address comes from the connection. Forwarded headers are not trusted
because nothing has been configured as a trusted proxy; treating them as the
client would let anyone reset their own limit by changing a header.
"""

from starlette.requests import Request

from app.core.config import Settings
from app.core.errors import RateLimitedError
from app.core.rate_limit import SlidingWindowLimiter

TOO_MANY_ATTEMPTS = "Too many sign-in attempts. Please wait before trying again."


def client_address(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class LoginGuard:
    def __init__(self, settings: Settings) -> None:
        window = settings.login_window_minutes * 60
        self.by_account = SlidingWindowLimiter(settings.login_max_attempts, window)
        self.by_address = SlidingWindowLimiter(settings.login_max_attempts_per_ip, window)

    def check(self, *, email: str, address: str) -> None:
        for key, limiter in ((email.lower(), self.by_account), (address, self.by_address)):
            if not limiter.check(key):
                raise RateLimitedError(TOO_MANY_ATTEMPTS, limiter.retry_after_seconds(key))

    def record_failure(self, *, email: str, address: str) -> None:
        self.by_account.record(email.lower())
        self.by_address.record(address)

    def record_success(self, *, email: str) -> None:
        """A correct password clears that account's failures, not the address's."""
        self.by_account.reset(email.lower())

    def clear(self) -> None:
        self.by_account.clear()
        self.by_address.clear()
