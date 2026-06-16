#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PLEXUS_API_URL="${PLEXUS_API_URL:-http://localhost:18080/graphql}"
export PLEXUS_API_KEY="${PLEXUS_API_KEY:-local-smoke-key}"
export PLEXUS_ACCOUNT_KEY="${PLEXUS_ACCOUNT_KEY:-local-demo}"
export SMOKE_PROOF_DIR="${SMOKE_PROOF_DIR:-$ROOT_DIR/tmp/local-control-plane-proof}"
export SMOKE_REPORT_PROOF_FILE="${SMOKE_REPORT_PROOF_FILE:-$SMOKE_PROOF_DIR/report.json}"
export SMOKE_REPORT_SCORECARD="${SMOKE_REPORT_SCORECARD:-nira-call-center-qa}"
export SMOKE_REPORT_SCORE="${SMOKE_REPORT_SCORE:-nira-resolution-quality}"
export SMOKE_REPORT_DAYS="${SMOKE_REPORT_DAYS:-30}"
export AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME="${AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME:-plexus-local-report-block-details}"
export PLEXUS_OBJECT_STORE_ENDPOINT="${PLEXUS_OBJECT_STORE_ENDPOINT:-http://localhost:19000}"
export PLEXUS_OBJECT_STORE_REGION="${PLEXUS_OBJECT_STORE_REGION:-us-east-1}"
export PLEXUS_OBJECT_STORE_FORCE_PATH_STYLE="${PLEXUS_OBJECT_STORE_FORCE_PATH_STYLE:-true}"
export PLEXUS_OBJECT_STORE_ACCESS_KEY_ID="${PLEXUS_OBJECT_STORE_ACCESS_KEY_ID:-plexus-local}"
export PLEXUS_OBJECT_STORE_SECRET_ACCESS_KEY="${PLEXUS_OBJECT_STORE_SECRET_ACCESS_KEY:-plexus-local-secret}"
SMOKE_ASSERT_NO_UPSTREAM="${SMOKE_ASSERT_NO_UPSTREAM:-1}"
SMOKE_READY_ATTEMPTS="${SMOKE_READY_ATTEMPTS:-60}"
SMOKE_READY_SLEEP_SECONDS="${SMOKE_READY_SLEEP_SECONDS:-2}"

failures=0
passes=0

log() {
  printf '[smoke-local-report] %s\n' "$*"
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

wait_for_object_store() {
  local i
  for ((i = 1; i <= SMOKE_READY_ATTEMPTS; i++)); do
    if (
      cd "$ROOT_DIR"
      poetry run python - <<'PY' >/dev/null 2>&1
import os
from plexus.reports.s3_utils import create_s3_client, get_bucket_name

create_s3_client().head_bucket(Bucket=get_bucket_name())
PY
    ); then
      return 0
    fi
    sleep "$SMOKE_READY_SLEEP_SECONDS"
  done
  return 1
}

run_report_and_verify_artifacts() {
  mkdir -p "$(dirname "$SMOKE_REPORT_PROOF_FILE")"
  (
    cd "$ROOT_DIR"
    poetry run python - <<'PY'
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time
import uuid

import requests
import yaml

from plexus.cli.feedback.report_runner import run_feedback_report_block
from plexus.reports.s3_utils import download_report_block_file

api_url = os.environ["PLEXUS_API_URL"]
api_key = os.environ["PLEXUS_API_KEY"]
proof_file = Path(os.environ["SMOKE_REPORT_PROOF_FILE"])
scorecard = os.environ["SMOKE_REPORT_SCORECARD"]
score = os.environ["SMOKE_REPORT_SCORE"]
days = int(os.environ["SMOKE_REPORT_DAYS"])
cache_key = f"local-report-smoke-{int(time.time())}-{uuid.uuid4()}"

result = run_feedback_report_block(
    block_class="FeedbackAlignment",
    scorecard=scorecard,
    score=score,
    days=days,
    account_identifier=os.environ["PLEXUS_ACCOUNT_KEY"],
    cache_key=cache_key,
    fresh=True,
)

if result.get("status") != "success":
    raise SystemExit(f"feedback alignment report did not succeed: {result}")

headers = {"x-api-key": api_key, "content-type": "application/json"}
query = """
query LocalReportBlocks {
  blocks: listReportBlocks(limit: 500) {
    items {
      id
      reportId
      type
      name
      output
      log
      attachedFiles
      createdAt
    }
  }
}
"""
response = requests.post(api_url, json={"query": query}, headers=headers, timeout=30)
response.raise_for_status()
body = response.json()
if body.get("errors"):
    raise SystemExit(f"report block lookup returned errors: {body['errors']}")

candidate_blocks = []
for block in ((body.get("data") or {}).get("blocks") or {}).get("items") or []:
    if block.get("type") != "FeedbackAlignment":
        continue
    try:
        output = json.loads(block.get("output") or "{}")
    except json.JSONDecodeError:
        continue
    attached_files = block.get("attachedFiles") or []
    if output.get("output_compacted") and output.get("output_attachment") and attached_files:
        candidate_blocks.append((block, output, attached_files))

if not candidate_blocks:
    raise SystemExit("could not find a persisted compacted FeedbackAlignment report block")

candidate_blocks.sort(key=lambda entry: entry[0].get("createdAt") or "")
block, compact_output, attached_files = candidate_blocks[-1]
output_attachment = compact_output["output_attachment"]
if output_attachment not in attached_files:
    raise SystemExit("output attachment missing from attachedFiles")
if not any(path.endswith("/log.txt") for path in attached_files):
    raise SystemExit("log attachment missing from attachedFiles")

artifact_content, _ = download_report_block_file(output_attachment)
artifact = yaml.safe_load(artifact_content)
if not isinstance(artifact, dict):
    raise SystemExit("downloaded report artifact was not a YAML/JSON object")

total_items = int(artifact.get("total_items") or 0)
accuracy = float(artifact.get("accuracy") or 0.0)
overall_ac1 = float(artifact.get("overall_ac1") or 0.0)
if total_items != 200:
    raise SystemExit(f"expected total_items=200, got {total_items}")
if not math.isclose(accuracy, 80.0, rel_tol=0, abs_tol=0.0001):
    raise SystemExit(f"expected accuracy=80.0, got {accuracy}")
if not math.isclose(overall_ac1, 0.6000000000000001, rel_tol=0, abs_tol=0.0001):
    raise SystemExit(f"expected overall_ac1=0.6000000000000001, got {overall_ac1}")

proof_file.parent.mkdir(parents=True, exist_ok=True)
proof_file.write_text(json.dumps({
    "reportBlockId": block["id"],
    "reportId": block["reportId"],
    "outputAttachment": output_attachment,
    "attachedFiles": attached_files,
    "totalItems": total_items,
    "accuracy": accuracy,
    "overallAc1": overall_ac1,
    "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}, indent=2, sort_keys=True))

print(f"Report smoke passed with report_block_id={block['id']}")
print(f"Report proof written to {proof_file}")
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
    raise SystemExit(f"expected no upstream proxy requests in local report smoke, found {len(payload)}")
' "$payload"
}

main() {
  run_step "Proxy readyz is healthy" wait_for_readyz
  run_step "MinIO report bucket is available" wait_for_object_store
  run_step "Feedback alignment report persists MinIO artifacts" run_report_and_verify_artifacts
  run_step "Proxy made no upstream requests" assert_no_upstream_requests

  log "Smoke summary: pass=$passes fail=$failures"
  if [[ "$failures" -gt 0 ]]; then
    exit 1
  fi
}

main "$@"
