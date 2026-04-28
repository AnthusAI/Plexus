from __future__ import annotations

from plexus.console import chat_runtime


def _raw_message(**overrides):
    payload = {
        "id": "msg-1",
        "accountId": "acct-1",
        "sessionId": "sess-1",
        "procedureId": "builtin:console/chat",
        "role": "USER",
        "humanInteraction": "CHAT",
        "messageType": "MESSAGE",
        "content": "Hello",
        "responseTarget": "cloud",
        "responseStatus": "PENDING",
        "createdAt": "2026-04-27T00:00:00.000Z",
    }
    payload.update(overrides)
    return payload


class FakeClient:
    def __init__(self, *, claim_result=True):
        self.claim_result = claim_result
        self.executed = []

    def execute(self, query, variables=None, **_kwargs):
        self.executed.append((query, variables or {}))
        if "ClaimConsoleChatMessage" in query:
            if self.claim_result:
                return {
                    "data": {
                        "updateChatMessage": {
                            "id": "msg-1",
                            "responseStatus": "RUNNING",
                            "responseTarget": "cloud",
                            "responseOwner": "cloud:test",
                        }
                    }
                }
            return {
                "errors": [
                    {
                        "errorType": "DynamoDB:ConditionalCheckFailedException",
                        "message": "The conditional request failed",
                    }
                ]
            }
        if "GetConsoleTriggerMessage" in query:
            return {"data": {"getChatMessage": _raw_message(responseStatus="RUNNING")}}
        if "ListConsoleSessionHistory" in query:
            return {
                "data": {
                    "listChatMessageBySessionIdAndCreatedAt": {
                        "items": [_raw_message()],
                        "nextToken": None,
                    }
                }
            }
        if "CompleteConsoleChatMessage" in query:
            return {"data": {"updateChatMessage": {"id": "msg-1", "responseStatus": "COMPLETED"}}}
        if "FailConsoleChatMessage" in query:
            return {"data": {"updateChatMessage": {"id": "msg-1", "responseStatus": "FAILED"}}}
        return {}


class FakePendingClient(FakeClient):
    def __init__(self, pages):
        super().__init__()
        self.pages = list(pages)

    def execute(self, query, variables=None, **_kwargs):
        if "ListPendingConsoleMessages" in query:
            self.executed.append((query, variables or {}))
            page = self.pages.pop(0) if self.pages else {"items": [], "nextToken": None}
            return {
                "data": {
                    "listChatMessageByResponseTargetAndResponseStatusAndCreatedAt": page
                }
            }
        return super().execute(query, variables, **_kwargs)


def test_should_handle_only_matching_pending_user_chat_message():
    message = chat_runtime.parse_chat_message(_raw_message())

    assert message is not None
    assert chat_runtime.should_handle_message(message, "cloud") is True
    assert chat_runtime.should_handle_message(message, "local:ryan") is False

    assistant = chat_runtime.parse_chat_message(_raw_message(role="ASSISTANT"))
    assert assistant is not None
    assert chat_runtime.should_handle_message(assistant, "cloud") is False

    running = chat_runtime.parse_chat_message(_raw_message(responseStatus="RUNNING"))
    assert running is not None
    assert chat_runtime.should_handle_message(running, "cloud") is False


def test_parse_chat_message_defaults_missing_response_target_to_cloud():
    message = chat_runtime.parse_chat_message(_raw_message(responseTarget=None))

    assert message is not None
    assert message.response_target == "cloud"


def test_should_handle_rejects_non_chat_message_shapes():
    tool_message = chat_runtime.parse_chat_message(_raw_message(messageType="TOOL_CALL"))
    internal = chat_runtime.parse_chat_message(_raw_message(humanInteraction="INTERNAL"))
    completed = chat_runtime.parse_chat_message(_raw_message(responseStatus="COMPLETED"))

    assert tool_message is not None
    assert internal is not None
    assert completed is not None
    assert chat_runtime.should_handle_message(tool_message, "cloud") is False
    assert chat_runtime.should_handle_message(internal, "cloud") is False
    assert chat_runtime.should_handle_message(completed, "cloud") is False


def test_claim_message_uses_conditional_pending_to_running_update():
    client = FakeClient()
    message = chat_runtime.parse_chat_message(_raw_message())

    assert message is not None
    assert chat_runtime.claim_message(client, message, expected_target="cloud", owner="cloud:test") is True

    query, variables = client.executed[0]
    assert "ClaimConsoleChatMessage" in query
    assert variables["input"]["createdAt"] == "2026-04-27T00:00:00.000Z"
    assert variables["input"]["responseStatus"] == "RUNNING"
    assert variables["input"]["responseOwner"] == "cloud:test"
    assert variables["condition"] == {
        "responseTarget": {"eq": "cloud"},
        "responseStatus": {"eq": "PENDING"},
    }


def test_duplicate_claim_returns_false_without_running_response(monkeypatch):
    client = FakeClient(claim_result=False)
    calls = []
    monkeypatch.setattr(
        chat_runtime,
        "run_console_chat_response",
        lambda *_args, **_kwargs: calls.append("ran"),
    )

    assert chat_runtime.process_console_message(
        client,
        _raw_message(),
        expected_target="cloud",
        owner="cloud:test",
    ) is False
    assert calls == []


