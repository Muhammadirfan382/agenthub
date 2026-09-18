"""Starting a real sandbox and checking that the box actually holds.

Every other sandbox test asserts what AgentHub *asks* for. These assert what a
kernel *does* with that request, which is the only way to know the arguments
mean what they are supposed to mean. They need a container runtime and the
sandbox image, so they are marked `sandbox` and skip when either is missing.

To run them:

    docker build -t agenthub/sandbox:0.6.0 agents/sandbox
    pytest -m sandbox

CI does exactly that (.github/workflows/ci.yml, the `sandbox` job). On a
machine without a container runtime these skip, and the suite reports that
isolation was asserted but not executed — it never reports it as verified.
"""

import asyncio
import json
import os
import shutil
import subprocess
from typing import Any

import pytest

from app.sandbox import ContainerSandbox, SandboxResult, build_spec

SANDBOX_COMMAND = os.environ.get("SANDBOX_COMMAND", "docker")
SANDBOX_IMAGE = os.environ.get("SANDBOX_IMAGE", "agenthub/sandbox:0.6.0")

MEMORY_MB = 512
PIDS_LIMIT = 128


def _why_not() -> str | None:
    """The reason these cannot run here, or None when they can."""
    if shutil.which(SANDBOX_COMMAND) is None:
        return f"`{SANDBOX_COMMAND}` is not installed"
    try:
        available = asyncio.run(ContainerSandbox(SANDBOX_COMMAND).available())
    except (OSError, RuntimeError) as error:  # pragma: no cover - host dependent
        return f"`{SANDBOX_COMMAND}` could not be started: {error}"
    if not available:
        return f"`{SANDBOX_COMMAND}` is installed but not responding"
    present = subprocess.run(  # noqa: S603  (a fixed command, no shell, no user input)
        [SANDBOX_COMMAND, "image", "inspect", SANDBOX_IMAGE],
        capture_output=True,
        check=False,
    )
    if present.returncode != 0:
        return f"the image {SANDBOX_IMAGE} is not built"
    return None


UNAVAILABLE = _why_not()

# CI sets this, so a job meant to prove isolation cannot pass by skipping.
# Without it, a mistyped image tag would turn every test here into a skip and
# the job would go green having verified nothing.
if UNAVAILABLE is not None and os.environ.get("AGENTHUB_REQUIRE_SANDBOX_TESTS") == "1":
    pytest.fail(
        f"AGENTHUB_REQUIRE_SANDBOX_TESTS is set but the sandbox cannot run: {UNAVAILABLE}",
        pytrace=False,
    )

pytestmark = [
    pytest.mark.sandbox,
    pytest.mark.skipif(UNAVAILABLE is not None, reason=str(UNAVAILABLE)),
]


@pytest.fixture(scope="module")
def result() -> SandboxResult:
    """One real container, probed once. Every assertion below reads this."""
    spec = build_spec(
        image=SANDBOX_IMAGE,
        execution_id="exe_container_test",
        organization_id="org_container_test",
        memory_mb=MEMORY_MB,
        cpus=1.0,
        pids_limit=PIDS_LIMIT,
        tmpfs_mb=64,
        timeout_seconds=120,
    )
    return asyncio.run(ContainerSandbox(SANDBOX_COMMAND).probe(spec))


@pytest.fixture(scope="module")
def observed(result: SandboxResult) -> dict[str, bool]:
    return {check.id: check.passed for check in result.report.checks}


def test_the_container_starts_and_reports_back(result: SandboxResult) -> None:
    assert result.started, result.error
    assert result.exit_code == 0
    assert not result.timed_out


def test_every_isolation_guarantee_holds(result: SandboxResult) -> None:
    """The one that matters. A failure here names the promise the kernel broke."""
    broken = [f"{check.label}: {check.detail}" for check in result.report.failures]

    assert result.isolated, "the sandbox did not hold: " + "; ".join(broken)


@pytest.mark.parametrize(
    "guarantee",
    [
        "non_root",
        "read_only_root",
        "writable_scratch",
        "no_capabilities",
        "no_escalation",
        "no_network",
        "no_dns",
        "no_container_socket",
        "no_host_mounts",
        "no_secret_environment",
        "clean_environment",
        "memory_limit",
        "process_limit",
    ],
)
def test_a_named_guarantee_holds_in_a_real_container(
    observed: dict[str, bool], result: SandboxResult, guarantee: str
) -> None:
    detail = next(check.detail for check in result.report.checks if check.id == guarantee)

    assert observed[guarantee], f"{guarantee}: {detail}"


class TestWhatTheContainerSaidAboutItself:
    """Spot checks on the raw answers, not just the verdicts."""

    @pytest.fixture
    def reported(self, result: SandboxResult) -> dict[str, Any]:
        return dict(json.loads(result.stdout.strip().splitlines()[-1]))

    def test_it_is_the_account_the_image_was_built_with(self, reported: dict[str, Any]) -> None:
        assert reported["identity"]["uid"] == 65532
        assert reported["identity"]["is_root"] is False

    def test_the_limits_are_the_ones_that_were_asked_for(self, reported: dict[str, Any]) -> None:
        assert reported["limits"]["memory_bytes"] == MEMORY_MB * 1024 * 1024
        assert reported["limits"]["process_limit"] == PIDS_LIMIT

    def test_it_carries_none_of_the_host_s_environment(self, reported: dict[str, Any]) -> None:
        assert reported["environment"]["unexpected"] == []
        assert reported["environment"]["suspicious"] == []


def test_no_container_is_left_behind(result: SandboxResult) -> None:
    """`--rm` is a promise about the host, so check the host."""
    assert result.started
    listed = subprocess.run(  # noqa: S603  (a fixed command, no shell, no user input)
        [
            SANDBOX_COMMAND,
            "ps",
            "--all",
            "--filter",
            "label=agenthub.role=sandbox",
            "--format",
            "{{.Names}}",
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert listed.stdout.strip() == ""
