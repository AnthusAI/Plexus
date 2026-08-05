"""
Canonical Plexus HITL adapter for procedure conversations.

This adapter persists pending control requests as ChatMessage records and
resolves responses strictly via child ChatMessage rows with:
- humanInteraction = RESPONSE
- parentMessageId = <pending_message_id>
- metadata.control envelope
"""

import json
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from tactus.core.exceptions import ProcedureWaitingForHuman
from tactus.protocols.models import HITLRequest, HITLResponse
from plexus.dashboard.api.client import LONG_RUNNING_WRITE_RETRY_POLICY_NAME

logger = logging.getLogger(__name__)

_PENDING_INTERACTION_BY_REQUEST_TYPE = {
    "approval": "PENDING_APPROVAL",
    "input": "PENDING_INPUT",
    "review": "PENDING_REVIEW",
    "escalation": "PENDING_ESCALATION",
}


def _parse_metadata(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        if not value.strip():
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _parse_iso8601(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def _canonical_json(value: Any) -> str:
    """Serialize an action identity deterministically without host-specific state."""
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


def _has_conditional_failure(result: Any) -> bool:
    if not isinstance(result, Mapping):
        return False
    errors = result.get("errors") or []
    if not isinstance(errors, list):
        return False
    for error in errors:
        if not isinstance(error, Mapping):
            continue
        error_type = str(error.get("errorType") or error.get("type") or "")
        message = str(error.get("message") or "")
        if "condition" in f"{error_type} {message}".lower():
            return True
    return False


class PlexusHITLAdapter:
    """Tactus HITLHandler implementation backed by Plexus ChatMessage records."""

    def __init__(
        self,
        client,
        procedure_id: str,
        chat_recorder=None,
        storage_adapter=None,
    ):
        self.client = client
        self.procedure_id = procedure_id
        self.chat_recorder = chat_recorder
        self.storage_adapter = storage_adapter
        logger.info("PlexusHITLAdapter initialized for procedure %s", procedure_id)

    def _build_request_id(self, procedure_id: str, execution_context: Any = None) -> str:
        run_token = "run"
        if execution_context is not None:
            invocation_id = getattr(execution_context, "invocation_id", None)
            current_run_id = getattr(execution_context, "current_run_id", None)
            token_source = current_run_id or invocation_id
            if isinstance(token_source, str) and token_source:
                run_token = token_source[:8]

            if hasattr(execution_context, "next_position"):
                try:
                    position = execution_context.next_position()
                except Exception:
                    position = None
                if position is not None:
                    return f"{procedure_id}:{run_token}:pos{position}"

        return f"{procedure_id}:{run_token}:{uuid.uuid4().hex[:12]}"

    def _build_control_request_envelope(
        self,
        procedure_id: str,
        request: HITLRequest,
        execution_context: Any = None,
    ) -> dict:
        raw_metadata = request.metadata if isinstance(request.metadata, dict) else {}

        procedure_name = getattr(execution_context, "procedure_name", None) if execution_context else None
        invocation_id = getattr(execution_context, "invocation_id", None) if execution_context else None
        runtime_context = None
        if execution_context and hasattr(execution_context, "get_runtime_context"):
            try:
                runtime_context = execution_context.get_runtime_context()
            except Exception:
                runtime_context = None

        envelope = {
            "request_id": self._build_request_id(procedure_id, execution_context),
            "procedure_id": procedure_id,
            "procedure_name": procedure_name or procedure_id,
            "invocation_id": invocation_id or procedure_id,
            "request_type": request.request_type,
            "prompt": request.message,
            "options": request.options or [],
            "timeout_seconds": request.timeout_seconds,
            "default_value": request.default_value,
            "metadata": raw_metadata,
            "runtime_context": runtime_context,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        structured = self._structured_metadata(request)
        if structured is not None:
            envelope.update(structured)
        return envelope

    def _record_pending_message(
        self,
        request: HITLRequest,
        control_envelope: dict,
    ) -> Optional[str]:
        if not self.chat_recorder or not self.chat_recorder.session_id:
            logger.error("Cannot create HITL message without active chat session")
            return None

        interaction = _PENDING_INTERACTION_BY_REQUEST_TYPE.get(
            str(request.request_type or "").lower(),
            "PENDING_INPUT",
        )
        message_metadata = {"control": control_envelope}
        sequence_number = None
        if hasattr(self.chat_recorder, "_get_next_sequence_number"):
            try:
                sequence_number = self.chat_recorder._get_next_sequence_number()
            except Exception:
                sequence_number = None
        if sequence_number is None:
            current = int(getattr(self.chat_recorder, "sequence_number", 0))
            sequence_number = current + 1
            self.chat_recorder.sequence_number = sequence_number

        message_data = {
            "sessionId": self.chat_recorder.session_id,
            "procedureId": self.procedure_id,
            "role": "ASSISTANT",
            "content": request.message,
            "messageType": "MESSAGE",
            "humanInteraction": interaction,
            "sequenceNumber": sequence_number,
            "metadata": json.dumps(message_metadata),
            "responseTarget": self.procedure_id,
            "responseStatus": "PENDING",
        }
        account_id = getattr(self.chat_recorder, "account_id", None)
        if account_id:
            message_data["accountId"] = account_id

        mutation = """
        mutation CreateChatMessage($input: CreateChatMessageInput!) {
            createChatMessage(input: $input) {
                id
                sequenceNumber
                createdAt
            }
        }
        """
        try:
            result = self.client.execute(
                mutation,
                {"input": message_data},
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
            if isinstance(result, dict) and result.get("errors"):
                logger.error("GraphQL error creating canonical HITL message: %s", result["errors"])
                return None
            record = None
            if isinstance(result, dict):
                if isinstance(result.get("data"), dict):
                    record = result["data"].get("createChatMessage")
                if record is None:
                    record = result.get("createChatMessage")
            if isinstance(record, dict):
                return record.get("id")
            logger.error("Unexpected createChatMessage result while creating HITL message: %s", result)
            return None
        except Exception as exc:
            logger.error("Error creating canonical HITL message: %s", exc, exc_info=True)
            return None

    @staticmethod
    def _structured_metadata(request: HITLRequest) -> Optional[dict[str, Any]]:
        metadata = request.metadata if isinstance(request.metadata, dict) else {}
        if not isinstance(metadata.get("action_key"), str) or not metadata["action_key"].strip():
            return None

        required = (
            "resource_refs",
            "preconditions",
            "expires_at",
            "response_schema",
            "ui_schema",
        )
        missing = [key for key in required if key not in metadata]
        if missing:
            raise ValueError("Structured HITL metadata is missing: " + ", ".join(missing))
        action_key = str(metadata["action_key"]).strip()
        resource_refs = metadata["resource_refs"]
        preconditions = metadata["preconditions"]
        response_schema = metadata["response_schema"]
        ui_schema = metadata["ui_schema"]
        if not isinstance(resource_refs, list) or not resource_refs:
            raise ValueError("Structured HITL resource_refs must be a nonempty list")
        if isinstance(preconditions, Mapping):
            normalized_preconditions: Any = dict(preconditions)
        elif isinstance(preconditions, list) and all(isinstance(item, Mapping) for item in preconditions):
            normalized_preconditions = [dict(item) for item in preconditions]
        else:
            raise ValueError("Structured HITL preconditions must be an object or a list of objects")
        if not isinstance(response_schema, Mapping) or not isinstance(ui_schema, Mapping):
            raise ValueError("Structured HITL response_schema and ui_schema must be objects")
        normalized_refs: list[dict[str, Any]] = []
        for reference in resource_refs:
            if not isinstance(reference, Mapping):
                raise ValueError("Structured HITL resource_refs entries must be objects")
            normalized = dict(reference)
            if normalized.get("system") != "plexus" or not all(
                isinstance(normalized.get(key), str) and normalized[key].strip()
                for key in ("kind", "id")
            ):
                raise ValueError("Structured HITL resource_refs must have plexus system, kind, and id")
            normalized_refs.append(normalized)
        expires_at = metadata["expires_at"]
        if not isinstance(expires_at, str) or not expires_at.strip():
            raise ValueError("Structured HITL expires_at must be an ISO-8601 string")
        try:
            parsed_expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if parsed_expiry.tzinfo is None:
                raise ValueError
        except ValueError as exc:
            raise ValueError("Structured HITL expires_at must be a timezone-aware ISO-8601 string") from exc
        report_links = metadata.get("report_links") or []
        if not isinstance(report_links, list) or any(not isinstance(item, Mapping) for item in report_links):
            raise ValueError("Structured HITL report_links must be a list of objects")
        return {
            "action_key": action_key,
            "resource_refs": normalized_refs,
            "preconditions": normalized_preconditions,
            "precondition_fingerprint": _fingerprint(normalized_preconditions),
            "expires_at": expires_at,
            "response_schema": dict(response_schema),
            "ui_schema": dict(ui_schema),
            "report_links": [dict(item) for item in report_links],
        }

    @staticmethod
    def _response_matches_schema(value: Any, schema: Any) -> bool:
        if not isinstance(schema, Mapping):
            return False
        try:
            from jsonschema import Draft202012Validator

            Draft202012Validator.check_schema(dict(schema))
            Draft202012Validator(dict(schema)).validate(value)
            return True
        except Exception:
            return False

    def request_interaction(
        self,
        procedure_id: str,
        request: HITLRequest,
        execution_context: Any = None,
    ) -> HITLResponse:
        if procedure_id != self.procedure_id:
            logger.warning(
                "Requested procedure_id %s does not match adapter procedure_id %s",
                procedure_id,
                self.procedure_id,
            )
            procedure_id = self.procedure_id

        if self.storage_adapter:
            metadata = self.storage_adapter.load_procedure_metadata(procedure_id)
            waiting_on_message_id = metadata.waiting_on_message_id
            if waiting_on_message_id:
                response = self.check_pending_response(
                    procedure_id,
                    waiting_on_message_id,
                    request=request,
                )
                if response:
                    logger.info("Found canonical response for pending message %s", waiting_on_message_id)
                    self.storage_adapter.update_procedure_status(
                        procedure_id,
                        status="RUNNING",
                        waiting_on_message_id=None,
                    )
                    return response
                logger.info(
                    "Pending HITL request %s has no response yet; reusing existing request",
                    waiting_on_message_id,
                )
                raise ProcedureWaitingForHuman(procedure_id, waiting_on_message_id)

        control_envelope = self._build_control_request_envelope(
            procedure_id=procedure_id,
            request=request,
            execution_context=execution_context,
        )
        message_id = self._record_pending_message(request, control_envelope)
        if not message_id:
            raise RuntimeError("Failed to create pending HITL message for procedure")

        if self.storage_adapter:
            self.storage_adapter.update_procedure_status(
                procedure_id,
                status="WAITING_FOR_HUMAN",
                waiting_on_message_id=message_id,
            )

        raise ProcedureWaitingForHuman(procedure_id, message_id)

    def check_pending_response(
        self,
        procedure_id: str,
        message_id: str,
        *,
        request: Optional[HITLRequest] = None,
    ) -> Optional[HITLResponse]:
        if request is None or self._structured_metadata(request) is None:
            return self._check_legacy_response(message_id)
        return self._check_structured_response(procedure_id, message_id, request)

    def _check_legacy_response(self, message_id: str) -> Optional[HITLResponse]:
        query = """
        query FindControlResponse($parentId: String!, $limit: Int) {
            listChatMessageByParentMessageId(
                parentMessageId: $parentId
                limit: $limit
                filter: { humanInteraction: { eq: RESPONSE } }
            ) {
                items {
                    id
                    content
                    metadata
                    createdAt
                    humanInteraction
                    parentMessageId
                }
            }
        }
        """

        try:
            result = self.client.execute(query, {"parentId": message_id, "limit": 20})
            items = result.get("listChatMessageByParentMessageId", {}).get("items", [])
            if not items:
                return None

            responses = [item for item in items if item.get("humanInteraction") == "RESPONSE"]
            if not responses:
                return None

            responses.sort(key=lambda item: item.get("createdAt") or "")
            response_message = responses[-1]

            response_metadata = _parse_metadata(response_message.get("metadata"))
            control = response_metadata.get("control")
            if not isinstance(control, dict):
                logger.warning(
                    "Ignoring non-canonical HITL response %s: missing metadata.control",
                    response_message.get("id"),
                )
                return None
            if "value" not in control:
                logger.warning(
                    "Ignoring non-canonical HITL response %s: metadata.control.value missing",
                    response_message.get("id"),
                )
                return None

            responded_at = _parse_iso8601(control.get("responded_at") or response_message.get("createdAt"))
            timed_out = bool(control.get("timed_out", False))

            return HITLResponse(
                value=control.get("value"),
                responded_at=responded_at,
                timed_out=timed_out,
            )
        except Exception as exc:
            logger.error("Error checking canonical HITL response: %s", exc, exc_info=True)
            return None

    def _read_structured_messages(
        self,
        message_id: str,
    ) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
        query = """
        query FindStructuredControlResponse(
            $messageId: ID!
            $parentId: String!
            $limit: Int
            $nextToken: String
        ) {
            getChatMessage(id: $messageId) {
                id
                accountId
                procedureId
                sessionId
                metadata
                humanInteraction
                responseStatus
                responseOwner
                createdAt
            }
            listChatMessageByParentMessageId(
                parentMessageId: $parentId
                limit: $limit
                nextToken: $nextToken
                filter: { humanInteraction: { eq: RESPONSE } }
            ) {
                items {
                    id
                    accountId
                    procedureId
                    sessionId
                    content
                    metadata
                    createdAt
                    humanInteraction
                    parentMessageId
                }
                nextToken
            }
        }
        """
        parent: Optional[dict[str, Any]] = None
        items: list[dict[str, Any]] = []
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
                return parent, items
            page_items = page.get("items") or []
            if isinstance(page_items, list):
                items.extend(dict(item) for item in page_items if isinstance(item, Mapping))
            raw_next_token = page.get("nextToken")
            next_token = raw_next_token if isinstance(raw_next_token, str) and raw_next_token else None
            if next_token is None:
                return parent, items

    @staticmethod
    def _structured_parent_control(
        parent: Any,
        *,
        procedure_id: str,
        message_id: str,
        request: HITLRequest,
        account_id: Optional[str],
    ) -> Optional[dict[str, Any]]:
        if not isinstance(parent, Mapping):
            return None
        if parent.get("id") != message_id or parent.get("procedureId") != procedure_id:
            return None
        expected_interaction = _PENDING_INTERACTION_BY_REQUEST_TYPE.get(
            str(request.request_type or "").lower(),
            "PENDING_INPUT",
        )
        if parent.get("humanInteraction") != expected_interaction:
            return None
        if not isinstance(parent.get("sessionId"), str) or not parent.get("sessionId"):
            return None
        parent_account_id = parent.get("accountId")
        if account_id and parent_account_id != account_id:
            return None
        if not isinstance(parent_account_id, str) or not parent_account_id:
            return None
        control = _parse_metadata(parent.get("metadata")).get("control")
        if not isinstance(control, Mapping):
            return None
        control = dict(control)
        request_metadata = PlexusHITLAdapter._structured_metadata(request)
        if request_metadata is None:
            return None
        if control.get("procedure_id") != procedure_id:
            return None
        if control.get("request_type") != request.request_type:
            return None
        if control.get("action_key") != request_metadata["action_key"]:
            return None
        if _canonical_json(control.get("resource_refs")) != _canonical_json(request_metadata["resource_refs"]):
            return None
        if _canonical_json(control.get("preconditions")) != _canonical_json(request_metadata["preconditions"]):
            return None
        expected_fingerprint = request_metadata["precondition_fingerprint"]
        if control.get("precondition_fingerprint") != expected_fingerprint:
            return None
        if _fingerprint(control.get("preconditions")) != expected_fingerprint:
            return None
        if _canonical_json(control.get("response_schema")) != _canonical_json(request_metadata["response_schema"]):
            return None
        if _canonical_json(control.get("ui_schema")) != _canonical_json(request_metadata["ui_schema"]):
            return None
        request_id = control.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            return None
        expires_at = control.get("expires_at")
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
    def _structured_child_value(
        child: Mapping[str, Any],
        *,
        parent: Mapping[str, Any],
        control: Mapping[str, Any],
    ) -> Optional[tuple[Any, datetime, bool]]:
        if child.get("humanInteraction") != "RESPONSE":
            return None
        if child.get("parentMessageId") != parent.get("id"):
            return None
        for key in ("accountId", "procedureId", "sessionId"):
            if child.get(key) != parent.get(key):
                return None
        response_control = _parse_metadata(child.get("metadata")).get("control")
        if not isinstance(response_control, Mapping):
            return None
        checks = {
            "request_id": control.get("request_id"),
            "procedure_id": control.get("procedure_id"),
            "request_type": control.get("request_type"),
            "action_key": control.get("action_key"),
            "precondition_fingerprint": control.get("precondition_fingerprint"),
        }
        if any(response_control.get(key) != value for key, value in checks.items()):
            return None
        if "value" not in response_control:
            return None
        value = response_control.get("value")
        try:
            content = json.loads(child.get("content") or "")
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(content, Mapping) or "value" not in content:
            return None
        if _canonical_json(content.get("value")) != _canonical_json(value):
            return None
        if not PlexusHITLAdapter._response_matches_schema(value, control.get("response_schema")):
            return None
        responded_at = _parse_iso8601(
            response_control.get("responded_at") or child.get("createdAt")
        )
        return value, responded_at, bool(response_control.get("timed_out", False))

    def _check_structured_response(
        self,
        procedure_id: str,
        message_id: str,
        request: HITLRequest,
    ) -> Optional[HITLResponse]:
        try:
            parent, children = self._read_structured_messages(message_id)
            recorder_account_id = getattr(self.chat_recorder, "account_id", None)
            account_id = recorder_account_id if isinstance(recorder_account_id, str) else None
            control = self._structured_parent_control(
                parent,
                procedure_id=procedure_id,
                message_id=message_id,
                request=request,
                account_id=account_id,
            )
            if control is None or parent is None:
                return None

            valid_children: dict[str, tuple[Any, datetime, bool]] = {}
            for child in sorted(
                children,
                key=lambda item: (str(item.get("createdAt") or ""), str(item.get("id") or "")),
            ):
                child_id = child.get("id")
                if not isinstance(child_id, str) or not child_id:
                    continue
                parsed = self._structured_child_value(child, parent=parent, control=control)
                if parsed is not None:
                    valid_children[child_id] = parsed

            response_owner = parent.get("responseOwner")
            if parent.get("responseStatus") == "COMPLETED":
                if not isinstance(response_owner, str) or response_owner not in valid_children:
                    return None
                value, responded_at, timed_out = valid_children[response_owner]
                return HITLResponse(value=value, responded_at=responded_at, timed_out=timed_out)
            if parent.get("responseStatus") != "PENDING" or not valid_children:
                return None

            winner_id = next(iter(valid_children))
            completed_at = datetime.now(timezone.utc).isoformat()
            mutation = """
            mutation ClaimStructuredControlResponse(
                $input: UpdateChatMessageInput!
                $condition: ModelChatMessageConditionInput
            ) {
                updateChatMessage(input: $input, condition: $condition) {
                    id
                    responseStatus
                    responseOwner
                    responseCompletedAt
                }
            }
            """
            variables = {
                "input": {
                    "id": message_id,
                    "createdAt": parent.get("createdAt"),
                    "responseStatus": "COMPLETED",
                    "responseOwner": winner_id,
                    "responseCompletedAt": completed_at,
                },
                "condition": {"responseStatus": {"eq": "PENDING"}},
            }
            try:
                claim_result = self.client.execute(
                    mutation,
                    variables,
                    retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
                )
            except Exception as exc:
                message = str(exc).lower()
                if "conditional" not in message and "condition" not in message:
                    raise
                claim_result = {"errors": [{"message": str(exc)}]}

            if _has_conditional_failure(claim_result):
                reread_parent, reread_children = self._read_structured_messages(message_id)
                reread_control = self._structured_parent_control(
                    reread_parent,
                    procedure_id=procedure_id,
                    message_id=message_id,
                    request=request,
                    account_id=account_id,
                )
                if reread_parent is None or reread_control is None:
                    return None
                recorded_owner = reread_parent.get("responseOwner")
                if reread_parent.get("responseStatus") != "COMPLETED" or not isinstance(recorded_owner, str):
                    return None
                recorded_child = next(
                    (child for child in reread_children if child.get("id") == recorded_owner),
                    None,
                )
                if recorded_child is None:
                    return None
                parsed = self._structured_child_value(
                    recorded_child,
                    parent=reread_parent,
                    control=reread_control,
                )
                if parsed is None:
                    return None
                value, responded_at, timed_out = parsed
                return HITLResponse(value=value, responded_at=responded_at, timed_out=timed_out)
            if isinstance(claim_result, Mapping) and claim_result.get("errors"):
                return None
            claimed = _graphql_field(claim_result, "updateChatMessage")
            if not isinstance(claimed, Mapping) or claimed.get("responseOwner") != winner_id:
                return None
            value, responded_at, timed_out = valid_children[winner_id]
            return HITLResponse(value=value, responded_at=responded_at, timed_out=timed_out)
        except Exception as exc:
            logger.error("Error checking structured HITL response: %s", exc, exc_info=True)
            return None

    def cancel_pending_request(self, procedure_id: str, message_id: str) -> None:
        mutation = """
        mutation CancelPendingMessage($input: UpdateChatMessageInput!) {
            updateChatMessage(input: $input) {
                id
                humanInteraction
            }
        }
        """

        try:
            self.client.execute(
                mutation,
                {
                    "input": {
                        "id": message_id,
                        "humanInteraction": "CANCELLED",
                    }
                },
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
            if self.storage_adapter:
                metadata = self.storage_adapter.load_procedure_metadata(procedure_id)
                if metadata.waiting_on_message_id == message_id:
                    self.storage_adapter.update_procedure_status(
                        procedure_id,
                        status="RUNNING",
                        waiting_on_message_id=None,
                    )
            logger.info("Cancelled pending HITL message %s", message_id)
        except Exception as exc:
            logger.error("Error cancelling pending HITL message: %s", exc, exc_info=True)
