from unittest.mock import Mock

import pytest

from plexus.cli.procedure.chat_recorder import ProcedureChatRecorder
from plexus.dashboard.api.client import CHAT_STREAM_WRITE_RETRY_POLICY_NAME


def test_resolve_account_id_prefers_context():
    client = Mock()
    recorder = ProcedureChatRecorder(client, "proc-1")

    account_id = recorder._resolve_account_id_for_session({"accountId": "acct-context"})

    assert account_id == "acct-context"
    client.execute.assert_not_called()


def test_resolve_account_id_uses_procedure_record():
    client = Mock()
    client.execute.return_value = {
        "data": {"getProcedure": {"accountId": "acct-from-procedure"}}
    }
    recorder = ProcedureChatRecorder(client, "proc-2")

    account_id = recorder._resolve_account_id_for_session({})

    assert account_id == "acct-from-procedure"
    client._resolve_account_id.assert_not_called()


def test_resolve_account_id_falls_back_to_client_resolver():
    client = Mock()
    client.execute.return_value = {"data": {"getProcedure": None}}
    client._resolve_account_id.return_value = "acct-fallback"
    recorder = ProcedureChatRecorder(client, "proc-3")

    account_id = recorder._resolve_account_id_for_session({})

    assert account_id == "acct-fallback"


@pytest.mark.asyncio
async def test_start_session_reuses_explicit_console_session_from_context(monkeypatch):
    client = Mock()
    recorder = ProcedureChatRecorder(client, "builtin:console/chat")
    monkeypatch.setattr(recorder, "_get_latest_sequence_number_for_session", lambda session_id: 7)

    session_id = await recorder.start_session(
        {
            "account_id": "acct-console",
            "chat_session_id": "session-console",
        }
    )

    assert session_id == "session-console"
    assert recorder.session_id == "session-console"
    assert recorder.account_id == "acct-console"
    assert recorder.sequence_number == 7
    client.execute.assert_not_called()


def test_get_latest_console_trigger_message_returns_chat_content():
    client = Mock()
    client.execute.side_effect = [
        {
            "data": {
                "listTaskByAccountIdAndUpdatedAt": {
                    "items": [
                        {
                            "id": "task-10",
                            "target": "procedure/proc-10",
                            "status": "PENDING",
                            "updatedAt": "2026-03-24T01:00:00.000Z",
                            "metadata": "{\"console_chat\": {\"trigger_message_id\": \"msg-123\"}}",
                        }
                    ],
                    "nextToken": None,
                }
            }
        },
        {"data": {"getChatMessage": {"id": "msg-123", "role": "USER", "content": "Hello from trigger"}}},
    ]
    recorder = ProcedureChatRecorder(client, "proc-10")

    message = recorder.get_latest_console_trigger_message(account_id="acct-10")

    assert message == "Hello from trigger"


