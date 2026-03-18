from unittest.mock import Mock

import pytest

from plexus.cli.procedure.chat_recorder import ProcedureChatRecorder


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
