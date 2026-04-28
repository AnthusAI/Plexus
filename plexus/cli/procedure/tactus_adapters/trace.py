"""
Plexus Trace Sink for Tactus trace event persistence.
"""

import logging
import inspect
import time
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

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

    STREAM_UPDATE_MAX_INTERVAL_SECONDS = 1.2
    STREAM_UPDATE_MIN_CHARS_DELTA = 48

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
        self._recent_finalized_streams: Dict[str, tuple[str, float]] = {}
        self._pending_tool_call_ids: Dict[str, list] = {}  # tool_name -> FIFO queue of message IDs
        self._in_progress_tool_calls: Dict[str, list] = {}  # tool_name -> FIFO queue of in-progress message IDs
        self._console_dispatch_metadata: Any = None  # None=not fetched, False=fetched but empty, dict=cached
        self._backend_execution_started_at: str = datetime.now(timezone.utc).isoformat()
        self._backend_runtime_execute_started_at: Optional[str] = None
        self._session_context: Optional[Dict[str, Any]] = None
        self._agent_cost_summaries: Dict[str, Dict[str, Any]] = {}
        self._message_metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._active_turn_agent_name: Optional[str] = None
        self._recent_assistant_message_ids: Dict[str, Tuple[str, float]] = {}
        self._recent_finalized_message_ids: Dict[str, Tuple[str, float]] = {}

    def _resolve_agent_name(self, event: Any, *, default: str = "assistant") -> str:
        explicit = _event_field(event, "agent_name")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        if isinstance(self._active_turn_agent_name, str) and self._active_turn_agent_name.strip():
            return self._active_turn_agent_name.strip()
        return default

    def _empty_cost_summary(self) -> Dict[str, Any]:
        return {
            "schema_version": 1,
            "total_usd": 0.0,
            "llm_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": 0,
            "breakdown": [],
        }

    def _merge_cost_row(self, summary: Dict[str, Any], row: Dict[str, Any], *, reused: bool) -> None:
        provider = row.get("provider")
        model = row.get("model")
        key = f"{provider or ''}|{model or ''}"
        index = summary.setdefault("_index", {})
        breakdown = summary.setdefault("breakdown", [])
        target = index.get(key)
        if not isinstance(target, dict):
            target = {
                "provider": provider,
                "model": model,
                "spent_usd": 0.0,
                "reused_usd": 0.0,
                "referenced_usd": 0.0,
                "llm_calls": 0,
                "evaluation_runs": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cached_tokens": 0,
            }
            index[key] = target
            breakdown.append(target)

        spent = float(row.get("spent_usd") or 0.0)
        reused_amount = float(row.get("reused_usd") or 0.0)
        referenced = float(row.get("referenced_usd") or (spent + reused_amount))
        target["spent_usd"] += 0.0 if reused else spent
        target["reused_usd"] += referenced if reused else reused_amount
        target["referenced_usd"] += referenced
        target["llm_calls"] += int(row.get("llm_calls") or 0)
        target["evaluation_runs"] += int(row.get("evaluation_runs") or 0)
        target["prompt_tokens"] += int(row.get("prompt_tokens") or 0)
        target["completion_tokens"] += int(row.get("completion_tokens") or 0)
        target["total_tokens"] += int(row.get("total_tokens") or 0)
        target["cached_tokens"] += int(row.get("cached_tokens") or 0)

    def _finalize_summary(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(summary)
        breakdown = out.get("breakdown") or []
        if isinstance(breakdown, list):
            breakdown.sort(key=lambda item: float(item.get("referenced_usd", 0.0)), reverse=True)
        out.pop("_index", None)
        return out

    def _summary_from_cost_event(self, event: Any) -> Dict[str, Any]:
        prompt_tokens = int(_event_field(event, "prompt_tokens", default=0) or 0)
        completion_tokens = int(_event_field(event, "completion_tokens", default=0) or 0)
        total_tokens = int(_event_field(event, "total_tokens", default=prompt_tokens + completion_tokens) or 0)
        total_cost = float(_event_field(event, "total_cost", "cost", default=0.0) or 0.0)
        provider = _event_field(event, "provider")
        model = _event_field(event, "model")
        summary = self._empty_cost_summary()
        summary["total_usd"] = total_cost
        summary["llm_calls"] = 1
        summary["prompt_tokens"] = prompt_tokens
        summary["completion_tokens"] = completion_tokens
        summary["total_tokens"] = total_tokens
        summary["cached_tokens"] = total_tokens if _event_field(event, "cache_hit", default=False) else 0
        self._merge_cost_row(
            summary,
            {
                "provider": provider if isinstance(provider, str) and provider else None,
                "model": model if isinstance(model, str) and model else None,
                "spent_usd": total_cost,
                "reused_usd": 0.0,
                "referenced_usd": total_cost,
                "llm_calls": 1,
                "evaluation_runs": 0,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cached_tokens": summary["cached_tokens"],
            },
            reused=False,
        )
        return summary

    def _merge_cost_summaries(self, current: Optional[Dict[str, Any]], incoming: Optional[Dict[str, Any]], *, reused: bool = False) -> Dict[str, Any]:
        merged = self._empty_cost_summary() if not isinstance(current, dict) else dict(current)
        if "_index" not in merged:
            merged["_index"] = {}
            for row in merged.get("breakdown", []) or []:
                if isinstance(row, dict):
                    key = f"{row.get('provider') or ''}|{row.get('model') or ''}"
                    merged["_index"][key] = row

        incoming_summary = incoming if isinstance(incoming, dict) else self._empty_cost_summary()
        merged["total_usd"] = float(merged.get("total_usd", 0.0) or 0.0) + float(incoming_summary.get("total_usd", 0.0) or 0.0)
        merged["llm_calls"] = int(merged.get("llm_calls", 0) or 0) + int(incoming_summary.get("llm_calls", 0) or 0)
        merged["prompt_tokens"] = int(merged.get("prompt_tokens", 0) or 0) + int(incoming_summary.get("prompt_tokens", 0) or 0)
        merged["completion_tokens"] = int(merged.get("completion_tokens", 0) or 0) + int(incoming_summary.get("completion_tokens", 0) or 0)
        merged["total_tokens"] = int(merged.get("total_tokens", 0) or 0) + int(incoming_summary.get("total_tokens", 0) or 0)
        merged["cached_tokens"] = int(merged.get("cached_tokens", 0) or 0) + int(incoming_summary.get("cached_tokens", 0) or 0)

        for row in incoming_summary.get("breakdown", []) or []:
            if isinstance(row, dict):
                self._merge_cost_row(merged, row, reused=reused)
        return merged

    def _tool_cost_summary(self, tool_result: Any) -> Tuple[Optional[Dict[str, Any]], str]:
        if not isinstance(tool_result, dict):
            return None, "spent"
        billing_mode = "reused" if tool_result.get("_from_cache") is True else "spent"
        cost_details = tool_result.get("cost_details")
        if isinstance(cost_details, dict):
            summary = self._empty_cost_summary()
            summary["total_usd"] = float(cost_details.get("total_usd", tool_result.get("cost", 0.0)) or 0.0)
            summary["llm_calls"] = int(cost_details.get("llm_calls", 0) or 0)
            summary["prompt_tokens"] = int(cost_details.get("prompt_tokens", 0) or 0)
            summary["completion_tokens"] = int(cost_details.get("completion_tokens", 0) or 0)
            summary["total_tokens"] = int(cost_details.get("total_tokens", 0) or 0)
            summary["cached_tokens"] = int(cost_details.get("cached_tokens", 0) or 0)
            for row in cost_details.get("breakdown", []) or []:
                if isinstance(row, dict):
                    self._merge_cost_row(summary, row, reused=(billing_mode == "reused"))
            return summary, billing_mode

        if tool_result.get("cost") is None:
            return None, billing_mode

        total_cost = float(tool_result.get("cost") or 0.0)
        summary = self._empty_cost_summary()
        summary["total_usd"] = total_cost
        summary["llm_calls"] = 0
        self._merge_cost_row(
            summary,
            {
                "provider": None,
                "model": None,
                "spent_usd": total_cost,
                "reused_usd": 0.0,
                "referenced_usd": total_cost,
                "llm_calls": 0,
                "evaluation_runs": 1,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cached_tokens": 0,
            },
            reused=(billing_mode == "reused"),
        )
        return summary, billing_mode

    def _merged_metadata(self, message_id: str, patch: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        patch_data = patch if isinstance(patch, dict) else {}
        current = self._message_metadata_cache.get(message_id, {})
        merged = dict(current) if isinstance(current, dict) else {}
        merged.update(patch_data)
        self._message_metadata_cache[message_id] = merged
        return merged if merged else None

    def _tool_metadata_patch(self, tool_result: Any) -> Optional[Dict[str, Any]]:
        tool_cost_summary, tool_billing_mode = self._tool_cost_summary(tool_result)
        if not isinstance(tool_cost_summary, dict):
            return None
        return {
            "cost": {
                "kind": "tool_execution",
                "billing_mode": tool_billing_mode,
                "live": False,
                "summary": self._finalize_summary(tool_cost_summary),
            }
        }

    def _tool_failure_message(self, tool_name: Any, tool_result: Any) -> Optional[str]:
        normalized_result = tool_result
        if isinstance(tool_result, str):
            stripped = tool_result.strip()
            if not stripped:
                return None
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    normalized_result = json.loads(stripped)
                except Exception:
                    normalized_result = tool_result
            else:
                lowered = stripped.lower()
                failure_prefixes = (
                    "tool execution error",
                    "error:",
                    "failed:",
                    "exception:",
                    "traceback",
                )
                if lowered.startswith(failure_prefixes):
                    resolved_name = str(tool_name or "Tool")
                    return f"{resolved_name} failed: {stripped}"
                return None

        if not isinstance(normalized_result, dict):
            return None

        status = str(
            normalized_result.get("status")
            or normalized_result.get("dispatchStatus")
            or ""
        ).strip().upper()
        error_message = normalized_result.get("errorMessage") or normalized_result.get("error")
        if isinstance(error_message, str):
            error_message = error_message.strip()

        if status in {"FAILED", "ERROR", "CANCELLED", "CANCELED"}:
            resolved_name = str(tool_name or "Tool")
            detail = error_message or f"terminal status {status.lower()}"
            return f"{resolved_name} failed: {detail}"

        if isinstance(error_message, str) and error_message:
            resolved_name = str(tool_name or "Tool")
            return f"{resolved_name} failed: {error_message}"

        return None

    async def _record_tool_failure_notice(self, tool_name: Any, tool_result: Any) -> None:
        failure_message = self._tool_failure_message(tool_name, tool_result)
        if not failure_message:
            return

        await self.chat_recorder.record_message(
            role="ASSISTANT",
            content=failure_message,
            message_type="MESSAGE",
            human_interaction="ALERT_ERROR",
            metadata={
                "tool_failure": {
                    "tool_name": str(tool_name or ""),
                    "message": failure_message,
                }
            },
        )
        self.assistant_message_texts.append(failure_message)

    def _agent_cost_metadata(self, agent_name: str, *, live: bool) -> Optional[Dict[str, Any]]:
        summary = self._agent_cost_summaries.get(agent_name)
        if not isinstance(summary, dict):
            return None
        finalized = self._finalize_summary(summary)
        if (
            float(finalized.get("total_usd", 0.0) or 0.0) <= 0.0
            and int(finalized.get("llm_calls", 0) or 0) <= 0
            and not (finalized.get("breakdown") or [])
        ):
            return None
        return {
            "cost": {
                "kind": "assistant_inference",
                "billing_mode": "spent",
                "live": live,
                "summary": finalized,
            }
        }

    async def _record_cost_event(self, event: Any) -> None:
        agent_name = self._resolve_agent_name(event)
        increment = self._summary_from_cost_event(event)
        merged_summary = self._merge_cost_summaries(self._agent_cost_summaries.get(agent_name), increment)
        self._agent_cost_summaries[agent_name] = merged_summary
        message_id = self._active_stream_message_ids.get(agent_name)
        live = True
        if not message_id:
            recent = self._recent_assistant_message_ids.get(agent_name)
            if recent and (time.monotonic() - recent[1]) <= 30:
                message_id = recent[0]
                live = False
            if not message_id:
                finalized = self._recent_finalized_message_ids.get(agent_name)
                if finalized and (time.monotonic() - finalized[1]) <= 30:
                    message_id = finalized[0]
                    live = False
        if message_id:
            metadata = self._merged_metadata(
                message_id,
                self._agent_cost_metadata(agent_name, live=live),
            )
            await self.chat_recorder.update_message(
                message_id=message_id,
                metadata=metadata,
                human_interaction="CHAT_ASSISTANT",
            )

    async def start_session(self, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        if isinstance(context, dict):
            self._session_context = dict(context)
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
        if self._console_dispatch_metadata is not None:
            return self._console_dispatch_metadata if isinstance(self._console_dispatch_metadata, dict) else None
        procedure_id = str(getattr(self.chat_recorder, "procedure_id", "") or "").strip()
        if procedure_id == "builtin:console/chat":
            # Stream-dispatch console chat does not use Task metadata for routing.
            # Skip expensive task-history lookup so first assistant chunk can persist immediately.
            self._console_dispatch_metadata = False
            return None
        if isinstance(self._session_context, dict):
            if self._session_context.get("disable_console_dispatch_metadata_lookup"):
                self._console_dispatch_metadata = False
                return None
            direct_metadata = self._session_context.get("console_dispatch_metadata")
            if isinstance(direct_metadata, dict):
                self._console_dispatch_metadata = direct_metadata
                return direct_metadata
        getter = getattr(self.chat_recorder, "get_latest_console_chat_metadata", None)
        if not callable(getter):
            self._console_dispatch_metadata = False  # sentinel to avoid re-fetching
            return None
        if inspect.iscoroutinefunction(getter):
            self._console_dispatch_metadata = False
            return None
        metadata = getter()
        if inspect.isawaitable(metadata):
            self._console_dispatch_metadata = False
            return None
        if isinstance(metadata, dict):
            self._console_dispatch_metadata = metadata
            return metadata
        self._console_dispatch_metadata = False  # cache negative result
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
            # Eagerly cache console dispatch metadata to avoid 10s delay on first stream chunk
            self._get_console_dispatch_metadata()
            return True

        self.session_id = await self.chat_recorder.start_session(self._session_context)
        if self.session_id:
            # Eagerly cache console dispatch metadata to avoid 10s delay on first stream chunk
            self._get_console_dispatch_metadata()
        return bool(self.session_id)

    async def _record_stream_chunk(self, event: Any) -> Optional[str]:
        agent_name = self._resolve_agent_name(event)
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

            # Build metadata only when we're about to persist (avoids expensive timing calls on every chunk)
            metadata_patch = {
                "streaming": {
                    "state": "streaming",
                    "agent_name": agent_name,
                    "last_chunk_at": timestamp,
                    "timings": self._build_stream_timing_metadata(agent_name),
                }
            }
            cost_patch = self._agent_cost_metadata(agent_name, live=True)
            if cost_patch:
                metadata_patch.update(cost_patch)
            metadata = self._merged_metadata(message_id, metadata_patch)

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
            # Build metadata for the CREATE (first chunk)
            metadata = {
                "streaming": {
                    "state": "streaming",
                    "agent_name": agent_name,
                    "last_chunk_at": timestamp,
                    "timings": self._build_stream_timing_metadata(agent_name),
                }
            }
            cost_patch = self._agent_cost_metadata(agent_name, live=True)
            if cost_patch:
                metadata.update(cost_patch)
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
            self._message_metadata_cache[message_id] = metadata
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
        metadata_patch = {
            "streaming": {
                "state": "complete",
                "agent_name": agent_name,
                "completed_at": self._iso_timestamp(timestamp),
                "timings": self._build_stream_timing_metadata(agent_name),
            }
        }
        cost_patch = self._agent_cost_metadata(agent_name, live=False)
        if cost_patch:
            metadata_patch.update(cost_patch)
        metadata = self._merged_metadata(message_id, metadata_patch)
        await self.chat_recorder.update_message(
            message_id=message_id,
            content=final_text or None,
            metadata=metadata,
            human_interaction="CHAT_ASSISTANT",
        )

        normalized = final_text.strip()
        now_mono = time.monotonic()
        if normalized:
            self.assistant_message_texts.append(normalized)
            self._recent_finalized_streams[agent_name] = (normalized, now_mono)
        self._recent_finalized_message_ids[agent_name] = (message_id, now_mono)

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

        if event_type in {"log", "execution_summary"}:
            return None
        if event_type == "cost":
            await self._record_cost_event(event)
            return None

        # ToolCallStartedEvent: tool is about to run — write a pending TOOL_CALL record
        # with just the parameters so the UI shows an in-progress component immediately.
        if event_type == "tool_call_started":
            tool_name = _event_field(event, "tool_name")
            tool_parameters = _event_field(event, "tool_args")
            pending_id = await self.chat_recorder.record_message(
                role="ASSISTANT",
                content=f"Tool call: {tool_name}",
                message_type="TOOL_CALL",
                tool_name=tool_name,
                tool_parameters=tool_parameters,
                tool_response=None,
                human_interaction="INTERNAL",
            )
            if pending_id and tool_name:
                key = str(tool_name)
                if key not in self._in_progress_tool_calls:
                    self._in_progress_tool_calls[key] = []
                self._in_progress_tool_calls[key].append(pending_id)
            return pending_id

        if event_type == "agent_stream_chunk":
            return await self._record_stream_chunk(event)

        if event_type == "agent_turn":
            stage = str(_event_field(event, "stage", default="") or "").strip().lower()
            if stage == "completed":
                agent_name = self._resolve_agent_name(event)
                result = await self._finalize_stream_for_agent(
                    agent_name=agent_name,
                    timestamp=_event_field(event, "timestamp"),
                )
                # Keep summary available briefly because CostEvent can arrive
                # after AgentTurnEvent(completed) in some runtimes.
                if self._active_turn_agent_name == agent_name:
                    self._active_turn_agent_name = None
                return result
            if stage == "started":
                agent_name = self._resolve_agent_name(event)
                self._active_turn_agent_name = agent_name
                self._agent_cost_summaries[agent_name] = self._empty_cost_summary()
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
            agent_name = self._resolve_agent_name(event)
            recent_stream = self._recent_finalized_streams.get(agent_name)
            if recent_stream:
                streamed_text, finalized_at = recent_stream
                if time.monotonic() - finalized_at <= 15 and normalized_content == streamed_text:
                    logger.debug("Dropping duplicate post-stream assistant message for agent %s", agent_name)
                    return None
            if normalized_content:
                self.assistant_message_texts.append(normalized_content)

        human_interaction = _event_field(event, "human_interaction", "classification", default="INTERNAL")
        if hasattr(human_interaction, "value"):
            human_interaction = human_interaction.value
        hi_str = str(human_interaction or "INTERNAL")

        tool_name = _event_field(event, "tool_name")
        message_metadata = _event_field(event, "metadata")
        if role == "ASSISTANT" and message_type == "MESSAGE":
            agent_name = self._resolve_agent_name(event)
            cost_patch = self._agent_cost_metadata(agent_name, live=True)
            if isinstance(cost_patch, dict):
                message_metadata = dict(message_metadata) if isinstance(message_metadata, dict) else {}
                message_metadata.update(cost_patch)

        # Tactus emits a single ToolCallEvent (event_type="tool_call") that carries
        # BOTH tool_args (parameters) and tool_result (response).
        # If a ToolCallStartedEvent was already written (in-progress record), update it
        # with the result rather than creating a duplicate record.
        if event_kind == "TOOL_CALL":
            tool_parameters = _event_field(event, "tool_parameters", "tool_args")
            tool_result = _event_field(event, "tool_response", "tool_result")
            tool_metadata_patch = self._tool_metadata_patch(tool_result)

            # Check if we have an in-progress record to update
            in_progress_id = None
            if tool_name:
                queue = self._in_progress_tool_calls.get(str(tool_name))
                if queue:
                    in_progress_id = queue.pop(0)

            if in_progress_id:
                # Update the existing in-progress record with the result
                merged_metadata = self._merged_metadata(in_progress_id, tool_metadata_patch)
                await self.chat_recorder.update_message(
                    message_id=in_progress_id,
                    tool_response=tool_result,
                    metadata=merged_metadata,
                )
                await self._record_tool_failure_notice(tool_name, tool_result)
                return in_progress_id
            else:
                # No in-progress record (e.g., replayed or short-lived tool) — create new
                metadata = message_metadata
                if isinstance(tool_metadata_patch, dict):
                    metadata = dict(metadata) if isinstance(metadata, dict) else {}
                    metadata.update(tool_metadata_patch)
                call_id = await self.chat_recorder.record_message(
                    role=role,
                    content=content_text,
                    message_type="TOOL_CALL",
                    tool_name=tool_name,
                    tool_parameters=tool_parameters,
                    tool_response=tool_result,
                    human_interaction=hi_str,
                    metadata=metadata,
                )
                if call_id and isinstance(metadata, dict):
                    self._message_metadata_cache[call_id] = metadata
                await self._record_tool_failure_notice(tool_name, tool_result)
                return call_id

        # For explicit TOOL_RESPONSE events (non-Tactus paths), link via parentMessageId.
        # If there is no pending TOOL_CALL waiting for a response, the TOOL_CALL event
        # already carried the result and was stored as a complete record — skip this
        # redundant TOOL_RESPONSE to avoid duplicating the tool call component.
        parent_message_id: Optional[str] = None
        if event_kind == "TOOL_RESPONSE" and tool_name:
            queue = self._pending_tool_call_ids.get(str(tool_name))
            if not queue:
                in_progress_queue = self._in_progress_tool_calls.get(str(tool_name))
                if not in_progress_queue:
                    return None
                in_progress_id = in_progress_queue.pop(0)
                tool_result = _event_field(event, "tool_response", "tool_result")
                merged_metadata = self._merged_metadata(in_progress_id, self._tool_metadata_patch(tool_result))
                await self.chat_recorder.update_message(
                    message_id=in_progress_id,
                    tool_response=tool_result,
                    metadata=merged_metadata,
                )
                await self._record_tool_failure_notice(tool_name, tool_result)
                return in_progress_id
            parent_message_id = queue.pop(0)

        message_id = await self.chat_recorder.record_message(
            role=role,
            content=content_text,
            message_type=message_type,
            tool_name=tool_name,
            tool_parameters=_event_field(event, "tool_parameters", "tool_args"),
            tool_response=_event_field(event, "tool_response", "tool_result"),
            parent_message_id=parent_message_id,
            human_interaction=hi_str,
            metadata=message_metadata,
        )
        if message_id and isinstance(message_metadata, dict):
            self._message_metadata_cache[message_id] = message_metadata
        if event_kind == "TOOL_RESPONSE":
            await self._record_tool_failure_notice(tool_name, _event_field(event, "tool_response", "tool_result"))
        if message_id and role == "ASSISTANT" and message_type == "MESSAGE":
            agent_name = self._resolve_agent_name(event)
            self._recent_assistant_message_ids[agent_name] = (message_id, time.monotonic())

        if event_kind == "TOOL_CALL" and message_id and tool_name:
            key = str(tool_name)
            if key not in self._pending_tool_call_ids:
                self._pending_tool_call_ids[key] = []
            self._pending_tool_call_ids[key].append(message_id)

        return message_id

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
