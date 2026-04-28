from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from plexus.cli.procedure.builtin_procedures import CONSOLE_CHAT_BUILTIN_ID
from plexus.cli.procedure.service import ProcedureService
from plexus.dashboard.api.client import PlexusDashboardClient

logger = logging.getLogger(__name__)

PRODUCTION_RESPONSE_TARGET = "cloud"
PENDING = "PENDING"
RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
HANDLED_HUMAN_INTERACTIONS = {"CHAT"}
CONSOLE_HISTORY_LIMIT = 16
_PROCEDURE_SERVICE_CACHE: Dict[int, ProcedureService] = {}


@dataclass(frozen=True)
class ConsoleMessage:
    id: str
    account_id: str
    session_id: str
    procedure_id: str
    content: str
    role: str
    message_type: str
    human_interaction: str
    response_target: str
    response_status: str
    created_at: str
    selected_model: Optional[str] = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_response_target(value: Optional[str]) -> str:
    target = str(value or "").strip()
    return target or PRODUCTION_RESPONSE_TARGET


def build_response_owner(target: str, *, request_id: Optional[str] = None) -> str:
    host = socket.gethostname()
    pid = os.getpid()
    suffix = f":{request_id}" if request_id else ""
    return f"{target}:{host}:{pid}{suffix}"


def _parse_metadata_object(raw_metadata: Any) -> Dict[str, Any]:
    if isinstance(raw_metadata, dict):
        return raw_metadata
    if isinstance(raw_metadata, str):
        candidate = raw_metadata.strip()
        if not candidate:
            return {}
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _extract_selected_model(raw_metadata: Any) -> Optional[str]:
    metadata = _parse_metadata_object(raw_metadata)
    model = metadata.get("model")
    if not isinstance(model, dict):
        return None
    model_id = model.get("id")
    if not isinstance(model_id, str):
        return None
    normalized = model_id.strip()
    return normalized or None


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None


def _duration_ms(start: Optional[str], end: Optional[str]) -> Optional[int]:
    start_dt = _parse_iso_datetime(start)
    end_dt = _parse_iso_datetime(end)
    if not start_dt or not end_dt:
        return None
    duration = (end_dt - start_dt).total_seconds() * 1000
    if duration < 0:
        return 0
    return int(duration)


def _build_latency_summary(trace: Dict[str, Any], *, status: str) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "event": "console_chat_latency",
        "status": status,
        "message_id": trace.get("message_id"),
        "session_id": trace.get("session_id"),
        "response_target": trace.get("response_target"),
        "selected_model": trace.get("selected_model"),
        "t_received": trace.get("t_received"),
        "t_claimed": trace.get("t_claimed"),
        "t_history_loaded": trace.get("t_history_loaded"),
        "t_run_started": trace.get("t_run_started"),
        "t_first_assistant_chunk": trace.get("t_first_assistant_chunk"),
        "t_completed": trace.get("t_completed"),
        "claim_ms": _duration_ms(trace.get("t_received"), trace.get("t_claimed")),
        "history_ms": _duration_ms(trace.get("t_claimed"), trace.get("t_history_loaded")),
        "startup_ms": _duration_ms(trace.get("t_history_loaded"), trace.get("t_run_started")),
        "first_token_ms": _duration_ms(trace.get("t_run_started"), trace.get("t_first_assistant_chunk")),
        "total_ms": _duration_ms(trace.get("t_received"), trace.get("t_completed")),
    }
    error = trace.get("error")
    if isinstance(error, str) and error:
        summary["error"] = error
    return summary


def _get_procedure_service(client: PlexusDashboardClient) -> ProcedureService:
    cache_key = id(client)
    cached = _PROCEDURE_SERVICE_CACHE.get(cache_key)
    if cached is None:
        cached = ProcedureService(client)
        _PROCEDURE_SERVICE_CACHE[cache_key] = cached
    return cached


def parse_chat_message(raw: Dict[str, Any]) -> Optional[ConsoleMessage]:
    message_id = str(raw.get("id") or "").strip()
    account_id = str(raw.get("accountId") or "").strip()
    session_id = str(raw.get("sessionId") or "").strip()
    content = str(raw.get("content") or "")
    if not message_id or not account_id or not session_id:
        return None

    return ConsoleMessage(
        id=message_id,
        account_id=account_id,
        session_id=session_id,
        procedure_id=str(raw.get("procedureId") or CONSOLE_CHAT_BUILTIN_ID).strip() or CONSOLE_CHAT_BUILTIN_ID,
        content=content,
        role=str(raw.get("role") or "").strip().upper(),
        message_type=str(raw.get("messageType") or "MESSAGE").strip().upper(),
        human_interaction=str(raw.get("humanInteraction") or "").strip().upper(),
        response_target=normalize_response_target(raw.get("responseTarget")),
        response_status=str(raw.get("responseStatus") or "").strip().upper(),
        created_at=str(raw.get("createdAt") or "").strip(),
        selected_model=_extract_selected_model(raw.get("metadata")),
    )


