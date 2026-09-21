"""The standalone worker's own metrics endpoint.

Metrics are per process. In production the worker is a separate process, and
it is the one that counts runs, model calls, tool calls, egress, sandbox checks
and alert gauges, so it serves them itself. The API's `/api/v1/metrics` only
has what the API did.

A tiny standard-library server on a background thread: `GET /metrics` only,
the same bearer token as the API's endpoint, nothing else answered. Off unless
`WORKER_METRICS_PORT` is set. It never stops the worker: if it cannot bind, the
worker logs that and runs without it (and the scrape target shows as down).
"""

import hmac
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import Settings
from app.observability.metrics import REGISTRY

logger = logging.getLogger(__name__)

PATH = "/metrics"


def authorized(header: str | None, token: str | None) -> bool:
    """Whether a request may read metrics. No token configured means open."""
    if token is None:
        return True
    supplied = (header or "").removeprefix("Bearer ").strip()
    return hmac.compare_digest(supplied.encode(), token.encode())


def _handler(token: str | None) -> type[BaseHTTPRequestHandler]:
    class MetricsHandler(BaseHTTPRequestHandler):
        server_version = "agenthub-worker"
        sys_version = ""

        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] != PATH:
                self._answer(404, b"not found\n", "text/plain")
                return
            if not authorized(self.headers.get("Authorization"), token):
                self._answer(403, b"a valid metrics token is required\n", "text/plain")
                return
            self._answer(200, generate_latest(REGISTRY), CONTENT_TYPE_LATEST)

        def _answer(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            # Scrapes every few seconds are not worth a log line each.
            return

    return MetricsHandler


def serve(settings: Settings) -> ThreadingHTTPServer | None:
    """Starts the endpoint if configured. Returns the server, or None."""
    if not settings.metrics_enabled or not settings.worker_metrics_port:
        return None
    token = settings.metrics_token.get_secret_value() if settings.metrics_token else None
    try:
        server = ThreadingHTTPServer(
            (settings.worker_metrics_host, settings.worker_metrics_port), _handler(token)
        )
    except OSError as error:
        logger.error(
            "worker metrics endpoint could not start",
            extra={
                "host": settings.worker_metrics_host,
                "port": settings.worker_metrics_port,
                "reason": error.strerror or str(error),
            },
        )
        return None
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="worker-metrics", daemon=True).start()
    logger.info(
        "worker metrics endpoint started",
        extra={"host": settings.worker_metrics_host, "port": server.server_address[1]},
    )
    return server
