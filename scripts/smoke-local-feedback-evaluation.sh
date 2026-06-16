#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PLEXUS_API_URL="${PLEXUS_API_URL:-http://localhost:18080/graphql}"
export PLEXUS_API_KEY="${PLEXUS_API_KEY:-local-smoke-key}"
export PLEXUS_ACCOUNT_KEY="${PLEXUS_ACCOUNT_KEY:-local-demo}"
export SMOKE_PROOF_DIR="${SMOKE_PROOF_DIR:-$ROOT_DIR/tmp/local-control-plane-proof}"
export SMOKE_FEEDBACK_PROOF_FILE="${SMOKE_FEEDBACK_PROOF_FILE:-$SMOKE_PROOF_DIR/feedback-evaluation.json}"
export SMOKE_FEEDBACK_MAX_ITEMS="${SMOKE_FEEDBACK_MAX_ITEMS:-200}"
export SMOKE_FEEDBACK_DAYS="${SMOKE_FEEDBACK_DAYS:-30}"
export SMOKE_FEEDBACK_SCORECARD="${SMOKE_FEEDBACK_SCORECARD:-nira-call-center-qa}"
export SMOKE_FEEDBACK_SCORE="${SMOKE_FEEDBACK_SCORE:-nira-resolution-quality}"
export SMOKE_FEEDBACK_SCORE_VERSION="${SMOKE_FEEDBACK_SCORE_VERSION:-nira-demo-score-version}"
SMOKE_ASSERT_NO_UPSTREAM="${SMOKE_ASSERT_NO_UPSTREAM:-1}"
SMOKE_READY_ATTEMPTS="${SMOKE_READY_ATTEMPTS:-60}"
SMOKE_READY_SLEEP_SECONDS="${SMOKE_READY_SLEEP_SECONDS:-2}"

failures=0
passes=0

log() {
  printf '[smoke-local-feedback-evaluation] %s\n' "$*"
}

run_step() {
  local name="$1"
  shift
  log "STEP: $name"
  if "$@"; then
    log "PASS: $name"
    passes=$((passes + 1))
  else
    log "FAIL: $name"
    failures=$((failures + 1))
  fi
}

wait_for_readyz() {
  local ready_url="${PLEXUS_API_URL%/graphql}/readyz"
  local i

  for ((i = 1; i <= SMOKE_READY_ATTEMPTS; i++)); do
    local body
    body="$(curl -fsS -m 3 "$ready_url" 2>/dev/null || true)"
    if [[ -n "$body" ]]; then
      local compact
      compact="$(printf '%s' "$body" | tr -d '[:space:]')"
      if [[ "$compact" == *'"status":"ready"'* ]]; then
        return 0
      fi
    fi
    sleep "$SMOKE_READY_SLEEP_SECONDS"
  done
  return 1
}

assert_feedback_fixture_dataset() {
  local query
  query='query FeedbackFixtureCheck($accountId: String!, $scoreId: String!, $scorecardId: String!, $start: String!, $end: String!) {
    items: listItemByScoreIdAndUpdatedAt(scoreId: $scoreId, sortDirection: DESC, limit: 500) {
      items { id scoreId }
      nextToken
    }
    feedback: listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt(
      accountId: $accountId
      scorecardIdScoreIdEditedAt: {
        between: [
          { scorecardId: $scorecardId, scoreId: $scoreId, editedAt: $start }
          { scorecardId: $scorecardId, scoreId: $scoreId, editedAt: $end }
        ]
      }
      sortDirection: DESC
      limit: 500
    ) {
      items { id itemId finalAnswerValue editedAt }
      nextToken
    }
  }'

  local variables
  variables='{"accountId":"local-demo-account","scoreId":"nira-demo-score","scorecardId":"nira-demo-scorecard","start":"1970-01-01T00:00:00Z","end":"2999-01-01T00:00:00Z"}'

  local body
  body="$(
    SMOKE_GQL_QUERY="$query" \
    SMOKE_GQL_VARIABLES="$variables" \
    python3 - <<'PY'
import json
import os

print(
    json.dumps(
        {
            "query": os.environ["SMOKE_GQL_QUERY"],
            "variables": json.loads(os.environ["SMOKE_GQL_VARIABLES"]),
        }
    )
)
PY
  )"

  local payload
  payload="$(curl -fsS -m 15 "$PLEXUS_API_URL" \
    -H 'content-type: application/json' \
    -H "x-api-key: $PLEXUS_API_KEY" \
    --data "$body" 2>/dev/null || true)"

  [[ -n "$payload" ]] || return 1

  python3 -c '
import json, os, sys
payload=json.loads(sys.argv[1])
if payload.get("errors"):
    raise SystemExit(1)
