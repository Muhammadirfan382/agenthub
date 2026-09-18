"""Choosing the sandbox the runtime uses.

One place decides, so tests can substitute a sandbox and the rest of the engine
never has to know which one it got.
"""

from app.core.config import Settings
from app.sandbox import ContainerSandbox, Sandbox, UnavailableSandbox

_override: Sandbox | None = None


def get_sandbox(settings: Settings) -> Sandbox:
    if _override is not None:
        return _override
    if not settings.sandbox_enabled:
        return UnavailableSandbox("Sandboxing is switched off (SANDBOX_ENABLED=false).")
    return ContainerSandbox(settings.sandbox_command)


def use_sandbox(sandbox: Sandbox | None) -> None:
    """Substitutes the sandbox. Tests use this; nothing else should."""
    global _override
    _override = sandbox
