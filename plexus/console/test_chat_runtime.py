from __future__ import annotations

import json

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


class FakeRaisingClaimClient(FakeClient):
    def execute(self, query, variables=None, **_kwargs):
        if "ClaimConsoleChatMessage" in query:
            raise Exception("GraphQL query failed: The conditional request failed")
        return super().execute(query, variables, **_kwargs)


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


class FakeHistoryClient(FakeClient):
    def __init__(self, pages):
        super().__init__()
        self.pages = list(pages)

    def execute(self, query, variables=None, **_kwargs):
        if "ListConsoleSessionHistory" in query:
            self.executed.append((query, variables or {}))
            page = self.pages.pop(0) if self.pages else {"items": [], "nextToken": None}
            return {"data": {"listChatMessageBySessionIdAndCreatedAt": page}}
        return super().execute(query, variables, **_kwargs)


class FakeSessionTitleClient(FakeClient):
    def __init__(self, *, turns=None, session_metadata=None, assistant_messages=None):
        super().__init__()
        self.turns = list(turns or [])
        self.session_metadata = session_metadata
        self.assistant_messages = list(assistant_messages or [])
        self.updated_title_payloads = []

    def execute(self, query, variables=None, **_kwargs):
        if "GetConsoleChatSession" in query:
            return {
                "data": {
                    "getChatSession": {
                        "id": "sess-1",
                        "name": None,
                        "metadata": self.session_metadata,
                    }
                }
            }
        if "ListRecentUserChatTurns" in query:
            items = []
            for index, turn in enumerate(self.turns):
                items.append(
                    {
                        "id": turn.get("id", f"user-{index + 1}"),
                        "role": "USER",
                        "humanInteraction": "CHAT",
                        "messageType": "MESSAGE",
                        "content": turn["content"],
                        "createdAt": turn.get("createdAt", f"2026-04-27T00:00:0{index}.000Z"),
                    }
                )
            return {
                "data": {
                    "listChatMessageBySessionIdAndCreatedAt": {
                        "items": items,
                        "nextToken": None,
                    }
                }
            }
        if "ListAssistantMessagesForTitle" in query:
            items = []
            for index, text in enumerate(self.assistant_messages):
                items.append(
                    {
                        "id": f"assistant-{index + 1}",
                        "role": "ASSISTANT",
                        "humanInteraction": "CHAT_ASSISTANT",
                        "messageType": "MESSAGE",
                        "content": text,
                        "createdAt": f"2026-04-27T00:00:0{index + 1}.500Z",
                    }
                )
            return {
                "data": {
                    "listChatMessageBySessionIdAndCreatedAt": {
                        "items": items,
                        "nextToken": None,
                    }
                }
            }
        if "UpdateConsoleChatSessionTitle" in query:
            payload = (variables or {}).get("input", {})
            self.updated_title_payloads.append(payload)
            return {
                "data": {
                    "updateChatSession": {
                        "id": payload.get("id"),
                        "name": payload.get("name"),
                        "updatedAt": payload.get("updatedAt"),
                    }
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


def test_parse_chat_message_extracts_selected_model_from_metadata():
    message = chat_runtime.parse_chat_message(
        _raw_message(
            metadata='{"model":{"id":"gpt-5.3"},"instrumentation":{"client_selected_model":"gpt-5.3"}}'
        )
    )

    assert message is not None
    assert message.selected_model == "gpt-5.3"


def test_parse_chat_message_ignores_non_object_metadata():
    message = chat_runtime.parse_chat_message(
        _raw_message(metadata="not-json")
    )

    assert message is not None
    assert message.selected_model is None


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


def test_duplicate_claim_exception_returns_false(monkeypatch):
    client = FakeRaisingClaimClient()
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


def test_process_console_message_ignores_auto_title_failures(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(
        chat_runtime,
        "run_console_chat_response",
        lambda *_args, **_kwargs: {"success": True},
    )
    monkeypatch.setattr(
        chat_runtime,
        "maybe_auto_title_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("title-fail")),
    )

    assert chat_runtime.process_console_message(
        client,
        _raw_message(),
        expected_target="cloud",
        owner="cloud:test",
    ) is True


def test_process_console_message_logs_latency_summary(monkeypatch):
    client = FakeClient()
    info_logs = []

    def fake_run_console_chat_response(_client, _message, *, owner, latency_trace=None):
        assert owner == "cloud:test"
        assert isinstance(latency_trace, dict)
        now = chat_runtime.utc_now()
        latency_trace["t_history_loaded"] = now
        latency_trace["t_run_started"] = now
        latency_trace["t_first_assistant_chunk"] = now
        return {"success": True}

    monkeypatch.setattr(
        chat_runtime,
        "run_console_chat_response",
        fake_run_console_chat_response,
    )
    monkeypatch.setattr(chat_runtime.logger, "info", lambda message, *args, **kwargs: info_logs.append(message % args if args else message))

    assert chat_runtime.process_console_message(
        client,
        _raw_message(),
        expected_target="cloud",
        owner="cloud:test",
    ) is True

    payloads = []
    for raw in info_logs:
        text = str(raw).strip()
        json_start = text.find("{")
        if json_start < 0:
            continue
        payload = json.loads(text[json_start:])
        if payload.get("event") == "console_chat_latency":
            payloads.append(payload)

    assert payloads, "expected console_chat_latency log payload"
    summary = payloads[-1]
    assert summary["status"] == "COMPLETED"
    assert summary["message_id"] == "msg-1"
    assert isinstance(summary["claim_ms"], int)
    assert isinstance(summary["history_ms"], int)
    assert isinstance(summary["startup_ms"], int)
    assert isinstance(summary["first_token_ms"], int)
    assert isinstance(summary["total_ms"], int)
    assert summary["claim_ms"] >= 0
    assert summary["history_ms"] >= 0
    assert summary["startup_ms"] >= 0
    assert summary["first_token_ms"] >= 0
    assert summary["total_ms"] >= 0


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


def test_process_console_message_falls_back_to_trigger_created_at(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(
        chat_runtime,
        "run_console_chat_response",
        lambda *_args, **_kwargs: {"success": True},
    )
    monkeypatch.setattr(
        chat_runtime,
        "fetch_message",
        lambda *_args, **_kwargs: chat_runtime.parse_chat_message(_raw_message(createdAt="")),
    )

    assert chat_runtime.process_console_message(
        client,
        _raw_message(createdAt="2026-04-27T00:00:00.000Z"),
        expected_target="cloud",
        owner="cloud:test",
    ) is True

    complete_call = next(
        variables
        for query, variables in client.executed
        if "CompleteConsoleChatMessage" in query
    )
    assert complete_call["input"]["createdAt"] == "2026-04-27T00:00:00.000Z"


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
    assert "responseStatus: PENDING" in query
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
    assert kwargs["enable_mcp"] is True
    assert kwargs["context"] == {
        "account_id": "acct-1",
        "chat_session_id": "sess-1",
        "console_trigger_message_id": "msg-1",
        "console_response_owner": "local:ryan:test",
        "disable_console_dispatch_metadata_lookup": True,
    }


def test_run_console_chat_response_passes_selected_model_override(monkeypatch):
    client = FakeClient()
    message = chat_runtime.parse_chat_message(
        _raw_message(
            content="Use model override",
            metadata='{"model":{"id":"gpt-5.3"}}',
        )
    )
    calls = []

    class FakeProcedureService:
        def __init__(self, service_client):
            self.service_client = service_client

        async def run_experiment(self, procedure_id, **kwargs):
            calls.append((procedure_id, kwargs, self.service_client))
            return {"success": True, "response": "ok"}

    monkeypatch.setattr(chat_runtime, "ProcedureService", FakeProcedureService)

    assert message is not None
    result = chat_runtime.run_console_chat_response(client, message, owner="local:ryan:test")

    assert result == {"success": True, "response": "ok"}
    procedure_id, kwargs, service_client = calls[0]
    assert procedure_id == "builtin:console/chat"
    assert service_client is client
    assert kwargs["context"]["agent_models"] == {"assistant": "gpt-5.3"}


def test_maybe_auto_title_session_sets_title_on_first_user_turn(monkeypatch):
    client = FakeSessionTitleClient(turns=[{"id": "msg-1", "content": "Need help with dosage guidelines"}])
    message = chat_runtime.parse_chat_message(_raw_message())
    assert message is not None

    monkeypatch.setattr(
        chat_runtime,
        "_generate_session_title_with_llm",
        lambda **kwargs: "Dosage Guidelines Help",
    )

    chat_runtime.maybe_auto_title_session(client, message=message)

    assert len(client.updated_title_payloads) == 1
    payload = client.updated_title_payloads[0]
    assert payload["name"] == "Dosage Guidelines Help"
    metadata = json.loads(payload["metadata"])
    assert metadata["title_source"] == "auto"
    assert metadata["auto_title_turn"] == 1
    assert metadata["auto_title_message_id"] == "msg-1"
    assert metadata["console"]["hidden_until_named"] is False


def test_maybe_auto_title_session_replaces_title_on_second_user_turn(monkeypatch):
    client = FakeSessionTitleClient(
        turns=[
            {"id": "msg-2", "content": "Also include prior authorization edge cases", "createdAt": "2026-04-27T00:00:02.000Z"},
            {"id": "msg-1", "content": "Need help with dosage guidelines", "createdAt": "2026-04-27T00:00:00.000Z"},
        ],
        assistant_messages=["Here's a first draft plan you can use."],
    )
    message = chat_runtime.parse_chat_message(_raw_message(id="msg-2", metadata='{"model":{"id":"gpt-5.3"}}'))
    assert message is not None

    calls = []

    def fake_title_generator(**kwargs):
        calls.append(kwargs)
        return "Dosage + Prior Authorization"

    monkeypatch.setattr(chat_runtime, "_generate_session_title_with_llm", fake_title_generator)

    chat_runtime.maybe_auto_title_session(client, message=message)

    assert len(client.updated_title_payloads) == 1
    payload = client.updated_title_payloads[0]
    metadata = json.loads(payload["metadata"])
    assert metadata["auto_title_turn"] == 2
    assert metadata["console"]["hidden_until_named"] is False
    assert payload["name"] == "Dosage + Prior Authorization"
    assert calls[0]["selected_model"] == "gpt-5.3"
    assert calls[0]["conversation_messages"] == [
        {"role": "USER", "content": "Need help with dosage guidelines"},
        {"role": "ASSISTANT", "content": "Here's a first draft plan you can use."},
        {"role": "USER", "content": "Also include prior authorization edge cases"},
    ]


def test_maybe_auto_title_session_skips_third_and_later_turns(monkeypatch):
    client = FakeSessionTitleClient(
        turns=[
            {"id": "msg-3", "content": "third message"},
            {"id": "msg-2", "content": "second message"},
            {"id": "msg-1", "content": "first message"},
        ]
    )
    message = chat_runtime.parse_chat_message(_raw_message(id="msg-3"))
    assert message is not None

    generator_calls = []
    monkeypatch.setattr(
        chat_runtime,
        "_generate_session_title_with_llm",
        lambda **kwargs: generator_calls.append(kwargs) or "Should Not Be Used",
    )

    chat_runtime.maybe_auto_title_session(client, message=message)

    assert client.updated_title_payloads == []
    assert generator_calls == []


def test_maybe_auto_title_session_respects_manual_title_lock(monkeypatch):
    client = FakeSessionTitleClient(
        turns=[{"id": "msg-1", "content": "first message"}],
        session_metadata={"title_source": "manual"},
    )
    message = chat_runtime.parse_chat_message(_raw_message())
    assert message is not None

    generator_calls = []
    monkeypatch.setattr(
        chat_runtime,
        "_generate_session_title_with_llm",
        lambda **kwargs: generator_calls.append(kwargs) or "Should Not Be Used",
    )

    chat_runtime.maybe_auto_title_session(client, message=message)

    assert client.updated_title_payloads == []
    assert generator_calls == []


def test_fetch_session_history_filters_and_sorts_messages():
    client = FakeHistoryClient([
        {
            "items": [
                {
                    "id": "msg-3",
                    "role": "ASSISTANT",
                    "messageType": "MESSAGE",
                    "humanInteraction": "CHAT_ASSISTANT",
                    "content": "third",
                    "createdAt": "2026-04-27T00:00:03.000Z",
                },
                {
                    "id": "msg-tool",
                    "role": "ASSISTANT",
                    "messageType": "TOOL_CALL",
                    "humanInteraction": "CHAT_ASSISTANT",
                    "content": "ignore",
                    "createdAt": "2026-04-27T00:00:02.000Z",
                },
            ],
            "nextToken": "page-2",
        },
        {
            "items": [
                {
                    "id": "msg-1",
                    "role": "USER",
                    "messageType": "MESSAGE",
                    "humanInteraction": "CHAT",
                    "content": "first",
                    "createdAt": "2026-04-27T00:00:01.000Z",
                },
                {
                    "id": "msg-sys",
                    "role": "SYSTEM",
                    "messageType": "MESSAGE",
                    "humanInteraction": "CHAT",
                    "content": "ignore",
                    "createdAt": "2026-04-27T00:00:00.500Z",
                },
            ],
            "nextToken": None,
        },
    ])

    history = chat_runtime.fetch_session_history(client, "sess-1", limit=10)

    assert history == [
        {"role": "USER", "content": "first"},
        {"role": "ASSISTANT", "content": "third"},
    ]
