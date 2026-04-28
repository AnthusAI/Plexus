from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from plexus.cli.scorecard.scorecards import resolve_account_identifier

DEFAULT_RESPONSE_TARGET = "cloud"
PENDING_HUMAN_INTERACTIONS = {
    "PENDING_APPROVAL",
    "PENDING_INPUT",
    "PENDING_REVIEW",
    "PENDING_ESCALATION",
}
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _graphql_field(result: Any, field_name: str) -> Any:
    if not isinstance(result, dict):
        return None
    data = result.get("data")
    if isinstance(data, dict) and field_name in data:
        return data.get(field_name)
    return result.get(field_name)


def _normalize_response_target(value: Optional[str]) -> str:
    target = str(value or "").strip()
    return target or DEFAULT_RESPONSE_TARGET


def _parse_metadata(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return {}
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _normalize_chat_message(raw: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _parse_metadata(raw.get("metadata"))
    return {
        "id": raw.get("id"),
        "accountId": raw.get("accountId"),
        "sessionId": raw.get("sessionId"),
        "procedureId": raw.get("procedureId"),
        "role": raw.get("role"),
        "humanInteraction": raw.get("humanInteraction"),
        "messageType": raw.get("messageType"),
        "content": raw.get("content"),
        "metadata": metadata,
        "parentMessageId": raw.get("parentMessageId"),
        "responseTarget": raw.get("responseTarget"),
        "responseStatus": raw.get("responseStatus"),
        "responseOwner": raw.get("responseOwner"),
        "responseStartedAt": raw.get("responseStartedAt"),
        "responseCompletedAt": raw.get("responseCompletedAt"),
        "responseError": raw.get("responseError"),
        "createdAt": raw.get("createdAt"),
        "sequenceNumber": raw.get("sequenceNumber"),
    }


def resolve_account_id(client: Any, account_identifier: Optional[str] = None) -> str:
    candidate = (account_identifier or "").strip()
    if not candidate:
        candidate = os.getenv("PLEXUS_ACCOUNT_ID", "").strip()
    if not candidate:
        candidate = os.getenv("PLEXUS_ACCOUNT_KEY", "").strip()
    if not candidate:
        raise ValueError(
            "Missing account context. Provide --account or set PLEXUS_ACCOUNT_ID/PLEXUS_ACCOUNT_KEY."
        )

    # If caller gives an explicit account UUID, trust it as the lookup key.
    if UUID_PATTERN.match(candidate):
        return candidate

    account_id = resolve_account_identifier(client, candidate)
    if not account_id:
        raise ValueError(f"Unable to resolve account identifier '{candidate}'.")
    return account_id


def get_chat_session(client: Any, session_id: str) -> Optional[Dict[str, Any]]:
    query = """
    query GetChatSession($id: ID!) {
      getChatSession(id: $id) {
        id
        accountId
        procedureId
        name
        category
        status
        metadata
        createdAt
        updatedAt
      }
    }
    """
    result = client.execute(query, {"id": session_id})
    session = _graphql_field(result, "getChatSession")
    return session if isinstance(session, dict) else None


def get_latest_chat_session(
    client: Any,
    *,
    account_id: str,
    procedure_id: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    query = """
    query ListLatestChatSessions(
      $accountId: String!
      $limit: Int
      $nextToken: String
      $filter: ModelChatSessionFilterInput
    ) {
      listChatSessionByAccountIdAndUpdatedAt(
        accountId: $accountId
        sortDirection: DESC
        limit: $limit
        nextToken: $nextToken
        filter: $filter
      ) {
        items {
          id
          accountId
          procedureId
          name
          category
          status
          metadata
          createdAt
          updatedAt
        }
        nextToken
      }
    }
    """
    gql_filter: Dict[str, Dict[str, str]] = {}
    if procedure_id:
        gql_filter["procedureId"] = {"eq": procedure_id}
    if status:
        gql_filter["status"] = {"eq": status}
    if category:
        gql_filter["category"] = {"eq": category}

    next_token: Optional[str] = None
    while True:
        variables: Dict[str, Any] = {
            "accountId": account_id,
            "limit": 50,
            "nextToken": next_token,
            "filter": gql_filter or None,
        }
        result = client.execute(query, variables)
        payload = _graphql_field(result, "listChatSessionByAccountIdAndUpdatedAt")
        if not isinstance(payload, dict):
            return None
        items = payload.get("items") or []
        for item in items:
            if isinstance(item, dict):
                return item
        next_token = payload.get("nextToken")
        if not next_token:
            return None


def list_session_messages(
    client: Any,
    *,
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    include_internal: bool = False,
) -> Dict[str, Any]:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    target_count = offset + limit

    query = """
    query ListSessionMessages($sessionId: String!, $limit: Int, $nextToken: String) {
      listChatMessageBySessionIdAndCreatedAt(
        sessionId: $sessionId
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
          metadata
          parentMessageId
          responseTarget
          responseStatus
          responseOwner
          responseStartedAt
          responseCompletedAt
          responseError
          createdAt
          sequenceNumber
        }
        nextToken
      }
    }
    """
    next_token: Optional[str] = None
    scanned = 0
    max_scan = 5000
    collected: List[Dict[str, Any]] = []

    while scanned < max_scan and len(collected) < target_count:
        result = client.execute(
            query,
            {"sessionId": session_id, "limit": min(200, target_count + 50), "nextToken": next_token},
        )
        payload = _graphql_field(result, "listChatMessageBySessionIdAndCreatedAt")
        if not isinstance(payload, dict):
            break
        items = payload.get("items") or []
        next_token = payload.get("nextToken")
        for item in items:
            if not isinstance(item, dict):
                continue
            scanned += 1
            human_interaction = str(item.get("humanInteraction") or "").upper()
            if not include_internal and human_interaction == "INTERNAL":
                continue
            collected.append(_normalize_chat_message(item))
            if len(collected) >= target_count:
                break
        if not next_token:
            break

    ordered = sorted(
        collected,
        key=lambda msg: (
            str(msg.get("createdAt") or ""),
            int(msg.get("sequenceNumber") or 0),
            str(msg.get("id") or ""),
        ),
    )
    window = ordered[offset : offset + limit]
    return {
        "sessionId": session_id,
        "offset": offset,
        "limit": limit,
        "count": len(window),
        "nextToken": next_token,
        "items": window,
    }


def _pending_to_request_type(human_interaction: Optional[str]) -> str:
    normalized = str(human_interaction or "").upper()
    if normalized == "PENDING_APPROVAL":
        return "approval"
    if normalized == "PENDING_REVIEW":
        return "review"
    if normalized == "PENDING_ESCALATION":
        return "escalation"
    return "input"


def _build_response_value(request_type: str, text: str) -> Any:
    normalized = str(request_type or "").lower().strip()
    raw = text.strip()
    if normalized == "approval":
        lowered = raw.lower()
        if lowered in {"approve", "approved", "yes", "y", "true", "1"}:
            return True
        if lowered in {"reject", "rejected", "no", "n", "false", "0"}:
            return False
        raise ValueError("Approval response must be one of: approve/reject/yes/no/true/false.")
    if normalized == "review":
        return {"decision": "approve", "feedback": raw}
    if normalized == "escalation":
        return {"acknowledged": True, "action": "acknowledge", "note": raw}
    if normalized == "input":
        return raw
    return {"action": "submit", "input": raw}


def get_chat_message(client: Any, message_id: str) -> Optional[Dict[str, Any]]:
    query = """
    query GetChatMessage($id: ID!) {
      getChatMessage(id: $id) {
        id
        accountId
        sessionId
        procedureId
        role
        humanInteraction
        messageType
        content
        metadata
        parentMessageId
        responseTarget
        responseStatus
        createdAt
      }
    }
    """
    result = client.execute(query, {"id": message_id})
    item = _graphql_field(result, "getChatMessage")
    return _normalize_chat_message(item) if isinstance(item, dict) else None


def send_chat_message(
    client: Any,
    *,
    session_id: str,
    text: str,
    mode: str = "chat",
    parent_message_id: Optional[str] = None,
    response_target: str = DEFAULT_RESPONSE_TARGET,
    model: Optional[str] = None,
    responder: Optional[str] = None,
) -> Dict[str, Any]:
    content = str(text or "").strip()
    if not content:
        raise ValueError("text is required.")

    session = get_chat_session(client, session_id)
    if not session:
        raise ValueError(f"Session '{session_id}' was not found.")

    normalized_mode = str(mode or "chat").strip().lower()
    if normalized_mode not in {"chat", "response"}:
        raise ValueError("mode must be either 'chat' or 'response'.")

    now = _utc_now_iso()
    payload: Dict[str, Any] = {
        "sessionId": session_id,
        "role": "USER",
        "messageType": "MESSAGE",
        "responseTarget": _normalize_response_target(response_target),
        "responseStatus": "PENDING",
        "createdAt": now,
    }
    if session.get("accountId"):
        payload["accountId"] = session.get("accountId")
    if session.get("procedureId"):
        payload["procedureId"] = session.get("procedureId")

    if normalized_mode == "chat":
        payload["humanInteraction"] = "CHAT"
        payload["content"] = content
        if model:
            payload["metadata"] = json.dumps({"model": {"id": str(model).strip()}})
    else:
        if not parent_message_id:
            raise ValueError("parent_message_id is required when mode=response.")
        parent = get_chat_message(client, parent_message_id)
        if not parent:
            raise ValueError(f"Parent message '{parent_message_id}' was not found.")
        if parent.get("sessionId") != session_id:
            raise ValueError("Parent message does not belong to the provided session.")
        parent_interaction = str(parent.get("humanInteraction") or "").upper()
        if parent_interaction not in PENDING_HUMAN_INTERACTIONS:
            raise ValueError("Parent message is not a pending HITL request.")

        parent_metadata = _parse_metadata(parent.get("metadata"))
        parent_control = parent_metadata.get("control") if isinstance(parent_metadata, dict) else None
        request_type = (
            str(parent_control.get("request_type")).strip().lower()
            if isinstance(parent_control, dict) and parent_control.get("request_type")
            else _pending_to_request_type(parent_interaction)
        )
        procedure_id = (
            str(parent_control.get("procedure_id")).strip()
            if isinstance(parent_control, dict) and parent_control.get("procedure_id")
            else str(parent.get("procedureId") or session.get("procedureId") or "").strip()
        )
        request_id = (
            str(parent_control.get("request_id")).strip()
            if isinstance(parent_control, dict) and parent_control.get("request_id")
            else f"{procedure_id or 'procedure'}:{parent_message_id}"
        )
        response_value = _build_response_value(request_type, content)
        response_metadata = {
            "control": {
                "request_id": request_id,
                "procedure_id": procedure_id,
                "request_type": request_type,
                "response_type": _pending_to_request_type(parent_interaction),
                "pending_message_id": parent_message_id,
                "value": response_value,
                "responded_at": now,
                "responder": responder or "plexus-chat-send",
            }
        }
        payload["humanInteraction"] = "RESPONSE"
        payload["parentMessageId"] = parent_message_id
        payload["content"] = json.dumps({"value": response_value})
        payload["metadata"] = json.dumps(response_metadata)
        if parent.get("accountId") and not payload.get("accountId"):
            payload["accountId"] = parent.get("accountId")
        if parent.get("procedureId") and not payload.get("procedureId"):
            payload["procedureId"] = parent.get("procedureId")

    mutation = """
    mutation CreateChatMessage($input: CreateChatMessageInput!) {
      createChatMessage(input: $input) {
        id
        accountId
        sessionId
        procedureId
        role
        humanInteraction
        messageType
        content
        metadata
        parentMessageId
        responseTarget
        responseStatus
        responseOwner
        responseStartedAt
        responseCompletedAt
        responseError
        createdAt
      }
    }
    """
    result = client.execute(mutation, {"input": payload})
    created = _graphql_field(result, "createChatMessage")
    if not isinstance(created, dict):
        raise RuntimeError("Failed to create chat message.")

    normalized = _normalize_chat_message(created)
    return {
        "mode": normalized_mode,
        "sessionId": session_id,
        "message": normalized,
    }
