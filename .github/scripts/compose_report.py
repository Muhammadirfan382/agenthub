"""Explains why the CI compose stack did not come up, without the raw log.

    python .github/scripts/compose_report.py <compose args...>

Called with the same `docker compose` arguments CI used. For every service
that is not running and healthy it emits an error annotation with its state
and last log lines, and it writes all of them to the job summary. The output
of the one-shot migration (removed after it runs) is read from
$RUNNER_TEMP/migrate.log when present. Never fails the step: it only reports.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

TAIL = 12
MAX_ANNOTATIONS = 10


def compose(args: list[str], *extra: str) -> str:
    result = subprocess.run(
        ["docker", "compose", *args, *extra],
        capture_output=True,
        text=True,
        check=False,
    )
    return (result.stdout or "") + (result.stderr or "")


def annotation(text: str) -> str:
    # GitHub's workflow-command encoding for multi-line messages.
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def tail(text: str, lines: int = TAIL) -> str:
    kept = [line for line in text.splitlines() if line.strip()]
    return "\n".join(kept[-lines:])


def main(args: list[str]) -> int:
    problems: list[tuple[str, str]] = []
    sections: list[str] = ["## Compose stack", ""]

    migrate_log = Path(os.environ.get("RUNNER_TEMP", ".")) / "migrate.log"
    if migrate_log.exists():
        text = migrate_log.read_text(encoding="utf-8", errors="replace")
        sections += ["### migrate", "```", tail(text, 40), "```", ""]
        if "Traceback" in text or "Error" in text or "error" in text.lower():
            problems.append(("migrate: failed", tail(text)))

    raw = compose(args, "ps", "--all", "--format", "json")
    services = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            services.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    for service in services:
        name = service.get("Service", "?")
        state = service.get("State", "?")
        health = service.get("Health", "")
        exit_code = service.get("ExitCode", "")
        logs = compose(
            args, "logs", "--no-color", "--no-log-prefix", "--tail", "60", name
        )
        status = f"{state}{' / ' + health if health else ''}"
        if state != "running":
            status += f" (exit {exit_code})"
        sections += [f"### {name}: {status}", "```", tail(logs, 40), "```", ""]
        if state != "running" or health not in ("", "healthy"):
            problems.append((f"{name}: {status}", tail(logs)))

    if not services:
        problems.append(
            ("no containers", tail(raw) or "docker compose ps returned nothing")
        )

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(sections) + "\n")
    print("\n".join(sections))

    for title, body in problems[:MAX_ANNOTATIONS]:
        # In a property value, ':' and ',' separate fields and must be encoded.
        safe_title = annotation(title).replace(":", "%3A").replace(",", "%2C")
        print(f"::error title={safe_title}::{annotation(body or '(no output)')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
