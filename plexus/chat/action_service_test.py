import json
from unittest.mock import Mock

from plexus.chat.action_service import ChatMessageActionService, _fingerprint


def _action(**overrides):
    value = {
        "action_key": "review:one",
        "account_id": "account-1",
        "kind": "stakeholder_clarification",
        "title": "Review finding",
        "message": "Which policy should apply?",
        "resource_refs": [{"system": "plexus", "kind": "score", "id": "score-1"}],
        "preconditions": {"evidence": "one"},
        "response_schema": {"type": "object"},
        "ui_schema": {"kind": "finding_review"},
    }
    value.update(overrides)
    return value


def _session():
    return {"id": "session-1", "accountId": "account-1", "procedureId": "procedure-1"}


def _row(*, evidence="one", status="PENDING", row_id="message-1"):
    fingerprint = _fingerprint({"evidence": evidence})
    return {
        "id": row_id,
        "accountId": "account-1",
        "sessionId": "session-1",
        "procedureId": "procedure-1",
        "humanInteraction": "PENDING_INPUT",
        "responseStatus": status,
        "metadata": json.dumps(
            {"control": {"action_key": "review:one", "evidence_fingerprint": fingerprint}}
        ),
        "createdAt": "2026-07-29T12:00:00Z",
    }


def _authority_control():
    preconditions = {"evidence": "one"}
    fingerprint = _fingerprint(preconditions)
    return {
        "request_id": "action-request-1",
        "procedure_id": "procedure-1",
        "request_type": "input",
        "action_key": "review:one",
        "preconditions": preconditions,
        "precondition_fingerprint": fingerprint,
        "evidence_fingerprint": fingerprint,
        "expires_at": "2099-08-01T00:00:00Z",
        "response_schema": {
            "type": "object",
            "required": ["response"],
            "properties": {"response": {"type": "string"}},
        },
    }


def _authority_parent():
    return {
        "id": "message-1",
        "accountId": "account-1",
        "sessionId": "session-1",
        "procedureId": "procedure-1",
        "humanInteraction": "PENDING_INPUT",
        "responseStatus": "PENDING",
        "responseOwner": None,
        "metadata": json.dumps({"control": _authority_control()}),
        "createdAt": "2026-07-29T12:00:00Z",
    }


def _authority_child(*, child_id="response-1", account_id="account-1", value=None):
    value = {"response": "approved"} if value is None else value
    control = _authority_control()
    child_control = {
        key: control[key]
        for key in (
            "request_id",
            "procedure_id",
            "request_type",
            "action_key",
            "precondition_fingerprint",
            "evidence_fingerprint",
        )
    }
    child_control.update({"value": value, "responded_at": "2026-07-29T12:01:00Z"})
    return {
        "id": child_id,
        "accountId": account_id,
        "sessionId": "session-1",
        "procedureId": "procedure-1",
        "humanInteraction": "RESPONSE",
        "parentMessageId": "message-1",
        "content": json.dumps({"value": value}),
        "metadata": json.dumps({"control": child_control}),
        "createdAt": "2026-07-29T12:01:00Z",
    }


def test_create_or_get_reuses_exact_action_without_touching_procedure():
    client = Mock()
    client.execute.side_effect = [
        {"getChatSession": _session()},
        {"listChatMessageByProcedureIdAndCreatedAt": {"items": [_row()], "nextToken": None}},
    ]

    result = ChatMessageActionService(client).create_or_get(
        _action(), procedure_id="procedure-1", session_id="session-1"
    )

    assert result == {"action": _row(), "created": False}
    assert all("updateProcedure" not in call.args[0] for call in client.execute.call_args_list)


def test_create_or_get_supersedes_incompatible_pending_then_creates_message():
    client = Mock()
    created = _row(evidence="two", row_id="created-message")
    client.execute.side_effect = [
        {"getChatSession": _session()},
        {"listChatMessageByProcedureIdAndCreatedAt": {"items": [_row()], "nextToken": None}},
        {"updateChatMessage": {"id": "message-1", "responseStatus": "FAILED"}},
        {"createChatMessage": created},
    ]

    result = ChatMessageActionService(client).create_or_get(
        _action(preconditions={"evidence": "two"}),
        procedure_id="procedure-1",
        session_id="session-1",
    )

    assert result == {"action": created, "created": True}
    supersede = client.execute.call_args_list[2].args[1]
    assert supersede["condition"] == {"responseStatus": {"eq": "PENDING"}}
    assert supersede["input"]["humanInteraction"] == "CANCELLED"
    create_input = client.execute.call_args_list[3].args[1]["input"]
    control = json.loads(create_input["metadata"])["control"]
    assert control["action_key"] == "review:one"
    assert control["evidence_fingerprint"] == _fingerprint({"evidence": "two"})
    assert control["kind"] == "stakeholder_clarification"
    assert control["title"] == "Review finding"
    assert control["message"] == "Which policy should apply?"
    assert create_input["responseStatus"] == "PENDING"
    assert all("updateProcedure" not in call.args[0] for call in client.execute.call_args_list)


