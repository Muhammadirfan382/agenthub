# Monitoring

How to see what AgentHub is doing, and what to do when it says something is
wrong. Phase 9 of the [roadmap](ROADMAP.md). For the code, see
[BACKEND.md](BACKEND.md) §10.

There are four signals, and each one answers a different question:

| Signal | Where | Answers |
| --- | --- | --- |
| Logs | stdout, one JSON object per line | What happened to this request or run? |
| Metrics | `GET /api/v1/metrics` (Prometheus text format) | How much, how fast, how often is it failing? |
| Traces | OpenTelemetry, exported over OTLP/HTTP if configured | Where did the time go in this request or run step? |
| Alerts | `alerts` table, the Security screen, an optional webhook | Does something need a person? |

None of them carries prompts, answers, fetched content, credentials or personal
data. That is enforced in code, not by convention: see
[What is never recorded](#what-is-never-recorded).

## 1. Logs

Every line is JSON with `level`, `logger`, `message`, `request_id`, `trace_id`
and `span_id`, plus any structured fields the caller passed with `extra=`.
Search by `request_id` (returned to clients in `X-Request-ID`) or by `trace_id`
(returned in `X-Trace-Id`) to follow one request.

Before a line is written, the message, every extra field and the last line of
any exception pass through `app/observability/redaction.py`, which removes
provider keys and tokens by shape (`sk-…`, `ghp_…`, `AKIA…`), bearer and basic
credentials, the value after any `password`, `token`, `secret`, `api_key`,
`authorization` or `cookie` name, email addresses, and query-string values.
Redaction is a backstop. Code still must not log secrets or personal data in
the first place.

## 2. Metrics

`GET /api/v1/metrics` serves a private registry, so there are no stray library
metrics. Every metric is named `agenthub_*` and defined in
`backend/app/observability/metrics.py`.

| Metric | Labels | Meaning |
| --- | --- | --- |
| `agenthub_build_info` | `version`, `environment` | Always 1; which build is running. |
| `agenthub_http_requests_total` | `method`, `route`, `status` | Requests by route **template** and status class (`2xx`…`5xx`). |
| `agenthub_http_request_duration_seconds` | `method`, `route` | Latency histogram. |
| `agenthub_executions_started_total` | `mode` | Runs started, by `model`, `sandbox` or `simulated`. |
| `agenthub_executions_finished_total` | `status`, `mode` | Runs that reached a final status. |
| `agenthub_execution_duration_seconds` | `status` | Run duration histogram. |
| `agenthub_executions_queued` / `_running` | none | Gauges, published by the worker. |
| `agenthub_approvals_pending` | none | Approvals waiting on a person. |
| `agenthub_model_requests_total` | `provider`, `model`, `outcome` | Provider calls and how they ended. |
| `agenthub_model_request_duration_seconds` | `provider`, `model` | Provider latency. |
| `agenthub_model_tokens_total` | `provider`, `model`, `kind` | Input, output, cache read and cache write tokens. |
| `agenthub_model_cost_microusd_total` | `provider`, `model` | Estimated spend, from published prices. |
| `agenthub_tool_calls_total` | `tool`, `status` | Tool calls by outcome. |
| `agenthub_policy_decisions_total` | `effect`, `rule` | Every policy decision. |
| `agenthub_egress_requests_total` | `outcome`, `rule` | Outbound requests: sent or blocked, and by which check. |
| `agenthub_sandbox_checks_total` | `result` | Sandbox verifications. |
| `agenthub_alerts_active` | `rule`, `severity` | Firing in-app alerts. |

**Labels are bounded.** Routes are templates (`/api/v1/agents/{agent_id}`),
never paths. Statuses are classes. No label holds an organization id, user,
email, agent name or anything else a caller controls. A new label must have a
fixed, small set of values. Otherwise it belongs in a trace attribute or a log
field.

**Access.** Set `METRICS_TOKEN`, then scrape with
`Authorization: Bearer <token>`. Production refuses to start with metrics on
and no token. Development leaves the endpoint open for convenience. Set
`METRICS_ENABLED=false` to remove it entirely (404). The endpoint does not
measure itself.

Counters live in each process. In production the worker is its own process
on the host and counts most of what matters (runs, model calls, tool calls,
egress, sandbox checks, alert gauges). With `WORKER_METRICS_PORT` set it
serves them at `GET /metrics` on `WORKER_METRICS_HOST`, behind the same token.
`infrastructure/deployment/prometheus.yml` scrapes both, as jobs `agenthub`
and `agenthub-worker`. With several processes, scrape each one: Prometheus
sums them.

## 3. Traces

A tracer provider is always installed, so every log line carries a trace id
even when nothing is exported. Set `OTLP_ENDPOINT` (for example
`http://otel-collector:4318/v1/traces`) to export spans in batches over
OTLP/HTTP.

Spans:

- `GET /api/v1/…`: one per request, named by route template, with method,
  route and status code. An incoming W3C `traceparent` is continued, so a
  frontend or gateway trace joins up.
- `execution.step`: one per runtime step.
- `sandbox.probe`: the container isolation check.
- `model.complete`: each provider call, with `gen_ai.*` attributes for system,
  model and token counts. It carries no prompt or answer.
- `egress.request`: each outbound request, with the host and outcome. It
  carries no body or query string.

Export was tested against the in-process SDK only. It has not been run
against a real collector in this repository.

## 4. Alerts

### In-app rules

The worker evaluates these for every organization every
`ALERT_INTERVAL_SECONDS` (default 60). A rule that matches opens one alert, or
bumps `occurrences` on the one already firing. A rule that stops matching
resolves its alert. Administrators can resolve an alert by hand on the
Security screen (`POST /api/v1/alerts/{id}/resolve`, audited as
`alert.resolved`). A hand-resolved alert fires again on the next evaluation if
its rule still matches.

| Rule | Severity | Fires when |
| --- | --- | --- |
| `runs_failing` | warning | `ALERT_FAILED_RUNS` (3) or more runs failed in 15 minutes. |
| `stalled_runs` | warning | A claimed run has sent no heartbeat for `ALERT_STALLED_RUN_SECONDS` (300). |
| `policy_denials` | warning | `ALERT_POLICY_DENIALS` (10) or more tool calls were refused by policy in 15 minutes. |
| `egress_blocked` | warning | The same threshold of outbound requests was blocked in 15 minutes. |
| `sandbox_unverified` | **critical** | A run stopped in the last hour because its sandbox could not be verified. |
| `model_errors` | warning | `ALERT_FAILED_RUNS` or more provider calls failed in 15 minutes. |
| `model_budget` | warning / **critical** | 90% of the daily token budget is used / it is spent. |
| `kill_switch` | info | The organization's kill switch is engaged. |

### The webhook

Set `ALERT_WEBHOOK_URL` (HTTPS only) to have each **newly** firing alert
POSTed as JSON with `source`, `rule`, `severity`, `summary`, `detail` (counts
only), `organization` and `at`. The request goes through the same egress
gateway as agent traffic, so a webhook that resolves to a private, loopback or
metadata address is refused, and redirects are not followed. A failed delivery
is logged. It never stops evaluation.

### Prometheus rules

`infrastructure/monitoring/prometheus-rules.yml` mirrors the in-app rules for
teams that run their own Prometheus, and adds availability rules (down, error
rate, latency, queue backlog). Load it with `rule_files` and scrape the backend
as job `agenthub`. The file parses as YAML, and every metric it uses exists.
It has **not** been evaluated by a running Prometheus here.

## 5. Health

| Endpoint | Auth | Use |
| --- | --- | --- |
| `GET /api/v1/health` | none | Liveness: the process answers. |
| `GET /api/v1/health/ready` | none | Readiness: 200 if the database answers `SELECT 1`, 503 if not. It names no configuration. |
| `GET /api/v1/system/status` | viewer | Per-component state (API, database, runtime, models, sandbox, security) for the dashboard. |

`system/status` is honest rather than green. With no provider key, `models` is
`degraded`. With no container runtime, `sandbox` is `degraded`. With queued work
and no live worker heartbeat, `runtime` is an `outage`. Any firing alert
degrades `security`. "Provider key" and "container runtime" mean the
runtime's, not the API process's. In production the worker holds both and
reports them every minute (`runtime_workers`). A worker silent for three
minutes stops counting.

## 6. Runbooks

### agenthubdown

Prometheus cannot scrape the backend. Check the process is running and
`/api/v1/health` answers. If it answers but scrapes fail, check `METRICS_TOKEN`
matches the scrape configuration (a mismatch is 403) and that
`METRICS_ENABLED` is not `false` (404). If the process exits at startup, its
last log line says which setting it refused.

### agenthubhigherrorrate

More than 5% of requests return 5xx. Group `agenthub_http_requests_total{status="5xx"}`
by `route` to find the endpoint. Take a `trace_id` from a failing response's
`X-Trace-Id` and search the logs for it. The handler logs the exception with
the request id, and clients only ever see `internal_error`. Check
`/api/v1/health/ready` first: a database outage fails almost every route.

### agenthubslowrequests

p95 latency is above two seconds. Group the duration histogram by `route`.
Slow run-related routes usually mean database contention. Check the database
before the application. Traces show which span inside the request took the
time.

### runs_failing

Several runs failed recently. Open Executions, filter by `FAILED` and read the
error code on each run. `model_*` codes point at the provider (see
[model_errors](#model_errors)), `sandbox_*` codes at the container runtime (see
[sandbox_unverified](#sandbox_unverified)), and budget codes at agent limits.
If failures are spreading, the organization's kill switch stops new runs
while you investigate.

### stalled_runs

A worker claimed a run and went silent. The runtime reclaims abandoned runs
automatically after the stale-claim interval, so a single stalled run usually
clears itself. If it keeps firing, check that a worker process is running
(`runtime` on the status card) and that it can reach the database.

### agenthubqueuebacklog

Runs are queueing faster than workers claim them. Check that a worker is
running (`RUNTIME_WORKER_ENABLED`, or a separate `python -m app.runtime.worker`)
and whether the kill switch is engaged. Add workers if the load is real.

### sandbox_unverified

**Critical.** A run could not get a verified sandbox and was stopped. With
`REQUIRE_SANDBOX=true` this is the platform refusing to run unsafely, which is
correct. Find out why. Run the check on Settings → Runtime (`POST
/organization/sandbox/check`) and read which isolation check failed. A failed
check means the container runtime is not providing the isolation AgentHub asks
for. Do not work around it by turning the sandbox off: fix the runtime.

### egress_blocked

Many outbound requests were blocked. Group
`agenthub_egress_requests_total{outcome="blocked"}` by `rule`, then read the
`egress.blocked` events in the audit log to see which agent and which check.
A burst against `private_address` or `not_allowed` hosts from one agent
suggests it is being steered by content it read. Suspend its installation,
review what it fetched and consider the kill switch. A burst after a config
change usually means an agent's allowed domains are wrong.

### policy_denials

Many tool calls were refused by policy. Read the `policy.denied` events in the
audit log. Denials by one agent for capabilities it was never granted suggest
prompt injection or a misconfigured manifest. Denials across many agents after
a change suggest the grants were narrowed too far.

### alerts

An in-app alert with severity `critical` is firing. Open Security in the app
to see which one, then follow its runbook here.

### model_errors

Provider calls are failing. Group `agenthub_model_requests_total` by `outcome`.
`authentication` means the key is wrong or revoked. `rate_limited` means the
provider, or this platform's own per-organization limit, is throttling.
`unavailable` means the provider failed or timed out. `bad_request` means
AgentHub sent something the provider refused, which is a bug worth reporting.
`budget_exhausted` means the daily token budget is spent (see `model_budget`).
Settings → Runtime shows which providers are configured and today's usage. Keys
are never displayed.

## What is never recorded

- Prompts, model answers, tool arguments and fetched content: not in logs, not
  in span attributes, not in metrics, not in the webhook.
- Credentials: keys are never logged, and redaction removes any that slip into
  a message.
- Personal data: no emails, names or organization ids in metric labels. Logs
  are redacted of email addresses. Webhook payloads carry counts.

`test_observability.py` asserts the metrics endpoint contains neither the
organization id nor the signed-in email after traffic.
`test_alerts_and_insights.py` asserts the webhook payload has exactly the
fields listed above.
