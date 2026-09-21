"""Logs that say enough and reveal nothing, metrics that count, traces that join up."""

import json
import logging
from typing import Any

import pytest

from app.core.config import Settings
from app.core.logging import JsonFormatter, request_id_var
from app.observability import tracing
from app.observability.metrics import HTTP_REQUESTS, REGISTRY, status_class
from app.observability.middleware import TRACE_HEADER
from app.observability.redaction import redact, redact_value
from tests.conftest import Harness, runtime_settings

# Credential-shaped test inputs are assembled at runtime, so no literal in the
# repository looks like a real key to a reader or a secret scanner.
FAKE_ANTHROPIC_KEY = "-".join(["sk", "ant", "api03", "abcdefghijklmnop"])
FAKE_OPENAI_KEY = "sk-" + "abcdefghijklmnopqrstuvwxyz012345"
FAKE_GITHUB_TOKEN = "ghp" + "_abcdefghijklmnopqrstuvwxyz"
FAKE_AWS_KEY_ID = "AKIA" + "ABCDEFGHIJKLMNOP"
FAKE_SHORT_KEY = "sk-" + "abcdefghijklmnopqrstuvwx"


def formatted(message: str, **fields: Any) -> dict[str, Any]:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, message, None, None)
    for key, value in fields.items():
        setattr(record, key, value)
    parsed: dict[str, Any] = json.loads(JsonFormatter().format(record))
    return parsed


class TestRedaction:
    @pytest.mark.parametrize(
        "secret",
        [
            FAKE_ANTHROPIC_KEY,
            FAKE_OPENAI_KEY,
            FAKE_GITHUB_TOKEN,
            FAKE_AWS_KEY_ID,
        ],
    )
    def test_credentials_are_removed_by_shape(self, secret: str) -> None:
        cleaned = redact(f"calling provider with key {secret} now")

        assert secret not in cleaned
        assert "redacted" in cleaned

    @pytest.mark.parametrize(
        "text",
        [
            "api_key=super-secret-value",
            'authorization: "Bearer abcdefghijklmnop"',
            "password: hunter2hunter2",
            "Set-Cookie: session=abcdefghijklmnop",
        ],
    )
    def test_values_after_a_secret_name_are_removed(self, text: str) -> None:
        cleaned = redact(text)

        assert "[redacted]" in cleaned
        for revealing in ("super-secret-value", "hunter2hunter2", "abcdefghijklmnop"):
            assert revealing not in cleaned

    def test_email_addresses_are_removed(self) -> None:
        assert redact("sign-in failed for person@example.com") == (
            "sign-in failed for [redacted-email]"
        )

    def test_query_string_values_are_removed(self) -> None:
        cleaned = redact("fetched https://api.example.com/v1?token=abc123&page=2")

        assert "abc123" not in cleaned
        assert "https://api.example.com/v1?token=[redacted]" in cleaned

    def test_ordinary_text_is_left_alone(self) -> None:
        message = "execution exe_123 finished with status COMPLETED in 1200ms"

        assert redact(message) == message

    def test_structured_fields_are_cleaned_too(self) -> None:
        cleaned = redact_value({"outer": {"api_key": FAKE_SHORT_KEY}, "n": 3})

        assert cleaned == {"outer": {"api_key": "[redacted-key]"}, "n": 3}


class TestLogLines:
    def test_a_line_carries_its_correlation_ids(self) -> None:
        token = request_id_var.set("req-abc")
        try:
            line = formatted("something happened")
        finally:
            request_id_var.reset(token)

        assert line["request_id"] == "req-abc"
        assert line["trace_id"] == "-"
        assert line["level"] == "info"

    def test_structured_fields_are_kept(self) -> None:
        line = formatted("model request", provider="anthropic", tokens=42)

        assert (line["provider"], line["tokens"]) == ("anthropic", 42)

    def test_a_secret_passed_as_a_field_is_still_removed(self) -> None:
        line = formatted("configured", api_key=FAKE_SHORT_KEY)

        assert line["api_key"] == "[redacted-key]"

    def test_a_line_inside_a_span_carries_the_trace(self) -> None:
        tracing.configure_tracing(runtime_settings())
        with tracing.span("test.unit"):
            line = formatted("inside a span")
            trace_id, span_id = tracing.current_ids()

        assert line["trace_id"] == trace_id != "-"
        assert line["span_id"] == span_id != "-"