def test_get_steering_messages_returns_completed_flat_filtered_rows():
    client = Mock()
    client.execute.return_value = {
        "data": {
            "listChatMessageByProcedureIdAndCreatedAt": {
                "items": [
                    {
                        "id": "msg-1",
                        "accountId": "acct-1",
                        "sessionId": "sess-1",
                        "procedureId": "proc-1",
                        "role": "USER",
                        "messageType": "MESSAGE",
                        "humanInteraction": "CHAT",
                        "content": "Emphasize contradictions in the summary.",
                        "metadata": '{"source":"procedure-steering-input","scope":"all_agents"}',
                        "createdAt": "2026-05-02T15:00:00.000Z",
                    },
                    {
                        "id": "msg-2",
                        "accountId": "acct-1",
                        "sessionId": "sess-1",
                        "procedureId": "proc-1",
                        "role": "USER",
                        "messageType": "MESSAGE",
                        "humanInteraction": "CHAT",
                        "content": "Regular console chat",
                        "metadata": '{"source":"console-prompt-input"}',
                        "createdAt": "2026-05-02T15:01:00.000Z",
                    },
                    {
                        "id": "msg-3",
                        "accountId": "acct-1",
                        "sessionId": "sess-1",
                        "procedureId": "proc-1",
                        "role": "ASSISTANT",
                        "messageType": "MESSAGE",
                        "humanInteraction": "CHAT_ASSISTANT",
                        "content": "Assistant response",
                        "metadata": '{"source":"procedure-steering-input"}',
                        "createdAt": "2026-05-02T15:02:00.000Z",
                    },
                ],
                "nextToken": None,
            }
        }
    }
    recorder = ProcedureChatRecorder(client, "proc-1")

    result = recorder.get_steering_messages(
        after="2026-05-02T14:00:00.000Z",
        agent_name="report_writer",
        limit=10,
    )

    assert result["watermark"] == "2026-05-02T15:00:00.000Z"
    assert result["messages"] == [
        {
            "id": "msg-1",
            "account_id": "acct-1",
            "session_id": "sess-1",
            "procedure_id": "proc-1",
            "created_at": "2026-05-02T15:00:00.000Z",
            "content": "Emphasize contradictions in the summary.",
            "metadata": {"source": "procedure-steering-input", "scope": "all_agents"},
        }
    ]
    variables = client.execute.call_args.args[1]
    assert variables["procedureId"] == "proc-1"
    assert variables["createdAt"] == {"gt": "2026-05-02T14:00:00.000Z"}


def test_get_latest_console_trigger_message_prefers_dispatch_task(monkeypatch):
    monkeypatch.setenv("PLEXUS_DISPATCH_TASK_ID", "task-dispatch-2")
    client = Mock()
    client.execute.side_effect = [
        {
            "data": {
                "getTask": {
                    "id": "task-dispatch-2",
                    "accountId": "acct-11",
                    "target": "procedure/run/proc-11",
                    "metadata": "{\"console_chat\": {\"trigger_message_id\": \"msg-999\"}}",
                }
            }
        },
        {"data": {"getChatMessage": {"id": "msg-999", "role": "USER", "content": "Dispatch prompt"}}},
    ]
    recorder = ProcedureChatRecorder(client, "proc-11")

    message = recorder.get_latest_console_trigger_message(account_id="acct-11")

    assert message == "Dispatch prompt"


def test_get_latest_console_trigger_message_prefers_inline_trigger_content():
    client = Mock()
    client.execute.return_value = {
        "data": {
            "listTaskByAccountIdAndUpdatedAt": {
                "items": [
                    {
                        "id": "task-11-inline",
                        "target": "procedure/proc-11-inline",
                        "status": "PENDING",
                        "updatedAt": "2026-03-29T02:00:00.000Z",
                        "metadata": "{\"console_chat\": {\"trigger_message_id\": \"msg-inline\", \"trigger_message_content\": \"Inline prompt from metadata\"}}",
                    }
                ],
                "nextToken": None,
            }
        }
    }
    recorder = ProcedureChatRecorder(client, "proc-11-inline")

    message = recorder.get_latest_console_trigger_message(account_id="acct-11-inline")

    assert message == "Inline prompt from metadata"
    assert client.execute.call_count == 1


def test_get_latest_console_trigger_message_uses_dispatch_task_when_account_context_mismatches(monkeypatch):
    monkeypatch.setenv("PLEXUS_DISPATCH_TASK_ID", "task-dispatch-mismatch")
    client = Mock()
    client.execute.side_effect = [
        {
            "data": {
                "getTask": {
                    "id": "task-dispatch-mismatch",
                    "accountId": "acct-real",
                    "target": "procedure/run/proc-11b",
                    "metadata": "{\"console_chat\": {\"trigger_message_id\": \"msg-1000\"}}",
                }
            }
        },
        {"data": {"getChatMessage": {"id": "msg-1000", "role": "USER", "content": "Current dispatch prompt"}}},
    ]
    recorder = ProcedureChatRecorder(client, "proc-11b")

    message = recorder.get_latest_console_trigger_message(account_id="acct-stale")

    assert message == "Current dispatch prompt"
    for call_args, _ in client.execute.call_args_list:
        if call_args:
            assert "listTaskByAccountIdAndUpdatedAt" not in call_args[0]


