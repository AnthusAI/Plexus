#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PLEXUS_API_URL="${PLEXUS_API_URL:-http://localhost:18080/graphql}"
export PLEXUS_API_KEY="${PLEXUS_API_KEY:-local-smoke-key}"
export PLEXUS_ACCOUNT_KEY="${PLEXUS_ACCOUNT_KEY:-local-demo}"
SMOKE_READY_ATTEMPTS="${SMOKE_READY_ATTEMPTS:-60}"
SMOKE_READY_SLEEP_SECONDS="${SMOKE_READY_SLEEP_SECONDS:-2}"

failures=0
passes=0

log() {
  printf '[smoke-local-predict] %s\n' "$*"
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

assert_nira_seed_and_champion_path() {
  local query
  query='query NiraSeed {
    account:getAccount(id:"local-demo-account"){id key}
    scorecard:getScorecard(id:"nira-demo-scorecard"){id key accountId}
    score:getScore(id:"nira-demo-score"){id key championVersionId}
    version:getScoreVersion(id:"nira-demo-score-version"){id scoreId configuration}
    item:getItem(id:"nira-demo-item-1"){id accountId scoreId externalId}
    identifier:getIdentifier(itemId:"nira-demo-item-1",name:"External ID"){itemId name value}
  }'

  local payload
  payload="$(curl -fsS -m 10 "$PLEXUS_API_URL" \
    -H 'content-type: application/json' \
    -H "x-api-key: $PLEXUS_API_KEY" \
    --data "$(python3 -c 'import json,sys; print(json.dumps({"query":sys.argv[1]}))' "$query")" 2>/dev/null || true)"

  [[ -n "$payload" ]] || return 1

  python3 -c '
import json,sys
payload=json.loads(sys.argv[1])
if payload.get("errors"):
    raise SystemExit(1)
data=payload.get("data") or {}
required=["account","scorecard","score","version","item","identifier"]
missing=[k for k in required if not data.get(k)]
if missing:
    raise SystemExit(1)
if data["account"].get("key")!="local-demo":
    raise SystemExit(1)
if data["score"].get("championVersionId")!="nira-demo-score-version":
    raise SystemExit(1)
if data["version"].get("scoreId")!="nira-demo-score":
    raise SystemExit(1)
configuration=data["version"].get("configuration") or ""
if "class: TactusScore" not in configuration:
    raise SystemExit(1)
if data["item"].get("scoreId")!="nira-demo-score":
    raise SystemExit(1)
if data["identifier"].get("value")!="nira-demo-external-1":
    raise SystemExit(1)
' "$payload"
}

ensure_predict_dependencies() {
  (
    cd "$ROOT_DIR"
    poetry run python - <<'PY'
import importlib
import subprocess
import sys

package_map = {
    "sklearn": "scikit-learn",
}
installed = set()

subprocess.run([sys.executable, "-m", "pip", "install", "griffe==1.15.0"], check=True)

for _ in range(12):
    try:
        importlib.import_module("plexus.cli.prediction.predictions")
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
    raise SystemExit("could not resolve CLI predict dependencies after multiple install attempts")

PY
  )
}