def should_handle_message(message: ConsoleMessage, expected_target: str) -> bool:
    return (
        message.role == "USER"
        and message.message_type == "MESSAGE"
        and message.human_interaction in HANDLED_HUMAN_INTERACTIONS
        and message.response_status == PENDING
        and message.response_target == expected_target
    )


def _graphql_field(result: Any, field_name: str) -> Any:
    if not isinstance(result, dict):
        return None
    data = result.get("data")
    if isinstance(data, dict) and field_name in data:
        return data.get(field_name)
    return result.get(field_name)


def _has_conditional_failure(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    errors = result.get("errors") or []
    if not isinstance(errors, list):
        return False
    for error in errors:
        if not isinstance(error, dict):
            continue
        error_type = str(error.get("errorType") or error.get("type") or "")
        message = str(error.get("message") or "")
        combined = f"{error_type} {message}".lower()
        if "conditional" in combined or "condition" in combined:
            return True
    return False


def claim_message(
    client: PlexusDashboardClient,
    message: ConsoleMessage,
    *,
    expected_target: str,
    owner: str,
) -> bool:
    if not should_handle_message(message, expected_target):
        return False

    mutation = """
    mutation ClaimConsoleChatMessage(
      $input: UpdateChatMessageInput!
      $condition: ModelChatMessageConditionInput
    ) {
      updateChatMessage(input: $input, condition: $condition) {
        id
        responseStatus
        responseTarget
        responseOwner
      }
    }
    """
    try:
        result = client.execute(
            mutation,
            {
                "input": {
                    "id": message.id,
                    "createdAt": message.created_at,
                    "responseStatus": RUNNING,
                    "responseOwner": owner,
                    "responseStartedAt": utc_now(),
                },
                "condition": {
                    "responseTarget": {"eq": expected_target},
                    "responseStatus": {"eq": PENDING},
                },
            },
        )
    except Exception as exc:
        message_text = str(exc).lower()
        if "conditional request failed" in message_text or "conditionalcheckfailed" in message_text:
            logger.info("Console message %s was already claimed", message.id)
            return False
        raise
    if _has_conditional_failure(result):
        logger.info("Console message %s was already claimed", message.id)
        return False
    if isinstance(result, dict) and result.get("errors"):
        raise RuntimeError(f"Failed to claim console message {message.id}: {result['errors']}")
    claimed = _graphql_field(result, "updateChatMessage")
    return isinstance(claimed, dict) and claimed.get("id") == message.id


def mark_message_completed(
    client: PlexusDashboardClient,
    message_id: str,
    *,
    created_at: Optional[str],
) -> None:
    mutation = """
    mutation CompleteConsoleChatMessage($input: UpdateChatMessageInput!) {
      updateChatMessage(input: $input) {
        id
        responseStatus
      }
    }
    """
    client.execute(
        mutation,
        {
            "input": {
                "id": message_id,
                "createdAt": created_at,
                "responseStatus": COMPLETED,
                "responseCompletedAt": utc_now(),
                "responseError": None,
            }
        },
    )


def mark_message_failed(
    client: PlexusDashboardClient,
    message_id: str,
    error: Exception,
    *,
    created_at: Optional[str],
) -> None:
    mutation = """
    mutation FailConsoleChatMessage($input: UpdateChatMessageInput!) {
      updateChatMessage(input: $input) {
        id
        responseStatus
      }
    }
    """
    client.execute(
        mutation,
        {
            "input": {
                "id": message_id,
                "createdAt": created_at,
                "responseStatus": FAILED,
                "responseCompletedAt": utc_now(),
                "responseError": str(error),
            }
        },
    )


def fetch_message(client: PlexusDashboardClient, message_id: str) -> Optional[ConsoleMessage]:
    query = """
    query GetConsoleTriggerMessage($id: ID!) {
      getChatMessage(id: $id) {
        id
        accountId
        sessionId
        procedureId
        role
        humanInteraction
        messageType
        content
        responseTarget
        responseStatus
        metadata
        createdAt
      }
    }
    """
    result = client.execute(query, {"id": message_id})
    raw = _graphql_field(result, "getChatMessage")
    return parse_chat_message(raw) if isinstance(raw, dict) else None


def fetch_session_history(
    client: PlexusDashboardClient,
    session_id: str,
    *,
    limit: int = CONSOLE_HISTORY_LIMIT,
) -> List[Dict[str, str]]:
    query = """
    query ListConsoleSessionHistory($sessionId: String!, $limit: Int, $nextToken: String) {
      listChatMessageBySessionIdAndCreatedAt(
        sessionId: $sessionId
        limit: $limit
        nextToken: $nextToken
      ) {
        items {
          id
          role
          humanInteraction
          messageType
          content
          metadata
          createdAt
        }
        nextToken
      }
    }
    """
    items: List[Dict[str, Any]] = []
    next_token: Optional[str] = None
    while len(items) < limit:
        result = client.execute(
            query,
            {"sessionId": session_id, "limit": min(100, limit), "nextToken": next_token},
        )
        page = _graphql_field(result, "listChatMessageBySessionIdAndCreatedAt")
        if not isinstance(page, dict):
            break
        page_items = page.get("items") or []
        if isinstance(page_items, list):
            items.extend(item for item in page_items if isinstance(item, dict))
        next_token = page.get("nextToken")
        if not next_token:
            break

    normalized: List[Dict[str, str]] = []
    for item in sorted(items, key=lambda value: str(value.get("createdAt") or "")):
        role = str(item.get("role") or "").upper()
        if role not in {"USER", "ASSISTANT"}:
            continue
        message_type = str(item.get("messageType") or "MESSAGE").upper()
        if message_type != "MESSAGE":
            continue
        human_interaction = str(item.get("humanInteraction") or "").upper()
        if human_interaction not in {"CHAT", "CHAT_ASSISTANT"}:
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            normalized.append({"role": role, "content": content.strip()})
    return normalized[-limit:]


def fetch_first_assistant_chunk_timestamp(
    client: PlexusDashboardClient,
    session_id: str,
    *,
    after_iso: Optional[str],
    max_items: int = 300,
) -> Optional[str]:
    query = """
    query ListAssistantChunks($sessionId: String!, $limit: Int, $nextToken: String) {
      listChatMessageBySessionIdAndCreatedAt(
        sessionId: $sessionId
        sortDirection: DESC
        limit: $limit
        nextToken: $nextToken
      ) {
        items {
          role
          humanInteraction
          messageType
          content
          metadata
          createdAt
        }
        nextToken
      }
    }
    """
    after_dt = _parse_iso_datetime(after_iso)
    next_token: Optional[str] = None
    items: List[Dict[str, Any]] = []
    while len(items) < max_items:
        result = client.execute(
            query,
            {"sessionId": session_id, "limit": 100, "nextToken": next_token},
        )
        page = _graphql_field(result, "listChatMessageBySessionIdAndCreatedAt")
        if not isinstance(page, dict):
            break
        page_items = page.get("items") or []
        if isinstance(page_items, list):
            remaining = max_items - len(items)
            if remaining <= 0:
                break
            items.extend(item for item in page_items[:remaining] if isinstance(item, dict))
        next_token = page.get("nextToken")
        if not next_token:
            break

    for item in items:
        role = str(item.get("role") or "").upper()
        if role != "ASSISTANT":
            continue
        message_type = str(item.get("messageType") or "").upper()
        if message_type != "MESSAGE":
            continue
        human_interaction = str(item.get("humanInteraction") or "").upper()
        if human_interaction != "CHAT_ASSISTANT":
            continue
        content = str(item.get("content") or "").strip()
        if not content or content == "Assistant turn completed.":
            continue
        metadata = _parse_metadata_object(item.get("metadata"))
        streaming = metadata.get("streaming") if isinstance(metadata, dict) else None
        timings = streaming.get("timings") if isinstance(streaming, dict) else None
        first_chunk_received_at = (
            str(timings.get("first_chunk_received_at") or "").strip()
            if isinstance(timings, dict)
            else ""
        )
        if first_chunk_received_at:
            first_chunk_dt = _parse_iso_datetime(first_chunk_received_at)
            if not after_dt or (first_chunk_dt and first_chunk_dt >= after_dt):
                return first_chunk_received_at
        created_at = str(item.get("createdAt") or "").strip()
        if not created_at:
            continue
        created_dt = _parse_iso_datetime(created_at)
        if after_dt and created_dt and created_dt < after_dt:
            continue
        return created_at
    return None


async def run_console_chat_response_async(
    client: PlexusDashboardClient,
    message: ConsoleMessage,
    *,
    owner: str,
    latency_trace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    history = fetch_session_history(client, message.session_id)
    if latency_trace is not None:
        latency_trace["t_history_loaded"] = utc_now()
    if not history or history[-1].get("content") != message.content:
        history.append({"role": "USER", "content": message.content})
    service = _get_procedure_service(client)
    run_started = utc_now()
    if latency_trace is not None:
        latency_trace["t_run_started"] = run_started
    context: Dict[str, Any] = {
        "account_id": message.account_id,
        "chat_session_id": message.session_id,
        "console_trigger_message_id": message.id,
        "console_response_owner": owner,
        # Console stream dispatch does not create a Task record, so task-metadata
        # lookup adds avoidable latency in chat tracing without adding signal.
        "disable_console_dispatch_metadata_lookup": True,
    }
    if message.selected_model:
        context["agent_models"] = {"assistant": message.selected_model}

    result = await service.run_experiment(
        CONSOLE_CHAT_BUILTIN_ID,
        account_id=message.account_id,
        console_user_message=message.content,
        console_session_history=history,
        enable_mcp=False,
        context=context,
    )
    if latency_trace is not None:
        latency_trace["t_first_assistant_chunk"] = fetch_first_assistant_chunk_timestamp(
            client,
            message.session_id,
            after_iso=run_started,
        )
    return result


def run_console_chat_response(
    client: PlexusDashboardClient,
    message: ConsoleMessage,
    *,
    owner: str,
    latency_trace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return asyncio.run(run_console_chat_response_async(client, message, owner=owner, latency_trace=latency_trace))


def process_console_message(
    client: PlexusDashboardClient,
    raw_message: Dict[str, Any],
    *,
    expected_target: str,
    owner: str,
) -> bool:
    message = parse_chat_message(raw_message)
    if not message:
        return False
    if not should_handle_message(message, expected_target):
        return False
    latency_trace: Dict[str, Any] = {
        "message_id": message.id,
        "session_id": message.session_id,
        "response_target": message.response_target,
        "selected_model": message.selected_model,
        "t_received": message.created_at or None,
    }
    if not claim_message(client, message, expected_target=expected_target, owner=owner):
        return False
    latency_trace["t_claimed"] = utc_now()

    latest_message = message
    try:
        latest_message = fetch_message(client, message.id) or message
        created_at = latest_message.created_at or message.created_at or None
        run_console_chat_response(client, latest_message, owner=owner, latency_trace=latency_trace)
        mark_message_completed(client, message.id, created_at=created_at)
        latency_trace["t_completed"] = utc_now()
        logger.info("%s", json.dumps(_build_latency_summary(latency_trace, status="COMPLETED"), sort_keys=True))
        return True
    except Exception as exc:
        logger.exception("Console chat response failed for message %s", message.id)
        created_at = latest_message.created_at or message.created_at or None
        mark_message_failed(client, message.id, exc, created_at=created_at)
        latency_trace["t_completed"] = utc_now()
        latency_trace["error"] = str(exc)
        logger.info("%s", json.dumps(_build_latency_summary(latency_trace, status="FAILED"), sort_keys=True))
        raise


def process_pending_local_messages(
    client: PlexusDashboardClient,
    *,
    response_target: str,
    owner: str,
    limit: int = 5,
) -> int:
    query = """
    query ListPendingConsoleMessages(
      $responseTarget: String!
      $limit: Int
      $nextToken: String
    ) {
      listChatMessageByResponseTargetAndResponseStatusAndCreatedAt(
        responseTarget: $responseTarget
        responseStatusCreatedAt: { beginsWith: { responseStatus: PENDING } }
        sortDirection: ASC
        limit: $limit
        nextToken: $nextToken
      ) {
        items {
          id
          accountId
          sessionId
          procedureId
          role
          humanInteraction
          messageType
          content
          responseTarget
          responseStatus
          metadata
          createdAt
        }
        nextToken
      }
    }
    """
    processed = 0
    next_token: Optional[str] = None
    while processed < limit:
        result = client.execute(
            query,
            {
                "responseTarget": response_target,
                "limit": min(100, max(1, limit - processed)),
                "nextToken": next_token,
            },
        )
        page = _graphql_field(result, "listChatMessageByResponseTargetAndResponseStatusAndCreatedAt")
        items: Iterable[Any] = page.get("items") if isinstance(page, dict) else []
        for item in items or []:
            if isinstance(item, dict) and process_console_message(
                client,
                item,
                expected_target=response_target,
                owner=owner,
            ):
                processed += 1
                if processed >= limit:
                    break
        next_token = page.get("nextToken") if isinstance(page, dict) else None
        if not next_token:
            break
    return processed
