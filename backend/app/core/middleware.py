"""Request context and response hardening."""

import hashlib
import re
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import SESSION_COOKIE
from app.core.logging import request_id_var
from app.core.rate_limit import SlidingWindowLimiter

REQUEST_ID_HEADER = "X-Request-ID"
# Only accept a client-supplied id that is safe to echo into headers and logs.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    # API responses carry workspace data; never store them in shared caches.
    "Cache-Control": "no-store",
    # The API returns JSON, never a document: nothing in a response may load,
    # run, frame or submit anything.
    "Content-Security-Policy": (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
#: Development-only interactive docs load their UI from a CDN; the strict policy
#: above would blank them. They do not exist outside ENVIRONMENT=development.
DOCS_PATHS = ("/api/docs", "/api/redoc")
HSTS = "max-age=63072000; includeSubDomains"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, hsts: bool = False) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.hsts = hsts

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        docs = request.url.path.startswith(DOCS_PATHS)
        for header, value in SECURITY_HEADERS.items():
            if docs and header == "Content-Security-Policy":
                continue
            response.headers.setdefault(header, value)
        if self.hsts:
            # Production only: over plain http in development it would pin the
            # browser to https for a host that does not serve it.
            response.headers.setdefault("Strict-Transport-Security", HSTS)
        return response


class WriteRateLimitMiddleware(BaseHTTPMiddleware):
    """Bounds state-changing requests per client: a runaway script, not a login.

    Keyed by a fingerprint of the session cookie when there is one (never the
    cookie itself), otherwise by client address. Per process, like sign-in
    throttling: a multi-process deployment needs a shared store.
    """

    def __init__(self, app: object, *, limit: int, window_seconds: int = 60) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.limiter = SlidingWindowLimiter(limit=limit, window_seconds=window_seconds)

    @staticmethod
    def _key(request: Request) -> str:
        cookie = request.cookies.get(SESSION_COOKIE, "")
        if cookie:
            return "s:" + hashlib.sha256(cookie.encode()).hexdigest()[:32]
        return "a:" + (request.client.host if request.client else "unknown")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method not in UNSAFE_METHODS:
            return await call_next(request)
        key = self._key(request)
        if not self.limiter.check(key):
            retry = self.limiter.retry_after_seconds(key)
            return JSONResponse(
                status_code=429,
                content={
                    "code": "rate_limited",
                    "message": "Too many changes in a short time. Try again shortly.",
                },
                headers={"Retry-After": str(retry)},
            )
        self.limiter.record(key)
        return await call_next(request)
