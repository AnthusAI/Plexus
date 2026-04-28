#!/usr/bin/env python3
"""Chat session MCP tools (read + send)."""

import logging
from typing import Any, Dict, Optional

from fastmcp import FastMCP

from plexus.chat.session_ops import (
    get_latest_chat_session,
    list_session_messages,
    resolve_account_id,
    send_chat_message,
)
from plexus.cli.shared.client_utils import create_client

logger = logging.getLogger(__name__)


def register_chat_tools(mcp: FastMCP):
    """Register chat tools with the MCP server."""

    @mcp.tool()
    async def plexus_chat_last(
        account_identifier: Optional[str] = None,
        procedure_id: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        messages_limit: int = 0,
        include_internal: bool = False,
    ) -> Dict[str, Any]:
        """
        Get the most recent chat session for an account, optionally filtered.
        """
        try:
            client = create_client()
            account_id = resolve_account_id(client, account_identifier)
            session = get_latest_chat_session(
                client,
                account_id=account_id,
                procedure_id=procedure_id,
                status=status,
                category=category,
            )
            if not session:
                return {"account_id": account_id, "found": False}

            payload: Dict[str, Any] = {
                "account_id": account_id,
                "found": True,
                "session": session,
            }
            if messages_limit > 0:
                payload["messages"] = list_session_messages(
                    client,
                    session_id=session["id"],
                    limit=messages_limit,
                    offset=0,
                    include_internal=include_internal,
                )
            return payload
        except Exception as exc:
            logger.error("plexus_chat_last failed: %s", exc, exc_info=True)
            return {"error": str(exc)}

    @mcp.tool()
    async def plexus_chat_messages(
        session_id: str,
        limit: int = 50,
        offset: int = 0,
        include_internal: bool = False,
    ) -> Dict[str, Any]:
        """
        List messages for a chat session.
        """
        try:
            client = create_client()
            return list_session_messages(
                client,
                session_id=session_id,
                limit=limit,
                offset=offset,
                include_internal=include_internal,
            )
        except Exception as exc:
            logger.error("plexus_chat_messages failed: %s", exc, exc_info=True)
            return {"error": str(exc)}

    @mcp.tool()
    async def plexus_chat_send(
        session_id: str,
        text: str,
        mode: str = "chat",
        parent_message_id: Optional[str] = None,
        response_target: str = "cloud",
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a USER chat message or HITL RESPONSE message.
        """
        try:
            client = create_client()
            return send_chat_message(
                client,
                session_id=session_id,
                text=text,
                mode=mode,
                parent_message_id=parent_message_id,
                response_target=response_target,
                model=model,
            )
        except Exception as exc:
            logger.error("plexus_chat_send failed: %s", exc, exc_info=True)
            return {"error": str(exc)}

