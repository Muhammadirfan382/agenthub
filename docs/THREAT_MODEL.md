# AgentHub threat model

**Status:** written in Phase 8 by the people building AgentHub, against the code
as it stands. It has not been reviewed by anyone independent. Every mitigation
below names where it lives, so each claim can be checked against the code.

## 1. What is being protected

| Asset | Why it matters |
| --- | --- |
| Provider credentials (`AGENTHUB_ANTHROPIC_API_KEY`, `AGENTHUB_OPENAI_API_KEY`) | Spend money, and read whatever the account can |
| Database credentials (`DATABASE_URL`) | Every organization's data |
| Sessions and passwords | Impersonation of any member |
| Organization data: agents, runs, conversations, fetched content | Confidential to that organization |
| The host and its network (cloud metadata, internal services) | Reachable from the server if anything lets a request through |
| The audit log | The record of who allowed what; worthless if it can be altered |
| Model spend | Unbounded usage is a financial denial of service |

## 2. Who might attack, and how

| Actor | Can do | Wants |
| --- | --- | --- |
| Anonymous internet user | Reach the API | Sign in, enumerate accounts, exhaust resources |
| Member of an organization | Everything their role allows | More than their role allows; another organization's data |
| **Author of content an agent reads** | Put text in a page or API response an agent fetches | Hijack the agent: exfiltrate data, reach internal hosts, act beyond its grants |
| **A hijacked model** | Emit any text and any tool call, in any order | The same, from inside the loop |
| Publisher of a marketplace agent | Describe an agent others install | Obtain grants the installer did not intend |
| Supply chain | Change a dependency or a CI action | Run code in the build or at runtime |

The model is assumed hostile at all times. Nothing it says is trusted: its text
is displayed as text, and its tool calls are requests that code outside the
model decides.

## 3. Trust boundaries

```
browser ──(session cookie + CSRF)──▶ API ──▶ database
                                      │
                                      ├──▶ model gateway ──▶ Anthropic / OpenAI     (credentials cross here, outbound only)
                                      │
                                      ├──▶ tool gateway ──▶ policy engine ──▶ egress gateway ──▶ allow-listed HTTPS hosts
                                      │
                                      └──▶ container runtime ──▶ sandbox (no network, no mounts, no env)
```

Untrusted data enters at four points: the browser, model output, fetched
content, and a marketplace manifest.

## 4. Threats and mitigations

### Spoofing

| Threat | Mitigation | Where |
| --- | --- | --- |
| Guessing passwords | scrypt; per-account and per-address sign-in throttling | `core/security.py`, `services/login_guard.py` |
| Learning which accounts exist | One failure message; a dummy hash for unknown addresses; the failed-login audit write happens after the response so its cost cannot be timed | `services/auth_service.py`, `api/v1/auth.py` |
| Stealing a session | Opaque tokens stored as hashes; HttpOnly, SameSite=Strict cookies; idle and absolute expiry | `services/auth_service.py` |
| Cross-site requests | CSRF token echoed in a header on every unsafe request | `api/deps.py` |

### Tampering

| Threat | Mitigation | Where |
| --- | --- | --- |
| Altering the audit record | Append-only table; no update or delete endpoint (tested) | `security/audit.py`, `api/v1/audit.py` |
| Changing a published agent after install | Published manifests are immutable versions | `services/registry_service.py` |
| Fetched text pretending to be the platform | Content wrapped in a labelled tag; lookalike tags neutralised; control characters removed | `security/untrusted.py` |
| Moving a CI action to malicious code | Every action pinned to a commit SHA; Dependabot proposes updates | `.github/workflows/ci.yml` |

### Repudiation

| Threat | Mitigation | Where |
| --- | --- | --- |
| "Who approved this?" having no answer | Sign-ins, role changes, kill switch, approvals, agent and installation changes, policy refusals and every outbound request are audited | `security/audit.py` and callers |

### Information disclosure

| Threat | Mitigation | Where |
| --- | --- | --- |
| **SSRF**: a hijacked model fetching cloud metadata or internal services | https only; no credentials or custom ports in URLs; host must exactly match an allowed domain; IP literals refused; every resolved address must be public (incl. IPv4-mapped, 6to4, Teredo forms); the socket is pinned to the checked address while TLS verifies the real name (no DNS rebinding); redirects never followed | `security/egress.py` |
| Exfiltration to an attacker's server | The same allow-list: only hosts the agent's owner listed are reachable | `security/egress.py`, `security/policy.py` |
| Keys leaking through logs or errors | Keys are `SecretStr`; SDK exceptions are not chained; prompts, answers and keys are never logged | `core/config.py`, `llm/` |
| Ambient credentials used unintentionally | Only `AGENTHUB_`-prefixed key variables are read; SDKs pinned to official endpoints; ambient OpenAI org/project/admin values dropped | `core/config.py`, `llm/providers/` |
| Cross-organization reads | Organization scope in every query; foreign ids answer 404 | repositories, services |
| Sandbox escape to host secrets | No env, mounts or socket in the container; 13 isolation checks before each run | `sandbox/` |
| Browser-side script injection | Model and fetched text rendered as plain text; strict CSP on the built app and on API responses | `features/executions/components/Conversation.tsx`, `src/config/contentSecurityPolicy.ts`, `core/middleware.py` |
| Secrets in the repository | Secret scanning over full history in CI (gitleaks); placeholders only in `.env.example` | CI `security` job |

