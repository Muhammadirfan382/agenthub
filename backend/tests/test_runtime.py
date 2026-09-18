"""The execution runtime: lifecycle, budgets, approvals, cancellation, stopping.

These tests drive the worker directly instead of waiting for the background
loop, so they assert behaviour rather than timing.
"""

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.models import Execution
from app.runtime.plan import build_plan
from app.runtime.worker import run_once
from tests.conftest import Harness, runtime_settings
from tests.factories import agent_payload, grant


def drain(harness: Harness, *, limit: int = 10, settings: Settings | None = None) -> int:
    """Runs queued work until there is none left. Returns how many runs moved."""

    async def _drain(factory: async_sessionmaker[AsyncSession]) -> int:
        moved = 0
        for _ in range(limit):
            if not await run_once(
                factory, worker="test-worker", settings=settings or runtime_settings()
            ):
                break
            moved += 1
        return moved

    return asyncio.run(_drain(harness.session_factory))


async def _edit(
    factory: async_sessionmaker[AsyncSession], execution_id: str, **values: Any
) -> None:
    async with factory() as session:
        await session.execute(
            update(Execution).where(Execution.id == execution_id).values(**values)
        )
        await session.commit()


def edit_execution(harness: Harness, execution_id: str, **values: Any) -> None:
    asyncio.run(_edit(harness.session_factory, execution_id, **values))


def read_execution(harness: Harness, execution_id: str) -> Execution:
    async def _read(factory: async_sessionmaker[AsyncSession]) -> Execution:
        async with factory() as session:
            execution = await session.scalar(select(Execution).where(Execution.id == execution_id))
            assert execution is not None
            return execution

    return asyncio.run(_read(harness.session_factory))


def active_agent(client: TestClient, name: str, **overrides: Any) -> dict[str, Any]:
    created = client.post("/api/v1/agents", json=agent_payload(name=name, **overrides))
    assert created.status_code == 201, created.text
    agent: dict[str, Any] = created.json()
    activated = client.patch(f"/api/v1/agents/{agent['id']}/status", json={"status": "active"})
    assert activated.status_code == 200, activated.text
    return agent


def tool_agent(client: TestClient, name: str, *, requires_approval: bool = False) -> dict[str, Any]:
    """An agent that declares a tool and the permission that tool needs."""
    payload = grant(
        agent_payload(
            name=name,
            tools=["web_search"],
            securityPolicy={
                "sandbox": "strict",
                "networkEgress": "allow_list",
                "allowedDomains": ["docs.example.com"],
                "approvalRequiredFor": ["high", "critical"],
                "auditLogging": True,
            },
        ),
        "web_access",
        level="restricted",
        scope="Allow-listed documentation",
        requiresApproval=requires_approval,
    )
    created = client.post("/api/v1/agents", json=payload)
    assert created.status_code == 201, created.text
    agent: dict[str, Any] = created.json()
    client.patch(f"/api/v1/agents/{agent['id']}/status", json={"status": "active"})
    return agent


def request_run(client: TestClient, agent_id: str) -> dict[str, Any]:
    response = client.post(f"/api/v1/agents/{agent_id}/executions")
    assert response.status_code == 202, response.text
    execution: dict[str, Any] = response.json()
    return execution


