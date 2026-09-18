"""What a sandbox container is allowed to be.

This module is the security boundary written down. It builds the exact
arguments the container runtime is invoked with, and it is deliberately pure:
no subprocesses, no environment reads, nothing that needs a daemon. That makes
every guarantee below assertable in a unit test.

The rules, and why each one is here:

* **Ephemeral** (`--rm`): a container never outlives the run that created it.
* **Non-root** (`--user 65532:65532`): even a total escape lands as nobody.
* **Read-only root** plus a small `noexec` tmpfs: nothing can be written where
  it could later be executed.
* **No capabilities** (`--cap-drop ALL`) and **no escalation**
  (`--security-opt no-new-privileges`): setuid binaries cannot help.
* **No network** (`--network none`): egress is denied by default. Phase 8 adds
  a gateway; until it exists, "allowed domains" are configuration, not access.
* **Limits** on memory, swap, CPU and processes: a run cannot starve the host.
* **Nothing from the host**: no bind mounts, no volumes, no socket, and not one
  environment variable of ours is passed in.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

#: The unprivileged account baked into the image (see agents/sandbox/Dockerfile).
SANDBOX_UID = 65532
SANDBOX_GID = 65532

#: Arguments that must never appear. Checked in tests, and by `validate`.
FORBIDDEN_ARGUMENTS = (
    "--privileged",
    "--pid=host",
    "--network=host",
    "--userns=host",
    "--ipc=host",
    "--cap-add",
    "-v",
    "--volume",
    "--mount",
    "--device",
)


@dataclass(frozen=True)
class SandboxSpec:
    """One container, fully described."""

    image: str
    name: str
    #: Written as labels so a stray container can be traced back to its run.
    execution_id: str
    organization_id: str
    memory_mb: int
    cpus: float
    pids_limit: int
    tmpfs_mb: int
    timeout_seconds: int
    #: Arguments passed to the image's entrypoint. Never a shell string.
    command: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.memory_mb < 64:
            raise ValueError("A sandbox needs at least 64 MB of memory.")
        if self.cpus <= 0:
            raise ValueError("A sandbox needs a positive CPU share.")
        if self.pids_limit < 8:
            raise ValueError("A sandbox needs at least 8 processes.")
        if self.timeout_seconds <= 0:
            raise ValueError("A sandbox needs a positive timeout.")
        if ":" not in self.image:
            raise ValueError("Pin the sandbox image to a tag, never 'latest' by omission.")


def build_spec(
    *,
    image: str,
    execution_id: str,
    organization_id: str,
    memory_mb: int,
    cpus: float,
    pids_limit: int,
    tmpfs_mb: int,
    timeout_seconds: int,
    command: Sequence[str] = (),
) -> SandboxSpec:
    return SandboxSpec(
        image=image,
        name=f"agenthub-{execution_id}",
        execution_id=execution_id,
        organization_id=organization_id,
        memory_mb=memory_mb,
        cpus=cpus,
        pids_limit=pids_limit,
        tmpfs_mb=tmpfs_mb,
        timeout_seconds=timeout_seconds,
        command=tuple(command),
    )


def run_arguments(spec: SandboxSpec) -> list[str]:
    """The full argument list for `docker run` (or a compatible runtime).

    Read this as the contract: if an argument is not here, the container does
    not get it.
    """
    arguments = [
        "run",
        # Ephemeral: removed as soon as it exits, whatever the exit code.
        "--rm",
        "--name",
        spec.name,
        # Nobody, in a container that cannot become anybody else.
        "--user",
        f"{SANDBOX_UID}:{SANDBOX_GID}",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        # Nothing on disk survives, and the one writable place cannot execute.
        "--read-only",
        "--tmpfs",
        # A path inside the container, not on the host: S108 does not apply.
        f"/tmp:rw,noexec,nosuid,nodev,size={spec.tmpfs_mb}m",  # noqa: S108
        "--workdir",
        "/opt/agenthub",
        # Egress denied. A gateway replaces this in a later phase.
        "--network",
        "none",
        # Limits, so one run cannot take the host down with it.
        "--memory",
        f"{spec.memory_mb}m",
        # Equal to --memory means no swap at all, rather than unlimited swap.
        "--memory-swap",
        f"{spec.memory_mb}m",
        "--cpus",
        str(spec.cpus),
        "--pids-limit",
        str(spec.pids_limit),
        # No host identity. Note what is absent: no --env, no --env-file and no
        # --volume anywhere in this list. The container starts with only what
        # the image itself carries.
        "--hostname",
        "sandbox",
        "--label",
        f"agenthub.execution={spec.execution_id}",
        "--label",
        f"agenthub.organization={spec.organization_id}",
        "--label",
        "agenthub.role=sandbox",
        spec.image,
        *spec.command,
    ]
    return arguments


def validate(arguments: Sequence[str]) -> None:
    """Refuses to start a container that was given something dangerous.

    The spec builder above cannot produce these, but the check runs anyway:
    this is the last point before a real container starts, and a future edit
    that adds a mount should fail loudly rather than quietly work.
    """
    for argument in arguments:
        for forbidden in FORBIDDEN_ARGUMENTS:
            if argument == forbidden or argument.startswith(f"{forbidden}="):
                raise ValueError(f"Refusing to start a sandbox with {argument}.")
        if "docker.sock" in argument:
            raise ValueError("Refusing to start a sandbox with the container socket.")