def test_get_console_session_history_returns_filtered_messages():
    client = Mock()
    client.execute.side_effect = [
        {
            "data": {
                "listTaskByAccountIdAndUpdatedAt": {
                    "items": [
                        {
                            "id": "task-12",
                            "target": "procedure/proc-12",
                            "status": "PENDING",
                            "updatedAt": "2026-03-29T01:00:00.000Z",
                            "metadata": "{\"console_chat\": {\"session_id\": \"session-12\"}}",
                        }
                    ],
                    "nextToken": None,
                }
            }
        },
        {
            "data": {
                "listChatMessageBySessionIdAndCreatedAt": {
                    "items": [
                        {
                            "id": "m1",
                            "role": "USER",
                            "messageType": "MESSAGE",
                            "content": "Pick a random number.",
                            "humanInteraction": "CHAT",
                            "sequenceNumber": 1,
                        },
                        {
                            "id": "m2",
                            "role": "ASSISTANT",
                            "messageType": "MESSAGE",
                            "content": "How about 7?",
                            "humanInteraction": "CHAT_ASSISTANT",
                            "sequenceNumber": 2,
                        },
                        {
                            "id": "m3",
                            "role": "ASSISTANT",
                            "messageType": "MESSAGE",
                            "content": "Assistant turn completed.",
                            "humanInteraction": "CHAT_ASSISTANT",
                            "sequenceNumber": 3,
                        },
                        {
                            "id": "m4",
                            "role": "ASSISTANT",
                            "messageType": "TOOL_CALL",
                            "content": "Tool invocation",
                            "humanInteraction": "INTERNAL",
                            "sequenceNumber": 4,
                        },
                    ],
                    "nextToken": None,
                }
            }
        },
    ]
    recorder = ProcedureChatRecorder(client, "proc-12")

    history = recorder.get_console_session_history(account_id="acct-12")

    assert history == [
        {"role": "USER", "content": "Pick a random number."},
        {"role": "ASSISTANT", "content": "How about 7?"},
    ]


def test_get_console_session_history_uses_client_snapshot_when_server_history_is_stale(monkeypatch):
    monkeypatch.setenv("PLEXUS_DISPATCH_TASK_ID", "task-dispatch-snapshot")
    client = Mock()
    metadata = (
        "{\"console_chat\": {"
        "\"session_id\": \"session-13\", "
        "\"trigger_message_content\": \"Multiply it by three.\", "
        "\"instrumentation\": {"
        "\"client_history_snapshot\": ["
        "{\"role\": \"USER\", \"content\": \"Pick a random number.\"},"
        "{\"role\": \"ASSISTANT\", \"content\": \"Here's a random number: 27.\"},"
        "{\"role\": \"USER\", \"content\": \"Multiply it by three.\"}"
        "]"
        "}"
        "}}"
    )
    client.execute.side_effect = [
        {
            "data": {
                "getTask": {
                    "id": "task-dispatch-snapshot",
                    "accountId": "acct-13",
                    "target": "procedure/run/proc-13",
                    "metadata": metadata,
                }
            }
        },
        {
            "data": {
                "listChatMessageBySessionIdAndCreatedAt": {
                    "items": [
                        {
                            "id": "m-latest-user",
                            "role": "USER",
                            "messageType": "MESSAGE",
                            "content": "Multiply it by three.",
                        }
                    ],
                    "nextToken": None,
                }
            }
        },
        {
            "data": {
                "getTask": {
                    "id": "task-dispatch-snapshot",
                    "accountId": "acct-13",
                    "target": "procedure/run/proc-13",
                    "metadata": metadata,
                }
            }
        },
    ]
    recorder = ProcedureChatRecorder(client, "proc-13")

    history = recorder.get_console_session_history(account_id="acct-13")

    assert history == [
        {"role": "USER", "content": "Pick a random number."},
        {"role": "ASSISTANT", "content": "Here's a random number: 27."},
        {"role": "USER", "content": "Multiply it by three."},
    ]


