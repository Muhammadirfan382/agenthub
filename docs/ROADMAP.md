# AgentHub roadmap

AgentHub is built **phase by phase**. Each phase ends with validation (tests, lint,
type check, build, security review, documentation update) and an explicit decision
before the next phase starts. Scope below is intentionally brief. Each phase is
designed in detail when it begins.

| Phase | Name | Status |
| --- | --- | --- |
| 0 | Initialization | ✅ Complete |
| 1 | Frontend | ✅ Complete (demonstration data; no backend integration) |
| 2 | Backend | ✅ Complete (agents and executions persisted; no auth) |
| 3 | Authentication / RBAC | ✅ Complete (password sign-in, sessions, roles) |
| 4 | Agent registry | ✅ Complete (manifests, versions, marketplace, installs) |
| 5 | Agent runtime | ✅ Complete (orchestration only; nothing is executed) |
| 6 | Docker sandbox | ⏳ Not started |
| 7 | AI/LLM integration | ⏳ Not started |
| 8 | Security layer | ⏳ Not started |
| 9 | Monitoring | ⏳ Not started |
| 10 | Production deployment | ⏳ Not started |

---

## Phase 0: Initialization

**Objective:** establish a clean, secure and verifiable foundation.

- Repository, directory structure, `.gitignore`, `.env.example` (placeholders only).
- Development rules (`CLAUDE.md`), `README.md`, `ARCHITECTURE.md`, this roadmap.
- Minimal React + TypeScript + Vite frontend with a status page; ESLint, Vitest.
- Minimal FastAPI backend with `GET /api/v1/health`; environment-based settings,
  pytest, Ruff, mypy.
- GitHub Actions CI for lint, type check, test and build.

## Phase 1: Frontend

**Objective:** build the application shell and core UI against a clearly labelled
mock API, using the old prototype only as a UX reference.

- Routing, layouts, design system, accessibility baseline.
- A typed API client layer through which all data flows (no component imports mock
  data directly).
- Loading, error and empty states for every view. A persistent "demo data" indicator
  while mocks are in use.

## Phase 2: Backend

**Objective:** a real, persistent API foundation.

- PostgreSQL connectivity, migrations, repository/service layering.
- Consistent error model, request IDs, pagination, input validation.
- Docker Compose for local PostgreSQL (Docker introduced here).
- Frontend switched from the mock API to the real one for the implemented resources.

**Delivered:** `agents` and `executions` tables with Alembic migrations; router →
service → repository layering; `{code, message, details}` errors; `X-Request-ID`
and security headers; offset pagination; server-side validation and risk scoring;
SQLite for local development and tests with PostgreSQL exercised in CI; a demo seed
script; and a frontend data-source switch (demo or API) surfaced in Settings.
See [BACKEND.md](BACKEND.md).

**Deliberately not in this phase:** authentication, authorization, rate limiting,
CORS for a separate origin, audit logging, and anything that actually runs an
agent.

## Phase 3: Authentication / RBAC

**Objective:** know who is making each request and enforce what they may do.

- User identity, secure sessions or tokens, logout, password/MFA or SSO strategy.
- Organizations, memberships and roles.
- Server-side authorization on every endpoint; CSRF protection; authentication rate
  limiting; negative tests for access control.

**Delivered:** accounts created out of band (`scripts/create_user.py`; no public
sign-up), scrypt password hashing, opaque server-side sessions in HttpOnly
cookies with absolute and idle expiry, CSRF tokens on every unsafe request,
per-account and per-address sign-in throttling, organizations with memberships
and four roles, authorization checked on every endpoint, organization scoping in
every query, and a frontend with a sign-in page, route guard, role-aware controls
and a members screen. See [BACKEND.md](BACKEND.md) §4.

**Strategy chosen:** passwords plus server-side sessions. MFA and SSO are
deliberately deferred — both need email or an identity provider, neither of which
exists yet — and so are password reset and email verification.

## Phase 4: Agent registry

**Objective:** model agents and what they are allowed to need.

- Agent manifests: capabilities, tools, required permissions with risk levels,
  model requirements, resource limits.
- Versions, publishing states, marketplace listing and search.
- Installation into an organization with explicit, scoped permission grants.

**Delivered:** immutable published versions carrying the full manifest;
`private` / `organization` / `public` visibility with the marketplace listing
only the newest published version; search, category, tag and verified filters;
and installations whose grants start denied, can never exceed or weaken what the
manifest asked for, and report the tools they leave unusable. See
[BACKEND.md](BACKEND.md) §5.

**Deliberately not in this phase:** enforcing a grant at runtime (nothing runs
yet), upgrading an installation to a newer version in one click, and real
verification - the verification label is stored, not earned.

## Phase 5: Agent runtime

**Objective:** orchestrate agent executions safely, without running untrusted code on
the host.

- Execution lifecycle and durable job orchestration.
- Human approval pause/resume for high-risk actions.
- Budgets, cancellation, organization-wide kill switch.
- Execution events and streaming status to the frontend.

**Delivered:** a database-backed queue with claim, heartbeat and reclaim; a step
engine that records a timeline, logs and tool calls; per-run budgets for time,
tokens and tool calls; approval pauses with approve/refuse and a note;
cancellation at the next step boundary; an organization-wide kill switch that
administrators engage and only owners release; and a server-sent event stream
with polling behind it. See [BACKEND.md](BACKEND.md) §6.

**Deliberately not in this phase:** running anything. No agent code, model call
or tool invocation happens — the sandbox is Phase 6 and the model gateway is
Phase 7 — so every run is recorded as `simulation` and tool calls as
`simulated`. Also absent: scheduled triggers, retries of failed runs, and
per-organization concurrency limits.

