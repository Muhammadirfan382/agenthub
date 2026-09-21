#!/usr/bin/env bash
# Prepares a Debian 13 host to run AgentHub, from a reviewed checkout.
#
#   sudo infrastructure/deployment/host/setup-host.sh --image-prefix ghcr.io/OWNER/agenthub-
#
# Idempotent: re-run it after pulling a new checkout to update the host
# scripts, units and compose files. It is the only way those change on a host;
# the CD pipeline can only choose which image digests to deploy.
#
# It does NOT install Docker, write any secret, or open firewall ports. It
# checks what it needs, creates accounts, directories and units, configures
# the rootless sandbox daemon, and prints what is left for a person to do.
# See docs/DEPLOYMENT.md, "Preparing a host".

set -euo pipefail
umask 022

REPO=$(cd "$(dirname "$(readlink -f "$0")")/../../.." && pwd)
PREFIX=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --image-prefix) PREFIX="${2:-}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

say() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run as root"
[[ "$PREFIX" =~ ^[a-z0-9][a-z0-9._/-]*/agenthub-$ ]] ||
  die "--image-prefix must look like ghcr.io/OWNER/agenthub- (got '$PREFIX')"

# --- Prerequisites ------------------------------------------------------------
say "checking prerequisites"
if ! grep -q '^VERSION_ID="13"' /etc/os-release || ! grep -q '^ID=debian' /etc/os-release; then
  echo "warning: this was written for Debian 13; the worker's Python must be 3.13" >&2
fi
for command in docker python3 curl flock runuser sha256sum newuidmap newgidmap visudo loginctl; do
  command -v "$command" >/dev/null || die "missing: $command"
done
docker compose version >/dev/null 2>&1 || die "missing: the docker compose plugin"
command -v dockerd-rootless-setuptool.sh >/dev/null ||
  die "missing: dockerd-rootless-setuptool.sh (install docker-ce-rootless-extras)"
python3 -c 'import sys, venv; sys.exit(sys.version_info[:2] != (3, 13))' ||
  die "the worker needs Python 3.13 with venv (python3-venv), matching the backend image"

# --- Accounts -------------------------------------------------------------------
say "creating accounts"
# gid 10001 is the backend container's group: host files it must read (its
# secrets) are shared through it. It must not belong to anything else.
if getent group 10001 >/dev/null; then
  [[ "$(getent group 10001 | cut -d: -f1)" == agenthub-secrets ]] ||
    die "gid 10001 is taken by another group"
else
  groupadd --system --gid 10001 agenthub-secrets
fi
id agenthub >/dev/null 2>&1 ||
  useradd --system --user-group --home-dir /nonexistent --no-create-home \
    --shell /usr/sbin/nologin agenthub
# The rootless Docker daemon's owner. A container that escaped its sandbox
# would be this account: it holds no secrets and cannot read the worker's.
if ! id agenthub-sandbox >/dev/null 2>&1; then
  useradd --user-group --create-home --home-dir /home/agenthub-sandbox \
    --shell /usr/sbin/nologin agenthub-sandbox
fi
grep -q '^agenthub-sandbox:' /etc/subuid ||
  usermod --add-subuids 231072-296607 agenthub-sandbox
grep -q '^agenthub-sandbox:' /etc/subgid ||
  usermod --add-subgids 231072-296607 agenthub-sandbox
# The worker reaches the rootless daemon's socket through this group only.
usermod --append --groups agenthub-sandbox agenthub
# The CD pipeline's account: a forced command, no shell, not in the docker group.
id agenthub-deploy >/dev/null 2>&1 ||
  useradd --create-home --home-dir /home/agenthub-deploy --shell /bin/sh agenthub-deploy

# --- Directories ------------------------------------------------------------------
say "creating directories"
install -d -m 0755 -o root -g root /etc/agenthub /opt/agenthub /opt/agenthub/bin
install -d -m 0750 -o root -g agenthub-secrets /etc/agenthub/secrets
install -d -m 0750 -o root -g agenthub /etc/agenthub/worker /etc/agenthub/worker/secrets
install -d -m 0750 -o root -g agenthub /opt/agenthub/worker /opt/agenthub/worker/releases
install -d -m 0700 -o root -g root /var/lib/agenthub /var/backups/agenthub
install -d -m 0750 -o agenthub-sandbox -g agenthub-sandbox /srv/agenthub-sandbox /srv/agenthub-sandbox/run

# --- Files from this checkout ----------------------------------------------------
say "installing scripts, compose files, units and docs"
for script in lib.sh agenthub-deploy agenthub-backup agenthub-restore-check; do
  install -m 0755 -o root -g root "$REPO/infrastructure/deployment/bin/$script" /opt/agenthub/bin/
done
install -d -m 0755 /opt/agenthub/infrastructure/deployment /opt/agenthub/infrastructure/monitoring /opt/agenthub/docs
install -m 0644 "$REPO/infrastructure/deployment/compose.yml" \
  "$REPO/infrastructure/deployment/prometheus.yml" /opt/agenthub/infrastructure/deployment/
install -m 0644 "$REPO/infrastructure/monitoring/prometheus-rules.yml" /opt/agenthub/infrastructure/monitoring/
for doc in DEPLOYMENT.md OPERATIONS.md MONITORING.md; do
  install -m 0644 "$REPO/docs/$doc" /opt/agenthub/docs/
done
for unit in agenthub-worker.service agenthub-backup.service agenthub-backup.timer \
  agenthub-restore-check.service agenthub-restore-check.timer; do
  install -m 0644 "$REPO/infrastructure/deployment/systemd/$unit" /etc/systemd/system/
