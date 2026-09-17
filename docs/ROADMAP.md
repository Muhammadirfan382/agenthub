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

## Phase 7: AI/LLM integration

**Objective:** connect agents to language models through a controlled gateway.

- Provider-agnostic model interface with modular adapters.
- Model gateway: routing, streaming, usage and cost metering, budgets, rate limits.
- Tool calling mediated by the tool gateway with schema validation and permission
  checks.
- LLM credentials server-side only.

## Phase 8: Security layer

**Objective:** harden the platform against realistic threats.

- Policy engine for agent actions; prompt-injection defence in depth with adversarial
  evaluations.
- Secret management integration, SSRF protection, security headers/CSP.
- Dependency and secret scanning in CI; SHA-pinned CI actions; threat model and
  security review.

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