def test_get_console_session_history_prefers_snapshot_over_db_when_both_exist(monkeypatch):
    monkeypatch.setenv("PLEXUS_DISPATCH_TASK_ID", "task-dispatch-snapshot-preferred")
    client = Mock()
    metadata = (
        "{\"console_chat\": {"
        "\"session_id\": \"session-14\", "
        "\"trigger_message_content\": \"Multiply that by three.\", "
        "\"instrumentation\": {"
        "\"client_history_snapshot\": ["
        "{\"role\": \"USER\", \"content\": \"Pick a random number.\"},"
        "{\"role\": \"ASSISTANT\", \"content\": \"How about the number 7?\"},"
        "{\"role\": \"USER\", \"content\": \"Multiply that by three.\"}"
        "]"
        "}"
        "}}"
    )
    client.execute.side_effect = [
        {
            "data": {
                "getTask": {
                    "id": "task-dispatch-snapshot-preferred",
                    "accountId": "acct-14",
                    "target": "procedure/run/proc-14",
                    "metadata": metadata,
                }
            }
        },
        {
            "data": {
                "listChatMessageBySessionIdAndCreatedAt": {
                    "items": [
                        {
                            "id": "old-user",
                            "role": "USER",
                            "messageType": "MESSAGE",
                            "content": "Old question",
                        },
                        {
                            "id": "old-assistant",
                            "role": "ASSISTANT",
                            "messageType": "MESSAGE",
                            "content": "Old answer",
                        },
                    ],
                    "nextToken": None,
                }
            }
        },
        {
            "data": {
                "getTask": {
                    "id": "task-dispatch-snapshot-preferred",
                    "accountId": "acct-14",
                    "target": "procedure/run/proc-14",
                    "metadata": metadata,
                }
            }
        },
    ]
    recorder = ProcedureChatRecorder(client, "proc-14")

    history = recorder.get_console_session_history(account_id="acct-14")

    assert history == [
        {"role": "USER", "content": "Pick a random number."},
        {"role": "ASSISTANT", "content": "How about the number 7?"},
        {"role": "USER", "content": "Multiply that by three."},
    ]


def test_get_console_session_history_prefers_db_when_snapshot_lacks_assistant_context(monkeypatch):
    monkeypatch.setenv("PLEXUS_DISPATCH_TASK_ID", "task-dispatch-snapshot-thin")
    client = Mock()
    metadata = (
        "{\"console_chat\": {"
        "\"session_id\": \"session-15\", "
        "\"trigger_message_content\": \"Multiply that by three.\", "
        "\"instrumentation\": {"
        "\"client_history_snapshot\": ["
        "{\"role\": \"USER\", \"content\": \"Multiply that by three.\"}"
        "]"
        "}"
        "}}"
    )
    client.execute.side_effect = [
        {
            "data": {
                "getTask": {
                    "id": "task-dispatch-snapshot-thin",
                    "accountId": "acct-15",
                    "target": "procedure/run/proc-15",
                    "metadata": metadata,
                }
            }
        },
        {
            "data": {
                "listChatMessageBySessionIdAndCreatedAt": {
                    "items": [
                        {
                            "id": "u1",
                            "role": "USER",
                            "messageType": "MESSAGE",
                            "content": "Pick a random number.",
                        },
                        {
                            "id": "a1",
                            "role": "ASSISTANT",
                            "messageType": "MESSAGE",
                            "content": "How about the number 7?",
                        },
                        {
                            "id": "u2",
                            "role": "USER",
                            "messageType": "MESSAGE",
                            "content": "Multiply that by three.",
                        },
                    ],
                    "nextToken": None,
                }
            }
        },
        {
            "data": {
                "getTask": {
                    "id": "task-dispatch-snapshot-thin",
                    "accountId": "acct-15",
                    "target": "procedure/run/proc-15",
                    "metadata": metadata,
                }
            }
        },
    ]
    recorder = ProcedureChatRecorder(client, "proc-15")

    history = recorder.get_console_session_history(account_id="acct-15")

    assert history == [
        {"role": "USER", "content": "Pick a random number."},
        {"role": "ASSISTANT", "content": "How about the number 7?"},
        {"role": "USER", "content": "Multiply that by three."},
    ]


