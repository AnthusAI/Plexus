#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PLEXUS_BACKEND_MODE="${PLEXUS_BACKEND_MODE:-local}"
export PLEXUS_PROXY_UPSTREAM_DISABLED="${PLEXUS_PROXY_UPSTREAM_DISABLED:-true}"
export PLEXUS_API_URL="${PLEXUS_API_URL:-http://localhost:18080/graphql}"
export PLEXUS_API_KEY="${PLEXUS_API_KEY:-local-smoke-key}"
export PLEXUS_ACCOUNT_KEY="${PLEXUS_ACCOUNT_KEY:-local-demo}"
export SMOKE_PROOF_DIR="${SMOKE_PROOF_DIR:-$ROOT_DIR/tmp/local-control-plane-proof}"
export SMOKE_TASK_DISPATCH_PROOF_FILE="${SMOKE_TASK_DISPATCH_PROOF_FILE:-$SMOKE_PROOF_DIR/task-dispatch.json}"
export SMOKE_CHAT_WORKER_PROOF_FILE="${SMOKE_CHAT_WORKER_PROOF_FILE:-$SMOKE_PROOF_DIR/chat-worker.json}"
export SMOKE_WORKER_ORCHESTRATION_PROOF_FILE="${SMOKE_WORKER_ORCHESTRATION_PROOF_FILE:-$SMOKE_PROOF_DIR/worker-orchestration.json}"
WORKER_PROOF_RUN_BASE="${WORKER_PROOF_RUN_BASE:-0}"

log() {
  printf '[prove-local-worker-orchestration] %s\n' "$*"
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

run_base_proof_if_requested() {
  if [[ "$WORKER_PROOF_RUN_BASE" != "1" ]]; then
    return 0
  fi

  log "Running full local control-plane proof before worker orchestration checks."
  "$ROOT_DIR/scripts/prove-local-control-plane.sh"
}

run_task_dispatch_smoke() {
  log "Running local task-dispatch smoke."
  "$ROOT_DIR/scripts/smoke-local-task-dispatch.sh"
}

run_chat_worker_smoke() {
  log "Running local chat-worker smoke."
  "$ROOT_DIR/scripts/smoke-local-chat-worker.sh"
}

write_worker_proof_artifact() {
  mkdir -p "$SMOKE_PROOF_DIR"
  python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

task_file = Path(os.environ["SMOKE_TASK_DISPATCH_PROOF_FILE"])
chat_file = Path(os.environ["SMOKE_CHAT_WORKER_PROOF_FILE"])
out_file = Path(os.environ["SMOKE_WORKER_ORCHESTRATION_PROOF_FILE"])

if not task_file.exists():
    raise SystemExit(f"task-dispatch proof file missing: {task_file}")
if not chat_file.exists():
    raise SystemExit(f"chat-worker proof file missing: {chat_file}")

task = json.loads(task_file.read_text())
chat = json.loads(chat_file.read_text())

artifact = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "backend_mode": os.environ.get("PLEXUS_BACKEND_MODE"),
    "upstream_disabled": os.environ.get("PLEXUS_PROXY_UPSTREAM_DISABLED"),
    "account_key": os.environ.get("PLEXUS_ACCOUNT_KEY"),
    "checks": {
        "task_dispatch": {
            "status": task.get("status"),
            "dispatch_status": task.get("dispatch_status"),
            "task_id": task.get("task_id"),
            "worker_node_id": task.get("worker_node_id"),
        },
        "chat_worker": {
            "response_status": chat.get("response_status"),
            "trigger_message_id": chat.get("trigger_message_id"),
            "assistant_message_id": chat.get("assistant_message_id"),
            "response_owner": chat.get("response_owner"),
        },
    },
}

if artifact["checks"]["task_dispatch"]["status"] != "COMPLETED":
    raise SystemExit("task dispatch check did not complete successfully")
if artifact["checks"]["chat_worker"]["response_status"] != "COMPLETED":
    raise SystemExit("chat worker check did not complete successfully")

out_file.write_text(json.dumps(artifact, indent=2, sort_keys=True))
print(json.dumps(artifact, indent=2, sort_keys=True))
PY
}

main() {
  assert_local_mode
  run_base_proof_if_requested
  run_task_dispatch_smoke
  run_chat_worker_smoke
  write_worker_proof_artifact
  log "Worker orchestration proof passed."
}

main "$@"
