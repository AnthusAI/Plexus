#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PLEXUS_API_URL="${PLEXUS_API_URL:-http://localhost:18080/graphql}"
export PLEXUS_API_KEY="${PLEXUS_API_KEY:-local-smoke-key}"
export PLEXUS_ACCOUNT_KEY="${PLEXUS_ACCOUNT_KEY:-local-demo}"
# The local control plane deliberately uses its API-key boundary instead of
# Cognito. Make the CLI client select that supported transport explicitly.
export PLEXUS_GRAPHQL_AUTH_MODE="api_key"
export PLEXUS_DISPATCH_MODE="${PLEXUS_DISPATCH_MODE:-local}"
export SMOKE_PROOF_DIR="${SMOKE_PROOF_DIR:-$ROOT_DIR/tmp/local-control-plane-proof}"
export SMOKE_TASK_DISPATCH_PROOF_FILE="${SMOKE_TASK_DISPATCH_PROOF_FILE:-$SMOKE_PROOF_DIR/task-dispatch.json}"
export SMOKE_TASK_COMMAND="${SMOKE_TASK_COMMAND:-items info local-demo-item-1 --account local-demo --minimal}"
SMOKE_DISPATCH_LIMIT="${SMOKE_DISPATCH_LIMIT:-25}"
SMOKE_READY_ATTEMPTS="${SMOKE_READY_ATTEMPTS:-60}"
SMOKE_READY_SLEEP_SECONDS="${SMOKE_READY_SLEEP_SECONDS:-2}"
SMOKE_ASSERT_NO_UPSTREAM="${SMOKE_ASSERT_NO_UPSTREAM:-1}"

failures=0
passes=0

log() {
  printf '[smoke-local-task-dispatch] %s\n' "$*"
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

ensure_dispatcher_cli_dependencies() {
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

for _ in range(24):
    try:
        importlib.import_module("plexus.cli.shared.CommandLineInterface")
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
    raise SystemExit("could not resolve dispatcher CLI dependencies after multiple install attempts")
PY
  )
}

create_pending_task() {
  mkdir -p "$(dirname "$SMOKE_TASK_DISPATCH_PROOF_FILE")"
  (
    cd "$ROOT_DIR"
    PLEXUS_API_URL="$PLEXUS_API_URL" \
    PLEXUS_API_KEY="$PLEXUS_API_KEY" \
    PLEXUS_ACCOUNT_KEY="$PLEXUS_ACCOUNT_KEY" \
    SMOKE_TASK_DISPATCH_PROOF_FILE="$SMOKE_TASK_DISPATCH_PROOF_FILE" \
    SMOKE_TASK_COMMAND="$SMOKE_TASK_COMMAND" \
    poetry run python - <<'PY'
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from plexus.dashboard.api.client import ClientContext, PlexusDashboardClient

api_url = os.environ["PLEXUS_API_URL"]
api_key = os.environ["PLEXUS_API_KEY"]
account_key = os.environ["PLEXUS_ACCOUNT_KEY"]
command = os.environ["SMOKE_TASK_COMMAND"]
proof_file = Path(os.environ["SMOKE_TASK_DISPATCH_PROOF_FILE"])
task_id_file = proof_file.with_suffix(".task-id")

client = PlexusDashboardClient(
    api_url=api_url,
    api_key=api_key,
    context=ClientContext(account_key=account_key),
)
account_id = client._resolve_account_id()
task_id = f"local-worker-smoke-task-{uuid.uuid4().hex[:12]}"
now = datetime.now(timezone.utc).isoformat()

mutation = """
mutation CreateTask($input: CreateTaskInput!) {
  createTask(input: $input) {
    id
    accountId
    status
    dispatchStatus
    target
    command
    createdAt
    updatedAt
  }
}
"""

metadata = {
    "smoke": "local-task-dispatch",
    "dispatch_mode": "local",
    "source": "scripts/smoke-local-task-dispatch.sh",
}

payload = client.execute(
    mutation,
    {
        "input": {
            "id": task_id,
            "accountId": account_id,
            "type": "Command",
            "status": "PENDING",
            "dispatchStatus": "PENDING",
            "target": "smoke/local-task-dispatch",
            "command": command,
            "metadata": json.dumps(metadata),
            "createdAt": now,
            "updatedAt": now,
        }
    },
)
created = payload.get("createTask")
if not isinstance(created, dict) or created.get("id") != task_id:
    raise SystemExit(f"createTask did not return expected task id: {payload}")

task_id_file.write_text(task_id)
proof = {
    "task_id": task_id,
    "account_id": account_id,
    "account_key": account_key,
    "command": command,
    "created_at": now,
}
proof_file.write_text(json.dumps(proof, indent=2, sort_keys=True))
print(task_id)
PY
  )
}