def test_get_console_session_history_merges_truncated_snapshot_with_db(monkeypatch):
    monkeypatch.setenv("PLEXUS_DISPATCH_TASK_ID", "task-dispatch-snapshot-merge")
    client = Mock()
    metadata = (
        "{\"console_chat\": {"
        "\"session_id\": \"session-16\", "
        "\"trigger_message_content\": \"Multiply that by three.\", "
        "\"instrumentation\": {"
        "\"client_history_snapshot\": ["
        "{\"role\": \"USER\", \"content\": \"Pick a random number.\"},"
        "{\"role\": \"ASSISTANT\", \"content\": \"Sure! Here\\u2019s\"},"
        "{\"role\": \"USER\", \"content\": \"Multiply that by three.\"}"
        "]"
        "}"
        "}}"
    )
    client.execute.side_effect = [
        {
            "data": {
                "getTask": {
                    "id": "task-dispatch-snapshot-merge",
                    "accountId": "acct-16",
                    "target": "procedure/run/proc-16",
                    "metadata": metadata,
                }
            }
        },
        {
            "data": {
                "listChatMessageBySessionIdAndCreatedAt": {
                    "items": [
                        {
                            "id": "u1",
                            "role": "USER",
                            "messageType": "MESSAGE",
                            "content": "Pick a random number.",
                        },
                        {
                            "id": "a1",
                            "role": "ASSISTANT",
                            "messageType": "MESSAGE",
                            "content": "Sure! Here’s a random number: 27.",
                        },
                        {
                            "id": "u2",
                            "role": "USER",
                            "messageType": "MESSAGE",
                            "content": "Multiply that by three.",
                        },
                    ],
                    "nextToken": None,
                }
            }
        },
        {
            "data": {
                "getTask": {
                    "id": "task-dispatch-snapshot-merge",
                    "accountId": "acct-16",
                    "target": "procedure/run/proc-16",
                    "metadata": metadata,
                }
            }
        },
    ]
    recorder = ProcedureChatRecorder(client, "proc-16")

    history = recorder.get_console_session_history(account_id="acct-16")

    assert history == [
        {"role": "USER", "content": "Pick a random number."},
        {"role": "ASSISTANT", "content": "Sure! Here’s a random number: 27."},
        {"role": "USER", "content": "Multiply that by three."},
    ]


@pytest.mark.asyncio
async def test_start_session_reuses_waiting_session_and_continues_sequence():
    client = Mock()
    client.execute.side_effect = [
        {"data": {"getProcedure": {"accountId": "acct-1"}}},
        {"data": {"getProcedure": {"status": "WAITING_FOR_HUMAN", "waitingOnMessageId": "pending-1"}}},
        {"data": {"getChatMessage": {"id": "pending-1", "sessionId": "session-1"}}},
        {"data": {"listChatMessageBySessionIdAndCreatedAt": {"items": [{"id": "msg-7", "sequenceNumber": 7}]}}},
    ]
    recorder = ProcedureChatRecorder(client, "proc-4")

    session_id = await recorder.start_session({})

    assert session_id == "session-1"
    assert recorder.session_id == "session-1"
    assert recorder.account_id == "acct-1"
    assert recorder.sequence_number == 7
    for call_args, _ in client.execute.call_args_list:
        if call_args:
            assert "createChatSession" not in call_args[0]