### Denial of service

| Threat | Mitigation | Where |
| --- | --- | --- |
| Runaway model spend | Per-run token, turn and tool-call budgets; per-organization requests per minute and daily token budget | `runtime/`, `llm/gateway.py` |
| Scripted write floods | Per-client limit on state-changing requests | `core/middleware.py` |
| Huge or slow responses to an agent | Response size and time limits; binary content refused | `security/egress.py` |
| Runaway containers | Memory, CPU, process and time limits | `sandbox/spec.py` |

### Elevation of privilege

| Threat | Mitigation | Where |
| --- | --- | --- |
| **Prompt injection turning into action** | The policy engine decides from facts the model cannot change: grants, the agent's declared egress mode, allowed domains and approval-by-risk policy; read-only egress (GET only); tools not granted are never offered and refused if called | `security/policy.py`, `runtime/tools.py` |
| A tool call a person should have seen | Approval required by the grant **or** by the agent's `approvalRequiredFor` risk levels | `security/policy.py` |
| Role escalation | Server-side role matrix on every endpoint; nobody grants a role above their own | `services/authorization.py` |
| An installed agent taking more than granted | Grants can never exceed the manifest; nothing granted by default | `services/registry_service.py` |

### Deployment (Phase 10)

| Threat | Mitigation | Where |
| --- | --- | --- |
| A sandbox escape reaching the host | Rootless Docker owned by `agenthub-sandbox`, an account with no secrets. The worker reaches the daemon only through a socket group. Containers keep every Phase 6 guarantee. | `setup-host.sh`, `agenthub-worker.service` |
| A compromised service container | Read-only, non-root, no capabilities, no-new-privileges, bounded memory and processes. No runtime socket anywhere. The API holds no provider keys and sits on an internal network. | `compose.yml` |
| A compromised CD pipeline | The SSH key is a forced command running one script that accepts only image digests under one prefix. Host code changes only by `setup-host.sh`. Production needs approval. | `agenthub-deploy`, `deploy.yml` |
| A tampered image | Built and scanned in CI, pushed by digest, build provenance attested. **Not verified at deploy time** (see §5). | `ci.yml` |
| Secrets on the host | One file per value. The API's and the worker's secrets are in separate directories with separate groups. Never in images or logs. | `DEPLOYMENT.md` §2 |
| Stolen backups | Root-only directory. Off-host copies must be encrypted (documented, not enforced). | `agenthub-backup` |
| Losing the host | Daily backups, weekly restore checks, restore onto a new host. A managed database is recommended. | `OPERATIONS.md` |

## 5. What is not mitigated

Stated plainly, because a threat model that only lists defences is marketing.

- **A model can still be fooled within its grants.** Containment bounds what a
  hijacked agent can *do*; it does not stop it from giving a wrong answer or
  summarising a hostile page misleadingly. Live evaluations of real models
  against injection have not been run (no provider key was available).
- **Allowed domains are trusted completely.** If an allowed host serves hostile
  content, or an attacker controls a path on it, the agent will read that.
- **Query strings reach the audit log.** URLs an agent requests are recorded
  (truncated). A secret a user put in a task could end up in a URL and so in the log.
- **Rate limits are per process.** Several processes each allow the full rate;
  a shared store (Redis) is needed for real limits at scale.
- **Forwarded-for trust is configuration.** Real client addresses depend on
  `FORWARDED_ALLOW_IPS` naming only the reverse proxy. A mistake there either
  merges every anonymous client into one limiter key or lets clients choose
  their address.
- **The development API docs page has no CSP.** It exists only in development.
- **Secrets from files, not a vault.** `SECRETS_DIR` supports Docker and
  Kubernetes secret mounts; there is no integration with a vault service.
- **Custom seccomp, user-namespace remapping and gVisor** are not in place for
  the sandbox (Docker's default seccomp applies).
- **Provenance is attested but not verified at deploy.** Anyone able to push
  under the allowed registry prefix can ship an image the host will accept.
- **The API container has a general outbound route** (needed for a managed
  database). Restrict it with host egress rules.
- **One host.** No failover: recovery is a restore.
- **No independent review or penetration test** has been done.

## 6. When to revisit

Before any new tool executes; before any tool may write or POST; when agents
gain memory or files; when a second process or host is added; before the first
real deployment (Phase 10).
