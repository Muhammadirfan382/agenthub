# Operations

Running AgentHub day to day, and what to do when it goes wrong. Read with
[DEPLOYMENT.md](DEPLOYMENT.md) (how it is laid out) and
[MONITORING.md](MONITORING.md) (alerts and their runbooks).

None of these procedures has been rehearsed on a real host yet. Rehearse the
first deploy, a rollback, and a restore on staging before production depends
on them.

## 1. First deploy on a new host

1. Prepare the host ([DEPLOYMENT.md](DEPLOYMENT.md) §2).
2. Run the Deploy workflow by hand with `target: staging` and the id of a
   green CI run on `main`, and watch the host:

   ```bash
   sudo journalctl -fu agenthub-worker
   ```

3. When it finishes: `sudo /opt/agenthub/bin/agenthub-deploy status`, then
   create the first owner account on the host:

   ```bash
   cd /opt/agenthub/worker/current/backend
   sudo -u agenthub env SECRETS_DIR=/etc/agenthub/worker/secrets ENVIRONMENT=production \
     ../venv/bin/python -m scripts.create_user --email you@example.com \
     --name "Your Name" --organization "Your Organization" --role owner
   ```

4. Sign in. Check that Settings → Runtime shows the sandbox and providers as
   available (reported by the worker), then run **Check sandbox**.
5. Open Prometheus through a tunnel (`ssh -L 9090:127.0.0.1:9090 host`) and
   confirm both targets, `agenthub` and `agenthub-worker`, are up.

## 2. Routine work

| Task | How |
| --- | --- |
| Ship a change | Merge to `main`. CI publishes, staging deploys, and production waits for approval. |
| See what is running | `sudo /opt/agenthub/bin/agenthub-deploy status` and `/var/lib/agenthub/history.log` |
| Base image or dependency updates | Dependabot opens PRs (pip, npm, actions, Dockerfiles, compose). CI's Trivy scan fails a build that ships a fixable HIGH/CRITICAL vulnerability, so a weekly merge of those PRs is the patching cadence. |
| Host updates | `unattended-upgrades` for Debian security updates. Reboot in a quiet period: containers restart, and runs resume from their last step. |
| Rotate a secret | Replace the file under `/etc/agenthub/…/secrets/`, then redeploy the current release (Deploy workflow with the same CI run), which restarts everything. For `metrics_token`, change both copies. For the database password, change it in PostgreSQL first, then both `database_url` files. |
| Rotate the CD key | Generate a new key, add it to `authorized_keys` with the same `restrict,command=…` prefix, update the environment's `DEPLOY_SSH_KEY`, then remove the old line. |
| Update host scripts or compose files | Merge the change, then on each host `git pull` the reviewed checkout and re-run `setup-host.sh`. The pipeline cannot do this, on purpose. |
| Stop all agent work now | The kill switch (Settings → Runtime). It is organization-wide, recorded in the audit log, and only the owner can release it. |

## 3. Runbooks

### A deploy failed

The workflow is red. Read its log: the host script says which step failed.
If it says *"rolled back"*, production is on the previous release. Nothing is
urgent: find out why on staging.

- **Backup failed**: nothing was changed. Check disk space
  (`df -h /var/backups`) and database reachability.
- **Migration failed**: the schema is unchanged (transactional DDL), and the
  old release was restored. Reproduce against a copy of the database.
- **Health check or smoke test failed**: `docker compose … logs backend web`
  (use the `compose` invocation from `agenthub-deploy`), and
  `journalctl -u agenthub-worker` for the worker.

### A rollback failed too

The script said *"the rollback failed too"*. The site may be down.

1. `sudo /opt/agenthub/bin/agenthub-deploy status`. Which containers are
   unhealthy?
2. If the database is the problem, fix it first: nothing else can work.
3. Try the last release that is known good by hand:
   `sudo /opt/agenthub/bin/agenthub-deploy deploy --backend … --web … --sandbox …`
   with its digests from `history.log`.
4. If a migration in the failed release broke the old code (it violated the
   expand/contract rule), restore the database from the pre-deploy backup
   (below). This loses writes made since that backup.

### Restoring the database

A decision for the incident lead, because it discards data written since the
backup.

1. Engage the kill switch, and stop the worker:
   `sudo systemctl stop agenthub-worker`.
2. Pick the dump: `ls -l /var/backups/agenthub`. The one written before the
   bad deploy is timestamped just before it in `history.log`.
3. Check it restores: `sudo /opt/agenthub/bin/agenthub-restore-check <dump>`.
4. Managed database: prefer its point-in-time recovery to a new instance, then
   switch both `database_url` files to it. Bundled: stop the API
   (`… compose stop backend`), then restore into the live server with
   `pg_restore --clean --if-exists` using the tools image (the same way
   `agenthub-backup` connects), and start it again.
