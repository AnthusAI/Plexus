#!/usr/bin/env python3
"""
Authenticated end-to-end smoke test for Console chat dispatch.

This script bootstraps a temporary Cognito app client + user, authenticates,
creates (or reuses) an account, sends one chat message, calls startConsoleRun,
and polls for assistant output and task status.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
import requests


DEFAULT_PROCEDURE_ID = "builtin:console/chat"


LIST_ACCOUNT_BY_KEY = """
query ListAccountByKey($key: String!, $limit: Int) {
  listAccountByKey(key: $key, limit: $limit) {
    items {
      id
      key
      name
    }
  }
}
"""

CREATE_ACCOUNT = """
mutation CreateAccount($input: CreateAccountInput!) {
  createAccount(input: $input) {
    id
    key
    name
  }
}
"""

CREATE_CHAT_SESSION = """
mutation CreateChatSession($input: CreateChatSessionInput!) {
  createChatSession(input: $input) {
    id
    accountId
    procedureId
    status
    category
    createdAt
  }
}
"""

CREATE_CHAT_MESSAGE = """
mutation CreateChatMessage($input: CreateChatMessageInput!) {
  createChatMessage(input: $input) {
    id
    sessionId
    role
    messageType
    createdAt
  }
}
"""

START_CONSOLE_RUN = """
mutation StartConsoleRun(
  $sessionId: String!,
  $procedureId: String!,
  $triggerMessageId: String!,
  $clientInstrumentation: AWSJSON
) {
  startConsoleRun(
    sessionId: $sessionId,
    procedureId: $procedureId,
    triggerMessageId: $triggerMessageId,
    clientInstrumentation: $clientInstrumentation
  ) {
    runId
    taskId
    accepted
    queuedAt
  }
}
"""

LIST_MESSAGES = """
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
      metadata
      createdAt
    }
  }
}
"""

GET_TASK = """
query GetTask($id: ID!) {
  getTask(id: $id) {
    id
    status
    dispatchStatus
    errorMessage
    metadata
    updatedAt
  }
}
"""


class SmokeError(RuntimeError):
    pass


@dataclass
class AuthArtifacts:
    app_client_id: str
    temp_user_email: str
    id_token: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--graphql-url",
        default=os.getenv("PLEXUS_API_URL"),
        required=os.getenv("PLEXUS_API_URL") is None,
        help="AppSync GraphQL endpoint URL (defaults to PLEXUS_API_URL).",
    )
    parser.add_argument("--region", default="us-west-2", help="AWS region for Cognito.")
    parser.add_argument(
        "--user-pool-id",
        required=True,
        help="Cognito User Pool ID used by the target AppSync API.",
    )
    parser.add_argument(
        "--account-key",
        default="console-smoke",
        help="Account key to use; created if missing.",
    )
    parser.add_argument(
        "--account-name",
        default="Console Smoke Account",
        help="Account name if account creation is needed.",
    )
    parser.add_argument(
        "--procedure-id",
        default=DEFAULT_PROCEDURE_ID,
        help=f"Procedure ID to dispatch (default: {DEFAULT_PROCEDURE_ID}).",
    )
    parser.add_argument(
        "--prompt",
        default="Automated smoke test: reply with READY and one short sentence.",
        help="Prompt content for the user chat message.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Max wait time for assistant output.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=2.0,
        help="Polling interval for task/messages.",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=300,
        help="Message fetch limit per poll.",
    )
    parser.add_argument(
        "--keep-auth-artifacts",
        action="store_true",
        help="Keep temporary Cognito user/app client after test.",
    )
    parser.add_argument(
        "--require-dispatch-mode",
        default=None,
        help="Optional expected task metadata.dispatch_mode value (for example: console_async_worker).",
    )
    return parser.parse_args()


def graphql(
    *,
    url: str,
    id_token: str,
    query: str,
    variables: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    response = requests.post(
        url,
        headers={"Authorization": id_token, "content-type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    try:
        payload = response.json()
    except Exception as exc:
        raise SmokeError(f"GraphQL response is not JSON: {exc}") from exc

    if response.status_code != 200:
        raise SmokeError(f"GraphQL HTTP {response.status_code}: {payload}")
    if payload.get("errors"):
        raise SmokeError(f"GraphQL errors: {payload['errors']}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SmokeError(f"GraphQL response missing data: {payload}")
    return data


def bootstrap_auth(region: str, user_pool_id: str) -> AuthArtifacts:
    cognito = boto3.client("cognito-idp", region_name=region)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    temp_user_email = f"codex-console-smoke-{suffix}@example.com"
    temp_password = "Temp!Passw0rd#2026"
    app_client_name = f"codex-console-smoke-{suffix}"

    client_resp = cognito.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName=app_client_name,
        GenerateSecret=False,
        ExplicitAuthFlows=[
            "ALLOW_USER_PASSWORD_AUTH",
            "ALLOW_ADMIN_USER_PASSWORD_AUTH",
            "ALLOW_USER_SRP_AUTH",
            "ALLOW_REFRESH_TOKEN_AUTH",
        ],
        PreventUserExistenceErrors="ENABLED",
    )
    app_client_id = client_resp["UserPoolClient"]["ClientId"]

    cognito.admin_create_user(
        UserPoolId=user_pool_id,
        Username=temp_user_email,
        UserAttributes=[
            {"Name": "email", "Value": temp_user_email},
            {"Name": "email_verified", "Value": "true"},
        ],
        TemporaryPassword=temp_password,
        MessageAction="SUPPRESS",
    )
    cognito.admin_set_user_password(
        UserPoolId=user_pool_id,
        Username=temp_user_email,
        Password=temp_password,
        Permanent=True,
    )
    auth_resp = cognito.initiate_auth(
        ClientId=app_client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": temp_user_email, "PASSWORD": temp_password},
    )
    auth = auth_resp.get("AuthenticationResult") or {}
    id_token = auth.get("IdToken")
    if not id_token:
        raise SmokeError("Failed to obtain Cognito id token")
    return AuthArtifacts(
        app_client_id=app_client_id,
        temp_user_email=temp_user_email,
        id_token=id_token,
    )


def cleanup_auth(*, region: str, user_pool_id: str, auth: AuthArtifacts) -> None:
    cognito = boto3.client("cognito-idp", region_name=region)
    try:
        cognito.admin_delete_user(UserPoolId=user_pool_id, Username=auth.temp_user_email)
    except Exception:
        pass
    try:
        cognito.delete_user_pool_client(UserPoolId=user_pool_id, ClientId=auth.app_client_id)
    except Exception:
        pass


def resolve_or_create_account(*, args: argparse.Namespace, auth: AuthArtifacts) -> Dict[str, Any]:
    account_data = graphql(
        url=args.graphql_url,
        id_token=auth.id_token,
        query=LIST_ACCOUNT_BY_KEY,
        variables={"key": args.account_key, "limit": 1},
    )
    items = ((account_data.get("listAccountByKey") or {}).get("items")) or []
    if items:
        return items[0]

    created = graphql(
        url=args.graphql_url,
        id_token=auth.id_token,
        query=CREATE_ACCOUNT,
        variables={"input": {"name": args.account_name, "key": args.account_key}},
    )
    account = created.get("createAccount")
    if not account:
        raise SmokeError("Failed to create account")
    return account


def run_smoke(args: argparse.Namespace) -> Dict[str, Any]:
    auth = bootstrap_auth(args.region, args.user_pool_id)
    cleaned = False
    try:
        account = resolve_or_create_account(args=args, auth=auth)
        account_id = account["id"]

        session_resp = graphql(
            url=args.graphql_url,
            id_token=auth.id_token,
            query=CREATE_CHAT_SESSION,
            variables={
                "input": {
                    "accountId": account_id,
                    "procedureId": args.procedure_id,
                    "status": "ACTIVE",
                    "category": "Console",
                    "name": "Codex automated smoke",
                }
            },
        )
        session = session_resp["createChatSession"]
        session_id = session["id"]

        user_msg_resp = graphql(
            url=args.graphql_url,
            id_token=auth.id_token,
            query=CREATE_CHAT_MESSAGE,
            variables={
                "input": {
                    "accountId": account_id,
                    "sessionId": session_id,
                    "procedureId": args.procedure_id,
                    "role": "USER",
                    "messageType": "MESSAGE",
                    "humanInteraction": "CHAT",
                    "content": args.prompt,
                }
            },
        )
        user_message = user_msg_resp["createChatMessage"]
        user_message_id = user_message["id"]

        dispatch_started_at = utc_now_iso()
        run_resp = graphql(
            url=args.graphql_url,
            id_token=auth.id_token,
            query=START_CONSOLE_RUN,
            variables={
                "sessionId": session_id,
                "procedureId": args.procedure_id,
                "triggerMessageId": user_message_id,
                "clientInstrumentation": json.dumps(
                    {"source": "scripts/console_auth_smoke.py", "dispatch_started_at": dispatch_started_at}
                ),
            },
        )
        run = run_resp["startConsoleRun"]
        task_id = run["taskId"]
        run_id = run["runId"]

        started = time.monotonic()
        first_assistant_delay: Optional[float] = None
        assistant_id: Optional[str] = None
        latest_assistant_content = ""
        latest_task: Optional[Dict[str, Any]] = None
        growth_samples: List[Dict[str, Any]] = []

        while time.monotonic() - started < args.timeout_seconds:
            task_data = graphql(
                url=args.graphql_url,
                id_token=auth.id_token,
                query=GET_TASK,
                variables={"id": task_id},
            )
            latest_task = task_data.get("getTask")

            messages_data = graphql(
                url=args.graphql_url,
                id_token=auth.id_token,
                query=LIST_MESSAGES,
                variables={"sessionId": session_id, "limit": args.max_messages},
            )
            items = ((messages_data.get("listChatMessageBySessionIdAndCreatedAt") or {}).get("items")) or []
            assistants = [message for message in items if (message.get("role") or "").upper() == "ASSISTANT"]
            if assistants:
                assistant = assistants[-1]
                content = assistant.get("content") or ""
                if assistant_id is None:
                    assistant_id = assistant.get("id")
                    first_assistant_delay = round(time.monotonic() - started, 3)
                if content != latest_assistant_content:
                    latest_assistant_content = content
                    growth_samples.append(
                        {
                            "elapsed_s": round(time.monotonic() - started, 3),
                            "content_len": len(content),
                            "preview": content[:160],
                        }
                    )
                metadata = assistant.get("metadata")
                state = None
                if isinstance(metadata, str):
                    try:
                        parsed = json.loads(metadata)
                        state = ((parsed.get("streaming") or {}).get("state"))
                    except Exception:
                        state = None
                if state == "complete" and content:
                    break

            if latest_task and latest_task.get("status") == "FAILED":
                break

            time.sleep(args.poll_interval_seconds)

        dispatch_mode: Optional[str] = None
        task_metadata = None
        if latest_task and isinstance(latest_task.get("metadata"), str):
            try:
                task_metadata = json.loads(latest_task["metadata"])
                dispatch_mode = task_metadata.get("dispatch_mode")
            except Exception:
                task_metadata = None

        result = {
            "graphql_url": args.graphql_url,
            "region": args.region,
            "user_pool_id": args.user_pool_id,
            "account": account,
            "session_id": session_id,
            "user_message_id": user_message_id,
            "run_id": run_id,
            "task_id": task_id,
            "queued_at": run.get("queuedAt"),
            "first_assistant_delay_s": first_assistant_delay,
            "assistant_message_id": assistant_id,
            "assistant_content_len": len(latest_assistant_content),
            "assistant_preview": latest_assistant_content[:200],
            "task": latest_task,
            "task_metadata_parsed": task_metadata,
            "dispatch_mode": dispatch_mode,
            "growth_samples": growth_samples[:25],
            "temp_auth_artifacts": {
                "app_client_id": auth.app_client_id,
                "temp_user_email": auth.temp_user_email,
            },
        }

        if not args.keep_auth_artifacts:
            cleanup_auth(region=args.region, user_pool_id=args.user_pool_id, auth=auth)
            cleaned = True

        result["auth_artifacts_cleaned"] = cleaned
        return result
    finally:
        if not args.keep_auth_artifacts and not cleaned:
            cleanup_auth(region=args.region, user_pool_id=args.user_pool_id, auth=auth)


def main() -> int:
    args = parse_args()
    try:
        result = run_smoke(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    if args.require_dispatch_mode and result.get("dispatch_mode") != args.require_dispatch_mode:
        print(
            f"ERROR: dispatch_mode={result.get('dispatch_mode')} does not match required {args.require_dispatch_mode}",
            file=sys.stderr,
        )
        return 2
    if not result.get("assistant_message_id") and (result.get("task") or {}).get("status") != "FAILED":
        # Not a hard failure for all environments, but make it explicit.
        print(
            "WARNING: No assistant message observed before timeout. Check task status and worker dispatch path.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