def test_process_console_message_runs_harness_and_marks_completed(monkeypatch):
    client = FakeClient()
    calls = []
    monkeypatch.setattr(
        chat_runtime,
        "run_console_chat_response",
        lambda *_args, **_kwargs: calls.append("ran") or {"success": True},
    )

    assert chat_runtime.process_console_message(
        client,
        _raw_message(),
        expected_target="cloud",
        owner="cloud:test",
    ) is True
    assert calls == ["ran"]
    complete_call = next(
        variables
        for query, variables in client.executed
        if "CompleteConsoleChatMessage" in query
    )
    assert complete_call["input"]["createdAt"] == "2026-04-27T00:00:00.000Z"
    assert complete_call["input"]["responseStatus"] == "COMPLETED"


def test_process_console_message_marks_failed_when_harness_raises(monkeypatch):
    client = FakeClient()

    def fail_response(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(chat_runtime, "run_console_chat_response", fail_response)

    try:
        chat_runtime.process_console_message(
            client,
            _raw_message(),
            expected_target="cloud",
            owner="cloud:test",
        )
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected RuntimeError")

    fail_call = next(
        variables
        for query, variables in client.executed
        if "FailConsoleChatMessage" in query
    )
    assert fail_call["input"]["createdAt"] == "2026-04-27T00:00:00.000Z"
    assert fail_call["input"]["responseStatus"] == "FAILED"
    assert fail_call["input"]["responseError"] == "boom"


def test_process_console_message_ignores_local_target_for_cloud_worker(monkeypatch):
    client = FakeClient()
    calls = []
    monkeypatch.setattr(
        chat_runtime,
        "run_console_chat_response",
        lambda *_args, **_kwargs: calls.append("ran"),
    )

    assert chat_runtime.process_console_message(
        client,
        _raw_message(responseTarget="local:ryan"),
        expected_target="cloud",
        owner="cloud:test",
    ) is False
    assert calls == []


def test_process_pending_local_messages_uses_response_status_sort_key(monkeypatch):
    client = FakePendingClient([
        {
            "items": [_raw_message(responseTarget="local:ryan")],
            "nextToken": None,
        }
    ])
    calls = []
    monkeypatch.setattr(
        chat_runtime,
        "process_console_message",
        lambda _client, item, **kwargs: calls.append((item, kwargs)) or True,
    )

    processed = chat_runtime.process_pending_local_messages(
        client,
        response_target="local:ryan",
        owner="local:ryan:test",
        limit=5,
    )

    assert processed == 1
    query, variables = client.executed[0]
    assert "responseStatusCreatedAt" in query
    assert 'responseStatus: "PENDING"' in query
    assert "filter:" not in query
    assert variables == {
        "responseTarget": "local:ryan",
        "limit": 5,
        "nextToken": None,
    }
    assert calls[0][1] == {
        "expected_target": "local:ryan",
        "owner": "local:ryan:test",
    }


def test_process_pending_local_messages_paginates_until_limit(monkeypatch):
    client = FakePendingClient([
        {
            "items": [_raw_message(id="msg-1", responseTarget="local:ryan")],
            "nextToken": "page-2",
        },
        {
            "items": [
                _raw_message(id="msg-2", responseTarget="local:ryan"),
                _raw_message(id="msg-3", responseTarget="local:ryan"),
            ],
            "nextToken": None,
        },
    ])
    seen = []
    monkeypatch.setattr(
        chat_runtime,
        "process_console_message",
        lambda _client, item, **_kwargs: seen.append(item["id"]) or True,
    )

    processed = chat_runtime.process_pending_local_messages(
        client,
        response_target="local:ryan",
        owner="local:ryan:test",
        limit=2,
    )

    assert processed == 2
    assert seen == ["msg-1", "msg-2"]
    assert client.executed[1][1]["nextToken"] == "page-2"


def test_run_console_chat_response_passes_console_context_to_builtin(monkeypatch):
    client = FakeClient()
    message = chat_runtime.parse_chat_message(_raw_message(content="Multiply 6 by 7"))
    calls = []

    class FakeProcedureService:
        def __init__(self, service_client):
            self.service_client = service_client

        async def run_experiment(self, procedure_id, **kwargs):
            calls.append((procedure_id, kwargs, self.service_client))
            return {"success": True, "response": "42"}

    monkeypatch.setattr(chat_runtime, "ProcedureService", FakeProcedureService)

    assert message is not None
    result = chat_runtime.run_console_chat_response(client, message, owner="local:ryan:test")

    assert result == {"success": True, "response": "42"}
    procedure_id, kwargs, service_client = calls[0]
    assert procedure_id == "builtin:console/chat"
    assert service_client is client
    assert kwargs["account_id"] == "acct-1"
    assert kwargs["console_user_message"] == "Multiply 6 by 7"
    assert kwargs["console_session_history"][-1] == {
        "role": "USER",
        "content": "Multiply 6 by 7",
    }
    assert kwargs["context"] == {
        "account_id": "acct-1",
        "chat_session_id": "sess-1",
        "console_trigger_message_id": "msg-1",
        "console_response_owner": "local:ryan:test",
    }
