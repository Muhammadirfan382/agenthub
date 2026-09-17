# AgentHub backend

FastAPI service for agents and executions, backed by SQLAlchemy and Alembic.

**Status (Phase 5).** Persists organizations, users, memberships, sessions,
agents, published versions, marketplace listings, installations, executions and
everything a run records. Every endpoint except the health check and sign-in
requires a session, and every action is checked against a role. A runtime now orchestrates
executions, but **executes nothing**: no sandbox exists yet, so no agent code,
model or tool is actually run (see §6). Treat it as pre-release software — it has never been deployed, audited or
run against real data.

---

## 1. Layout

```
backend/
├── app/
│   ├── api/deps.py         AuthDep: session lookup and the CSRF check
│   ├── api/v1/             Routers: health, auth, agents, executions, members,
│   │                       registry (versions, marketplace, installations)
│   ├── core/               config, errors, logging, middleware, pagination,
│   │                       rate_limit, security (hashing), time
│   ├── db/                 base metadata, engine/session, models/
│   ├── repositories/       Queries (no business rules)
│   ├── schemas/            Pydantic request/response models and enums
│   ├── runtime/            Plan, engine and worker (orchestration only)
│   ├── services/           Business rules, authorization matrix, risk scoring
│   └── main.py             create_app() application factory
├── scripts/create_user.py  Creates an account; there is no public sign-up
├── scripts/seed_demo.py    Demonstration data
└── tests/                  pytest suite
database/migrations/      Alembic environment and versions
infrastructure/compose/   Local PostgreSQL (docker-compose.yml)
```

**Layering rule:** routers parse and shape, services decide, repositories query.
A router never writes SQL; a repository never raises HTTP errors.

## 2. Configuration

Read from the environment and an optional repository-root `.env`
(`.env.example` documents every key). Nothing is hard-coded and no secret has a
default.

| Variable | Default | Meaning |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | `development`, `test` or `production`. Only `development` exposes `/api/docs`. |
| `DATABASE_URL` | empty | SQLAlchemy async URL. **Required in production:** the app refuses to start rather than fall back to a local file database. In development it defaults to `sqlite+aiosqlite:///./agenthub-dev.db`. |
| `DB_ECHO` | `false` | Log every SQL statement. Development only. |
| `SESSION_LIFETIME_MINUTES` | `720` | Absolute session lifetime. |
| `SESSION_IDLE_TIMEOUT_MINUTES` | `60` | A session dies after this long unused. |
| `LOGIN_MAX_ATTEMPTS` | `5` | Failed sign-ins per account per window. |
| `LOGIN_MAX_ATTEMPTS_PER_IP` | `20` | Failed sign-ins per client address per window. |
| `LOGIN_WINDOW_MINUTES` | `15` | The window both limits use. |
| `PASSWORD_HASH_COST_EXPONENT` | `15` | scrypt work factor (n = 2^exponent). Production refuses below 14. |
| `RUNTIME_WORKER_ENABLED` | `true` | Run the execution worker inside the API process. Turn off when running `python -m app.runtime.worker` separately. |

Passwords are masked (`safe_database_url`) before the URL is ever logged.

Importing `app.main` never requires configuration; the ASGI app is built on first
access, so `uvicorn app.main:app` still fails loudly when configuration is missing.

## 3. Endpoints

