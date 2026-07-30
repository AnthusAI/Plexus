"""Structured human actions persisted exclusively as existing ChatMessage rows."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from plexus.chat.session_ops import get_chat_session, get_latest_chat_session
from plexus.dashboard.api.client import LONG_RUNNING_WRITE_RETRY_POLICY_NAME


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _graphql_field(result: Any, field_name: str) -> Any:
    if not isinstance(result, Mapping):
        return None
    data = result.get("data")
    if isinstance(data, Mapping) and field_name in data:
        return data.get(field_name)
    return result.get(field_name)


def _parse_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return dict(parsed) if isinstance(parsed, Mapping) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _has_conditional_failure(result: Any) -> bool:
    if not isinstance(result, Mapping):
        return False
    for error in result.get("errors") or []:
        if not isinstance(error, Mapping):
            continue
        combined = f"{error.get('errorType') or error.get('type') or ''} {error.get('message') or ''}"
        if "condition" in combined.lower():
            return True
    return False


class ChatMessageActionService:
    """Create or reuse nonblocking human actions without changing Procedure state."""

    def __init__(self, client: Any):
        self.client = client

    def create_or_get(
        self,
        action: Mapping[str, Any],
        *,
        procedure_id: str,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        normalized = self._normalize_action(action, procedure_id=procedure_id)
        session = self._resolve_session(
            account_id=normalized["account_id"],
            procedure_id=procedure_id,
            session_id=session_id,
        )
        existing = self._list_actions(procedure_id)
        exact = [
            row
            for row in existing
            if self._identity(row)
            == (normalized["action_key"], normalized["evidence_fingerprint"])
            and row.get("accountId") == normalized["account_id"]
        ]
        exact.sort(key=lambda row: (str(row.get("createdAt") or ""), str(row.get("id") or "")))
        if exact:
            return {"action": exact[0], "created": False}

        for row in existing:
            identity = self._identity(row)
            if (
                identity is not None
                and identity[0] == normalized["action_key"]
                and identity[1] != normalized["evidence_fingerprint"]
                and row.get("accountId") == normalized["account_id"]
                and row.get("responseStatus") == "PENDING"
            ):
                self._supersede(row)

        created = self._create_message(normalized, session)
        return {"action": created, "created": True}

    def publish_update(
        self,
        update: Mapping[str, Any],
        *,
        procedure_id: str,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create one idempotent milestone notification using ChatMessage."""
        event_key = str(update.get("event_key") or "").strip()
        account_id = str(update.get("account_id") or update.get("accountId") or "").strip()
        milestone = str(update.get("milestone") or "").strip().upper()
        title = str(update.get("title") or "").strip()
        if not event_key or not account_id or not procedure_id or not milestone or not title:
            raise ValueError("event_key, account_id, procedure_id, milestone, and title are required")
        resource_refs = update.get("resource_refs") or []
        if not isinstance(resource_refs, list) or any(not isinstance(row, Mapping) for row in resource_refs):
            raise ValueError("resource_refs must be a list of objects")
        session = self._resolve_session(
            account_id=account_id,
            procedure_id=procedure_id,
            session_id=session_id,
        )
        message_id = f"update-{_fingerprint({'account_id': account_id, 'procedure_id': procedure_id, 'event_key': event_key})[:48]}"
        existing = self._get_message(message_id)
        if existing is not None:
            return {"update": existing, "created": False}
        now = datetime.now(timezone.utc).isoformat()
        metadata = {
            "event_key": event_key,
            "milestone": milestone,
            "title": title,
            "summary": str(update.get("summary") or "").strip() or None,
            "resource_refs": [dict(row) for row in resource_refs],
        }
        create_input = {
            "id": message_id,
            "accountId": account_id,
            "sessionId": session["id"],
            "procedureId": procedure_id,
            "role": "ASSISTANT",
            "humanInteraction": "NOTIFICATION",
            "messageType": "MESSAGE",
            "content": title,
            "metadata": json.dumps(metadata),
            "responseStatus": "COMPLETED",
            "createdAt": now,
        }
        mutation = """
        mutation CreateChatMessageUpdate($input: CreateChatMessageInput!) {
            createChatMessage(input: $input) {
                id accountId sessionId procedureId role humanInteraction content metadata
                responseStatus createdAt sequenceNumber
            }
        }
        """
        try:
            result = self.client.execute(
                mutation,
                {"input": create_input},
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
        except Exception:
            existing = self._get_message(message_id)
            if existing is not None:
                return {"update": existing, "created": False}
            raise
        created = _graphql_field(result, "createChatMessage")
        if isinstance(created, Mapping):
            return {"update": dict(created), "created": True}
        existing = self._get_message(message_id)
        if existing is not None:
            return {"update": existing, "created": False}
        raise RuntimeError("Unable to create ChatMessage update")

    def resolve_first_valid_response(
        self,
        message_id: str,
        *,
        account_id: str,
        procedure_id: str,
    ) -> Optional[dict[str, Any]]:
        """Validate and atomically claim the oldest valid child RESPONSE."""
        parent, children = self._read_action_and_responses(message_id)
        control = self._valid_parent_control(
            parent,
            message_id=message_id,
            account_id=account_id,
            procedure_id=procedure_id,
        )
        if parent is None or control is None:
            return None

        valid_children: dict[str, tuple[Any, str]] = {}
        for child in sorted(
            children,
            key=lambda row: (str(row.get("createdAt") or ""), str(row.get("id") or "")),
        ):
            child_id = child.get("id")
            if not isinstance(child_id, str) or not child_id:
                continue
            parsed = self._valid_child_response(child, parent=parent, control=control)
            if parsed is not None:
                valid_children[child_id] = parsed

        owner = parent.get("responseOwner")
        if parent.get("responseStatus") == "COMPLETED":
            if not isinstance(owner, str) or owner not in valid_children:
                return None
            value, responded_at = valid_children[owner]
            return {
                "action": parent,
                "response": value,
                "response_message_id": owner,
                "responded_at": responded_at,
            }
        if parent.get("responseStatus") != "PENDING" or not valid_children:
            return None

        winner_id = next(iter(valid_children))
        claim = self._claim_response(parent, winner_id)
        if claim == "conditional_loser":
            reread_parent, reread_children = self._read_action_and_responses(message_id)
            reread_control = self._valid_parent_control(
                reread_parent,
                message_id=message_id,
                account_id=account_id,
                procedure_id=procedure_id,
            )
            if reread_parent is None or reread_control is None:
                return None
            recorded_owner = reread_parent.get("responseOwner")
            if (
                reread_parent.get("responseStatus") != "COMPLETED"
                or not isinstance(recorded_owner, str)
            ):
                return None
            recorded_child = next(
                (row for row in reread_children if row.get("id") == recorded_owner),
                None,
            )
            if recorded_child is None:
                return None
            parsed = self._valid_child_response(
                recorded_child,
                parent=reread_parent,
                control=reread_control,
            )
            if parsed is None:
                return None
            value, responded_at = parsed
            return {
                "action": reread_parent,
                "response": value,
                "response_message_id": recorded_owner,
                "responded_at": responded_at,
            }
        if claim is None:
            return None
        value, responded_at = valid_children[winner_id]
        completed_parent = {**parent, **claim}
        return {
            "action": completed_parent,
            "response": value,
            "response_message_id": winner_id,
            "responded_at": responded_at,
        }

    @staticmethod
    def _normalize_action(
        action: Mapping[str, Any],
        *,
        procedure_id: str,
    ) -> dict[str, Any]:
        if not isinstance(action, Mapping):
            raise ValueError("action must be an object")
        action_key = str(action.get("action_key") or "").strip()
        account_id = str(action.get("account_id") or action.get("accountId") or "").strip()
        if not action_key or not account_id or not procedure_id:
            raise ValueError("action_key, account_id, and procedure_id are required")
        preconditions = action.get("preconditions")
        if not isinstance(preconditions, (Mapping, list)):
            raise ValueError("preconditions must be an object or list")
        supplied_fingerprint = action.get("evidence_fingerprint")
        evidence_fingerprint = (
            str(supplied_fingerprint).strip()
            if isinstance(supplied_fingerprint, str) and supplied_fingerprint.strip()
            else _fingerprint(preconditions)
        )
        resource_refs = action.get("resource_refs") or []
        if not isinstance(resource_refs, list) or any(not isinstance(row, Mapping) for row in resource_refs):
            raise ValueError("resource_refs must be a list of objects")
        response_schema = action.get("response_schema") or {}
        ui_schema = action.get("ui_schema") or {}
        if not isinstance(response_schema, Mapping) or not isinstance(ui_schema, Mapping):
            raise ValueError("response_schema and ui_schema must be objects")
        return {
            **dict(action),
            "procedure_id": procedure_id,
            "account_id": account_id,
            "action_key": action_key,
            "preconditions": dict(preconditions) if isinstance(preconditions, Mapping) else list(preconditions),
            "evidence_fingerprint": evidence_fingerprint,
            "precondition_fingerprint": _fingerprint(preconditions),
            "resource_refs": [dict(row) for row in resource_refs],
            "response_schema": dict(response_schema),
            "ui_schema": dict(ui_schema),
        }

    def _resolve_session(
        self,
        *,
        account_id: str,
        procedure_id: str,
        session_id: Optional[str],
    ) -> Mapping[str, Any]:
        session = (
            get_chat_session(self.client, session_id)
            if session_id
            else get_latest_chat_session(
                self.client,
                account_id=account_id,
                procedure_id=procedure_id,
            )
        )
        if not isinstance(session, Mapping):
            raise RuntimeError("No existing ChatSession is available for the action")
        if session.get("accountId") != account_id or session.get("procedureId") != procedure_id:
            raise RuntimeError("ChatSession does not belong to the action account and procedure")
        return session

    def _list_actions(self, procedure_id: str) -> list[dict[str, Any]]:
        query = """
        query ListProcedureActions($procedureId: String!, $limit: Int, $nextToken: String) {
            listChatMessageByProcedureIdAndCreatedAt(
                procedureId: $procedureId
                sortDirection: ASC
                limit: $limit
                nextToken: $nextToken
            ) {
                items {
                    id accountId sessionId procedureId role humanInteraction content metadata
                    responseStatus responseOwner responseCompletedAt createdAt sequenceNumber
                }
                nextToken
            }
        }
        """
        rows: list[dict[str, Any]] = []
        next_token: Optional[str] = None
        while True:
            result = self.client.execute(
                query,
                {"procedureId": procedure_id, "limit": 100, "nextToken": next_token},
            )
            page = _graphql_field(result, "listChatMessageByProcedureIdAndCreatedAt")
            if not isinstance(page, Mapping):
                raise RuntimeError("Unable to enumerate existing procedure actions")
            items = page.get("items") or []
            if isinstance(items, list):
                rows.extend(dict(row) for row in items if isinstance(row, Mapping))
            raw_next = page.get("nextToken")
            next_token = raw_next if isinstance(raw_next, str) and raw_next else None
            if next_token is None:
                return rows

    def _read_action_and_responses(
        self,
        message_id: str,
    ) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
        query = """
        query ReadChatMessageAction(
            $messageId: ID!
            $parentId: String!
            $limit: Int
            $nextToken: String
        ) {
            getChatMessage(id: $messageId) {
                id accountId sessionId procedureId role humanInteraction content metadata
                responseStatus responseOwner responseCompletedAt createdAt sequenceNumber
            }
            listChatMessageByParentMessageId(
                parentMessageId: $parentId
                limit: $limit
                nextToken: $nextToken
                filter: { humanInteraction: { eq: RESPONSE } }
            ) {
                items {
                    id accountId sessionId procedureId humanInteraction parentMessageId
                    content metadata createdAt
                }
                nextToken
            }
        }
        """
        parent: Optional[dict[str, Any]] = None
        children: list[dict[str, Any]] = []
        next_token: Optional[str] = None
        while True:
            result = self.client.execute(
                query,
                {
                    "messageId": message_id,
                    "parentId": message_id,
                    "limit": 100,
                    "nextToken": next_token,
                },
            )
            if not isinstance(result, Mapping) or result.get("errors"):
                return None, []
            if parent is None:
                raw_parent = _graphql_field(result, "getChatMessage")
                parent = dict(raw_parent) if isinstance(raw_parent, Mapping) else None
            page = _graphql_field(result, "listChatMessageByParentMessageId")
            if not isinstance(page, Mapping):
                return parent, children
            items = page.get("items") or []
            if isinstance(items, list):
                children.extend(dict(row) for row in items if isinstance(row, Mapping))
            raw_next = page.get("nextToken")
            next_token = raw_next if isinstance(raw_next, str) and raw_next else None
            if next_token is None:
                return parent, children

    @staticmethod
    def _valid_parent_control(
        parent: Any,
        *,
        message_id: str,
        account_id: str,
        procedure_id: str,
    ) -> Optional[dict[str, Any]]:
        if not isinstance(parent, Mapping):
            return None
        if (
            parent.get("id") != message_id
            or parent.get("accountId") != account_id
            or parent.get("procedureId") != procedure_id
            or parent.get("humanInteraction")
            not in {"PENDING_APPROVAL", "PENDING_INPUT", "PENDING_REVIEW", "PENDING_ESCALATION"}
            or not isinstance(parent.get("sessionId"), str)
            or not parent.get("sessionId")
        ):
            return None
        control = _parse_metadata(parent.get("metadata")).get("control")
        if not isinstance(control, Mapping):
            return None
        control = dict(control)
        required_strings = (
            "request_id",
            "procedure_id",
            "request_type",
            "action_key",
            "precondition_fingerprint",
            "evidence_fingerprint",
        )
        if any(not isinstance(control.get(key), str) or not control.get(key) for key in required_strings):
            return None
        if control["procedure_id"] != procedure_id:
            return None
        preconditions = control.get("preconditions")
        if not isinstance(preconditions, (Mapping, list)):
            return None
        if _fingerprint(preconditions) != control["precondition_fingerprint"]:
            return None
        response_schema = control.get("response_schema")
        if not isinstance(response_schema, Mapping):
            return None
        expires_at = control.get("expires_at")
        if expires_at is not None:
            if not isinstance(expires_at, str):
                return None
            try:
                expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except ValueError:
                return None
            if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
                return None
        return control

    @staticmethod
    def _valid_child_response(
        child: Mapping[str, Any],
        *,
        parent: Mapping[str, Any],
        control: Mapping[str, Any],
    ) -> Optional[tuple[Any, str]]:
        if (
            child.get("humanInteraction") != "RESPONSE"
            or child.get("parentMessageId") != parent.get("id")
        ):
            return None
        for key in ("accountId", "sessionId", "procedureId"):
            if child.get(key) != parent.get(key):
                return None
        child_control = _parse_metadata(child.get("metadata")).get("control")
        if not isinstance(child_control, Mapping):
            return None
        for key in (
            "request_id",
            "procedure_id",
            "request_type",
            "action_key",
            "precondition_fingerprint",
            "evidence_fingerprint",
        ):
            if child_control.get(key) != control.get(key):
                return None
        if "value" not in child_control:
            return None
        value = child_control.get("value")
        try:
            content = json.loads(child.get("content") or "")
        except (TypeError, json.JSONDecodeError):
            return None
        if (
            not isinstance(content, Mapping)
            or "value" not in content
            or _canonical_json(content.get("value")) != _canonical_json(value)
        ):
            return None
        try:
            from jsonschema import Draft202012Validator

            schema = dict(control["response_schema"])
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(value)
        except Exception:
            return None
        responded_at = child_control.get("responded_at") or child.get("createdAt")
        if not isinstance(responded_at, str):
            return None
        try:
            parsed = datetime.fromisoformat(responded_at.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return value, responded_at

    def _claim_response(
        self,
        parent: Mapping[str, Any],
        winner_id: str,
    ) -> Optional[dict[str, Any] | str]:
        mutation = """
        mutation ResolveChatMessageAction(
            $input: UpdateChatMessageInput!
            $condition: ModelChatMessageConditionInput
        ) {
            updateChatMessage(input: $input, condition: $condition) {
                id responseStatus responseOwner responseCompletedAt
            }
        }
        """
        variables = {
            "input": {
                "id": parent.get("id"),
                "createdAt": parent.get("createdAt"),
                "responseStatus": "COMPLETED",
                "responseOwner": winner_id,
                "responseCompletedAt": datetime.now(timezone.utc).isoformat(),
            },
            "condition": {"responseStatus": {"eq": "PENDING"}},
        }
        try:
            result = self.client.execute(
                mutation,
                variables,
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
        except Exception as exc:
            if "condition" in str(exc).lower():
                return "conditional_loser"
            raise
        if _has_conditional_failure(result):
            return "conditional_loser"
        if isinstance(result, Mapping) and result.get("errors"):
            return None
        claimed = _graphql_field(result, "updateChatMessage")
        if not isinstance(claimed, Mapping) or claimed.get("responseOwner") != winner_id:
            return None
        return dict(claimed)

    @staticmethod
    def _identity(row: Mapping[str, Any]) -> Optional[tuple[str, str]]:
        control = _parse_metadata(row.get("metadata")).get("control")
        if not isinstance(control, Mapping):
            return None
        action_key = control.get("action_key")
        fingerprint = control.get("evidence_fingerprint")
        if not isinstance(action_key, str) or not isinstance(fingerprint, str):
            return None
        return action_key, fingerprint

    def _supersede(self, row: Mapping[str, Any]) -> None:
        mutation = """
        mutation SupersedeChatMessageAction(
            $input: UpdateChatMessageInput!
            $condition: ModelChatMessageConditionInput
        ) {
            updateChatMessage(input: $input, condition: $condition) {
                id humanInteraction responseStatus responseCompletedAt
            }
        }
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            result = self.client.execute(
                mutation,
                {
                    "input": {
                        "id": row.get("id"),
                        "createdAt": row.get("createdAt"),
                        "humanInteraction": "CANCELLED",
                        "responseStatus": "FAILED",
                        "responseCompletedAt": now,
                        "responseError": "Superseded by newer evidence",
                    },
                    "condition": {"responseStatus": {"eq": "PENDING"}},
                },
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
        except Exception as exc:
            if "condition" in str(exc).lower():
                return
            raise
        if _has_conditional_failure(result):
            return
        if isinstance(result, Mapping) and result.get("errors"):
            raise RuntimeError(f"Unable to supersede stale action: {result['errors']}")

    def _create_message(
        self,
        action: Mapping[str, Any],
        session: Mapping[str, Any],
    ) -> dict[str, Any]:
        identity = {
            "account_id": action["account_id"],
            "procedure_id": action["procedure_id"],
            "action_key": action["action_key"],
            "evidence_fingerprint": action["evidence_fingerprint"],
        }
        digest = _fingerprint(identity)
        message_id = f"action-{digest[:48]}"
        kind = str(action.get("kind") or "review")
        interaction = (
            "PENDING_APPROVAL"
            if "approval" in kind
            else "PENDING_INPUT"
            if "clarification" in kind
            else "PENDING_REVIEW"
        )
        request_type = (
            "approval"
            if interaction == "PENDING_APPROVAL"
            else "input"
            if interaction == "PENDING_INPUT"
            else "review"
        )
        now = datetime.now(timezone.utc).isoformat()
        control = {
            "request_id": message_id,
            "procedure_id": action["procedure_id"],
            "request_type": request_type,
            "action_key": action["action_key"],
            "kind": action.get("kind"),
            "title": action.get("title"),
            "message": action.get("message"),
            "resource_refs": action["resource_refs"],
            "preconditions": action["preconditions"],
            "precondition_fingerprint": action["precondition_fingerprint"],
            "evidence_fingerprint": action["evidence_fingerprint"],
            "expires_at": action.get("expires_at"),
            "response_schema": action["response_schema"],
            "ui_schema": action["ui_schema"],
            "report_links": action.get("report_links") or [],
            "payload": action.get("payload"),
            "created_at": now,
        }
        create_input = {
            "id": message_id,
            "accountId": action["account_id"],
            "sessionId": session["id"],
            "procedureId": action["procedure_id"],
            "role": "ASSISTANT",
            "humanInteraction": interaction,
            "messageType": "MESSAGE",
            "content": str(action.get("message") or action.get("title") or action["action_key"]),
            "metadata": json.dumps({"control": control}),
            "responseStatus": "PENDING",
            "createdAt": now,
        }
        mutation = """
        mutation CreateChatMessageAction($input: CreateChatMessageInput!) {
            createChatMessage(input: $input) {
                id accountId sessionId procedureId role humanInteraction content metadata
                responseStatus responseOwner responseCompletedAt createdAt sequenceNumber
            }
        }
        """
        try:
            result = self.client.execute(
                mutation,
                {"input": create_input},
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
        except Exception:
            existing = self._get_message(message_id)
            if existing is not None:
                return existing
            raise
        created = _graphql_field(result, "createChatMessage")
        if isinstance(created, Mapping):
            return dict(created)
        existing = self._get_message(message_id)
        if existing is not None:
            return existing
        raise RuntimeError("Unable to create ChatMessage action")

    def _get_message(self, message_id: str) -> Optional[dict[str, Any]]:
        query = """
        query GetChatMessageAction($id: ID!) {
            getChatMessage(id: $id) {
                id accountId sessionId procedureId role humanInteraction content metadata
                responseStatus responseOwner responseCompletedAt createdAt sequenceNumber
            }
        }
        """
        result = self.client.execute(query, {"id": message_id})
        row = _graphql_field(result, "getChatMessage")
        return dict(row) if isinstance(row, Mapping) else None