class TestLifecycle:
    def test_a_requested_run_starts_queued_with_its_budget(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Queued Agent")

        execution = request_run(client, agent["id"])

        assert execution["status"] == "QUEUED"
        assert execution["runtime"] == "simulation"
        assert execution["requestedBy"] == "Admin Person"
        assert execution["budget"] == {
            "maxRuntimeSeconds": 300,
            "maxTokens": 50000,
            "maxToolCalls": 20,
        }

    def test_the_worker_runs_it_to_completion_and_records_the_trace(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Recorded Agent")
        execution = request_run(client, agent["id"])

        assert drain(harness) == 1

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "COMPLETED"
        assert body["durationMs"] is not None
        kinds = [event["kind"] for event in body["timeline"]]
        # The run opens with its lifecycle events — started, and what it was
        # given to run in — and a model step follows.
        assert kinds[0] == "lifecycle"
        assert "model" in kinds
        assert any("simulated" in event["label"].lower() for event in body["timeline"])
        assert body["logs"], "the run should have written logs"
        assert body["result"].startswith("Simulated run finished")

    def test_a_tool_call_is_recorded_as_simulated_never_as_succeeded(
        self, harness: Harness
    ) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Tooling Agent")
        execution = request_run(client, agent["id"])
        drain(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()

        calls = body["toolCalls"]
        assert [call["tool"] for call in calls] == ["web_search"]
        assert calls[0]["status"] == "simulated"
        assert "no agent code" in (calls[0]["outputSummary"] or "").lower()
        assert body["toolCallCount"] == 1

    def test_an_agent_with_no_tools_completes_without_tool_calls(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Toolless Agent")
        execution = request_run(client, agent["id"])
        drain(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "COMPLETED"
        assert body["toolCalls"] == []

    def test_token_usage_is_counted_from_the_simulated_steps(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Counting Agent")
        execution = request_run(client, agent["id"])
        drain(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["tokenUsage"]["input"] > 0
        assert body["tokenUsage"]["output"] > 0


class TestBudgets:
    def test_a_run_over_its_token_budget_fails(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Greedy Agent")
        execution = request_run(client, agent["id"])
        edit_execution(harness, execution["id"], max_tokens=10, token_input=999)

        drain(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "FAILED"
        assert body["error"]["code"] == "token_budget"

    def test_a_run_over_its_runtime_budget_times_out(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Slow Agent")
        execution = request_run(client, agent["id"])
        edit_execution(harness, execution["id"], max_runtime_seconds=0)

        drain(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "TIMEOUT"
        assert body["error"]["code"] == "runtime_limit"

    def test_a_run_over_its_tool_call_budget_fails(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Chatty Agent")
        execution = request_run(client, agent["id"])
        edit_execution(harness, execution["id"], max_tool_calls=0)

        drain(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "FAILED"
        assert body["error"]["code"] == "tool_call_budget"


class TestApprovals:
    def test_a_step_needing_approval_pauses_the_run(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Approval Agent", requires_approval=True)
        execution = request_run(client, agent["id"])

        drain(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "WAITING_FOR_APPROVAL"
        assert body["pendingApprovals"] == 1
        approval = body["approvals"][0]
        assert approval["status"] == "pending"
        assert approval["tool"] == "web_search"
        assert approval["capability"] == "web_access"
        # Nothing was recorded as done while it waits.
        assert body["toolCalls"] == []

    def test_approving_lets_the_run_continue(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Approval Agent", requires_approval=True)
        execution = request_run(client, agent["id"])
        drain(harness)
        approval = client.get(f"/api/v1/executions/{execution['id']}").json()["approvals"][0]

        decided = client.post(
            f"/api/v1/executions/{execution['id']}/approvals/{approval['id']}",
            json={"decision": "approved", "note": "Scope looks right."},
        )
        assert decided.status_code == 200
        drain(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "COMPLETED"
        assert body["approvals"][0]["status"] == "approved"
        assert body["approvals"][0]["decidedBy"] == "Admin Person"
        assert [call["status"] for call in body["toolCalls"]] == ["simulated"]

    def test_refusing_records_the_refusal_and_finishes_without_the_tool(
        self, harness: Harness
    ) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Refused Agent", requires_approval=True)
        execution = request_run(client, agent["id"])
        drain(harness)
        approval = client.get(f"/api/v1/executions/{execution['id']}").json()["approvals"][0]

        client.post(
            f"/api/v1/executions/{execution['id']}/approvals/{approval['id']}",
            json={"decision": "denied", "note": "Too broad."},
        )
        drain(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "COMPLETED"
        assert [call["status"] for call in body["toolCalls"]] == ["denied"]
        assert body["toolCallCount"] == 0

    def test_a_decision_cannot_be_made_twice(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Twice Agent", requires_approval=True)
        execution = request_run(client, agent["id"])
        drain(harness)
        approval = client.get(f"/api/v1/executions/{execution['id']}").json()["approvals"][0]
        url = f"/api/v1/executions/{execution['id']}/approvals/{approval['id']}"

        assert client.post(url, json={"decision": "approved"}).status_code == 200
        second = client.post(url, json={"decision": "denied"})

        assert second.status_code == 409
        assert "already" in second.json()["message"]

    def test_a_viewer_cannot_approve(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        viewer = harness.sign_in("viewer")
        agent = tool_agent(admin, "Viewer Approval Agent", requires_approval=True)
        execution = request_run(admin, agent["id"])
        drain(harness)
        approval = admin.get(f"/api/v1/executions/{execution['id']}").json()["approvals"][0]

        refused = viewer.post(
            f"/api/v1/executions/{execution['id']}/approvals/{approval['id']}",
            json={"decision": "approved"},
        )

        assert refused.status_code == 403

    def test_pending_approvals_are_listed_for_the_organization(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Listed Approval Agent", requires_approval=True)
        request_run(client, agent["id"])
        drain(harness)

        body = client.get("/api/v1/executions/approvals").json()

        assert body["total"] == 1
        assert body["items"][0]["agentName"] == "Listed Approval Agent"

    def test_approvals_do_not_cross_organizations(self, harness: Harness) -> None:
        inside = harness.sign_in("admin")
        outside = harness.sign_in("admin", workspace=harness.other_workspace)
        agent = tool_agent(inside, "Private Approval Agent", requires_approval=True)
        execution = request_run(inside, agent["id"])
        drain(harness)
        approval = inside.get(f"/api/v1/executions/{execution['id']}").json()["approvals"][0]

        assert outside.get("/api/v1/executions/approvals").json()["total"] == 0
        assert (
            outside.post(
                f"/api/v1/executions/{execution['id']}/approvals/{approval['id']}",
                json={"decision": "approved"},
            ).status_code
            == 404
        )


class TestCancellation:
    def test_cancelling_stops_the_run_at_the_next_step(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Cancelled Agent")
        execution = request_run(client, agent["id"])

        cancelled = client.post(f"/api/v1/executions/{execution['id']}/cancel")
        assert cancelled.status_code == 202
        assert cancelled.json()["cancelRequested"] is True
        drain(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "CANCELLED"
        assert body["error"]["code"] == "cancelled"
        assert "Admin Person" in body["error"]["message"]

    def test_a_finished_run_cannot_be_cancelled(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Finished Agent")
        execution = request_run(client, agent["id"])
        drain(harness)

        response = client.post(f"/api/v1/executions/{execution['id']}/cancel")

        assert response.status_code == 409
        assert "already finished" in response.json()["message"]

    def test_a_viewer_cannot_cancel(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        viewer = harness.sign_in("viewer")
        agent = tool_agent(admin, "Protected Agent")
        execution = request_run(admin, agent["id"])

        assert viewer.post(f"/api/v1/executions/{execution['id']}/cancel").status_code == 403


class TestKillSwitch:
    def test_engaging_it_blocks_new_runs(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Blocked Agent")

        engaged = client.patch(
            "/api/v1/organization/runtime",
            json={"executionsPaused": True, "reason": "Investigating an incident."},
        )
        assert engaged.status_code == 200
        assert engaged.json()["executionsPaused"] is True
        assert engaged.json()["pausedBy"] == "Admin Person"

        refused = client.post(f"/api/v1/agents/{agent['id']}/executions")
        assert refused.status_code == 422
        assert "kill switch" in refused.json()["message"]

    def test_engaging_it_stops_what_is_already_running(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Running Agent")
        execution = request_run(client, agent["id"])

        client.patch("/api/v1/organization/runtime", json={"executionsPaused": True})
        drain(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "CANCELLED"
        assert body["error"]["code"] == "kill_switch"

    def test_only_the_owner_can_release_it(self, harness: Harness) -> None:
        admin = harness.sign_in("admin")
        owner = harness.sign_in("owner")
        admin.patch("/api/v1/organization/runtime", json={"executionsPaused": True})

        refused = admin.patch("/api/v1/organization/runtime", json={"executionsPaused": False})
        assert refused.status_code == 403

        released = owner.patch("/api/v1/organization/runtime", json={"executionsPaused": False})
        assert released.status_code == 200
        assert released.json()["executionsPaused"] is False
        assert released.json()["pausedBy"] is None

    def test_a_member_cannot_engage_it(self, harness: Harness) -> None:
        member = harness.sign_in("member")

        assert (
            member.patch(
                "/api/v1/organization/runtime", json={"executionsPaused": True}
            ).status_code
            == 403
        )

    def test_it_does_not_reach_other_organizations(self, harness: Harness) -> None:
        inside = harness.sign_in("admin")
        outside = harness.sign_in("admin", workspace=harness.other_workspace)
        inside.patch("/api/v1/organization/runtime", json={"executionsPaused": True})

        assert outside.get("/api/v1/organization/runtime").json()["executionsPaused"] is False
        agent = active_agent(outside, "Unaffected Agent")
        assert outside.post(f"/api/v1/agents/{agent['id']}/executions").status_code == 202


class TestWorkerClaiming:
    def test_only_one_worker_takes_a_run(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Contended Agent")
        request_run(client, agent["id"])

        async def race() -> list[bool]:
            return list(
                await asyncio.gather(
                    run_once(
                        harness.session_factory,
                        worker="worker-a",
                        settings=runtime_settings(),
                    ),
                    run_once(
                        harness.session_factory,
                        worker="worker-b",
                        settings=runtime_settings(),
                    ),
                )
            )

        results = asyncio.run(race())

        # One of them did the work; the other found nothing to do.
        assert sorted(results) == [False, True]

    def test_an_abandoned_run_is_picked_up_again(self, harness: Harness) -> None:
        client = harness.sign_in("admin")
        agent = tool_agent(client, "Abandoned Agent")
        execution = request_run(client, agent["id"])
        # A worker claimed it and then died: the heartbeat never moved.
        edit_execution(
            harness,
            execution["id"],
            status="RUNNING",
            claimed_by="dead-worker",
            heartbeat_at=None,
        )

        assert drain(harness) == 1

        assert read_execution(harness, execution["id"]).status == "COMPLETED"

    def test_nothing_to_do_is_not_an_error(self, harness: Harness) -> None:
        assert drain(harness) == 0


@pytest.mark.parametrize("role", ["viewer", "member"])
def test_reading_a_run_is_open_to_everyone_in_the_organization(harness: Harness, role: str) -> None:
    admin = harness.sign_in("admin")
    agent = tool_agent(admin, f"Readable Agent {role}")
    execution = request_run(admin, agent["id"])
    drain(harness)

    reader = harness.sign_in(role)  # type: ignore[arg-type]

    body = reader.get(f"/api/v1/executions/{execution['id']}")
    assert body.status_code == 200
    assert body.json()["runtime"] == "simulation"


class TestPlanning:
    """The plan is derived from the agent's declaration, not from a model."""

    def test_a_tool_whose_capability_is_denied_is_planned_as_denied(self) -> None:
        plan = build_plan(
            tools=["web_search"],
            permissions=[
                {"capability": "web_access", "level": "denied", "requiresApproval": False}
            ],
            model="balanced-large",
        )

        tool_step = next(step for step in plan if step.is_tool)
        assert tool_step.capability == "web_access"
        assert tool_step.level == "denied"

    def test_a_tool_outside_the_catalogue_is_planned_and_refused(self) -> None:
        plan = build_plan(tools=["mystery_tool"], permissions=[], model="balanced-large")

        tool_step = next(step for step in plan if step.is_tool)
        assert tool_step.capability is None
        assert tool_step.level == "denied"

    def test_every_plan_prepares_thinks_and_finishes(self) -> None:
        plan = build_plan(tools=[], permissions=[], model="fast-small")

        assert [step.kind for step in plan] == ["prepare", "model", "finish"]

    def test_approval_and_risk_come_from_the_permission(self) -> None:
        plan = build_plan(
            tools=["code_sandbox"],
            permissions=[
                {
                    "capability": "code_execution",
                    "level": "restricted",
                    "requiresApproval": True,
                    "scope": "Test suite",
                }
            ],
            model="reasoning-large",
        )

        tool_step = next(step for step in plan if step.is_tool)
        assert tool_step.requires_approval is True
        assert tool_step.risk == "critical"
        assert tool_step.scope == "Test suite"
