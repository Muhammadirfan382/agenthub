# AgentHub

**A platform for discovering, deploying and securely governing AI agents.**

> **AgentHub is currently under active development.**
> It is not production-ready and must not be used to run real agents, handle real
> credentials, or process real data.

---

## Purpose

AI agents act on real systems: they read data, call tools and take actions. AgentHub
aims to make that safe to do inside an organization by combining two things:

- **A marketplace.** Discover agents and understand exactly what each one needs
  (permissions, data access, tools, cost) before installing it.
- **A control plane.** Grant narrowly scoped permissions, require human approval for
  high-risk actions, execute agents in isolated sandboxes, and keep an auditable
  record of everything they do.

## Current development status

| Phase | Name | Status |
| --- | --- | --- |
| 0 | Project initialization | ✅ Complete |
| 1 | Frontend and UI (demonstration data) | ✅ Complete |
| 2 | Backend: API, PostgreSQL, migrations | ✅ Complete |
| 3 | Authentication and RBAC | ✅ Complete |
| 4 | Agent registry: manifests, versions, marketplace, installs | ✅ Complete |
| 5 | Agent runtime: orchestration, approvals, budgets, kill switch | ✅ Complete |
| 6 | Docker sandbox: isolated, verified containers per run | ✅ Complete (real-container tests run in CI only) |
| 7 | AI/LLM: model gateway, Claude and OpenAI adapters, tool gateway | ✅ Complete (no live provider call made; see below) |
| 8 | Security layer: policy engine, egress gateway, audit log, CSP, scanning | ✅ Complete |
| 9–10 | Monitoring, deployment | ⏳ Not started |

**What exists today (Phases 0–8):**

- Repository structure, development rules ([CLAUDE.md](CLAUDE.md)), architecture
  notes ([ARCHITECTURE.md](ARCHITECTURE.md)) and a roadmap
  ([docs/ROADMAP.md](docs/ROADMAP.md)).
- A React + TypeScript frontend ([docs/FRONTEND.md](docs/FRONTEND.md)):
  - Screens: application shell, dashboard, agent management (list, details, create/edit), marketplace, executions (list and detail), security dashboard, analytics and settings.
  - Foundations: a reusable design system and a typed service layer.
  - Data: two modes, switchable in **Settings → API**. *Demo* answers everything from **clearly labelled demonstration data**; *API* reads agents, executions and dashboard counts from the backend and keeps saying which sections are still demo data.
- A FastAPI backend ([docs/BACKEND.md](docs/BACKEND.md)) that persists agents and executions:
  - Routers → services → repositories, Alembic migrations, SQLite for local development and PostgreSQL for production.
  - A uniform `{code, message, details}` error envelope, request ids, security headers, pagination and server-side validation and risk scoring.
  - Password sign-in, server-side sessions in HttpOnly cookies, CSRF protection, sign-in throttling, organizations with memberships, and four roles (viewer, member, admin, owner) enforced on every endpoint.
  - An agent registry: publishing freezes a manifest as an immutable version, visibility decides who sees it in the marketplace, and installing it into another organization grants only what that organization chooses - never more than the manifest asked for, and nothing by default.
  - An execution runtime that orchestrates runs: a durable queue and worker, per-run budgets for time, tokens and tool calls, pauses for human approval, cancellation, an organization-wide kill switch, and a recorded timeline, logs and tool calls streamed to the UI.
  - A sandbox: before each run the runtime starts an ephemeral, non-root, read-only, capability-free, network-less and resource-limited container, checks 13 isolation guarantees from inside it, records the result on the run, and fails the run if any guarantee does not hold. Without a container runtime, runs are recorded as simulations, or refused when `REQUIRE_SANDBOX=true`.
  - A model gateway: with `AGENTHUB_ANTHROPIC_API_KEY` (or `AGENTHUB_OPENAI_API_KEY`) set, a real model answers each run. Agents pick a tier; the deployment routes it to a model. Every request is rate limited, budgeted and metered per organization, and credentials never leave the server.
  - A security layer: every tool call is decided by a policy engine from what the agent declared (allowed domains, egress mode, which risk levels need a person), and the only way out of the server is an SSRF-safe egress gateway - HTTPS GET, allow-listed hosts, public addresses only, connections pinned against DNS rebinding, no redirects, bounded. `api_request` runs through it; every other tool is still recorded as not executed. What it fetches reaches the model labelled as untrusted data.
  - An append-only audit log of security decisions (sign-ins, roles, the kill switch, approvals, policy refusals, every outbound request), readable by administrators; a strict Content-Security-Policy; per-client write limits; dependency and secret scanning in CI with actions pinned to commits. A [threat model](docs/THREAT_MODEL.md) and a [security review](docs/SECURITY_REVIEW.md) say what is and is not covered.
