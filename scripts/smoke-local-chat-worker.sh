#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PLEXUS_API_URL="${PLEXUS_API_URL:-http://localhost:18080/graphql}"
export PLEXUS_API_KEY="${PLEXUS_API_KEY:-local-smoke-key}"
export PLEXUS_ACCOUNT_KEY="${PLEXUS_ACCOUNT_KEY:-local-demo}"
export SMOKE_CHAT_RESPONSE_TARGET="${SMOKE_CHAT_RESPONSE_TARGET:-local:smoke-worker}"
export SMOKE_CHAT_PROMPT="${SMOKE_CHAT_PROMPT:-Please multiply 7 by 6.}"
export SMOKE_PROOF_DIR="${SMOKE_PROOF_DIR:-$ROOT_DIR/tmp/local-control-plane-proof}"
export SMOKE_CHAT_WORKER_PROOF_FILE="${SMOKE_CHAT_WORKER_PROOF_FILE:-$SMOKE_PROOF_DIR/chat-worker.json}"
SMOKE_CHAT_LIMIT="${SMOKE_CHAT_LIMIT:-1}"
SMOKE_READY_ATTEMPTS="${SMOKE_READY_ATTEMPTS:-60}"
SMOKE_READY_SLEEP_SECONDS="${SMOKE_READY_SLEEP_SECONDS:-2}"
SMOKE_ASSERT_NO_UPSTREAM="${SMOKE_ASSERT_NO_UPSTREAM:-1}"

failures=0
passes=0

