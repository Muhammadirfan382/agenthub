"""The policy engine: whether an agent may take an action, decided outside the model.

The model proposes; this module disposes. It sees only facts the platform
controls - the agent's grants and declared security policy, the tool and its
already schema-validated arguments - never the model's reasoning or any text a
tool returned. A prompt-injected model can ask for anything; it cannot change
what these rules say.

Rules run in a fixed order and the first one that decides wins:

1. ``grant`` - the tool's capability must be granted (not ``denied``).
2. ``network_mode`` - a network capability is refused when the agent's policy
   says ``networkEgress: none``.
3. ``read_only`` - only GET requests may leave the server in this release.
4. ``egress`` - a URL must pass every static egress check (https, no
   credentials, default port, a host name that is exactly one of the agent's
   allowed domains). DNS and address checks happen again at request time.
5. ``approval`` - a person must approve when the grant says so **or** when the
   capability's risk is one the agent's policy lists in ``approvalRequiredFor``.
6. ``allow``.

Every decision names the rule that made it, so it can be audited and shown.
"""

from dataclasses import dataclass
from typing import Any, Literal

from app.runtime.plan import Step
from app.security.egress import EgressBlocked, check_url

Effect = Literal["allow", "deny", "require_approval"]

#: Capabilities whose tools reach the network.
NETWORK_CAPABILITIES = frozenset({"web_access", "api_access"})
#: Tools whose arguments name a URL the egress gateway would fetch.
URL_TOOLS = frozenset({"api_request"})


@dataclass(frozen=True)
class PolicyDecision:
    effect: Effect
    #: The rule that decided: grant, network_mode, read_only, egress.<rule>,
    #: approval or allow.
    rule: str
    reason: str


@dataclass(frozen=True)
class AgentPolicy:
    """The parts of an agent's declared security policy the engine enforces."""

    network_egress: str
    allowed_domains: list[str]
    approval_required_for: list[str]

    @classmethod
    def from_agent(cls, security_policy: dict[str, Any] | None) -> "AgentPolicy":
        policy = security_policy or {}
        return cls(
            # Anything but an explicit allow-list means no egress at all.
            network_egress=str(policy.get("networkEgress", "none")),
            allowed_domains=[str(domain) for domain in policy.get("allowedDomains") or []],
            approval_required_for=[str(level) for level in policy.get("approvalRequiredFor") or []],
        )


def decide(
    tool: str, arguments: dict[str, Any], grant: Step, policy: AgentPolicy
) -> PolicyDecision:
    """Decides one tool call. Pure: no I/O, no clock, no model input."""
    if grant.capability is None or grant.level == "denied":
        return PolicyDecision("deny", "grant", f"{tool} needs a capability that is not granted.")

    if grant.capability in NETWORK_CAPABILITIES and policy.network_egress != "allow_list":
        return PolicyDecision(
            "deny", "network_mode", "This agent's security policy allows no network egress."
        )

    if tool in URL_TOOLS:
        if str(arguments.get("method", "GET")).upper() != "GET":
            return PolicyDecision(
                "deny", "read_only", "Only GET requests may leave the server in this release."
            )
        try:
            check_url(str(arguments.get("url", "")), policy.allowed_domains)
        except EgressBlocked as blocked:
            return PolicyDecision("deny", f"egress.{blocked.rule}", blocked.message)

    reasons = []
    if grant.requires_approval:
        reasons.append("the grant for this capability requires approval")
    if grant.risk in policy.approval_required_for:
        reasons.append(f"the agent's policy requires approval for {grant.risk}-risk actions")
    if reasons:
        return PolicyDecision(
            "require_approval", "approval", "A person must approve: " + "; ".join(reasons) + "."
        )

    return PolicyDecision("allow", "allow", "Allowed by the agent's grants and security policy.")
