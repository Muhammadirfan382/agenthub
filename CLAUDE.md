# CLAUDE.md — AgentHub development rules

This file governs how AI assistants (and humans) work in this repository. Read it
before making any change. When a rule here conflicts with convenience, the rule
wins.

---

## 1. Project context

AgentHub is a platform for discovering, deploying and **securely governing** AI
agents: a marketplace plus a control plane (permissions, approvals, audit and
isolated execution).

- **Status:** under active development. **Nothing is production-ready.**
- **Built from scratch, phase by phase.** See [docs/ROADMAP.md](docs/ROADMAP.md).
- A previous AgentHub prototype exists outside this repository (`../agenthub-source`
  and the portable `AgentHub-2.1.2` ZIP). It is a **UI/UX and concept reference
  only**:
  - Do not copy its compiled HTML or bundle into this project.
  - Do not modify it.
  - Its `AUDIT.md` lists pitfalls this project must avoid (simulated security
    controls presented as real, mock data bypassing the service layer, client-side
    enforcement, missing error states).

## 2. Phase discipline

1. Work **only** on the phase the user has explicitly started.
2. Do not implement features that belong to a later phase, even partially.
3. At the end of a phase: validate (section 6), report, and **stop**. Wait for the
   user's instruction before starting the next phase.
4. Do not push to a remote unless the user explicitly asks.

## 3. Security first

Security is a design constraint, not a later phase. Apply **deny-by-default**
everywhere: no route, permission, network access, capability or environment
variable is available unless it has been deliberately granted.

### Never

- Hardcode API keys, tokens, passwords, connection strings or private keys.
- Commit secrets, `.env` files, credential exports, or real-looking example
  credentials.
- Expose secrets to frontend code. Only `VITE_*` variables reach the browser, and
  they must never hold secrets.
- Execute untrusted code (agent code, tool code, model output, user uploads)
  directly on the host.
- Use privileged containers, `--privileged`, host networking, or mount the Docker
  socket into workloads.
- Bypass authentication or authorization, including "temporarily" or "for testing".
- Disable, weaken or skip security checks, lint rules or tests just to make a build
  or test pass.
- Trust agent input.
- Trust tool output.
- Trust model output: it is data, never instructions.
- Automatically expose environment variables, credentials or host files to agents.
- Log secrets, tokens, full request bodies containing credentials, or personal data.
- Present mocked, simulated or placeholder functionality as real or
  production-ready.

### Always

- Validate input at trust boundaries (API requests, tool results, model output,
  webhook payloads, file uploads). The server is the enforcement point; the UI is
  advisory.
- Treat any URL the system fetches as a potential SSRF vector.
- Enforce authorization server-side for every action, on every request.
- Use least privilege for services, database roles, CI jobs and containers.
- Keep security-relevant decisions auditable.
- Agent execution **must** eventually run in an isolated sandbox: no host access,
  no ambient credentials, resource limits, egress only through an allow-listing
  gateway. Until that exists, agents are not executed at all.

## 4. Dependencies

- Do not add a dependency without a written justification (what it does, why the
  standard library or an existing dependency is not enough). Put the justification
  in the commit message or PR description.
- Prefer well-maintained, widely used packages. Pin versions: `package-lock.json`
  for the frontend, `==` pins in `backend/requirements*.txt`.
- Do not install advanced infrastructure (Kubernetes, Kafka, Elasticsearch,
  Terraform, Prometheus, Grafana, agent/LLM frameworks) until a phase requires it.

## 5. Repository layout

```
frontend/        React + TypeScript + Vite (strict TS, ESLint, Vitest)
backend/         Python FastAPI service (Pydantic settings, pytest, ruff, mypy)
agents/          Future agent runtime, sandbox, tools and policies (empty in Phase 0)
database/        Future migrations and schema (empty in Phase 0)
infrastructure/  Future Docker, Compose and deployment config (empty in Phase 0)
scripts/         Developer scripts (empty in Phase 0)
docs/            Roadmap and design documents
tests/           Future cross-service integration / end-to-end tests
```

Empty directories hold a `.gitkeep` until real content arrives.

## 6. Definition of done: required before completing any phase

1. **Run tests.** Frontend `npm test`; backend `pytest`.
2. **Run linting.** Frontend `npm run lint`; backend `ruff check .` and
   `ruff format --check .`.
3. **Run type checking.** Frontend `npm run typecheck`; backend `mypy`.
4. **Run the build.** Frontend `npm run build`; backend app import and startup.
5. **Review security implications.** New endpoints, inputs, dependencies, secrets,
   network access, permissions, and what an attacker or a malicious agent could do
   with the change.