## Phase 6: Docker sandbox

**Objective:** isolate agent execution.

- Ephemeral, non-root, unprivileged, resource-limited containers per execution.
- No host mounts, no Docker socket, no ambient credentials or environment variables.
- Network egress denied by default; allowed only through gateways.
- Tests that verify isolation guarantees.

**Delivered:** a sandbox image with a fixed non-root account and an in-container
probe; a container spec that is ephemeral, read-only, capability-free,
network-less and resource-limited, with no mounts, socket or environment passed
in; a runner with timeouts, forced cleanup and capped output; 13 isolation
checks judged outside the container; and an engine that starts and checks a
container before every run, fails the run when the box does not hold, and
records the report on it. Settings → Runtime shows the configuration and can run
the check on demand. See [BACKEND.md](BACKEND.md) §7.

**How it is verified:** the container arguments, the runner (against a stand-in
runtime) and the engine's decisions are tested on any machine. Starting real
containers needs a daemon, so those tests run in the `sandbox` CI job, which
fails rather than skips when it cannot run them. They were **not** executed on
the development machine this phase was built on, which has no container
runtime.

**Deliberately not in this phase:** running anything inside the sandbox (there
is no agent program until the model gateway exists), an egress gateway (the
network is simply off), a custom seccomp profile, and stronger isolation such as
gVisor or microVMs. Without a runtime, runs still proceed as recorded
simulations unless `REQUIRE_SANDBOX=true`.

## Phase 7: AI/LLM integration

**Objective:** connect agents to language models through a controlled gateway.

- Provider-agnostic model interface with modular adapters.
- Model gateway: routing, streaming, usage and cost metering, budgets, rate limits.
- Tool calling mediated by the tool gateway with schema validation and permission
  checks.
- LLM credentials server-side only.

**Delivered:** a provider-neutral model interface with Claude and OpenAI
adapters on their official SDKs; tier routing configured per deployment
(Claude Haiku 4.5 / Sonnet 5 / Opus 5 by default); a gateway that enforces
per-organization request rates and daily token budgets and writes every request
to a usage ledger with an estimated cost; a tool gateway that validates every
model tool call against the agent's grants, a strict schema and human approval;
a model-driven run loop that resumes after approvals and worker loss without
re-asking the model; per-step commits and heartbeats so long model calls are
safe; and the task, conversation, route and cost shown on each run, with the
gateway's state in Settings → Runtime. See [BACKEND.md](BACKEND.md) §8.

**How it is verified:** adapters against each SDK's own types with a recording
client, and whole runs against a scripted provider, on any machine. **No real
provider was called** while this phase was built: no credentials were
available. `python -m scripts.model_smoke_test --yes` checks real routes once a
key is configured.

**Deliberately not in this phase:** executing any tool (every allowed call is
recorded as not executed until Phase 8's SSRF and egress protection exists),
token-by-token streaming to the browser, per-agent instruction prompts, prices
for OpenAI models, and rate limits shared across processes.

## Phase 8: Security layer

**Objective:** harden the platform against realistic threats.

- Policy engine for agent actions; prompt-injection defence in depth with adversarial
  evaluations.
- Secret management integration, SSRF protection, security headers/CSP.
- Dependency and secret scanning in CI; SHA-pinned CI actions; threat model and
  security review.

**Delivered:** a policy engine that enforces what each agent declared -
`networkEgress`, `allowedDomains` and approval by risk level, none of which the
runtime honoured before; an SSRF-safe egress gateway (https only, allow-listed
hosts, public addresses only, connections pinned against DNS rebinding, no
redirects, bounded size and time) which is the only way a request leaves the
server; `api_request` running through it as a read-only GET, with what it
fetched handed to the model as labelled untrusted content; an append-only audit
log with an admin-only read API and an Audit log screen; a strict CSP on the
built app and on API responses, plus cross-origin isolation and HSTS; per-client
write rate limiting; secrets from file mounts (`SECRETS_DIR`); and a CI
`security` job (pip-audit, npm audit, gitleaks over full history) with every
action pinned to a commit SHA and Dependabot proposing updates. Adversarial
containment evaluations, a [threat model](THREAT_MODEL.md) and a
[security review](SECURITY_REVIEW.md) ship with it. See [BACKEND.md](BACKEND.md) §9.

**How it is verified:** the egress gateway against a replaced resolver and a
recording transport; the policy engine and untrusted wrapper as pure functions;
the audit log, headers, write limit and secrets through the API; and
`test_containment.py`, where a scripted fully-hijacked model tries to
exfiltrate, reach cloud metadata, write, and smuggle instructions back - each
scenario asserting nothing left the server. The production build was loaded in
a browser to confirm it runs under the strict CSP with no violations.

**Deliberately not in this phase:** executing any tool other than
`api_request`, preventing (rather than containing) prompt injection, live
adversarial evaluations against real models - which need a provider key and
were not run - rate limits shared across processes, vault integration, and a
custom seccomp profile. No independent review or penetration test was done.

## Phase 9: Monitoring

**Objective:** make the system observable and auditable.

- Structured logging with redaction, metrics, distributed tracing.
- Health and readiness checks, alerting, audit and security dashboards.

## Phase 10: Production deployment

**Objective:** run AgentHub reliably in production.

- Container images, staging and production environments, CD pipeline with rollback.
- Managed PostgreSQL/Redis, backups and restore testing, secrets manager.
- Operational runbooks, incident response, performance and load testing, final
  security sign-off.