All under `/api/v1`. Bodies and query parameters are camelCase; the Python code
stays snake_case (`CamelModel` generates the aliases).

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| `GET` | `/health` | — | Liveness. Exposes nothing about configuration. |
| `POST` | `/auth/login` | — | Sets the session and CSRF cookies. Rate limited. |
| `GET` | `/auth/session` | any role | Current user, organization, role and memberships. |
| `POST` | `/auth/logout` | any role | Revokes the session server-side and clears the cookies. |
| `POST` | `/auth/password` | any role | Requires the current password. |
| `PATCH` | `/auth/profile` | any role | Name and time zone. Email changes need verification, which does not exist. |
| `POST` | `/auth/organization` | any role | Switches the session to another organization you belong to. |
| `GET` | `/members` | viewer | Members of the active organization. |
| `POST` | `/members` | admin | Adds an **existing** account and sets its role. |
| `PATCH` | `/members/{id}` | admin | Changes a role. |
| `DELETE` | `/members/{id}` | admin | Removes a membership; that person's sessions stop working at once. |
| `GET` | `/agents` | viewer | `search`, `status`, `risk`, `category`, `sort`, `limit`, `offset`. |
| `POST` | `/agents` | member | Creates a `draft` agent. 409 if the name is taken in this organization. |
| `GET` | `/agents/{id}` | viewer | 404 when unknown **or** owned by another organization. |
| `PUT` | `/agents/{id}` | owner of the agent, or admin | Replaces the configuration; recomputes the risk score. |
| `PATCH` | `/agents/{id}/status` | owner of the agent, or admin | `active`, `paused`, `draft`, `disabled`. |
| `DELETE` | `/agents/{id}` | owner of the agent, or admin | 204. Cascades to that agent's executions. |
| `POST` | `/agents/{id}/executions` | owner of the agent, or admin | 202. Records a `QUEUED` execution. Nothing runs. |
| `GET` | `/agents/{id}/versions` | viewer | Published manifests, newest first. |
| `POST` | `/agents/{id}/versions` | owner of the agent, or admin | Publishes the current configuration. 409 if that version exists. |
| `GET` | `/agents/{id}/versions/{versionId}` | viewer | One frozen manifest. |
| `PATCH` | `/agents/{id}/versions/{versionId}` | owner of the agent, or admin | Deprecate or restore. |
| `PATCH` | `/agents/{id}/visibility` | owner of the agent, or admin | `private`, `organization` or `public`. |
| `GET` | `/marketplace` | viewer | `search`, `category`, `tag`, `verified`. Newest published version per agent. |
| `GET` | `/marketplace/tags` | viewer | Tags in use by visible listings. |
| `GET` | `/marketplace/{versionId}` | viewer | Listing with its manifest. 404 when not listed for you. |
| `GET` | `/installations` | viewer | Agents installed by your organization. |
| `POST` | `/installations` | admin | Installs with explicit grants. |
| `GET` | `/installations/{id}` | viewer | One installation, with the manifest it was granted against. |
| `PATCH` | `/installations/{id}` | admin | Change grants, suspend or resume. |
| `DELETE` | `/installations/{id}` | admin | Uninstall. |
| `GET` | `/executions` | viewer | `status`, `agentId`, `search`, `limit`, `offset`. |
| `GET` | `/executions/{id}` | viewer | The run with everything it recorded: timeline, logs, tool calls, approvals. |
| `POST` | `/executions/{id}/cancel` | owner of the agent, or admin | 202. The runtime stops at the next step boundary. |
| `GET` | `/executions/approvals` | viewer | Approvals waiting on a person. |
| `POST` | `/executions/{id}/approvals/{approvalId}` | owner of the agent, or admin | `approved` or `denied`, with an optional note. |
| `GET` | `/executions/{id}/stream` | viewer | Server-sent events while the run is live. |
| `GET` | `/organization/runtime` | viewer | Kill-switch state and how many approvals are waiting. |
| `PATCH` | `/organization/runtime` | admin to engage, owner to release | The organization-wide stop. |

**Collections** answer with `{items, total, limit, offset}`; `limit` defaults to 50
and is capped at 200.

**Errors** always answer with `{code, message, details?}`:
`unauthenticated` (401), `forbidden` (403), `csrf_failed` (403),
`rate_limited` (429, with `Retry-After`), `validation_failed` (422),
`not_found` (404), `conflict` (409), `method_not_allowed` (405),
`internal_error` (500). Handlers never leak exception
text, SQL or stack traces; the detail goes to the log with the request id.

