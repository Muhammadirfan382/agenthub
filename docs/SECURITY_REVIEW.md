# Security review — Phase 8

**What this is:** a review of the whole codebase by the people who wrote it,
done while building the security layer. It is not independent and it is not a
penetration test. Its value is that each finding below is specific, and each
fix is covered by a test that fails if the fix is undone.

**Scope:** backend (`backend/app`), frontend (`frontend/src`), CI
(`.github/`), dependencies. Date: 2026-09-18.

## Findings

| # | Finding | Severity | Introduced | Status |
| --- | --- | --- | --- | --- |
| 1 | An agent's declared security policy - `networkEgress`, `allowedDomains`, `approvalRequiredFor` - was validated on save but **never enforced at run time**. A tool call at a risk level the agent said needs approval went ahead without one. | High | Phase 2 (schema), Phase 7 (tool gateway) | **Fixed.** The policy engine enforces all three (`security/policy.py`); `test_policy.py`, `test_containment.py`. |
| 2 | Recording failed sign-ins did extra database work only for existing accounts, making their responses measurably slower: **account enumeration by timing**, undoing the dummy-hash defence. | Medium | Phase 8 (this phase's own first draft) | **Fixed.** Recorded in a background task after the response is sent (`api/v1/auth.py`); `test_security_layer.py`. |
| 3 | A machine-wide `ANTHROPIC_API_KEY` set for other tools was picked up and used; SDKs also honoured ambient base URLs, org and project ids. | High | Phase 7 | **Fixed in Phase 7.** Namespaced keys, pinned endpoints; `test_llm_gateway.py::TestNoAmbientCredentials`. |
| 4 | API responses had no Content-Security-Policy, no cross-origin isolation headers, and no HSTS; the built frontend had no CSP. | Medium | Phase 2 | **Fixed.** `core/middleware.py`, `src/config/contentSecurityPolicy.ts`; verified the production build renders with no CSP violations. |
| 5 | CI actions were referenced by movable tags. | Medium | Phase 0 | **Fixed.** Pinned to commit SHAs; Dependabot for updates. |
| 6 | No dependency or secret scanning in CI. | Medium | Phase 0 | **Fixed.** `security` job: pip-audit, npm audit, gitleaks over full history (checksum-verified binary). |
| 7 | No limit on state-changing requests outside sign-in. | Low | Phase 2 | **Fixed** per process (`WriteRateLimitMiddleware`); shared-store limits are Phase 10. |
| 8 | No audit trail for security decisions. | Medium | Phase 3 onwards | **Fixed.** Append-only audit log, admin-read only, key-filtered details. |
| 9 | Secrets could only come from environment variables or `.env`. | Low | Phase 2 | **Fixed** for file mounts (`SECRETS_DIR`); vault integration is open. |

## Checked, nothing found

- **Dangerous calls:** no shell execution, `eval`, `exec`, pickle, unsafe YAML,
  string-built SQL, `innerHTML`/`dangerouslySetInnerHTML`, or disabled TLS
  verification anywhere. The only subprocess is the sandbox runner: `exec` with
  a fixed, validated argument list and no shell.
- **Authorization:** every route refuses an unauthenticated caller (a test walks
  the OpenAPI schema); foreign ids answer 404; the audit log is admin-only and
  has no write endpoint.
- **Dependencies:** `pip-audit` (runtime and dev) and `npm audit` (all
  dependencies) report no known vulnerabilities as of this review.
- **Secrets in the repository:** staged content scanned for key-shaped strings
  before every commit; gitleaks over full history runs in CI. It was **not** run
  locally in this review (it would mean downloading and running a binary on the
  developer's machine).

## Open, by decision

See [THREAT_MODEL.md](THREAT_MODEL.md) §5 for the full list. The most
important: prompt injection is **contained**, not prevented - a hijacked agent
cannot act beyond its grants, but can still be misled; live injection
evaluations against real models have not been run; allowed domains are trusted
completely; rate limits are per process.

## Phase 10 review (deployment)

Date: 2026-09-21. Same caveat: by the authors, not independent. Scope: what
changes when AgentHub runs as separate processes behind a reverse proxy on a
real host.

| # | Finding | Severity | Status |
| --- | --- | --- | --- |
| 10 | Behind a reverse proxy, `request.client.host` is the proxy for everyone: all anonymous clients would share one sign-in limiter key, so **20 failed sign-ins from anyone would lock out every anonymous sign-in** (and share the write limit). | High (in deployment) | **Fixed in configuration**: uvicorn honours `X-Forwarded-For` only from Caddy's fixed address (`--proxy-headers`, `FORWARDED_ALLOW_IPS`), and Caddy ignores incoming forwarded headers. Not exercised on a host. |
| 11 | The sandbox runner started the container CLI with the worker's **entire environment**, including the database URL and provider keys. The containers never saw them, but any CLI plugin or wrapper could. | Medium | **Fixed**: an allow-list of variables (`RUNTIME_ENVIRONMENT`); `test_sandbox_runner.py`. |
| 12 | The metrics token was compared with `!=`, which is not constant-time. | Low | **Fixed**: `hmac.compare_digest`, shared by the API and worker endpoints; `test_runtime_workers.py`. |
| 13 | Split into processes, the API would have reported providers "not configured" and the sandbox "unavailable" (it holds neither), and the worker's metrics (runs, models, egress, sandbox, alerts) would not have been served anywhere. | Medium (misleading status, blind monitoring) | **Fixed**: workers report capabilities (`runtime_workers`); the worker serves its own token-protected `/metrics`; `test_runtime_workers.py`. |
| 14 | A default edge access log would record every visitor's IP address. | Low | **Avoided**: no access log in the Caddyfile. |

The deployment's own controls (non-root read-only containers, no socket,
rootless sandbox under a separate account, digest-only forced-command CD) are
listed with their evidence in [SECURITY_SIGNOFF.md](SECURITY_SIGNOFF.md),
together with what blocks production.
