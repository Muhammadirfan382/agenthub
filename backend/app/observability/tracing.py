"""Tracing: one thread through a request, its run, and every gateway it reaches.

OpenTelemetry, configured in one place. Spans are always created, so their ids
can be written into every log line and a log can be matched to the work that
produced it. They are only **exported** when `OTEL_EXPORTER_OTLP_ENDPOINT` names
a collector; with none configured nothing leaves the process and nothing is
kept.

Incoming `traceparent` headers are honoured, so a request that arrives from
another service continues that trace rather than starting a new one.

Attributes follow the same rule as metrics: counts, names and outcomes - never
a prompt, an answer, a URL's query string, or anything personal.
"""

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import context, propagate, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

from app.core.config import Settings

logger = logging.getLogger(__name__)

SERVICE_NAME = "agenthub-backend"
_configured = False


def configure_tracing(settings: Settings) -> None:
    """Sets up tracing once per process. Safe to call again."""
    global _configured
    if _configured:
        return
    _configured = True

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": SERVICE_NAME,
                "service.version": settings.service_version,
                "deployment.environment": settings.environment,
            }
        )
    )
    endpoint = settings.otlp_endpoint.strip()
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
            logger.info("tracing exports to a collector", extra={"otlp_endpoint": endpoint})
        except Exception:  # a broken collector must never stop the application
            logger.exception("could not set up the OTLP exporter; tracing stays local")
    trace.set_tracer_provider(provider)


def tracer() -> trace.Tracer:
    return trace.get_tracer(SERVICE_NAME)


def current_ids() -> tuple[str, str]:
    """The current trace and span ids as hex, or `-` when there is no span."""
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return "-", "-"
    return f"{span_context.trace_id:032x}", f"{span_context.span_id:016x}"


@contextmanager
def span(
    name: str,
    attributes: Mapping[str, Any] | None = None,
    *,
    kind: SpanKind = SpanKind.INTERNAL,
) -> Iterator[Span]:
    """One span, ended whatever happens, marked failed if something is raised."""
    with tracer().start_as_current_span(name, kind=kind) as current:
        for key, value in (attributes or {}).items():
            if value is not None:
                current.set_attribute(key, value)
        try:
            yield current
        except Exception as error:
            current.set_status(Status(StatusCode.ERROR, type(error).__name__))
            raise


@contextmanager
def continued_from(headers: Mapping[str, str]) -> Iterator[None]:
    """Continues the trace an incoming request carries, if it carries one."""
    token = context.attach(propagate.extract(headers))
    try:
        yield
    finally:
        context.detach(token)