data=payload.get("data") or {}
items=(data.get("items") or {}).get("items") or []
feedback=(data.get("feedback") or {}).get("items") or []
required=int(os.environ["SMOKE_FEEDBACK_MAX_ITEMS"])
if len(items) < required:
    raise SystemExit(1)
if len(feedback) < required:
    raise SystemExit(1)
yes=sum(1 for row in feedback if (row.get("finalAnswerValue") or "").strip()=="Yes")
no=sum(1 for row in feedback if (row.get("finalAnswerValue") or "").strip()=="No")
if yes < required // 2 or no < required // 2:
    raise SystemExit(1)
' "$payload"
}

ensure_feedback_dependencies() {
  (
    cd "$ROOT_DIR"
    poetry run python - <<'PY'
import importlib
import subprocess
import sys

package_map = {
    "dotenv": "python-dotenv",
    "sklearn": "scikit-learn",
}
installed = set()

subprocess.run([sys.executable, "-m", "pip", "install", "griffe==1.15.0"], check=True)

for _ in range(24):
    try:
        importlib.import_module("plexus.cli.evaluation.evaluations")
        break
    except ModuleNotFoundError as exc:
        module_name = (exc.name or "").split(".")[0]
        if not module_name:
            raise
        package_name = package_map.get(module_name, module_name)
        if package_name in installed:
            raise
        subprocess.run([sys.executable, "-m", "pip", "install", package_name], check=True)
        installed.add(package_name)
else:
    raise SystemExit("could not resolve CLI feedback-evaluation dependencies after multiple install attempts")
PY
  )
}

