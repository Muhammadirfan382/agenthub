"""Starting and stopping sandbox containers.

The runtime is driven through its command-line interface rather than a socket
API: AgentHub never holds a handle to the container runtime, and nothing it
runs is given one either.

Everything here is defensive about the same three things: the container must
not outlive its timeout, its output must not be allowed to grow without bound,
and no container may be left behind.
"""

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from typing import Any, Protocol

from app.sandbox.report import IsolationReport, evaluate, unavailable_report
from app.sandbox.spec import SandboxSpec, run_arguments, validate

logger = logging.getLogger(__name__)

#: Output beyond this is truncated. A sandbox that talks too much is a problem
#: to notice, not a reason to fill the database.
MAX_OUTPUT_BYTES = 64 * 1024
#: How long `docker version` may take before the runtime counts as absent.
AVAILABILITY_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class SandboxResult:
    """What one container did."""

    started: bool
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    report: IsolationReport
    error: str | None = None

    @property
    def isolated(self) -> bool:
        return self.started and not self.timed_out and self.report.passed


class Sandbox(Protocol):
    """What the runtime needs from a sandbox, so it can be substituted."""

    name: str

    async def available(self) -> bool: ...

    async def probe(self, spec: SandboxSpec) -> SandboxResult: ...


class UnavailableSandbox:
    """The sandbox when no container runtime is installed.

    It refuses rather than pretending: a run that needs isolation is told there
    is none, and the runtime decides what to do about that.
    """

    name = "unavailable"

    def __init__(self, reason: str = "No container runtime is installed.") -> None:
        self.reason = reason

    async def available(self) -> bool:
        return False

    async def probe(self, spec: SandboxSpec) -> SandboxResult:
        return SandboxResult(
            started=False,
            exit_code=None,
            stdout="",
            stderr="",
            timed_out=False,
            report=unavailable_report(self.reason),
            error=self.reason,
        )


def _truncate(raw: bytes) -> str:
    text = raw[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    if len(raw) > MAX_OUTPUT_BYTES:
        text += f"\n… truncated at {MAX_OUTPUT_BYTES} bytes"
    return text


class ContainerSandbox:
    """Runs containers through `docker` (or any CLI-compatible runtime)."""

    name = "container"

    def __init__(self, command: str = "docker") -> None:
        self.command = command
        self._available: bool | None = None

    async def _run(
        self, arguments: list[str], *, timeout: float
    ) -> tuple[int | None, bytes, bytes]:
        process = await asyncio.create_subprocess_exec(
            self.command,
            *arguments,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # The container gets nothing on stdin, ever.
            stdin=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise
        return process.returncode, stdout, stderr

    async def available(self) -> bool:
        """True when the runtime answers. Cached: the answer rarely changes."""
        if self._available is not None:
            return self._available

        if shutil.which(self.command) is None:
            self._available = False
            return False
        try:
            code, _, _ = await self._run(
                ["version", "--format", "{{.Server.Version}}"], timeout=AVAILABILITY_TIMEOUT_SECONDS
            )
            self._available = code == 0
        except (TimeoutError, OSError):
            self._available = False
        return self._available

    async def remove(self, name: str) -> None:
        """Removes a container by name, ignoring "it was not there"."""
        try:
            await self._run(["rm", "--force", name], timeout=AVAILABILITY_TIMEOUT_SECONDS)
        except (TimeoutError, OSError):
            logger.warning("could not remove sandbox container", extra={"container": name})

    async def probe(self, spec: SandboxSpec) -> SandboxResult:
        """Starts one container and reads back what it could do."""
        arguments = run_arguments(spec)
        # The last gate before a container exists.
        validate(arguments)

        if not await self.available():
            return await UnavailableSandbox(f"`{self.command}` did not respond.").probe(spec)

        try:
            code, stdout, stderr = await self._run(arguments, timeout=spec.timeout_seconds)
        except TimeoutError:
            # The client was killed; the container may still be running.
            await self.remove(spec.name)
            return SandboxResult(
                started=True,
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=True,
                report=unavailable_report(
                    f"The sandbox did not finish within {spec.timeout_seconds}s."
                ),
                error="timeout",
            )
        except OSError as error:
            return SandboxResult(
                started=False,
                exit_code=None,
                stdout="",
                stderr="",
                timed_out=False,
                report=unavailable_report(f"The container runtime failed: {error}."),
                error=str(error),
            )

        out, err = _truncate(stdout), _truncate(stderr)
        if code != 0:
            return SandboxResult(
                started=True,
                exit_code=code,
                stdout=out,
                stderr=err,
                timed_out=False,
                report=unavailable_report(f"The sandbox exited with code {code}."),
                error=err.strip() or f"exit code {code}",
            )

        payload = _parse(out)
        if payload is None:
            return SandboxResult(
                started=True,
                exit_code=code,
                stdout=out,
                stderr=err,
                timed_out=False,
                report=unavailable_report("The sandbox did not report anything readable."),
                error="unreadable probe output",
            )

        report = evaluate(payload, expected_memory_mb=spec.memory_mb, expected_pids=spec.pids_limit)
        return SandboxResult(
            started=True,
            exit_code=code,
            stdout=out,
            stderr=err,
            timed_out=False,
            report=report,
        )


def _parse(output: str) -> dict[str, Any] | None:
    """Reads the probe's JSON, ignoring anything a runtime printed around it."""
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