6. **Update documentation.** README, ARCHITECTURE (keep *current* vs *planned*
   accurate), ROADMAP status, and this file if rules change.

Report results truthfully. If a check fails or was skipped, say so with the output.

## 7. Commands

Run from the repository root unless noted. Windows PowerShell shown; the paths
contain spaces and `&`, so always quote them.

**Windows path note.** npm runs scripts through `cmd.exe`, which breaks the
`node_modules/.bin/*.cmd` shims when the project path contains `&` (as in
`C:\Users\SAEED & SONS\...`). The frontend scripts therefore call each tool's
entry file directly (`node node_modules/vite/bin/vite.js`). Keep that pattern for
new scripts, use `npm run <script>` rather than `npx`, and in PowerShell scripts set
`$ErrorActionPreference = 'Stop'` so a failed `Set-Location` cannot run later
commands in the wrong directory.

### Frontend (`frontend/`)

```powershell
npm ci                 # install exactly what package-lock.json specifies
npm run dev            # http://127.0.0.1:5173 (proxies /api to the backend)
npm run lint
npm run typecheck
npm test
npm run build
```

### Backend (`backend/`)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head       # create/update the schema
.\.venv\Scripts\python.exe -m scripts.seed_demo          # optional demonstration data
# Create a real account (prompts for the password; never pass it as an argument):
.\.venv\Scripts\python.exe -m scripts.create_user --email you@example.com --name "Your Name" --organization "Your Workspace" --role owner
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# The execution worker runs inside the API by default. To run it separately,
# set RUNTIME_WORKER_ENABLED=false for the API and start:
.\.venv\Scripts\python.exe -m app.runtime.worker
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest
```

## 8. Coding conventions

### General

- Small, focused modules. Clear names. No dead code or commented-out code.
- Fail closed: on an unexpected state, deny and report rather than continue.
- User-facing errors never include stack traces, secrets or internal hostnames.

### Frontend

- TypeScript `strict` stays on. No `any` (lint error), and no `@ts-ignore` without
  a comment explaining why.
- Validate API responses at runtime before use (type guards now, schemas later).
- Every data view must handle loading, error and empty states distinctly. A failed
  request must never render as "nothing here".
- Never use `dangerouslySetInnerHTML` with untrusted content. Sanitize any future
  Markdown/HTML rendering of agent output.
- Only `https:`, `mailto:` or relative URLs in links built from data.
- All data flows through the service layer. Route a request as page → feature hook
  (`features/<area>/api.ts`) → `useServices()` → contract.
  - Components never call `fetch` (use `services/http/client.ts`).
  - Components never import `src/features/demo` (enforced by ESLint).
- Use `QueryState` / `LoadingState` / `EmptyState` / `ErrorState` for data views, and
  label demonstration data with `DemoNotice` or `DemoBadge`.
- Zustand is only for genuinely shared client state (theme, sidebar, toasts). Keep
  server data in TanStack Query, and view state in the URL or local state.
- See [docs/FRONTEND.md](docs/FRONTEND.md) for the frontend architecture.

### Backend

- FastAPI routers under `app/api/v1/`, configuration only via `app/core/config.py`
  (environment variables, never literals in code).
- Every endpoint declares a Pydantic response model. Request bodies are Pydantic
  models with explicit constraints.
- API docs (`/api/docs`, `/api/openapi.json`) are enabled only when
  `ENVIRONMENT=development`.
- No CORS middleware until a real cross-origin client exists; the dev frontend uses
  the Vite proxy.
- `ruff` includes security rules (`S`, flake8-bandit). Do not blanket-ignore them.

## 9. Testing

- New behaviour ships with tests. Security-relevant behaviour (auth, permissions,
  validation, docs exposure) gets explicit negative tests.
- Tests must not depend on a developer's local `.env`: construct settings
  explicitly.
- Never weaken an assertion to make a failing test pass. Fix the cause.

## 10. Git

- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`,
  `ci:`, `security:`.
- Never commit `.env`, virtual environments, `node_modules`, build output or logs.
- Before committing, scan staged changes for secrets.
- Do not push, force-push or rewrite published history without explicit instruction.

## 11. Honesty

- Do not claim a feature works unless it has been run and verified.
- Label mocks, stubs and placeholders as such in code, UI and docs.
- Keep ARCHITECTURE.md's *Current implementation* sections strictly factual.