**Every response** carries `X-Request-ID` (a client-supplied one is echoed only if
it matches `^[A-Za-z0-9._-]{1,64}$`), `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a restrictive
`Permissions-Policy` and `Cache-Control: no-store`.

## 4. Authentication and authorization

**Accounts.** There is no public sign-up. `scripts/create_user.py` creates an
account and puts it in an organization; the password is typed at a prompt, never
passed as an argument, so it stays out of shell history and process listings.
Administrators then add existing accounts to their organization by email.

**Passwords** are hashed with scrypt from the standard library (n = 2^15, r = 8,
p = 1 by default) with a random 16-byte salt. The hash is self-describing
(`scrypt$n=...,r=...,p=...$salt$key`), so raising the cost later does not
invalidate existing passwords. Hashing runs in a worker thread so it never blocks
the event loop. The minimum length is 12 characters; there are no composition
rules, because length is what matters.

**Sessions** are opaque 32-byte random tokens. Only a SHA-256 fingerprint is
stored, so a leaked database yields no usable tokens. Every request re-checks the
session row, which means signing out, disabling an account or removing a
membership takes effect immediately. A session dies at the absolute lifetime, or
after the idle timeout, whichever comes first. Signing in again in the same
browser revokes the previous session (no session fixation); sessions in other
browsers are untouched. Changing a password ends every other session for that
account, keeping only the one that made the change.

**Cookies.** `agenthub_session` is `HttpOnly`, so page scripts - including
anything injected - cannot read it. `agenthub_csrf` is deliberately readable: the
app echoes it in the `X-CSRF-Token` header, and the backend compares it with the
token stored on the session. Both are `SameSite=Strict`, and `Secure` whenever
`ENVIRONMENT=production`.

**CSRF.** Every `POST`/`PUT`/`PATCH`/`DELETE` made with a session must carry a
matching `X-CSRF-Token`. A cross-site page can make a browser send cookies, but
it cannot read them, so it cannot produce the header.

**Sign-in throttling.** Failed attempts are limited per account and per client
address; a correct password clears that account's counter. Client addresses come
from the connection - forwarded headers are not trusted, because nothing is
configured as a trusted proxy. The limiter is per process (see
`app/core/rate_limit.py`); more than one worker needs a shared store.

**Login answers identically** for an unknown address and for a wrong password,
and spends comparable time on both, so it cannot be used to enumerate accounts.

**Roles.** A user reaches an organization through a membership, and the role
lives on that membership: `viewer` < `member` < `admin` < `owner`.

| Action | viewer | member | admin | owner |
| --- | --- | --- | --- | --- |
| Read agents, executions, members | yes | yes | yes | yes |
| Create agents | no | yes | yes | yes |
| Change, delete or run **their own** agent | no | yes | yes | yes |
| Change, delete or run **any** agent | no | no | yes | yes |
| Add members, change roles, remove members | no | no | yes | yes |
| Change another owner, or grant the owner role | no | no | no | yes |

Two more rules: nobody may change or remove their own membership, and an
organization always keeps at least one owner.

**Isolation.** Every agent and execution belongs to exactly one organization, and
every repository query filters on it. An id belonging to another organization
answers 404, not 403, so ids cannot be probed.

## 5. The registry

**A manifest is a request; an installation is a grant.** Keeping those two apart
is the whole point of this phase.

**Publishing** (`POST /agents/{id}/versions`) freezes the agent's current
configuration - model, tools, required permissions, limits, policy - into an
immutable `agent_versions` row. Editing the agent afterwards changes what the
*next* version will say, never what an installer already agreed to. A version
number can only be published once, and a rejected agent or one with a failed
security check cannot be published at all.

**Visibility** decides who sees a published agent in the marketplace:

| Visibility | Who can see the listing |
| --- | --- |
| `private` (default) | Nobody. It is not listed, not even to its own organization. |
| `organization` | Members of the publishing organization. |
| `public` | Every organization on this AgentHub. |

An agent must have a published version before it can leave `private`, and the
marketplace only ever lists the newest published, non-deprecated version of each
agent. Deprecating that version removes the listing.

**Installing** (`POST /installations`) records what the installing organization
allows. The rules are enforced server-side, in `registry_service.normalise_grants`:

- Every capability starts **denied**; anything left out of the request stays denied.
- A grant may never exceed the level the manifest asked for.
- An approval requirement set by the publisher cannot be removed, and any grant
  that works out as critical risk must require approval.
- Anything granted needs a scope in words, so the limit is on the record.
- Risk is recomputed from the grants; a client cannot claim a lower risk.

Installing is allowed to grant nothing. The response then lists `unusableTools`:
the manifest's tools whose capability was denied, so the cost of granting
nothing is visible rather than silent.

An organization cannot install its own agent, and can install a given agent
once; changing your mind means updating the installation, which re-runs the same
validation. `updateAvailable` says whether the publisher has released a newer
version - upgrading is a deliberate act, because a new manifest may ask for more.

## 6. The runtime

**It orchestrates; it does not execute.** There is no sandbox (Phase 6) and no
model gateway (Phase 7), so no agent code runs, no model is called and no tool
is invoked. Every run records `runtime = "simulation"`, every simulated step
says so in its own text, and tool calls are recorded as `simulated` — never as
`succeeded`. Nothing in the database can be mistaken for work that happened.

What *is* real is everything around the work: the state machine, the budget,
the approval pauses, cancellation, the kill switch, and the record.

**The plan** (`app/runtime/plan.py`) comes from the agent's own declaration:
prepare, think, one step per declared tool, finish. It is not a model deciding
what to do — that arrives with Phase 7.

**The engine** (`app/runtime/engine.py`) walks one step at a time, writing
progress after each. Before every step it checks, in order: the kill switch,
cancellation, then the budget. A tool step is refused outright when its
capability is denied, pauses when the agent requires human approval, and is
otherwise recorded as simulated.

**The worker** (`app/runtime/worker.py`) claims runs with a conditional UPDATE,
so two workers racing for the same run cannot both win. It heartbeats while it
works; a run whose worker stopped heartbeating for 60 seconds is reclaimed and
continues from the step it reached, because `step_index` is in the database
rather than in memory. It runs inside the API process by default
(`RUNTIME_WORKER_ENABLED`), or separately with
`python -m app.runtime.worker`.

**States**

```
QUEUED -> STARTING -> RUNNING -> COMPLETED
                         |  \-> WAITING_FOR_APPROVAL -> RUNNING
                         |
                         +-> FAILED | TIMEOUT | CANCELLED
