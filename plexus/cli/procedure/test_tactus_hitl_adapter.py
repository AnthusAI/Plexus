from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tactus.core.exceptions import ProcedureWaitingForHuman
from tactus.protocols.models import HITLRequest

from plexus.cli.procedure.tactus_adapters.hitl import PlexusHITLAdapter


def _make_request(**overrides):
    payload = {
        "request_type": "approval",
        "message": "Approve this action?",
        "timeout_seconds": 120,
        "default_value": False,
        "options": [{"label": "Approve", "value": "approve"}],
        "metadata": {"stage": "decide"},
    }
    payload.update(overrides)
    return HITLRequest(**payload)


def test_request_interaction_creates_pending_message_and_sets_waiting_status():
    client = Mock()
    client.execute.return_value = {
        "createChatMessage": {
            "id": "pending-msg-1",
            "sequenceNumber": 1,
            "createdAt": "2026-03-16T12:00:00Z",
        }
    }
    chat_recorder = Mock()
    chat_recorder.session_id = "session-1"
    chat_recorder.account_id = "account-1"

    storage = Mock()
    storage.load_procedure_metadata.return_value = SimpleNamespace(waiting_on_message_id=None)

    adapter = PlexusHITLAdapter(
        client=client,
        procedure_id="procedure-1",
        chat_recorder=chat_recorder,
        storage_adapter=storage,
    )

    request = _make_request()
    with pytest.raises(ProcedureWaitingForHuman) as exc_info:
        adapter.request_interaction("procedure-1", request)

    assert exc_info.value.procedure_id == "procedure-1"
    assert exc_info.value.pending_message_id == "pending-msg-1"
    mutation_variables = None
    for call in client.execute.call_args_list:
        call_args, _ = call
        if len(call_args) >= 2 and isinstance(call_args[1], dict) and "input" in call_args[1]:
            mutation_variables = call_args[1]
            break
    assert mutation_variables is not None
    message_input = mutation_variables["input"]
    assert message_input["humanInteraction"] == "PENDING_APPROVAL"
    assert message_input["messageType"] == "MESSAGE"
    metadata = message_input["metadata"]
    assert isinstance(metadata, str)
    metadata_obj = __import__("json").loads(metadata)
    assert metadata_obj["control"]["request_type"] == "approval"
    assert metadata_obj["control"]["procedure_id"] == "procedure-1"
    assert metadata_obj["control"]["request_id"]

    storage.update_procedure_status.assert_called_once_with(
        "procedure-1",
        status="WAITING_FOR_HUMAN",
        waiting_on_message_id="pending-msg-1",
    )


def test_request_interaction_returns_response_from_existing_pending_message():
    client = Mock()
    client.execute.return_value = {
        "listChatMessageByParentMessageId": {
            "items": [
                {
                    "id": "response-msg-1",
                    "content": "{\"value\":true}",
                    "metadata": {
                        "control": {
                            "request_id": "req-1",
                            "procedure_id": "procedure-1",
                            "request_type": "approval",
                            "value": True,
                            "responded_at": "2026-03-16T12:00:00Z",
                        }
                    },
                    "createdAt": "2026-03-16T12:00:00Z",
                    "humanInteraction": "RESPONSE",
                    "parentMessageId": "pending-msg-1",
                }
            ]
        }
    }

    chat_recorder = Mock()
    chat_recorder.session_id = "session-1"

    storage = Mock()
    storage.load_procedure_metadata.return_value = SimpleNamespace(waiting_on_message_id="pending-msg-1")

    adapter = PlexusHITLAdapter(
        client=client,
        procedure_id="procedure-1",
        chat_recorder=chat_recorder,
        storage_adapter=storage,
    )

    response = adapter.request_interaction("procedure-1", _make_request())
    assert response.value is True
    assert response.timed_out is False
    storage.update_procedure_status.assert_called_once_with(
        "procedure-1",
        status="RUNNING",
        waiting_on_message_id=None,
    )


def test_check_pending_response_ignores_non_canonical_response_payload():
    client = Mock()
    client.execute.return_value = {
        "listChatMessageByParentMessageId": {
            "items": [
                {
                    "id": "response-msg-1",
                    "content": "{\"approved\":true}",
                    "metadata": {"foo": "bar"},
                    "createdAt": "2026-03-16T12:00:00Z",
                    "humanInteraction": "RESPONSE",
                    "parentMessageId": "pending-msg-1",
                }
            ]
        }
    }
    adapter = PlexusHITLAdapter(client=client, procedure_id="procedure-1")

    response = adapter.check_pending_response("procedure-1", "pending-msg-1")
    assert response is None


def test_request_interaction_reuses_existing_unresolved_pending_message():
    client = Mock()
    client.execute.return_value = {
        "listChatMessageByParentMessageId": {
            "items": []
        }
    }

    storage = Mock()
    storage.load_procedure_metadata.return_value = SimpleNamespace(waiting_on_message_id="pending-msg-1")
    adapter = PlexusHITLAdapter(
        client=client,
        procedure_id="procedure-1",
        chat_recorder=Mock(session_id="session-1"),
        storage_adapter=storage,
    )

    with pytest.raises(ProcedureWaitingForHuman) as exc_info:
        adapter.request_interaction("procedure-1", _make_request())

    assert exc_info.value.pending_message_id == "pending-msg-1"
    storage.update_procedure_status.assert_not_called()
    for call_args, _ in client.execute.call_args_list:
        if call_args:
            assert "createChatMessage" not in call_args[0]
