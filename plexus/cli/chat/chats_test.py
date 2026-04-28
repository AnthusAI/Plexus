from click.testing import CliRunner

from plexus.cli.chat.chats import chat


def test_chat_last_uses_default_account_and_prints_session(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("plexus.cli.chat.chats.create_client", lambda: object())
    monkeypatch.setattr("plexus.cli.chat.chats.resolve_account_id", lambda _c, _a: "acct-1")
    monkeypatch.setattr(
        "plexus.cli.chat.chats.get_latest_chat_session",
        lambda *_args, **_kwargs: {"id": "sess-1", "accountId": "acct-1", "updatedAt": "2026-04-28T00:00:00Z"},
    )

    result = runner.invoke(chat, ["last", "--output", "json"])
    assert result.exit_code == 0
    assert '"id": "sess-1"' in result.output


def test_chat_messages_invokes_shared_message_listing(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("plexus.cli.chat.chats.create_client", lambda: object())
    monkeypatch.setattr(
        "plexus.cli.chat.chats.list_session_messages",
        lambda *_args, **_kwargs: {"sessionId": "sess-1", "offset": 0, "limit": 2, "count": 1, "nextToken": None, "items": []},
    )

    result = runner.invoke(chat, ["messages", "--session-id", "sess-1", "--output", "json"])
    assert result.exit_code == 0
    assert '"sessionId": "sess-1"' in result.output


def test_chat_send_chat_mode_calls_shared_sender(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("plexus.cli.chat.chats.create_client", lambda: object())
    monkeypatch.setattr(
        "plexus.cli.chat.chats.send_chat_message",
        lambda *_args, **_kwargs: {"mode": "chat", "message": {"id": "msg-1", "sessionId": "sess-1"}},
    )

    result = runner.invoke(
        chat,
        ["send", "--session-id", "sess-1", "--text", "hello", "--output", "json"],
    )
    assert result.exit_code == 0
    assert '"mode": "chat"' in result.output


def test_chat_send_response_mode_requires_parent():
    runner = CliRunner()
    result = runner.invoke(
        chat,
        ["send", "--session-id", "sess-1", "--text", "approve", "--mode", "response"],
    )
    assert result.exit_code != 0
    assert "--parent-message-id is required" in result.output