```

**Budgets** are copied onto the run when it is requested — runtime seconds,
tokens and tool calls — so editing the agent mid-run cannot move the limits the
run is being held to. Passing them ends the run as `TIMEOUT` (time) or `FAILED`
(tokens, tool calls) with an error code saying which.

**Approvals.** A tool step whose permission says `requiresApproval` creates a
pending approval and parks the run in `WAITING_FOR_APPROVAL`; nothing is
recorded as done while it waits. Deciding it needs the same permission as
running the agent. Refusal is not a failure: the refusal is recorded, the step
is skipped, and the run continues.

**Cancellation** is a request, not a kill: the engine stops at the next step
boundary, so a run never ends mid-step with a half-written record.

**The kill switch** is organization-wide. Engaging it refuses new runs and asks
every live run to stop; any administrator can engage it, and only the owner can
release it. Turning protection back on should be easier than turning it off.

**Watching a run.** `GET /executions/{id}/stream` is a server-sent event stream
of status changes and new timeline entries. It is an optimisation: the UI also
polls while a run is live, so a browser without `EventSource`, or a proxy that
buffers the stream, still sees progress.

## 7. Domain rules

The backend is authoritative; the frontend's Zod rules only improve the form.

- Name 3–60 characters, description 20–500, 1–10 tags, at most 10 tools, semantic
  version, temperature 0–2.
- Permissions must cover every capability exactly once. Risk is derived
  server-side from the granted levels — a client cannot claim a lower risk.
- `code_execution` is always critical risk.
- Granting web or API access requires `networkEgress: allow_list` with at least one
  domain, and each domain must be a bare hostname (no scheme, path or wildcard).
- An agent can only become `active` if its security checks have not failed and its
  verification is not `rejected`.
- Executions can only be requested for an `active` agent.

## 8. Database

- **Runtime tables:** `execution_events`, `execution_logs`,
  `execution_tool_calls` and `execution_approvals`, all cascading from the
  execution. `executions` also carries the budget it was given, the worker
  claim, the heartbeat and any error.
- **Registry tables:** `agent_versions` (immutable manifests) and
  `installations` (one row per organization per installed agent, holding the
  grants). Both are organization-scoped like everything else.
- **Identity tables:** `organizations`, `users`, `memberships`, `sessions`.
  Passwords and tokens are stored only as hashes, and sessions record no IP
  address or user agent.
- **Tables:** `agents`, `executions` (with `alembic_version`). Configuration
  documents (model, permissions, limits, policy, versions, checks) are stored as
  JSON columns: `JSON` on SQLite, `JSONB` on PostgreSQL, from one portable type.
- **Executions** reference agents with `ON DELETE CASCADE`. SQLite only enforces
  foreign keys when asked, so every SQLite connection runs
  `PRAGMA foreign_keys=ON`; without it local behaviour would silently differ from
  PostgreSQL.
- **Development** uses a local SQLite file by default so the app runs with no
  services installed. **Staging and production use PostgreSQL**, which CI exercises
  on every push.

### Migrations

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head     # apply
.\.venv\Scripts\python.exe -m alembic check            # models vs migrations
.\.venv\Scripts\python.exe -m alembic downgrade base   # roll back
.\.venv\Scripts\python.exe -m alembic revision -m "..."  # new revision
```

