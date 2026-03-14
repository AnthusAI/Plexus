"""
Plexus Trace Sink for Tactus TraceEvent persistence.
"""

import logging
from typing import Any, Dict, Optional

from tactus.protocols.models import TraceEvent

logger = logging.getLogger(__name__)


class PlexusTraceSink:
    """Persist Tactus TraceEvent records into Plexus ChatSession/ChatMessage models."""

    def __init__(self, chat_recorder):
        self.chat_recorder = chat_recorder
        self.session_id: Optional[str] = None

    async def start_session(self, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        self.session_id = await self.chat_recorder.start_session(context)
        return self.session_id

    async def record(self, event: TraceEvent) -> Optional[str]:
        if not self.session_id:
            self.session_id = await self.chat_recorder.start_session()
            if not self.session_id:
                logger.warning("TraceSink could not create chat session; dropping event")
                return None

        message_type = "MESSAGE"
        if event.kind == "TOOL_CALL":
            message_type = "TOOL_CALL"
        elif event.kind == "TOOL_RESPONSE":
            message_type = "TOOL_RESPONSE"

        role = (event.role or "SYSTEM").upper()
        if role not in {"USER", "ASSISTANT", "SYSTEM", "TOOL"}:
            role = "SYSTEM"

        return await self.chat_recorder.record_message(
            role=role,
            content=event.content or "",
            message_type=message_type,
            tool_name=event.tool_name,
            tool_parameters=event.tool_parameters,
            tool_response=event.tool_response,
            human_interaction=event.human_interaction or "INTERNAL",
            metadata=event.metadata,
        )

    async def flush(self) -> None:
        return None

    async def end_session(self, status: str = "COMPLETED") -> None:
        if not self.session_id:
            return
        await self.chat_recorder.end_session(status=status)
        self.session_id = None