done

# Configuration: examples are copied once, never overwritten.
copy_once() {
  local source="$1" target="$2" mode="$3" group="$4"
  if [[ ! -e "$target" ]]; then
    install -m "$mode" -o root -g "$group" "$source" "$target"
    echo "    created $target (edit it)"
  fi
}
copy_once "$REPO/infrastructure/deployment/config/agenthub.env.example" /etc/agenthub/agenthub.env 0644 root
copy_once "$REPO/infrastructure/deployment/config/backend.env.example" /etc/agenthub/backend.env 0644 root
copy_once "$REPO/infrastructure/deployment/config/worker.env.example" /etc/agenthub/worker.env 0640 agenthub
printf 'ALLOWED_IMAGE_PREFIX=%s\n' "$PREFIX" >/etc/agenthub/deploy.conf
chmod 0644 /etc/agenthub/deploy.conf

# --- The CD account may run the deploy script, and nothing else --------------------
say "restricting the CD account to the deploy script"
sudoers=$(mktemp)
cat >"$sudoers" <<'SUDOERS'
# AgentHub CD: the forced SSH command runs the deploy script as root, and only it.
Defaults!/opt/agenthub/bin/agenthub-deploy env_keep += "SSH_ORIGINAL_COMMAND"
agenthub-deploy ALL=(root) NOPASSWD: /opt/agenthub/bin/agenthub-deploy --ssh
SUDOERS
visudo -cf "$sudoers" >/dev/null || die "generated sudoers did not validate"
install -m 0440 -o root -g root "$sudoers" /etc/sudoers.d/agenthub-deploy
rm -f "$sudoers"

# --- Rootless Docker for the sandbox -----------------------------------------------
say "configuring the rootless sandbox daemon"
sandbox_uid=$(id -u agenthub-sandbox)
loginctl enable-linger agenthub-sandbox
for _ in $(seq 1 20); do
  [[ -S "/run/user/$sandbox_uid/bus" ]] && break
  sleep 0.5
done
install -d -m 0700 -o agenthub-sandbox -g agenthub-sandbox \
  /home/agenthub-sandbox/.config /home/agenthub-sandbox/.config/docker
cat >/home/agenthub-sandbox/.config/docker/daemon.json <<'JSON'
{
  "hosts": ["unix:///srv/agenthub-sandbox/run/docker.sock"],
  "no-new-privileges": true,
  "icc": false,
  "log-driver": "json-file",
  "log-opts": { "max-size": "1m", "max-file": "2" }
}
JSON
chown agenthub-sandbox:agenthub-sandbox /home/agenthub-sandbox/.config/docker/daemon.json
chmod 0600 /home/agenthub-sandbox/.config/docker/daemon.json
as_sandbox() {
  runuser -u agenthub-sandbox -- env \
    XDG_RUNTIME_DIR="/run/user/$sandbox_uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$sandbox_uid/bus" \
    DOCKER_HOST="unix:///srv/agenthub-sandbox/run/docker.sock" \
    "$@"
}
if [[ ! -e /home/agenthub-sandbox/.config/systemd/user/docker.service ]]; then
  as_sandbox dockerd-rootless-setuptool.sh install --skip-iptables
fi
as_sandbox systemctl --user daemon-reload
as_sandbox systemctl --user enable --now docker.service
as_sandbox systemctl --user restart docker.service
for _ in $(seq 1 30); do
  as_sandbox docker version --format '{{.Server.Version}}' >/dev/null 2>&1 && break
  sleep 1
done
as_sandbox docker info --format '{{.SecurityOptions}}' | grep -q rootless ||
  die "the sandbox daemon is not answering in rootless mode"

# --- Units ------------------------------------------------------------------------
systemctl daemon-reload
systemctl enable --now agenthub-backup.timer agenthub-restore-check.timer
# Started by the first deploy, once there is a worker release to run.
systemctl enable agenthub-worker.service

cat <<NEXT

Host prepared. Still to do by hand (docs/DEPLOYMENT.md, "Preparing a host"):

  1. Edit /etc/agenthub/agenthub.env, backend.env and worker.env.
  2. Create the secrets (one value per file, no trailing newline needed):
       /etc/agenthub/secrets/database_url          root:agenthub-secrets 0640
       /etc/agenthub/secrets/metrics_token         root:agenthub-secrets 0640
       /etc/agenthub/secrets/postgres_password     root:agenthub-secrets 0640 (bundled-db)
       /etc/agenthub/worker/secrets/database_url   root:agenthub 0640
       /etc/agenthub/worker/secrets/metrics_token  root:agenthub 0640 (same value)
       /etc/agenthub/worker/secrets/AGENTHUB_ANTHROPIC_API_KEY  root:agenthub 0640 (optional)
     e.g. a token:  openssl rand -base64 48 | tr -d '\\n' > FILE
  3. Let both daemons pull from the registry (read-only token):
       docker login ghcr.io
       runuser -u agenthub-sandbox -- env DOCKER_HOST=unix:///srv/agenthub-sandbox/run/docker.sock docker login ghcr.io
  4. Add the CD public key to /home/agenthub-deploy/.ssh/authorized_keys as:
       restrict,command="sudo -n /opt/agenthub/bin/agenthub-deploy --ssh" ssh-ed25519 AAAA... agenthub-cd
  5. Allow only 22, 80 and 443 inbound at the firewall.
NEXT