Migrations are hand-reviewed; autogenerate is a starting point, not the output.

### Local PostgreSQL (optional)

```powershell
docker compose -f infrastructure/compose/docker-compose.yml up -d
```

It publishes `127.0.0.1:5432` only, with development-only credentials that exist
solely in that file. Then set `DATABASE_URL` in `.env` and run the migrations.

### Demonstration data

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.seed_demo
```

Four fictional agents and three execution records, safe to run twice. The
execution rows are records of requests, not evidence that anything ran.

## 9. Testing

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

Each test gets its own SQLite file, its own application instance and a seeded
workspace with one account per role (plus a second organization), so tests share
no state. Clients sign in through the real login endpoint, exercising cookies and
CSRF the way a browser does.

They cover the API contract, pagination, filtering, the error envelope, request
ids, security headers, validation rules, status transitions, cascade deletion and
the risk model - and, for this phase, sign-in and throttling, session expiry and
revocation, CSRF rejection, the role matrix, ownership rules, membership rules,
cross-organization isolation, and a deny-by-default check that walks the OpenAPI
schema and asserts every route refuses an unauthenticated caller.

The runtime is driven directly rather than through the background loop, so the
tests assert behaviour instead of timing: a run walks to completion and records
its trace, each budget ends it with the right status, an approval pauses it and
approving or refusing continues it, cancellation stops it at the next step, the
kill switch blocks and stops runs, two workers cannot claim the same run, and an
abandoned run is reclaimed.

The registry adds its own: that a published manifest does not change when the
agent is edited, that private agents are never listed, that only the newest
published version appears, that a grant cannot exceed or weaken what the
manifest asked for, that installing grants nothing by default, and that
installations never cross organizations. PostgreSQL is covered in CI by applying,
rolling back and reapplying the migrations against a real server.

## 10. Security status

Implemented: an orchestrator that executes nothing, budgets enforced per run,
human approval before a declared capability is used, cancellation and an
organization-wide kill switch, immutable published manifests, deny-by-default
permission grants
that can never exceed what a manifest requested, password authentication with
scrypt, revocable server-side sessions
in HttpOnly cookies, CSRF protection on every state-changing request, sign-in
throttling, role-based authorization on every endpoint, organization isolation in
every query, strict input validation, server-derived risk, a uniform error
envelope that leaks nothing, security headers, request ids in structured JSON
logs, masked database URLs, an explicit refusal to start in production without
`DATABASE_URL` or with weak password hashing, and parameterised queries
throughout.

**Not implemented yet:** MFA and SSO (password sign-in is the only method), email
delivery and therefore password reset and email verification, an audit log, CORS
configuration for a separate frontend origin, shared-store rate limiting for
multiple workers, agent execution and sandboxing (Phase 6), a real model
(Phase 7) and real security scanning (Phase 8). Grants and policies are checked
when the runtime plans a step, but nothing enforces them against real code
because no real code runs. Verification is a stored label, not the result of a
review anyone performed. Nothing here has been penetration-tested or reviewed by
anyone outside this repository.