run_dispatcher_once() {
  (
    cd "$ROOT_DIR"
    PLEXUS_DISPATCH_MODE="$PLEXUS_DISPATCH_MODE" \
    PLEXUS_API_URL="$PLEXUS_API_URL" \
    PLEXUS_API_KEY="$PLEXUS_API_KEY" \
    PLEXUS_ACCOUNT_KEY="$PLEXUS_ACCOUNT_KEY" \
    SMOKE_DISPATCH_LIMIT="$SMOKE_DISPATCH_LIMIT" \
    poetry run python - <<'PY' >/tmp/plexus-smoke-task-dispatcher.out
from plexus.cli.shared.CommandDispatch import dispatcher
import os

dispatcher.main(
    args=[
        "--once",
        "--account",
        os.environ["PLEXUS_ACCOUNT_KEY"],
        "--limit",
        os.environ["SMOKE_DISPATCH_LIMIT"],
        "--interval",
        "0.2",
        "--loglevel",
        "INFO",
    ],
    prog_name="dispatcher",
    standalone_mode=False,
)
PY
  )
}

verify_task_completion() {
  (
    cd "$ROOT_DIR"
    PLEXUS_API_URL="$PLEXUS_API_URL" \
    PLEXUS_API_KEY="$PLEXUS_API_KEY" \
    SMOKE_TASK_DISPATCH_PROOF_FILE="$SMOKE_TASK_DISPATCH_PROOF_FILE" \
    poetry run python - <<'PY'
import json
import os
from pathlib import Path

from plexus.dashboard.api.client import PlexusDashboardClient

proof_file = Path(os.environ["SMOKE_TASK_DISPATCH_PROOF_FILE"])
task_id_file = proof_file.with_suffix(".task-id")
if not task_id_file.exists():
    raise SystemExit("missing task id file for verification")
task_id = task_id_file.read_text().strip()
if not task_id:
    raise SystemExit("task id file is empty")

client = PlexusDashboardClient(
    api_url=os.environ["PLEXUS_API_URL"],
    api_key=os.environ["PLEXUS_API_KEY"],
)
query = """
query GetTask($id: ID!) {
  getTask(id: $id) {
    id
    accountId
    status
    dispatchStatus
    target
    command
    metadata
    startedAt
    completedAt
    errorMessage
    errorDetails
    stdout
    stderr
    workerNodeId
    updatedAt
  }
}
"""
result = client.execute(query, {"id": task_id})
task = result.get("getTask")
if not isinstance(task, dict):
    raise SystemExit(f"getTask({task_id}) returned no task: {result}")

if task.get("status") != "COMPLETED":
    raise SystemExit(
        f"task {task_id} did not complete successfully: status={task.get('status')} "
        f"error={task.get('errorMessage')!r}"
    )
if task.get("dispatchStatus") != "DISPATCHED":
    raise SystemExit(
        f"task {task_id} has unexpected dispatchStatus={task.get('dispatchStatus')!r}"
    )
if not str(task.get("workerNodeId") or "").strip():
    raise SystemExit(f"task {task_id} is missing workerNodeId")
if not str(task.get("startedAt") or "").strip():
    raise SystemExit(f"task {task_id} is missing startedAt")
if not str(task.get("completedAt") or "").strip():
    raise SystemExit(f"task {task_id} is missing completedAt")

metadata = task.get("metadata")
if isinstance(metadata, str):
    try:
        metadata = json.loads(metadata)
    except json.JSONDecodeError:
        metadata = {}
if not isinstance(metadata, dict):
    metadata = {}
if metadata.get("dispatch_mode") != "local":
    raise SystemExit(
        f"task {task_id} metadata dispatch_mode expected 'local', got {metadata.get('dispatch_mode')!r}"
    )
if not str(task.get("stdout") or "").strip():
    raise SystemExit(f"task {task_id} expected non-empty stdout from command execution")

proof = json.loads(proof_file.read_text()) if proof_file.exists() else {}
proof.update(
    {
        "status": task.get("status"),
        "dispatch_status": task.get("dispatchStatus"),
        "worker_node_id": task.get("workerNodeId"),
        "started_at": task.get("startedAt"),
        "completed_at": task.get("completedAt"),
        "updated_at": task.get("updatedAt"),
        "stdout_tail": str(task.get("stdout") or "")[-400:],
    }
)
proof_file.write_text(json.dumps(proof, indent=2, sort_keys=True))
print(json.dumps({"task_id": task_id, "status": task.get("status")}))
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
    raise SystemExit(f"expected no upstream proxy requests in local smoke, found {len(payload)}")
' "$payload"
}

main() {
  run_step "Proxy readyz is healthy" wait_for_readyz
  run_step "Ensure dispatcher CLI dependencies are installed" ensure_dispatcher_cli_dependencies
  run_step "Create local pending task for dispatcher" create_pending_task
  run_step "Run local dispatcher once" run_dispatcher_once
  run_step "Task reached terminal COMPLETED state" verify_task_completion
  run_step "Proxy made no upstream requests" assert_no_upstream_requests

  log "Smoke summary: pass=$passes fail=$failures"
  if [[ "$failures" -gt 0 ]]; then
    exit 1
  fi
}

main "$@"
