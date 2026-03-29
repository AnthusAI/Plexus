"""
Plexus Trace Sink for Tactus trace event persistence.
"""

import logging
import inspect
import os
import time
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


def _env_float(name: str, default: float, minimum: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = float(raw)
    except Exception:
        return default
    if parsed < minimum:
        return minimum
    return parsed


def _env_int(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except Exception:
        return default
    if parsed < minimum:
        return minimum
    return parsed


class PlexusTraceSink:
    """Persist Tactus trace records into Plexus ChatSession/ChatMessage models."""

    STREAM_UPDATE_MAX_INTERVAL_SECONDS = _env_float(
        "PLEXUS_STREAM_UPDATE_MAX_INTERVAL_SECONDS",
        0.35,
        0.05,
    )
    STREAM_UPDATE_MIN_CHARS_DELTA = _env_int(
        "PLEXUS_STREAM_UPDATE_MIN_CHARS_DELTA",
        20,
        1,
    )

    def __init__(self, chat_recorder):
        self.chat_recorder = chat_recorder
        self.session_id: Optional[str] = None
        self.assistant_message_texts: list[str] = []
        self._active_stream_message_ids: Dict[str, str] = {}
        self._active_stream_texts: Dict[str, str] = {}
        self._active_stream_last_persisted_texts: Dict[str, str] = {}
        self._active_stream_last_persisted_at: Dict[str, float] = {}
        self._active_stream_chunk_counts: Dict[str, int] = {}
        self._active_stream_first_chunk_received_at: Dict[str, str] = {}
        self._active_stream_first_chunk_persisted_at: Dict[str, str] = {}
        self._active_stream_last_chunk_received_at: Dict[str, str] = {}
        self._active_stream_prev_chunk_received_epoch_ms: Dict[str, float] = {}
        self._active_stream_inter_chunk_gap_sum_ms: Dict[str, float] = {}
        self._active_stream_inter_chunk_gap_max_ms: Dict[str, float] = {}
        self._active_stream_persist_update_counts: Dict[str, int] = {}
        self._active_stream_prev_persisted_epoch_ms: Dict[str, float] = {}
        self._active_stream_persist_gap_sum_ms: Dict[str, float] = {}
        self._active_stream_persist_gap_max_ms: Dict[str, float] = {}
        self._active_stream_last_persisted_at_iso: Dict[str, str] = {}
        self._console_dispatch_metadata: Optional[Dict[str, Any]] = None
        self._backend_execution_started_at: str = datetime.now(timezone.utc).isoformat()
        self._backend_runtime_execute_started_at: Optional[str] = None

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

    def mark_runtime_execute_started(self, value: Optional[str] = None) -> None:
        self._backend_runtime_execute_started_at = self._iso_timestamp(value)

    def _iso_to_epoch_ms(self, value: Optional[str]) -> Optional[float]:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).timestamp() * 1000.0
        except Exception:
            return None

    def _get_console_dispatch_metadata(self) -> Optional[Dict[str, Any]]:
        if isinstance(self._console_dispatch_metadata, dict):
            return self._console_dispatch_metadata
        getter = getattr(self.chat_recorder, "get_latest_console_chat_metadata", None)
        if not callable(getter):
            return None
        if inspect.iscoroutinefunction(getter):
            return None
        metadata = getter()
        if inspect.isawaitable(metadata):
            return None
        if isinstance(metadata, dict):
            self._console_dispatch_metadata = metadata
            return metadata
        return None

    def _mark_persisted_update(self, agent_name: str, persisted_at_iso: str) -> None:
        persisted_epoch_ms = self._iso_to_epoch_ms(persisted_at_iso)
        previous_persisted_epoch_ms = self._active_stream_prev_persisted_epoch_ms.get(agent_name)
        next_count = self._active_stream_persist_update_counts.get(agent_name, 0) + 1
        self._active_stream_persist_update_counts[agent_name] = next_count
        self._active_stream_last_persisted_at_iso[agent_name] = persisted_at_iso

        if persisted_epoch_ms is None:
            return
        if previous_persisted_epoch_ms is not None:
            gap_ms = max(0.0, persisted_epoch_ms - previous_persisted_epoch_ms)
            self._active_stream_persist_gap_sum_ms[agent_name] = (
                self._active_stream_persist_gap_sum_ms.get(agent_name, 0.0) + gap_ms
            )
            self._active_stream_persist_gap_max_ms[agent_name] = max(
                self._active_stream_persist_gap_max_ms.get(agent_name, 0.0),
                gap_ms,
            )
        self._active_stream_prev_persisted_epoch_ms[agent_name] = persisted_epoch_ms

    def _build_stream_timing_metadata(self, agent_name: str) -> Dict[str, Any]:
        chunk_count = self._active_stream_chunk_counts.get(agent_name, 0)
        gap_events = max(0, chunk_count - 1)
        gap_sum = self._active_stream_inter_chunk_gap_sum_ms.get(agent_name, 0.0)
        average_gap_ms = (gap_sum / gap_events) if gap_events > 0 else None
        persisted_update_count = self._active_stream_persist_update_counts.get(agent_name, 0)
        persisted_gap_events = max(0, persisted_update_count - 1)
        persisted_gap_sum = self._active_stream_persist_gap_sum_ms.get(agent_name, 0.0)
        persisted_average_gap_ms = (
            persisted_gap_sum / persisted_gap_events
        ) if persisted_gap_events > 0 else None
        dispatch_meta = self._get_console_dispatch_metadata() or {}
        dispatch_instrumentation = dispatch_meta.get("instrumentation") if isinstance(dispatch_meta, dict) else None

        return {
            "chunk_count": chunk_count,
            "first_chunk_received_at": self._active_stream_first_chunk_received_at.get(agent_name),
            "first_chunk_persisted_at": self._active_stream_first_chunk_persisted_at.get(agent_name),
            "last_chunk_received_at": self._active_stream_last_chunk_received_at.get(agent_name),
            "inter_chunk_average_ms": round(average_gap_ms, 2) if isinstance(average_gap_ms, (int, float)) else None,
            "inter_chunk_max_ms": round(self._active_stream_inter_chunk_gap_max_ms.get(agent_name, 0.0), 2) if gap_events > 0 else None,
            "persisted_update_count": persisted_update_count,
            "last_chunk_persisted_at": self._active_stream_last_persisted_at_iso.get(agent_name),
            "persisted_inter_update_average_ms": (
                round(persisted_average_gap_ms, 2)
                if isinstance(persisted_average_gap_ms, (int, float))
                else None
            ),
            "persisted_inter_update_max_ms": (
                round(self._active_stream_persist_gap_max_ms.get(agent_name, 0.0), 2)
                if persisted_gap_events > 0
                else None
            ),
            "backend_execution_started_at": self._backend_execution_started_at,
            "backend_runtime_execute_started_at": self._backend_runtime_execute_started_at,
            "dispatch_queued_at": dispatch_meta.get("queued_at") if isinstance(dispatch_meta, dict) else None,
            "dispatch_client_timing": dispatch_instrumentation if isinstance(dispatch_instrumentation, dict) else None,
        }

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
        received_epoch_ms = self._iso_to_epoch_ms(timestamp)
        current_chunk_count = self._active_stream_chunk_counts.get(agent_name, 0) + 1
        self._active_stream_chunk_counts[agent_name] = current_chunk_count
        self._active_stream_last_chunk_received_at[agent_name] = timestamp
        if agent_name not in self._active_stream_first_chunk_received_at:
            self._active_stream_first_chunk_received_at[agent_name] = timestamp

        previous_chunk_epoch_ms = self._active_stream_prev_chunk_received_epoch_ms.get(agent_name)
        if received_epoch_ms is not None:
            if previous_chunk_epoch_ms is not None:
                gap_ms = max(0.0, received_epoch_ms - previous_chunk_epoch_ms)
                self._active_stream_inter_chunk_gap_sum_ms[agent_name] = (
                    self._active_stream_inter_chunk_gap_sum_ms.get(agent_name, 0.0) + gap_ms
                )
                self._active_stream_inter_chunk_gap_max_ms[agent_name] = max(
                    self._active_stream_inter_chunk_gap_max_ms.get(agent_name, 0.0),
                    gap_ms,
                )
            self._active_stream_prev_chunk_received_epoch_ms[agent_name] = received_epoch_ms

        metadata = {
            "streaming": {
                "state": "streaming",
                "agent_name": agent_name,
                "last_chunk_at": timestamp,
                "timings": self._build_stream_timing_metadata(agent_name),
            }
        }

        message_id = self._active_stream_message_ids.get(agent_name)
        if message_id:
            last_persisted_text = self._active_stream_last_persisted_texts.get(agent_name, "")
            last_persisted_at = self._active_stream_last_persisted_at.get(agent_name, 0.0)
            now = time.monotonic()
            grew_by = max(0, len(accumulated_text) - len(last_persisted_text))
            punctuation_flush = accumulated_text.endswith(("\n", ".", "!", "?"))
            should_persist = (
                grew_by >= self.STREAM_UPDATE_MIN_CHARS_DELTA
                or punctuation_flush
                or (now - last_persisted_at) >= self.STREAM_UPDATE_MAX_INTERVAL_SECONDS
            )
            if not should_persist:
                self._active_stream_texts[agent_name] = accumulated_text
                return message_id

            updated = await self.chat_recorder.update_message(
                message_id=message_id,
                content=accumulated_text,
                metadata=metadata,
                human_interaction="CHAT_ASSISTANT",
            )
            if not updated:
                logger.warning("Failed updating streamed assistant message %s for %s", message_id, agent_name)
                return None
            self._active_stream_last_persisted_texts[agent_name] = accumulated_text
            self._active_stream_last_persisted_at[agent_name] = now
            persisted_at_iso = datetime.now(timezone.utc).isoformat()
            if agent_name not in self._active_stream_first_chunk_persisted_at:
                self._active_stream_first_chunk_persisted_at[agent_name] = persisted_at_iso
            self._mark_persisted_update(agent_name, persisted_at_iso)
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
            self._active_stream_last_persisted_texts[agent_name] = accumulated_text
            self._active_stream_last_persisted_at[agent_name] = time.monotonic()
            persisted_at_iso = datetime.now(timezone.utc).isoformat()
            self._active_stream_first_chunk_persisted_at[agent_name] = persisted_at_iso
            self._mark_persisted_update(agent_name, persisted_at_iso)

        self._active_stream_texts[agent_name] = accumulated_text
        return message_id

    async def _finalize_stream_for_agent(self, agent_name: str, timestamp: Any = None) -> Optional[str]:
        message_id = self._active_stream_message_ids.pop(agent_name, None)
        final_text = self._active_stream_texts.pop(agent_name, "")
        if not message_id:
            return None

        self._active_stream_last_persisted_texts.pop(agent_name, None)
        self._active_stream_last_persisted_at.pop(agent_name, None)
        metadata = {
            "streaming": {
                "state": "complete",
                "agent_name": agent_name,
                "completed_at": self._iso_timestamp(timestamp),
                "timings": self._build_stream_timing_metadata(agent_name),
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

        self._active_stream_chunk_counts.pop(agent_name, None)
        self._active_stream_first_chunk_received_at.pop(agent_name, None)
        self._active_stream_first_chunk_persisted_at.pop(agent_name, None)
        self._active_stream_last_chunk_received_at.pop(agent_name, None)
        self._active_stream_prev_chunk_received_epoch_ms.pop(agent_name, None)
        self._active_stream_inter_chunk_gap_sum_ms.pop(agent_name, None)
        self._active_stream_inter_chunk_gap_max_ms.pop(agent_name, None)
        self._active_stream_persist_update_counts.pop(agent_name, None)
        self._active_stream_prev_persisted_epoch_ms.pop(agent_name, None)
        self._active_stream_persist_gap_sum_ms.pop(agent_name, None)
        self._active_stream_persist_gap_max_ms.pop(agent_name, None)
        self._active_stream_last_persisted_at_iso.pop(agent_name, None)

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

        if message_type == "MESSAGE" and normalized_content.lower() == "assistant turn completed.":
            logger.debug("Dropping placeholder completion trace message: %s", normalized_content)
            return None

        if role == "ASSISTANT" and message_type == "MESSAGE":
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