5. Deploy the release that matches the restored schema version.
6. Start the worker, check, and release the kill switch.

### The restore check failed

The backups cannot be trusted until this is fixed: treat it as a SEV-2.
Checksum mismatch: the file is damaged, so check the disk and the upload copy.
Restore error: run it by hand and read the output. A backup that restores
nothing is worse than none, so do not wait for next week's run.

### The worker is down

`AgentHubDown` for job `agenthub-worker`, or the status card shows the runtime
degraded or in outage.

1. `systemctl status agenthub-worker` and `journalctl -u agenthub-worker -n 200`.
2. A crash loop at start is usually configuration. The process says which
   setting it refused (`worker.env`, the secrets files).
3. The sandbox daemon: `runuser -u agenthub-sandbox -- env
   DOCKER_HOST=unix:///srv/agenthub-sandbox/run/docker.sock docker info`. If
   it is not answering, check `systemctl --user -M agenthub-sandbox@ status docker`.
4. Runs are durable: when a worker comes back, stalled runs are reclaimed from
   their last step.

### Certificates

Caddy renews automatically. If renewal fails, the web container's logs say why
(`… compose logs web`): usually DNS no longer pointing at the host, or port 80
blocked. Certificates live in the `caddy-data` volume. Do not delete it: it
would trigger fresh issuance and risk the CA's rate limits.

### Disk is filling up

Check in this order: `/var/backups/agenthub` (retention is
`AGENTHUB_BACKUP_KEEP_DAYS`), Docker (`docker system df`; old images from
previous releases are safe to prune after a successful deploy, except the
previous release's, which rollback needs), Prometheus data (15-day retention),
and the PostgreSQL volume.

## 4. Incident response

### Severity

| Level | Meaning | Response |
| --- | --- | --- |
| SEV-1 | Suspected compromise, data exposure, or production down | Immediately, around the clock |
| SEV-2 | A core function broken (runs failing, sign-in broken, backups untrustworthy) | Same working day |
| SEV-3 | Degraded or at risk (one alert rule firing, slow pages) | Next working day |

### Roles

One **incident lead** decides and keeps a timeline. It is not necessarily the
person fixing things. Others investigate and report to the lead. For SEV-1,
someone else handles communication.

### Steps

1. **Declare.** Name the lead, open a timeline (time, what was seen, what
   was done), and pick a severity.
2. **Contain before you investigate.** Engage the kill switch. If a
   credential may be exposed, rotate it now: provider keys at the provider,
   then the secret file, then redeploy. Suspend the installation of an agent
   that is misbehaving.
3. **Preserve evidence.** The audit log is append-only. Export the relevant
   range before changing anything (`GET /api/v1/audit`). Keep container logs
   (`docker compose logs`), the worker journal, `history.log` and the
   Prometheus data. Do not rebuild a host you suspect is compromised until its
   disk is imaged.
4. **Eradicate and recover.** Redeploy a known-good release. For a suspected
   host compromise, build a new host from the checkout, restore data, and
   rotate every secret, including the CD key and the registry token.
5. **Communicate.** Tell affected users what happened, what it means for them
   and what they should do, as soon as it is known. Personal data breaches may
   carry legal notification deadlines (72 hours under GDPR): involve whoever
   owns that decision on day one.
6. **Review.** Within a week, a blameless write-up: timeline, root cause, what
   detected it (or should have), and changes with owners. Security-relevant
   findings go into [THREAT_MODEL.md](THREAT_MODEL.md).

### Specific scenarios

- **A provider key leaked:** revoke it at the provider first (that is the only
  step that actually stops misuse), replace the worker's secret file, redeploy,
  and check provider usage for the exposure window.
- **An agent exfiltrated or tried to:** `egress_blocked` and `policy_denials`
  alerts, and `egress.*` and `policy.denied` in the audit log, show what it
  tried and what was refused. Suspend its installation, and review its manifest
  and what it fetched (runs record their tool calls). Only the egress
  allow-list could have let data out: check which domains it allowed.
- **A sandbox isolation check failed** (`sandbox_unverified`, critical): the
  run was refused, which is the system working. Do not turn the sandbox off.
  Find out what changed on the host (kernel, Docker version, rootless setup)
  with `POST /organization/sandbox/check`, which reports each guarantee.
- **The CD pipeline or GitHub account is compromised:** the pipeline can only
  deploy digests under the allowed prefix, but an attacker who can publish
  there can ship code. Remove the CD key from `authorized_keys` on every host,
  then investigate. Check provenance of the running digests with
  `gh attestation verify`.
