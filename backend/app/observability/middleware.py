"""Measuring and tracing every HTTP request.

The span is named after the **route template** (`/api/v1/agents/{agent_id}`),
never the path, so neither traces nor metrics grow a new series per id. The
trace id is returned in `X-Trace-Id`, so a report of "this request failed" can
be followed without asking the reporter for anything else.
"""

import time
from collections.abc import Awaitable, Callable

from opentelemetry.trace import Span, SpanKind
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import API_V1_PREFIX
from app.observability import tracing
from app.observability.metrics import HTTP_DURATION, HTTP_REQUESTS, status_class

#: The scrape endpoint does not measure itself.
IGNORED_PATHS = ("/api/v1/metrics",)
UNMATCHED = "unmatched"
TRACE_HEADER = "X-Trace-Id"


def route_template(request: Request) -> str:
    """The matched route's full template, or `unmatched` - never a raw path.

    Routers included under the API prefix report their templates without it
    (`/health` for `/api/v1/health`), so it is put back when the request came
    in under that prefix.
    """
    route = request.scope.get("route")
    template = str(getattr(route, "path", "") or "")
    if not template:
        return UNMATCHED
    if request.url.path.startswith(API_V1_PREFIX) and not template.startswith(API_V1_PREFIX):
        template = API_V1_PREFIX + template
    return template


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in IGNORED_PATHS:
            return await call_next(request)

        started = time.perf_counter()
        # Continue the caller's trace when it sent one, rather than starting a new one.
        with (
            tracing.continued_from(request.headers),
            tracing.span(f"{request.method} {UNMATCHED}", kind=SpanKind.SERVER) as span,
        ):
            status_code = 500
            try:
                response = await call_next(request)
                status_code = response.status_code
            finally:
                # Recorded even when the handler raised: a 500 is a measurement too.
                self._record(request, span, status_code, time.perf_counter() - started)

            trace_id, _ = tracing.current_ids()
            if trace_id != "-":
                response.headers.setdefault(TRACE_HEADER, trace_id)
            return response

    @staticmethod
    def _record(request: Request, span: Span, status_code: int, elapsed: float) -> None:
        template = route_template(request)
        span.update_name(f"{request.method} {template}")
        span.set_attribute("http.request.method", request.method)
        span.set_attribute("http.route", template)
        span.set_attribute("http.response.status_code", status_code)
        HTTP_REQUESTS.labels(
            method=request.method, route=template, status=status_class(status_code)
        ).inc()
        HTTP_DURATION.labels(method=request.method, route=template).observe(elapsed)
