# AgentHub backend

FastAPI service for agents and executions, backed by SQLAlchemy and Alembic.

**Status (Phase 7).** Persists organizations, users, memberships, sessions,
agents, published versions, marketplace listings, installations, executions and
everything a run records. Every endpoint except the health check and sign-in
requires a session, and every action is checked against a role. A runtime
orchestrates executions and gives each one an isolated, verified container
(§7). With a provider configured, a real model answers each run through the
model gateway (§8); the tools it asks for are checked and never executed. Treat it as pre-release software — it has never been deployed, audited or
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
│   ├── sandbox/            Container spec, runner and isolation report
│   ├── llm/                Model gateway, routing, pricing, provider adapters
│   ├── services/           Business rules, authorization matrix, risk scoring
│   └── main.py             create_app() application factory
├── scripts/create_user.py  Creates an account; there is no public sign-up
├── scripts/seed_demo.py    Demonstration data
└── tests/                  pytest suite
agents/sandbox/           The sandbox image and its in-container probe
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
| `SANDBOX_ENABLED` | `true` | Give each run a container. Off means every run is a recorded simulation. |
| `SANDBOX_COMMAND` | `docker` | The container CLI: `docker`, or anything compatible with its `run` arguments. |
| `SANDBOX_IMAGE` | `agenthub/sandbox:0.6.0` | Must carry a tag or digest; may name a registry. |
| `SANDBOX_MEMORY_MB` | `512` | Memory per container, with no swap. At least 64. |
| `SANDBOX_CPUS` | `1.0` | CPU share per container. |
| `SANDBOX_PIDS_LIMIT` | `128` | Processes per container. At least 8. |
| `SANDBOX_TMPFS_MB` | `64` | The one writable, non-executable scratch directory. |
| `SANDBOX_TIMEOUT_SECONDS` | `60` | After this the container is killed and removed. |
| `REQUIRE_SANDBOX` | `false` | Refuse a run that cannot get a verified container, instead of simulating it. |

| `AGENTHUB_ANTHROPIC_API_KEY` | unset | Enables the Claude adapter. Server-side only; never logged or returned. |
| `AGENTHUB_OPENAI_API_KEY` | unset | Enables the OpenAI adapter. Same rules. |
| `MODELS_ENABLED` | `true` | Off means every run is simulated, whatever keys exist. |
| `MODEL_ROUTE_FAST_SMALL` | `anthropic:claude-haiku-4-5` | `provider:model` for this tier. |
| `MODEL_ROUTE_BALANCED_LARGE` | `anthropic:claude-sonnet-5` | Same. |
| `MODEL_ROUTE_REASONING_LARGE` | `anthropic:claude-opus-5` | Same. |
| `MODEL_REQUEST_TIMEOUT_SECONDS` | `180` | Per model request. |
| `MODEL_MAX_TURNS` | `8` | Model turns one run may take. |
| `MODEL_REQUESTS_PER_MINUTE_PER_ORG` | `30` | Per organization, per process. |
| `MODEL_DAILY_TOKEN_LIMIT_PER_ORG` | `2000000` | Per organization per UTC day, from the ledger. |

A blank key is the same as no key. Routes are validated when settings load.

**No ambient credentials.** Only the `AGENTHUB_`-prefixed key variables are read:
a plain `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` set machine-wide for other tools
is ignored. Both SDK clients are pinned to the official endpoints, so
`ANTHROPIC_BASE_URL` or `OPENAI_BASE_URL` cannot redirect prompts or keys, and
the OpenAI client drops any ambient `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID` or
`OPENAI_ADMIN_KEY`. One residual: both SDKs still merge `ANTHROPIC_CUSTOM_HEADERS` /
`OPENAI_CUSTOM_HEADERS` from the environment if set; nothing here sets them.

The sandbox limits are checked when settings load: an out-of-range value stops
the process rather than failing every run it later picks up.

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
| `POST` | `/agents/{id}/executions` | owner of the agent, or admin | 202. Queues a run; optional `input` (≤ 8,000 characters) is the task sent to the model. |
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
| `GET` | `/organization/sandbox` | viewer | Sandbox configuration and whether a runtime answers. Starts nothing. |
| `POST` | `/organization/sandbox/check` | admin | Starts one throwaway container and returns every isolation check. |
| `GET` | `/organization/models` | viewer | Providers (configured or not, never the key), routes, limits and today's usage. |

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

