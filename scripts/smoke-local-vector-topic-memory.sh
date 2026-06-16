#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PLEXUS_API_URL="${PLEXUS_API_URL:-http://localhost:18080/graphql}"
export PLEXUS_API_KEY="${PLEXUS_API_KEY:-local-smoke-key}"
export PLEXUS_ACCOUNT_KEY="${PLEXUS_ACCOUNT_KEY:-local-demo}"
export SMOKE_PROOF_DIR="${SMOKE_PROOF_DIR:-$ROOT_DIR/tmp/local-control-plane-proof}"
export SMOKE_VECTOR_TOPIC_MEMORY_PROOF_FILE="${SMOKE_VECTOR_TOPIC_MEMORY_PROOF_FILE:-$SMOKE_PROOF_DIR/vector-topic-memory.json}"
export SMOKE_VECTOR_TOPIC_MEMORY_SCORECARD="${SMOKE_VECTOR_TOPIC_MEMORY_SCORECARD:-nira-call-center-qa}"
export SMOKE_VECTOR_TOPIC_MEMORY_DAYS="${SMOKE_VECTOR_TOPIC_MEMORY_DAYS:-30}"
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
SMOKE_ASSERT_NO_UPSTREAM="${SMOKE_ASSERT_NO_UPSTREAM:-1}"
SMOKE_READY_ATTEMPTS="${SMOKE_READY_ATTEMPTS:-60}"
SMOKE_READY_SLEEP_SECONDS="${SMOKE_READY_SLEEP_SECONDS:-2}"

failures=0
passes=0

log() {
  printf '[smoke-local-vector-topic-memory] %s\n' "$*"
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

wait_for_qdrant() {
  local i
  local qdrant_collections_url="${PLEXUS_VECTOR_STORE_URL%/}/collections"
  for ((i = 1; i <= SMOKE_READY_ATTEMPTS; i++)); do
    if curl -fsS -m 3 "$qdrant_collections_url" >/dev/null 2>&1; then
      return 0
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

run_vector_topic_memory_and_verify() {
  mkdir -p "$(dirname "$SMOKE_VECTOR_TOPIC_MEMORY_PROOF_FILE")"
  (
    cd "$ROOT_DIR"
    poetry run python - <<'PY'
from datetime import datetime, timezone
import json
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
proof_file = Path(os.environ["SMOKE_VECTOR_TOPIC_MEMORY_PROOF_FILE"])
scorecard = os.environ["SMOKE_VECTOR_TOPIC_MEMORY_SCORECARD"]
days = int(os.environ["SMOKE_VECTOR_TOPIC_MEMORY_DAYS"])
cache_key = f"local-vtm-smoke-{int(time.time())}-{uuid.uuid4()}"

result = run_feedback_report_block(
    block_class="VectorTopicMemory",
    scorecard=scorecard,
    days=days,
    account_identifier=os.environ["PLEXUS_ACCOUNT_KEY"],
    cache_key=cache_key,
    fresh=True,
    extra_config={
        "label": {"use_llm": False},
        "vector_store": {
            "provider": os.environ["PLEXUS_VECTOR_STORE_PROVIDER"],
            "url": os.environ["PLEXUS_VECTOR_STORE_URL"],
            "collection": os.environ["PLEXUS_VECTOR_STORE_COLLECTION"],
        },
    },
)

if result.get("status") != "success":
    raise SystemExit(f"vector topic memory report did not succeed: {result}")

headers = {"x-api-key": api_key, "content-type": "application/json"}
query = """
query LocalVectorTopicMemoryBlocks {
  blocks: listReportBlocks(limit: 500) {
    items {
      id
      reportId
      type
      name
      output
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
    if block.get("type") != "VectorTopicMemory":
        continue
    try:
        output = json.loads(block.get("output") or "{}")
    except json.JSONDecodeError:
        continue
    attached_files = block.get("attachedFiles") or []
    if output.get("output_compacted") and output.get("output_attachment") and attached_files:
        candidate_blocks.append((block, output, attached_files))

if not candidate_blocks:
    raise SystemExit("could not find a persisted compacted VectorTopicMemory report block")

candidate_blocks.sort(key=lambda entry: entry[0].get("createdAt") or "")
block, compact_output, attached_files = candidate_blocks[-1]
output_attachment = compact_output["output_attachment"]
if output_attachment not in attached_files:
    raise SystemExit("output attachment missing from attachedFiles")

artifact_content, _ = download_report_block_file(output_attachment)
artifact = yaml.safe_load(artifact_content)
if not isinstance(artifact, dict):
    raise SystemExit("downloaded vector topic memory artifact was not a YAML/JSON object")

if artifact.get("status") != "ok":
    raise SystemExit(f"expected status=ok, got {artifact.get('status')}")
if artifact.get("vector_store_provider") != "qdrant":
    raise SystemExit(
        f"expected vector_store_provider=qdrant, got {artifact.get('vector_store_provider')}"
    )

indexed_doc_count = int(artifact.get("indexed_doc_count") or 0)
if indexed_doc_count <= 0:
    raise SystemExit(f"expected indexed_doc_count > 0, got {indexed_doc_count}")

scores = artifact.get("scores") or []
if not scores:
    raise SystemExit("expected non-empty score list in vector topic memory artifact")
topic_count = sum(len((score or {}).get("topics") or []) for score in scores)
if topic_count <= 0:
    raise SystemExit("expected at least one topic in vector topic memory artifact")

proof_file.parent.mkdir(parents=True, exist_ok=True)
proof_file.write_text(
    json.dumps(
        {
            "reportId": block["reportId"],
            "reportBlockId": block["id"],
            "outputAttachment": output_attachment,
            "indexedDocCount": indexed_doc_count,
            "topicCount": topic_count,
            "vectorStoreProvider": artifact.get("vector_store_provider"),
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        indent=2,
        sort_keys=True,
    )
)

print(f"VectorTopicMemory smoke passed with report_block_id={block['id']}")
print(f"VectorTopicMemory proof written to {proof_file}")
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
    raise SystemExit(f"expected no upstream proxy requests in local vector topic memory smoke, found {len(payload)}")
' "$payload"
}

main() {
  run_step "Proxy readyz is healthy" wait_for_readyz
  run_step "Qdrant is available" wait_for_qdrant
  run_step "MinIO report bucket is available" wait_for_object_store
  run_step "VectorTopicMemory persists local vector/report artifacts" run_vector_topic_memory_and_verify
  run_step "Proxy made no upstream requests" assert_no_upstream_requests

  log "Smoke summary: pass=$passes fail=$failures"
  [[ "$failures" -eq 0 ]]
}

main "$@"
