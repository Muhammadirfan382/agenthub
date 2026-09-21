#!/usr/bin/env bash
# Smoke test of the CI compose stack, through the edge (Caddy).
#
#   .github/scripts/smoke_test.sh [base-url] [prometheus-url]
#
# Runs every check even when one fails, and reports each failure as an error
# annotation carrying what was actually received, so a red run says why.
set -uo pipefail

BASE="${1:-http://localhost:8080}"
PROMETHEUS="${2:-http://localhost:9090}"
failed=0
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# One line, annotation-safe: newlines become " | ", percent signs encoded.
flatten() { tr -d '\r' | tr '\n' '|' | sed 's/|/ | /g; s/%/%25/g' | cut -c1-900; }

report() {
  local name="$1" detail="$2"
  echo "::error title=Smoke test - ${name}::${detail}"
  echo "FAILED: $name"
  failed=1
}

# fetch URL -> sets CODE and writes the body to $work/body, headers to $work/headers
fetch() {
  : >"$work/headers" >"$work/body"
  CODE=$(curl -s -D "$work/headers" -o "$work/body" -w '%{http_code}' --max-time 10 "$1")
  [ -n "$CODE" ] || CODE=000
}

fetch "$BASE/api/v1/health/ready"
if [ "$CODE" = 200 ]; then echo "ok: readiness"; else
  report "readiness" "HTTP $CODE: $(flatten <"$work/body")"; fi

fetch "$BASE/"
if [ "$CODE" = 200 ] && grep -q '<div id="root">' "$work/body"; then echo "ok: app shell"; else
  report "app shell" "HTTP $CODE: $(head -c 400 "$work/body" | flatten)"; fi

fetch "$BASE/agents/does-not-exist"
if [ "$CODE" = 200 ] && grep -q '<div id="root">' "$work/body"; then echo "ok: client route"; else
  report "client route" "HTTP $CODE: $(head -c 400 "$work/body" | flatten)"; fi

# The page may not be framed (CSP frame-ancestors, sent as a header).
fetch "$BASE/"
if tr -d '\r' <"$work/headers" | grep -qi "^content-security-policy: frame-ancestors 'none'"; then
  echo "ok: framing refused"
else
  report "framing header" "headers: $(flatten <"$work/headers")"
fi

# Metrics are internal only.
fetch "$BASE/api/v1/metrics"
if [ "$CODE" = 404 ]; then echo "ok: metrics not public"; else
  report "metrics exposed" "HTTP $CODE from /api/v1/metrics through the edge"; fi

# Prometheus scrapes the API with the bearer token.
scraped=0
for _ in $(seq 1 20); do
  if curl -s --max-time 10 "$PROMETHEUS/api/v1/targets?state=active" >"$work/targets" &&
    jq -e '.data.activeTargets[] | select(.labels.job == "agenthub" and .health == "up")' \
      "$work/targets" >/dev/null 2>&1; then
    scraped=1
    break
  fi
  sleep 3
done
if [ "$scraped" = 1 ]; then echo "ok: prometheus scrapes the API"; else
  detail=$(jq -r '.data.activeTargets[]? | "\(.labels.job) \(.health) \(.lastError)"' \
    "$work/targets" 2>/dev/null | flatten)
  report "prometheus" "targets: ${detail:-$(head -c 400 "$work/targets" 2>/dev/null | flatten)}"
fi

exit "$failed"
