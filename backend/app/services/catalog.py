"""What agents may be configured with.

The catalog is server-side so the API can reject a configuration the frontend
would have blocked. Tool execution itself does not exist yet.
"""

from app.schemas.enums import CapabilityKey

# Model tiers routed through the future model gateway. No provider is connected.
MODEL_IDS: tuple[str, ...] = ("fast-small", "balanced-large", "reasoning-large")
MODEL_PROVIDER = "Model gateway"

# Each tool requires the capability it needs to do its work.
TOOL_CAPABILITIES: dict[str, CapabilityKey] = {
    "web_search": "web_access",
    "document_reader": "file_access",
    "sql_readonly": "database_access",
    "api_request": "api_access",
    "code_sandbox": "code_execution",
    "email_draft": "email_send",
    "chart_renderer": "tool_calling",
}

TOOL_IDS: tuple[str, ...] = tuple(TOOL_CAPABILITIES)
