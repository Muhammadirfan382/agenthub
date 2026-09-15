# AgentHub roadmap

AgentHub is built **phase by phase**. Each phase ends with validation (tests, lint,
type check, build, security review, documentation update) and an explicit decision
before the next phase starts. Scope below is intentionally brief. Each phase is
designed in detail when it begins.

| Phase | Name | Status |
| --- | --- | --- |
| 0 | Initialization | ✅ Complete |
| 1 | Frontend | ✅ Complete (demonstration data; no backend integration) |
| 2 | Backend | ⏳ Not started |
| 3 | Authentication / RBAC | ⏳ Not started |
| 4 | Agent registry | ⏳ Not started |
| 5 | Agent runtime | ⏳ Not started |
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

## Phase 3: Authentication / RBAC

**Objective:** know who is making each request and enforce what they may do.

- User identity, secure sessions or tokens, logout, password/MFA or SSO strategy.
- Organizations, memberships and roles.
- Server-side authorization on every endpoint; CSRF protection; authentication rate
  limiting; negative tests for access control.

## Phase 4: Agent registry

**Objective:** model agents and what they are allowed to need.

- Agent manifests: capabilities, tools, required permissions with risk levels,
  model requirements, resource limits.
- Versions, publishing states, marketplace listing and search.
- Installation into an organization with explicit, scoped permission grants.

## Phase 5: Agent runtime

**Objective:** orchestrate agent executions safely, without running untrusted code on
the host.

- Execution lifecycle and durable job orchestration.
- Human approval pause/resume for high-risk actions.
- Budgets, cancellation, organization-wide kill switch.
- Execution events and streaming status to the frontend.

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
