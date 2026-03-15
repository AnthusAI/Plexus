"""
Plexus Trace Sink for Tactus trace event persistence.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _event_field(event: Any, *names: str, default: Any = None) -> Any:
    """Get a field from object-like or dict-like events."""
    for name in names:
        if isinstance(event, dict) and name in event:
            return event.get(name)
        if hasattr(event, name):
            return getattr(event, name)
    return default


class PlexusTraceSink:
    """Persist Tactus trace records into Plexus ChatSession/ChatMessage models."""

    def __init__(self, chat_recorder):
        self.chat_recorder = chat_recorder
        self.session_id: Optional[str] = None

    async def start_session(self, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        self.session_id = await self.chat_recorder.start_session(context)
        return self.session_id

    async def record(self, event: Any) -> Optional[str]:
        if not self.session_id:
            self.session_id = await self.chat_recorder.start_session()
            if not self.session_id:
                logger.warning("TraceSink could not create chat session; dropping event")
                return None

        raw_kind = _event_field(event, "kind", "event_type", default="")
        event_kind = str(raw_kind or "").strip().upper()

        message_type = "MESSAGE"
        if event_kind == "TOOL_CALL":
            message_type = "TOOL_CALL"
        elif event_kind == "TOOL_RESPONSE":
            message_type = "TOOL_RESPONSE"

        raw_role = _event_field(event, "role")
        if not raw_role:
            if event_kind in {"TOOL_CALL", "TOOL_RESPONSE"} or _event_field(event, "agent_name"):
                raw_role = "ASSISTANT"
            else:
                raw_role = "SYSTEM"

        role = str(raw_role).upper()
        if role not in {"USER", "ASSISTANT", "SYSTEM", "TOOL"}:
            role = "SYSTEM"

        content = _event_field(event, "content", "message", "chunk_text", "accumulated_text")
        if not content and event_kind == "TOOL_CALL":
            tool_name = _event_field(event, "tool_name")
            if tool_name:
                content = f"Tool call: {tool_name}"

        human_interaction = _event_field(event, "human_interaction", "classification", default="INTERNAL")
        if hasattr(human_interaction, "value"):
            human_interaction = human_interaction.value

        return await self.chat_recorder.record_message(
            role=role,
            content=str(content or ""),
            message_type=message_type,
            tool_name=_event_field(event, "tool_name"),
            tool_parameters=_event_field(event, "tool_parameters", "tool_args"),
            tool_response=_event_field(event, "tool_response", "tool_result"),
            human_interaction=str(human_interaction or "INTERNAL"),
            metadata=_event_field(event, "metadata"),
        )

    async def flush(self) -> None:
        return None

    async def end_session(self, status: str = "COMPLETED") -> None:
        if not self.session_id:
            return
        await self.chat_recorder.end_session(status=status)
        self.session_id = None