run_predict_and_verify_score_result() {
  (
    cd "$ROOT_DIR"
    poetry run python - <<'PY'
import json
import os
import io
from contextlib import redirect_stdout

import requests

api_url = os.environ["PLEXUS_API_URL"]
api_key = os.environ["PLEXUS_API_KEY"]
account_key = os.environ["PLEXUS_ACCOUNT_KEY"]
from plexus.cli.prediction.predictions import predict

predict_output = io.StringIO()
try:
    with redirect_stdout(predict_output):
        predict.main(
            args=[
                "--scorecard",
                "nira-call-center-qa",
                "--score",
                "nira-resolution-quality",
                "--item",
                "nira-demo-item-1",
                "--no-cache",
                "--format",
                "json",
            ],
            prog_name="predict",
            standalone_mode=False,
        )
except Exception as exc:
    raise SystemExit(
        "plexus predict failed\n"
        f"error: {exc}\n"
        f"stdout:\n{predict_output.getvalue()}"
    ) from exc

decoder = json.JSONDecoder()
predictions = None
raw_output = predict_output.getvalue()
for index, char in enumerate(raw_output):
    if char != "[":
        continue
    try:
        parsed, end = decoder.raw_decode(raw_output[index:])
    except json.JSONDecodeError:
        continue
    if isinstance(parsed, list) and not raw_output[index + end :].strip():
        predictions = parsed
        break
if predictions is None:
    raise SystemExit(f"could not parse prediction JSON output:\n{raw_output}")
if len(predictions) != 1:
    raise SystemExit(f"expected one prediction result, got {len(predictions)}")

row = predictions[0]
if row.get("item_id") != "nira-demo-item-1":
    raise SystemExit(f"unexpected item_id in prediction output: {row.get('item_id')}")
scores = row.get("scores") or []
if not scores:
    raise SystemExit(f"prediction output missing scores: {row}")
score_entry = scores[0]
score_result_id = score_entry.get("score_result_id")
if not score_result_id:
    raise SystemExit(f"prediction output missing score_result_id: {score_entry}")

headers = {"x-api-key": api_key, "content-type": "application/json"}
query = """
query VerifyPrediction($scoreResultId: ID!, $itemId: String!, $accountKey: String!) {
  account: listAccountByKey(key: $accountKey) {
    items { id key }
  }
  score: getScore(id: "nira-demo-score") {
    id
    championVersionId
  }
  scoreResult: getScoreResult(id: $scoreResultId) {
    id
    itemId
    accountId
    scorecardId
    scoreId
    scoreVersionId
    value
    type
    status
    code
  }
  byItem: listScoreResultByItemId(itemId: $itemId, limit: 20) {
    items { id itemId scoreId scoreVersionId }
  }
}
"""
variables = {
    "scoreResultId": score_result_id,
    "itemId": "nira-demo-item-1",
    "accountKey": account_key,
}
payload = requests.post(
    api_url,
    json={"query": query, "variables": variables},
    headers=headers,
    timeout=30,
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
if score_data.get("championVersionId") != "nira-demo-score-version":
    raise SystemExit("unexpected championVersionId for nira-demo-score")

persisted = data.get("scoreResult") or {}
if not persisted:
    raise SystemExit(f"score result {score_result_id} not found")
if persisted.get("id") != score_result_id:
    raise SystemExit("persisted score result id mismatch")
if persisted.get("itemId") != "nira-demo-item-1":
    raise SystemExit("persisted score result itemId mismatch")
if persisted.get("accountId") != account_id:
    raise SystemExit("persisted score result accountId mismatch")
if persisted.get("scorecardId") != "nira-demo-scorecard":
    raise SystemExit("persisted score result scorecardId mismatch")
if persisted.get("scoreId") != "nira-demo-score":
    raise SystemExit("persisted score result scoreId mismatch")
if persisted.get("scoreVersionId") != "nira-demo-score-version":
    raise SystemExit("persisted score result scoreVersionId mismatch")
if persisted.get("type") != "prediction":
    raise SystemExit("persisted score result type mismatch")
if persisted.get("status") != "COMPLETED":
    raise SystemExit("persisted score result status mismatch")

by_item = (data.get("byItem") or {}).get("items") or []
if score_result_id not in {row.get("id") for row in by_item}:
    raise SystemExit("new score result missing from listScoreResultByItemId results")

print(f"Prediction smoke passed with score_result_id={score_result_id}")
PY
  )
}

main() {
  run_step "Proxy readyz is healthy" wait_for_readyz
  run_step "Nira seed data and champion path are available" assert_nira_seed_and_champion_path
  run_step "Prediction CLI dependencies are available" ensure_predict_dependencies
  run_step "CLI predict roundtrip persists ScoreResult locally" run_predict_and_verify_score_result

  log "Smoke summary: pass=$passes fail=$failures"
  if [[ "$failures" -gt 0 ]]; then
    exit 1
  fi
}

main "$@"
