# Performance

What is measured, what a release must meet, and what limits capacity today.

> **No numbers yet.** The load test below runs in CI against the production
> compose stack on every build, but CI has not run it: nothing has been pushed.
> This page states the budget and the method. Record the first measured
> results here when they exist, with the date and the runner type.

## The load test

`tests/load/agenthub.js` (k6), run by the CI `images` job against the real
images: Caddy, then the API, then PostgreSQL, started from the production
compose file with the same hardening.

- **Model:** signed-in people browsing. 25 virtual users for two minutes, each
  loading the dashboard's reads, agent and execution lists, the marketplace,
  security and analytics, with 1–3 s of think time between pages. Setup
  creates ten agents so the lists have rows.
- **Budget (enforced; the build fails when missed):**

  | Metric | Threshold |
  | --- | --- |
  | Failed requests | < 1% |
  | Checks passing | > 99% |
  | Read latency p95 / p99 | < 500 ms / < 1500 ms |
  | Health endpoint p95 | < 200 ms |

- **Not modelled:** runs executing (the CI stack has no worker, and a run's
  time is model and sandbox time, not API time), long-lived SSE streams, many
  distinct accounts, and writes beyond setup. Writes are deliberately bounded
  by the per-session write limit.

Run it against staging, never production:

```bash
AGENTHUB_URL=https://staging.example.com AGENTHUB_EMAIL=... AGENTHUB_PASSWORD=... k6 run tests/load/agenthub.js
```

## What limits capacity today

| Limit | Why | Where it goes next |
| --- | --- | --- |
| One API process per host | Sign-in throttling, write limits and model rate limits are per process. More processes would multiply every limit. | Move the limiters to a shared store (Redis or PostgreSQL), then run several API processes. |
| One host | The compose stack is single-host by design. | Several hosts behind a load balancer, once limits are shared. The worker already coordinates through the database. |
| Worker throughput | A worker advances runs from the database queue. Runs are dominated by model latency and sandbox start-up (a container per run). | More worker processes (claims are atomic, so they can run side by side), on the same or other hosts. |
| Database connections | SQLAlchemy's default pool per process | Tune the pool size against the managed database's connection limit when adding processes. |
| Sandbox start-up | One container is started and checked before each run | Measure it first. Pre-warmed containers would trade isolation for speed and need a design review. |

## Where to look when it is slow

`agenthub_http_request_duration_seconds` by route (the `AgentHubSlowRequests`
rule), then traces for the slow route, then the database. See
[MONITORING.md](MONITORING.md).
