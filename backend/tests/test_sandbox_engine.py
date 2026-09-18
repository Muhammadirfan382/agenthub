"""What the engine does with the sandbox it is given.

Three answers matter, and each one is a decision about whether work may
proceed at all:

* a container that passes every check — the run continues, marked `sandbox`;
* a container that starts and fails a check — the run **fails**, because a box
  that does not hold is worse than an honest absence of one;
* no container runtime at all — the run continues as a recorded simulation and
  says so, unless the deployment demanded isolation.

A stub sandbox stands in for the runtime, so all three are reachable on a
machine that has no daemon.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.runtime.sandbox import get_sandbox, use_sandbox
from app.sandbox import ContainerSandbox, SandboxResult, UnavailableSandbox
from app.sandbox.report import NO_CAPABILITIES, evaluate, unavailable_report
from app.sandbox.spec import SandboxSpec
from tests.conftest import Harness, runtime_settings
from tests.test_runtime import active_agent, drain, read_execution, request_run


def clean_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "identity": {"uid": 65532, "gid": 65532, "is_root": False, "groups": []},
        "filesystem": {
            "root_writable": False,
            "tmp_writable": True,
            "docker_socket_present": False,
            "host_mounts": [],
        },
        "privileges": {"capabilities": NO_CAPABILITIES, "no_new_privileges": True},
        "network": {"reachable": False, "dns_resolves": False},
        "limits": {"memory_bytes": 512 * 1024 * 1024, "process_limit": 128},
        "environment": {"names": ["PATH"], "unexpected": [], "suspicious": []},
    }
    payload.update(overrides)
    return payload


def result_for(payload: dict[str, Any]) -> SandboxResult:
    return SandboxResult(
        started=True,
        exit_code=0,
        stdout="",
        stderr="",
        timed_out=False,
        report=evaluate(payload, expected_memory_mb=512, expected_pids=128),
    )


class StubSandbox:
    """A sandbox that answers however a test needs, and remembers what it was asked."""

    name = "stub"

    def __init__(self, result: SandboxResult) -> None:
        self.result = result
        self.specs: list[SandboxSpec] = []

    async def available(self) -> bool:
        return self.result.started

    async def probe(self, spec: SandboxSpec) -> SandboxResult:
        self.specs.append(spec)
        return self.result


def settings_for(**overrides: Any) -> Settings:
    return runtime_settings(**overrides)


@pytest.fixture
def verified() -> StubSandbox:
    sandbox = StubSandbox(result_for(clean_payload()))
    use_sandbox(sandbox)
    return sandbox


def run_one(harness: Harness, **settings: Any) -> None:
    drain(harness, settings=settings_for(**settings))


class TestAVerifiedSandbox:
    def test_the_run_is_marked_as_sandboxed(self, harness: Harness, verified: StubSandbox) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Sandboxed Agent")
        execution = request_run(client, agent["id"])

        run_one(harness)

        stored = read_execution(harness, execution["id"])
        assert stored.status == "COMPLETED"
        assert stored.runtime == "sandbox"

    def test_the_report_is_kept_so_the_claim_can_be_checked(
        self, harness: Harness, verified: StubSandbox
    ) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Audited Agent")
        execution = request_run(client, agent["id"])

        run_one(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        report = body["sandboxReport"]
        assert report["passed"] is True
        assert len(report["checks"]) == 13
        assert {"id", "label", "passed", "detail"} == set(report["checks"][0])

    def test_the_timeline_says_the_box_was_checked_and_that_nothing_ran_in_it(
        self, harness: Harness, verified: StubSandbox
    ) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Honest Agent")
        execution = request_run(client, agent["id"])

        run_one(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        verified_event = next(
            event for event in body["timeline"] if event["label"] == "Sandbox verified"
        )
        assert "13 of 13" in verified_event["detail"]
        assert "Nothing ran inside it" in verified_event["detail"]

    def test_the_container_is_asked_for_with_this_run_s_identity_and_limits(
        self, harness: Harness, verified: StubSandbox
    ) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Labelled Agent")
        execution = request_run(client, agent["id"])

        run_one(harness, sandbox_memory_mb=256, sandbox_pids_limit=64)

        assert len(verified.specs) == 1
        spec = verified.specs[0]
        assert spec.execution_id == execution["id"]
        assert spec.organization_id == harness.workspace.organization_id
        assert (spec.memory_mb, spec.pids_limit) == (256, 64)


class TestASandboxThatDoesNotHold:
    @pytest.fixture
    def leaky(self) -> StubSandbox:
        sandbox = StubSandbox(
            result_for(clean_payload(network={"reachable": True, "dns_resolves": True}))
        )
        use_sandbox(sandbox)
        return sandbox

    def test_the_run_fails_rather_than_continuing(
        self, harness: Harness, leaky: StubSandbox
    ) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Leaky Agent")
        execution = request_run(client, agent["id"])

        run_one(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "FAILED"
        assert body["error"]["code"] == "sandbox_unsafe"
        assert "Cannot reach the network" in body["error"]["message"]

    def test_it_does_not_claim_to_have_been_sandboxed(
        self, harness: Harness, leaky: StubSandbox
    ) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Leaky Agent Two")
        execution = request_run(client, agent["id"])

        run_one(harness)

        stored = read_execution(harness, execution["id"])
        assert stored.runtime != "sandbox"

    def test_the_failing_checks_are_stored(self, harness: Harness, leaky: StubSandbox) -> None:
        client = harness.sign_in("admin")
        agent = active_agent(client, "Leaky Agent Three")
        execution = request_run(client, agent["id"])

        run_one(harness)

        report = client.get(f"/api/v1/executions/{execution['id']}").json()["sandboxReport"]
        assert report["passed"] is False
        failed = [check["id"] for check in report["checks"] if not check["passed"]]
        assert failed == ["no_network", "no_dns"]

    def test_a_container_that_never_finished_is_not_a_sandbox(self, harness: Harness) -> None:
        use_sandbox(
            StubSandbox(
                SandboxResult(
                    started=True,
                    exit_code=None,
                    stdout="",
                    stderr="",
                    timed_out=True,
                    report=unavailable_report("The sandbox did not finish within 60s."),
                    error="timeout",
                )
            )
        )
        client = harness.sign_in("admin")
        agent = active_agent(client, "Hanging Agent")
        execution = request_run(client, agent["id"])

        run_one(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "FAILED"
        assert body["error"]["code"] == "sandbox_unsafe"


class TestNoSandboxAtAll:
    def test_the_run_is_recorded_as_a_simulation_and_says_so(self, harness: Harness) -> None:
        use_sandbox(UnavailableSandbox("docker is not installed"))
        client = harness.sign_in("admin")
        agent = active_agent(client, "Unsandboxed Agent")
        execution = request_run(client, agent["id"])

        run_one(harness)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "COMPLETED"
        assert body["runtime"] == "simulation"
        absent = next(
            event for event in body["timeline"] if event["label"] == "No sandbox available"
        )
        assert "docker is not installed" in absent["detail"]
        assert "executes nothing" in absent["detail"]

    def test_a_deployment_can_demand_isolation_and_get_a_refusal(self, harness: Harness) -> None:
        use_sandbox(UnavailableSandbox("docker is not installed"))
        client = harness.sign_in("admin")
        agent = active_agent(client, "Strict Agent")
        execution = request_run(client, agent["id"])

        run_one(harness, require_sandbox=True)

        body = client.get(f"/api/v1/executions/{execution['id']}").json()
        assert body["status"] == "FAILED"
        assert body["error"]["code"] == "sandbox_unavailable"
        assert "docker is not installed" in body["error"]["message"]

    def test_nothing_is_recorded_as_having_run_in_a_box_that_never_existed(
        self, harness: Harness
    ) -> None:
        use_sandbox(UnavailableSandbox("docker is not installed"))
        client = harness.sign_in("admin")
        agent = active_agent(client, "Strict Agent Two")
        execution = request_run(client, agent["id"])

        run_one(harness, require_sandbox=True)

        report = client.get(f"/api/v1/executions/{execution['id']}").json()["sandboxReport"]
        assert report["passed"] is False
        assert [check["id"] for check in report["checks"]] == ["runtime_available"]


class TestChoosingTheSandbox:
    def test_switching_sandboxing_off_gives_a_sandbox_that_refuses(self) -> None:
        use_sandbox(None)

        sandbox = get_sandbox(settings_for(sandbox_enabled=False))

        assert isinstance(sandbox, UnavailableSandbox)
        assert "switched off" in sandbox.reason

    def test_otherwise_the_configured_runtime_is_used(self) -> None:
        use_sandbox(None)

        sandbox = get_sandbox(settings_for(sandbox_command="podman"))

        assert isinstance(sandbox, ContainerSandbox)
        assert sandbox.command == "podman"


class TestAMisconfiguredSandbox:
    """A bad limit stops the process at startup rather than failing every run."""

    @pytest.mark.parametrize(
        "overrides",
        [
            {"sandbox_memory_mb": 32},
            {"sandbox_cpus": 0},
            {"sandbox_pids_limit": 2},
            {"sandbox_timeout_seconds": 0},
            {"sandbox_tmpfs_mb": 0},
            {"sandbox_image": "agenthub/sandbox"},
            {"sandbox_image": "agenthub/sandbox:0.6.0 --privileged"},
            {"sandbox_image": "--privileged:0.6.0"},
            {"sandbox_image": "registry.example.com:5000/agenthub/sandbox"},
        ],
    )
    def test_it_is_refused_when_the_settings_load(self, overrides: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            settings_for(**overrides)

    @pytest.mark.parametrize(
        "image",
        [
            "agenthub/sandbox:0.6.0",
            "registry.example.com:5000/agenthub/sandbox:0.6.0",
            "agenthub/sandbox@sha256:0123456789abcdef",
        ],
    )
    def test_a_pinned_image_from_any_registry_is_accepted(self, image: str) -> None:
        assert settings_for(sandbox_image=image).sandbox_image == image
