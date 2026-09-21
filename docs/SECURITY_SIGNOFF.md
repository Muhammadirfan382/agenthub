# Security sign-off — Phase 10

**Decision: not signed off for production with real users' data.** AgentHub
is ready for a **staging deployment and a supervised pilot** with trusted
users and non-sensitive data. It is not ready for production until the
blocking items below are done.

**Who wrote this:** the same people who built the system, at the end of
Phase 10. It is a self-assessment against the rules in
[CLAUDE.md](../CLAUDE.md), the [threat model](THREAT_MODEL.md) and the
[security review](SECURITY_REVIEW.md). It is not an independent review, and
nothing has been penetration-tested. Date: 2026-09-21.

## Blocking before production

| # | Item | Why it blocks |
| --- | --- | --- |
| 1 | **An independent security review and penetration test**, covering the API, the edge, the sandbox and the deployment | Everything here has been reviewed only by its authors. |
| 2 | **Exercise the deployment on a real staging host**: first deploy, a failed deploy's automatic rollback, a manual rollback, and a restore from backup | None of it has run ([DEPLOYMENT.md](DEPLOYMENT.md) §6). The rootless sandbox socket shared across two accounts is the least certain part. |
| 3 | **Run CI green on `main`**: image scans, the load test, the backup and restore test, the real-container sandbox tests, and the Python 3.13 leg | Written, never executed. Nothing has been pushed. |
| 4 | **MFA for administrators and owners** | Password-only sign-in protects the accounts that can grant agents capabilities and release the kill switch. |
| 5 | **Off-host, encrypted backups** configured (`AGENTHUB_BACKUP_UPLOAD`) or a managed database with point-in-time recovery | Local backups do not survive losing the host. |
| 6 | **Verify provenance at deploy time** (`gh attestation verify` for each digest before `agenthub-deploy` pulls it) | Attestations are created but not checked, so a digest pushed to the registry by other means would be accepted. The prefix check is a partial guard. |

## Should do soon after

- Live prompt-injection evaluations against real models ([THREAT_MODEL.md](THREAT_MODEL.md) §5).
- Egress rules on the host so the API container can reach only the database
  (today it has a general outbound route, needed for a managed database).
- Shared-store rate limits, so more than one API process can run.
- Password reset and email verification (need email delivery).
- A custom seccomp profile for sandbox containers.

## Checked

| Area | State | Evidence |
| --- | --- | --- |
| Secrets | Never in the repository, images or logs. Files with owner/group/mode set per consumer. The API cannot read the worker's provider keys. | `.dockerignore` allow-lists; gitleaks in CI; staged-content scans before each commit; [DEPLOYMENT.md](DEPLOYMENT.md) §2 |
| Untrusted code on the host | Never. Sandboxes run under a rootless daemon owned by an account with no secrets. The worker has no capabilities and systemd confinement. | `agenthub-worker.service`, `setup-host.sh`, `test_sandbox_*` |
| Container runtime socket | Never mounted into any container | `compose.yml` (no socket volumes), worker on the host |
| Privileged containers, host networking | None. Every service runs read-only as a fixed non-root uid with all capabilities dropped and no-new-privileges. | `compose.yml` |
| Authentication and authorization | Enforced server-side on every route. A test walks the route table. | `test_authorization.py` |
| Input at trust boundaries | Validated. Model output and fetched content are treated as data. | Phases 7–8, `test_containment.py` |
| SSRF | Egress gateway; the alert webhook goes through it too | `test_egress.py`, `test_alerts_and_insights.py` |
| The sandbox CLI's environment | Allow-listed: no database URL or keys reach it | `test_sandbox_runner.py` |
| Client addresses behind the proxy | Taken from `X-Forwarded-For` only when Caddy sent it | `FORWARDED_ALLOW_IPS`, `--proxy-headers`; not exercised on a host |
| Supply chain | Base images and CI actions pinned by digest or SHA; tools checksum-verified; images scanned; SBOMs; build provenance | `ci.yml`, Dockerfiles, `dependabot.yml` |
| CD blast radius | The pipeline's key is bound to one script, which accepts only digests under one prefix. Production needs approval. | `agenthub-deploy --ssh`, `deploy.yml` |
| Logs and personal data | Redacted logs; no access logs at the edge; metrics carry no ids or emails | Phase 9, `Caddyfile` |
| Transport | HTTPS only, HSTS, automatic certificates, secure cookies | `Caddyfile`, Phase 3 |

## Residual risks accepted for a pilot

- Prompt injection is contained, not prevented. Allowed domains are trusted
  completely.
- Rate limits are per process, and there is one process.
- An attacker who controls the GitHub organization can publish images under
  the allowed prefix (see blocking item 6).
- A single host is a single point of failure. Recovery is a restore onto a
  new host.
