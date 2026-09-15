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
| 1–10 | Frontend, backend, auth, registry, runtime, sandbox, LLM, security, monitoring, deployment | ⏳ Not started |

**What exists today (Phase 0):**

- Repository structure, development rules ([CLAUDE.md](CLAUDE.md)), architecture
  notes ([ARCHITECTURE.md](ARCHITECTURE.md)) and a roadmap
  ([docs/ROADMAP.md](docs/ROADMAP.md)).
- A minimal React + TypeScript + Vite frontend with a single **status page** that
  reports whether the frontend and backend are running.
- A minimal FastAPI backend with one endpoint: `GET /api/v1/health`.
- Unit tests (Vitest + Testing Library, pytest), linting and type checking.
- A GitHub Actions CI workflow.

**What does not exist yet:** authentication, authorization, a database, an agent
registry or marketplace, agent execution, sandboxing, LLM integration, monitoring
and deployment. Directories for these areas are placeholders.

## Technology stack

| Area | Current (Phase 0) | Planned |
| --- | --- | --- |
| Frontend | React 19, TypeScript 6 (strict), Vite 8, ESLint 10, Vitest 5, Testing Library | Routing, server-state management and a design system (Phase 1) |
| Backend | Python, FastAPI, Pydantic v2, pydantic-settings, Uvicorn, pytest, Ruff, mypy | Domain services, persistence, background jobs |
| Database | — | PostgreSQL |
| Cache / queue | — | Redis |
| Containers | — | Docker (local services, agent sandboxes) |
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
| Docker Desktop (with Compose v2) | — | not installed | **Not needed yet.** Required from the phase that introduces PostgreSQL / sandboxes. |

## Running AgentHub locally (Windows PowerShell)

Open two terminals at the repository root.

**Terminal 1: backend**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check it: `http://127.0.0.1:8000/api/v1/health`.

**Terminal 2: frontend**

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The status page calls the backend through the Vite
development proxy.

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
├── frontend/              React + TypeScript + Vite application
│   ├── src/api/           API client functions (health check)
│   ├── src/pages/         Pages (status page)
│   └── src/test/          Test setup
├── backend/               FastAPI service
│   ├── app/core/          Environment-based configuration
│   ├── app/api/v1/        Versioned API routes (health)
│   └── tests/             pytest suite
├── agents/                Placeholder: future agent layer
│   ├── runtime/           Agent execution orchestration
│   ├── sandbox/           Isolated execution environment
│   ├── tools/             Tool definitions and gateway adapters
│   └── policies/          Permission and policy definitions
├── database/              Placeholder
│   ├── migrations/        Schema migrations
│   └── schema/            Schema documentation
├── infrastructure/        Placeholder
│   ├── docker/            Dockerfiles
│   ├── compose/           Local multi-service Compose files
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
| 2 | Backend: API structure, PostgreSQL, migrations, error handling |
| 3 | Authentication / RBAC: identity, sessions, roles, server-side authorization |
| 4 | Agent registry: agent manifests, versions, permissions model, marketplace data |
| 5 | Agent runtime: execution lifecycle, orchestration, approvals |
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
  ambient credentials and limited resources. Until the sandbox exists, agents are
  not executed.
- **No secrets in code, Git or the browser.** Configuration comes from the
  environment; real values live outside the repository.
- **Honesty over appearance.** Placeholder or mocked functionality is labelled as
  such and never presented as production-ready.

See [CLAUDE.md](CLAUDE.md) for the full rules.

## License

The GitHub repository (`origin`) was created with an MIT `LICENSE` file in its initial
commit. That file is not yet part of this local history; it will be included when the
local repository is integrated with the remote, before the first push.
