#!/usr/bin/env bash
set -euo pipefail

# End-to-end smoke test for K8s scoring + log visibility.
# Automatically finds Envoy service, port-forwards, fires a scoring request,
# and verifies structured logs appear in kubectl output.
#
# Prerequisites: kind cluster deployed via setup_envoy_gateway_poc.sh
#
# Usage:
#   docker/scripts/smoke_test_k8s_logging.sh [--score SCORE_NAME]
#
# Flags:
#   --score NAME     Score to test (default: nira-resolution-quality-lua)
#                    Use "nira-resolution-quality" for the LLM-backed score.
#
# Environment overrides:
#   CLUSTER_NAME     kind cluster name (default: plexus-envoy-poc)
#   NAMESPACE        K8s namespace (default: plexus-local)
#   RELEASE_NAME     Helm release (default: plexus)
#   SCORING_API_KEY  Inbound API key (default: local-scoring-api-key)
#   SCORE_NAME       Same as --score flag

CLUSTER_NAME="${CLUSTER_NAME:-plexus-envoy-poc}"
NAMESPACE="${NAMESPACE:-plexus-local}"
RELEASE_NAME="${RELEASE_NAME:-plexus}"
SCORING_API_KEY="${SCORING_API_KEY:-local-scoring-api-key}"
LOCAL_PORT="${LOCAL_PORT:-18090}"
SCORING_JOB_ID="log-smoke-$(date +%s)"
SCORE_NAME="${SCORE_NAME:-nira-resolution-quality-lua}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --score) SCORE_NAME="${2:-}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

cleanup() {
  local pids="${PF_PID:-} ${LOG_PID:-}"
  for pid in $pids; do
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT

echo "=== K8s Logging Smoke Test ==="
echo ""

# Verify cluster context
if ! kubectl config use-context "kind-$CLUSTER_NAME" >/dev/null 2>&1; then
  echo "FAIL: kind cluster '$CLUSTER_NAME' not found. Run setup_envoy_gateway_poc.sh first." >&2
  exit 1
fi

# Verify worker is running
if ! kubectl get deployment/"$RELEASE_NAME-plexus-worker" -n "$NAMESPACE" >/dev/null 2>&1; then
  echo "FAIL: Worker deployment not found in $NAMESPACE." >&2
  exit 1
fi

echo "1. Finding Envoy data-plane service..."
ENVOY_SVC=""
for _ in {1..10}; do
  ENVOY_SVC="$(kubectl get svc -A \
    -l gateway.envoyproxy.io/owning-gateway-name="$RELEASE_NAME-plexus-worker-gateway" \
    -o jsonpath='{range .items[0]}{.metadata.namespace}{" "}{.metadata.name}{end}' 2>/dev/null || true)"
  if [ -n "$ENVOY_SVC" ]; then break; fi
  sleep 2
done

if [ -z "$ENVOY_SVC" ]; then
  echo "FAIL: Could not find Envoy data-plane service." >&2
  exit 1
fi

ENVOY_NS="$(echo "$ENVOY_SVC" | awk '{print $1}')"
ENVOY_NAME="$(echo "$ENVOY_SVC" | awk '{print $2}')"
echo "   Found: $ENVOY_NS/$ENVOY_NAME"

echo "2. Port-forwarding Envoy on localhost:$LOCAL_PORT..."
kubectl port-forward -n "$ENVOY_NS" "svc/$ENVOY_NAME" "$LOCAL_PORT:80" >/dev/null 2>&1 &
PF_PID=$!
sleep 3

if ! kill -0 "$PF_PID" 2>/dev/null; then
  echo "FAIL: Port-forward died. Is port $LOCAL_PORT in use?" >&2
  exit 1
fi

echo "3. Capturing worker logs in background..."
LOG_FILE="$(mktemp)"
kubectl logs -f -n "$NAMESPACE" "deployment/$RELEASE_NAME-plexus-worker" --since=5s > "$LOG_FILE" 2>&1 &
LOG_PID=$!
sleep 1

echo "4. Sending scoring request (job: $SCORING_JOB_ID, score: $SCORE_NAME)..."
HTTP_RESPONSE="$(curl -sS -w '\n%{http_code}' \
  --max-time 60 \
  -X POST "http://localhost:$LOCAL_PORT/v1/score" \
  -H 'content-type: application/json' \
  -H "x-plexus-scoring-api-key: $SCORING_API_KEY" \
  -d "{\"scoring_job_id\":\"$SCORING_JOB_ID\",\"scorecard\":\"nira-demo-scorecard\",\"score\":\"$SCORE_NAME\",\"item_id\":\"nira-demo-item-1\"}")"

HTTP_BODY="$(echo "$HTTP_RESPONSE" | sed '$d')"
HTTP_CODE="$(echo "$HTTP_RESPONSE" | tail -1)"

echo "   HTTP $HTTP_CODE"
echo "   Response: $HTTP_BODY"
echo ""

# Give logs a moment to flush
sleep 2

echo "5. Verifying log visibility..."
echo "--- Worker logs (last 30 lines) ---"
tail -30 "$LOG_FILE"
echo "--- End logs ---"
echo ""

# Check for expected log content
PASS=true

if ! grep -q "$SCORING_JOB_ID" "$LOG_FILE"; then
  echo "FAIL: Scoring job ID '$SCORING_JOB_ID' not found in logs." >&2
  PASS=false
fi

if ! grep -q "Processing scoring job" "$LOG_FILE"; then
  echo "FAIL: Expected 'Processing scoring job' log line not found." >&2
  PASS=false
fi

if [ "$HTTP_CODE" != "200" ]; then
  echo "FAIL: Expected HTTP 200, got $HTTP_CODE." >&2
  PASS=false
fi

rm -f "$LOG_FILE"

echo ""
if [ "$PASS" = true ]; then
  echo "=== PASS: Structured logs visible via kubectl, scoring succeeded ==="
else
  echo "=== FAIL: See errors above ==="
  exit 1
fi
