#!/usr/bin/env bash
# Shared helpers for the AgentHub host scripts. Sourced, never run.

set -euo pipefail
umask 077

AGENTHUB_HOME="${AGENTHUB_HOME:-/opt/agenthub}"
AGENTHUB_CONFIG_DIR="${AGENTHUB_CONFIG_DIR:-/etc/agenthub}"
AGENTHUB_STATE_DIR="${AGENTHUB_STATE_DIR:-/var/lib/agenthub}"
COMPOSE_FILE="${COMPOSE_FILE:-$AGENTHUB_HOME/infrastructure/deployment/compose.yml}"
# The compose project's outbound network (compose.yml: `outbound`).
AGENTHUB_DB_NETWORK="${AGENTHUB_DB_NETWORK:-agenthub_outbound}"
POSTGRES_TOOLS_IMAGE="${POSTGRES_TOOLS_IMAGE:-postgres:17.11-alpine@sha256:f02121de6f74d30d8a94cd1d9584125e2178d7e6c377d8130112d4e52d867995}"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }
die() { log "error: $*"; exit 1; }

# An image reference is accepted only by digest, under the allowed prefix.
# Nothing else from the caller is ever used as a command or a path.
validate_image() {
  local ref="$1" prefix="$2"
  [[ "$ref" =~ ^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || die "not a digest reference: $ref"
  [[ "$ref" == "$prefix"* ]] || die "image is not under the allowed prefix $prefix: $ref"
}

# Compose takes interpolation variables from --env-file but not its own
# settings: COMPOSE_PROFILES there is ignored, so the bundled database would
# never start. It is read from agenthub.env and passed in the environment.
compose() {
  local profiles
  profiles=$(sed -n 's/^COMPOSE_PROFILES=//p' "$AGENTHUB_CONFIG_DIR/agenthub.env" | tail -n 1)
  COMPOSE_PROFILES="$profiles" docker compose \
    --project-name agenthub \
    --file "$COMPOSE_FILE" \
    --env-file "$AGENTHUB_STATE_DIR/release.env" \
    --env-file "$AGENTHUB_CONFIG_DIR/agenthub.env" \
    "$@"
}

# Writes libpq variables for the database URL in file $1 to file $2, so a
# password never appears in a command line or process listing.
write_pg_env() {
  local url_file="$1" out="$2"
  [[ -r "$url_file" ]] || die "cannot read $url_file"
  python3 - "$url_file" "$out" <<'PY'
import sys
from urllib.parse import unquote, urlsplit

url = open(sys.argv[1], encoding="utf-8").read().strip()
parts = urlsplit(url)
if not parts.scheme.startswith("postgresql"):
    sys.exit("database_url is not a PostgreSQL URL")
values = {
    "PGHOST": parts.hostname or "",
    "PGPORT": str(parts.port or 5432),
    "PGUSER": unquote(parts.username or ""),
    "PGPASSWORD": unquote(parts.password or ""),
    "PGDATABASE": parts.path.lstrip("/"),
}
for name, value in values.items():
    if "\n" in value:
        sys.exit(f"{name} contains a newline")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    for name, value in values.items():
        handle.write(f"{name}={value}\n")
PY
}
