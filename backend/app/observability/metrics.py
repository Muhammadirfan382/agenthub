"""What AgentHub measures about itself, in Prometheus' format.

One registry, defined in one place, so every metric's name, labels and meaning
can be read at once. Two rules govern what may become a label:

* **No personal data and no content.** Never an email, a user id, a prompt, an
  answer or a URL. Organization ids are deliberately absent too: a metric says
  *how many*, the audit log says *who*.
* **Bounded values only.** Labels come from fixed sets - a status, a tool name
  from the catalog, a provider, a route template - so the number of series
  cannot grow with traffic.

Counters and histograms live in this process. Several processes each keep their
own; an aggregating scrape (or a shared store) is a deployment concern.
"""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

#: A private registry rather than the global default: the metrics are ours, and
#: tests can build a fresh one without leaking state between them.
REGISTRY = CollectorRegistry()

# --- the platform itself -----------------------------------------------------

BUILD = Gauge(
    "agenthub_build_info",
    "Always 1. Its labels carry the running version and environment.",
    ["version", "environment"],
    registry=REGISTRY,
)

# --- HTTP --------------------------------------------------------------------

#: Seconds. Buckets cover a fast JSON API; the top bucket catches model-bound work.
HTTP_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

HTTP_REQUESTS = Counter(
    "agenthub_http_requests_total",
    "HTTP requests, by method, route template and status class.",
    ["method", "route", "status"],
    registry=REGISTRY,
)
HTTP_DURATION = Histogram(
    "agenthub_http_request_duration_seconds",
    "How long requests take, by method and route template.",
    ["method", "route"],
    buckets=HTTP_DURATION_BUCKETS,
    registry=REGISTRY,
)

# --- executions --------------------------------------------------------------

EXECUTION_DURATION_BUCKETS = (0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600)

EXECUTIONS_STARTED = Counter(
    "agenthub_executions_started_total",
    "Runs the worker began, by mode (model or simulated).",
    ["mode"],
    registry=REGISTRY,
)
EXECUTIONS_FINISHED = Counter(
    "agenthub_executions_finished_total",
    "Runs that reached an end, by final status and mode.",
    ["status", "mode"],
    registry=REGISTRY,
)
EXECUTION_DURATION = Histogram(
    "agenthub_execution_duration_seconds",
    "How long finished runs took, by final status.",
    ["status"],
    buckets=EXECUTION_DURATION_BUCKETS,
    registry=REGISTRY,
)
EXECUTIONS_QUEUED = Gauge(
    "agenthub_executions_queued",
    "Runs waiting to be claimed, as the worker last saw it.",
    registry=REGISTRY,
)
EXECUTIONS_RUNNING = Gauge(
    "agenthub_executions_running",
    "Runs claimed and in progress, as the worker last saw it.",
    registry=REGISTRY,
)
APPROVALS_PENDING = Gauge(
    "agenthub_approvals_pending",
    "Tool calls waiting for a person, as the worker last saw it.",
    registry=REGISTRY,
)

# --- the model gateway -------------------------------------------------------

MODEL_LATENCY_BUCKETS = (0.25, 0.5, 1, 2.5, 5, 10, 20, 40, 80, 160)

MODEL_REQUESTS = Counter(
    "agenthub_model_requests_total",
    "Model requests, by provider, model and outcome (ok, refused or an error kind).",
    ["provider", "model", "outcome"],
    registry=REGISTRY,
)
MODEL_DURATION = Histogram(
    "agenthub_model_request_duration_seconds",
    "How long model requests take, by provider and model.",
    ["provider", "model"],
    buckets=MODEL_LATENCY_BUCKETS,
    registry=REGISTRY,
)
MODEL_TOKENS = Counter(
    "agenthub_model_tokens_total",
    "Tokens billed, by provider, model and kind (input, output, cache_read, cache_write).",
    ["provider", "model", "kind"],
    registry=REGISTRY,
)
MODEL_COST = Counter(
    "agenthub_model_cost_microusd_total",
    "Estimated spend in millionths of a US dollar. Unpriced models add nothing.",
    ["provider", "model"],
    registry=REGISTRY,
)

# --- tools, policy and egress ------------------------------------------------

TOOL_CALLS = Counter(
    "agenthub_tool_calls_total",
    "Tool calls a model asked for, by tool and what became of them.",
    ["tool", "status"],
    registry=REGISTRY,
)
POLICY_DECISIONS = Counter(
    "agenthub_policy_decisions_total",
    "Policy engine decisions, by effect and the rule that decided.",
    ["effect", "rule"],
    registry=REGISTRY,
)
EGRESS_REQUESTS = Counter(
    "agenthub_egress_requests_total",
    "Outbound requests, by outcome. Blocked ones carry the rule that refused them.",
    ["outcome", "rule"],
    registry=REGISTRY,
)

# --- the sandbox -------------------------------------------------------------

SANDBOX_CHECKS = Counter(
    "agenthub_sandbox_checks_total",
    "Sandbox verifications, by result (isolated, unsafe or unavailable).",
    ["result"],
    registry=REGISTRY,
)

# --- alerts ------------------------------------------------------------------

ALERTS_ACTIVE = Gauge(
    "agenthub_alerts_active",
    "Alerts currently firing, by rule and severity.",
    ["rule", "severity"],
    registry=REGISTRY,
)


def status_class(status_code: int) -> str:
    """`2xx`, `4xx`, ... - a bounded label where the exact code is not."""
    return f"{status_code // 100}xx"


def record_build(version: str, environment: str) -> None:
    BUILD.labels(version=version, environment=environment).set(1)
