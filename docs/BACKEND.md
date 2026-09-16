# AgentHub backend

FastAPI service for agents and executions, backed by SQLAlchemy and Alembic.

**Status (Phase 3).** Persists organizations, users, memberships, sessions,
agents and executions. Every endpoint except the health check and sign-in
requires a session, and every action is checked against a role. There is still
**no agent runtime**: requesting an execution records a queued row and nothing
runs. Treat it as pre-release software — it has never been deployed, audited or
run against real data.

---

## 1. Layout

```
backend/
├── app/
│   ├── api/deps.py         AuthDep: session lookup and the CSRF check
│   ├── api/v1/             Routers: health, auth, agents, executions, members
│   ├── core/               config, errors, logging, middleware, pagination,
│   │                       rate_limit, security (hashing), time
│   ├── db/                 base metadata, engine/session, models/
│   ├── repositories/       Queries (no business rules)
│   ├── schemas/            Pydantic request/response models and enums
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
| `GET` | `/executions` | viewer | `status`, `agentId`, `search`, `limit`, `offset`. |
| `GET` | `/executions/{id}` | viewer | Timeline, logs and tool calls are empty until a runtime records them. |

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

## 5. Domain rules

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

## 6. Database

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

## 7. Testing

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
schema and asserts every route refuses an unauthenticated caller. PostgreSQL is covered in CI by applying,
rolling back and reapplying the migrations against a real server.

## 8. Security status

Implemented: password authentication with scrypt, revocable server-side sessions
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
multiple workers, agent execution and sandboxing (Phases 5-6), and real security
scanning (Phase 8). Nothing here has been penetration-tested or reviewed by
anyone outside this repository.