@pytest.mark.asyncio
async def test_start_session_reuses_console_session_from_task_metadata():
    client = Mock()
    client.execute.side_effect = [
        {"data": {"getProcedure": {"accountId": "acct-2"}}},
        {"data": {"getProcedure": {"status": "COMPLETED", "waitingOnMessageId": None}}},
        {
            "data": {
                "listTaskByAccountIdAndUpdatedAt": {
                    "items": [
                        {
                            "id": "task-1",
                            "target": "procedure/proc-5",
                            "status": "PENDING",
                            "updatedAt": "2026-03-23T18:00:00.000Z",
                            "metadata": "{\"console_chat\": {\"session_id\": \"session-from-task\"}}",
                        }
                    ],
                    "nextToken": None,
                }
            }
        },
        {"data": {"listChatMessageBySessionIdAndCreatedAt": {"items": [{"id": "msg-3", "sequenceNumber": 3}]}}},
    ]
    recorder = ProcedureChatRecorder(client, "proc-5")

    session_id = await recorder.start_session({})

    assert session_id == "session-from-task"
    assert recorder.session_id == "session-from-task"
    assert recorder.account_id == "acct-2"
    assert recorder.sequence_number == 3
    for call_args, _ in client.execute.call_args_list:
        if call_args:
            assert "createChatSession" not in call_args[0]


@pytest.mark.asyncio
async def test_start_session_prefers_dispatch_task_console_metadata(monkeypatch):
    monkeypatch.setenv("PLEXUS_DISPATCH_TASK_ID", "task-dispatch-1")
    client = Mock()
    client.execute.side_effect = [
        {"data": {"getProcedure": {"accountId": "acct-2"}}},
        {"data": {"getProcedure": {"status": "COMPLETED", "waitingOnMessageId": None}}},
        {
            "data": {
                "getTask": {
                    "id": "task-dispatch-1",
                    "accountId": "acct-2",
                    "target": "procedure/run/proc-5a",
                    "metadata": "{\"console_chat\": {\"session_id\": \"session-from-dispatch-task\"}}",
                }
            }
        },
        {"data": {"listChatMessageBySessionIdAndCreatedAt": {"items": [{"id": "msg-4", "sequenceNumber": 4}]}}},
    ]
    recorder = ProcedureChatRecorder(client, "proc-5a")

    session_id = await recorder.start_session({})

    assert session_id == "session-from-dispatch-task"
    assert recorder.session_id == "session-from-dispatch-task"
    assert recorder.account_id == "acct-2"
    assert recorder.sequence_number == 4
    for call_args, _ in client.execute.call_args_list:
        if call_args:
            assert "listTaskByAccountIdAndUpdatedAt" not in call_args[0]


@pytest.mark.asyncio
async def test_start_session_uses_dispatch_task_console_metadata_when_account_resolution_is_stale(monkeypatch):
    monkeypatch.setenv("PLEXUS_DISPATCH_TASK_ID", "task-dispatch-stale-account")
    client = Mock()
    client._resolve_account_id.return_value = "acct-stale-context"
    client.execute.side_effect = [
        {"data": {"getProcedure": None}},
        {"data": {"getProcedure": {"status": "COMPLETED", "waitingOnMessageId": None}}},
        {
            "data": {
                "getTask": {
                    "id": "task-dispatch-stale-account",
                    "accountId": "acct-real",
                    "target": "procedure/run/proc-5b",
                    "metadata": "{\"console_chat\": {\"session_id\": \"session-from-dispatch-mismatch\"}}",
                }
            }
        },
        {"data": {"listChatMessageBySessionIdAndCreatedAt": {"items": [{"id": "msg-5", "sequenceNumber": 5}]}}},
    ]
    recorder = ProcedureChatRecorder(client, "proc-5b")

    session_id = await recorder.start_session({})

    assert session_id == "session-from-dispatch-mismatch"
    assert recorder.session_id == "session-from-dispatch-mismatch"
    assert recorder.account_id == "acct-stale-context"
    assert recorder.sequence_number == 5
    for call_args, _ in client.execute.call_args_list:
        if call_args:
            assert "listTaskByAccountIdAndUpdatedAt" not in call_args[0]


