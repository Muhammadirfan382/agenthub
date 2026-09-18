"""Judging what came back from inside the sandbox.

The probe reports facts; this decides whether those facts are acceptable. Each
check is one guarantee from spec.py, written as a question with a yes/no
answer, so a failure names exactly which promise was not kept.

A check that cannot be evaluated counts as a failure. "The container did not
tell us whether it was root" is not a pass.
"""

from dataclasses import dataclass
from typing import Any

#: A container with no capabilities reports this mask.
NO_CAPABILITIES = "0000000000000000"


@dataclass(frozen=True)
class Check:
    id: str
    label: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class IsolationReport:
    checks: list[Check]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if not check.passed]

    def summary(self) -> str:
        total = len(self.checks)
        kept = total - len(self.failures)
        return f"{kept} of {total} isolation checks passed"

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "summary": self.summary(),
            "checks": [
                {
                    "id": check.id,
                    "label": check.label,
                    "passed": check.passed,
                    "detail": check.detail,
                }
                for check in self.checks
            ],
        }


def _section(payload: dict[str, Any], name: str) -> dict[str, Any]:
    section = payload.get(name)
    return section if isinstance(section, dict) else {}


def _reported_list(section: dict[str, Any], name: str) -> list[Any] | None:
    """The list the probe sent, or None when it sent nothing usable."""
    value = section.get(name)
    return value if isinstance(value, list) else None


def evaluate(
    payload: dict[str, Any], *, expected_memory_mb: int, expected_pids: int
) -> IsolationReport:
    """Turns one probe result into the list of guarantees kept or broken."""
    identity = _section(payload, "identity")
    filesystem = _section(payload, "filesystem")
    privileges = _section(payload, "privileges")
    network = _section(payload, "network")
    limits = _section(payload, "limits")
    environment = _section(payload, "environment")

    uid = identity.get("uid")
    capabilities = privileges.get("capabilities")
    no_new_privileges = privileges.get("no_new_privileges")
    memory_bytes = limits.get("memory_bytes")
    process_limit = limits.get("process_limit")
    # A list the container actually sent, or None when it said nothing. The
    # difference matters: "no host mounts" is a fact the probe has to state,
    # and an absent field is silence, not a clean bill of health.
    suspicious_env = _reported_list(environment, "suspicious")
    unexpected_env = _reported_list(environment, "unexpected")
    host_mounts = _reported_list(filesystem, "host_mounts")

    checks = [
        Check(
            id="non_root",
            label="Runs as an unprivileged user",
            passed=isinstance(uid, int) and uid != 0,
            detail=f"uid {uid}" if uid is not None else "the container did not report its user",
        ),
        Check(
            id="read_only_root",
            label="Root filesystem is read-only",
            passed=filesystem.get("root_writable") is False,
            detail="/ is not writable"
            if filesystem.get("root_writable") is False
            else "/ accepted a write",
        ),
        Check(
            id="writable_scratch",
            label="Has a writable scratch directory",
            passed=filesystem.get("tmp_writable") is True,
            # Both strings name a path inside the container, not on the host.
            detail="/tmp is writable"  # noqa: S108
            if filesystem.get("tmp_writable") is True
            else "/tmp could not be written; the sandbox is unusable",  # noqa: S108
        ),
        Check(
            id="no_capabilities",
            label="Holds no Linux capabilities",
            passed=capabilities == NO_CAPABILITIES,
            detail=f"CapEff {capabilities}" if capabilities else "capabilities were not reported",
        ),
        Check(
            id="no_escalation",
            label="Cannot gain privileges",
            passed=no_new_privileges is True,
            detail="NoNewPrivs is set" if no_new_privileges is True else "NoNewPrivs is not set",
        ),
        Check(
            id="no_network",
            label="Cannot reach the network",
            passed=network.get("reachable") is False,
            detail="no route out"
            if network.get("reachable") is False
            else "something on the outside answered",
        ),
        Check(
            id="no_dns",
            label="Cannot resolve names",
            passed=network.get("dns_resolves") is False,
            detail="DNS does not resolve"
            if network.get("dns_resolves") is False
            else "DNS resolved a public name",
        ),
        Check(
            id="no_container_socket",
            label="Cannot reach the container runtime",
            passed=filesystem.get("docker_socket_present") is False,
            detail="no socket inside"
            if filesystem.get("docker_socket_present") is False
            else "the container socket is visible inside the sandbox",
        ),
        Check(
            id="no_host_mounts",
            label="Nothing from the host is mounted",
            passed=host_mounts == [],
            detail="no host paths"
            if host_mounts == []
            else (
                f"found {', '.join(str(mount) for mount in host_mounts)}"
                if host_mounts
                else "the container did not list its mounts"
            ),
        ),
        Check(
            id="no_secret_environment",
            label="No host secrets in the environment",
            passed=suspicious_env == [],
            detail="nothing sensitive"
            if suspicious_env == []
            else (
                f"saw {', '.join(sorted(str(name) for name in suspicious_env))}"
                if suspicious_env
                else "the container did not list its environment"
            ),
        ),
        Check(
            id="clean_environment",
            label="Only the image's own environment is present",
            passed=unexpected_env == [],
            detail="expected variables only"
            if unexpected_env == []
            else (
                f"unexpected: {', '.join(sorted(str(name) for name in unexpected_env))}"
                if unexpected_env
                else "the container did not list its environment"
            ),
        ),
        Check(
            id="memory_limit",
            label="Memory is capped",
            passed=isinstance(memory_bytes, int)
            and memory_bytes <= expected_memory_mb * 1024 * 1024,
            detail=f"{memory_bytes} bytes"
            if isinstance(memory_bytes, int)
            else "no memory limit was applied",
        ),
        Check(
            id="process_limit",
            label="Process count is capped",
            passed=isinstance(process_limit, int) and process_limit <= expected_pids,
            detail=f"{process_limit} processes"
            if isinstance(process_limit, int)
            else "no process limit was applied",
        ),
    ]
    return IsolationReport(checks=checks)


def unavailable_report(reason: str) -> IsolationReport:
    """Used when no container runtime answered at all."""
    return IsolationReport(
        checks=[
            Check(
                id="runtime_available",
                label="A container runtime is available",
                passed=False,
                detail=reason,
            )
        ]
    )
