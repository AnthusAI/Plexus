"""
Plexus Trace Sink for Tactus trace event persistence.
"""

import logging
from datetime import datetime, timezone
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
        self.assistant_message_texts: list[str] = []
        self._active_stream_message_ids: Dict[str, str] = {}
        self._active_stream_texts: Dict[str, str] = {}

    async def start_session(self, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        self.session_id = await self.chat_recorder.start_session(context)
        return self.session_id

    def _iso_timestamp(self, value: Any) -> str:
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        if isinstance(value, str) and value.strip():
            return value
        return datetime.now(timezone.utc).isoformat()

    async def _ensure_session(self) -> bool:
        if self.session_id:
            return True

        recorder_session_id = getattr(self.chat_recorder, "session_id", None)
        if isinstance(recorder_session_id, str) and recorder_session_id:
            self.session_id = recorder_session_id
            return True

        self.session_id = await self.chat_recorder.start_session()
        return bool(self.session_id)

    async def _record_stream_chunk(self, event: Any) -> Optional[str]:
        agent_name = str(_event_field(event, "agent_name", default="assistant") or "assistant")
        chunk_text = str(_event_field(event, "chunk_text", default="") or "")
        accumulated_text = str(_event_field(event, "accumulated_text", default="") or "")
        if not accumulated_text:
            existing = self._active_stream_texts.get(agent_name, "")
            accumulated_text = f"{existing}{chunk_text}"
        if not accumulated_text:
            return None

        timestamp = self._iso_timestamp(_event_field(event, "timestamp"))
        metadata = {
            "streaming": {
                "state": "streaming",
                "agent_name": agent_name,
                "last_chunk_at": timestamp,
            }
        }

        message_id = self._active_stream_message_ids.get(agent_name)
        if message_id:
            updated = await self.chat_recorder.update_message(
                message_id=message_id,
                content=accumulated_text,
                metadata=metadata,
                human_interaction="CHAT_ASSISTANT",
            )
            if not updated:
                logger.warning("Failed updating streamed assistant message %s for %s", message_id, agent_name)
                return None
        else:
            message_id = await self.chat_recorder.record_message(
                role="ASSISTANT",
                content=accumulated_text,
                message_type="MESSAGE",
                human_interaction="CHAT_ASSISTANT",
                metadata=metadata,
            )
            if not message_id:
                logger.warning("Failed creating streamed assistant message for %s", agent_name)
                return None
            self._active_stream_message_ids[agent_name] = message_id

        self._active_stream_texts[agent_name] = accumulated_text
        return message_id

    async def _finalize_stream_for_agent(self, agent_name: str, timestamp: Any = None) -> Optional[str]:
        message_id = self._active_stream_message_ids.pop(agent_name, None)
        final_text = self._active_stream_texts.pop(agent_name, "")
        if not message_id:
            return None

        metadata = {
            "streaming": {
                "state": "complete",
                "agent_name": agent_name,
                "completed_at": self._iso_timestamp(timestamp),
            }
        }
        await self.chat_recorder.update_message(
            message_id=message_id,
            content=final_text or None,
            metadata=metadata,
            human_interaction="CHAT_ASSISTANT",
        )

        normalized = final_text.strip()
        if normalized:
            self.assistant_message_texts.append(normalized)

        return message_id

    async def record(self, event: Any) -> Optional[str]:
        if not await self._ensure_session():
            logger.warning("TraceSink could not create chat session; dropping event")
            return None

        raw_kind = _event_field(event, "kind", "event_type", default="")
        event_kind = str(raw_kind or "").strip().upper()
        event_type = str(_event_field(event, "event_type", default="") or "").strip().lower()

        if event_type in {"log", "cost", "execution_summary"}:
            return None

        if event_type == "agent_stream_chunk":
            return await self._record_stream_chunk(event)

        if event_type == "agent_turn":
            stage = str(_event_field(event, "stage", default="") or "").strip().lower()
            if stage == "completed":
                agent_name = str(_event_field(event, "agent_name", default="assistant") or "assistant")
                return await self._finalize_stream_for_agent(
                    agent_name=agent_name,
                    timestamp=_event_field(event, "timestamp"),
                )
            return None

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
        if not content and event_kind == "TOOL_RESPONSE":
            tool_name = _event_field(event, "tool_name")
            if tool_name:
                content = f"Tool response: {tool_name}"
        content_text = str(content or "")
        normalized_content = content_text.strip()

        if role == "ASSISTANT" and message_type == "MESSAGE":
            if normalized_content.lower() == "assistant turn completed.":
                logger.debug("Dropping placeholder assistant trace message: %s", normalized_content)
                return None
            if normalized_content:
                self.assistant_message_texts.append(normalized_content)

        human_interaction = _event_field(event, "human_interaction", "classification", default="INTERNAL")
        if hasattr(human_interaction, "value"):
            human_interaction = human_interaction.value

        return await self.chat_recorder.record_message(
            role=role,
            content=content_text,
            message_type=message_type,
            tool_name=_event_field(event, "tool_name"),
            tool_parameters=_event_field(event, "tool_parameters", "tool_args"),
            tool_response=_event_field(event, "tool_response", "tool_result"),
            human_interaction=str(human_interaction or "INTERNAL"),
            metadata=_event_field(event, "metadata"),
        )

    async def flush(self) -> None:
        if not self._active_stream_message_ids:
            return None
        pending_agents = list(self._active_stream_message_ids.keys())
        for agent_name in pending_agents:
            await self._finalize_stream_for_agent(agent_name, timestamp=None)
        return None

    async def end_session(self, status: str = "COMPLETED") -> None:
        if not self.session_id:
            return
        await self.flush()
        await self.chat_recorder.end_session(status=status)
        self.session_id = None
