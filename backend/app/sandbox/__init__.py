"""The execution sandbox: what a container may be, and how it is checked."""

from app.sandbox.report import Check, IsolationReport, evaluate, unavailable_report
from app.sandbox.runner import ContainerSandbox, Sandbox, SandboxResult, UnavailableSandbox
from app.sandbox.spec import SandboxSpec, build_spec, run_arguments, validate

__all__ = [
    "Check",
    "ContainerSandbox",
    "IsolationReport",
    "Sandbox",
    "SandboxResult",
    "SandboxSpec",
    "UnavailableSandbox",
    "build_spec",
    "evaluate",
    "run_arguments",
    "unavailable_report",
    "validate",
]
