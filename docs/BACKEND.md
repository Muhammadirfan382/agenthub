# AgentHub backend

FastAPI service for agents and executions, backed by SQLAlchemy and Alembic.

**Status (Phase 2).** Two resources are persisted: agents and executions. There is
**no authentication, no authorization and no agent runtime**. Every request is
treated as coming from the same placeholder user, and requesting an execution only
records a queued row. Run it on a trusted machine, bound to loopback, with
demonstration data only.

---

## 1. Layout

```
backend/
├── app/
│   ├── api/v1/           Routers: agents, executions, health, router.py
│   ├── core/             config, errors, logging, middleware, pagination, time
│   ├── db/               base metadata, engine/session, models/
│   ├── repositories/     Queries (no business rules)
│   ├── schemas/          Pydantic request/response models and enums
│   ├── services/         Business rules, risk scoring, mappers
│   └── main.py           create_app() application factory
├── scripts/seed_demo.py  Demonstration data
└── tests/                pytest suite
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

Passwords are masked (`safe_database_url`) before the URL is ever logged.

Importing `app.main` never requires configuration; the ASGI app is built on first
access, so `uvicorn app.main:app` still fails loudly when configuration is missing.

## 3. Endpoints

All under `/api/v1`. Bodies and query parameters are camelCase; the Python code
stays snake_case (`CamelModel` generates the aliases).

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/health` | Liveness. Exposes nothing about configuration. |
| `GET` | `/agents` | `search`, `status`, `risk`, `category`, `sort`, `limit`, `offset`. |
| `POST` | `/agents` | Creates a `draft` agent. 409 if the name is taken. |
| `GET` | `/agents/{id}` | 404 when unknown. |
| `PUT` | `/agents/{id}` | Replaces the configuration; recomputes the risk score. |
| `PATCH` | `/agents/{id}/status` | `active`, `paused`, `draft`, `disabled`. |
| `DELETE` | `/agents/{id}` | 204. Cascades to that agent's executions. |
| `POST` | `/agents/{id}/executions` | 202. Records a `QUEUED` execution. Nothing runs. |
| `GET` | `/executions` | `status`, `agentId`, `search`, `limit`, `offset`. |
| `GET` | `/executions/{id}` | Timeline, logs and tool calls are empty until a runtime records them. |

**Collections** answer with `{items, total, limit, offset}`; `limit` defaults to 50
and is capped at 200.

**Errors** always answer with `{code, message, details?}`:
`validation_failed` (422), `not_found` (404), `conflict` (409),
`method_not_allowed` (405), `internal_error` (500). Handlers never leak exception
text, SQL or stack traces; the detail goes to the log with the request id.

**Every response** carries `X-Request-ID` (a client-supplied one is echoed only if
it matches `^[A-Za-z0-9._-]{1,64}$`), `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a restrictive
`Permissions-Policy` and `Cache-Control: no-store`.

## 4. Domain rules

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

## 5. Database

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

## 6. Testing

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

Each test gets its own SQLite file and its own application instance, so tests
share no state. They cover the API contract, pagination, filtering, the error
envelope, request ids, security headers, validation rules, status transitions,
cascade deletion and the risk model. PostgreSQL is covered in CI by applying,
rolling back and reapplying the migrations against a real server.

## 7. Security status

Implemented: strict input validation, server-derived risk, a uniform error
envelope that leaks nothing, security headers, request ids in structured JSON
logs, masked database URLs, an explicit refusal to start in production without
`DATABASE_URL`, and parameterised queries throughout (no string-built SQL).

**Not implemented yet, by design of the phase plan:** authentication and
authorization (Phase 3), rate limiting, CORS configuration for a separate origin,
audit logging, agent execution and sandboxing (Phases 5–6), real security scanning
(Phase 8). Until Phase 3 lands, anyone who can reach the port can read and change
every agent — bind it to loopback and keep it off shared networks.