log() {
  printf '[smoke-local-chat-worker] %s\n' "$*"
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

create_pending_chat_message() {
  mkdir -p "$(dirname "$SMOKE_CHAT_WORKER_PROOF_FILE")"
  (
    cd "$ROOT_DIR"
    PLEXUS_API_URL="$PLEXUS_API_URL" \
    PLEXUS_API_KEY="$PLEXUS_API_KEY" \
    PLEXUS_ACCOUNT_KEY="$PLEXUS_ACCOUNT_KEY" \
    SMOKE_CHAT_RESPONSE_TARGET="$SMOKE_CHAT_RESPONSE_TARGET" \
    SMOKE_CHAT_PROMPT="$SMOKE_CHAT_PROMPT" \
    SMOKE_CHAT_WORKER_PROOF_FILE="$SMOKE_CHAT_WORKER_PROOF_FILE" \
    poetry run python - <<'PY'
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from plexus.cli.procedure.builtin_procedures import CONSOLE_CHAT_BUILTIN_ID
from plexus.dashboard.api.client import ClientContext, PlexusDashboardClient

api_url = os.environ["PLEXUS_API_URL"]
api_key = os.environ["PLEXUS_API_KEY"]
account_key = os.environ["PLEXUS_ACCOUNT_KEY"]
response_target = os.environ["SMOKE_CHAT_RESPONSE_TARGET"]
prompt = os.environ["SMOKE_CHAT_PROMPT"]
proof_file = Path(os.environ["SMOKE_CHAT_WORKER_PROOF_FILE"])
ids_file = proof_file.with_suffix(".ids.json")

client = PlexusDashboardClient(
    api_url=api_url,
    api_key=api_key,
    context=ClientContext(account_key=account_key),
)
account_id = client._resolve_account_id()
session_id = f"local-worker-smoke-session-{uuid.uuid4().hex[:12]}"
message_id = f"local-worker-smoke-message-{uuid.uuid4().hex[:12]}"
now = datetime.now(timezone.utc).isoformat()

create_session = """
mutation CreateChatSession($input: CreateChatSessionInput!) {
  createChatSession(input: $input) {
    id
    accountId
    procedureId
    category
    status
    createdAt
    updatedAt
  }
}
"""
create_message = """
mutation CreateChatMessage($input: CreateChatMessageInput!) {
  createChatMessage(input: $input) {
    id
    accountId
    sessionId
    role
    humanInteraction
    messageType
    responseTarget
    responseStatus
    createdAt
  }
}
"""

session_result = client.execute(
    create_session,
    {
        "input": {
            "id": session_id,
            "accountId": account_id,
            "procedureId": CONSOLE_CHAT_BUILTIN_ID,
            "name": "Local Worker Smoke Session",
            "category": "Console Chat",
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        }
    },
)
session = session_result.get("createChatSession")
if not isinstance(session, dict) or session.get("id") != session_id:
    raise SystemExit(f"createChatSession did not return expected id: {session_result}")

message_result = client.execute(
    create_message,
    {
        "input": {
            "id": message_id,
            "accountId": account_id,
            "sessionId": session_id,
            "procedureId": CONSOLE_CHAT_BUILTIN_ID,
            "role": "USER",
            "messageType": "MESSAGE",
            "humanInteraction": "CHAT",
            "responseTarget": response_target,
            "responseStatus": "PENDING",
            "content": prompt,
            "metadata": json.dumps(
                {
                    "source": "scripts/smoke-local-chat-worker.sh",
                    "smoke": "local-chat-worker",
                }
            ),
            "createdAt": now,
        }
    },
)
message = message_result.get("createChatMessage")
if not isinstance(message, dict) or message.get("id") != message_id:
    raise SystemExit(f"createChatMessage did not return expected id: {message_result}")

proof = {
    "account_id": account_id,
    "account_key": account_key,
    "session_id": session_id,
    "trigger_message_id": message_id,
    "prompt": prompt,
    "response_target": response_target,
    "created_at": now,
}
proof_file.write_text(json.dumps(proof, indent=2, sort_keys=True))
ids_file.write_text(json.dumps({"session_id": session_id, "message_id": message_id}, sort_keys=True))
print(json.dumps({"session_id": session_id, "message_id": message_id}))
PY
  )
}

run_chat_worker_once() {
  (
    cd "$ROOT_DIR"
    PLEXUS_API_URL="$PLEXUS_API_URL" \
    PLEXUS_API_KEY="$PLEXUS_API_KEY" \
    PLEXUS_ACCOUNT_KEY="$PLEXUS_ACCOUNT_KEY" \
    CONSOLE_AUTO_TITLE_ENABLED=false \
    SMOKE_CHAT_RESPONSE_TARGET="$SMOKE_CHAT_RESPONSE_TARGET" \
    SMOKE_CHAT_LIMIT="$SMOKE_CHAT_LIMIT" \
    poetry run python - <<'PY' >/tmp/plexus-smoke-chat-worker.out
from plexus.cli.chat.chats import chat
import os

chat.main(
    args=[
        "worker",
        "--response-target",
        os.environ["SMOKE_CHAT_RESPONSE_TARGET"],
        "--limit",
        os.environ["SMOKE_CHAT_LIMIT"],
        "--once",
    ],
    prog_name="chat",
    standalone_mode=False,
)
PY
  )
}

verify_chat_completion() {
  (
    cd "$ROOT_DIR"
    PLEXUS_API_URL="$PLEXUS_API_URL" \
    PLEXUS_API_KEY="$PLEXUS_API_KEY" \
    SMOKE_CHAT_WORKER_PROOF_FILE="$SMOKE_CHAT_WORKER_PROOF_FILE" \
    poetry run python - <<'PY'
import json
import os
from datetime import datetime
from pathlib import Path

from plexus.dashboard.api.client import PlexusDashboardClient

proof_file = Path(os.environ["SMOKE_CHAT_WORKER_PROOF_FILE"])
proof = json.loads(proof_file.read_text())
session_id = proof["session_id"]
trigger_message_id = proof["trigger_message_id"]
trigger_created_at = proof["created_at"]

client = PlexusDashboardClient(
    api_url=os.environ["PLEXUS_API_URL"],
    api_key=os.environ["PLEXUS_API_KEY"],
)

get_message = """
query GetChatMessage($id: ID!) {
  getChatMessage(id: $id) {
    id
    sessionId
    responseStatus
    responseOwner
    responseTarget
    responseCompletedAt
    responseError
    updatedAt
  }
}
"""
trigger_result = client.execute(get_message, {"id": trigger_message_id})
trigger = trigger_result.get("getChatMessage")
if not isinstance(trigger, dict):
    raise SystemExit(f"trigger message {trigger_message_id} missing from API response")
if trigger.get("responseStatus") != "COMPLETED":
    raise SystemExit(
        f"trigger message did not complete: responseStatus={trigger.get('responseStatus')} "
        f"responseError={trigger.get('responseError')!r}"
    )
if not str(trigger.get("responseOwner") or "").strip():
    raise SystemExit("trigger message is missing responseOwner")
if not str(trigger.get("responseCompletedAt") or "").strip():
    raise SystemExit("trigger message is missing responseCompletedAt")

list_messages = """
query ListChatMessages($sessionId: String!, $limit: Int) {
  listChatMessageBySessionIdAndCreatedAt(
    sessionId: $sessionId
    sortDirection: ASC
    limit: $limit
  ) {
    items {
      id
      role
      humanInteraction
      messageType
      content
      createdAt
    }
  }
}
"""
message_page = client.execute(list_messages, {"sessionId": session_id, "limit": 200})
items = (message_page.get("listChatMessageBySessionIdAndCreatedAt") or {}).get("items") or []

assistant_messages = []
for item in items:
    if not isinstance(item, dict):
        continue
    if str(item.get("role") or "").upper() != "ASSISTANT":
        continue
    if str(item.get("messageType") or "").upper() != "MESSAGE":
        continue
    if str(item.get("humanInteraction") or "").upper() != "CHAT_ASSISTANT":
        continue
    created_at = str(item.get("createdAt") or "")
    if created_at and created_at < trigger_created_at:
        continue
    assistant_messages.append(item)

if not assistant_messages:
    raise SystemExit("no assistant CHAT_ASSISTANT response found in session")

assistant = assistant_messages[-1]
assistant_content = str(assistant.get("content") or "").strip()
if "42" not in assistant_content:
    raise SystemExit(
        "assistant response did not contain expected deterministic value '42' "
        f"(content={assistant_content!r})"
    )

proof.update(
    {
        "response_status": trigger.get("responseStatus"),
        "response_owner": trigger.get("responseOwner"),
        "response_completed_at": trigger.get("responseCompletedAt"),
        "assistant_message_id": assistant.get("id"),
        "assistant_content": assistant_content,
        "verified_at": datetime.utcnow().isoformat() + "Z",
    }
)
proof_file.write_text(json.dumps(proof, indent=2, sort_keys=True))
print(json.dumps({"trigger_message_id": trigger_message_id, "assistant_message_id": assistant.get("id")}))
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
  run_step "Create local pending chat message" create_pending_chat_message
  run_step "Run local chat worker once" run_chat_worker_once
  run_step "Trigger message completed and assistant reply persisted" verify_chat_completion
  run_step "Proxy made no upstream requests" assert_no_upstream_requests

  log "Smoke summary: pass=$passes fail=$failures"
  if [[ "$failures" -gt 0 ]]; then
    exit 1
  fi
}

main "$@"
