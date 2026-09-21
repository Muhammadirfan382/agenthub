"""Driving the container runner without a container runtime.

`ContainerSandbox` talks to `docker` over its command line, so a stand-in
executable that records what it was asked to do is enough to test everything
AgentHub is responsible for: the arguments it sends, what it does with a
timeout, a crash, a flood of output or an unreadable answer, and whether it
leaves containers behind.

The stand-in is a real process, started the same way a real runtime would be.
What is *not* tested here is whether a kernel honours those arguments; that is
test_sandbox_container.py, which needs a daemon.
"""

import asyncio
import json
import os
import stat
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.sandbox.report import NO_CAPABILITIES
from app.sandbox.runner import MAX_OUTPUT_BYTES, ContainerSandbox, UnavailableSandbox
from app.sandbox.spec import build_spec, run_arguments

FAKE_RUNTIME = '''"""A stand-in for `docker`. It records its arguments and answers to script."""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "config.json"), encoding="utf-8") as handle:
    config = json.load(handle)

arguments = sys.argv[1:]
# Whatever arrived on stdin is recorded too: the runner promises a container
# is given nothing to read, and that promise should be checkable.
stdin_text = sys.stdin.read()

with open(os.path.join(HERE, "calls.jsonl"), "a", encoding="utf-8") as log:
    record = {"arguments": arguments, "stdin": stdin_text, "environment": sorted(os.environ)}
    log.write(json.dumps(record) + "\\n")

subcommand = arguments[0] if arguments else ""

if subcommand == "version":
    if not config.get("present", True):
        sys.stderr.write("Cannot connect to the container runtime.\\n")
        sys.exit(1)
    sys.stdout.write("27.0.0\\n")
    sys.exit(0)

if subcommand == "run":
    sys.stdout.write(config.get("stdout", ""))
    sys.stderr.write(config.get("stderr", ""))
    sys.stdout.flush()
    sys.stderr.flush()
    time.sleep(config.get("delay", 0))
    sys.exit(config.get("exit_code", 0))

sys.exit(0)
'''


def probe_output(**overrides: Any) -> str:
    """What a well-behaved sandbox prints: one line of JSON."""
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
    return json.dumps(payload) + "\n"


class FakeRuntime:
    """A `docker` that does whatever a test tells it to."""

    def __init__(self, root: Path) -> None:
        # The directory name contains a space on purpose. A Windows path
        # holding "&" is only parsed correctly when the launcher is quoted,
        # and it is quoted only when it contains a space. This keeps the test
        # working on machines whose home directory has an "&" in it.
        self.home = root / "fake runtime"
        self.home.mkdir(parents=True)
        (self.home / "fake_docker.py").write_text(FAKE_RUNTIME, encoding="utf-8")
        self.configure()

        script = self.home / "fake_docker.py"
        if sys.platform == "win32":
            launcher = self.home / "docker.bat"
            launcher.write_text(
                f'@echo off\r\n"{sys.executable}" "{script}" %*\r\nexit /b %ERRORLEVEL%\r\n',
                encoding="utf-8",
            )
        else:
            launcher = self.home / "docker"
            launcher.write_text(
                f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8"
            )
            launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
        self.command = str(launcher)

    def configure(self, **values: Any) -> None:
        """Scripts the next answers: stdout, stderr, exit_code, delay, present."""
        defaults: dict[str, Any] = {
            "stdout": probe_output(),
            "stderr": "",
            "exit_code": 0,
            "delay": 0,
            "present": True,
        }
        (self.home / "config.json").write_text(json.dumps({**defaults, **values}), encoding="utf-8")

    @property
    def calls(self) -> list[dict[str, Any]]:
        log = self.home / "calls.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]

    def invocations(self, subcommand: str) -> list[list[str]]:
        return [
            call["arguments"]
            for call in self.calls
            if call["arguments"] and call["arguments"][0] == subcommand
        ]


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[FakeRuntime]:
    yield FakeRuntime(tmp_path)


@pytest.fixture
def spec() -> Any:
    return build_spec(
        image="agenthub/sandbox:0.6.0",
        execution_id="exe_test",
        organization_id="org_test",
        memory_mb=512,
        cpus=1.0,
        pids_limit=128,
        tmpfs_mb=64,
        timeout_seconds=30,
    )


def probe(sandbox: ContainerSandbox, spec: Any) -> Any:
    return asyncio.run(sandbox.probe(spec))


