"""What a sandbox container is allowed to be.

These tests are the isolation guarantees written as assertions. They need no
container runtime: they check the arguments AgentHub asks for, which is the
part AgentHub is responsible for. Whether the kernel then honours them is
checked in test_sandbox_container.py, which needs a real runtime.

If one of these fails, the box got weaker.
"""

import pytest

from app.sandbox.spec import (
    FORBIDDEN_ARGUMENTS,
    SANDBOX_GID,
    SANDBOX_UID,
    SandboxSpec,
    build_spec,
    run_arguments,
    validate,
)


def spec(**overrides: object) -> SandboxSpec:
    defaults: dict[str, object] = {
        "image": "agenthub/sandbox:0.6.0",
        "execution_id": "exe_abc123",
        "organization_id": "org_xyz789",
        "memory_mb": 512,
        "cpus": 1.0,
        "pids_limit": 128,
        "tmpfs_mb": 64,
        "timeout_seconds": 60,
    }
    return build_spec(**{**defaults, **overrides})  # type: ignore[arg-type]


def argument_value(arguments: list[str], flag: str) -> str:
    """The value that follows a flag, so tests read like the command does."""
    return arguments[arguments.index(flag) + 1]


class TestTheContainerIsUnprivileged:
    def test_it_runs_as_a_fixed_non_root_account(self) -> None:
        arguments = run_arguments(spec())

        assert argument_value(arguments, "--user") == f"{SANDBOX_UID}:{SANDBOX_GID}"
        assert SANDBOX_UID != 0

    def test_it_holds_no_capabilities(self) -> None:
        arguments = run_arguments(spec())

        assert argument_value(arguments, "--cap-drop") == "ALL"
        assert "--cap-add" not in arguments

    def test_it_cannot_gain_privileges(self) -> None:
        assert argument_value(run_arguments(spec()), "--security-opt") == "no-new-privileges"


class TestTheContainerIsSealed:
    def test_the_filesystem_is_read_only(self) -> None:
        assert "--read-only" in run_arguments(spec())

    def test_the_only_writable_place_cannot_execute(self) -> None:
        tmpfs = argument_value(run_arguments(spec(tmpfs_mb=32)), "--tmpfs")

        assert tmpfs.startswith("/tmp:")  # noqa: S108  (a container path, not a host one)
        for option in ("rw", "noexec", "nosuid", "nodev", "size=32m"):
            assert option in tmpfs

    def test_nothing_from_the_host_is_mounted(self) -> None:
        arguments = run_arguments(spec())

        for flag in ("-v", "--volume", "--mount", "--device"):
            assert flag not in arguments
        assert not any("docker.sock" in argument for argument in arguments)
        # The only host-shaped path anywhere is the container's own tmpfs.
        paths = [argument for argument in arguments if argument.startswith("/")]
        assert paths == [
            "/tmp:rw,noexec,nosuid,nodev,size=64m",  # noqa: S108  (inside the container)
            "/opt/agenthub",
        ]

    def test_no_environment_is_passed_in(self) -> None:
        arguments = run_arguments(spec())

        assert "--env" not in arguments
        assert "-e" not in arguments
        assert "--env-file" not in arguments

    def test_it_is_removed_when_it_exits(self) -> None:
        assert "--rm" in run_arguments(spec())


class TestTheContainerHasNoNetwork:
    def test_networking_is_off(self) -> None:
        assert argument_value(run_arguments(spec()), "--network") == "none"

    def test_no_ports_are_published(self) -> None:
        arguments = run_arguments(spec())

        assert "-p" not in arguments
        assert "--publish" not in arguments
        assert "--publish-all" not in arguments


class TestTheContainerIsLimited:
    def test_memory_and_swap_are_capped_together(self) -> None:
        arguments = run_arguments(spec(memory_mb=256))

        # Equal values mean no swap at all, rather than unlimited swap.
        assert argument_value(arguments, "--memory") == "256m"
        assert argument_value(arguments, "--memory-swap") == "256m"

    def test_cpu_and_process_count_are_capped(self) -> None:
        arguments = run_arguments(spec(cpus=0.5, pids_limit=64))

        assert argument_value(arguments, "--cpus") == "0.5"
        assert argument_value(arguments, "--pids-limit") == "64"

    @pytest.mark.parametrize(
        ("field", "value"),
        [("memory_mb", 32), ("cpus", 0), ("pids_limit", 2), ("timeout_seconds", 0)],
    )
    def test_a_uselessly_small_limit_is_refused(self, field: str, value: object) -> None:
        with pytest.raises(ValueError):
            spec(**{field: value})

    def test_an_unpinned_image_is_refused(self) -> None:
        with pytest.raises(ValueError, match="Pin the sandbox image"):
            spec(image="agenthub/sandbox")


class TestTheContainerIsTraceable:
    def test_it_is_labelled_with_the_run_it_belongs_to(self) -> None:
        arguments = run_arguments(spec(execution_id="exe_1", organization_id="org_2"))

        assert "agenthub.execution=exe_1" in arguments
        assert "agenthub.organization=org_2" in arguments
        assert "agenthub.role=sandbox" in arguments

    def test_its_name_identifies_the_run(self) -> None:
        arguments = run_arguments(spec(execution_id="exe_1"))

        assert argument_value(arguments, "--name") == "agenthub-exe_1"

    def test_the_image_comes_last_before_the_command(self) -> None:
        arguments = run_arguments(spec())

        assert arguments[-1] == "agenthub/sandbox:0.6.0"
        assert arguments[0] == "run"


class TestTheLastGate:
    @pytest.mark.parametrize("dangerous", FORBIDDEN_ARGUMENTS)
    def test_a_dangerous_argument_is_refused(self, dangerous: str) -> None:
        with pytest.raises(ValueError, match="Refusing to start a sandbox"):
            validate([*run_arguments(spec()), dangerous])

    def test_the_container_socket_is_refused_however_it_is_spelled(self) -> None:
        with pytest.raises(ValueError, match="container socket"):
            validate([*run_arguments(spec()), "/var/run/docker.sock:/var/run/docker.sock"])

    def test_what_the_builder_produces_always_passes(self) -> None:
        validate(run_arguments(spec()))
