"""
Procedure Executor - Routes procedure execution based on class field.

Supports multiple procedure execution engines:
- Tactus: Lua-based DSL runtime
- SOPAgent: Existing SOP agent system (default)
"""

import logging
import json
import inspect
import asyncio
import os
import queue
import re
import sys
import threading
import uuid
import yaml
from contextlib import nullcontext
from typing import Dict, Any, Optional, List

from plexus.runtime_budget import (
    RuntimeBudgetLimitExceeded,
    RuntimeBudgetMeter,
    RuntimeBudgetSpec,
)

logger = logging.getLogger(__name__)

CONSOLE_CHAT_BUILTIN_ID = "builtin:console/chat"


class ProcedureExecutionCancelled(RuntimeError):
    """Raised when a procedure worker observes a dashboard cancellation request."""


def _ensure_direct_run_cli_path() -> None:
    """Make the current Python environment's console scripts available to a direct run.

    Some existing procedure primitives invoke the ``plexus`` CLI as a child
    process.  An in-process caller may use an absolute Python executable rather
    than activating the virtual environment first, so preserve the runtime's
    executable directory explicitly for those child processes.
    """
    executable_dir = os.path.dirname(os.path.abspath(sys.executable))
    current_path = os.environ.get("PATH", "")
    path_parts = current_path.split(os.pathsep) if current_path else []
    if executable_dir not in path_parts:
        os.environ["PATH"] = os.pathsep.join([executable_dir, *path_parts])


