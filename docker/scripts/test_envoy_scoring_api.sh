#!/usr/bin/env bash
set -euo pipefail

ENVOY_URL="${ENVOY_URL:-http://localhost:8080}"
SCORING_JOB_ID="${SCORING_JOB_ID:-kind-envoy-score-$(date +%Y%m%d%H%M%S)}"
SCORING_API_KEY="${SCORING_API_KEY:-}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"

usage() {
  cat <<'EOF'
Usage:
  docker/scripts/test_envoy_scoring_api.sh --scorecard SCORECARD --score SCORE --item-id ITEM_ID

Environment:
  ENVOY_URL          Envoy listener URL. Default: http://localhost:8080
  SCORING_JOB_ID    Override generated scoring job ID.
  SCORING_API_KEY   Optional inbound scoring API key; sent as x-plexus-scoring-api-key.
  TIMEOUT_SECONDS   curl timeout. Default: 300

Example:
  SCORING_API_KEY=local-scoring-api-key \
  docker/scripts/test_envoy_scoring_api.sh \
    --scorecard demo-scorecard-id \
    --score ProblemResolution \
    --item-id demo-item-id
EOF
}

SCORECARD=""
SCORE=""
ITEM_ID=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --scorecard)
      SCORECARD="${2:-}"
      shift 2
      ;;
    --score)
      SCORE="${2:-}"
      shift 2
      ;;
    --item-id)
      ITEM_ID="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [ -z "$SCORECARD" ] || [ -z "$SCORE" ] || [ -z "$ITEM_ID" ]; then
  echo "--scorecard, --score, and --item-id are required." >&2
  usage >&2
  exit 1
fi

REQUEST_BODY="$(
  python3 - "$SCORING_JOB_ID" "$SCORECARD" "$SCORE" "$ITEM_ID" <<'PY'
import json
import sys

scoring_job_id, scorecard, score, item_id = sys.argv[1:]
print(json.dumps({
    "scoring_job_id": scoring_job_id,
    "scorecard": scorecard,
    "score": score,
    "item_id": item_id,
}))
PY
)"

HEADERS=(-H "content-type: application/json")
if [ -n "$SCORING_API_KEY" ]; then
  HEADERS+=(-H "x-plexus-scoring-api-key: $SCORING_API_KEY")
fi

echo "POST $ENVOY_URL/v1/score"
echo "Scoring job: $SCORING_JOB_ID"

curl --max-time "$TIMEOUT_SECONDS" -sS -w '\nHTTP_STATUS:%{http_code}\n' \
  -X POST "$ENVOY_URL/v1/score" \
  "${HEADERS[@]}" \
  -d "$REQUEST_BODY"
