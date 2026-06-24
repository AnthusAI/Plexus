#!/usr/bin/env bash
set -euo pipefail

export PLEXUS_API_URL="${PLEXUS_API_URL:-http://localhost:18080/graphql}"

log() {
  printf '[smoke-local-trusted-open] %s\n' "$*"
}

ready_url="${PLEXUS_API_URL%/graphql}/readyz"
debug_url="${PLEXUS_API_URL%/graphql}/debug/upstream-requests"

ready_body="$(curl -fsS -m 10 "$ready_url")"
python3 - "$ready_body" <<'PY'
import json
import sys

body = json.loads(sys.argv[1])
if body.get("status") != "ready":
    raise SystemExit("proxy is not ready")
if body.get("authMode") != "trusted_open":
    raise SystemExit(f"expected authMode=trusted_open, got {body.get('authMode')!r}")
if body.get("externalAccessControlRequired") is not True:
    raise SystemExit("trusted_open readyz must require external access control")
if body.get("upstreamDisabled") is not True:
    raise SystemExit("trusted_open requires upstreamDisabled=true")
if body.get("backendMode") != "local":
    raise SystemExit("trusted_open requires backendMode=local")
PY

log "readyz reports explicit trusted-open local mode."

query='query TrustedOpenSeedCheck { getAccount(id:"local-demo-account") { id key } listItems(limit: 1) { items { id accountId } nextToken } }'
payload="$(curl -fsS -m 10 "$PLEXUS_API_URL" \
  -H 'content-type: application/json' \
  --data "$(python3 -c 'import json,sys; print(json.dumps({"query":sys.argv[1]}))' "$query")")"

python3 - "$payload" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
if payload.get("errors"):
    raise SystemExit(payload["errors"])
data = payload.get("data") or {}
account = data.get("getAccount") or {}
items = ((data.get("listItems") or {}).get("items") or [])
if account.get("key") != "local-demo":
    raise SystemExit("local demo account was not readable without an API key")
if not items:
    raise SystemExit("local items were not readable without an API key")
PY

log "GraphQL read without x-api-key succeeded by design."

upstream_payload="$(curl -fsS -m 10 "$debug_url")"
python3 - "$upstream_payload" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
if payload:
    raise SystemExit(f"expected no upstream requests, found {len(payload)}")
PY

log "No hosted upstream requests recorded."
log "Trusted-open smoke passed."