- Unit and component tests (Vitest + Testing Library, pytest), linting and type checking.
- A GitHub Actions CI workflow.

**What does not exist yet:** MFA and SSO, email delivery (so no password reset or
email verification), tools other than `api_request`, scheduled triggers, real security scanning (the verification label
is stored, not earned), monitoring and deployment.
Directories for these areas are placeholders. Nothing here has been deployed,
penetration-tested or reviewed outside this repository: run it locally, with
demonstration data.

## Technology stack

| Area | Current (Phases 0–2) | Planned |
| --- | --- | --- |
| Frontend | React 19, TypeScript 6 (strict), Vite 8, Tailwind CSS 4, React Router, TanStack Query, Zustand, React Hook Form, Zod, lucide-react, ESLint 10, Vitest 5, Testing Library | Pagination for large collections, approval workflows |
| Backend | Python, FastAPI, Pydantic v2, pydantic-settings, Uvicorn, SQLAlchemy 2 (async), Alembic, asyncpg, scrypt (stdlib) for passwords, pytest, Ruff, mypy | MFA/SSO, background jobs, agent orchestration |
| Database | PostgreSQL 17 (SQLite for local development and tests) | Tenant isolation, row-level security, Redis |
| Cache / queue | — | Redis |
| Containers | Docker Compose for local PostgreSQL (optional) | Docker for agent sandboxes and deployment |
| CI/CD | GitHub Actions (lint, type check, test, build) | Security scanning, image builds, deployment |
| AI / agents | — | Modular provider and runtime architecture behind a gateway |

## Planned architecture

```
Browser ──► Frontend (React SPA) ──► Backend API (FastAPI) ──► PostgreSQL / Redis
                                          │
                                          ├─► Agent runtime ──► Isolated sandbox (Docker)
                                          │                         │
                                          │                         └─► Tool gateway (policy-checked)
                                          └─► Model gateway ──► LLM providers
```

The backend is the enforcement point for identity, permissions, approvals and audit.
Agents never receive raw credentials and never run on the host. Details, including
which parts exist today and which are planned, are in
[ARCHITECTURE.md](ARCHITECTURE.md).

## Local development requirements

| Tool | Required version | Verified with | Needed for |
| --- | --- | --- | --- |
| Git | 2.40+ | 2.54.0 | Everything |
| Node.js | `^20.19.0` or `>=22.12.0` (Vite 8) | 24.16.0 | Frontend |
| npm | 10+ | 11.13.0 | Frontend |
| Python | 3.12+ | 3.14.3 | Backend |
| pip | recent | 26.0.1 | Backend |
| Docker Desktop (with Compose v2) | any recent | not installed | **Optional.** To run PostgreSQL locally, and to give runs a real sandbox (`docker build -t agenthub/sandbox:0.6.0 agents/sandbox`). Without it, development uses a SQLite file and runs are recorded as simulations. |

## Running AgentHub locally (Windows PowerShell)

Open two terminals at the repository root.

**Terminal 1: backend**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:ENVIRONMENT = 'development'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_demo
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`seed_demo` creates a demonstration organization with three accounts and prints
their generated passwords **once**. For your own account, which prompts for the
password instead of taking it as an argument:

```powershell
.\.venv\Scripts\python.exe -m scripts.create_user --email you@example.com --name "Your Name" --organization "Your Workspace" --role owner
```

Check it: `http://127.0.0.1:8000/api/v1/health`. The migrations create
`backend/agenthub-dev.db` (SQLite); set `DATABASE_URL` in `.env` to use PostgreSQL
instead — see [docs/BACKEND.md](docs/BACKEND.md).

**Terminal 2: frontend**

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The UI starts in **demo mode** and works without the
backend; it signs you in as a demonstration user and any password is accepted.

With the backend running, switch to the real API in **Settings → API → Data source
→ Backend API**. The app then asks you to sign in with a real account, and agents,
executions, members and the dashboard counts come from the database. The header
badge changes from *Demo mode* to *API mode*, and sections the backend does not
implement yet stay labelled as demonstration data.

**Windows note:** the npm scripts invoke tools via `node node_modules/...` rather
than `npx` or `.bin` shims, because `cmd.exe` mis-parses shim paths containing `&`
(for example `C:\Users\SAEED & SONS\...`). Always use `npm run <script>`.