class TestMetricsEndpoint:
    def test_it_answers_in_prometheus_format(self, harness: Harness) -> None:
        client = harness.app_client()
        client.get("/api/v1/health")

        response = client.get("/api/v1/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "agenthub_http_requests_total" in response.text
        assert "agenthub_build_info" in response.text

    def test_requests_are_counted_by_route_template_not_path(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        before = _counter_value("GET", "/api/v1/agents/{agent_id}", "4xx")
        client.get("/api/v1/agents/agt_does_not_exist_1")
        client.get("/api/v1/agents/agt_does_not_exist_2")

        after = _counter_value("GET", "/api/v1/agents/{agent_id}", "4xx")

        assert after == before + 2
        # The ids themselves never become labels.
        assert "agt_does_not_exist_1" not in harness.app_client().get("/api/v1/metrics").text

    def test_it_can_be_closed_with_a_token(self, harness: Harness) -> None:
        client = harness.app_client(metrics_token="a-scrape-token")

        refused = client.get("/api/v1/metrics")
        allowed = client.get("/api/v1/metrics", headers={"Authorization": "Bearer a-scrape-token"})

        assert refused.status_code == 403
        assert allowed.status_code == 200

    def test_it_can_be_switched_off(self, harness: Harness) -> None:
        assert harness.app_client(metrics_enabled=False).get("/api/v1/metrics").status_code == 404

    def test_production_refuses_to_serve_it_without_a_token(self) -> None:
        def production(**overrides: Any) -> Settings:
            return Settings(
                environment="production",
                database_url="postgresql://db/agenthub",
                _env_file=None,
                **overrides,
            )

        with pytest.raises(ValueError, match="METRICS_TOKEN"):
            production(metrics_token=None)

        assert production(metrics_token="a-scrape-token").metrics_enabled
        assert not production(metrics_token=None, metrics_enabled=False).metrics_enabled

    def test_it_carries_no_organization_or_personal_data(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        client.get("/api/v1/agents")

        body = client.get("/api/v1/metrics").text

        assert harness.workspace.organization_id not in body
        assert harness.workspace.account("admin").email not in body


def _counter_value(method: str, route: str, status: str) -> float:
    value = REGISTRY.get_sample_value(
        "agenthub_http_requests_total", {"method": method, "route": route, "status": status}
    )
    return float(value or 0)


class TestTracing:
    def test_a_response_carries_its_trace_id(self, harness: Harness) -> None:
        response = harness.app_client().get("/api/v1/health")

        assert len(response.headers[TRACE_HEADER]) == 32

    def test_an_incoming_trace_is_continued(self, harness: Harness) -> None:
        incoming = "4bf92f3577b34da6a3ce929d0e0e4736"
        response = harness.app_client().get(
            "/api/v1/health",
            headers={"traceparent": f"00-{incoming}-00f067aa0ba902b7-01"},
        )

        assert response.headers[TRACE_HEADER] == incoming

    def test_status_classes_are_bounded(self) -> None:
        assert (status_class(200), status_class(404), status_class(503)) == ("2xx", "4xx", "5xx")


class TestReadiness:
    def test_it_reports_ready_with_a_working_database(self, harness: Harness) -> None:
        response = harness.app_client().get("/api/v1/health/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert {check["name"] for check in body["checks"]} == {"database"}

    def test_it_needs_no_session(self, harness: Harness) -> None:
        assert harness.app_client().get("/api/v1/health/ready").status_code == 200

    def test_it_says_nothing_about_configuration(self, harness: Harness) -> None:
        body = harness.app_client().get("/api/v1/health/ready").text

        for revealing in ("sqlite", "database_url", "anthropic", "secret"):
            assert revealing not in body.lower()


def test_http_metrics_count_failures_too(harness: Harness) -> None:
    before = _counter_value("GET", "/api/v1/agents", "4xx")

    harness.app_client().get("/api/v1/agents")  # unauthenticated

    assert _counter_value("GET", "/api/v1/agents", "4xx") == before + 1


def test_the_counter_used_by_these_tests_exists() -> None:
    # Guards the tests themselves: a renamed metric must not silently pass.
    assert HTTP_REQUESTS._name == "agenthub_http_requests"


def test_metrics_do_not_measure_themselves(harness: Harness) -> None:
    client = harness.app_client()
    client.get("/api/v1/metrics")

    body = client.get("/api/v1/metrics").text

    assert '/api/v1/metrics"' not in body


def test_a_trace_id_is_returned_even_when_a_request_fails(harness: Harness) -> None:
    response = harness.app_client().get("/api/v1/agents")

    assert response.status_code == 401
    assert TRACE_HEADER.lower() in {key.lower() for key in response.headers}