class TestWhatTheRunnerAsksFor:
    def test_it_sends_exactly_the_arguments_the_spec_builds(
        self, runtime: FakeRuntime, spec: Any
    ) -> None:
        probe(ContainerSandbox(runtime.command), spec)

        assert runtime.invocations("run") == [run_arguments(spec)]

    def test_the_container_is_given_nothing_to_read(self, runtime: FakeRuntime, spec: Any) -> None:
        probe(ContainerSandbox(runtime.command), spec)

        assert all(call["stdin"] == "" for call in runtime.calls)

    def test_the_runtime_cli_is_not_given_the_worker_s_secrets(
        self, runtime: FakeRuntime, spec: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user@db.invalid/agenthub")
        monkeypatch.setenv("AGENTHUB_ANTHROPIC_API_KEY", "not-a-real-key")
        monkeypatch.setenv("METRICS_TOKEN", "not-a-real-token")
        monkeypatch.setenv("DOCKER_HOST", "unix:///run/agenthub-sandbox/docker.sock")

        probe(ContainerSandbox(runtime.command), spec)

        assert runtime.calls
        for call in runtime.calls:
            names = {name.upper() for name in call["environment"]}
            assert not names & {"DATABASE_URL", "AGENTHUB_ANTHROPIC_API_KEY", "METRICS_TOKEN"}
            # Which daemon to use still gets through.
            assert "DOCKER_HOST" in names

    def test_nothing_starts_before_the_arguments_are_checked(
        self, runtime: FakeRuntime, spec: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The gate belongs inside probe(), not only in the spec builder.
        monkeypatch.setattr(
            "app.sandbox.runner.run_arguments",
            lambda _spec: ["run", "--privileged", "agenthub/sandbox:0.6.0"],
        )

        with pytest.raises(ValueError, match="Refusing to start a sandbox"):
            probe(ContainerSandbox(runtime.command), spec)
        assert runtime.calls == []


class TestAContainerThatBehaves:
    def test_a_clean_probe_counts_as_isolated(self, runtime: FakeRuntime, spec: Any) -> None:
        result = probe(ContainerSandbox(runtime.command), spec)

        assert result.started
        assert result.isolated
        assert result.exit_code == 0
        assert result.error is None
        assert result.report.passed

    def test_a_failed_check_is_reported_rather_than_hidden(
        self, runtime: FakeRuntime, spec: Any
    ) -> None:
        runtime.configure(stdout=probe_output(network={"reachable": True, "dns_resolves": True}))

        result = probe(ContainerSandbox(runtime.command), spec)

        assert result.started
        assert not result.isolated
        assert [check.id for check in result.report.failures] == ["no_network", "no_dns"]

    def test_the_answer_is_found_among_a_runtime_s_own_chatter(
        self, runtime: FakeRuntime, spec: Any
    ) -> None:
        runtime.configure(
            stdout="Unable to find image locally\nPulling from library\n" + probe_output()
        )

        assert probe(ContainerSandbox(runtime.command), spec).isolated


class TestAContainerThatMisbehaves:
    def test_a_non_zero_exit_is_not_isolation(self, runtime: FakeRuntime, spec: Any) -> None:
        runtime.configure(stdout="", stderr="exec format error\n", exit_code=125)

        result = probe(ContainerSandbox(runtime.command), spec)

        assert result.started
        assert not result.isolated
        assert result.exit_code == 125
        assert result.error == "exec format error"
        assert not result.report.passed

    def test_an_unreadable_answer_is_not_isolation(self, runtime: FakeRuntime, spec: Any) -> None:
        runtime.configure(stdout="probe finished\n{not json at all\n")

        result = probe(ContainerSandbox(runtime.command), spec)

        assert result.started
        assert not result.isolated
        assert result.error == "unreadable probe output"

    def test_silence_is_not_isolation(self, runtime: FakeRuntime, spec: Any) -> None:
        runtime.configure(stdout="")

        assert not probe(ContainerSandbox(runtime.command), spec).isolated

    def test_a_flood_of_output_is_cut_off(self, runtime: FakeRuntime, spec: Any) -> None:
        runtime.configure(stdout="x" * (MAX_OUTPUT_BYTES * 2))

        result = probe(ContainerSandbox(runtime.command), spec)

        assert len(result.stdout) <= MAX_OUTPUT_BYTES + 64
        assert result.stdout.endswith(f"truncated at {MAX_OUTPUT_BYTES} bytes")
        # A truncated answer is unreadable, and therefore not isolation.
        assert not result.isolated


class TestAContainerThatWillNotStop:
    def test_it_is_abandoned_and_removed(self, runtime: FakeRuntime) -> None:
        # Long enough to still be running when the one-second timeout fires,
        # short enough that Windows — where the stand-in is launched through a
        # batch wrapper and so outlives the kill — does not hold up the suite.
        runtime.configure(stdout="", delay=5)
        slow = build_spec(
            image="agenthub/sandbox:0.6.0",
            execution_id="exe_slow",
            organization_id="org_test",
            memory_mb=512,
            cpus=1.0,
            pids_limit=128,
            tmpfs_mb=64,
            timeout_seconds=1,
        )

        result = probe(ContainerSandbox(runtime.command), slow)

        assert result.timed_out
        assert not result.isolated
        assert result.error == "timeout"
        # Whatever happened, no container is left running under that name.
        assert runtime.invocations("rm") == [["rm", "--force", "agenthub-exe_slow"]]


class TestNoRuntime:
    def test_a_runtime_that_does_not_answer_starts_nothing(
        self, runtime: FakeRuntime, spec: Any
    ) -> None:
        runtime.configure(present=False)

        result = probe(ContainerSandbox(runtime.command), spec)

        assert not result.started
        assert not result.isolated
        assert result.error is not None
        assert runtime.invocations("run") == []

    def test_a_missing_runtime_is_not_looked_for_twice(self, tmp_path: Path) -> None:
        sandbox = ContainerSandbox(str(tmp_path / "there-is-no-docker-here"))

        assert asyncio.run(sandbox.available()) is False
        assert asyncio.run(sandbox.available()) is False

    def test_the_answer_is_remembered(self, runtime: FakeRuntime) -> None:
        sandbox = ContainerSandbox(runtime.command)

        assert asyncio.run(sandbox.available()) is True
        assert asyncio.run(sandbox.available()) is True
        assert len(runtime.invocations("version")) == 1

    def test_the_unavailable_sandbox_refuses_rather_than_pretends(self, spec: Any) -> None:
        sandbox = UnavailableSandbox("docker is not installed")

        result = asyncio.run(sandbox.probe(spec))

        assert asyncio.run(sandbox.available()) is False
        assert not result.started
        assert not result.isolated
        assert result.error == "docker is not installed"
        assert result.report.failures[0].id == "runtime_available"


def test_the_fake_runtime_is_never_mistaken_for_a_real_one(runtime: FakeRuntime) -> None:
    """Guards the tests themselves: this is a stand-in, not a container."""
    assert os.path.basename(runtime.command).startswith("docker")
    assert "fake runtime" in runtime.command