**A model may think; nothing acts.** Each run records two independent facts:
`runtime` - `sandbox` when a verified container was created for it (§7),
`simulation` when none was available - and `mode` - `model` when a real model
answered through the gateway (§8), `simulated` when no provider was configured
and the scripted plan below was recorded instead. In both modes no tool is
executed and nothing runs inside the container, so tool calls are recorded as
`unavailable`, `simulated`, `denied` or `failed` - never `succeeded`.

**Every step is committed** as soon as it is done, and a worker heartbeats on a
separate connection while a step waits on a model, so a long model call never
looks like a dead worker (which would pay for the same call twice) and never
holds the database. A run that keeps failing inside its worker is failed after
three claims (`worker_retries`) instead of being retried forever.

What *is* real is everything around the work: the state machine, the budget,
the approval pauses, cancellation, the kill switch, the sandbox, and the record.

**The plan** (`app/runtime/plan.py`) comes from the agent's own declaration:
prepare, think, one step per declared tool, finish. Simulated runs walk it;
model-driven runs let the model decide (§8).

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

## 7. The sandbox

**What it is for.** Agent code must never run on the host. Before a run takes
its first step, the engine starts a container for it, asks the container what
it can do, and decides from the answers whether the run may continue. Nothing
executes inside it yet; this phase builds the box and proves it holds.

**The image** (`agents/sandbox/`) is Alpine Python with a fixed unprivileged
account, uid/gid 65532, and one read-only program: `probe.py`. The probe reports
its identity, whether `/` and `/tmp` are writable, its effective capabilities,
`NoNewPrivs`, whether anything on the network answers or DNS resolves, its
cgroup memory and process limits, whether the container socket or a host path is
visible, and the names (never the values) of its environment variables.

```
docker build -t agenthub/sandbox:0.6.0 agents/sandbox
```

**The container spec** (`app/sandbox/spec.py`) is a pure function from limits to
arguments, so every rule is a unit test:

| Rule | Argument |
| --- | --- |
| Ephemeral | `--rm` |
| Unprivileged | `--user 65532:65532`, `--cap-drop ALL`, `--security-opt no-new-privileges` |
| Nothing persists or executes from disk | `--read-only`, `--tmpfs /tmp:rw,noexec,nosuid,nodev,size=…` |
| No network | `--network none` |
| Bounded | `--memory` equal to `--memory-swap` (no swap), `--cpus`, `--pids-limit` |
| Traceable | `--name agenthub-<execution>`, labels for execution, organization and role |
| Nothing from the host | no `-v`, `--mount`, `--device`, `--env` or `--env-file`, and no socket |

`validate()` is the last gate before a container starts: it refuses
`--privileged`, host PID/IPC/user/network namespaces, `--cap-add`, volumes,
mounts, devices and anything naming `docker.sock`, even though the builder
cannot produce them. A future edit that adds one should fail loudly.

**The runner** (`app/sandbox/runner.py`) drives the runtime's CLI as a
subprocess — never a shell, never a socket handle — with stdin closed. A
container that outlives its timeout is killed and force-removed by name. Output
is capped at 64 KiB. A missing or unresponsive runtime is reported as
unavailable, not as an error.

**Verification** (`app/sandbox/report.py`) turns the probe's answer into 13
checks: non-root, read-only root, writable scratch, no capabilities, no
escalation, no network, no DNS, no container socket, no host mounts, no
credential-shaped variables, only the image's own variables, memory capped, and
processes capped. **A check the container did not answer counts as failed**:
silence is not a clean bill of health.

**What the engine does with it**

| Outcome | Run continues? | Recorded as |
| --- | --- | --- |
| Container starts, every check passes | yes | `runtime = sandbox`, "Sandbox verified" |
| Container starts but a check fails, or it times out | **no**, `FAILED` | error `sandbox_unsafe`, naming the failed checks |
| No runtime, `REQUIRE_SANDBOX=false` | yes | `runtime = simulation`, "No sandbox available" |
| No runtime, `REQUIRE_SANDBOX=true` | **no**, `FAILED` | error `sandbox_unavailable` |