def test_publish_update_creates_one_idempotent_notification_for_an_event_key():
    client = Mock()
    created = {
        "id": "update-created",
        "accountId": "account-1",
        "sessionId": "session-1",
        "procedureId": "procedure-1",
        "humanInteraction": "NOTIFICATION",
        "content": "Portfolio analysis started",
        "createdAt": "2026-07-30T12:00:00Z",
    }
    client.execute.side_effect = [
        {"getChatSession": _session()},
        {"getChatMessage": None},
        {"createChatMessage": created},
    ]

    result = ChatMessageActionService(client).publish_update(
        {
            "event_key": "optimization:run-1:started",
            "account_id": "account-1",
            "milestone": "STARTED",
            "title": "Portfolio analysis started",
            "summary": "The living report is available while ranking proceeds.",
            "resource_refs": [{"system": "plexus", "kind": "report", "id": "report-1"}],
        },
        procedure_id="procedure-1",
        session_id="session-1",
    )

    assert result == {"update": created, "created": True}
    create_input = client.execute.call_args_list[2].args[1]["input"]
    assert create_input["humanInteraction"] == "NOTIFICATION"
    assert create_input["content"] == "Portfolio analysis started"
    control = json.loads(create_input["metadata"])
    assert control["event_key"] == "optimization:run-1:started"
    assert control["milestone"] == "STARTED"
    assert control["summary"] == "The living report is available while ranking proceeds."
    assert control["resource_refs"] == [{"system": "plexus", "kind": "report", "id": "report-1"}]

    existing_client = Mock()
    existing_client.execute.side_effect = [
        {"getChatSession": _session()},
        {"getChatMessage": created},
    ]
    replay = ChatMessageActionService(existing_client).publish_update(
        {
            "event_key": "optimization:run-1:started",
            "account_id": "account-1",
            "milestone": "STARTED",
            "title": "Portfolio analysis started",
            "resource_refs": [],
        },
        procedure_id="procedure-1",
        session_id="session-1",
    )
    assert replay == {"update": created, "created": False}
    assert len(existing_client.execute.call_args_list) == 2


def test_resolve_first_valid_response_validates_authority_and_atomically_completes_parent():
    client = Mock()
    invalid_other_account = _authority_child(child_id="response-other", account_id="account-2")
    valid = _authority_child(child_id="response-valid")
    client.execute.side_effect = [
        {
            "getChatMessage": _authority_parent(),
            "listChatMessageByParentMessageId": {
                "items": [valid, invalid_other_account],
                "nextToken": None,
            },
        },
        {
            "updateChatMessage": {
                "id": "message-1",
                "responseStatus": "COMPLETED",
                "responseOwner": "response-valid",
            }
        },
    ]

    result = ChatMessageActionService(client).resolve_first_valid_response(
        "message-1", account_id="account-1", procedure_id="procedure-1"
    )

    assert result["response"] == {"response": "approved"}
    assert result["response_message_id"] == "response-valid"
    authority_query = client.execute.call_args_list[0].args[0]
    authority_variables = client.execute.call_args_list[0].args[1]
    assert "$messageId: ID!" in authority_query
    assert "$parentId: String!" in authority_query
    assert "getChatMessage(id: $messageId)" in authority_query
    assert authority_variables["messageId"] == "message-1"
    assert authority_variables["parentId"] == "message-1"
    claim = client.execute.call_args_list[1].args[1]
    assert claim["input"]["responseOwner"] == "response-valid"
    assert claim["input"]["responseStatus"] == "COMPLETED"
    assert claim["condition"] == {"responseStatus": {"eq": "PENDING"}}
    assert all("updateProcedure" not in call.args[0] for call in client.execute.call_args_list)


def test_resolve_first_valid_response_fails_closed_for_cross_account_or_schema_invalid_children():
    client = Mock()
    client.execute.return_value = {
        "getChatMessage": _authority_parent(),
        "listChatMessageByParentMessageId": {
            "items": [
                _authority_child(account_id="account-2"),
                _authority_child(child_id="response-invalid", value={"response": 42}),
            ],
            "nextToken": None,
        },
    }

    result = ChatMessageActionService(client).resolve_first_valid_response(
        "message-1", account_id="account-1", procedure_id="procedure-1"
    )

    assert result is None
    assert len(client.execute.call_args_list) == 1
