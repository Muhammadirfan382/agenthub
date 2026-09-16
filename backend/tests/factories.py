"""Request payload builders for tests."""

from typing import Any

from app.schemas.enums import CAPABILITY_KEYS


def denied_permissions() -> list[dict[str, Any]]:
    return [
        {"capability": capability, "level": "denied", "requiresApproval": False, "scope": ""}
        for capability in CAPABILITY_KEYS
    ]


def agent_payload(**overrides: Any) -> dict[str, Any]:
    """A valid, minimal, deny-everything agent configuration."""
    payload: dict[str, Any] = {
        "name": "Test Agent",
        "description": "An agent used by the backend test suite for validation.",
        "category": "research",
        "tags": ["test"],
        "version": "1.0.0",
        "model": {
            "provider": "Model gateway",
            "model": "balanced-large",
            "temperature": 0.2,
            "maxOutputTokens": 4096,
        },
        "tools": [],
        "permissions": denied_permissions(),
        "resourceLimits": {
            "maxRuntimeSeconds": 300,
            "maxMemoryMb": 512,
            "maxTokensPerRun": 50000,
            "maxToolCalls": 20,
        },
        "securityPolicy": {
            "sandbox": "strict",
            "networkEgress": "none",
            "allowedDomains": [],
            "approvalRequiredFor": ["high", "critical"],
            "auditLogging": True,
        },
    }
    payload.update(overrides)
    return payload


def grant(payload: dict[str, Any], capability: str, **patch: Any) -> dict[str, Any]:
    """Return a copy of the payload with one capability changed."""
    permissions = [
        {**permission, **patch} if permission["capability"] == capability else permission
        for permission in payload["permissions"]
    ]
    return {**payload, "permissions": permissions}
