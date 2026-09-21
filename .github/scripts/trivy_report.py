"""Turns Trivy JSON reports into a readable CI result.

    python .github/scripts/trivy_report.py trivy-backend.json trivy-web.json ...

Writes every finding to the job summary (visible on the run page, including
to people who are not signed in, for a public repository), emits the first
findings as error annotations, and exits non-zero if there are any. The
policy itself - HIGH and CRITICAL, fixed versions available - is applied by
the Trivy flags in ci.yml; this script only reports.
"""

import json
import os
import sys
from pathlib import Path

#: GitHub shows at most 10 error annotations per step.
MAX_ANNOTATIONS = 10


def findings(report_path: Path) -> list[dict[str, str]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    image = report.get("ArtifactName", report_path.stem)
    rows: list[dict[str, str]] = []
    for result in report.get("Results") or []:
        for vulnerability in result.get("Vulnerabilities") or []:
            rows.append(
                {
                    "image": image,
                    "target": result.get("Target", ""),
                    "package": vulnerability.get("PkgName", ""),
                    "installed": vulnerability.get("InstalledVersion", ""),
                    "fixed": vulnerability.get("FixedVersion", ""),
                    "id": vulnerability.get("VulnerabilityID", ""),
                    "severity": vulnerability.get("Severity", ""),
                    "title": (vulnerability.get("Title") or "")[:90],
                }
            )
    return rows


def escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def main(paths: list[str]) -> int:
    rows = [row for path in paths for row in findings(Path(path))]
    rows.sort(
        key=lambda r: (r["image"], r["severity"] != "CRITICAL", r["package"], r["id"])
    )

    lines = ["## Image vulnerability scan", ""]
    if not rows:
        lines.append("No fixable HIGH or CRITICAL vulnerabilities in any image.")
    else:
        lines += [
            (
                f"{len(rows)} fixable HIGH/CRITICAL findings. Upgrade the package (or the "
                "base image that ships it) to the fixed version."
            ),
            "",
            "| Image | Where | Package | Installed | Fixed in | Severity | ID | Title |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        lines += [
            "| "
            + " | ".join(
                escape(r[k])
                for k in (
                    "image",
                    "target",
                    "package",
                    "installed",
                    "fixed",
                    "severity",
                    "id",
                    "title",
                )
            )
            + " |"
            for r in rows
        ]

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    print("\n".join(lines))

    for row in rows[:MAX_ANNOTATIONS]:
        print(
            f"::error title={row['severity']} {row['id']} in {row['image']}::"
            f"{row['package']} {row['installed']} -> fixed in {row['fixed']} ({row['target']})"
        )
    if len(rows) > MAX_ANNOTATIONS:
        print(
            f"::error title=More findings::{len(rows) - MAX_ANNOTATIONS} more in the job summary"
        )
    return 1 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
