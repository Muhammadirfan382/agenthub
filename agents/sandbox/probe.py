"""Reports what this container can do, so the isolation can be checked.

This runs *inside* the sandbox. It is AgentHub's own code, not an agent's: no
agent code exists yet, and none may run until this box is proven to hold. It
takes no input, opens no files it was not given, and writes one JSON object to
stdout.

Everything here is a question about the container itself:

    Am I root?  Can I write to the filesystem?  Can I gain privileges?
    Can I reach the network?  Was anything from the host handed to me?

The answers are evaluated outside, in backend/app/sandbox/report.py.
"""

import contextlib
import json
import os
import socket
import sys
import tempfile
from pathlib import Path

#: Addresses the probe tries. Any success means egress was not actually denied.
NETWORK_TARGETS = (("1.1.1.1", 53), ("8.8.8.8", 53), ("169.254.169.254", 80))
NETWORK_TIMEOUT_SECONDS = 1.5

#: Host variables that must never be visible inside the sandbox.
FORBIDDEN_ENV_SUBSTRINGS = ("SECRET", "TOKEN", "PASSWORD", "KEY", "DATABASE_URL", "AWS_", "GITHUB_")

#: What a container is allowed to see: what the base image and the runtime set
#: for themselves. Anything else arrived from outside and is worth reporting.
EXPECTED_ENV = {"PATH", "HOME", "HOSTNAME", "LANG", "GPG_KEY"}
#: The Python base image sets a handful of PYTHON_* variables that describe its
#: own build. They vary between releases, so they are matched by prefix.
EXPECTED_ENV_PREFIXES = ("PYTHON",)


def can_write(path: str) -> bool:
    """True when a file can actually be created at `path`."""
    probe_file = Path(path) / ".agenthub-write-probe"
    try:
        probe_file.write_text("probe", encoding="utf-8")
    except OSError:
        return False
    with contextlib.suppress(OSError):
        probe_file.unlink()
    return True


def effective_capabilities() -> str | None:
    """The CapEff mask from /proc. "0000000000000000" means none at all."""
    try:
        for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("CapEff:"):
                return line.split()[1]
    except OSError:
        return None
    return None


def no_new_privileges() -> bool | None:
    """True when the kernel will refuse setuid escalation for this process."""
    try:
        for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("NoNewPrivs:"):
                return line.split()[1] == "1"
    except OSError:
        return None
    return None


def network_reachable() -> bool:
    """True if anything on the outside answered. It should not."""
    for host, port in NETWORK_TARGETS:
        try:
            with socket.create_connection((host, port), timeout=NETWORK_TIMEOUT_SECONDS):
                return True
        except OSError:
            continue
    return False


def dns_resolves() -> bool:
    try:
        socket.getaddrinfo("example.com", 80)
    except OSError:
        return False
    return True


def memory_limit_bytes() -> int | None:
    """The cgroup v2 memory ceiling, or None when there is no limit."""
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            raw = Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if raw == "max":
            return None
        try:
            value = int(raw)
        except ValueError:
            continue
        # Unlimited cgroup v1 reports a number close to 2**63.
        return None if value >= 2**62 else value
    return None


def process_limit() -> int | None:
    for path in ("/sys/fs/cgroup/pids.max", "/sys/fs/cgroup/pids/pids.max"):
        try:
            raw = Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if raw == "max":
            return None
        try:
            return int(raw)
        except ValueError:
            continue
    return None


def belongs_to_the_image(name: str) -> bool:
    return name in EXPECTED_ENV or name.startswith(EXPECTED_ENV_PREFIXES)


def environment_report() -> dict[str, object]:
    names = sorted(os.environ)
    # Only variables the image did not set itself can have come from the host,
    # so those are the ones examined for credential-shaped names. The image's
    # own GPG_KEY is a package-signing key, not one of ours.
    unexpected = [name for name in names if not belongs_to_the_image(name)]
    suspicious = [
        name
        for name in unexpected
        if any(fragment in name.upper() for fragment in FORBIDDEN_ENV_SUBSTRINGS)
    ]
    return {
        "names": names,
        "unexpected": unexpected,
        "suspicious": suspicious,
    }


def main() -> int:
    writable_root = can_write("/")
    writable_tmp = can_write(tempfile.gettempdir())

    report = {
        "probe": "agenthub-sandbox",
        "version": 1,
        "identity": {
            "uid": os.getuid(),
            "gid": os.getgid(),
            "is_root": os.getuid() == 0,
            "groups": sorted(os.getgroups()),
        },
        "filesystem": {
            "root_writable": writable_root,
            "tmp_writable": writable_tmp,
            "docker_socket_present": Path("/var/run/docker.sock").exists(),
            "host_mounts": sorted(
                str(path)
                for path in (Path("/host"), Path("/mnt/host"), Path("/workspace/host"))
                if path.exists()
            ),
        },
        "privileges": {
            "capabilities": effective_capabilities(),
            "no_new_privileges": no_new_privileges(),
        },
        "network": {
            "reachable": network_reachable(),
            "dns_resolves": dns_resolves(),
        },
        "limits": {
            "memory_bytes": memory_limit_bytes(),
            "process_limit": process_limit(),
        },
        "environment": environment_report(),
    }

    json.dump(report, sys.stdout, separators=(",", ":"), sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
