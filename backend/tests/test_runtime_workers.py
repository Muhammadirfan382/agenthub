"""The split deployment: a worker that can do things the API process cannot.

In production the API holds no provider keys and no container runtime; the
worker holds both. These tests check the API reports what the runtime can do
from the worker's reports, ignores a worker that has gone quiet, and never
reveals which host a worker runs on.
"""

import asyncio
import socket
import urllib.error
import urllib.request
from datetime import timedelta
from typing import Any, cast

import pytest
from sqlalchemy import select

from app.core.time import now_utc
from app.db.models import RuntimeWorker
from app.llm.gateway import ModelGateway, use_gateway
from app.observability.worker_metrics import authorized, serve
from app.runtime import workers
from tests.conftest import Harness, runtime_settings

WORKER = "worker-host.internal:4242:abc123"


def add_worker(harness: Harness, *, seen_ago: timedelta = timedelta(), **values: Any) -> None:
    async def insert() -> None:
        async with harness.session_factory() as session:
            now = now_utc()
            session.add(
                RuntimeWorker(
                    id=WORKER,
                    version="0.10.0",
                    started_at=now - seen_ago,
                    seen_at=now - seen_ago,
                    sandbox_available=values.get("sandbox_available", True),
                    providers=values.get("providers", ["anthropic"]),
                    live_tiers=values.get(
                        "live_tiers", ["fast-small", "balanced-large", "reasoning-large"]
                    ),
                )
            )
            await session.commit()

    asyncio.run(insert())


def components(client: Any) -> dict[str, dict[str, str]]:
    body = client.get("/api/v1/system/status").json()
    return {component["id"]: component for component in body["components"]}


class TestTheApiSpeaksForTheWorker:
    def test_a_reporting_worker_s_capabilities_show_in_status(self, harness: Harness) -> None:
        add_worker(harness)

        status = components(harness.sign_in("viewer"))

        assert status["models"]["state"] == "operational"
        assert status["sandbox"]["state"] == "operational"
        assert status["runtime"]["state"] == "operational"

    def test_the_model_settings_screen_counts_the_worker_s_providers(
        self, harness: Harness
    ) -> None:
        add_worker(harness, live_tiers=["fast-small"])

        body = harness.sign_in("viewer").get("/api/v1/organization/models").json()

        assert {p["name"]: p["configured"] for p in body["providers"]}["anthropic"] is True
        available = {route["tier"]: route["available"] for route in body["routes"]}
        assert available == {
            "fast-small": True,
            "balanced-large": False,
            "reasoning-large": False,
        }

    def test_the_sandbox_screen_counts_the_worker_s_runtime(self, harness: Harness) -> None:
        add_worker(harness)

        body = harness.sign_in("viewer").get("/api/v1/organization/sandbox").json()

        assert body["available"] is True
        assert "worker" in body["detail"]

    def test_a_worker_that_went_quiet_no_longer_counts(self, harness: Harness) -> None:
        add_worker(harness, seen_ago=timedelta(seconds=workers.FRESH_SECONDS + 60))

        status = components(harness.sign_in("viewer"))

        assert status["models"]["state"] == "degraded"
        assert status["sandbox"]["state"] == "degraded"

    def test_a_worker_s_host_name_is_never_returned(self, harness: Harness) -> None:
        add_worker(harness)
        client = harness.sign_in("admin")

        for path in ("/system/status", "/organization/models", "/organization/sandbox"):
            assert "worker-host" not in client.get(f"/api/v1{path}").text


class TestReporting:
    def test_a_worker_records_its_providers_but_never_its_keys(self, harness: Harness) -> None:
        settings = runtime_settings(anthropic_api_key="not-a-real-key", sandbox_enabled=False)
        # A provider is configured; it is never called, so a stand-in will do.
        use_gateway(ModelGateway(settings, providers={"anthropic": cast(Any, object())}))

        async def run() -> RuntimeWorker | None:
            async with harness.session_factory() as session:
                await workers.report(session, settings, worker=WORKER, started_at=now_utc())
                await session.commit()
            async with harness.session_factory() as session:
                return await session.get(RuntimeWorker, WORKER)

        row = asyncio.run(run())

        assert row is not None
        assert row.providers == ["anthropic"]
        assert row.sandbox_available is False
        assert "not-a-real-key" not in repr(vars(row))

    def test_long_gone_workers_are_forgotten(self, harness: Harness) -> None:
        add_worker(harness, seen_ago=timedelta(days=2))
        settings = runtime_settings(sandbox_enabled=False)

        async def run() -> list[str]:
            async with harness.session_factory() as session:
                await workers.report(session, settings, worker="fresh:1:x", started_at=now_utc())
                await session.commit()
                rows = await session.scalars(select(RuntimeWorker))
                return [row.id for row in rows]

        assert asyncio.run(run()) == ["fresh:1:x"]


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def fetch(url: str, token: str | None = None) -> tuple[int, str]:
    request = urllib.request.Request(url)  # noqa: S310 - a loopback http URL built here
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - loopback
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, ""


class TestWorkerMetricsEndpoint:
    def test_it_is_off_unless_a_port_is_set(self) -> None:
        assert serve(runtime_settings()) is None

    def test_it_serves_the_registry_behind_the_token(self) -> None:
        port = free_port()
        server = serve(runtime_settings(worker_metrics_port=port, metrics_token="a-scrape-token"))
        assert server is not None
        try:
            base = f"http://127.0.0.1:{port}"
            assert fetch(f"{base}/metrics")[0] == 403
            assert fetch(f"{base}/metrics", "wrong-token")[0] == 403
            status, body = fetch(f"{base}/metrics", "a-scrape-token")
            assert status == 200
            assert "agenthub_build_info" in body
            assert fetch(f"{base}/anything-else", "a-scrape-token")[0] == 404
        finally:
            server.shutdown()
            server.server_close()

    def test_a_port_in_use_does_not_stop_the_worker(self) -> None:
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", 0))
            taken.listen()
            port = taken.getsockname()[1]

            assert serve(runtime_settings(worker_metrics_port=port)) is None

    @pytest.mark.parametrize(
        ("header", "token", "allowed"),
        [
            (None, None, True),
            (None, "t", False),
            ("Bearer t", "t", True),
            ("Bearer x", "t", False),
            ("t", "t", True),
        ],
    )
    def test_the_token_check(self, header: str | None, token: str | None, allowed: bool) -> None:
        assert authorized(header, token) is allowed