The full report is stored on the execution (`sandbox_report`) and returned by
`GET /executions/{id}`, so the claim "this run was isolated" can be checked. A
box that starts but does not hold fails the run, because it looks like
protection without providing it.

**Not yet:** anything running inside the container, an egress gateway (the
network is simply absent), a custom seccomp profile (Docker's default applies),
user-namespace remapping, and stronger isolation such as gVisor or microVMs.

## 8. The model gateway

**What is real now.** When an agent's tier routes to a provider with
credentials, a real model answers the run. Everything it does goes through two
gateways; neither lets it touch anything.

**Tiers and routes** (`app/llm/routing.py`). Agents choose a tier, never a
vendor model. Each deployment decides what a tier means:

| Tier | Default route | Setting |
| --- | --- | --- |
| `fast-small` | `anthropic:claude-haiku-4-5` | `MODEL_ROUTE_FAST_SMALL` |
| `balanced-large` | `anthropic:claude-sonnet-5` | `MODEL_ROUTE_BALANCED_LARGE` |
| `reasoning-large` | `anthropic:claude-opus-5` | `MODEL_ROUTE_REASONING_LARGE` |

A route is `anthropic:<model>` or `openai:<model>`. No OpenAI model is routed by
default, and none is priced: this code does not guess which models an account
has or what they cost.

**Adapters** (`app/llm/providers/`). One per provider, each through its
official SDK, each translating to and from neutral types (`app/llm/types.py`):

- *Claude* streams every request and waits for the final message; sends no
  temperature (current models reject sampling parameters); caches the stable
  system prompt and tool list; and for `claude-opus-5` and `claude-fable-5-1`
  opts into Anthropic's server-side refusal fallback (`fallbacks="default"`),
  recording the model that actually answered. Assistant turns are replayed
  exactly as Claude produced them, except the blocks Anthropic says to drop
  after a mid-answer fallback.
- *OpenAI* uses Chat Completions. Tool arguments that are not a JSON object are
  marked malformed and refused, never repaired.
- Both map SDK exceptions to platform errors without chaining the original, so
  a request, header or key an SDK exception might carry never reaches a log.

**The gateway** (`app/llm/gateway.py`) resolves the route, refuses a provider
without credentials, enforces the organization's requests per minute (per
process, like sign-in throttling) and daily token budget (counted from the
ledger), calls the adapter, and writes a `model_usage` row for **every** request
- answered, refused, failed or throttled - with tokens and an estimated cost. It
never logs a prompt, an answer or a key.

**The tool gateway** (`app/runtime/tools.py`). Only tools the agent declared and
was granted are offered. Every call the model makes is checked, in order: is it
a tool this agent may use; are the arguments a JSON object matching the tool's
schema exactly (unknown fields rejected); does the grant require a person's
approval. Then it is **not executed** - no tool has an implementation until
Phase 8's egress protection exists - and the model is told so in plain words.

| The model asks for… | Recorded as | The model is told |
| --- | --- | --- |
| a tool it was not given | `denied` | Refused |
| arguments outside the schema | `failed` | Invalid arguments, and which |
| an approved tool, or one needing no approval | `unavailable` | Not executed; no result |
| a tool a person refused | `denied` | Refused by that person |

**The loop** (`app/runtime/agent_loop.py`). Each engine step is one model turn or
one tool call, and the conversation is saved on the execution between steps, so
the kill switch, cancellation and budgets apply between every turn and every
call, and a run paused for approval - or reclaimed from a dead worker - resumes
exactly where it was without asking the model again. A run ends when the model
answers; fails on `turn_limit` (`MODEL_MAX_TURNS`), `token_budget`,
`tool_call_budget`, `model_refused`, `model_truncated` (a tool call cut off by
the output limit) or `model_<error>`; and a truncated text answer is kept and
flagged. The model's text is the run's result, stored and returned as text.

**Without credentials** nothing changes from Phase 6: runs are `simulated`, and
the timeline says which tier had no provider.

