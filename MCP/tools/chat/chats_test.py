#!/usr/bin/env python3
"""Unit tests for chat MCP tools."""

import asyncio
from unittest.mock import Mock, patch

import pytest

pytestmark = pytest.mark.unit


def _register_tools():
    from tools.chat.chats import register_chat_tools

    mock_mcp = Mock()
    registered = {}

    def tool_decorator():
        def decorator(func):
            registered[func.__name__] = func
            return func

        return decorator

    mock_mcp.tool = tool_decorator
    register_chat_tools(mock_mcp)
    return registered


def test_chat_tool_registration():
    tools = _register_tools()
    assert "plexus_chat_last" in tools
    assert "plexus_chat_messages" in tools
    assert "plexus_chat_send" in tools


def test_plexus_chat_last_success():
    tools = _register_tools()
    tool = tools["plexus_chat_last"]
    with patch("tools.chat.chats.create_client", return_value=object()), patch(
        "tools.chat.chats.resolve_account_id", return_value="acct-1"
    ), patch(
        "tools.chat.chats.get_latest_chat_session", return_value={"id": "sess-1"}
    ):
        payload = asyncio.run(tool())
    assert payload["found"] is True
    assert payload["session"]["id"] == "sess-1"


def test_plexus_chat_messages_success():
    tools = _register_tools()
    tool = tools["plexus_chat_messages"]
    with patch("tools.chat.chats.create_client", return_value=object()), patch(
        "tools.chat.chats.list_session_messages",
        return_value={"sessionId": "sess-1", "items": [{"id": "m1"}], "count": 1},
    ):
        payload = asyncio.run(tool(session_id="sess-1"))
    assert payload["sessionId"] == "sess-1"
    assert payload["count"] == 1


def test_plexus_chat_send_success():
    tools = _register_tools()
    tool = tools["plexus_chat_send"]
    with patch("tools.chat.chats.create_client", return_value=object()), patch(
        "tools.chat.chats.send_chat_message",
        return_value={"mode": "chat", "message": {"id": "msg-1"}},
    ):
        payload = asyncio.run(tool(session_id="sess-1", text="hello"))
    assert payload["mode"] == "chat"
    assert payload["message"]["id"] == "msg-1"

