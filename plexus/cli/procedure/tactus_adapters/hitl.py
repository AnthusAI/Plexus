"""
Canonical Plexus HITL adapter for procedure conversations.

This adapter persists pending control requests as ChatMessage records and
resolves responses strictly via child ChatMessage rows with:
- humanInteraction = RESPONSE
- parentMessageId = <pending_message_id>
- metadata.control envelope
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

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


class PlexusHITLAdapter:
    """Tactus HITLHandler implementation backed by Plexus ChatMessage records."""

    def __init__(self, client, procedure_id: str, chat_recorder=None, storage_adapter=None):
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

        return {
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
                response = self.check_pending_response(procedure_id, waiting_on_message_id)
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

    def check_pending_response(self, procedure_id: str, message_id: str) -> Optional[HITLResponse]:
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