@pytest.mark.asyncio
async def test_start_session_creates_console_category_when_console_trigger_missing_session_id():
    client = Mock()
    client.execute.side_effect = [
        {"data": {"getProcedure": {"accountId": "acct-3"}}},
        {"data": {"getProcedure": {"status": "COMPLETED", "waitingOnMessageId": None}}},
        {
            "data": {
                "listTaskByAccountIdAndUpdatedAt": {
                    "items": [
                        {
                            "id": "task-2",
                            "target": "procedure/proc-6",
                            "status": "PENDING",
                            "updatedAt": "2026-03-23T19:00:00.000Z",
                            "metadata": "{\"console_chat\": {\"trigger_message_id\": \"msg-1\"}}",
                        }
                    ],
                    "nextToken": None,
                }
            }
        },
        {"data": {"createChatSession": {"id": "session-new", "status": "ACTIVE", "createdAt": "2026-03-23T19:00:10.000Z"}}},
    ]
    recorder = ProcedureChatRecorder(client, "proc-6")

    session_id = await recorder.start_session({})

    assert session_id == "session-new"
    assert recorder.session_id == "session-new"
    assert recorder.account_id == "acct-3"
    create_call = client.execute.call_args_list[-1]
    assert "mutation CreateChatSession" in create_call.args[0]
    assert create_call.args[1]["input"]["category"] == "Console"


@pytest.mark.asyncio
async def test_start_session_ignores_stale_console_metadata_when_latest_task_is_not_console():
    client = Mock()
    client.execute.side_effect = [
        {"data": {"getProcedure": {"accountId": "acct-4"}}},
        {"data": {"getProcedure": {"status": "COMPLETED", "waitingOnMessageId": None}}},
        {
            "data": {
                "listTaskByAccountIdAndUpdatedAt": {
                    "items": [
                        {
                            "id": "task-newest",
                            "target": "procedure/proc-7",
                            "status": "PENDING",
                            "updatedAt": "2026-03-23T20:00:00.000Z",
                            "metadata": "{}",
                        },
                        {
                            "id": "task-older",
                            "target": "procedure/proc-7",
                            "status": "PENDING",
                            "updatedAt": "2026-03-23T19:00:00.000Z",
                            "metadata": "{\"console_chat\": {\"session_id\": \"session-stale\"}}",
                        },
                    ],
                    "nextToken": None,
                }
            }
        },
        {"data": {"createChatSession": {"id": "session-fresh", "status": "ACTIVE", "createdAt": "2026-03-23T20:00:10.000Z"}}},
    ]
    recorder = ProcedureChatRecorder(client, "proc-7")

    session_id = await recorder.start_session({})

    assert session_id == "session-fresh"
    assert recorder.session_id == "session-fresh"
    assert recorder.account_id == "acct-4"
    create_call = client.execute.call_args_list[-1]
    assert "mutation CreateChatSession" in create_call.args[0]
    assert create_call.args[1]["input"]["category"] == "Hypothesize"


