#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/services/private-graphql-proxy/docker-compose.smoke.yml"

export PLEXUS_BACKEND_MODE="${PLEXUS_BACKEND_MODE:-local}"
export PLEXUS_PROXY_UPSTREAM_DISABLED="${PLEXUS_PROXY_UPSTREAM_DISABLED:-true}"
export PLEXUS_PROXY_API_KEY="${PLEXUS_PROXY_API_KEY:-local-smoke-key}"
export PLEXUS_PROXY_AUTH_MODE="${PLEXUS_PROXY_AUTH_MODE:-}"
export PLEXUS_API_URL="${PLEXUS_API_URL:-http://localhost:18080/graphql}"
export PLEXUS_API_KEY="${PLEXUS_API_KEY:-$PLEXUS_PROXY_API_KEY}"
export PLEXUS_ACCOUNT_KEY="${PLEXUS_ACCOUNT_KEY:-local-demo}"
export SMOKE_DASHBOARD_URL="${SMOKE_DASHBOARD_URL:-http://localhost:3000}"
export SMOKE_PROOF_DIR="${SMOKE_PROOF_DIR:-$ROOT_DIR/tmp/local-control-plane-proof}"
export SMOKE_PREDICTION_PROOF_FILE="${SMOKE_PREDICTION_PROOF_FILE:-$SMOKE_PROOF_DIR/prediction.json}"
export SMOKE_FEEDBACK_PROOF_FILE="${SMOKE_FEEDBACK_PROOF_FILE:-$SMOKE_PROOF_DIR/feedback-evaluation.json}"
export SMOKE_REPORT_PROOF_FILE="${SMOKE_REPORT_PROOF_FILE:-$SMOKE_PROOF_DIR/report.json}"
export SMOKE_VECTOR_TOPIC_MEMORY_PROOF_FILE="${SMOKE_VECTOR_TOPIC_MEMORY_PROOF_FILE:-$SMOKE_PROOF_DIR/vector-topic-memory.json}"
export AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME="${AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME:-plexus-local-report-block-details}"
export EMBEDDING_CACHE_BUCKET="${EMBEDDING_CACHE_BUCKET:-plexus-embeddings}"
export PLEXUS_OBJECT_STORE_ENDPOINT="${PLEXUS_OBJECT_STORE_ENDPOINT:-http://localhost:19000}"
export PLEXUS_OBJECT_STORE_REGION="${PLEXUS_OBJECT_STORE_REGION:-us-east-1}"
export PLEXUS_OBJECT_STORE_FORCE_PATH_STYLE="${PLEXUS_OBJECT_STORE_FORCE_PATH_STYLE:-true}"
export PLEXUS_OBJECT_STORE_ACCESS_KEY_ID="${PLEXUS_OBJECT_STORE_ACCESS_KEY_ID:-plexus-local}"
export PLEXUS_OBJECT_STORE_SECRET_ACCESS_KEY="${PLEXUS_OBJECT_STORE_SECRET_ACCESS_KEY:-plexus-local-secret}"
export PLEXUS_VECTOR_STORE_PROVIDER="${PLEXUS_VECTOR_STORE_PROVIDER:-qdrant}"
export PLEXUS_VECTOR_STORE_URL="${PLEXUS_VECTOR_STORE_URL:-http://localhost:19002}"
export PLEXUS_VECTOR_STORE_COLLECTION="${PLEXUS_VECTOR_STORE_COLLECTION:-topic-memory-local}"

SMOKE_RESET_STACK="${SMOKE_RESET_STACK:-1}"

log() {
  printf '[prove-local-control-plane] %s\n' "$*"
}

assert_local_mode() {
  if [[ "$PLEXUS_BACKEND_MODE" != "local" ]]; then
    log "PLEXUS_BACKEND_MODE must be local for this proof harness."
    exit 1
  fi
  if [[ "$PLEXUS_PROXY_UPSTREAM_DISABLED" != "true" ]]; then
    log "PLEXUS_PROXY_UPSTREAM_DISABLED must be true for this proof harness."
    exit 1
  fi
}

reset_smoke_stack() {
  if [[ "$SMOKE_RESET_STACK" != "1" ]]; then
    log "Skipping smoke stack reset because SMOKE_RESET_STACK=$SMOKE_RESET_STACK"
    return 0
  fi

  log "Resetting smoke compose stack and volumes."
  docker compose -f "$COMPOSE_FILE" down --volumes --remove-orphans
}

start_smoke_stack() {
  log "Starting local PostgreSQL, MinIO, Qdrant, and GraphQL proxy."
  docker compose -f "$COMPOSE_FILE" up -d --build postgres minio minio-init qdrant proxy
}

seed_demo_data() {
  log "Seeding deterministic local demo data."
  docker compose -f "$COMPOSE_FILE" run --rm \
    -e PLEXUS_API_URL=http://proxy:8000/graphql \
    -e PLEXUS_API_KEY="$PLEXUS_PROXY_API_KEY" \
    smoke-tests \
    sh -c "pip install --no-cache-dir -r services/private-graphql-proxy/requirements.txt >/dev/null && python services/private-graphql-proxy/scripts/seed_local_demo.py"
}

assert_no_upstream_requests() {
  local debug_url="${PLEXUS_API_URL%/graphql}/debug/upstream-requests"
  local payload

  payload="$(curl -fsS -m 10 "$debug_url")"
  python3 -c '
import json,sys
payload=json.loads(sys.argv[1])
if payload:
    raise SystemExit(f"expected no upstream proxy requests in local proof, found {len(payload)}")
' "$payload"
}

dashboard_is_reachable() {
  curl -fsS -m 5 "$SMOKE_DASHBOARD_URL/lab/items/nira-demo-item-1" >/dev/null 2>&1
}

ensure_vector_topic_memory_deps() {
  if poetry run python -c "import sentence_transformers" >/dev/null 2>&1; then
    return 0
  fi
  log "Installing sentence-transformers for VectorTopicMemory smoke."
  poetry run pip install --disable-pip-version-check sentence-transformers
}

main() {
  assert_local_mode
  ensure_vector_topic_memory_deps
  rm -rf "$SMOKE_PROOF_DIR"
  mkdir -p "$SMOKE_PROOF_DIR"

  reset_smoke_stack
  start_smoke_stack
  seed_demo_data

  log "Running strict CLI smoke."
  "$ROOT_DIR/scripts/smoke-local-cli.sh"

  log "Running exact prediction smoke."
  "$ROOT_DIR/scripts/smoke-local-predict.sh"

  log "Running feedback-evaluation smoke."
  "$ROOT_DIR/scripts/smoke-local-feedback-evaluation.sh"

  log "Running feedback-alignment report smoke."
  "$ROOT_DIR/scripts/smoke-local-report.sh"

  log "Running vector-topic-memory smoke."
  "$ROOT_DIR/scripts/smoke-local-vector-topic-memory.sh"

  log "Asserting proxy made no upstream requests."
  assert_no_upstream_requests

  if dashboard_is_reachable; then
    log "Dashboard is reachable; running browser smoke."
    "$ROOT_DIR/scripts/smoke-local-browser.sh"
  else
    log "Dashboard not reachable at $SMOKE_DASHBOARD_URL; skipping browser smoke."
  fi

  log "Local control-plane proof passed."
}

main "$@"
