#!/usr/bin/env python3
"""
Console chat smoke test: create session + user message + run task and verify assistant reply.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import pathlib
from typing import Any, Dict, List, Optional

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plexus.dashboard.api.client import ClientContext, PlexusDashboardClient
from plexus.cli.procedure.builtin_procedures import CONSOLE_CHAT_BUILTIN_ID


CREATE_CHAT_SESSION_MUTATION = """
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


CREATE_CHAT_MESSAGE_MUTATION = """
mutation CreateChatMessage($input: CreateChatMessageInput!) {
  createChatMessage(input: $input) {
    id
    sessionId
    procedureId
    role
    humanInteraction
    createdAt
  }
}
"""


CREATE_TASK_MUTATION = """
mutation CreateTask($input: CreateTaskInput!) {
  createTask(input: $input) {
    id
    status
    dispatchStatus
    createdAt
    updatedAt
  }
}
"""


GET_TASK_QUERY = """
query GetTask($id: ID!) {
  getTask(id: $id) {
    id
    status
    dispatchStatus
    errorMessage
    updatedAt
    completedAt
  }
}
"""


LIST_MESSAGES_QUERY = """
query ListMessages($sessionId: String!, $limit: Int) {
  listChatMessageBySessionIdAndCreatedAt(
    sessionId: $sessionId
    sortDirection: ASC
    limit: $limit
  ) {
    items {
      id
      role
      messageType
      humanInteraction
      content
      createdAt
      sessionId
      procedureId
    }
  }
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--account-key",
        default=os.getenv("PLEXUS_ACCOUNT_KEY"),
        help="Account key (defaults to PLEXUS_ACCOUNT_KEY).",
    )
    parser.add_argument(
        "--procedure-id",
        default=CONSOLE_CHAT_BUILTIN_ID,
        help="Procedure ID to run (defaults to builtin:console/chat).",
    )
    parser.add_argument(
        "--message",
        default="Console smoke test ping.",
        help="User message content.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=90,
        help="Max time to wait for assistant response.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=2.0,
        help="Polling interval while waiting for response.",
    )
    parser.add_argument(
        "--dispatch-once",
        action="store_true",
        help="Run local dispatcher once after task creation.",
    )
    parser.add_argument(
        "--mode",
        choices=["direct", "queue"],
        default="direct",
        help="Dispatch mode: direct runs the procedure locally with PLEXUS_DISPATCH_TASK_ID; queue waits for worker dispatch.",
    )
    return parser.parse_args()


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_iso(value: Optional[str]) -> dt.datetime:
    if not value:
        return dt.datetime.fromtimestamp(0, tz=dt.timezone.utc)
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def find_assistant_messages(messages: List[Dict[str, Any]], since: dt.datetime) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for msg in messages:
        role = (msg.get("role") or "").upper()
        created_at = parse_iso(msg.get("createdAt"))
        if role == "ASSISTANT" and created_at >= since:
            results.append(msg)
    return results


def main() -> int:
    args = parse_args()
    if not args.account_key:
        print("Missing account key. Set PLEXUS_ACCOUNT_KEY or pass --account-key.", file=sys.stderr)
        return 1
    if not args.procedure_id:
        print(
            "Missing procedure ID. Pass --procedure-id (for Console default use builtin:console/chat).",
            file=sys.stderr,
        )
        return 1

    client = PlexusDashboardClient(context=ClientContext(account_key=args.account_key))
    account_id = client._resolve_account_id()
    now = iso_now()

    session_input = {
        "accountId": account_id,
        "procedureId": args.procedure_id,
        "category": "Console Chat",
        "status": "ACTIVE",
        "createdAt": now,
        "updatedAt": now,
    }
    session = client.execute(CREATE_CHAT_SESSION_MUTATION, {"input": session_input}).get("createChatSession")
    if not session or not session.get("id"):
        print("Failed to create ChatSession.", file=sys.stderr)
        return 1
    session_id = session["id"]
    print(f"Session: {session_id}")

    message_input = {
        "accountId": account_id,
        "sessionId": session_id,
        "procedureId": args.procedure_id,
        "role": "USER",
        "messageType": "MESSAGE",
        "humanInteraction": "CHAT",
        "content": args.message,
        "metadata": json.dumps({"source": "console-chat-smoke", "sent_at": now}),
        "createdAt": now,
    }
    user_message = client.execute(CREATE_CHAT_MESSAGE_MUTATION, {"input": message_input}).get("createChatMessage")
    if not user_message or not user_message.get("id"):
        print("Failed to create USER ChatMessage.", file=sys.stderr)
        return 1
    user_message_id = user_message["id"]
    user_created_at = parse_iso(user_message.get("createdAt") or now)
    print(f"User message: {user_message_id}")

    dispatch_mode = "local" if args.mode == "direct" else "queue"
    task_metadata = {
        "dispatch_mode": dispatch_mode,
        "console_chat": {
            "session_id": session_id,
            "trigger_message_id": user_message_id,
            "queued_at": now,
        },
    }
    task_input = {
        "accountId": account_id,
        "type": "Procedure Run",
        "status": "RUNNING" if args.mode == "direct" else "PENDING",
        "dispatchStatus": "DISPATCHED" if args.mode == "direct" else "PENDING",
        "target": f"procedure/run/{args.procedure_id}",
        "command": f"procedure run {args.procedure_id}",
        "description": f"Console chat smoke run for {args.procedure_id}",
        "metadata": json.dumps(task_metadata),
        "createdAt": now,
        "updatedAt": now,
    }
    task = client.execute(CREATE_TASK_MUTATION, {"input": task_input}).get("createTask")
    if not task or not task.get("id"):
        print("Failed to create Procedure Run task.", file=sys.stderr)
        return 1
    task_id = task["id"]
    print(f"Task: {task_id}")

    if args.mode == "direct":
        direct_env = os.environ.copy()
        direct_env["PLEXUS_DISPATCH_TASK_ID"] = task_id
        command = ["plexus", "procedure", "run", args.procedure_id, "-o", "json"]
        print(f"Direct run: {' '.join(command)}")
        result = subprocess.run(command, text=True, capture_output=True, check=False, env=direct_env)
        if result.returncode != 0:
            print("Direct procedure run failed:", file=sys.stderr)
            print(result.stderr or result.stdout, file=sys.stderr)
            return 1
    elif args.dispatch_once:
        command = ["plexus", "command", "dispatcher", "--once", "--account", args.account_key]
        print(f"Dispatching once: {' '.join(command)}")
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            print("Dispatcher --once failed:", file=sys.stderr)
            print(result.stderr or result.stdout, file=sys.stderr)
            return 1

    deadline = time.time() + max(5, args.timeout_seconds)
    latest_task: Optional[Dict[str, Any]] = None
    latest_messages: List[Dict[str, Any]] = []
    while time.time() < deadline:
        task_state = client.execute(GET_TASK_QUERY, {"id": task_id}).get("getTask") or {}
        latest_task = task_state

        message_page = client.execute(LIST_MESSAGES_QUERY, {"sessionId": session_id, "limit": 200})
        latest_messages = (
            message_page.get("listChatMessageBySessionIdAndCreatedAt", {}).get("items", [])
            or []
        )
        assistant_messages = find_assistant_messages(latest_messages, user_created_at)
        if assistant_messages:
            latest = assistant_messages[-1]
            print("Assistant reply detected.")
            print(f"Assistant message id: {latest.get('id')}")
            print(f"Assistant content: {str(latest.get('content') or '').strip()[:400]}")
            return 0

        task_status = (task_state.get("status") or "").upper()
        if task_status == "FAILED":
            print("Task failed before assistant reply.", file=sys.stderr)
            print(json.dumps(task_state, indent=2), file=sys.stderr)
            return 1

        time.sleep(max(0.25, args.poll_seconds))

    print("Timed out waiting for assistant reply.", file=sys.stderr)
    if latest_task:
        print("Last task state:", file=sys.stderr)
        print(json.dumps(latest_task, indent=2), file=sys.stderr)
    if latest_messages:
        print("Last messages:", file=sys.stderr)
        print(json.dumps(latest_messages[-5:], indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