@pytest.mark.asyncio
async def test_end_session_supports_legacy_status_positional_call():
    client = Mock()
    client.execute.return_value = {"data": {"updateChatSession": {"id": "session-9"}}}
    recorder = ProcedureChatRecorder(client, "proc-8")
    recorder.session_id = "session-9"

    ok = await recorder.end_session("COMPLETED")

    assert ok is True
    mutation_call = client.execute.call_args_list[-1]
    assert mutation_call.args[1]["input"]["id"] == "session-9"
    assert mutation_call.args[1]["input"]["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_end_session_supports_tactus_signature_with_session_id():
    client = Mock()
    client.execute.return_value = {"data": {"updateChatSession": {"id": "session-10"}}}
    recorder = ProcedureChatRecorder(client, "proc-9")
    recorder.session_id = "session-current"

    ok = await recorder.end_session("session-10", status="FAILED")

    assert ok is True
    mutation_call = client.execute.call_args_list[-1]
    assert mutation_call.args[1]["input"]["id"] == "session-10"
    assert mutation_call.args[1]["input"]["status"] == "ERROR"


@pytest.mark.asyncio
async def test_record_message_uses_chat_stream_retry_policy():
    client = Mock()
    client.execute.return_value = {
        "createChatMessage": {
            "id": "msg-1",
            "sequenceNumber": 1,
            "createdAt": "2026-03-29T02:00:00.000Z",
        }
    }
    recorder = ProcedureChatRecorder(client, "proc-write-1")
    recorder.session_id = "session-1"
    recorder.account_id = "acct-1"

    message_id = await recorder.record_message("ASSISTANT", "hello world")

    assert message_id == "msg-1"
    assert client.execute.call_args.kwargs["retry_policy"] == CHAT_STREAM_WRITE_RETRY_POLICY_NAME
    message_input = client.execute.call_args.args[1]["input"]
    assert message_input["responseTarget"] == "proc-write-1"
    assert message_input["responseStatus"] == "COMPLETED"


def test_get_steering_messages_returns_flat_filtered_rows():
    client = Mock()
    client.execute.return_value = {
        "data": {
            "listChatMessageByProcedureIdAndCreatedAt": {
                "items": [
                    {
                        "id": "m-steer",
                        "accountId": "acct-1",
                        "sessionId": "sess-1",
                        "procedureId": "proc-1",
                        "role": "USER",
                        "content": "Prioritize reviewer contradiction analysis.",
                        "messageType": "MESSAGE",
                        "humanInteraction": "CHAT",
                        "responseStatus": "COMPLETED",
                        "metadata": '{"source": "procedure-steering-input", "scope": "all_agents"}',
                        "createdAt": "2026-04-01T00:00:02.000Z",
                    },
                    {
                        "id": "m-console",
                        "accountId": "acct-1",
                        "sessionId": "sess-1",
                        "procedureId": "proc-1",
                        "role": "USER",
                        "content": "Console request",
                        "messageType": "MESSAGE",
                        "humanInteraction": "CHAT",
                        "responseStatus": "COMPLETED",
                        "metadata": '{"source": "console-prompt-input"}',
                        "createdAt": "2026-04-01T00:00:03.000Z",
                    },
                    {
                        "id": "m-assistant",
                        "accountId": "acct-1",
                        "sessionId": "sess-1",
                        "procedureId": "proc-1",
                        "role": "ASSISTANT",
                        "content": "Assistant text",
                        "messageType": "MESSAGE",
                        "humanInteraction": "CHAT_ASSISTANT",
                        "responseStatus": "COMPLETED",
                        "metadata": '{"source": "procedure-steering-input", "scope": "all_agents"}',
                        "createdAt": "2026-04-01T00:00:04.000Z",
                    },
                ],
                "nextToken": None,
            }
        }
    }
    recorder = ProcedureChatRecorder(client, "proc-1")

    result = recorder.get_steering_messages(
        after="2026-04-01T00:00:00.000Z",
        agent_name="report_writer",
        limit=20,
    )

    assert result["watermark"] == "2026-04-01T00:00:02.000Z"
    assert result["messages"] == [
        {
            "id": "m-steer",
            "account_id": "acct-1",
            "session_id": "sess-1",
            "procedure_id": "proc-1",
            "created_at": "2026-04-01T00:00:02.000Z",
            "content": "Prioritize reviewer contradiction analysis.",
            "metadata": {"source": "procedure-steering-input", "scope": "all_agents"},
        }
    ]
    variables = client.execute.call_args.args[1]
    assert variables["procedureId"] == "proc-1"
    assert variables["createdAt"] == {"gt": "2026-04-01T00:00:00.000Z"}