run_feedback_evaluation_and_verify() {
  mkdir -p "$(dirname "$SMOKE_FEEDBACK_PROOF_FILE")"
  (
    cd "$ROOT_DIR"
    poetry run python - <<'PY'
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
from contextlib import redirect_stdout

import requests

from plexus.cli.evaluation.evaluations import evaluate

api_url = os.environ["PLEXUS_API_URL"]
api_key = os.environ["PLEXUS_API_KEY"]
account_key = os.environ["PLEXUS_ACCOUNT_KEY"]
scorecard = os.environ["SMOKE_FEEDBACK_SCORECARD"]
score = os.environ["SMOKE_FEEDBACK_SCORE"]
score_version_id = os.environ["SMOKE_FEEDBACK_SCORE_VERSION"]
max_items = int(os.environ["SMOKE_FEEDBACK_MAX_ITEMS"])
days = int(os.environ["SMOKE_FEEDBACK_DAYS"])
proof_file = Path(os.environ["SMOKE_FEEDBACK_PROOF_FILE"])
evaluation_id_file = proof_file.with_suffix(".id")

if evaluation_id_file.exists():
    evaluation_id_file.unlink()

evaluation_stdout = io.StringIO()
try:
    with redirect_stdout(evaluation_stdout):
        evaluate.main(
            args=[
                "feedback",
                "--scorecard",
                scorecard,
                "--score",
                score,
                "--version",
                score_version_id,
                "--days",
                str(days),
                "--max-items",
                str(max_items),
                "--sampling-mode",
                "newest",
                "--emit-id-file",
                str(evaluation_id_file),
            ],
            prog_name="evaluate",
            standalone_mode=False,
        )
except Exception as exc:
    raise SystemExit(
        "plexus evaluate feedback failed\n"
        f"error: {exc}\n"
        f"stdout:\n{evaluation_stdout.getvalue()}"
    ) from exc

if not evaluation_id_file.exists():
    raise SystemExit(
        "feedback evaluation did not emit evaluation id file\n"
        f"stdout:\n{evaluation_stdout.getvalue()}"
    )

evaluation_id = evaluation_id_file.read_text().strip()
if not evaluation_id:
    raise SystemExit("feedback evaluation emitted an empty evaluation id")

headers = {"x-api-key": api_key, "content-type": "application/json"}
query = """
query VerifyFeedbackEvaluation($evaluationId: ID!, $accountKey: String!) {
  account: listAccountByKey(key: $accountKey) {
    items { id key }
  }
  score: getScore(id: "nira-demo-score") {
    id
    championVersionId
  }
  evaluation: getEvaluation(id: $evaluationId) {
    id
    accountId
    scorecardId
    scoreId
    scoreVersionId
    type
    status
    totalItems
    processedItems
    createdAt
    updatedAt
    taskId
  }
  scoreResults: listScoreResultByEvaluationId(evaluationId: $evaluationId, limit: 300) {
    items {
      id
      evaluationId
      itemId
      scorecardId
      scoreId
      scoreVersionId
      type
      status
    }
    nextToken
  }
}
"""
variables = {"evaluationId": evaluation_id, "accountKey": account_key}
payload = requests.post(
    api_url,
    json={"query": query, "variables": variables},
    headers=headers,
    timeout=60,
)
payload.raise_for_status()
body = payload.json()
if body.get("errors"):
    raise SystemExit(f"verification query returned errors: {body['errors']}")
data = body.get("data") or {}

account_items = (data.get("account") or {}).get("items") or []
if not account_items:
    raise SystemExit(f"could not resolve account by key {account_key}")
account_id = account_items[0]["id"]

score_data = data.get("score") or {}
if score_data.get("championVersionId") != score_version_id:
    raise SystemExit("unexpected championVersionId for nira-demo-score")

evaluation = data.get("evaluation") or {}
if not evaluation:
    raise SystemExit(f"evaluation {evaluation_id} not found")
if evaluation.get("accountId") != account_id:
    raise SystemExit("evaluation accountId mismatch")
if evaluation.get("scorecardId") != "nira-demo-scorecard":
    raise SystemExit("evaluation scorecardId mismatch")
if evaluation.get("scoreId") != "nira-demo-score":
    raise SystemExit("evaluation scoreId mismatch")
if evaluation.get("scoreVersionId") != score_version_id:
    raise SystemExit("evaluation scoreVersionId mismatch")
if evaluation.get("type") != "feedback":
    raise SystemExit("evaluation type mismatch")
if evaluation.get("status") != "COMPLETED":
    raise SystemExit(f"evaluation status mismatch: {evaluation.get('status')}")

total_items = int(evaluation.get("totalItems") or 0)
processed_items = int(evaluation.get("processedItems") or 0)
if total_items < max_items:
    raise SystemExit(f"evaluation totalItems too small: {total_items} < {max_items}")
if processed_items < max_items:
    raise SystemExit(f"evaluation processedItems too small: {processed_items} < {max_items}")

score_results = (data.get("scoreResults") or {}).get("items") or []
if len(score_results) < max_items:
    raise SystemExit(f"expected at least {max_items} score results for evaluation, got {len(score_results)}")
for row in score_results:
    if row.get("evaluationId") != evaluation_id:
        raise SystemExit("score result evaluation linkage mismatch")
    if row.get("scorecardId") != "nira-demo-scorecard":
        raise SystemExit("score result scorecard linkage mismatch")
    if row.get("scoreId") != "nira-demo-score":
        raise SystemExit("score result score linkage mismatch")
    if row.get("status") != "COMPLETED":
        raise SystemExit("score result status mismatch")

score_version_values = {row.get("scoreVersionId") for row in score_results}
allowed_score_version_values = {None, score_version_id}
if not score_version_values.issubset(allowed_score_version_values):
    raise SystemExit(
        "score result scoreVersionId values were outside expected set: "
        f"{sorted(str(value) for value in score_version_values)}"
    )

proof = {
    "evaluationId": evaluation_id,
    "accountId": account_id,
    "accountKey": account_key,
    "scorecardId": "nira-demo-scorecard",
    "scoreId": "nira-demo-score",
    "scoreVersionId": score_version_id,
    "type": "feedback",
    "status": "COMPLETED",
    "totalItems": total_items,
    "processedItems": processed_items,
    "scoreResultCount": len(score_results),
    "scoreResultScoreVersionIds": sorted(
        str(value) if value is not None else "null"
        for value in score_version_values
    ),
    "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
proof_file.parent.mkdir(parents=True, exist_ok=True)
proof_file.write_text(json.dumps(proof, indent=2, sort_keys=True))
print(f"Feedback evaluation smoke passed with evaluation_id={evaluation_id}")
print(f"Feedback evaluation proof written to {proof_file}")
PY
  )
}

assert_no_upstream_requests() {
  if [[ "$SMOKE_ASSERT_NO_UPSTREAM" != "1" ]]; then
    return 0
  fi

  local debug_url="${PLEXUS_API_URL%/graphql}/debug/upstream-requests"
  local payload
  payload="$(curl -fsS -m 10 "$debug_url")"
  python3 -c '
import json,sys
payload=json.loads(sys.argv[1])
if payload:
    raise SystemExit(f"expected no upstream proxy requests in local feedback smoke, found {len(payload)}")
' "$payload"
}

main() {
  run_step "Proxy readyz is healthy" wait_for_readyz
  run_step "Nira feedback fixture dataset has at least 200 labeled records" assert_feedback_fixture_dataset
  run_step "Feedback evaluation CLI dependencies are available" ensure_feedback_dependencies
  run_step "CLI feedback evaluation persists evaluation and score results locally" run_feedback_evaluation_and_verify
  run_step "Proxy made no upstream requests" assert_no_upstream_requests

  log "Smoke summary: pass=$passes fail=$failures"
  if [[ "$failures" -gt 0 ]]; then
    exit 1
  fi
}

main "$@"
