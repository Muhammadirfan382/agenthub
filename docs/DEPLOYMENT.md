# Deployment

How AgentHub runs in staging and production, how a release gets there, and
how it is taken back. Phase 10 of the [roadmap](ROADMAP.md). Day-to-day
operation and incidents are in [OPERATIONS.md](OPERATIONS.md). Monitoring is
in [MONITORING.md](MONITORING.md).

> **Status:** everything described here is written and statically checked,
> but none of it has run end to end. No host has been prepared, no image has
> been pushed, and no deploy has happened. The CI jobs that build, scan and
> load-test the images, and that test backup and restore, run on the first
> push to `main`, which has not happened. See [Verification](#verification).

## 1. Shape

```
                  Internet
                     │ 80/443
        ┌────────────▼─────────────── one Debian 13 host ───────────────────────┐
        │  web (Caddy: TLS, SPA, /api proxy)   ── edge network                  │
        │     │                                                                 │
        │     │ app network (internal: no route out)                            │
        │  backend (API)   postgres (bundled-db)   prometheus                   │
        │     │               │ 127.0.0.1:5432         │ 127.0.0.1:9090         │
        │     └── outbound network (managed DB, published loopback ports) ──┐   │
        │                                                                   │   │
        │  agenthub-worker.service  (host process, user agenthub)  ◄────────┘   │
        │     │ DOCKER_HOST=unix:///srv/agenthub-sandbox/run/docker.sock        │
        │  rootless dockerd (user agenthub-sandbox) ── sandbox containers       │
        └───────────────────────────────────────────────────────────────────────┘
```

- **Staging and production are the same stack** on two hosts, with their own
  configuration and secrets. Staging always gets a release first.
- **Images:** `agenthub-backend` (the API, the migrations, and the worker's
  code), `agenthub-web` (the built frontend in Caddy) and `agenthub-sandbox`.
  All three are built once by CI and deployed by digest, never by tag.
- **Why the worker is not a container.** It starts sandbox containers, and
  nothing may be handed a container runtime socket. It runs under systemd as an
  unprivileged account and talks to a **rootless** Docker daemon owned by a
  second account, `agenthub-sandbox`. A process that escaped a sandbox would
  land as `agenthub-sandbox`, which holds no secrets and cannot read the
  worker's secrets. The worker's code is copied out of the backend image at
  deploy time, so it runs the digest the API runs.
- **What the API container holds:** a database URL and the metrics token.
  No provider keys (the worker holds those), no container runtime, and no route
  out except to reach a managed database.

### Least privilege, by component

| Component | Runs as | Can reach | Holds |
| --- | --- | --- | --- |
| web | uid 10002, read-only, no capabilities | the internet (ACME), backend | TLS certificates |
| backend | uid 10001, read-only, no capabilities | database | `database_url`, `metrics_token` |
| postgres (optional) | uid 70, read-only root, no capabilities | nothing it needs | its data |
| prometheus | uid 65534, read-only, no capabilities | backend, worker metrics | `metrics_token` |
| worker | `agenthub`, systemd sandboxing, no capabilities | database, providers, egress allow-list, sandbox socket | database URL, provider keys, metrics token |
| sandbox daemon | `agenthub-sandbox`, rootless | nothing on behalf of runs (`--network none`) | nothing |
| CD key | `agenthub-deploy`, forced command | runs `agenthub-deploy` only | nothing |

## 2. Preparing a host

Debian 13, x86-64, a public IP, and DNS pointing the site's name at it.

1. Install Docker Engine, the Compose plugin and `docker-ce-rootless-extras`
   from Docker's signed apt repository, plus `uidmap`, `python3-venv`, `curl`
   and `jq`. Nothing here pipes a script from the internet into a shell.
2. From a reviewed checkout of this repository, run:

   ```bash
   sudo infrastructure/deployment/host/setup-host.sh --image-prefix ghcr.io/OWNER/agenthub-
   ```

   It creates the accounts (`agenthub`, `agenthub-sandbox`, `agenthub-deploy`,
   group `agenthub-secrets` at gid 10001), the directories, the systemd units
   and timers, a sudoers entry that lets the CD account run the deploy script
   and nothing else, and the rootless sandbox daemon. It installs the host
   scripts into `/opt/agenthub/bin`. Re-running it is the **only** way those
   scripts change on a host. The pipeline can choose digests, not code.
3. Edit `/etc/agenthub/agenthub.env`, `backend.env` and `worker.env`. The
   examples are in `infrastructure/deployment/config/`.
4. Create the secrets. The script prints the exact list. Each is one file
   holding one value:

   | File | Owner, mode | Read by |
   | --- | --- | --- |
   | `/etc/agenthub/secrets/database_url` | `root:agenthub-secrets 0640` | API, migrations, backups |
   | `/etc/agenthub/secrets/metrics_token` | same | API, Prometheus |
   | `/etc/agenthub/secrets/postgres_password` | same | bundled PostgreSQL |
   | `/etc/agenthub/worker/secrets/database_url` | `root:agenthub 0640` | worker |
   | `/etc/agenthub/worker/secrets/metrics_token` | same | worker (same value as the API's) |
   | `/etc/agenthub/worker/secrets/AGENTHUB_ANTHROPIC_API_KEY` | same | worker only |

   Generate tokens with `openssl rand -base64 48`. With a secrets manager,
   render these files from it (Vault Agent, a cloud secrets CSI driver,
   `sops`): AgentHub reads files (`SECRETS_DIR`), so no code changes. Rotate a
   value by replacing the file and redeploying.
5. Let both Docker daemons pull from GHCR with a read-only token (the commands
   are printed by the setup script), or make the packages public.
6. Add the CD public key to `/home/agenthub-deploy/.ssh/authorized_keys`,
   bound to the deploy script:

   ```
   restrict,command="sudo -n /opt/agenthub/bin/agenthub-deploy --ssh" ssh-ed25519 AAAA… agenthub-cd
   ```

7. Open only 22, 80 and 443 inbound. Published loopback ports (5432, 9090)
   and the worker's metrics address (172.30.2.1:9464) are not reachable from
   outside.

**Managed or bundled database.** A managed PostgreSQL 17, with its own
backups, point-in-time recovery, failover and patching, is recommended:
leave `COMPOSE_PROFILES` empty and point both `database_url` files at it. With
`COMPOSE_PROFILES=bundled-db`, PostgreSQL runs in compose on a named volume.
The API reaches it as `postgres:5432` and the worker as `127.0.0.1:5432`, so
the two URL files differ. Redis is not used by anything and is not deployed.

## 3. The pipeline

```
push to main ─► CI ─┬─ security, frontend, backend (3.13 + 3.14), sandbox,
                    │  migrations (+ backup/restore), deployment-config
                    ├─ images: build → Trivy (vulns + Dockerfiles) → SBOM →
                    │          production compose stack → smoke → k6 load test
                    └─ publish (main only): push by digest → provenance attestation
                                             → release.json
Deploy workflow ─► staging (automatic) ─► production (required reviewers)
```

- **What CI proves before anything is published:** the code's tests on both
  Python versions, no known HIGH/CRITICAL fixable vulnerabilities in any image,
  no HIGH/CRITICAL Dockerfile misconfigurations, the production compose file
  starting healthy with its own hardening, the edge behaving (SPA routes,
  framing refused, `/api/v1/metrics` not public, Prometheus scraping with the
  token), the load-test thresholds, and a backup that restores.
- **Publish** pushes exactly the images that were scanned and tested, and
  records build provenance for each digest (`gh attestation verify
  oci://… --owner OWNER`). SBOMs (CycloneDX) are kept as CI artifacts for 90 days.
- **Deploy** runs the host's deploy script over SSH with the three digests.
  Production is a GitHub environment: configure it with required reviewers,
  and every production deploy and rollback waits for that approval.

### What a deploy does on the host

`/opt/agenthub/bin/agenthub-deploy deploy --backend … --web … --sandbox …`

1. Refuses anything that is not a digest under `ALLOWED_IMAGE_PREFIX`.
2. Pulls the images (the sandbox image into the rootless daemon).
3. Backs up the database. If the backup fails, it stops with nothing changed.
4. Runs the migrations.
5. Starts the new containers and waits for their health checks.
6. Installs the worker from the backend image into
   `/opt/agenthub/worker/releases/<digest>`, switches `current`, restarts it.
7. Smoke-tests through the public name (`/api/v1/health/ready`, the app shell)
   and waits for the worker's metrics endpoint to answer.

If any of 4–7 fails, it puts the previous release back the same way and exits
non-zero, so the workflow fails. Every outcome is appended to
`/var/lib/agenthub/history.log`.

### Migrations

**A migration must work with the release before it.** The database is never
downgraded on rollback: a rollback runs the old code against the new schema.
So changes are made in two releases: first *expand* (add the column or table,
keep the old one working), then *contract* (remove the old one) once no
running release uses it. A migration that cannot be written that way needs a
maintenance window and a restore plan, decided before it merges. PostgreSQL
runs migrations in a transaction, so a migration that fails leaves the schema
as it was.

### Rolling back

- **Automatic:** a failed deploy rolls itself back (above).
- **By hand, from GitHub:** run the Deploy workflow with `action: rollback`
  and the environment. For production this also waits for approval.
- **On the host:** `sudo /opt/agenthub/bin/agenthub-deploy rollback` returns
  to the previous release. Running it again returns to the one after it.

## 4. Backups and restore

- **Daily** (`agenthub-backup.timer`, 02:30 UTC) and **before every deploy**:
  `pg_dump --format=custom` in the pinned PostgreSQL image, written with a
  SHA-256 checksum to `/var/backups/agenthub` (root only, 0700), kept 14 days.
- **Weekly** (`agenthub-restore-check.timer`): the newest dump is checksummed,
  restored into a throwaway PostgreSQL container with no network, and checked
  (schema version, core tables, organizations and accounts present). A failure
  is an incident: see [OPERATIONS.md](OPERATIONS.md).
- **Off the host:** local backups do not survive losing the host. Set
  `AGENTHUB_BACKUP_UPLOAD` in `/etc/agenthub/backup.conf` to an executable that
  copies a dump elsewhere, encrypted (restic, or rclone to a bucket with
  server-side encryption). With a managed database, its own backups and
  point-in-time recovery are the primary copy and these are a second one.
- **Tested in CI:** the migrations job seeds a real PostgreSQL, runs these same
  two scripts, and requires the restored schema version to equal the newest
  migration.

Restoring for real is a decision, not a script: see "Restoring the database"
in [OPERATIONS.md](OPERATIONS.md).

## 5. TLS, headers and the edge

Caddy obtains and renews certificates automatically (HTTP-01 or TLS-ALPN-01).
It redirects all plain http to https, serves the SPA with long-lived caching
for hashed assets and `no-cache` for the shell, and sends HSTS (two years),
`frame-ancestors 'none'` and the other security headers on pages. The page's
own CSP comes from the build, and the API sets its own headers. Caddy's admin
API is off. It keeps no access log, because that would record every visitor's
IP address. It ignores incoming `X-Forwarded-*` headers and sets
`X-Forwarded-For` itself. The API trusts that header only from Caddy's fixed
address (`FORWARDED_ALLOW_IPS`), so the sign-in limiter sees real client
addresses, and a client cannot choose its own.

## 6. Verification

| Claim | How it is checked | Has it run? |
| --- | --- | --- |
| Backend and frontend behave | the test suites | Yes, locally (Python 3.14); 3.13 in CI only |
| The worker reports its capabilities; the API uses them | `test_runtime_workers.py` | Yes, locally |
| The worker's metrics endpoint enforces its token | `test_runtime_workers.py` | Yes, locally |
| The sandbox CLI never receives the worker's secrets | `test_sandbox_runner.py` | Yes, locally |
| Migration 0009 applies, matches the models, rolls back | alembic upgrade/check/downgrade | Yes, locally (SQLite); PostgreSQL in CI |
| Scripts are valid shell | `bash -n` locally; shellcheck in CI | Syntax only, locally |
| Compose, Caddyfile, Prometheus files are valid | YAML parse locally; `docker compose config`, `caddy validate`, `promtool` in CI | Parse only, locally |
| Images build, have no fixable HIGH/CRITICAL CVEs | CI `images` | No: not pushed |
| The stack starts hardened and meets load thresholds | CI `images` (compose + k6) | No: not pushed |
| Backups restore | CI `migrations` | No: not pushed |
| A host can be prepared; the rootless sandbox socket works across accounts | a real Debian 13 host | **No**: no host available |
| Deploy, automatic rollback and manual rollback work | a real staging host | **No** |

The two unexercised rows at the bottom are the ones most likely to need
fixing on first contact. The rootless daemon's socket location and
permissions across two accounts are the least certain. Do a first deploy on
staging with someone watching, and read [OPERATIONS.md](OPERATIONS.md) §1
first.