def _is_dashboard_task_cancelled(client: Any, task_id: Optional[str]) -> bool:
    if not task_id:
        return False
    try:
        from plexus.dashboard.api.models.task import Task

        task = Task.get_by_id(task_id, client)
        return str(getattr(task, "status", "") or "").upper() in {
            "CANCELLED",
            "CANCELED",
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not check cancellation status for task %s: %s", task_id, exc)
        return False


def _install_tactus_dspy_context_capture_patch() -> None:
    """Capture Tactus DSPy agent prompt_context before model invocation."""
    try:
        from tactus.dspy.agent import DSPyAgentHandle
    except Exception as exc:  # pragma: no cover - optional dependency variance
        logger.debug("Could not import Tactus DSPy agent for context capture: %s", exc)
        return

    if getattr(DSPyAgentHandle, "_plexus_context_capture_patched", False):
        return

    from .logging_utils import capture_tactus_dspy_context_for_agent

    original_streaming = DSPyAgentHandle._turn_with_streaming
    original_non_streaming = DSPyAgentHandle._turn_without_streaming

    def _capture(agent: Any, prompt_context: Dict[str, Any], call_site: str) -> None:
        try:
            capture_tactus_dspy_context_for_agent(
                agent_name=f"Tactus DSPy Agent: {getattr(agent, 'name', 'unknown')}",
                prompt_context=prompt_context,
                turn_count=getattr(agent, "_turn_count", None),
                call_site=call_site,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to capture Tactus DSPy LLM context for agent %s: %s",
                getattr(agent, "name", "unknown"),
                exc,
            )

    def patched_streaming(self, opts: Dict[str, Any], prompt_context: Dict[str, Any]):
        logger.info(
            "Tactus DSPy streaming call path selected for agent=%s",
            getattr(self, "name", "unknown"),
        )
        _capture(self, prompt_context, "tactus_dspy_agent_streaming")
        return original_streaming(self, opts, prompt_context)

    def patched_non_streaming(self, opts: Dict[str, Any], prompt_context: Dict[str, Any]):
        logger.info(
            "Tactus DSPy non-streaming call path selected for agent=%s",
            getattr(self, "name", "unknown"),
        )
        _capture(self, prompt_context, "tactus_dspy_agent_non_streaming")
        return original_non_streaming(self, opts, prompt_context)

    DSPyAgentHandle._turn_with_streaming = patched_streaming
    DSPyAgentHandle._turn_without_streaming = patched_non_streaming
    DSPyAgentHandle._plexus_context_capture_patched = True
    logger.debug("Installed Tactus DSPy context capture patch")


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _serialize_cost_event(event: Any) -> Optional[Dict[str, Any]]:
    if event is None:
        return None

    cost = _to_float(getattr(event, "total_cost", None))
    if cost is None:
        cost = _to_float(getattr(event, "cost", None))
    if cost is None:
        return None

    timestamp = getattr(event, "timestamp", None)
    if hasattr(timestamp, "isoformat"):
        timestamp = timestamp.isoformat()

    return {
        "agent_name": getattr(event, "agent_name", None),
        "provider": getattr(event, "provider", None),
        "model": getattr(event, "model", None),
        "prompt_tokens": _to_int(getattr(event, "prompt_tokens", None)),
        "completion_tokens": _to_int(getattr(event, "completion_tokens", None)),
        "total_tokens": _to_int(getattr(event, "total_tokens", None)),
        "prompt_cost": _to_float(getattr(event, "prompt_cost", None)),
        "completion_cost": _to_float(getattr(event, "completion_cost", None)),
        "cost": cost,
        "cache_hit": bool(getattr(event, "cache_hit", False)),
        "request_id": getattr(event, "request_id", None),
        "timestamp": timestamp,
    }


def _cost_event_signature(entry: Dict[str, Any]) -> str:
    request_id = entry.get("request_id")
    if isinstance(request_id, str) and request_id:
        return f"request:{request_id}"
    return "|".join(
        str(entry.get(key))
        for key in (
            "agent_name",
            "provider",
            "model",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cost",
            "timestamp",
        )
    )


def _mcp_tool_value(tool: Any, key: str, default: Any = None) -> Any:
    if isinstance(tool, dict):
        return tool.get(key, default)
    return getattr(tool, key, default)


def _mcp_tool_result_to_text(result: Any) -> str:
    def _content_to_text(content: Any) -> str:
        if not isinstance(content, list):
            return str(content)

        text_parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                text_parts.append(str(item["text"]))
            elif hasattr(item, "text"):
                text_parts.append(str(getattr(item, "text")))
            else:
                text_parts.append(str(item))
        return "\n".join(text_parts)

    if isinstance(result, dict):
        content = result.get("content")
        if content is not None:
            return _content_to_text(content)
        if "text" in result:
            return str(result["text"])
        return json.dumps(result, indent=2, default=str)

    if isinstance(result, list):
        return _content_to_text(result)

    return str(result)


def _console_score_edit_audit_events(context: Any) -> List[Dict[str, Any]]:
    if not isinstance(context, dict):
        return []
    raw_events = context.get("console_audit_events")
    if not isinstance(raw_events, list):
        return []
    events: List[Dict[str, Any]] = []
    for event in raw_events:
        if not isinstance(event, dict):
            continue
        if str(event.get("kind") or "").strip().lower() != "score_edit":
            continue
        events.append(event)
    return events


def _trace_sink_score_edit_audit_events(trace_sink: Any) -> List[Dict[str, Any]]:
    raw_events = getattr(trace_sink, "console_audit_events", None)
    if not isinstance(raw_events, list):
        return []
    events: List[Dict[str, Any]] = []
    for event in raw_events:
        if not isinstance(event, dict):
            continue
        if str(event.get("kind") or "").strip().lower() != "score_edit":
            continue
        events.append(event)
    return events


def _score_edit_event_rank(event: Dict[str, Any], index: int) -> tuple[int, int]:
    score = 0
    diffs = event.get("diffs")
    if isinstance(diffs, dict) and any(
        isinstance(diffs.get(key), dict) for key in ("code", "guidelines")
    ):
        score += 100
    if str(event.get("version_url") or "").strip():
        score += 20
    if str(event.get("parent_version_url") or "").strip():
        score += 20
    if str(event.get("version_id") or "").strip():
        score += 10
    if str(event.get("parent_version_id") or "").strip():
        score += 5
    changed_fields = event.get("changed_fields")
    if isinstance(changed_fields, list) and any(str(field).strip() for field in changed_fields):
        score += 3
    for key in ("post_submit_test", "post_submit_verification"):
        step = event.get(key)
        if isinstance(step, dict):
            status = str(step.get("status") or "").strip().lower()
            if status and status != "unknown":
                score += 2
    if event.get("success") is True:
        score += 4
    elif event.get("success") is False:
        score += 2
    if str(event.get("error") or "").strip():
        score += 1
    return score, index


def _preferred_score_edit_audit_event(events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    best_event: Optional[Dict[str, Any]] = None
    best_rank: tuple[int, int] | None = None
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        rank = _score_edit_event_rank(event, index)
        if best_rank is None or rank > best_rank:
            best_event = event
            best_rank = rank
    return best_event


def _latest_trace_assistant_message(trace_sink: Any) -> tuple[Optional[str], str]:
    message_id: Optional[str] = None
    newest_ts = -1.0
    for attr_name in ("_recent_finalized_message_ids", "_recent_assistant_message_ids"):
        bucket = getattr(trace_sink, attr_name, None)
        if not isinstance(bucket, dict):
            continue
        for value in bucket.values():
            if not isinstance(value, tuple) or len(value) < 2:
                continue
            candidate_id, timestamp = value[0], value[1]
            if not isinstance(candidate_id, str) or not candidate_id.strip():
                continue
            try:
                ts = float(timestamp)
            except (TypeError, ValueError):
                ts = -1.0
            if ts >= newest_ts:
                newest_ts = ts
                message_id = candidate_id
    texts = getattr(trace_sink, "assistant_message_texts", None)
    if isinstance(texts, list):
        for candidate in reversed(texts):
            if isinstance(candidate, str) and candidate.strip():
                return message_id, candidate.strip()
    return message_id, ""


def _score_edit_audit_markdown(event: Dict[str, Any]) -> str:
    version_id = str(event.get("version_id") or "").strip()
    parent_version_id = str(event.get("parent_version_id") or "").strip()
    version_url = str(event.get("version_url") or "").strip()
    parent_version_url = str(event.get("parent_version_url") or "").strip()
    error_text = str(event.get("error") or "").strip()
    changed_fields = event.get("changed_fields")
    changed_fields_text = ", ".join(str(field) for field in changed_fields or [] if field) or "unknown"
    smoke = event.get("post_submit_test")
    smoke_status = (
        str(smoke.get("status") or "").strip().lower()
        if isinstance(smoke, dict)
        else "unknown"
    )
    verification = event.get("post_submit_verification")
    verification_status = (
        str(verification.get("status") or "").strip().lower()
        if isinstance(verification, dict)
        else "unknown"
    )
    success = bool(event.get("success"))
    changed_field_set = {str(field) for field in changed_fields or [] if field}

    if success and version_id:
        title = (
            "**Guidelines update saved**"
            if changed_field_set == {"guidelines"}
            else "**Score edit saved**"
        )
    elif version_id:
        title = "**Score edit needs review**"
    else:
        title = "**Score edit not saved**"

    lines: List[str] = [title, ""]
    if parent_version_url and parent_version_id:
        lines.append(f"[Previous score version]({parent_version_url})")
    if version_url and version_id:
        lines.append(f"[Updated score version]({version_url})")
    if (parent_version_url and parent_version_id) or (version_url and version_id):
        lines.append("")

    if version_id:
        lines.append(f"- Updated score version id: `{version_id}`")
    if parent_version_id:
        lines.append(f"- Previous score version id: `{parent_version_id}`")
    lines.append(f"- Changed fields: `{changed_fields_text}`")
    lines.append(f"- Smoke test: `{smoke_status}`")
    lines.append(f"- Post-submit verification: `{verification_status}`")
    lines.append("- Updated score version status: `not promoted`")
    if error_text:
        lines.append(f"- Error: `{error_text}`")

    return "\n".join(lines).strip()


def _linkify_score_edit_version_mentions(
    text: str, event: Dict[str, Any]
) -> str:
    if not isinstance(text, str) or not text.strip():
        return text
    if not isinstance(event, dict):
        return text

    version_id = str(event.get("version_id") or "").strip()
    version_url = str(event.get("version_url") or "").strip()
    if not version_id or not version_url:
        return text

    linked_version = f"[`{version_id}`]({version_url})"
    escaped_version = re.escape(version_id)
    label_prefixes = (
        r"(?:-\s*)?(?:\*\*)?new candidate version(?: created)?(?:\*\*)?(?:\*\*:|:\*\*|:)\s*",
        r"(?:-\s*)?(?:\*\*)?candidate version(?:\*\*)?(?:\*\*:|:\*\*|:)\s*",
    )

    updated = text
    for prefix in label_prefixes:
        updated = re.sub(
            rf"(?i)({prefix})`{escaped_version}`",
            rf"\1{linked_version}",
            updated,
        )
        updated = re.sub(
            rf"(?i)({prefix}){escaped_version}\b",
            rf"\1{linked_version}",
            updated,
        )

    updated_label_prefixes = (
        r"(?:-\s*)?(?:\*\*)?updated score version(?: id)?(?:\*\*)?(?:\*\*:|:\*\*|:)\s*",
        r"(?:-\s*)?(?:\*\*)?new score version(?: created)?(?:\*\*)?(?:\*\*:|:\*\*|:)\s*",
    )
    for prefix in updated_label_prefixes:
        updated = re.sub(
            rf"(?i)({prefix})`{escaped_version}`",
            rf"\1{linked_version}",
            updated,
        )
        updated = re.sub(
            rf"(?i)({prefix}){escaped_version}\b",
            rf"\1{linked_version}",
            updated,
        )
    updated = re.sub(
        r"(?i)\bnew candidate version(?: created)?\b",
        "Updated score version",
        updated,
    )
    updated = re.sub(
        r"(?i)\bcandidate version\b",
        "Updated score version",
        updated,
    )
    return updated


def _score_change_audit_metadata(event: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "kind": "score_edit",
        "success": bool(event.get("success")),
        "version_id": str(event.get("version_id") or "").strip() or None,
        "parent_version_id": str(event.get("parent_version_id") or "").strip() or None,
        "scorecard_id": str(event.get("scorecard_id") or "").strip() or None,
        "score_id": str(event.get("score_id") or "").strip() or None,
        "version_url": str(event.get("version_url") or "").strip() or None,
        "parent_version_url": str(event.get("parent_version_url") or "").strip() or None,
        "changed_fields": list(event.get("changed_fields") or []),
        "post_submit_test": event.get("post_submit_test"),
        "post_submit_verification": event.get("post_submit_verification"),
        "push_outcome": event.get("push_outcome"),
        "promoted": bool(event.get("promoted")),
    }
    if isinstance(event.get("diffs"), dict):
        payload["diffs"] = event.get("diffs")
    error_text = str(event.get("error") or "").strip()
    if error_text:
        payload["error"] = error_text
    return payload


def _merge_trace_message_metadata(
    trace_sink: Any, message_id: Optional[str], patch: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    if not isinstance(patch, dict) or not patch:
        return None
    merged: Dict[str, Any] = {}
    cache = getattr(trace_sink, "_message_metadata_cache", None)
    if isinstance(cache, dict) and isinstance(message_id, str) and message_id:
        cached = cache.get(message_id)
        if isinstance(cached, dict):
            merged.update(cached)
    merged.update(patch)
    if isinstance(cache, dict) and isinstance(message_id, str) and message_id:
        cache[message_id] = merged
    return merged


def _persist_inference_costs_to_state(storage: Any, procedure_id: str, cost_events: List[Any]) -> None:
    if not cost_events:
        return

    state_get = getattr(storage, "state_get", None)
    state_set = getattr(storage, "state_set", None)
    if not callable(state_get) or not callable(state_set):
        return

    try:
        costs = state_get(procedure_id, "costs", {}) or {}
        if not isinstance(costs, dict):
            costs = {}

        inference = costs.get("inference") or {}
        if not isinstance(inference, dict):
            inference = {}

        entries = inference.get("entries") or []
        if not isinstance(entries, list):
            entries = []
        seen_signatures = inference.get("seen_signatures") or {}
        if not isinstance(seen_signatures, dict):
            seen_signatures = {}

        added = 0
        for event in cost_events:
            serialized = _serialize_cost_event(event)
            if not serialized:
                continue
            signature = _cost_event_signature(serialized)
            if seen_signatures.get(signature):
                continue
            entries.append(serialized)
            seen_signatures[signature] = True
            added += 1

        if added == 0:
            return

        inference_total = 0.0
        by_agent: Dict[str, float] = {}
        by_model: Dict[str, float] = {}
        grouped_breakdown: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_cost = _to_float(entry.get("cost"))
            if entry_cost is None:
                continue
            inference_total += entry_cost

            agent_name = entry.get("agent_name")
            if isinstance(agent_name, str) and agent_name:
                by_agent[agent_name] = by_agent.get(agent_name, 0.0) + entry_cost

            model_name = entry.get("model")
            if isinstance(model_name, str) and model_name:
                by_model[model_name] = by_model.get(model_name, 0.0) + entry_cost

            provider_name = entry.get("provider")
            provider_key = provider_name if isinstance(provider_name, str) and provider_name else ""
            model_key = model_name if isinstance(model_name, str) and model_name else ""
            breakdown_key = f"{provider_key}|{model_key}"
            row = grouped_breakdown.get(breakdown_key)
            if row is None:
                row = {
                    "provider": provider_key or None,
                    "model": model_key or None,
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
                grouped_breakdown[breakdown_key] = row

            prompt_tokens = _to_int(entry.get("prompt_tokens")) or 0
            completion_tokens = _to_int(entry.get("completion_tokens")) or 0
            total_tokens = _to_int(entry.get("total_tokens"))
            if total_tokens is None:
                total_tokens = prompt_tokens + completion_tokens
            row["spent_usd"] += entry_cost
            row["referenced_usd"] += entry_cost
            row["llm_calls"] += 1
            row["prompt_tokens"] += prompt_tokens
            row["completion_tokens"] += completion_tokens
            row["total_tokens"] += total_tokens
            if entry.get("cache_hit") is True:
                row["cached_tokens"] += total_tokens

        inference["entries"] = entries
        inference["seen_signatures"] = seen_signatures
        inference["total"] = inference_total
        inference["by_agent"] = by_agent
        inference["by_model"] = by_model
        inference["breakdown"] = sorted(
            grouped_breakdown.values(),
            key=lambda item: float(item.get("referenced_usd", 0.0)),
            reverse=True,
        )
        costs["inference"] = inference

        evaluation = costs.get("evaluation") or {}
        if not isinstance(evaluation, dict):
            evaluation = {}
        eval_incurred = _to_float(evaluation.get("incurred_total")) or 0.0
        eval_reused = _to_float(evaluation.get("reused_total")) or 0.0
        eval_total = _to_float(evaluation.get("total"))
        if eval_total is None:
            eval_total = eval_incurred + eval_reused

        totals = costs.get("totals") or {}
        if not isinstance(totals, dict):
            totals = {}
        totals["evaluation"] = {
            "incurred": eval_incurred,
            "reused": eval_reused,
            "total": eval_total,
        }
        totals["inference"] = {"total": inference_total}
        totals["overall"] = {
            "incurred": eval_incurred + inference_total,
            "total": eval_total + inference_total,
        }
        costs["totals"] = totals

        state_set(procedure_id, "costs", costs)
    except Exception as exc:
        logger.warning("Failed persisting inference costs to state: %s", exc)


def _normalize_tactus_result(result: Any) -> Dict[str, Any]:
    """Normalize runtime results so wrapped logical failures are surfaced as top-level failures."""
    if not isinstance(result, dict):
        return {"success": False, "error": "Tactus runtime returned non-dict result"}

    top_level_success = bool(result.get("success"))
    nested_result = result.get("result")
    if not top_level_success or not isinstance(nested_result, dict):
        return result

    nested_success = nested_result.get("success")
    nested_status = str(nested_result.get("status") or "").strip().lower()
    nested_failed = nested_success is False or nested_status in {"error", "failed", "cancelled", "canceled"}
    if not nested_failed:
        return result

    normalized = dict(result)
    normalized["success"] = False
    if not normalized.get("error"):
        normalized["error"] = (
            nested_result.get("error")
            or nested_result.get("message")
            or "Tactus runtime returned nested failure result"
        )
    if not normalized.get("message") and nested_result.get("message"):
        normalized["message"] = nested_result.get("message")
    return normalized


def _complete_all_task_stages(client: Any, task_id: str) -> None:
    """
    Mark all PENDING or RUNNING task stages as COMPLETED.

    Called after procedure execution finishes so the dashboard stage display
    reflects completion rather than staying stuck at the last active stage.
    """
    from datetime import datetime, timezone

    stage_query = """
    query GetTask($id: ID!) {
        getTask(id: $id) {
            stages {
                items {
                    id
                    order
                    status
                }
            }
        }
    }
    """
    result = client.execute(stage_query, {"id": task_id})
    stages = result.get("getTask", {}).get("stages", {}).get("items", [])
    logger.info(f"[STAGE_COMPLETE] Task {task_id}: found {len(stages)} stages")
    if not stages:
        logger.warning(f"[STAGE_COMPLETE] No stages found for task {task_id}")
        return

    update_mutation = """
    mutation UpdateTaskStage($input: UpdateTaskStageInput!) {
        updateTaskStage(input: $input) {
            id
            status
        }
    }
    """
    now = datetime.now(timezone.utc).isoformat()
    for stage in stages:
        stage_status = stage.get("status")
        stage_id = stage.get("id")
        if stage_status in ("PENDING", "RUNNING"):
            logger.info(f"[STAGE_COMPLETE] Marking stage {stage_id} (order {stage.get('order')}) COMPLETED")
            client.execute(update_mutation, {
                "input": {"id": stage_id, "status": "COMPLETED", "completedAt": now}
            })
            logger.info(f"[STAGE_COMPLETE] Stage {stage_id} marked COMPLETED")
        else:
            logger.info(f"[STAGE_COMPLETE] Stage {stage_id} already {stage_status}, skipping")


def _fail_all_task_stages(client: Any, task_id: str, error_message: str = "") -> None:
    """
    Mark all PENDING or RUNNING task stages as FAILED.

    Called after procedure execution errors so the dashboard stage display
    reflects the failure rather than appearing as COMPLETED.
    """
    from datetime import datetime, timezone

    stage_query = """
    query GetTask($id: ID!) {
        getTask(id: $id) {
            stages {
                items {
                    id
                    order
                    status
                }
            }
        }
    }
    """
    result = client.execute(stage_query, {"id": task_id})
    stages = result.get("getTask", {}).get("stages", {}).get("items", [])
    logger.info(f"[STAGE_FAIL] Task {task_id}: found {len(stages)} stages")
    if not stages:
        logger.warning(f"[STAGE_FAIL] No stages found for task {task_id}")
        return

    update_mutation = """
    mutation UpdateTaskStage($input: UpdateTaskStageInput!) {
        updateTaskStage(input: $input) {
            id
            status
        }
    }
    """
    now = datetime.now(timezone.utc).isoformat()
    short_error = error_message[:500] if error_message else ""
    for stage in stages:
        stage_status = stage.get("status")
        stage_id = stage.get("id")
        if stage_status in ("PENDING", "RUNNING"):
            logger.info(f"[STAGE_FAIL] Marking stage {stage_id} (order {stage.get('order')}) FAILED")
            client.execute(update_mutation, {
                "input": {
                    "id": stage_id,
                    "status": "FAILED",
                    "completedAt": now,
                    "statusMessage": short_error,
                }
            })
            logger.info(f"[STAGE_FAIL] Stage {stage_id} marked FAILED")
        else:
            logger.info(f"[STAGE_FAIL] Stage {stage_id} already {stage_status}, skipping")


def _cancel_all_task_stages(client: Any, task_id: str, status_message: str = "") -> None:
    """
    Mark all PENDING or RUNNING task stages as CANCELLED.

    Called after an operator interruption so the dashboard distinguishes a
    cancelled run from an optimizer logic failure.
    """
    from datetime import datetime, timezone

    stage_query = """
    query GetTask($id: ID!) {
        getTask(id: $id) {
            stages {
                items {
                    id
                    order
                    status
                }
            }
        }
    }
    """
    result = client.execute(stage_query, {"id": task_id})
    stages = result.get("getTask", {}).get("stages", {}).get("items", [])
    logger.info(f"[STAGE_CANCEL] Task {task_id}: found {len(stages)} stages")
    if not stages:
        logger.warning(f"[STAGE_CANCEL] No stages found for task {task_id}")
        return

    update_mutation = """
    mutation UpdateTaskStage($input: UpdateTaskStageInput!) {
        updateTaskStage(input: $input) {
            id
            status
        }
    }
    """
    now = datetime.now(timezone.utc).isoformat()
    short_message = status_message[:500] if status_message else ""
    for stage in stages:
        stage_status = stage.get("status")
        stage_id = stage.get("id")
        if stage_status in ("PENDING", "RUNNING"):
            logger.info(f"[STAGE_CANCEL] Marking stage {stage_id} (order {stage.get('order')}) CANCELLED")
            client.execute(update_mutation, {
                "input": {
                    "id": stage_id,
                    "status": "CANCELLED",
                    "completedAt": now,
                    "statusMessage": short_message,
                }
            })
            logger.info(f"[STAGE_CANCEL] Stage {stage_id} marked CANCELLED")
        else:
            logger.info(f"[STAGE_CANCEL] Stage {stage_id} already {stage_status}, skipping")


def _advance_task_to_running_stage(client: Any, task_id: str, target_order: int) -> None:
    """
    Advance a task's stages so that stages before target_order are COMPLETED
    and the stage at target_order is RUNNING.

    Args:
        client: PlexusDashboardClient
        task_id: ID of the Task whose stages to update
        target_order: The order number of the stage to mark RUNNING
    """
    from datetime import datetime, timezone

    stage_query = """
    query GetTask($id: ID!) {
        getTask(id: $id) {
            stages {
                items {
                    id
                    order
                    status
                }
            }
        }
    }
    """
    result = client.execute(stage_query, {"id": task_id})
    stages = result.get("getTask", {}).get("stages", {}).get("items", [])
    if not stages:
        logger.debug("No TaskStages found for task %s; skipping stage advance.", task_id)
        return

    update_mutation = """
    mutation UpdateTaskStage($input: UpdateTaskStageInput!) {
        updateTaskStage(input: $input) {
            id
            status
        }
    }
    """
    now = datetime.now(timezone.utc).isoformat()
    for stage in stages:
        order = stage.get("order", 0)
        if order < target_order:
            if stage.get("status") != "COMPLETED":
                client.execute(update_mutation, {
                    "input": {"id": stage["id"], "status": "COMPLETED", "completedAt": now}
                })
        elif order == target_order:
            if stage.get("status") != "RUNNING":
                client.execute(update_mutation, {
                    "input": {"id": stage["id"], "status": "RUNNING", "startedAt": now}
                })


class _PlexusTraceLogBridge:
    """
    Bridges synchronous Tactus log events to async Plexus trace persistence.

    - Exposes supports_streaming=True so Tactus enables agent chunk streaming.
    - Captures CostEvent entries for execution summary accounting.
    - Forwards all non-cost events to PlexusTraceSink on a background worker.
    """

    supports_streaming = True
    _STREAM_CHUNK_FLUSH_EVENT = "__plexus_flush_agent_stream_chunk__"

    def __init__(self, trace_sink: Any, on_cost_event: Optional[Any] = None, cw_logger: Optional[Any] = None):
        self.trace_sink = trace_sink
        self.cost_events = []
        self._on_cost_event = on_cost_event
        self._cw_logger = cw_logger
        self._events: "queue.Queue[Any]" = queue.Queue()
        self._pending_stream_chunks: Dict[str, Any] = {}
        self._queued_stream_flush_agents: set[str] = set()
        self._stream_chunk_lock = threading.Lock()
        self._closed = threading.Event()
        self._worker = threading.Thread(
            target=self._worker_main,
            name="plexus-trace-log-bridge",
            daemon=True,
        )
        self._worker.start()

    @staticmethod
    def _event_type_name(event: Any) -> str:
        value = getattr(event, "event_type", None)
        if value is None and isinstance(event, dict):
            value = event.get("event_type")
        return str(value or "").strip().lower()

    @staticmethod
    def _event_agent_name(event: Any) -> str:
        value = getattr(event, "agent_name", None)
        if value is None and isinstance(event, dict):
            value = event.get("agent_name")
        return str(value or "").strip()

    @staticmethod
    def _event_field(event: Any, key: str, default: Any = None) -> Any:
        if isinstance(event, dict):
            return event.get(key, default)
        return getattr(event, key, default)

    @classmethod
    def _coalesced_stream_chunk_event(cls, prior: Any, incoming: Any) -> Dict[str, Any]:
        prior_text = str(cls._event_field(prior, "chunk_text", "") or "")
        incoming_text = str(cls._event_field(incoming, "chunk_text", "") or "")
        merged: Dict[str, Any] = {
            "event_type": "agent_stream_chunk",
            "agent_name": cls._event_agent_name(incoming) or cls._event_agent_name(prior),
            "chunk_text": f"{prior_text}{incoming_text}",
        }
        incoming_timestamp = cls._event_field(incoming, "timestamp")
        prior_timestamp = cls._event_field(prior, "timestamp")
        if incoming_timestamp is not None:
            merged["timestamp"] = incoming_timestamp
        elif prior_timestamp is not None:
            merged["timestamp"] = prior_timestamp
        return merged

    def _queue_latest_stream_chunk(self, event: Any) -> None:
        agent_name = self._event_agent_name(event)
        if not agent_name:
            self._events.put_nowait(event)
            return
        with self._stream_chunk_lock:
            existing = self._pending_stream_chunks.get(agent_name)
            if existing is None:
                self._pending_stream_chunks[agent_name] = event
            else:
                self._pending_stream_chunks[agent_name] = self._coalesced_stream_chunk_event(existing, event)
            if agent_name in self._queued_stream_flush_agents:
                return
            self._queued_stream_flush_agents.add(agent_name)
        self._events.put_nowait((self._STREAM_CHUNK_FLUSH_EVENT, agent_name))

    def _consume_latest_stream_chunk(self, agent_name: str) -> Optional[Any]:
        with self._stream_chunk_lock:
            event = self._pending_stream_chunks.pop(agent_name, None)
            self._queued_stream_flush_agents.discard(agent_name)
            return event

    def log(self, event: Any) -> None:
        try:
            from tactus.protocols.models import CostEvent
        except Exception:
            CostEvent = None  # type: ignore

        if CostEvent is not None and isinstance(event, CostEvent):
            self.cost_events.append(event)
            if callable(self._on_cost_event):
                try:
                    self._on_cost_event(event)
                except RuntimeBudgetLimitExceeded:
                    raise
                except Exception as exc:
                    logger.warning("Failed processing incremental cost event: %s", exc)
            # Also forward cost events to the trace sink so assistant/tool chat
            # messages can receive live per-turn cost metadata updates.

        try:
            if self._event_type_name(event) == "agent_stream_chunk":
                self._queue_latest_stream_chunk(event)
            else:
                self._events.put_nowait(event)
        except Exception as exc:
            logger.warning("Failed queueing trace event for persistence: %s", exc)

    def _worker_main(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            while not self._closed.is_set() or not self._events.empty():
                try:
                    queued_item = self._events.get(timeout=0.05)
                except queue.Empty:
                    continue

                try:
                    event = queued_item
                    if (
                        isinstance(queued_item, tuple)
                        and len(queued_item) == 2
                        and queued_item[0] == self._STREAM_CHUNK_FLUSH_EVENT
                    ):
                        agent_name = str(queued_item[1] or "").strip()
                        event = self._consume_latest_stream_chunk(agent_name) if agent_name else None
                        if event is None:
                            continue
                    try:
                        record_fn = getattr(self.trace_sink, "record", None)
                        if callable(record_fn):
                            loop.run_until_complete(record_fn(event))
                    except Exception as exc:
                        logger.warning("Failed recording streamed trace event: %s", exc)

                    if self._cw_logger is not None:
                        try:
                            self._cw_logger.log_run_event_from_tactus(event)
                        except Exception as exc:
                            logger.debug("CloudWatch run log failed: %s", exc)
                finally:
                    self._events.task_done()
        finally:
            loop.close()

    async def flush(self) -> None:
        await asyncio.to_thread(self._events.join)
        flush_fn = getattr(self.trace_sink, "flush", None)
        if callable(flush_fn):
            await flush_fn()

    async def close(self) -> None:
        self._closed.set()
        await asyncio.to_thread(self._worker.join, 1.0)


async def execute_procedure(
    procedure_id: str,
    procedure_code: str,
    client,
    mcp_server,
    context: Optional[Dict[str, Any]] = None,
    **options
) -> Dict[str, Any]:
    """
    Execute a procedure using the appropriate engine.

    Args:
        procedure_id: Procedure ID
        procedure_code: Procedure YAML (Tactus or SOPAgent)
        client: PlexusDashboardClient instance
        mcp_server: MCP server for tool access
        context: Optional context dict with pre-loaded data
        **options: Additional execution options (openai_api_key, etc.)

    Returns:
        Execution results dict
    """
    try:
        # Parse YAML procedure wrapper
        config = yaml.safe_load(procedure_code)

        if not isinstance(config, dict):
            raise ValueError("Invalid YAML: root must be a dictionary")

        # Check class field to determine executor
        procedure_class = config.get('class', '')

        logger.info(f"Routing procedure {procedure_id} to executor: {procedure_class}")

        if procedure_class == 'Tactus':
            code = config.get('code')
            if not isinstance(code, str) or not code.strip():
                raise ValueError("Tactus procedure requires non-empty 'code' field")
            return await _execute_tactus(
                procedure_id,
                procedure_code,
                client,
                mcp_server,
                context,
                **options
            )

        else:
            # Unknown class
            error_msg = f"Unknown procedure class: {procedure_class!r}. Only 'Tactus' is supported."
            logger.error(error_msg)
            return {
                'success': False,
                'procedure_id': procedure_id,
                'error': error_msg
            }

    except yaml.YAMLError as e:
        error_msg = f"Failed to parse procedure configuration: {e}"
        logger.error(error_msg)
        return {
            'success': False,
            'procedure_id': procedure_id,
            'error': error_msg
        }

    except Exception as e:
        error_msg = f"Procedure execution failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            'success': False,
            'procedure_id': procedure_id,
            'error': error_msg
        }


async def _execute_tactus(
    procedure_id: str,
    procedure_source: str,
    client,
    mcp_server,
    context: Optional[Dict[str, Any]],
    **options
) -> Dict[str, Any]:
    """
    Execute procedure using Tactus runtime with Plexus adapters.

    Args:
        procedure_id: Procedure ID
        procedure_source: Full Tactus YAML procedure source
        client: PlexusDashboardClient
        mcp_server: MCP server
        context: Optional context
        **options: Additional options (openai_api_key, etc.)

    Returns:
        Execution results
    """
    logger.info(f"Executing procedure {procedure_id} with Tactus runtime")
    log_bridge: Optional[_PlexusTraceLogBridge] = None
    cw_logger = None
    _uninstall_cw_llm_patch = None

    try:
        from tactus.core import TactusRuntime
        from .tactus_adapters import (
            InMemoryStorageAdapter,
            PlexusStorageAdapter,
            PlexusHITLAdapter,
            PlexusTraceSink,
        )
        from .chat_recorder import ProcedureChatRecorder
        
        def _extract_legacy_input_from_params(source_config: Dict[str, Any]) -> Dict[str, Any]:
            """Resolve legacy runtime input from params.<name>.value/default declarations."""
            params_config = source_config.get("params")
            if not isinstance(params_config, dict):
                return {}

            resolved: Dict[str, Any] = {}
            for name, definition in params_config.items():
                if not isinstance(name, str) or not name:
                    continue
                if not isinstance(definition, dict):
                    continue
                if "value" in definition:
                    resolved[name] = definition.get("value")
                elif "default" in definition:
                    resolved[name] = definition.get("default")
            return resolved

        def _lua_string(value: str) -> str:
            escaped = (
                value.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "\\r")
            )
            return f'"{escaped}"'

        def _lua_literal(value: Any) -> str:
            if value is None:
                return "nil"
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return repr(value)
            if isinstance(value, str):
                return _lua_string(value)
            try:
                payload = json.dumps(value)
                payload = payload.replace("]]", "] ]")
                return f"Json.decode([[{payload}]])"
            except Exception:
                return _lua_string(str(value))

        def _lua_table_literal(values: Dict[str, Any]) -> str:
            entries = []
            for key, value in values.items():
                if not isinstance(key, str) or not key:
                    continue
                entries.append(f"[{_lua_string(key)}] = {_lua_literal(value)}")
            return "{ " + ", ".join(entries) + " }" if entries else "{}"

        def _extract_assistant_text(payload: Any) -> Optional[str]:
            if not isinstance(payload, dict):
                return None
            response_value = payload.get("response")
            if isinstance(response_value, str) and response_value.strip():
                return response_value.strip()
            nested_result = payload.get("result")
            if isinstance(nested_result, dict):
                nested_response = nested_result.get("response")
                if isinstance(nested_response, str) and nested_response.strip():
                    return nested_response.strip()
            return None

        def _normalize_agent_model_overrides(raw_overrides: Any) -> Dict[str, str]:
            if not isinstance(raw_overrides, dict):
                return {}
            normalized: Dict[str, str] = {}
            for agent_name, model_name in raw_overrides.items():
                if not isinstance(agent_name, str):
                    continue
                agent_key = agent_name.strip()
                if not agent_key:
                    continue
                model = str(model_name or "").strip()
                if not model:
                    continue
                normalized[agent_key] = model
            return normalized

        def _apply_agent_model_overrides_to_source(
            source_text: str,
            overrides: Dict[str, str],
        ) -> tuple[str, Dict[str, str]]:
            if not overrides:
                return source_text, {}
            try:
                parsed = yaml.safe_load(source_text)
            except Exception:
                return source_text, {}
            if not isinstance(parsed, dict):
                return source_text, {}
            agents = parsed.get("agents")
            if not isinstance(agents, dict):
                return source_text, {}

            updated_agents = dict(agents)
            applied: Dict[str, str] = {}
            changed = False
            for agent_name, requested_model in overrides.items():
                agent_config = updated_agents.get(agent_name)
                if not isinstance(agent_config, dict):
                    continue
                current_model = str(agent_config.get("model") or "").strip()
                next_agent_config = dict(agent_config)
                agent_changed = False
                if current_model != requested_model:
                    next_agent_config["model"] = requested_model
                    agent_changed = True

                # DSPy's OpenAI reasoning-model adapter rejects these compact
                # GPT-5 variants unless max_tokens is at least 16k. The
                # Console model picker is a supported user control, so a
                # selected runnable model must also receive a runnable token
                # configuration instead of failing after the user waits for a
                # response.
                if requested_model.strip().lower() in {"gpt-5-mini", "gpt-5-nano"}:
                    try:
                        configured_max_tokens = int(next_agent_config.get("max_tokens") or 0)
                    except (TypeError, ValueError):
                        configured_max_tokens = 0
                    if configured_max_tokens < 16000:
                        next_agent_config["max_tokens"] = 16000
                        agent_changed = True

                if agent_changed:
                    updated_agents[agent_name] = next_agent_config
                applied[agent_name] = requested_model
                changed = changed or agent_changed

            if not changed:
                return source_text, applied

            updated = dict(parsed)
            updated["agents"] = updated_agents
            return yaml.safe_dump(updated, sort_keys=False), applied

        # Backward compatibility: older Plexus templates use `code:` for Lua source.
        # Current Tactus parser expects `procedure:` as the required field.
        try:
            parsed_source = yaml.safe_load(procedure_source)
            if isinstance(parsed_source, dict):
                changed = False

                if 'procedure' not in parsed_source:
                    legacy_code = parsed_source.get('code')
                    if isinstance(legacy_code, str) and legacy_code.strip():
                        parsed_source = dict(parsed_source)
                        parsed_source['procedure'] = legacy_code
                        parsed_source.pop('code', None)
                        changed = True
                        logger.info("Adapted legacy Tactus config: mapped 'code' to 'procedure'")

                if not parsed_source.get('default_provider'):
                    parsed_source = dict(parsed_source)
                    parsed_source['default_provider'] = 'openai'
                    changed = True
                    logger.info("Adapted Tactus config: set default_provider to 'openai'")

                agents = parsed_source.get('agents')
                if isinstance(agents, dict):
                    normalized_agents = dict(agents)
                    agents_changed = False
                    for agent_name, agent_config in agents.items():
                        if not isinstance(agent_config, dict):
                            continue
                        tools = agent_config.get('tools')
                        if (
                            isinstance(tools, list)
                            and tools
                            and all(isinstance(tool, str) for tool in tools)
                            and all(tool.startswith('plexus_') for tool in tools)
                        ):
                            updated_agent_config = dict(agent_config)
                            # Use direct named toolset binding for compatibility with DSPy tool conversion.
                            # Filtered toolset wrappers currently lose visible tool definitions, resulting in
                            # zero callable tools at runtime.
                            updated_agent_config['tools'] = ['plexus']
                            normalized_agents[agent_name] = updated_agent_config
                            agents_changed = True
                    if agents_changed:
                        parsed_source = dict(parsed_source)
                        parsed_source['agents'] = normalized_agents
                        changed = True
                        logger.info("Adapted Tactus config: normalized legacy tool lists to plexus toolset expressions")

                if changed:
                    procedure_source = yaml.safe_dump(parsed_source, sort_keys=False)

            # Backward compatibility shims for older Lua procedures.
            if isinstance(parsed_source, dict):
                lua_source = parsed_source.get('procedure')
                if isinstance(lua_source, str):
                    shim_parts = []

                    if 'Specification(' in lua_source and 'function Specification' not in lua_source:
                        shim_parts.append(
                            "if Specification == nil then\n"
                            "  function Specification(spec)\n"
                            "    return spec\n"
                            "  end\n"
                            "end\n"
                        )
                        shim_parts.append(
                            "if field == nil then\n"
                            "  field = setmetatable({}, {\n"
                            "    __index = function(_, _)\n"
                            "      return function(value)\n"
                            "        return value\n"
                            "      end\n"
                            "    end\n"
                            "  })\n"
                            "end\n"
                        )

                    if 'State.' in lua_source and 'State = ' not in lua_source:
                        shim_parts.append(
                            "if State == nil then\n"
                            "  State = {\n"
                            "    get = function(key, default)\n"
                            "      if _state_primitive ~= nil then\n"
                            "        local value = _state_primitive.get(key)\n"
                            "        if value == nil then return default end\n"
                            "        return value\n"
                            "      end\n"
                            "      return default\n"
                            "    end,\n"
                            "    set = function(key, value)\n"
                            "      if _state_primitive ~= nil then\n"
                            "        _state_primitive.set(key, value)\n"
                            "      end\n"
                            "      return value\n"
                            "    end,\n"
                            "    increment = function(key, amount)\n"
                            "      if _state_primitive ~= nil then\n"
                            "        return _state_primitive.increment(key, amount or 1)\n"
                            "      end\n"
                            "      return 0\n"
                            "    end,\n"
                            "    append = function(key, value)\n"
                            "      if _state_primitive ~= nil then\n"
                            "        _state_primitive.append(key, value)\n"
                            "      end\n"
                            "    end,\n"
                            "    all = function()\n"
                            "      if _state_primitive ~= nil then\n"
                            "        return _state_primitive.all()\n"
                            "      end\n"
                            "      return {}\n"
                            "    end\n"
                            "  }\n"
                            "end\n"
                        )

                    if 'Stage.' in lua_source and 'Stage = ' not in lua_source:
                        shim_parts.append(
                            "if Stage == nil then\n"
                            "  local __stage_value = nil\n"
                            "  Stage = {\n"
                            "    set = function(value)\n"
                            "      __stage_value = value\n"
                            "      if State ~= nil and State.set ~= nil then\n"
                            "        State.set(\"stage\", value)\n"
                            "      end\n"
                            "      local stage_tool = Tool.get(\"plexus_set_procedure_stage\")\n"
                            "      if stage_tool ~= nil then stage_tool({stage = value}) end\n"
                            "      return value\n"
                            "    end,\n"
                            "    get = function()\n"
                            "      return __stage_value\n"
                            "    end,\n"
                            "    progress = function(current, total)\n"
                            "      local progress_tool = Tool.get(\"plexus_set_stage_progress\")\n"
                            "      if progress_tool ~= nil then progress_tool({current = current, total = total}) end\n"
                            "    end\n"
                            "  }\n"
                            "end\n"
                        )

                    agents = parsed_source.get('agents')
                    if isinstance(agents, dict):
                        alias_lines = []
                        for agent_name in agents.keys():
                            if not isinstance(agent_name, str) or not agent_name:
                                continue
                            alias = ''.join(part.capitalize() for part in agent_name.split('_'))
                            if not alias:
                                continue
                            alias_lines.append(
                                f"if {alias} == nil then "
                                f"if {agent_name} ~= nil then {alias} = {agent_name} "
                                f"elseif Agent ~= nil then {alias} = Agent('{agent_name}') end end"
                            )
                        if alias_lines:
                            shim_parts.append('\n'.join(alias_lines) + '\n')

                    # Always inject the plexus global from the registered Python module.
                    # register_python_module("plexus") makes it available via require(),
                    # but Lua procedures use it as a plain global, so we expose it here.
                    shim_parts.insert(0,
                        'if plexus == nil then\n'
                        '  local ok, _mod = pcall(require, "plexus")\n'
                        '  if ok and _mod ~= nil then plexus = _mod end\n'
                        'end\n'
                    )

                    if shim_parts:
                        parsed_source = dict(parsed_source)
                        parsed_source['procedure'] = '\n'.join(shim_parts) + '\n' + lua_source
                        procedure_source = yaml.safe_dump(parsed_source, sort_keys=False)
                        logger.info("Adapted Tactus config: added legacy Lua compatibility shims")

                if (
                    isinstance(lua_source, str)
                    and 'Specification(' in lua_source
                    and 'function Specification' not in lua_source
                ):
                    # No-op: condition retained for compatibility with previous log messages.
                    procedure_source = yaml.safe_dump(parsed_source, sort_keys=False)
                    logger.info("Adapted Tactus config: added legacy Specification/field compatibility shims")

            # Backward compatibility: older procedures ended with:
            #   Procedure { ..., function(input) return run(input) end }
            # In current Tactus runtime, `Procedure(...)` is a lookup primitive, not a declarative
            # wrapper, so executing this block raises "Named procedure '<Lua table ...>' not found".
            # Rewrite to direct legacy execution entrypoint.
            if isinstance(parsed_source, dict):
                legacy_input = _extract_legacy_input_from_params(parsed_source)
                if legacy_input:
                    if isinstance(context, dict):
                        context = {**legacy_input, **context}
                    elif context is None:
                        context = legacy_input

                # CRITICAL FIX: For YAML format with class: Tactus, the Tactus runtime does NOT
                # automatically inject context dict values into the params table in Lua.
                # We need to manually inject params by prepending Lua code that builds the params table.
                # This ensures params.scorecard, params.score, etc. are available in the Lua code.
                if parsed_source.get('class') == 'Tactus' and context:
                    lua_source = parsed_source.get('code') or parsed_source.get('procedure')
                    if isinstance(lua_source, str):
                        # Build params table from context dict, applying YAML defaults for missing params
                        params_dict = {}
                        params_schema = parsed_source.get('params', {})
                        for param_name, param_def in params_schema.items():
                            if param_name in context:
                                raw_value = context[param_name]
                                # Coerce numeric context values back to string if the
                                # schema declares type: string. This handles the case
                                # where the CLI --set parser converts "45425" → int(45425)
                                # but the param is an identifier that must stay as string.
                                if (isinstance(raw_value, (int, float))
                                        and isinstance(param_def, dict)
                                        and param_def.get('type') == 'string'):
                                    raw_value = str(raw_value)
                                params_dict[param_name] = raw_value
                            elif isinstance(param_def, dict) and param_def.get('default') is not None:
                                params_dict[param_name] = param_def['default']

                        if params_dict:
                            # Inject params initialization at the start of Lua code
                            params_lua = _lua_table_literal(params_dict)
                            injected_lua = f"-- Injected params from runtime context\nparams = {params_lua}\n\n{lua_source}"
                            if 'code' in parsed_source:
                                parsed_source['code'] = injected_lua
                            else:
                                parsed_source['procedure'] = injected_lua
                            procedure_source = yaml.safe_dump(parsed_source, sort_keys=False)
                            logger.info(f"Injected params into Lua code: {list(params_dict.keys())}")

                lua_source = parsed_source.get('procedure')
                if (
                    isinstance(lua_source, str)
                    and 'Procedure {' in lua_source
                    and 'return run(' in lua_source
                ):
                    block_start = lua_source.rfind('Procedure {')
                    if block_start > -1:
                        legacy_defaults_lua = _lua_table_literal(legacy_input)
                        normalized_lua = (
                            lua_source[:block_start].rstrip()
                            + "\n\nlocal __legacy_defaults = "
                            + legacy_defaults_lua
                            + "\nlocal __legacy_input = {}\n"
                            + "for k, v in pairs(__legacy_defaults) do\n"
                            + "  __legacy_input[k] = v\n"
                            + "end\n"
                            + "if type(input) == 'table' then\n"
                            + "  for k, v in pairs(input) do\n"
                            + "    __legacy_input[k] = v\n"
                            + "  end\n"
                            + "end\n"
                            + "return run(__legacy_input)\n"
                        )
                        parsed_source = dict(parsed_source)
                        parsed_source['procedure'] = normalized_lua
                        procedure_source = yaml.safe_dump(parsed_source, sort_keys=False)
                        logger.info(
                            "Adapted Tactus config: replaced legacy Procedure block with direct run(input)"
                        )

                if isinstance(context, dict):
                    model_overrides = _normalize_agent_model_overrides(context.get("agent_models"))
                    if model_overrides:
                        procedure_source, applied_model_overrides = _apply_agent_model_overrides_to_source(
                            procedure_source,
                            model_overrides,
                        )
                        if applied_model_overrides:
                            context = dict(context)
                            context["agent_models_applied"] = applied_model_overrides
                            logger.info(
                                "Applied Tactus agent model overrides: %s",
                                ", ".join(
                                    f"{agent}={model}"
                                    for agent, model in sorted(applied_model_overrides.items())
                                ),
                            )
        except Exception:  # noqa: BLE001
            # Let runtime report parse errors with full context if adaptation fails.
            pass

        # Get OpenAI API key from options or environment (not logged — passed to API client only)
        _api_key = options.get('openai_api_key')

        if not _api_key:
            from plexus.config.loader import load_config
            load_config()
            import os
            _api_key = os.getenv('OPENAI_API_KEY')

        # A caller may explicitly request a direct, process-local execution.
        # Unlike a dashboard procedure it owns no durable Procedure record, so
        # checkpoint/state must remain in memory and never touch S3.
        direct_run = bool(options.pop("direct_run", False))
        if direct_run:
            _ensure_direct_run_cli_path()
        storage = (
            InMemoryStorageAdapter(procedure_id)
            if direct_run
            else PlexusStorageAdapter(client, procedure_id)
        )
        chat_recorder = ProcedureChatRecorder(client, procedure_id)
        child_budget = (
            context.get("_plexus_child_budget")
            if isinstance(context, dict)
            else None
        )
        try:
            child_budget_meter = (
                RuntimeBudgetMeter(RuntimeBudgetSpec.from_dict(child_budget))
                if isinstance(child_budget, dict)
                else None
            )
        except ValueError as budget_error:
            raise RuntimeBudgetLimitExceeded(str(budget_error)) from budget_error

        if child_budget_meter is not None:
            try:
                parsed_source = yaml.safe_load(procedure_source)
                if isinstance(parsed_source, dict):
                    parsed_source = dict(parsed_source)
                    parsed_source["max_depth"] = child_budget_meter.spec.depth
                    procedure_source = yaml.safe_dump(parsed_source, sort_keys=False)
            except Exception as budget_depth_error:  # noqa: BLE001
                raise RuntimeBudgetLimitExceeded(
                    f"Could not apply child depth budget: {budget_depth_error}"
                ) from budget_depth_error

        # Allow callers to inject a custom HITL adapter (e.g. TerminalHITLAdapter for CLI)
        hitl = options.pop("hitl_adapter", None)
        if hitl is None:
            hitl = PlexusHITLAdapter(client, procedure_id, chat_recorder, storage)
        trace_sink = PlexusTraceSink(chat_recorder)

        def _on_incremental_cost_event(event: Any) -> None:
            # Persist each inference cost event as it arrives so dashboards can
            # display near-real-time optimizer spend during long-running cycles.
            if child_budget_meter is not None:
                child_budget_meter.record_usd(
                    "procedure.llm",
                    getattr(event, "total_cost", None) or getattr(event, "cost", None),
                )
            _persist_inference_costs_to_state(storage, procedure_id, [event])

        # Generate invocation_run_id here so it can be used for CloudWatch stream naming.
        invocation_run_id = str(uuid.uuid4())

        _account_key = getattr(getattr(client, "context", None), "account_key", None) or "unknown"
        from .cloudwatch_logger import _create_procedure_cloudwatch_logger, _install_cloudwatch_llm_context_patch
        # A direct run has no durable dashboard Procedure record and must not
        # establish CloudWatch transport or metadata writes before its local
        # procedure body can execute.
        if not direct_run:
            cw_logger = _create_procedure_cloudwatch_logger(
                account_key=_account_key,
                procedure_id=procedure_id,
                invocation_run_id=invocation_run_id,
            )

        log_bridge = _PlexusTraceLogBridge(
            trace_sink,
            on_cost_event=_on_incremental_cost_event,
            cw_logger=cw_logger,
        )

        # Create Tactus runtime with Plexus adapters.
        # Support both newer and older runtime signatures.
        _runtime_param_names: list = [
            "procedure_id", "storage_backend", "hitl_handler", "chat_recorder",
            "trace_sink", "log_handler", "mcp_server", "openai_api_key", "run_id",
            "source_file_path",
        ]

        runtime_kwargs: Dict[str, Any] = {
            "procedure_id": procedure_id,
            "storage_backend": storage,
            "hitl_handler": hitl,
            "chat_recorder": chat_recorder,
            "trace_sink": trace_sink,
            "log_handler": log_bridge,
            "mcp_server": mcp_server,
            "openai_api_key": _api_key,
            "run_id": invocation_run_id,
            "source_file_path": options.pop("source_file_path", None),
        }
        supports_chat_recorder = True
        try:
            runtime_sig = inspect.signature(TactusRuntime.__init__)
            accepts_var_kwargs = any(
                param.kind == inspect.Parameter.VAR_KEYWORD
                for param in runtime_sig.parameters.values()
            )
            if not accepts_var_kwargs:
                supported_params = {
                    name
                    for name in runtime_sig.parameters.keys()
                    if name != "self"
                }
                supports_chat_recorder = "chat_recorder" in supported_params
                # Use the static param names list (not runtime_kwargs) to avoid
                # taint-analysis false positives on logged key names.
                dropped = sorted(k for k in _runtime_param_names if k not in supported_params)
                if dropped:
                    logger.info(
                        "TactusRuntime.__init__ does not accept %s; continuing without them",
                        ", ".join(dropped),
                    )
                runtime_kwargs = {
                    key: value
                    for key, value in runtime_kwargs.items()
                    if key in supported_params
                }
        except Exception as sig_error:
            logger.debug(
                "Could not inspect TactusRuntime signature (%s); using default runtime kwargs",
                sig_error,
            )

        runtime = TactusRuntime(**runtime_kwargs)

        # Ensure DSPy agents can stream even when runtime constructor does not expose log_handler.
        if getattr(runtime, "log_handler", None) is None:
            runtime.log_handler = log_bridge

        _install_tactus_dspy_context_capture_patch()
        _uninstall_cw_llm_patch = None
        if cw_logger is not None:
            _uninstall_cw_llm_patch = _install_cloudwatch_llm_context_patch(cw_logger)

        # Bridge legacy in-process MCP server to Tactus toolset registry.
        # Newer Tactus versions resolve agent tools through named toolsets.
        mcp_client_for_bridge = None
        if mcp_server and hasattr(mcp_server, "list_tools") and hasattr(mcp_server, "call_tool"):
            mcp_client_for_bridge = mcp_server
        elif mcp_server and hasattr(mcp_server, "transport"):
            try:
                from .mcp_transport import ProcedureMCPClient
                # Embedded transport must be initialized before any tool calls.
                transport = mcp_server.transport
                if hasattr(transport, "initialize") and not getattr(transport, "connected", False):
                    await transport.initialize({"name": "Tactus Procedure Runtime", "version": "1.0.0"})
                mcp_client_for_bridge = ProcedureMCPClient(mcp_server.transport)
            except Exception:
                mcp_client_for_bridge = None

        # Register score editor tools on transport BEFORE load_tools() so they appear
        # in the bridged toolset registry alongside the Plexus MCP tools.
        if mcp_server and hasattr(mcp_server, "transport") and getattr(mcp_server.transport, "connected", False):
            try:
                from .tactus_adapters.score_editor_toolset import ScoreEditorToolset
                score_editor_instance = ScoreEditorToolset.register_on_transport(
                    mcp_server.transport, mcp_client=mcp_client_for_bridge
                )
                # Pre-populate scorecard/score from execution context so the toolset
                # can auto-load YAML even when the orchestrator LLM strips args from
                # score_editor_setup (DSPy tool conversion drops all args).
                if isinstance(context, dict):
                    if context.get("scorecard"):
                        score_editor_instance._scorecard = str(context["scorecard"])
                    if context.get("score"):
                        score_editor_instance._score = str(context["score"])
                    logger.info(
                        "ScoreEditorToolset pre-populated from context: scorecard=%s score=%s",
                        score_editor_instance._scorecard, score_editor_instance._score,
                    )
            except Exception as exc:
                logger.warning("Could not register ScoreEditorToolset: %s", exc)

            try:
                from .tactus_adapters.rubric_memory_toolset import register_on_transport as register_rubric_memory
                register_rubric_memory(mcp_server.transport)
            except Exception as exc:
                logger.warning("Could not register rubric memory tools: %s", exc)

        if mcp_client_for_bridge:
            try:
                from pydantic_ai.toolsets import FunctionToolset
                from tactus.adapters.mcp import PydanticAIMCPAdapter

                # Bridge embedded MCP tools into the Tactus toolset registry.
                # In the `execute_tactus` world we want ONE model-facing tool surface:
                # a single toolset named "plexus" containing the MCP tools (usually only
                # `execute_tactus` in local console chat).
                mcp_adapter = PydanticAIMCPAdapter(
                    mcp_client_for_bridge,
                    runtime=runtime,
                )
                mcp_tools = await mcp_adapter.load_tools()
                if mcp_tools and "plexus" not in runtime.toolset_registry:
                    runtime.toolset_registry["plexus"] = FunctionToolset(tools=mcp_tools)
                    logger.info(
                        "Registered bridged MCP toolset 'plexus' with %d tool(s)",
                        len(mcp_tools),
                    )
                    # Also register each tool individually so agent configs can reference
                    # specific tool names directly (e.g., tools: [execute_tactus]).
                    for tool in mcp_tools:
                        tool_name = getattr(tool, "name", None)
                        if tool_name and tool_name not in runtime.toolset_registry:
                            runtime.toolset_registry[tool_name] = FunctionToolset(tools=[tool])
            except Exception as exc:
                logger.warning("Could not bridge MCP tools into Tactus toolset registry: %s", exc)

        # Register the plexus.* runtime module directly into the Tactus procedure
        # runtime so that procedure Lua can call plexus.evaluation.run({...}),
        # plexus.score.pull({...}), plexus.rubric_memory.recent_entries({...}), etc.
        # without routing through any MCP bridge.
        try:
            import os as _os
            import sys as _sys

            _mcp_dir = _os.path.normpath(
                _os.path.join(_os.path.dirname(__file__), "..", "..", "..", "MCP")
            )
            if _os.path.isdir(_mcp_dir) and _mcp_dir not in _sys.path:
                _sys.path.insert(0, _mcp_dir)

            from tools.tactus_runtime.execute import (  # type: ignore[import]
                PlexusRuntimeModule,
                _default_handle_store,
                _default_evaluation_runner,
                _default_report_runner_sync,
                _default_procedure_runner,
                BudgetGate,
            )

            if hasattr(runtime, "register_python_module"):
                # Procedures can run for hours; use an effectively unlimited budget
                # so API calls inside the procedure are not killed by the 60s default.
                from tools.tactus_runtime.execute import BudgetSpec  # type: ignore[import]
                _proc_budget = BudgetGate(BudgetSpec(
                    usd=float("inf"),
                    wallclock_seconds=float("inf"),
                    depth=99,
                    tool_calls=999_999,
                ))
                _plexus_module = PlexusRuntimeModule(
                    mcp=None,
                    trace_id=procedure_id,
                    handle_store=_default_handle_store(),
                    evaluation_runner=lambda args: _default_evaluation_runner(args, None),
                    report_runner=_default_report_runner_sync,
                    procedure_runner=_default_procedure_runner,
                    budget=_proc_budget,
                )
                runtime.register_python_module("plexus", _plexus_module)
                logger.info("Registered plexus.* runtime module in procedure runtime")
            else:
                logger.warning(
                    "TactusRuntime.register_python_module not available; "
                    "plexus.* module not registered (update tactus package)"
                )
        except Exception as _exc:
            logger.warning("Could not register plexus.* runtime module: %s", _exc)

        # Compatibility patch: newer DSPy ToolCall objects are attribute-based,
        # while current Tactus agent code indexes them like dictionaries.
        try:
            from dspy.adapters.types.tool import ToolCalls

            dspy_tool_call_cls = getattr(ToolCalls, "ToolCall", None)
            if dspy_tool_call_cls and not hasattr(dspy_tool_call_cls, "__getitem__"):
                def _tool_call_getitem(self, key):
                    if key == "name":
                        return getattr(self, "name", None)
                    if key == "args":
                        return getattr(self, "args", None)
                    if hasattr(self, key):
                        return getattr(self, key)
                    raise KeyError(key)

                dspy_tool_call_cls.__getitem__ = _tool_call_getitem
                logger.info("Patched DSPy ToolCalls.ToolCall for dict-style compatibility")
        except Exception as exc:
            logger.warning("Could not patch DSPy ToolCall compatibility: %s", exc)

        # Hydrate console-trigger text into runtime context so procedures can access
        # the exact user prompt even when runtime message history is empty.
        runtime_context: Any = context
        if isinstance(context, dict):
            runtime_context = dict(context)
        elif context is None:
            runtime_context = {}

        if isinstance(runtime_context, dict):
            runtime_account_id = runtime_context.get("account_id") or runtime_context.get("accountId")
            if runtime_account_id:
                try:
                    chat_recorder.account_id = str(runtime_account_id)
                except Exception:  # noqa: BLE001
                    pass  # account_id is best-effort; proceed without it

            get_console_trigger_message = getattr(chat_recorder, "get_latest_console_trigger_message", None)
            get_console_session_history = getattr(chat_recorder, "get_console_session_history", None)
            is_console_context = (
                procedure_id == CONSOLE_CHAT_BUILTIN_ID
                or any(
                    runtime_context.get(key)
                    for key in (
                        "console_user_message",
                        "console_session_history",
                        "console_chat",
                    )
                )
                # If the chat recorder supports console-trigger hydration, treat this as
                # console-like context even when the caller did not pass console keys.
                # Direct runs deliberately have no Console session to hydrate.
                or (
                    not direct_run
                    and (
                        callable(get_console_trigger_message)
                        or callable(get_console_session_history)
                    )
                )
            )

            if is_console_context and not runtime_context.get("console_user_message"):
                console_trigger_message = (
                    get_console_trigger_message()
                    if callable(get_console_trigger_message)
                    else None
                )
                if isinstance(console_trigger_message, str) and console_trigger_message.strip():
                    runtime_context["console_user_message"] = console_trigger_message.strip()

            if is_console_context and not runtime_context.get("console_session_history"):
                console_session_history = (
                    get_console_session_history()
                    if callable(get_console_session_history)
                    else None
                )
                if isinstance(console_session_history, list) and console_session_history:
                    runtime_context["console_session_history"] = console_session_history

        mark_runtime_execute_started = getattr(trace_sink, "mark_runtime_execute_started", None)
        if callable(mark_runtime_execute_started):
            mark_runtime_execute_started()

        # Advance task stage to the second stage (e.g. "Baseline Evaluation") now
        # that the procedure is actually executing, giving the dashboard live feedback.
        _task_id = options.pop("_task_id_for_stage_tracking", None)
        if _is_dashboard_task_cancelled(client, _task_id):
            raise ProcedureExecutionCancelled(
                f"Procedure execution cancelled for task {_task_id}"
            )
        if _task_id:
            try:
                _advance_task_to_running_stage(client, _task_id, target_order=2)
            except Exception as _se:
                logger.debug("Could not advance task stage at execution start: %s", _se)

        # Inject procedure_id into State so Lua code can use it (e.g. for chat mailbox polling).
        # This is best-effort — if it fails, mailbox polling will be silently skipped.
        try:
            storage.state_set(procedure_id, "_procedure_id", procedure_id)
        except Exception as _inject_err:
            logger.debug("Could not inject _procedure_id into State: %s", _inject_err)

        # Store CloudWatch log stream pointer in procedure metadata so the UI can locate logs.
        if cw_logger is not None:
            try:
                import json as _json
                _cw_meta_result = client.execute(
                    "query GetProcedureMeta($id: ID!) { getProcedure(id: $id) { metadata } }",
                    {"id": procedure_id},
                )
                _existing_meta_str = (
                    (_cw_meta_result.get("getProcedure") or {}).get("metadata") or "{}"
                )
                try:
                    _meta = _json.loads(_existing_meta_str) or {}
                except Exception:
                    _meta = {}
                _meta["cloudwatchLogGroup"] = cw_logger.log_group
                _meta["cloudwatchLogStreamPrefix"] = f"{procedure_id}/"
                client.execute(
                    "mutation UpdateProcedureCWMeta($input: UpdateProcedureInput!) { updateProcedure(input: $input) { id } }",
                    {"input": {"id": procedure_id, "metadata": _json.dumps(_meta)}},
                )
            except Exception as _cw_meta_err:
                logger.debug("Could not store CloudWatch metadata on procedure: %s", _cw_meta_err)

        if _is_dashboard_task_cancelled(client, _task_id):
            raise ProcedureExecutionCancelled(
                f"Procedure execution cancelled for task {_task_id}"
            )

        # Execute the full Tactus YAML source so params/agents/stages are preserved.
        budget_context = (
            child_budget_meter.enforce_wallclock("procedure.run")
            if child_budget_meter is not None
            else nullcontext()
        )
        with budget_context:
            result = _normalize_tactus_result(
                await runtime.execute(procedure_source, runtime_context, format="yaml")
            )
        if log_bridge:
            await log_bridge.flush()
            _persist_inference_costs_to_state(storage, procedure_id, log_bridge.cost_events)

        execution_succeeded = bool(isinstance(result, dict) and result.get("success"))

        if _task_id:
            try:
                if execution_succeeded:
                    _complete_all_task_stages(client, _task_id)
                else:
                    task_error = ""
                    if isinstance(result, dict):
                        task_error = str(result.get("error") or result.get("message") or "")
                    _fail_all_task_stages(client, _task_id, task_error)
            except Exception as _ce:
                logger.warning("Could not finalize task stages after execution: %s", _ce, exc_info=True)

        score_edit_audit_block = ""
        score_edit_audit_applied = False
        latest_score_edit_audit_event: Optional[Dict[str, Any]] = None
        score_edit_audit_patch: Optional[Dict[str, Any]] = None
        if procedure_id == CONSOLE_CHAT_BUILTIN_ID:
            audit_events = []
            audit_events.extend(_trace_sink_score_edit_audit_events(trace_sink))
            audit_events.extend(_console_score_edit_audit_events(runtime_context))
            if context is not runtime_context:
                audit_events.extend(_console_score_edit_audit_events(context))
            if audit_events:
                latest_score_edit_audit_event = _preferred_score_edit_audit_event(
                    audit_events
                )
            if latest_score_edit_audit_event:
                score_edit_audit_patch = {
                    "score_change_audit": _score_change_audit_metadata(
                        latest_score_edit_audit_event
                    )
                }
                score_edit_audit_block = _score_edit_audit_markdown(
                    latest_score_edit_audit_event
                )
                message_id, existing_text = _latest_trace_assistant_message(trace_sink)
                existing_text = _linkify_score_edit_version_mentions(
                    existing_text, latest_score_edit_audit_event
                )
                if score_edit_audit_block and existing_text and score_edit_audit_block in existing_text:
                    score_edit_audit_applied = True
                    if (
                        supports_chat_recorder
                        and message_id
                        and callable(getattr(chat_recorder, "update_message", None))
                        and score_edit_audit_patch
                    ):
                        try:
                            merged_metadata = _merge_trace_message_metadata(
                                trace_sink,
                                message_id,
                                score_edit_audit_patch,
                            )
                            await chat_recorder.update_message(
                                message_id=message_id,
                                metadata=merged_metadata,
                            )
                        except Exception as metadata_error:
                            logger.warning(
                                "Could not update Console assistant message metadata with score-change audit: %s",
                                metadata_error,
                            )
                elif (
                    supports_chat_recorder
                    and score_edit_audit_block
                    and message_id
                    and callable(getattr(chat_recorder, "update_message", None))
                ):
                    combined_text = (
                        score_edit_audit_block
                        if not existing_text
                        else f"{score_edit_audit_block}\n\n{existing_text}"
                    )
                    try:
                        merged_metadata = _merge_trace_message_metadata(
                            trace_sink,
                            message_id,
                            score_edit_audit_patch or {},
                        )
                        updated = await chat_recorder.update_message(
                            message_id=message_id,
                            content=combined_text,
                            metadata=merged_metadata,
                            human_interaction="CHAT_ASSISTANT",
                        )
                        if updated:
                            score_edit_audit_applied = True
                            sink_messages = getattr(trace_sink, "assistant_message_texts", None)
                            if isinstance(sink_messages, list):
                                if sink_messages and isinstance(sink_messages[-1], str):
                                    sink_messages[-1] = combined_text
                                else:
                                    sink_messages.append(combined_text)
                    except Exception as audit_error:
                        logger.warning(
                            "Could not update Console assistant message with deterministic score-edit audit summary: %s",
                            audit_error,
                        )

        # Ensure Console receives a meaningful assistant message from procedure output.
        # Some runtime/trace combinations emit only placeholder completion events.
        if supports_chat_recorder and isinstance(result, dict):
            assistant_text = _extract_assistant_text(result)
            if assistant_text:
                if latest_score_edit_audit_event:
                    assistant_text = _linkify_score_edit_version_mentions(
                        assistant_text, latest_score_edit_audit_event
                    )
                if (
                    score_edit_audit_block
                    and not score_edit_audit_applied
                    and score_edit_audit_block not in assistant_text
                ):
                    assistant_text = f"{score_edit_audit_block}\n\n{assistant_text}"
                trace_messages = getattr(trace_sink, "assistant_message_texts", [])
                has_meaningful_trace_assistant = any(
                    isinstance(message, str) and message.strip()
                    for message in trace_messages
                )
                if not has_meaningful_trace_assistant:
                    if callable(getattr(chat_recorder, "record_message", None)):
                        await chat_recorder.record_message(
                            role="ASSISTANT",
                            content=assistant_text,
                            human_interaction="CHAT_ASSISTANT",
                            metadata=score_edit_audit_patch,
                        )
                    else:
                        await chat_recorder.record_assistant_message(assistant_text)

        if log_bridge:
            try:
                await log_bridge.close()
            except Exception as close_error:
                logger.warning("Failed closing trace log bridge after success: %s", close_error)

        if _uninstall_cw_llm_patch is not None:
            _uninstall_cw_llm_patch()
        if cw_logger is not None:
            try:
                await asyncio.to_thread(cw_logger.close, execution_succeeded)
            except Exception as _cw_err:
                logger.debug("Failed closing CloudWatch logger after success: %s", _cw_err)

        logger.info(f"Tactus execution complete: {result.get('success')}")
        return result

    except ProcedureExecutionCancelled as e:
        if log_bridge:
            try:
                await log_bridge.flush()
            except Exception as flush_error:
                logger.warning("Failed flushing trace log bridge after cancellation: %s", flush_error)
            try:
                await log_bridge.close()
            except Exception as close_error:
                logger.warning("Failed closing trace log bridge after cancellation: %s", close_error)
        if _uninstall_cw_llm_patch is not None:
            _uninstall_cw_llm_patch()
        if cw_logger is not None:
            try:
                await asyncio.to_thread(cw_logger.close, False)
            except Exception as _cw_err:
                logger.debug("Failed closing CloudWatch logger after cancellation: %s", _cw_err)
        logger.info("Tactus procedure execution cancelled: %s", e)
        return {
            'success': False,
            'procedure_id': procedure_id,
            'status': 'CANCELLED',
            'error': str(e),
        }

    except Exception as e:
        if log_bridge:
            try:
                await log_bridge.flush()
                _persist_inference_costs_to_state(storage, procedure_id, log_bridge.cost_events)
            except Exception as flush_error:
                logger.warning("Failed flushing trace log bridge after error: %s", flush_error)
            try:
                await log_bridge.close()
            except Exception as close_error:
                logger.warning("Failed closing trace log bridge after error: %s", close_error)
        if _uninstall_cw_llm_patch is not None:
            _uninstall_cw_llm_patch()
        if cw_logger is not None:
            try:
                await asyncio.to_thread(cw_logger.close, False)
            except Exception as _cw_err:
                logger.debug("Failed closing CloudWatch logger after error: %s", _cw_err)
        if _task_id:
            try:
                _fail_all_task_stages(client, _task_id, str(e))
            except Exception as _ce:
                logger.warning("Could not fail task stages after error: %s", _ce, exc_info=True)
        logger.error(f"Tactus execution error: {e}", exc_info=True)
        return {
            'success': False,
            'procedure_id': procedure_id,
            'error': f"Tactus execution error: {e}"
        }
