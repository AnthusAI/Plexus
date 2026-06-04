#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PLEXUS_API_URL="${PLEXUS_API_URL:-http://localhost:18080/graphql}"
export PLEXUS_API_KEY="${PLEXUS_API_KEY:-local-smoke-key}"
export PLEXUS_ACCOUNT_KEY="${PLEXUS_ACCOUNT_KEY:-local-demo}"
SMOKE_CLEANUP="${SMOKE_CLEANUP:-1}"
SMOKE_READY_ATTEMPTS="${SMOKE_READY_ATTEMPTS:-60}"
SMOKE_READY_SLEEP_SECONDS="${SMOKE_READY_SLEEP_SECONDS:-2}"

failures=0
passes=0

log() {
  printf '[smoke-local-cli] %s\n' "$*"
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

assert_seeded_graphql_records() {
  local query
  query='query LocalSeedCheck { account:getAccount(id:"local-demo-account"){id key} scorecard:getScorecard(id:"local-demo-scorecard"){id} item:getItem(id:"local-demo-item-1"){id} task:getTask(id:"local-demo-task"){id} evaluation:getEvaluation(id:"local-demo-evaluation"){id} report:getReport(id:"local-demo-report"){id} procedure:getProcedure(id:"local-demo-procedure"){id} chatSession:getChatSession(id:"local-demo-chat-session"){id} }'

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
required=["account","scorecard","item","task","evaluation","report","procedure","chatSession"]
missing=[k for k in required if not data.get(k)]
if missing:
    raise SystemExit(1)
account=data["account"]
if account.get("key")!="local-demo":
    raise SystemExit(1)
' "$payload"
}

cli_items_list_with_fallback() {
  (
    cd "$ROOT_DIR"
    PLEXUS_API_URL="$PLEXUS_API_URL" \
    PLEXUS_API_KEY="$PLEXUS_API_KEY" \
    PLEXUS_ACCOUNT_KEY="$PLEXUS_ACCOUNT_KEY" \
    poetry run python - <<'PY' >/tmp/plexus-smoke-items-list.out
from plexus.cli.item.items import items
import os

account = os.environ["PLEXUS_ACCOUNT_KEY"]

try:
    items.main(
        args=["list", "--account", account, "--limit", "1"],
        prog_name="items",
        standalone_mode=False,
    )
except Exception as exc:
    print(f"items list fallback triggered: {exc}")
    items.main(
        args=[
            "info",
            "local-demo-item-1",
            "--account",
            account,
            "--minimal",
        ],
        prog_name="items",
        standalone_mode=False,
    )
PY
  )
}

cli_tasks_last_with_fallback() {
  (
    cd "$ROOT_DIR"
    PLEXUS_API_URL="$PLEXUS_API_URL" \
    PLEXUS_API_KEY="$PLEXUS_API_KEY" \
    PLEXUS_ACCOUNT_KEY="$PLEXUS_ACCOUNT_KEY" \
    poetry run python - <<'PY' >/tmp/plexus-smoke-tasks-last.out
from plexus.cli.task.tasks import tasks

account = __import__("os").environ["PLEXUS_ACCOUNT_KEY"]

try:
    tasks.main(
        args=["last", "--account", account],
        prog_name="tasks",
        standalone_mode=False,
    )
except Exception as exc:
    print(f"tasks last fallback triggered: {exc}")
    tasks.main(
        args=["info", "--id", "local-demo-task"],
        prog_name="tasks",
        standalone_mode=False,
    )
PY
  )
}

cli_create_and_lookup() {
  (
    cd "$ROOT_DIR"
    PLEXUS_API_URL="$PLEXUS_API_URL" \
    PLEXUS_API_KEY="$PLEXUS_API_KEY" \
    PLEXUS_ACCOUNT_KEY="$PLEXUS_ACCOUNT_KEY" \
    SMOKE_CLEANUP="$SMOKE_CLEANUP" \
    poetry run python - <<'PY' >/tmp/plexus-smoke-item-create-info-delete.out
import io
import os
import re
from contextlib import redirect_stdout

from plexus.cli.item.items import items

account = os.environ["PLEXUS_ACCOUNT_KEY"]
cleanup = os.environ.get("SMOKE_CLEANUP", "1") == "1"
external_id = f"local-cli-smoke-{__import__('time').strftime('%Y%m%d%H%M%S')}"

create_out = io.StringIO()
with redirect_stdout(create_out):
    items.main(
        args=[
            "create",
            "--account",
            account,
            "--text",
            "Local CLI smoke item",
            "--description",
            "Created by scripts/smoke-local-cli.sh",
            "--external-id",
            external_id,
        ],
        prog_name="items",
        standalone_mode=False,
    )

create_text = create_out.getvalue()
print(create_text)
match = re.search(r"Successfully created item:\s*([A-Za-z0-9-]+)", create_text)
if not match:
    raise SystemExit("Could not parse created item ID from CLI output")

created_id = match.group(1)

items.main(
    args=[
        "info",
        created_id,
        "--account",
        account,
        "--minimal",
    ],
    prog_name="items",
    standalone_mode=False,
)

if cleanup:
    items.main(
        args=[
            "delete",
            created_id,
            "--account",
            account,
            "--force",
        ],
        prog_name="items",
        standalone_mode=False,
    )

print(f"SMOKE_EXTERNAL_ID={external_id}")
print(f"SMOKE_ITEM_ID={created_id}")
PY
  )
}

main() {
  run_step "Proxy readyz is healthy" wait_for_readyz
  run_step "Seeded GraphQL records exist" assert_seeded_graphql_records
  run_step "CLI items list (fallback to seeded info if index root is unavailable)" cli_items_list_with_fallback
  run_step "CLI tasks last (fallback to seeded task info if index root is unavailable)" cli_tasks_last_with_fallback
  run_step "CLI create + info (+ optional cleanup)" cli_create_and_lookup

  log "Smoke summary: pass=$passes fail=$failures"
  if [[ "$failures" -gt 0 ]]; then
    exit 1
  fi
}

main "$@"
