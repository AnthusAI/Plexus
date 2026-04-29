import json
import pytest

from plexus.chat import session_ops

pytestmark = pytest.mark.unit


class _StubClient:
    def __init__(self):
        self.calls = []
        self._responses = []

    def queue(self, response):
        self._responses.append(response)

    def execute(self, query, variables=None):
        self.calls.append({"query": query, "variables": variables or {}})
        if not self._responses:
            raise AssertionError("No queued response for execute call")
        return self._responses.pop(0)


def test_get_latest_chat_session_returns_most_recent_item():
    client = _StubClient()
    client.queue(
        {
            "data": {
                "listChatSessionByAccountIdAndUpdatedAt": {
                    "items": [
                        {"id": "sess-2", "updatedAt": "2026-04-28T02:00:00Z"},
                        {"id": "sess-1", "updatedAt": "2026-04-28T01:00:00Z"},
                    ],
                    "nextToken": None,
                }
            }
        }
    )

    session = session_ops.get_latest_chat_session(client, account_id="acct-1")
    assert session["id"] == "sess-2"
    variables = client.calls[0]["variables"]
    assert variables["accountId"] == "acct-1"
    assert variables["filter"] is None


def test_list_session_messages_filters_internal_and_orders_deterministically():
    client = _StubClient()
    client.queue(
        {
            "data": {
                "listChatMessageBySessionIdAndCreatedAt": {
                    "items": [
                        {
                            "id": "m2",
                            "sessionId": "sess-1",
                            "role": "ASSISTANT",
                            "humanInteraction": "CHAT_ASSISTANT",
                            "messageType": "MESSAGE",
                            "content": "b",
                            "metadata": "{}",
                            "createdAt": "2026-04-28T01:00:02Z",
                            "sequenceNumber": 2,
                        },
                        {
                            "id": "m-internal",
                            "sessionId": "sess-1",
                            "role": "TOOL",
                            "humanInteraction": "INTERNAL",
                            "messageType": "TOOL_CALL",
                            "content": "hidden",
                            "metadata": "{}",
                            "createdAt": "2026-04-28T01:00:01Z",
                            "sequenceNumber": 1,
                        },
                        {
                            "id": "m1",
                            "sessionId": "sess-1",
                            "role": "USER",
                            "humanInteraction": "CHAT",
                            "messageType": "MESSAGE",
                            "content": "a",
                            "metadata": "{}",
                            "createdAt": "2026-04-28T01:00:00Z",
                            "sequenceNumber": 0,
                        },
                    ],
                    "nextToken": None,
                }
            }
        }
    )

    payload = session_ops.list_session_messages(
        client,
        session_id="sess-1",
        limit=10,
        offset=0,
        include_internal=False,
    )
    assert [item["id"] for item in payload["items"]] == ["m1", "m2"]


def test_send_chat_message_sets_pending_status_and_model_metadata(monkeypatch):
    monkeypatch.setattr(session_ops, "_utc_now_iso", lambda: "2026-04-28T03:00:00+00:00")

    client = _StubClient()
    client.queue(
        {
            "data": {
                "getChatSession": {
                    "id": "sess-1",
                    "accountId": "acct-1",
                    "procedureId": "proc-1",
                }
            }
        }
    )
    client.queue(
        {
            "data": {
                "createChatMessage": {
                    "id": "msg-1",
                    "sessionId": "sess-1",
                    "accountId": "acct-1",
                    "procedureId": "proc-1",
                    "role": "USER",
                    "humanInteraction": "CHAT",
                    "messageType": "MESSAGE",
                    "content": "hello",
                    "metadata": json.dumps({"model": {"id": "gpt-5.3"}}),
                    "responseTarget": "cloud",
                    "responseStatus": "PENDING",
                    "createdAt": "2026-04-28T03:00:00+00:00",
                }
            }
        }
    )

    result = session_ops.send_chat_message(
        client,
        session_id="sess-1",
        text="hello",
        mode="chat",
        response_target="cloud",
        model="gpt-5.3",
    )
    assert result["message"]["responseStatus"] == "PENDING"
    create_variables = client.calls[-1]["variables"]["input"]
    assert create_variables["responseTarget"] == "cloud"
    assert create_variables["responseStatus"] == "PENDING"
    assert json.loads(create_variables["metadata"])["model"]["id"] == "gpt-5.3"


def test_send_response_requires_pending_parent():
    client = _StubClient()
    client.queue({"data": {"getChatSession": {"id": "sess-1", "accountId": "acct-1"}}})
    client.queue(
        {
            "data": {
                "getChatMessage": {
                    "id": "parent-1",
                    "sessionId": "sess-1",
                    "humanInteraction": "CHAT_ASSISTANT",
                    "metadata": "{}",
                }
            }
        }
    )

    with pytest.raises(ValueError, match="not a pending HITL request"):
        session_ops.send_chat_message(
            client,
            session_id="sess-1",
            text="approve",
            mode="response",
            parent_message_id="parent-1",
        )


def test_send_response_derives_control_metadata(monkeypatch):
    monkeypatch.setattr(session_ops, "_utc_now_iso", lambda: "2026-04-28T03:05:00+00:00")

    client = _StubClient()
    client.queue({"data": {"getChatSession": {"id": "sess-1", "accountId": "acct-1", "procedureId": "proc-1"}}})
    client.queue(
        {
            "data": {
                "getChatMessage": {
                    "id": "parent-1",
                    "sessionId": "sess-1",
                    "accountId": "acct-1",
                    "procedureId": "proc-1",
                    "humanInteraction": "PENDING_APPROVAL",
                    "metadata": json.dumps(
                        {
                            "control": {
                                "request_id": "req-1",
                                "procedure_id": "proc-1",
                                "request_type": "approval",
                            }
                        }
                    ),
                }
            }
        }
    )
    client.queue(
        {
            "data": {
                "createChatMessage": {
                    "id": "resp-1",
                    "sessionId": "sess-1",
                    "role": "USER",
                    "humanInteraction": "RESPONSE",
                    "messageType": "MESSAGE",
                    "content": "{\"value\": true}",
                    "metadata": "{}",
                    "responseTarget": "cloud",
                    "responseStatus": "PENDING",
                    "createdAt": "2026-04-28T03:05:00+00:00",
                }
            }
        }
    )

    session_ops.send_chat_message(
        client,
        session_id="sess-1",
        text="approve",
        mode="response",
        parent_message_id="parent-1",
    )
    payload = client.calls[-1]["variables"]["input"]
    metadata = json.loads(payload["metadata"])
    assert payload["humanInteraction"] == "RESPONSE"
    assert payload["responseStatus"] == "PENDING"
    assert metadata["control"]["request_id"] == "req-1"
    assert metadata["control"]["value"] is True


def test_resolve_account_id_accepts_uuid_without_lookup():
    account_id = "9c929f25-a91f-4db7-8943-5aa93498b8e9"
    client = _StubClient()
    assert session_ops.resolve_account_id(client, account_id) == account_id
    assert client.calls == []


def test_resolve_account_id_uses_account_id_env(monkeypatch):
    account_id = "9c929f25-a91f-4db7-8943-5aa93498b8e9"
    monkeypatch.setenv("PLEXUS_ACCOUNT_ID", account_id)
    monkeypatch.delenv("PLEXUS_ACCOUNT_KEY", raising=False)
    client = _StubClient()
    assert session_ops.resolve_account_id(client) == account_id
    assert client.calls == []
