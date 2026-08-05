import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tactus.core.exceptions import ProcedureWaitingForHuman
from tactus.protocols.models import HITLRequest

from plexus.cli.procedure.tactus_adapters.hitl import PlexusHITLAdapter
from plexus.dashboard.api.client import LONG_RUNNING_WRITE_RETRY_POLICY_NAME


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


def _structured_request(**overrides):
    metadata = {
        "action_key": "approve-score-change",
        "resource_refs": [{"system": "plexus", "kind": "score", "id": "score-1"}],
        "preconditions": [{"field": "score_version_id", "expected": "version-1"}],
        "expires_at": "2099-08-01T00:00:00Z",
        "response_schema": {"type": "boolean"},
        "ui_schema": {"ui:widget": "approval"},
        "report_links": [{"report_id": "report-1", "label": "Evidence"}],
    }
    metadata.update(overrides.pop("metadata", {}))
    return _make_request(metadata=metadata, **overrides)


def _fingerprint(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _pending_message(control, **overrides):
    value = {
        "id": "pending-msg-1",
        "accountId": "account-1",
        "procedureId": "procedure-1",
        "sessionId": "session-1",
        "humanInteraction": "PENDING_APPROVAL",
        "responseStatus": "PENDING",
        "responseOwner": None,
        "metadata": json.dumps({"control": control}),
        "createdAt": "2026-07-29T12:00:00Z",
    }
    value.update(overrides)
    return value


def _response_message(control, response_id, value, **overrides):
    response_control = {
        "request_id": control["request_id"],
        "procedure_id": "procedure-1",
        "request_type": "approval",
        "action_key": control["action_key"],
        "precondition_fingerprint": control["precondition_fingerprint"],
        "value": value,
        "responded_at": "2026-07-29T12:01:00Z",
    }
    row = {
        "id": response_id,
        "accountId": "account-1",
        "procedureId": "procedure-1",
        "sessionId": "session-1",
        "content": json.dumps({"value": value}),
        "metadata": json.dumps({"control": response_control}),
        "createdAt": "2026-07-29T12:01:00Z",
        "humanInteraction": "RESPONSE",
        "parentMessageId": "pending-msg-1",
    }
    row.update(overrides)
    return row


def _control_envelope():
    preconditions = [{"field": "score_version_id", "expected": "version-1"}]
    return {
        "request_id": "request-1",
        "procedure_id": "procedure-1",
        "request_type": "approval",
        "action_key": "approve-score-change",
        "resource_refs": [{"system": "plexus", "kind": "score", "id": "score-1"}],
        "preconditions": preconditions,
        "precondition_fingerprint": _fingerprint(preconditions),
        "expires_at": "2099-08-01T00:00:00Z",
        "response_schema": {"type": "boolean"},
        "ui_schema": {"ui:widget": "approval"},
        "report_links": [{"report_id": "report-1", "label": "Evidence"}],
    }


def test_structured_hitl_uses_existing_pending_message_with_authority_envelope():
    client = Mock()
    client.execute.return_value = {"createChatMessage": {"id": "pending-msg-1"}}
    storage = Mock()
    storage.load_procedure_metadata.return_value = SimpleNamespace(waiting_on_message_id=None)
    adapter = PlexusHITLAdapter(
        client=client,
        procedure_id="procedure-1",
        chat_recorder=Mock(session_id="session-1", account_id="account-1"),
        storage_adapter=storage,
    )

    with pytest.raises(ProcedureWaitingForHuman) as exc_info:
        adapter.request_interaction("procedure-1", _structured_request())

    assert exc_info.value.pending_message_id == "pending-msg-1"
    mutation_variables = client.execute.call_args.args[1]
    control = json.loads(mutation_variables["input"]["metadata"])["control"]
    assert control["action_key"] == "approve-score-change"
    assert control["precondition_fingerprint"] == _fingerprint(control["preconditions"])
    assert control["resource_refs"] == [{"system": "plexus", "kind": "score", "id": "score-1"}]
    assert control["response_schema"] == {"type": "boolean"}
    assert control["ui_schema"] == {"ui:widget": "approval"}
    assert control["report_links"] == [{"report_id": "report-1", "label": "Evidence"}]
    storage.update_procedure_status.assert_called_once_with(
        "procedure-1", status="WAITING_FOR_HUMAN", waiting_on_message_id="pending-msg-1"
    )


def test_structured_hitl_first_valid_same_account_response_claims_pending_parent():
    control = _control_envelope()
    other_account = _response_message(control, "response-other", False, accountId="account-2")
    winner = _response_message(control, "response-winner", True, createdAt="2026-07-29T12:02:00Z")
    client = Mock()
    client.execute.side_effect = [
        {
            "getChatMessage": _pending_message(control),
            "listChatMessageByParentMessageId": {"items": [winner, other_account]},
        },
        {"updateChatMessage": {"id": "pending-msg-1", "responseStatus": "COMPLETED", "responseOwner": "response-winner"}},
    ]
    adapter = PlexusHITLAdapter(
        client=client,
        procedure_id="procedure-1",
        chat_recorder=Mock(session_id="session-1", account_id="account-1"),
    )

    response = adapter.check_pending_response(
        "procedure-1", "pending-msg-1", request=_structured_request()
    )

    assert response.value is True
    authority_query = client.execute.call_args_list[0].args[0]
    authority_variables = client.execute.call_args_list[0].args[1]
    assert "$messageId: ID!" in authority_query
    assert "$parentId: String!" in authority_query
    assert "getChatMessage(id: $messageId)" in authority_query
    assert authority_variables["messageId"] == "pending-msg-1"
    assert authority_variables["parentId"] == "pending-msg-1"
    claim_variables = client.execute.call_args_list[1].args[1]
    assert claim_variables["input"]["responseStatus"] == "COMPLETED"
    assert claim_variables["input"]["responseOwner"] == "response-winner"
    assert claim_variables["condition"] == {"responseStatus": {"eq": "PENDING"}}


def test_structured_hitl_claims_oldest_valid_response_not_latest():
    control = _control_envelope()
    oldest = _response_message(
        control, "response-oldest", False, createdAt="2026-07-29T12:01:00Z"
    )
    latest = _response_message(
        control, "response-latest", True, createdAt="2026-07-29T12:02:00Z"
    )
    client = Mock()
    client.execute.side_effect = [
        {
            "getChatMessage": _pending_message(control),
            "listChatMessageByParentMessageId": {"items": [latest, oldest]},
        },
        {
            "updateChatMessage": {
                "id": "pending-msg-1",
                "responseStatus": "COMPLETED",
                "responseOwner": "response-oldest",
            }
        },
    ]
    adapter = PlexusHITLAdapter(
        client=client,
        procedure_id="procedure-1",
        chat_recorder=Mock(session_id="session-1", account_id="account-1"),
    )

    response = adapter.check_pending_response(
        "procedure-1", "pending-msg-1", request=_structured_request()
    )

    assert response.value is False
    claim = client.execute.call_args_list[1].args[1]
    assert claim["input"]["responseOwner"] == "response-oldest"
    assert claim["input"]["createdAt"] == "2026-07-29T12:00:00Z"


def test_structured_hitl_conditional_loser_uses_recorded_winner():
    control = _control_envelope()
    losing_candidate = _response_message(control, "response-loser", True)
    recorded_winner = _response_message(control, "response-winner", False)
    client = Mock()
    client.execute.side_effect = [
        {
            "getChatMessage": _pending_message(control),
            "listChatMessageByParentMessageId": {"items": [losing_candidate]},
        },
        {"errors": [{"errorType": "ConditionalCheckFailedException", "message": "condition failed"}]},
        {
            "getChatMessage": _pending_message(
                control, responseStatus="COMPLETED", responseOwner="response-winner"
            ),
            "listChatMessageByParentMessageId": {"items": [recorded_winner, losing_candidate]},
        },
    ]
    adapter = PlexusHITLAdapter(
        client=client,
        procedure_id="procedure-1",
        chat_recorder=Mock(session_id="session-1", account_id="account-1"),
    )

    response = adapter.check_pending_response(
        "procedure-1", "pending-msg-1", request=_structured_request()
    )

    assert response.value is False
    assert len(client.execute.call_args_list) == 3


@pytest.mark.parametrize(
    ("parent_overrides", "request_metadata"),
    [
        ({"expires_at": "2000-01-01T00:00:00Z"}, {}),
        ({"precondition_fingerprint": "stale"}, {}),
    ],
)
def test_structured_hitl_expired_or_stale_request_fails_closed(
    parent_overrides, request_metadata
):
    control = {**_control_envelope(), **parent_overrides}
    child = _response_message(control, "response-1", True)
    client = Mock()
    client.execute.return_value = {
        "getChatMessage": _pending_message(control),
        "listChatMessageByParentMessageId": {"items": [child]},
    }
    adapter = PlexusHITLAdapter(
        client=client,
        procedure_id="procedure-1",
        chat_recorder=Mock(session_id="session-1", account_id="account-1"),
    )

    response = adapter.check_pending_response(
        "procedure-1",
        "pending-msg-1",
        request=_structured_request(metadata=request_metadata),
    )

    assert response is None
    assert len(client.execute.call_args_list) == 1


def test_structured_hitl_skips_schema_invalid_child_and_claims_next_valid_child():
    control = _control_envelope()
    invalid = _response_message(control, "response-invalid", "yes")
    valid = _response_message(control, "response-valid", True, createdAt="2026-07-29T12:02:00Z")
    client = Mock()
    client.execute.side_effect = [
        {
            "getChatMessage": _pending_message(control),
            "listChatMessageByParentMessageId": {"items": [valid, invalid]},
        },
        {"updateChatMessage": {"id": "pending-msg-1", "responseStatus": "COMPLETED", "responseOwner": "response-valid"}},
    ]
    adapter = PlexusHITLAdapter(
        client=client,
        procedure_id="procedure-1",
        chat_recorder=Mock(session_id="session-1", account_id="account-1"),
    )

    response = adapter.check_pending_response(
        "procedure-1", "pending-msg-1", request=_structured_request()
    )

    assert response.value is True
    assert client.execute.call_args_list[1].args[1]["input"]["responseOwner"] == "response-valid"


def test_structured_hitl_cross_account_child_fails_closed_without_claiming():
    control = _control_envelope()
    child = _response_message(control, "response-other", True, accountId="account-2")
    client = Mock()
    client.execute.return_value = {
        "getChatMessage": _pending_message(control),
        "listChatMessageByParentMessageId": {"items": [child]},
    }
    adapter = PlexusHITLAdapter(
        client=client,
        procedure_id="procedure-1",
        chat_recorder=Mock(session_id="session-1", account_id="account-1"),
    )

    response = adapter.check_pending_response(
        "procedure-1", "pending-msg-1", request=_structured_request()
    )

    assert response is None
    assert len(client.execute.call_args_list) == 1


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
    assert message_input["responseTarget"] == "procedure-1"
    assert message_input["responseStatus"] == "PENDING"
    metadata = message_input["metadata"]
    assert isinstance(metadata, str)
    metadata_obj = __import__("json").loads(metadata)
    assert metadata_obj["control"]["request_type"] == "approval"
    assert metadata_obj["control"]["procedure_id"] == "procedure-1"
    assert metadata_obj["control"]["request_id"]
    assert client.execute.call_args.kwargs["retry_policy"] == LONG_RUNNING_WRITE_RETRY_POLICY_NAME

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


def test_cancel_pending_request_uses_long_running_retry_policy():
    client = Mock()
    client.execute.return_value = {"updateChatMessage": {"id": "pending-msg-1", "humanInteraction": "CANCELLED"}}

    storage = Mock()
    storage.load_procedure_metadata.return_value = SimpleNamespace(waiting_on_message_id="pending-msg-1")
    adapter = PlexusHITLAdapter(
        client=client,
        procedure_id="procedure-1",
        chat_recorder=Mock(session_id="session-1"),
        storage_adapter=storage,
    )

    adapter.cancel_pending_request("procedure-1", "pending-msg-1")

    assert client.execute.call_args.kwargs["retry_policy"] == LONG_RUNNING_WRITE_RETRY_POLICY_NAME
