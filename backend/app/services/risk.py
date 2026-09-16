"""Indicative risk derived from requested permissions.

Mirrors the frontend estimate so both show the same number, but the server
value is the authoritative one stored with the agent. It is a heuristic for
prioritisation, not a security control.
"""

from typing import Any

from app.schemas.enums import RISK_LEVELS, RISK_RANK, CapabilityKey, PermissionLevel, RiskLevel

BASE_SCORE: dict[str, int] = {"low": 15, "medium": 40, "high": 65, "critical": 85}

CAPABILITY_BASE_RISK: dict[str, RiskLevel] = {
    "web_access": "medium",
    "api_access": "high",
    "file_access": "medium",
    "database_access": "high",
    "tool_calling": "low",
    "code_execution": "critical",
    "email_send": "high",
}


def permission_risk(capability: CapabilityKey, level: PermissionLevel) -> RiskLevel:
    base = RISK_RANK[CAPABILITY_BASE_RISK[capability]]
    adjusted = base - 1 if level == "read_only" else base + 1 if level == "allowed" else base
    return RISK_LEVELS[max(0, min(len(RISK_LEVELS) - 1, adjusted))]


def derive_risk(permissions: list[dict[str, Any]]) -> tuple[RiskLevel, int]:
    granted = [p for p in permissions if p.get("level") != "denied"]
    if not granted:
        return "low", 5

    level: RiskLevel = "low"
    for permission in granted:
        risk = permission.get("risk", "low")
        if RISK_RANK[risk] > RISK_RANK[level]:
            level = risk

    breadth = min(10, len(granted) * 2)
    unguarded = sum(
        1
        for p in granted
        if RISK_RANK[p.get("risk", "low")] >= RISK_RANK["high"]
        and not p.get("requiresApproval", False)
    )
    score = min(100, BASE_SCORE[level] + breadth + unguarded * 3)
    return level, score