**Checking real calls.** The automated suite never reaches a provider: an
autouse fixture gives every test a gateway with no providers, and model-driven
tests use a scripted stand-in that lives in the test package. To check real
credentials and routes (a few cents per run):

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.model_smoke_test --yes
```

**Not yet:** executing any tool, streaming answers to the browser token by token,
per-agent instruction prompts beyond the description, shared-store rate limits
for several processes, and prices for OpenAI models.

## 9. Domain rules

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

## 10. Database

- **Runtime tables:** `execution_events`, `execution_logs`,
  `execution_tool_calls` and `execution_approvals`, all cascading from the
  execution. `executions` also carries the budget it was given, the worker
  claim, the heartbeat, any error, and `sandbox_report` — what its container
  said about its own isolation, null for runs that never had one; `mode`,
  `model_route`, `input_text`, `cost_microusd` and `conversation` for
  model-driven runs.
- **Usage ledger:** `model_usage`, one row per model request with tier,
  provider, requested and served model, outcome, tokens, estimated cost in
  micro-dollars and the provider's request id. Counts only - never a prompt or
  an answer. Rows outlive a deleted execution: spend is spend.
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

## 11. Testing

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

The model gateway is tested without a network or a key. Adapters are fed each
SDK's own response types and a recording client (`test_llm_providers.py`):
request shape, no sampling parameters, caching, refusal fallback only for the
models that take it, the fallback echo rule, malformed tool arguments and every
error mapping. Routing, pricing and the tool gateway's decisions are unit
tested (`test_llm_gateway.py`). Whole runs go through the real engine, worker
and API with a scripted provider (`test_model_runs.py`): answers, tool calls
checked but not run, refusals and schema rejections, approval pauses that
resume without re-asking the model, refusal, truncation, the turn, token, rate
and daily limits, provider failures in the ledger, the status endpoint never
returning a key, and organization isolation of usage.

The sandbox is tested in three layers, and only one of them needs a daemon:

- **What AgentHub asks for** (`test_sandbox_spec.py`, `test_sandbox_report.py`,
  `test_sandbox_probe.py`): every container argument, the refusal of dangerous
  ones, the verdict for each check including silent and malformed answers, and
  the probe's judgement of which environment variables are leaks.
- **What AgentHub does with the answer** (`test_sandbox_runner.py`,
  `test_sandbox_engine.py`): the runner is driven against a stand-in `docker`
  executable that records its arguments — exact arguments, empty stdin,
  timeouts with forced removal, non-zero exits, unreadable and oversized
  output. The engine is driven with stub sandboxes through every row of the
  outcome table in §7, and misconfigured limits are refused at startup. An
  autouse fixture guarantees no other test ever touches the host's container
  runtime.
- **What a kernel actually does** (`test_sandbox_container.py`, marked
  `sandbox`): starts the real image and requires all 13 checks to pass, the
  limits to be the ones asked for, and no container to be left behind. These
  skip without a runtime and image; the `sandbox` CI job builds the image and
  sets `AGENTHUB_REQUIRE_SANDBOX_TESTS=1`, which turns a skip into a failure.

```powershell
docker build -t agenthub/sandbox:0.6.0 agents/sandbox
cd backend
.\.venv\Scripts\python.exe -m pytest -m sandbox
```

## 12. Security status

Implemented: a model gateway that keeps provider credentials server-side, never
logs prompts, answers or keys, and meters every request against per-organization
rate and daily token limits; a tool gateway that checks every model tool call
against the agent's grants, a strict schema and human approval, and executes
none; model output treated as data throughout; a per-run container that is
ephemeral, non-root, capability-free, read-only, network-less and
resource-limited, checked from the inside before every run and failing the run
when it does not hold, budgets enforced per run,
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
multiple workers, executing any tool, an egress gateway, prompt-injection
defences beyond treating all model and tool text as data, a custom seccomp
profile, and real security scanning (Phase 8). Real model calls are tested
against scripted stand-ins only: no provider was called while this phase was
built, because no credentials were available.
Real-container isolation is verified only in CI: it was not exercised on the
machine this phase was built on, which has no container runtime. Grants and policies are checked
before every tool call, but no tool runs, so they are enforced against
requests rather than actions. Verification is a stored label, not the result of a
review anyone performed. Nothing here has been penetration-tested or reviewed by
anyone outside this repository.
