"""Alert rules, the operator webhook, component status and the dashboards' numbers."""

import asyncio
import json
from datetime import timedelta
from typing import Any

import httpx2
import pytest

from app.core.time import now_utc
from app.observability.alerts import evaluate_all
from app.security.egress import EgressBlocked, EgressGateway, use_egress
from tests.conftest import Harness, runtime_settings
from tests.test_runtime import active_agent, edit_execution, request_run


def evaluate(harness: Harness, **settings: Any) -> int:
    return asyncio.run(evaluate_all(harness.session_factory, runtime_settings(**settings)))


def alerts(client: Any, **params: Any) -> list[dict[str, Any]]:
    response = client.get("/api/v1/alerts", params=params)
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


def failed_runs(harness: Harness, client: Any, count: int, *, ago: timedelta = timedelta()) -> None:
    agent = active_agent(client, f"Failing Agent {count}{int(ago.total_seconds())}")
    for _ in range(count):
        execution = request_run(client, agent["id"])
        edit_execution(harness, execution["id"], status="FAILED", ended_at=now_utc() - ago)


class TestRules:
    def test_failing_runs_raise_an_alert(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        failed_runs(harness, client, 3)

        assert evaluate(harness, alert_failed_runs=3) >= 1

        firing = alerts(client, state="firing")
        assert [alert["rule"] for alert in firing] == ["runs_failing"]
        assert firing[0]["detail"]["failed"] == 3

    def test_below_the_threshold_nothing_fires(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        failed_runs(harness, client, 2)

        evaluate(harness, alert_failed_runs=3)

        assert alerts(client, state="firing") == []

    def test_a_rule_that_keeps_matching_updates_one_alert(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        failed_runs(harness, client, 3)

        evaluate(harness, alert_failed_runs=3)
        evaluate(harness, alert_failed_runs=3)

        firing = alerts(client, state="firing")
        assert len(firing) == 1
        assert firing[0]["occurrences"] == 2

    def test_a_rule_that_stops_matching_resolves(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        failed_runs(harness, client, 3)
        evaluate(harness, alert_failed_runs=3)

        # Raise the threshold: the same data no longer matches.
        evaluate(harness, alert_failed_runs=10)

        assert alerts(client, state="firing") == []
        resolved = alerts(client, state="resolved")
        assert resolved[0]["rule"] == "runs_failing"
        assert resolved[0]["resolvedAt"] is not None

    def test_old_failures_do_not_count(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        failed_runs(harness, client, 5, ago=timedelta(hours=2))

        evaluate(harness, alert_failed_runs=3)

        assert alerts(client, state="firing") == []

    def test_the_kill_switch_is_an_alert_while_it_is_engaged(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        client.patch(
            "/api/v1/organization/runtime", json={"executionsPaused": True, "reason": "Incident"}
        )

        evaluate(harness)

        firing = alerts(client, state="firing")
        assert [(alert["rule"], alert["severity"]) for alert in firing] == [("kill_switch", "info")]

    def test_a_stalled_run_is_noticed(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Stalled Agent")
        execution = request_run(client, agent["id"])
        edit_execution(
            harness,
            execution["id"],
            status="RUNNING",
            claimed_by="worker-gone",
            heartbeat_at=now_utc() - timedelta(minutes=30),
        )

        evaluate(harness, alert_stalled_run_seconds=300)

        assert "stalled_runs" in {alert["rule"] for alert in alerts(client, state="firing")}

    def test_alerts_never_cross_organizations(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        failed_runs(harness, client, 3)
        evaluate(harness, alert_failed_runs=3)

        other = harness.sign_in("admin", workspace=harness.other_workspace)

        assert alerts(other) == []


class TestResolvingByHand:
    def test_an_administrator_can_resolve_and_it_is_audited(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        failed_runs(harness, client, 3)
        evaluate(harness, alert_failed_runs=3)
        alert = alerts(client, state="firing")[0]

        response = client.post(f"/api/v1/alerts/{alert['id']}/resolve")

        assert response.status_code == 200
        assert response.json()["state"] == "resolved"
        audit = client.get("/api/v1/audit", params={"action": "alert."}).json()["items"]
        assert audit[0]["action"] == "alert.resolved"

    def test_a_member_cannot(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        failed_runs(harness, admin, 3)
        evaluate(harness, alert_failed_runs=3)
        alert = alerts(admin, state="firing")[0]

        member = harness.sign_in("member")

        assert member.post(f"/api/v1/alerts/{alert['id']}/resolve").status_code == 403

    def test_another_organization_s_alert_is_not_found(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        failed_runs(harness, admin, 3)
        evaluate(harness, alert_failed_runs=3)
        alert = alerts(admin, state="firing")[0]

        other = harness.sign_in("admin", workspace=harness.other_workspace)

        assert other.post(f"/api/v1/alerts/{alert['id']}/resolve").status_code == 404


class Hook:
    """A fake webhook receiver behind the real egress checks."""

    def __init__(self, address: str = "93.184.215.14") -> None:
        self.address = address
        self.requests: list[httpx2.Request] = []

    async def resolve(self, host: str) -> list[str]:
        if host != "hooks.example.com":
            raise EgressBlocked("resolution", f"{host} could not be resolved.")
        return [self.address]

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return httpx2.Response(200, headers={"content-type": "application/json"}, json={})

    def install(self) -> "Hook":
        use_egress(
            EgressGateway(transport=httpx2.MockTransport(self.handle), resolver=self.resolve)
        )
        return self


class TestWebhook:
    URL = "https://hooks.example.com/agenthub"

    def test_a_new_alert_is_sent_once_with_metadata_only(self, harness: Harness) -> None:
        hook = Hook().install()
        client = harness.sign_in("admin")
        failed_runs(harness, client, 3)

        evaluate(harness, alert_failed_runs=3, alert_webhook_url=self.URL)
        evaluate(harness, alert_failed_runs=3, alert_webhook_url=self.URL)

        assert len(hook.requests) == 1
        sent = json.loads(hook.requests[0].content)
        assert set(sent) == {
            "source",
            "rule",
            "severity",
            "summary",
            "detail",
            "organization",
            "at",
        }
        assert sent["rule"] == "runs_failing"
        assert hook.requests[0].method == "POST"

    def test_a_webhook_on_an_internal_address_is_refused(self, harness: Harness) -> None:
        hook = Hook(address="10.0.0.5").install()
        client = harness.sign_in("admin")
        failed_runs(harness, client, 3)

        evaluate(harness, alert_failed_runs=3, alert_webhook_url=self.URL)

        # Refused before connecting; the alert is still recorded.
        assert hook.requests == []
        assert alerts(client, state="firing")[0]["rule"] == "runs_failing"

    def test_a_plain_http_webhook_is_refused_at_startup(self) -> None:
        with pytest.raises(ValueError):
            runtime_settings(alert_webhook_url="http://hooks.example.com/agenthub")


class TestSystemStatus:
    def test_every_component_reports_from_a_live_check(self, harness: Harness) -> None:
        body = harness.sign_in("viewer").get("/api/v1/system/status").json()

        states = {component["id"]: component["state"] for component in body["components"]}
        assert set(states) == {"api", "database", "runtime", "models", "sandbox", "security"}
        assert states["database"] == "operational"
        # No provider and no container runtime in tests: honest, not green.
        assert states["models"] == "degraded"
        assert states["sandbox"] == "degraded"
        assert body["state"] == "degraded"

    def test_waiting_work_with_no_worker_is_an_outage(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Waiting Agent")
        request_run(client, agent["id"])

        body = client.get("/api/v1/system/status").json()

        runtime = next(c for c in body["components"] if c["id"] == "runtime")
        assert runtime["state"] == "outage"

    def test_firing_alerts_degrade_security(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        failed_runs(harness, client, 3)
        evaluate(harness, alert_failed_runs=3)

        body = client.get("/api/v1/system/status").json()

        security = next(c for c in body["components"] if c["id"] == "security")
        assert security["state"] == "degraded"

    def test_it_requires_a_session(self, harness: Harness) -> None:
        assert harness.app_client().get("/api/v1/system/status").status_code == 401


class TestInsights:
    def test_the_security_overview_counts_real_agents(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        active_agent(client, "Counted Agent One")
        active_agent(client, "Counted Agent Two")

        body = client.get("/api/v1/security/overview").json()

        assert sum(body["riskDistribution"].values()) == 2
        assert body["openAlerts"] == 0
        assert {row["capability"] for row in body["permissions"]}

    def test_security_events_come_from_the_audit_log(self, harness: Harness) -> None:
        harness.app_client().post(
            "/api/v1/auth/login",
            json={"email": harness.workspace.account("member").email, "password": "wrong-1"},
        )
        client = harness.sign_in("admin")

        events: list[dict[str, Any]] = []
        for _ in range(100):
            events = client.get("/api/v1/security/events").json()
            if events:
                break
            asyncio.run(asyncio.sleep(0.05))

        assert events[0]["type"] == "Failed sign-in"
        assert events[0]["severity"] == "medium"

    def test_analytics_count_real_runs(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Analysed Agent")
        done = request_run(client, agent["id"])
        failed = request_run(client, agent["id"])
        edit_execution(
            harness, done["id"], status="COMPLETED", ended_at=now_utc(), duration_ms=1000
        )
        edit_execution(harness, failed["id"], status="FAILED", ended_at=now_utc(), duration_ms=3000)

        body = client.get("/api/v1/analytics/summary", params={"days": 7}).json()

        assert sum(point["value"] for point in body["executionsPerDay"]) == 2
        assert body["successRate"] == 0.5
        assert body["averageDurationMs"] == 2000
        assert body["topAgents"][0]["name"] == "Analysed Agent"
        assert body["statusBreakdown"] == {"COMPLETED": 1, "FAILED": 1}

    def test_insights_never_cross_organizations(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        active_agent(client, "Private Analysed Agent")

        other = harness.sign_in("admin", workspace=harness.other_workspace)

        assert sum(other.get("/api/v1/security/overview").json()["riskDistribution"].values()) == 0