**Optional:** copy `.env.example` to `.env` and keep `ENVIRONMENT=development`
to enable the interactive API docs at `http://127.0.0.1:8000/api/docs`. Without
`.env` the backend runs in `production` mode and the docs are disabled.

### Quality checks

```powershell
# frontend/
npm run lint
npm run typecheck
npm test
npm run build

# backend/
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest
```

The same checks run in CI (`.github/workflows/ci.yml`).

## Project structure

```
AgentHub/
├── frontend/              React + TypeScript + Vite application (see docs/FRONTEND.md)
│   ├── src/app/           Router, providers, query client
│   ├── src/components/    Design system, layout, feedback and status components
│   ├── src/features/      Product areas (dashboard, agents, marketplace, …) and demo data
│   ├── src/services/      Service contracts, demo implementations, HTTP client
│   ├── src/stores/        Zustand stores (theme/sidebar, toasts)
│   └── src/test/          Test setup and render harness
├── backend/               FastAPI service (see docs/BACKEND.md)
│   ├── app/core/          Configuration, errors, logging, middleware, pagination, password hashing
│   ├── app/api/v1/        Versioned API routes (health, auth, agents, executions, members)
│   ├── app/db/            Engine, session and ORM models
│   ├── app/repositories/  Database queries
│   ├── app/schemas/       Request/response models
│   ├── app/runtime/       Execution plan, engine and worker (orchestration only)
│   ├── app/services/      Business rules and risk scoring
│   ├── scripts/           Account creation and demonstration seed scripts
│   └── tests/             pytest suite
├── agents/                Placeholder: future agent layer
│   ├── runtime/           Agent execution orchestration
│   ├── sandbox/           Isolated execution environment
│   ├── tools/             Tool definitions and gateway adapters
│   └── policies/          Permission and policy definitions
├── database/
│   ├── migrations/        Alembic environment and versioned migrations
│   └── schema/            Schema documentation (placeholder)
├── infrastructure/
│   ├── docker/            Dockerfiles (placeholder)
│   ├── compose/           Local PostgreSQL for development
│   └── deployment/        Deployment configuration
├── scripts/               Developer scripts (placeholder)
├── docs/                  Roadmap and design documents
├── tests/                 Future cross-service integration / end-to-end tests
├── .github/workflows/     CI
├── .env.example           Environment variable placeholders (no secrets)
├── CLAUDE.md              Development and security rules
├── ARCHITECTURE.md        Current vs planned architecture
└── README.md
```

## Development phases

| Phase | Objective |
| --- | --- |
| 0 | Initialization: repository, tooling, skeletons, CI |
| 1 | Frontend: application shell, routing, design system, UI against a clearly labelled mock API |
| 2 | Backend: API structure, PostgreSQL, migrations, error handling ✅ |
| 3 | Authentication / RBAC: identity, sessions, roles, server-side authorization ✅ |
| 4 | Agent registry: agent manifests, versions, permissions model, marketplace data ✅ |
| 5 | Agent runtime: execution lifecycle, orchestration, approvals ✅ |
| 6 | Docker sandbox: isolated, resource-limited, credential-free execution |
| 7 | AI/LLM integration: provider abstraction, model gateway, tool calling |
| 8 | Security layer: policy engine, prompt-injection defences, secrets management, hardening |
| 9 | Monitoring: logging, metrics, tracing, alerting, audit dashboards |
| 10 | Production deployment: environments, CD, backups, operational readiness |

Full descriptions: [docs/ROADMAP.md](docs/ROADMAP.md).

## Security philosophy

- **Deny by default.** Nothing is accessible without an explicit grant: routes,
  permissions, network egress, tools, environment variables.
- **The server enforces; the UI only informs.** Every authorization decision is
  made server-side.
- **Agents, tools and models are untrusted.** Their inputs and outputs are validated
  and never treated as instructions to the platform.
- **Isolation.** Agent code will run only inside sandboxes with no host access, no
  ambient credentials and limited resources. The sandbox exists and is checked
  before every run. Models answer through a gateway outside it, and the only
  request an agent can make is a read-only, allow-listed HTTPS GET.
- **No secrets in code, Git or the browser.** Configuration comes from the
  environment; real values live outside the repository.
- **Honesty over appearance.** Placeholder or mocked functionality is labelled as
  such and never presented as production-ready.

See [CLAUDE.md](CLAUDE.md) for the full rules.

## License

The GitHub repository (`origin`) was created with an MIT `LICENSE` file in its initial
commit. That file is not yet part of this local history; it will be included when the
local repository is integrated with the remote, before the first push.
