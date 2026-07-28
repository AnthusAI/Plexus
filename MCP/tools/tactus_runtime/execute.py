#!/usr/bin/env python3
"""Single-tool Tactus execution prototype for the Plexus MCP server."""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import re
import shlex
import signal
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Mapping, Optional

from fastmcp import Context, FastMCP
from pydantic import Field
from plexus.runtime_budget import RuntimeBudgetSpec
from plexus.attribution.actor_context import (
    apply_actor_attribution,
    apply_actor_context_to_env,
    extract_request_user_id_from_mcp_context,
    resolve_actor_context,
    set_runtime_actor_context,
)

logger = logging.getLogger(__name__)

_EVALUATION_PROCESS_LOCK = threading.Lock()
_EVALUATION_PROCESSES: dict[int, Any] = {}
CONSOLE_AUDIT_EVENTS_KEY = "console_audit_events"
SCORE_EDIT_AUDIT_EVENT_KEY = "score_edit_audit"
SCORE_EDIT_AUDIT_COMPACT_KEY = "score_edit_audit_compact"
SCORE_AUDIT_DIFF_TEXT_MAX_CHARS = 20_000
SCORE_AUDIT_UNIFIED_DIFF_MAX_CHARS = 20_000
FEEDBACK_ALIGNMENT_SCORE_CONCURRENCY = 4
FEEDBACK_ALIGNMENT_SCORECARD_CONCURRENCY = 5


PLEXUS_DOCS_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "documentation",
        "agent",
    )
)

PLEXUS_SKILLS_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "skills",
    )
)

PLEXUS_TACTUS_TRACE_DIR_DEFAULT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "tmp", "tactus_traces")
)

PLEXUS_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

PLEXUS_PROCEDURE_RUN_LOG_DIR_DEFAULT = os.path.join(
    PLEXUS_PROJECT_ROOT, "tmp", "tactus_procedure_runs"
)


def _resolve_trace_dir(request_id: Optional[str] = None) -> str:
    configured = os.environ.get("PLEXUS_TACTUS_TRACE_DIR")
    if configured:
        base_dir = configured
    elif os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get("LAMBDA_TASK_ROOT"):
        base_dir = os.path.join("/tmp", "tactus_traces")
    else:
        base_dir = PLEXUS_TACTUS_TRACE_DIR_DEFAULT

    if request_id:
        return os.path.join("/tmp", request_id, os.path.basename(base_dir))
    return base_dir


def _resolve_procedure_run_log_dir(request_id: Optional[str] = None) -> str:
    configured = os.environ.get("PLEXUS_PROCEDURE_RUN_LOG_DIR")
    if configured:
        base_dir = configured
    elif os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get("LAMBDA_TASK_ROOT"):
        base_dir = os.path.join("/tmp", "tactus_procedure_runs")
    else:
        base_dir = PLEXUS_PROCEDURE_RUN_LOG_DIR_DEFAULT

    if request_id:
        return os.path.join("/tmp", request_id, os.path.basename(base_dir))
    return base_dir


def _register_evaluation_process(process: Any) -> None:
    pid = getattr(process, "pid", None)
    if pid is None:
        return
    with _EVALUATION_PROCESS_LOCK:
        _EVALUATION_PROCESSES[int(pid)] = process


def _registered_evaluation_process(process_id: Any) -> Any | None:
    try:
        pid = int(process_id)
    except (TypeError, ValueError):
        return None
    with _EVALUATION_PROCESS_LOCK:
        return _EVALUATION_PROCESSES.get(pid)


def _forget_evaluation_process(process_id: Any) -> None:
    try:
        pid = int(process_id)
    except (TypeError, ValueError):
        return
    with _EVALUATION_PROCESS_LOCK:
        _EVALUATION_PROCESSES.pop(pid, None)


def _local_procedure_env() -> dict[str, str]:
    env = {
        **os.environ,
        "PYTHONUNBUFFERED": "1",
        "PLEXUS_LOCAL_DISPATCH": "1",
    }
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        PLEXUS_PROJECT_ROOT
        if not existing_pythonpath
        else os.pathsep.join([PLEXUS_PROJECT_ROOT, existing_pythonpath])
    )
    return apply_actor_context_to_env(env)


def _score_version_relative_path(
    *, scorecard_id: Any, score_id: Any, version_id: Any
) -> str | None:
    scorecard = str(scorecard_id or "").strip()
    score = str(score_id or "").strip()
    version = str(version_id or "").strip()
    if not scorecard or not score or not version:
        return None
    return f"/lab/scorecards/{scorecard}/scores/{score}/versions/{version}"


def _truncate_for_score_audit_diff(
    value: Any, *, limit: int = SCORE_AUDIT_DIFF_TEXT_MAX_CHARS
) -> tuple[str, bool]:
    text = str(value or "")
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def _build_unified_diff(
    *,
    original_text: str,
    modified_text: str,
    fromfile: str,
    tofile: str,
) -> str:
    diff = "".join(
        difflib.unified_diff(
            original_text.splitlines(keepends=True),
            modified_text.splitlines(keepends=True),
            fromfile=fromfile,
            tofile=tofile,
        )
    )
    if len(diff) <= SCORE_AUDIT_UNIFIED_DIFF_MAX_CHARS:
        return diff
    return diff[:SCORE_AUDIT_UNIFIED_DIFF_MAX_CHARS]


def _build_score_diff_entry(
    *,
    kind: str,
    language: str,
    original_text: Any,
    modified_text: Any,
    original_version_id: Any,
    modified_version_id: Any,
    original_url: str | None,
    modified_url: str | None,
) -> dict[str, Any]:
    original, original_truncated = _truncate_for_score_audit_diff(original_text)
    modified, modified_truncated = _truncate_for_score_audit_diff(modified_text)
    unified = _build_unified_diff(
        original_text=original,
        modified_text=modified,
        fromfile=f"{kind}:previous",
        tofile=f"{kind}:updated",
    )
    return {
        "kind": kind,
        "language": language,
        "has_changes": original != modified,
        "original": original,
        "modified": modified,
        "unified_diff": unified,
        "original_label": "Previous score version",
        "modified_label": "Updated score version",
        "original_version_id": str(original_version_id or "").strip() or None,
        "modified_version_id": str(modified_version_id or "").strip() or None,
        "original_url": original_url,
        "modified_url": modified_url,
        "truncated": bool(original_truncated or modified_truncated),
    }


def _build_score_change_diffs(
    *,
    scorecard_id: Any,
    score_id: Any,
    parent_version_id: Any,
    version_id: Any,
    changed_fields: list[str] | None,
    original_code: Any,
    modified_code: Any,
    original_guidelines: Any,
    modified_guidelines: Any,
) -> dict[str, Any]:
    changed = {
        str(field).strip().lower()
        for field in list(changed_fields or [])
        if str(field).strip()
    }

    parent_url = _score_version_relative_path(
        scorecard_id=scorecard_id,
        score_id=score_id,
        version_id=parent_version_id,
    )
    version_url = _score_version_relative_path(
        scorecard_id=scorecard_id,
        score_id=score_id,
        version_id=version_id,
    )

    diffs: dict[str, Any] = {}
    original_code_text = str(original_code or "")
    modified_code_text = str(modified_code or "")
    original_guidelines_text = str(original_guidelines or "")
    modified_guidelines_text = str(modified_guidelines or "")

    if "code" in changed or original_code_text != modified_code_text:
        diffs["code"] = _build_score_diff_entry(
            kind="code",
            language="yaml",
            original_text=original_code_text,
            modified_text=modified_code_text,
            original_version_id=parent_version_id,
            modified_version_id=version_id,
            original_url=parent_url,
            modified_url=version_url,
        )

    if "guidelines" in changed or original_guidelines_text != modified_guidelines_text:
        diffs["guidelines"] = _build_score_diff_entry(
            kind="guidelines",
            language="markdown",
            original_text=original_guidelines_text,
            modified_text=modified_guidelines_text,
            original_version_id=parent_version_id,
            modified_version_id=version_id,
            original_url=parent_url,
            modified_url=version_url,
        )

    return diffs


def _extract_console_audit_events(runtime_context: Any) -> list[dict[str, Any]]:
    if not isinstance(runtime_context, dict):
        return []
    raw_events = runtime_context.get(CONSOLE_AUDIT_EVENTS_KEY)
    if not isinstance(raw_events, list):
        return []
    events: list[dict[str, Any]] = []
    for event in raw_events:
        if not isinstance(event, dict):
            continue
        events.append(_jsonable(event))
    return events


def _extract_score_edit_audit_events_from_value(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    event = value.get(SCORE_EDIT_AUDIT_EVENT_KEY)
    if isinstance(event, dict):
        kind = str(event.get("kind") or event.get("k") or "").strip().lower()
        if kind == "score_edit":
            if "kind" not in event and "k" in event:
                error_text = str(event.get("e") or "").strip()
                handle_status = str(event.get("hs") or "").strip().lower()
                success_value = event.get("s")
                if isinstance(success_value, bool):
                    success = success_value
                else:
                    success = handle_status == "completed" and not error_text
                return [
                    {
                        "kind": "score_edit",
                        "success": success,
                        "version_id": event.get("v"),
                        "parent_version_id": event.get("p"),
                        "version_url": event.get("u"),
                        "parent_version_url": event.get("pu"),
                        "handle_status": event.get("hs"),
                        "post_submit_test": {"status": event.get("ss")},
                        "post_submit_verification": {"status": event.get("vs")},
                        "push_outcome": event.get("po"),
                        "promoted": event.get("pm"),
                        "changed_fields": (
                            [part for part in str(event.get("cf") or "").split(",") if part]
                            if event.get("cf")
                            else []
                        ),
                        "error": error_text or None,
                    }
                ]
            return [_jsonable(event)]
    return []


def _compact_score_edit_audit_event(latest: dict[str, Any]) -> dict[str, Any]:
    smoke = latest.get("post_submit_test")
    verification = latest.get("post_submit_verification")
    compact: dict[str, Any] = {
        # Keep this payload intentionally tiny so ChatMessage slimming
        # (512-byte nested cap) preserves it in tool_response storage.
        "k": "score_edit",
        "s": bool(latest.get("success")),
        "v": str(latest.get("version_id") or "").strip() or None,
        "p": str(latest.get("parent_version_id") or "").strip() or None,
        "u": str(latest.get("version_url") or "").strip() or None,
        "pu": str(latest.get("parent_version_url") or "").strip() or None,
        "hs": str(latest.get("handle_status") or "").strip() or "unknown",
        "ss": (
            str(smoke.get("status") or "").strip() if isinstance(smoke, dict) else "unknown"
        )
        or "unknown",
        "vs": (
            str(verification.get("status") or "").strip()
            if isinstance(verification, dict)
            else "unknown"
        )
        or "unknown",
        "po": str(latest.get("push_outcome") or "").strip() or "not_pushed",
        "pm": bool(latest.get("promoted")),
        "cf": ",".join(str(field) for field in list(latest.get("changed_fields") or [])[:4]),
    }
    error_text = str(latest.get("error") or "").strip()
    if error_text:
        compact["e"] = error_text[:80]
    return compact


def _attach_console_audit_events(
    envelope: dict[str, Any],
    runtime_context: Any,
    *,
    score_edit_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        return envelope

    events = _extract_console_audit_events(runtime_context)
    if isinstance(score_edit_events, list):
        for event in score_edit_events:
            if isinstance(event, dict):
                events.append(event)

    if events:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for event in events:
            marker = json.dumps(event, sort_keys=True, default=str)
            if marker in seen:
                continue
            seen.add(marker)
            deduped.append(event)
        envelope["console_audit_events"] = deduped
        latest = deduped[-1]
        if isinstance(latest, dict):
            envelope[SCORE_EDIT_AUDIT_COMPACT_KEY] = _compact_score_edit_audit_event(
                latest
            )
    return envelope


def _launch_local_procedure_subprocess(cmd: list[str], procedure_id: str) -> tuple[Any, str]:
    import subprocess

    request_id = os.environ.get("PLEXUS_LAMBDA_REQUEST_ID")
    log_dir = _resolve_procedure_run_log_dir(request_id=request_id)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{procedure_id}.log")
    with open(log_path, "ab", buffering=0) as log_file:
        proc = subprocess.Popen(
            cmd,
            cwd=PLEXUS_PROJECT_ROOT,
            env=_local_procedure_env(),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    return proc, log_path


class TactusTraceStore:
    """Pluggable persistence for execute_tactus run traces."""

    def write(self, record: dict[str, Any]) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class FileTactusTraceStore(TactusTraceStore):
    """Default trace store that writes one JSON file per run under ``directory``."""

    def __init__(self, directory: str) -> None:
        self._directory = directory

    @property
    def directory(self) -> str:
        return self._directory

    def write(self, record: dict[str, Any]) -> str:
        os.makedirs(self._directory, exist_ok=True)
        trace_id = record["trace_id"]
        path = os.path.join(self._directory, f"{trace_id}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True, default=str)
        return path


def _default_trace_store() -> TactusTraceStore:
    request_id = os.environ.get("PLEXUS_LAMBDA_REQUEST_ID")
    return FileTactusTraceStore(_resolve_trace_dir(request_id=request_id))


class TactusHandleStore:
    """Pluggable persistence for long-running execute_tactus handles."""

    def create(
        self,
        *,
        kind: str,
        parent_trace_id: str,
        api_call: str,
        args: dict[str, Any],
        dispatch_result: dict[str, Any],
        child_budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    def get(self, handle_id: str) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError

    def update(
        self, handle_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:  # pragma: no cover - interface
        raise NotImplementedError


class FileTactusHandleStore(TactusHandleStore):
    """Default handle store backed by JSON files next to Tactus traces."""

    def __init__(self, directory: str) -> None:
        self._directory = directory

    def _path(self, handle_id: str) -> str:
        if (
            not handle_id
            or "/" in handle_id
            or "\\" in handle_id
            or handle_id.startswith(".")
        ):
            raise ValueError(f"Invalid execute_tactus handle id: {handle_id!r}")
        return os.path.join(self._directory, f"{handle_id}.json")

    def create(
        self,
        *,
        kind: str,
        parent_trace_id: str,
        api_call: str,
        args: dict[str, Any],
        dispatch_result: dict[str, Any],
        child_budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        os.makedirs(self._directory, exist_ok=True)
        handle_id = str(uuid.uuid4())
        created_at = _iso(time.time())
        dashboard_url = dispatch_result.get("dashboard_url") or dispatch_result.get(
            "status_url"
        )
        status = str(dispatch_result.get("status") or "running")
        if status == "dispatched":
            status = "running"
        record = {
            "id": handle_id,
            "kind": kind,
            "status": status,
            "status_url": dashboard_url,
            "created_at": created_at,
            "updated_at": created_at,
            "parent_trace_id": parent_trace_id,
            "api_call": api_call,
            "args": _jsonable(args),
            "dispatch_result": _jsonable(dispatch_result),
            "child_budget": _jsonable(child_budget),
        }
        with open(self._path(handle_id), "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True, default=str)
        return _public_handle(record)

    def get(self, handle_id: str) -> dict[str, Any]:
        path = self._path(handle_id)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Unknown execute_tactus handle: {handle_id}")
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def update(self, handle_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        record = self.get(handle_id)
        record.update(_jsonable(updates))
        record["updated_at"] = _iso(time.time())
        with open(self._path(handle_id), "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True, default=str)
        return record


def _default_handle_store() -> TactusHandleStore:
    request_id = os.environ.get("PLEXUS_LAMBDA_REQUEST_ID")
    return FileTactusHandleStore(os.path.join(_resolve_trace_dir(request_id=request_id), "handles"))


def _build_trace_record(
    *,
    trace_id: str,
    envelope: dict[str, Any],
    submitted_tactus: str,
    wrapped_tactus: str | None,
    runtime_result: Any = None,
    started_at_wall: float,
    ended_at_wall: float,
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "started_at": _iso(started_at_wall),
        "ended_at": _iso(ended_at_wall),
        "duration_ms": int(round((ended_at_wall - started_at_wall) * 1000)),
        "ok": envelope.get("ok"),
        "value": envelope.get("value"),
        "error": envelope.get("error"),
        "cost": envelope.get("cost"),
        "partial": envelope.get("partial", False),
        "api_calls": envelope.get("api_calls", []),
        "submitted_tactus": submitted_tactus,
        "wrapped_tactus": wrapped_tactus,
        "tactus_runtime_result": (
            _jsonable(runtime_result) if runtime_result is not None else None
        ),
    }


def _iso(epoch_seconds: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_seconds))


def _safe_write_trace(store: TactusTraceStore, record: dict[str, Any]) -> None:
    try:
        store.write(record)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to write Tactus trace %s: %s", record.get("trace_id"), exc
        )


HELPER_BINDINGS: tuple[tuple[str, str, str], ...] = (
    ("scorecards_list", "scorecards", "list"),
    ("scorecards_info", "scorecards", "info"),
    ("scorecards_search", "scorecards", "search"),
    ("scorecards_create", "scorecards", "create"),
    ("scorecards_update", "scorecards", "update"),
    ("scorecards_delete", "scorecards", "delete"),
    ("score_info", "score", "info"),
    ("score_create", "score", "create"),
    ("score_search", "score", "search"),
    ("score_evaluations", "score", "evaluations"),
    ("score_predict", "score", "predict"),
    ("score_contradictions", "score", "contradictions"),
    ("score_pull", "score", "pull"),
    ("score_resolve", "score", "resolve"),
    ("score_update", "score", "update"),
    ("score_delete", "score", "delete"),
    ("score_edit", "score", "edit"),
    ("score_test", "score", "test"),
    ("score_set_champion", "score", "set_champion"),
    ("item_info", "item", "info"),
    ("item_last", "item", "last"),
    ("feedback_find", "feedback", "find"),
    ("feedback_alignment", "feedback", "alignment"),
    ("feedback_alignment_batch", "feedback", "alignment_batch"),
    ("feedback_latest_update", "feedback", "latest_update"),
    ("acceptance_rate", "report", "acceptance_rate"),
    ("report_acceptance_rate", "report", "acceptance_rate"),
    ("score_champion_version_timeline", "report", "score_champion_version_timeline"),
    ("report_score_champion_version_timeline", "report", "score_champion_version_timeline"),
    ("rubric_memory_recent_entries", "rubric_memory", "recent_entries"),
    ("rubric_memory_evidence_pack", "rubric_memory", "evidence_pack"),
    ("rubric_memory_sme_question_gate", "rubric_memory", "sme_question_gate"),
    ("evaluation_info", "evaluation", "info"),
    ("evaluation_find_recent", "evaluation", "find_recent"),
    ("evaluation_compare", "evaluation", "compare"),
    ("evaluation_archive", "evaluation", "archive"),
    ("evaluation_run", "evaluation", "run"),
    ("dataset_build_from_feedback_window", "dataset", "build_from_feedback_window"),
    ("dataset_check_associated", "dataset", "check_associated"),
    ("report_configurations_list", "report", "configurations_list"),
    ("report_list", "report", "list"),
    ("report_info", "report", "info"),
    ("report_blocks", "report", "blocks"),
    ("report_run", "report", "run"),
    ("procedure_info", "procedure", "info"),
    ("procedure_list", "procedure", "list"),
    ("procedure_archive", "procedure", "archive"),
    ("procedure_chat_sessions", "procedure", "chat_sessions"),
    ("procedure_chat_messages", "procedure", "chat_messages"),
    ("procedure_steering_messages", "procedure", "steering_messages"),
    ("procedure_run", "procedure", "run"),
    ("procedure_optimize", "procedure", "optimize"),
    ("procedure_optimize_batch", "procedure", "optimize_batch"),
    ("procedure_status_batch", "procedure", "status_batch"),
    ("procedure_continue", "procedure", "continue"),
    ("procedure_branch", "procedure", "branch"),
    ("handle_peek", "handle", "peek"),
    ("handle_status", "handle", "status"),
    ("handle_await", "handle", "await"),
    ("handle_cancel", "handle", "cancel"),
    ("docs_list", "docs", "list"),
    ("docs_get", "docs", "get"),
    ("skills_list", "skills", "list"),
    ("skills_get", "skills", "get"),
    ("guidelines_validate", "guidelines", "validate"),
    ("optimization_rank", "optimization", "rank"),
    ("optimization_assess", "optimization", "assess"),
    ("optimization_diagnose", "optimization", "diagnose"),
    ("optimization_run", "optimization", "run"),
    ("optimization_review", "optimization", "review"),
    ("optimization_summary", "optimization", "summary"),
    ("api_list", "api", "list"),
    ("model_frontier_plan", "model_frontier", "plan"),
    ("model_frontier_build_result_row", "model_frontier", "build_result_row"),
    ("model_frontier_finalize", "model_frontier", "finalize"),
    ("scorecard_retarget_plan_score", "scorecard_retarget", "plan_score"),
    ("scorecards", "scorecards", "list"),
    ("scorecard", "scorecards", "info"),
    ("evaluate", "evaluation", "run"),
    ("evaluation", "evaluation", "info"),
    ("recent_evaluations", "evaluation", "find_recent"),
    ("compare_evaluations", "evaluation", "compare"),
    ("predict", "score", "predict"),
    ("score", "score", "info"),
    ("last_item", "item", "last"),
    ("item", "item", "info"),
    ("feedback", "feedback", "find"),
    ("dataset", "dataset", "build_from_feedback_window"),
    ("dataset_association", "dataset", "check_associated"),
    ("report", "report", "run"),
    ("report_configs", "report", "configurations_list"),
    ("procedure", "procedure", "info"),
    ("procedures", "procedure", "list"),
    ("procedure_sessions", "procedure", "chat_sessions"),
    ("procedure_messages", "procedure", "chat_messages"),
    ("procedure_steering", "procedure", "steering_messages"),
)

# Long-running operations require handle/streaming semantics that the v0 prototype
# does not yet implement. See Kanbus epic plx-247588 (streaming + handle ergonomics)
# for the contract these will follow. Until that lands, these calls short-circuit
# with a structured `requires_handle_protocol` error rather than blocking the
# synchronous Tactus runtime for tens of minutes or hours.
LONG_RUNNING_METHODS: frozenset[tuple[str, str]] = frozenset({})


class RequiresHandleProtocol(RuntimeError):
    """Raised when a long-running Plexus runtime API is called in v0."""

    def __init__(self, namespace: str, method: str) -> None:
        super().__init__(
            f"plexus.{namespace}.{method} requires the long-running handle/streaming "
            "protocol (see Kanbus epic plx-247588) and is not enabled in this "
            "execute_tactus build."
        )
        self.namespace = namespace
        self.method = method


class PlanningModeToolNotAllowed(PermissionError):
    """Raised when planning mode blocks a significant mutation."""

    def __init__(self, namespace: str, method: str) -> None:
        super().__init__(
            f"plexus.{namespace}.{method} is visible for planning, but cannot run "
            "while Console is in planning mode because it can create or mutate "
            "score versions, promote champions, or start/continue procedure runs. "
            "Switch the chat to Execute mode before calling this method."
        )
        self.namespace = namespace
        self.method = method


class ConsoleScoreCodeUpdateRequiresSubagent(PermissionError):
    """Raised when console chat tries to update score code directly."""

    def __init__(self) -> None:
        super().__init__(
            "Console chat cannot call plexus.score.update with direct score code "
            "or YAML content. Use plexus.score.edit with a concrete instruction so "
            "the dedicated score editor worker creates the updated score version."
        )


class ConsoleGuidelinesUpdateRequiresGuidelinesIntent(PermissionError):
    """Raised when console chat tries a guidelines update for a behavior request."""

    def __init__(self) -> None:
        super().__init__(
            "Console chat can use plexus.score.update with guidelines only when "
            "the current user request is explicitly about guidelines, rubric, or "
            "policy wording. For scoring behavior, classifier logic, prompt, or "
            "stricter/looser scoring requests, use plexus.score.edit instead."
        )


class ConsoleScoreEditBlockedForGuidelinesOnly(PermissionError):
    """Raised when a guidelines-only Console request attempts a code-edit workflow."""

    def __init__(self) -> None:
        super().__init__(
            "Console chat cannot call plexus.score.edit for an explicitly guidelines-only, "
            "behavior-preserving request. Load the full current guidelines and use "
            "plexus.score.update with guidelines only."
        )


class ConsoleScoreEditRequiresConcreteInstruction(PermissionError):
    """Raised when Console attempts a candidate-only score edit with no requested change."""

    def __init__(self) -> None:
        super().__init__(
            "Console chat cannot start plexus.score.edit from a candidate-only approval "
            "without a concrete score change. Ask what behavior, code, or prompt should "
            "change, or continue the specific proposal already present in this chat session."
        )


@dataclass(frozen=True)
class RuntimeMethodSpec:
    handler: str
    planning_allowed: bool


MCP_TOOL_MAP: dict[tuple[str, str], str] = {}


def _method_spec(handler: str, *, planning_allowed: bool) -> RuntimeMethodSpec:
    return RuntimeMethodSpec(handler=handler, planning_allowed=planning_allowed)


# Per-method handlers implemented directly on PlexusRuntimeModule (no MCP loopback).
# Each (namespace, method) here MUST NOT also appear in MCP_TOOL_MAP — every
# method has exactly one dispatcher and one planning-mode policy.
RUNTIME_METHOD_SPECS: dict[tuple[str, str], RuntimeMethodSpec] = {
    ("scorecards", "list"): _method_spec("_call_scorecards", planning_allowed=True),
    ("scorecards", "info"): _method_spec("_call_scorecards", planning_allowed=True),
    ("scorecards", "search"): _method_spec("_call_scorecards", planning_allowed=True),
    ("scorecards", "create"): _method_spec("_call_scorecards", planning_allowed=False),
    ("scorecards", "update"): _method_spec("_call_scorecards", planning_allowed=False),
    ("scorecards", "delete"): _method_spec("_call_scorecards", planning_allowed=False),
    ("score", "info"): _method_spec("_call_score", planning_allowed=True),
    ("score", "create"): _method_spec("_call_score", planning_allowed=False),
    ("score", "search"): _method_spec("_call_score", planning_allowed=True),
    ("score", "evaluations"): _method_spec("_call_score", planning_allowed=True),
    ("score", "predict"): _method_spec("_call_score", planning_allowed=True),
    ("score", "contradictions"): _method_spec("_call_score", planning_allowed=True),
    ("score", "pull"): _method_spec("_call_score", planning_allowed=True),
    ("score", "resolve"): _method_spec("_call_score", planning_allowed=True),
    ("score", "update"): _method_spec("_call_score", planning_allowed=False),
    ("score", "delete"): _method_spec("_call_score", planning_allowed=False),
    ("score", "edit"): _method_spec("_call_score", planning_allowed=False),
    ("score", "test"): _method_spec("_call_score", planning_allowed=True),
    ("score", "set_champion"): _method_spec("_call_score", planning_allowed=False),
    ("item", "info"): _method_spec("_call_item", planning_allowed=True),
    ("item", "last"): _method_spec("_call_item", planning_allowed=True),
    ("feedback", "find"): _method_spec("_call_feedback", planning_allowed=True),
    ("feedback", "alignment"): _method_spec("_call_feedback", planning_allowed=True),
    ("feedback", "alignment_batch"): _method_spec("_call_feedback", planning_allowed=True),
    ("feedback", "latest_update"): _method_spec("_call_feedback", planning_allowed=True),
    ("evaluation", "info"): _method_spec("_call_evaluation_read", planning_allowed=True),
    ("evaluation", "find_recent"): _method_spec("_call_evaluation_read", planning_allowed=True),
    ("evaluation", "compare"): _method_spec("_call_evaluation_read", planning_allowed=True),
    ("evaluation", "archive"): _method_spec("_call_evaluation_write", planning_allowed=False),
    ("evaluation", "run"): _method_spec("_call_evaluation_run", planning_allowed=True),
    ("report", "run"): _method_spec("_call_report_run", planning_allowed=True),
    ("report", "acceptance_rate"): _method_spec("_call_report_run", planning_allowed=True),
    ("report", "score_champion_version_timeline"): _method_spec("_call_report_run", planning_allowed=True),
    ("report", "configurations_list"): _method_spec("_call_report_read", planning_allowed=True),
    ("report", "list"): _method_spec("_call_report_read", planning_allowed=True),
    ("report", "info"): _method_spec("_call_report_read", planning_allowed=True),
    ("report", "blocks"): _method_spec("_call_report_read", planning_allowed=True),
    ("dataset", "build_from_feedback_window"): _method_spec("_call_dataset", planning_allowed=True),
    ("dataset", "check_associated"): _method_spec("_call_dataset", planning_allowed=True),
    ("procedure", "list"): _method_spec("_call_procedure_read", planning_allowed=True),
    ("procedure", "info"): _method_spec("_call_procedure_read", planning_allowed=True),
    ("procedure", "chat_sessions"): _method_spec("_call_procedure_read", planning_allowed=True),
    ("procedure", "chat_messages"): _method_spec("_call_procedure_read", planning_allowed=True),
    ("procedure", "steering_messages"): _method_spec("_call_procedure_read", planning_allowed=True),
    ("procedure", "archive"): _method_spec("_call_procedure_write", planning_allowed=False),
    ("procedure", "run"): _method_spec("_call_procedure_run", planning_allowed=False),
    ("procedure", "optimize"): _method_spec("_call_procedure_run", planning_allowed=False),
    ("procedure", "optimize_batch"): _method_spec("_call_procedure_run", planning_allowed=False),
    ("procedure", "status_batch"): _method_spec("_call_procedure_read", planning_allowed=True),
    ("procedure", "continue"): _method_spec("_call_procedure_run", planning_allowed=False),
    ("procedure", "branch"): _method_spec("_call_procedure_run", planning_allowed=False),
    ("handle", "peek"): _method_spec("_call_handle", planning_allowed=True),
    ("handle", "status"): _method_spec("_call_handle", planning_allowed=True),
    ("handle", "await"): _method_spec("_call_handle", planning_allowed=True),
    ("handle", "cancel"): _method_spec("_call_handle", planning_allowed=False),
    ("skills", "list"): _method_spec("_call_skills", planning_allowed=True),
    ("skills", "get"): _method_spec("_call_skills", planning_allowed=True),
    ("guidelines", "validate"): _method_spec("_call_guidelines", planning_allowed=True),
    ("rubric_memory", "recent_entries"): _method_spec("_call_rubric_memory", planning_allowed=True),
    ("rubric_memory", "evidence_pack"): _method_spec("_call_rubric_memory", planning_allowed=True),
    ("rubric_memory", "sme_question_gate"): _method_spec("_call_rubric_memory", planning_allowed=True),
    ("model_frontier", "plan"): _method_spec("_call_model_frontier", planning_allowed=True),
    ("model_frontier", "build_result_row"): _method_spec("_call_model_frontier", planning_allowed=True),
    ("model_frontier", "finalize"): _method_spec("_call_model_frontier", planning_allowed=False),
    ("scorecard_retarget", "plan_score"): _method_spec("_call_scorecard_retarget", planning_allowed=True),
    # The decision service owns policy and packet construction.  The runtime
    # only exposes its methods, supplies existing Plexus capabilities, and
    # blocks optimizer dispatch in Console planning mode.
    ("optimization", "rank"): _method_spec("_call_optimization", planning_allowed=True),
    ("optimization", "assess"): _method_spec("_call_optimization", planning_allowed=True),
    ("optimization", "diagnose"): _method_spec("_call_optimization", planning_allowed=True),
    ("optimization", "run"): _method_spec("_call_optimization", planning_allowed=False),
    ("optimization", "review"): _method_spec("_call_optimization", planning_allowed=True),
    ("optimization", "summary"): _method_spec("_call_optimization", planning_allowed=True),
}


DIRECT_HANDLERS: dict[tuple[str, str], str] = {
    key: spec.handler for key, spec in RUNTIME_METHOD_SPECS.items()
}


def _default_scorecards_list(args: dict[str, Any]) -> Any:
    """Run plexus.scorecards.list directly against the dashboard.

    Equivalent to the legacy `plexus_scorecards_list` MCP tool but native
    Python so the runtime no longer depends on the legacy tool registration.
    """

    import json as _json

    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.memoized_resolvers import (
        memoized_resolve_scorecard_identifier,
    )

    identifier = args.get("identifier") or args.get("name") or args.get("key")
    next_token = args.get("next_token") or args.get("nextToken")
    return_metadata = bool(args.get("return_metadata", False))
    include_scores = bool(args.get("_include_scores", False))

    raw_limit = args.get("limit")
    if raw_limit is None:
        fetch_limit = 1000
    else:
        try:
            fetch_limit = int(raw_limit)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"plexus.scorecards.list limit must be an integer, got {raw_limit!r}"
            ) from exc
        if fetch_limit < 1:
            raise ValueError(
                "plexus.scorecards.list limit must be a positive integer"
            )

    client = create_client()
    if not client:
        raise RuntimeError("plexus.scorecards.list: could not create dashboard client")

    if identifier:
        scorecard_id = memoized_resolve_scorecard_identifier(client, str(identifier))
        if scorecard_id:
            query = (
                'query GetScorecard { '
                f'getScorecard(id: "{scorecard_id}") {{ '
                "id name key description externalId createdAt updatedAt "
                "} }"
            )
            response = client.execute(query)
            if "errors" in response:
                raise RuntimeError(
                    "plexus.scorecards.list dashboard error: "
                    + _json.dumps(response["errors"])
                )
            scorecard_data = response.get("getScorecard")
            items = [scorecard_data] if scorecard_data else []
            if return_metadata:
                return {"items": items, "nextToken": None}
            return items

    filter_parts: list[str] = []
    account_id = _resolve_runtime_account_id(client, args, "plexus.scorecards.list")
    filter_parts.append(f'accountId: {{ eq: "{account_id}" }}')
    if identifier:
        ident = str(identifier)
        if " " in ident or not ident.islower():
            filter_parts.append(f'name: {{ contains: "{ident}" }}')
        else:
            filter_parts.append(
                f'or: [{{name: {{ contains: "{ident}" }}}}, '
                f'{{key: {{ contains: "{ident}" }}}}]'
            )

    filter_str = ", ".join(filter_parts)
    next_token_arg = f', nextToken: "{next_token}"' if next_token else ""
    scorecard_fields = "id name key description externalId createdAt updatedAt"
    if include_scores:
        # Portfolio ranking consumes these fields directly from the exhaustive
        # inventory.  Do not re-resolve identifiers per score just to learn
        # whether the score is eligible for ranking.
        scorecard_fields += (
            " sections { items { scores { items { "
            "id name championVersionId isDisabled updatedAt "
            "championVersion { id scoreId createdAt } "
            "versions(sortDirection: DESC, limit: 1) { items { id createdAt } } "
            "} } } }"
        )
    query = (
        "query ListScorecards { "
        f"listScorecards(filter: {{ {filter_str} }}, limit: {fetch_limit}{next_token_arg}) {{ "
        f"items {{ {scorecard_fields} }} "
        "nextToken } }"
    )
    response = client.execute(query)
    if "errors" in response:
        raise RuntimeError(
            "plexus.scorecards.list dashboard error: "
            + _json.dumps(response["errors"])
        )

    list_scorecards = response.get("listScorecards") or {}
    items = list_scorecards.get("items") or []
    next_token_value = list_scorecards.get("nextToken")
    if return_metadata:
        return {"items": items, "nextToken": next_token_value}
    return items


def _default_scorecards_info(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.scorecards.info directly against the dashboard."""

    import json as _json

    from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
    from plexus.cli.shared.client_utils import create_client

    identifier = (
        args.get("identifier")
        or args.get("scorecard_identifier")
        or args.get("id")
        or args.get("name")
        or args.get("key")
        or args.get("external_id")
        or args.get("externalId")
    )
    if not identifier:
        raise ValueError(
            "plexus.scorecards.info requires identifier (id, name, key, or external_id)"
        )

    client = create_client()
    if not client:
        raise RuntimeError("plexus.scorecards.info: could not create dashboard client")

    scorecard_id = resolve_scorecard_identifier(client, str(identifier))
    if not scorecard_id:
        raise ValueError(
            f"plexus.scorecards.info: scorecard {identifier!r} not found"
        )

    query = (
        "query GetScorecard { "
        f'getScorecard(id: "{scorecard_id}") {{ '
        "id name key description guidelines externalId createdAt updatedAt "
        "sections { items { id name order scores { items { "
        "id name key description type order externalId } } } } "
        "} }"
    )
    response = client.execute(query)
    if "errors" in response:
        raise RuntimeError(
            "plexus.scorecards.info dashboard error: "
            + _json.dumps(response["errors"])
        )

    data = response.get("getScorecard")
    if not data:
        raise ValueError(
            f"plexus.scorecards.info: scorecard {identifier!r} (id {scorecard_id}) "
            "not found after query"
        )

    return {
        "name": data.get("name"),
        "key": data.get("key"),
        "externalId": data.get("externalId"),
        "description": data.get("description"),
        "guidelines": data.get("guidelines"),
        "additionalDetails": {
            "id": data.get("id"),
            "createdAt": data.get("createdAt"),
            "updatedAt": data.get("updatedAt"),
        },
        "sections": data.get("sections"),
    }


def _search_query_string(args: dict[str, Any]) -> str:
    raw = args.get("query") or args.get("q") or args.get("name")
    if raw is None:
        return ""
    text = str(raw).strip()
    return text


def _default_scorecards_search(args: dict[str, Any]) -> dict[str, Any]:
    """Fuzzy-search scorecards by name, key, and externalId (RapidFuzz WRatio)."""

    import json as _json

    from rapidfuzz import fuzz, process

    from plexus.cli.shared.client_utils import create_client

    query = _search_query_string(args)
    if not query:
        raise ValueError(
            "plexus.scorecards.search requires query (or q / name)"
        )

    try:
        result_limit = int(args.get("limit") or 20)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"plexus.scorecards.search limit must be an integer, got {args.get('limit')!r}"
        ) from exc
    if result_limit < 1:
        raise ValueError("plexus.scorecards.search limit must be a positive integer")

    try:
        min_score = float(args.get("min_score") if args.get("min_score") is not None else 55.0)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"plexus.scorecards.search min_score must be a number, got {args.get('min_score')!r}"
        ) from exc

    try:
        fetch_limit = int(args.get("scorecard_limit") or args.get("fetch_limit") or 1000)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "plexus.scorecards.search scorecard_limit must be an integer"
        ) from exc
    if fetch_limit < 1:
        raise ValueError(
            "plexus.scorecards.search scorecard_limit must be a positive integer"
        )

    client = create_client()
    if not client:
        raise RuntimeError("plexus.scorecards.search: could not create dashboard client")

    filter_parts: list[str] = []
    account_id = _resolve_runtime_account_id(client, args, "plexus.scorecards.search")
    filter_parts.append(f'accountId: {{ eq: "{account_id}" }}')
    filter_str = ", ".join(filter_parts)
    gql = (
        "query ListScorecardsForSearch { "
        f"listScorecards(filter: {{ {filter_str} }}, limit: {fetch_limit}) {{ "
        "items { id name key description externalId createdAt updatedAt } "
        "nextToken } }"
    )
    response = client.execute(gql)
    if "errors" in response:
        raise RuntimeError(
            "plexus.scorecards.search dashboard error: "
            + _json.dumps(response["errors"])
        )
    items = (response.get("listScorecards") or {}).get("items") or []

    choices: list[str] = []
    metas: list[dict[str, Any]] = []
    for row in items:
        name = str(row.get("name") or "")
        key = str(row.get("key") or "")
        ext = str(row.get("externalId") or "")
        desc = str(row.get("description") or "")
        choice = " ".join(part for part in (name, key, ext, desc) if part).strip()
        if not choice:
            choice = str(row.get("id") or "")
        choices.append(choice)
        metas.append(row)

    if not choices:
        return {
            "success": True,
            "query": query,
            "count": 0,
            "matches": [],
            "message": "No scorecards available to search",
        }

    extracted = process.extract(
        query,
        choices,
        scorer=fuzz.WRatio,
        limit=len(choices),
    )
    hits: list[dict[str, Any]] = []
    for _choice_text, score, idx in extracted:
        if float(score) < min_score:
            continue
        row = metas[idx]
        hits.append(
            {
                "match_score": float(score),
                "matched_choice": choices[idx],
                "scorecard": {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "key": row.get("key"),
                    "externalId": row.get("externalId"),
                    "description": row.get("description"),
                    "createdAt": row.get("createdAt"),
                    "updatedAt": row.get("updatedAt"),
                },
            }
        )
        if len(hits) >= result_limit:
            break

    return {
        "success": True,
        "query": query,
        "count": len(hits),
        "matches": hits,
    }


def _default_scorecards_create(args: dict[str, Any]) -> dict[str, Any]:
    """Create a scorecard directly in Plexus."""
    from plexus.attribution.actor_context import apply_actor_attribution
    from plexus.cli.report.utils import resolve_account_id_for_command
    from plexus.cli.shared.client_utils import create_client

    def _slugify(value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower())
        return cleaned.strip("-") or "scorecard"

    name = str(args.get("name") or "").strip()
    if not name:
        raise ValueError("plexus.scorecards.create requires name")

    key = str(args.get("key") or "").strip() or _slugify(name)

    # Parse external_id - handle both int and string inputs
    external_id_raw = args.get("external_id") or args.get("externalId")
    if external_id_raw is not None:
        # If it's an int, keep it as int; if string, try to parse as int
        if isinstance(external_id_raw, int):
            external_id = external_id_raw
        else:
            external_id_str = str(external_id_raw).strip()
            try:
                external_id = int(external_id_str) if external_id_str else None
            except ValueError:
                external_id = external_id_str if external_id_str else None
    else:
        external_id = None

    description = str(args.get("description") or "").strip() or None
    account_identifier = args.get("account_identifier") or args.get("account") or args.get("account_id") or None

    client = create_client()
    if not client:
        raise RuntimeError("plexus.scorecards.create: could not create dashboard client")

    account_id = resolve_account_id_for_command(
        client,
        str(account_identifier) if account_identifier is not None else None,
    )

    mutation = """
    mutation CreateScorecard($input: CreateScorecardInput!) {
      createScorecard(input: $input) {
        id
        name
        key
        externalId
      }
    }
    """

    # Compatibility strategy:
    # 1) Try most complete variants first (with all provided fields)
    # 2) Fall back to simpler variants if complete ones fail
    # This ensures external_id and other fields are actually used
    base_variants: list[dict[str, Any]] = []

    # Most complete first
    if key and external_id and description:
        base_variants.append({
            "name": name,
            "key": key,
            "externalId": external_id,
            "description": description,
        })
    if key and external_id:
        base_variants.append({"name": name, "key": key, "externalId": external_id})
    if external_id and description:
        base_variants.append({"name": name, "externalId": external_id, "description": description})
    if key and description:
        base_variants.append({"name": name, "key": key, "description": description})
    if external_id:
        base_variants.append({"name": name, "externalId": external_id})
    if description:
        base_variants.append({"name": name, "description": description})
    if key:
        base_variants.append({"name": name, "key": key})
    # Simplest last (fallback)
    base_variants.append({"name": name})

    if account_id:
        account_variants: list[dict[str, Any]] = []
        for variant in base_variants:
            with_account = dict(variant)
            with_account["accountId"] = account_id
            account_variants.append(with_account)
        base_variants.extend(account_variants)

    attempted_errors: list[str] = []
    seen_payloads: set[str] = set()

    for use_attribution in (False, True):
        for variant in base_variants:
            input_obj = dict(variant)
            if use_attribution:
                input_obj = apply_actor_attribution(
                    input_obj,
                    client_context=getattr(client, "context", None),
                    source="execute_tactus",
                )

            payload_key = json.dumps(input_obj, sort_keys=True, default=str)
            if payload_key in seen_payloads:
                continue
            seen_payloads.add(payload_key)

            try:
                response = client.execute(mutation, {"input": input_obj})
                created = (response or {}).get("createScorecard") or {}
                created_id = created.get("id")
                if created_id:
                    # Create a default section for the scorecard
                    section_mutation = """
                    mutation CreateSection($input: CreateScorecardSectionInput!) {
                        createScorecardSection(input: $input) {
                            id
                            name
                        }
                    }
                    """
                    section_input = {
                        "scorecardId": created_id,
                        "name": "Default",
                        "order": 0,
                    }
                    try:
                        section_response = client.execute(section_mutation, {"input": section_input})
                        created_section = (section_response or {}).get("createScorecardSection") or {}
                        section_id = created_section.get("id")
                    except Exception as section_exc:
                        logger.warning(
                            f"Failed to create default section for scorecard {created_id}: {section_exc}"
                        )
                        section_id = None

                    return {
                        "success": True,
                        "id": created_id,
                        "name": created.get("name"),
                        "key": created.get("key"),
                        "externalId": created.get("externalId"),
                        "defaultSectionId": section_id,
                    }
                attempted_errors.append(
                    f"attribution={use_attribution} payload={input_obj!r} -> missing id in response {response!r}"
                )
            except Exception as exc:
                attempted_errors.append(
                    f"attribution={use_attribution} payload={input_obj!r} -> {exc}"
                )

    raise RuntimeError(
        "plexus.scorecards.create failed after compatibility attempts: "
        + " | ".join(attempted_errors)
    )


def _default_scorecards_update(args: dict[str, Any]) -> dict[str, Any]:
    """Update scorecard metadata without changing its scores or versions."""
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.direct_identifier_resolution import (
        direct_resolve_scorecard_identifier,
    )

    identifier = (
        args.get("id")
        or args.get("scorecard_id")
        or args.get("identifier")
        or args.get("scorecard_identifier")
        or args.get("scorecard")
    )
    if not identifier:
        raise ValueError("plexus.scorecards.update requires id or scorecard identifier")

    fields = {
        "name": "name",
        "key": "key",
        "description": "description",
        "external_id": "externalId",
        "externalId": "externalId",
    }
    updates = {
        graph_field: args[arg_name]
        for arg_name, graph_field in fields.items()
        if args.get(arg_name) is not None
    }
    if not updates:
        raise ValueError(
            "plexus.scorecards.update requires at least one metadata field "
            "(name, key, description, or external_id)"
        )

    client = create_client()
    if not client:
        raise RuntimeError("plexus.scorecards.update: could not create dashboard client")
    scorecard_id = direct_resolve_scorecard_identifier(client, str(identifier))
    if not scorecard_id:
        raise ValueError(f"Scorecard not found: {identifier!r}")

    # UpdateScorecardInput deliberately contains only model fields; unlike a
    # create input it does not accept the runtime attribution metadata.
    input_obj = {"id": scorecard_id, **updates}
    mutation = """
    mutation UpdateScorecard($input: UpdateScorecardInput!) {
      updateScorecard(input: $input) { id name key description externalId }
    }
    """
    response = client.execute(mutation, {"input": input_obj})
    updated = (response or {}).get("updateScorecard") or {}
    if not updated.get("id"):
        raise RuntimeError("plexus.scorecards.update returned no scorecard")
    return {"success": True, "scorecard": updated, "changed_fields": sorted(updates)}


def _default_scorecards_delete(args: dict[str, Any]) -> dict[str, Any]:
    """Delete an explicitly confirmed scorecard and all of its contents."""
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.direct_identifier_resolution import (
        direct_resolve_scorecard_identifier,
    )

    if args.get("confirmed") is not True:
        raise ValueError(
            "plexus.scorecards.delete is destructive and requires confirmed = true"
        )
    identifier = (
        args.get("id")
        or args.get("scorecard_id")
        or args.get("identifier")
        or args.get("scorecard_identifier")
        or args.get("scorecard")
    )
    if not identifier:
        raise ValueError("plexus.scorecards.delete requires id or scorecard identifier")

    client = create_client()
    if not client:
        raise RuntimeError("plexus.scorecards.delete: could not create dashboard client")
    scorecard_id = direct_resolve_scorecard_identifier(client, str(identifier))
    if not scorecard_id:
        raise ValueError(f"Scorecard not found: {identifier!r}")

    info = _default_scorecards_info({"id": scorecard_id})
    sections = ((info.get("sections") or {}).get("items") or [])
    deleted_scores = 0
    deleted_sections = 0
    for section in sections:
        for score in ((section.get("scores") or {}).get("items") or []):
            score_id = score.get("id")
            if not score_id:
                continue
            _default_score_delete({"id": score_id, "confirmed": True})
            deleted_scores += 1
        section_id = section.get("id")
        if section_id:
            mutation = """
            mutation DeleteScorecardSection($input: DeleteScorecardSectionInput!) {
              deleteScorecardSection(input: $input) { id }
            }
            """
            client.execute(
                mutation,
                {"input": {"id": section_id}},
            )
            deleted_sections += 1

    mutation = """
    mutation DeleteScorecard($input: DeleteScorecardInput!) {
      deleteScorecard(input: $input) { id }
    }
    """
    response = client.execute(
        mutation,
        {"input": {"id": scorecard_id}},
    )
    deleted = (response or {}).get("deleteScorecard") or {}
    if not deleted.get("id"):
        raise RuntimeError("plexus.scorecards.delete returned no scorecard")
    return {
        "success": True,
        "id": deleted["id"],
        "deleted_scores": deleted_scores,
        "deleted_sections": deleted_sections,
    }


def _default_score_search(args: dict[str, Any]) -> dict[str, Any]:
    """Fuzzy-search scores by name (and key / externalId) across scorecards."""

    import json as _json

    from rapidfuzz import fuzz, process

    from plexus.cli.report.utils import resolve_account_id_for_command
    from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
    from plexus.cli.shared.client_utils import create_client

    query = _search_query_string(args)
    if not query:
        raise ValueError("plexus.score.search requires query (or q / name)")

    try:
        result_limit = int(args.get("limit") or 30)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"plexus.score.search limit must be an integer, got {args.get('limit')!r}"
        ) from exc
    if result_limit < 1:
        raise ValueError("plexus.score.search limit must be a positive integer")

    try:
        min_score = float(args.get("min_score") if args.get("min_score") is not None else 55.0)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"plexus.score.search min_score must be a number, got {args.get('min_score')!r}"
        ) from exc

    try:
        scorecard_fetch_limit = int(
            args.get("scorecard_limit") or args.get("fetch_limit") or 100
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "plexus.score.search scorecard_limit must be an integer"
        ) from exc
    if scorecard_fetch_limit < 1:
        raise ValueError(
            "plexus.score.search scorecard_limit must be a positive integer"
        )

    scorecard_identifier = (
        args.get("scorecard_identifier")
        or args.get("scorecard")
        or args.get("scorecard_id")
        or args.get("scorecard_name")
    )

    client = create_client()
    if not client:
        raise RuntimeError("plexus.score.search: could not create dashboard client")

    scorecards: list[dict[str, Any]] = []
    if scorecard_identifier:
        scorecard_id = resolve_scorecard_identifier(client, str(scorecard_identifier))
        if not scorecard_id:
            raise ValueError(
                f"plexus.score.search: scorecard {scorecard_identifier!r} not found"
            )
        result = client.execute(
            f"""query GetScorecardWithScores {{
                getScorecard(id: "{scorecard_id}") {{
                    id name key
                    sections {{ items {{ id name scores {{ items {{
                        id name key externalId description type
                        championVersionId isDisabled
                    }} }} }} }}
                }}
            }}"""
        )
        if "errors" in result:
            raise RuntimeError(
                "plexus.score.search dashboard error: "
                + _json.dumps(result["errors"])
            )
        one = result.get("getScorecard")
        if one:
            scorecards = [one]
    else:
        account_id = _resolve_runtime_account_id(client, args, "plexus.score.search")
        result = client.execute(
            f"""query ListScorecardsForScoreSearch {{
                listScorecards(filter: {{ accountId: {{ eq: "{account_id}" }} }}, limit: {scorecard_fetch_limit}) {{
                    items {{
                        id name key
                        sections {{ items {{ id name scores {{ items {{
                            id name key externalId description type
                            championVersionId isDisabled
                        }} }} }} }}
                    }}
                }}
            }}"""
        )
        if "errors" in result:
            raise RuntimeError(
                "plexus.score.search dashboard error: "
                + _json.dumps(result["errors"])
            )
        scorecards = result.get("listScorecards", {}).get("items") or []

    choices: list[str] = []
    metas: list[dict[str, Any]] = []
    for scorecard in scorecards:
        sc_name = str(scorecard.get("name") or "")
        sc_id = str(scorecard.get("id") or "")
        for section in scorecard.get("sections", {}).get("items", []) or []:
            sec_name = str(section.get("name") or "")
            for score in section.get("scores", {}).get("items", []) or []:
                s_name = str(score.get("name") or "")
                s_key = str(score.get("key") or "")
                ext = str(score.get("externalId") or "")
                choice = (
                    f"{s_name} | key:{s_key} | ext:{ext} | card:{sc_name} | "
                    f"section:{sec_name}"
                )
                choices.append(choice)
                metas.append(
                    {
                        "score": score,
                        "section_name": sec_name,
                        "scorecard_id": sc_id,
                        "scorecard_name": sc_name,
                    }
                )

    if not choices:
        return {
            "success": True,
            "query": query,
            "scorecard_filter": scorecard_identifier,
            "count": 0,
            "matches": [],
            "message": "No scores available to search",
        }

    extracted = process.extract(
        query,
        choices,
        scorer=fuzz.WRatio,
        limit=len(choices),
    )
    hits: list[dict[str, Any]] = []
    for _choice_text, score, idx in extracted:
        if float(score) < min_score:
            continue
        meta = metas[idx]
        sc_row = meta["score"]
        hits.append(
            {
                "match_score": float(score),
                "matched_choice": choices[idx],
                "score_id": sc_row.get("id"),
                "score_name": sc_row.get("name"),
                "score_key": sc_row.get("key"),
                "external_id": sc_row.get("externalId"),
                "section_name": meta["section_name"],
                "scorecard_id": meta["scorecard_id"],
                "scorecard_name": meta["scorecard_name"],
                "is_disabled": sc_row.get("isDisabled", False),
            }
        )
        if len(hits) >= result_limit:
            break

    return {
        "success": True,
        "query": query,
        "scorecard_filter": scorecard_identifier,
        "count": len(hits),
        "matches": hits,
    }


def _make_procedure_service():
    """Build a ProcedureService bound to a fresh dashboard client."""

    from plexus.cli.procedure.service import ProcedureService
    from plexus.cli.shared.client_utils import create_client

    client = create_client()
    if not client:
        raise RuntimeError(
            "plexus.procedure.*: could not create dashboard client"
        )
    return ProcedureService(client)


def _metadata_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except Exception:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _build_archived_metadata(
    existing_metadata: Any,
    *,
    previous_status: str | None,
    reason: str | None = None,
    archived_by: str | None = None,
) -> tuple[dict[str, Any], str]:
    archived_at = _iso(time.time())
    metadata = _metadata_object(existing_metadata)
    archive_entry = _metadata_object(metadata.get("archive"))
    archive_entry["archived"] = True
    archive_entry["archivedAt"] = archived_at
    archive_entry["previousStatus"] = previous_status
    if reason:
        archive_entry["reason"] = reason
    if archived_by:
        archive_entry["archivedBy"] = archived_by
    metadata["archive"] = archive_entry
    return metadata, archived_at


def _default_procedure_list(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.procedure.list directly via ProcedureService."""

    account_identifier = (
        args.get("account_identifier")
        or args.get("account")
        or args.get("account_id")
        or args.get("accountId")
        or os.environ.get("PLEXUS_ACCOUNT_KEY")
    )
    if not account_identifier:
        raise ValueError(
            "plexus.procedure.list requires account_identifier or "
            "PLEXUS_ACCOUNT_KEY environment variable"
        )

    scorecard_identifier = args.get("scorecard_identifier") or args.get("scorecard")
    limit = int(args.get("limit") or 20)

    service = _make_procedure_service()
    procedures = service.list_procedures(
        account_identifier=account_identifier,
        scorecard_identifier=scorecard_identifier,
        limit=limit,
    )
    return {
        "success": True,
        "count": len(procedures),
        "procedures": [
            {
                "id": exp.id,
                "name": getattr(exp, "name", None),
                "status": getattr(exp, "status", None),
                "featured": exp.featured,
                "created_at": exp.createdAt.isoformat(),
                "updated_at": exp.updatedAt.isoformat(),
                "scorecard_id": exp.scorecardId,
                "score_id": exp.scoreId,
            }
            for exp in procedures
        ],
    }


def _default_procedure_info(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.procedure.info directly via ProcedureService."""

    procedure_id = args.get("procedure_id") or args.get("id")
    if not procedure_id:
        raise ValueError("plexus.procedure.info requires id or procedure_id")
    include_yaml = bool(args.get("include_yaml", False))

    service = _make_procedure_service()
    info = service.get_procedure_info(str(procedure_id))
    if not info:
        return {
            "success": False,
            "error": f"Procedure {procedure_id} not found",
        }

    result: dict[str, Any] = {
        "success": True,
        "procedure": {
            "id": info.procedure.id,
            "status": getattr(info.procedure, "status", None),
            "featured": info.procedure.featured,
            "created_at": info.procedure.createdAt.isoformat(),
            "updated_at": info.procedure.updatedAt.isoformat(),
            "account_id": info.procedure.accountId,
            "scorecard_id": info.procedure.scorecardId,
            "score_id": info.procedure.scoreId,
        },
        "summary": {
            "scorecard_name": info.scorecard_name,
            "score_name": info.score_name,
        },
    }
    if include_yaml:
        yaml_config = service.get_procedure_yaml(str(procedure_id))
        if yaml_config:
            result["yaml_config"] = yaml_config
    return result


def _default_procedure_archive(args: dict[str, Any]) -> dict[str, Any]:
    """Archive a procedure by setting status=ARCHIVED and recording archive metadata."""

    from plexus.cli.shared.client_utils import create_client

    procedure_id = args.get("procedure_id") or args.get("id")
    if not procedure_id:
        raise ValueError("plexus.procedure.archive requires id or procedure_id")

    reason = args.get("reason")
    archived_by = args.get("archived_by") or args.get("archivedBy")

    client = create_client()
    if not client:
        raise RuntimeError("plexus.procedure.archive: could not create dashboard client")

    query = """
    query GetProcedureForArchive($id: ID!) {
      getProcedure(id: $id) {
        id
        status
        metadata
      }
    }
    """
    fetched = client.execute(query, {"id": str(procedure_id)})
    procedure = (fetched or {}).get("getProcedure")
    if not procedure:
        raise ValueError(f"Procedure not found: {procedure_id}")

    previous_status = procedure.get("status")
    merged_metadata, archived_at = _build_archived_metadata(
        procedure.get("metadata"),
        previous_status=previous_status,
        reason=str(reason) if reason is not None else None,
        archived_by=str(archived_by) if archived_by is not None else None,
    )

    mutation = """
    mutation UpdateProcedureArchive($input: UpdateProcedureInput!) {
      updateProcedure(input: $input) {
        id
        status
        metadata
        updatedAt
      }
    }
    """
    result = client.execute(
        mutation,
        {
            "input": {
                "id": str(procedure_id),
                "status": "ARCHIVED",
                "metadata": json.dumps(merged_metadata),
            }
        },
    )
    updated = (result or {}).get("updateProcedure")
    if not updated:
        raise RuntimeError(
            f"Failed to archive procedure {procedure_id}: missing updateProcedure payload"
        )

    return {
        "success": True,
        "procedure_id": str(procedure_id),
        "status": updated.get("status") or "ARCHIVED",
        "previous_status": previous_status,
        "archived_at": archived_at,
        "metadata": merged_metadata,
        "updated_at": updated.get("updatedAt"),
    }


def _default_procedure_chat_sessions(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.procedure.chat_sessions directly via dashboard GraphQL."""

    from plexus.dashboard.api.client import PlexusDashboardClient

    procedure_id = args.get("procedure_id") or args.get("id")
    if not procedure_id:
        raise ValueError(
            "plexus.procedure.chat_sessions requires id or procedure_id"
        )
    limit = int(args.get("limit") or 10)

    client = PlexusDashboardClient()
    query = """
    query ListChatSessionByProcedureId($procedureId: String!, $limit: Int!) {
        listChatSessionByProcedureIdAndCreatedAt(
            procedureId: $procedureId
            sortDirection: DESC
            limit: $limit
        ) {
            items {
                id status procedureId createdAt updatedAt
                messages { items { id messageType } }
            }
        }
    }
    """
    result = client.execute(query, {"procedureId": str(procedure_id), "limit": limit})
    if "errors" in result:
        raise RuntimeError(
            f"plexus.procedure.chat_sessions GraphQL errors: {result['errors']}"
        )

    sessions: list = []
    if "data" in result:
        sessions = (
            result["data"]
            .get("listChatSessionByProcedureIdAndCreatedAt", {})
            .get("items", [])
        )
    elif "listChatSessionByProcedureIdAndCreatedAt" in result:
        sessions = result["listChatSessionByProcedureIdAndCreatedAt"].get("items", [])

    processed: list[dict[str, Any]] = []
    for session in sessions:
        messages = session.get("messages", {}).get("items", []) or []
        message_types: dict[str, int] = {}
        for msg in messages:
            mt = msg.get("messageType", "MESSAGE")
            message_types[mt] = message_types.get(mt, 0) + 1
        processed.append(
            {
                "id": session["id"],
                "status": session["status"],
                "created_at": session["createdAt"],
                "updated_at": session.get("updatedAt"),
                "message_count": len(messages),
                "message_types": message_types,
            }
        )

    return {
        "success": True,
        "procedure_id": str(procedure_id),
        "session_count": len(processed),
        "sessions": processed,
    }


def _default_procedure_chat_messages(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.procedure.chat_messages directly via dashboard GraphQL."""

    import json as _json

    from plexus.dashboard.api.client import PlexusDashboardClient

    procedure_id = args.get("procedure_id") or args.get("id")
    session_id = args.get("session_id")
    if not procedure_id and not session_id:
        raise ValueError(
            "plexus.procedure.chat_messages requires id (procedure_id) or session_id"
        )
    limit = int(args.get("limit") or 50)
    show_tool_calls = bool(args.get("show_tool_calls", True))
    show_tool_responses = bool(args.get("show_tool_responses", True))

    client = PlexusDashboardClient()
    if session_id:
        query = """
        query GetChatSession($id: ID!) {
            getChatSession(id: $id) {
                id status procedureId createdAt
                messages { items { id role messageType toolName content
                    toolResponse sequenceNumber parentMessageId createdAt } }
            }
        }
        """
        result = client.execute(query, {"id": str(session_id)})
        if "errors" in result:
            raise RuntimeError(
                f"plexus.procedure.chat_messages GraphQL errors: {result['errors']}"
            )
        session = None
        if "data" in result:
            session = result["data"].get("getChatSession")
        elif "getChatSession" in result:
            session = result["getChatSession"]
        if not session:
            return {
                "success": False,
                "error": f"Session {session_id} not found",
            }
        sessions = [session]
    else:
        query = """
        query ListChatSessionByProcedureId($procedureId: String!, $limit: Int!) {
            listChatSessionByProcedureIdAndCreatedAt(
                procedureId: $procedureId sortDirection: DESC limit: $limit
            ) {
                items {
                    id status procedureId createdAt
                    messages { items { id role messageType toolName content
                        toolResponse sequenceNumber parentMessageId createdAt } }
                }
            }
        }
        """
        result = client.execute(
            query, {"procedureId": str(procedure_id), "limit": limit}
        )
        if "errors" in result:
            raise RuntimeError(
                f"plexus.procedure.chat_messages GraphQL errors: {result['errors']}"
            )
        sessions = []
        if "data" in result:
            sessions = (
                result["data"]
                .get("listChatSessionByProcedureIdAndCreatedAt", {})
                .get("items", [])
            )
        elif "listChatSessionByProcedureIdAndCreatedAt" in result:
            sessions = result["listChatSessionByProcedureIdAndCreatedAt"].get(
                "items", []
            )

    processed_sessions: list[dict[str, Any]] = []
    total_messages = 0
    tool_calls = 0
    tool_responses = 0
    missing_responses = 0

    def _sequence_key(message: dict[str, Any]) -> int:
        # GraphQL ChatMessage.sequenceNumber may be null, so dict.get(..., 0)
        # is not enough; coerce explicitly to keep `sorted` total-orderable.
        seq = message.get("sequenceNumber")
        return seq if isinstance(seq, int) else 0

    for session in sessions:
        messages = session.get("messages", {}).get("items", []) or []
        messages.sort(key=_sequence_key)
        session_tool_calls: list[str] = []
        session_tool_responses: list[str] = []
        processed_messages: list[dict[str, Any]] = []

        for msg in messages[:limit]:
            msg_type = msg.get("messageType", "MESSAGE")
            role = msg.get("role", "")

            raw_content = msg.get("content", "") or ""
            parsed_content: Any = raw_content
            if isinstance(raw_content, str) and raw_content.startswith("{") and raw_content.endswith("}"):
                try:
                    parsed_content = _json.loads(raw_content)
                except (ValueError, TypeError):
                    parsed_content = raw_content

            processed_msg: dict[str, Any] = {
                "id": msg["id"],
                "sequence_number": _sequence_key(msg),
                "role": role,
                "message_type": msg_type,
                "content": parsed_content,
                "created_at": msg["createdAt"],
                "parent_message_id": msg.get("parentMessageId"),
            }
            is_tool_response = role == "SYSTEM" and msg.get("parentMessageId")

            if msg_type == "TOOL_CALL":
                processed_msg["tool_name"] = msg.get("toolName")
                session_tool_calls.append(msg["id"])
                tool_calls += 1
                tool_response_raw = msg.get("toolResponse") or ""
                if show_tool_responses and tool_response_raw:
                    tool_response_parsed: Any = tool_response_raw
                    if (
                        isinstance(tool_response_raw, str)
                        and tool_response_raw.startswith("{")
                        and tool_response_raw.endswith("}")
                    ):
                        try:
                            tool_response_parsed = _json.loads(tool_response_raw)
                        except (ValueError, TypeError):
                            tool_response_parsed = tool_response_raw
                    processed_msg["tool_response"] = tool_response_parsed
                    session_tool_responses.append(msg["id"])
                    tool_responses += 1
            elif (msg_type == "TOOL_RESPONSE" or is_tool_response) and show_tool_responses:
                processed_msg["tool_name"] = msg.get("toolName", "Unknown")
                session_tool_responses.append(msg["id"])
                tool_responses += 1

            if not show_tool_calls and msg_type == "TOOL_CALL":
                continue

            processed_messages.append(processed_msg)
            total_messages += 1

        session_missing = 0
        for call_id in session_tool_calls:
            call_msg = next((m for m in messages if m.get("id") == call_id), None)
            has_inline_response = bool(call_msg and (call_msg.get("toolResponse") or ""))
            has_child_response = any(
                resp_msg.get("parentMessageId") == call_id
                for resp_msg in messages
                if resp_msg.get("messageType") == "TOOL_RESPONSE"
                or (resp_msg.get("role") == "SYSTEM" and resp_msg.get("parentMessageId"))
            )
            if not (has_inline_response or has_child_response):
                session_missing += 1

        missing_responses += session_missing

        processed_sessions.append(
            {
                "session_id": session["id"],
                "status": session["status"],
                "created_at": session["createdAt"],
                "message_count": len(processed_messages),
                "tool_calls": len(session_tool_calls),
                "tool_responses": len(session_tool_responses),
                "missing_responses": session_missing,
                "messages": processed_messages,
            }
        )

    return {
        "success": True,
        "procedure_id": str(procedure_id),
        "session_count": len(processed_sessions),
        "total_messages": total_messages,
        "summary": {
            "tool_calls": tool_calls,
            "tool_responses": tool_responses,
            "missing_responses": missing_responses,
            "response_rate": (
                f"{((tool_responses / tool_calls) * 100):.1f}%"
                if tool_calls > 0
                else "N/A"
            ),
        },
        "sessions": processed_sessions,
    }


def _default_procedure_steering_messages(args: dict[str, Any]) -> dict[str, Any]:
    """Return flat procedure steering messages for runtime agent injection."""

    from plexus.cli.procedure.chat_recorder import ProcedureChatRecorder
    from plexus.dashboard.api.client import PlexusDashboardClient

    procedure_id = args.get("procedure_id") or args.get("id")
    if not procedure_id:
        raise ValueError("plexus.procedure.steering_messages requires id or procedure_id")

    recorder = ProcedureChatRecorder(PlexusDashboardClient(), str(procedure_id))
    result = recorder.get_steering_messages(
        after=args.get("after"),
        agent_name=args.get("agent_name"),
        limit=int(args.get("limit") or 50),
    )
    return {"success": True, "procedure_id": str(procedure_id), **result}


def _default_feedback_alignment(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.feedback.alignment directly via FeedbackService.

    Mirrors the legacy plexus_feedback_alignment MCP tool but native Python,
    using memoized resolvers for scorecard/score lookup.
    """

    from plexus.cli.feedback.feedback_service import FeedbackService
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.memoized_resolvers import (
        memoized_resolve_score_identifier,
        memoized_resolve_scorecard_identifier,
    )

    scorecard_name = args.get("scorecard_name") or args.get("scorecard")
    score_name = args.get("score_name") or args.get("score")
    if not scorecard_name or not score_name:
        raise ValueError(
            "plexus.feedback.alignment requires scorecard_name and score_name"
        )
    days = int(float(args.get("days", 7)))

    client = create_client()
    if not client:
        raise RuntimeError(
            "plexus.feedback.alignment: could not create dashboard client"
        )
    account_id = _resolve_runtime_account_id(
        client, args, "plexus.feedback.alignment"
    )
    scorecard_id = memoized_resolve_scorecard_identifier(client, str(scorecard_name))
    if not scorecard_id:
        raise ValueError(
            f"plexus.feedback.alignment: scorecard {scorecard_name!r} not found"
        )
    score_id = memoized_resolve_score_identifier(
        client, scorecard_id, str(score_name)
    )
    if not score_id:
        raise ValueError(
            f"plexus.feedback.alignment: score {score_name!r} not found in "
            f"scorecard {scorecard_name!r}"
        )

    summary = _run_async_from_sync(
        FeedbackService.summarize_feedback(
            client=client,
            scorecard_name=str(scorecard_name),
            score_name=str(score_name),
            scorecard_id=scorecard_id,
            score_id=score_id,
            account_id=account_id,
            days=days,
        )
    )
    return FeedbackService.format_summary_result_as_dict(summary)


def _load_feedback_alignment_window(
    client: Any,
    *,
    account_id: str,
    days: int,
    window_start: str | None = None,
    window_end: str | None = None,
) -> list[dict[str, Any]]:
    """Load one account-scoped feedback window for bounded portfolio triage."""
    from datetime import datetime, timedelta, timezone

    query = """
    query ListFeedbackItemsByEditedTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listFeedbackItemByAccountIdAndEditedAt(
            accountId: $accountId,
            editedAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                id
                scorecardId
                scoreId
                initialAnswerValue
                finalAnswerValue
                isInvalid
                editedAt
            }
            nextToken
        }
    }
    """
    def _parse_window_time(value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

    end_time = _parse_window_time(window_end)
    start_time = _parse_window_time(window_start)
    if end_time is None or start_time is None:
        end_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        start_time = end_time - timedelta(days=days, minutes=5)
    variables = {
        "accountId": account_id,
        "startTime": start_time.isoformat().replace("+00:00", "Z"),
        "endTime": end_time.isoformat().replace("+00:00", "Z"),
        "nextToken": None,
    }
    items: list[dict[str, Any]] = []

    while True:
        response = client.execute(query, variables)
        if not isinstance(response, dict):
            raise TypeError(
                "plexus.feedback.alignment_batch received an invalid feedback-window response"
            )
        if response.get("errors"):
            raise RuntimeError(
                "plexus.feedback.alignment_batch feedback-window query failed: "
                + json.dumps(response["errors"])
            )
        page = response.get("listFeedbackItemByAccountIdAndEditedAt")
        if not isinstance(page, dict):
            data = response.get("data")
            page = (
                data.get("listFeedbackItemByAccountIdAndEditedAt")
                if isinstance(data, dict)
                else None
            )
        if not isinstance(page, dict):
            raise RuntimeError(
                "plexus.feedback.alignment_batch feedback-window data was missing"
            )
        page_items = page.get("items") or []
        if isinstance(page_items, list):
            items.extend(
                item
                for item in page_items
                if isinstance(item, dict) and not item.get("isInvalid")
            )
        next_token = page.get("nextToken")
        if not next_token:
            return items
        variables["nextToken"] = next_token


def _aggregate_feedback_alignment_window(
    client: Any,
    *,
    account_id: str,
    days: int,
    window_start: str | None = None,
    window_end: str | None = None,
) -> dict[tuple[str, str], dict[tuple[str, str], int]]:
    """Stream one complete feedback window into compact per-score pair counts.

    Portfolio analysis needs only final/predicted label pairs.  Keeping raw
    feedback rows until every target has been analyzed makes large, complete
    account reads needlessly memory-bound.
    """
    from collections import Counter, defaultdict
    from datetime import datetime, timedelta, timezone

    query = """
    query ListFeedbackItemsByEditedTime(
        $accountId: String!,
        $startTime: String!,
        $endTime: String!,
        $nextToken: String
    ) {
        listFeedbackItemByAccountIdAndEditedAt(
            accountId: $accountId,
            editedAt: { between: [$startTime, $endTime] },
            limit: 1000,
            nextToken: $nextToken
        ) {
            items {
                scorecardId
                scoreId
                initialAnswerValue
                finalAnswerValue
                isInvalid
            }
            nextToken
        }
    }
    """
    if bool(window_start) != bool(window_end):
        raise ValueError(
            "plexus.feedback.alignment_batch requires both window_start and "
            "window_end when either is supplied"
        )
    if window_start and window_end:
        start_value = str(window_start)
        end_value = str(window_end)
    else:
        end_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        start_time = end_time - timedelta(days=days, minutes=5)
        start_value = start_time.isoformat().replace("+00:00", "Z")
        end_value = end_time.isoformat().replace("+00:00", "Z")
    variables = {
        "accountId": account_id,
        "startTime": start_value,
        "endTime": end_value,
        "nextToken": None,
    }
    aggregates: dict[tuple[str, str], Counter[tuple[str, str]]] = defaultdict(Counter)

    while True:
        response = client.execute(query, variables)
        if not isinstance(response, dict):
            raise TypeError(
                "plexus.feedback.alignment_batch received an invalid feedback-window response"
            )
        if response.get("errors"):
            raise RuntimeError(
                "plexus.feedback.alignment_batch feedback-window query failed: "
                + json.dumps(response["errors"])
            )
        page = response.get("listFeedbackItemByAccountIdAndEditedAt")
        if not isinstance(page, dict):
            data = response.get("data")
            page = (
                data.get("listFeedbackItemByAccountIdAndEditedAt")
                if isinstance(data, dict)
                else None
            )
        if not isinstance(page, dict):
            raise RuntimeError(
                "plexus.feedback.alignment_batch feedback-window data was missing"
            )
        for item in page.get("items") or []:
            if not isinstance(item, dict) or item.get("isInvalid"):
                continue
            scorecard_id = str(item.get("scorecardId") or "").strip()
            score_id = str(item.get("scoreId") or "").strip()
            initial = item.get("initialAnswerValue")
            final = item.get("finalAnswerValue")
            if scorecard_id and score_id and initial is not None and final is not None:
                aggregates[(scorecard_id, score_id)][(final, initial)] += 1
        next_token = page.get("nextToken")
        if not next_token:
            return {key: dict(counts) for key, counts in aggregates.items()}
        variables["nextToken"] = next_token


def _default_feedback_alignment_batch(
    args: dict[str, Any],
    *,
    _prefetched_feedback_items: list[dict[str, Any]] | None = None,
    _prefetched_feedback_pair_counts: dict[
        tuple[str, str], dict[tuple[str, str], int]
    ] | None = None,
    _prefetched_account_id: str | None = None,
    _prefetched_scorecard_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run plexus.feedback.alignment for all scores in one or more scorecards.

    Returns alignment metrics for each score in a single call, avoiding
    N separate API calls when analyzing scorecard-wide performance. An explicit
    ``scorecards`` list may contain the complete discovered target set; it is
    evaluated with bounded concurrency and one shared feedback-window read.

    Target args (one of):
        scorecard (str): Scorecard name, key, or ID.
        scorecard_name (str): Scorecard name.
        scorecard_id (str): Scorecard ID.
        scorecards (list[str]): Scorecard names, keys, or IDs. Complete account
            coverage should be discovered with paginated scorecards.list calls
            and passed here as one explicit list.
        scorecard_limit (int): Select the first 1-5 account scorecards for a
            bounded portfolio sample without a separate inventory tool call.

    Optional args:
        days (int): Feedback lookback window in days. Default 7.
        accuracy_threshold (float): If provided, only return scores below this accuracy %.
        include_scores (list[str]): If provided, only return metrics for these score names.
        exclude_scores (list[str]): If provided, exclude these score names from results.

    Returns dict with:
        {
            "scorecard_id": str,
            "scorecard_name": str,
            "days": int,
            "total_scores": int,
            "scores_analyzed": int,
            "scores": [
                {
                    "score_id": str,
                    "score_name": str,
                    "accuracy": float (0-100),
                    "ac1": float (0-1),
                    "total_items": int,
                    "disagreements": int,
                    "disagreement_rate": float (0-1) | None,
                    "reviewed_error_opportunity": float,
                    "confusion_matrix": dict,
                    "precision": float,
                    "recall": float,
                    "warning": str | None,
                },
                ...
            ]
        }
    """
    raw_scorecards = args.get("scorecards")
    prefetched_scorecards_by_id: dict[str, dict[str, Any]] = {}
    portfolio_selection_rule: str | None = None
    has_explicit_scorecard = any(
        args.get(key) for key in ("scorecard", "scorecard_name", "scorecard_id")
    )
    raw_scorecard_limit = args.get("scorecard_limit")
    if (
        raw_scorecards is None
        and raw_scorecard_limit is not None
        and not has_explicit_scorecard
    ):
        try:
            scorecard_limit = int(raw_scorecard_limit)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "plexus.feedback.alignment_batch scorecard_limit must be an integer"
            ) from exc
        if not 1 <= scorecard_limit <= 5:
            raise ValueError(
                "plexus.feedback.alignment_batch scorecard_limit must be between 1 and 5"
            )
        inventory = _default_scorecards_list(
            {"limit": scorecard_limit, "_include_scores": True}
        )
        prefetched_scorecards_by_id = {
            str(card.get("id")): card
            for card in inventory
            if isinstance(card, dict) and card.get("id")
        }
        raw_scorecards = [
            card.get("id") or card.get("name")
            for card in inventory
            if isinstance(card, dict) and (card.get("name") or card.get("id"))
        ]
        portfolio_selection_rule = f"first {scorecard_limit} scorecards returned"

    if raw_scorecards is not None:
        from concurrent.futures import ThreadPoolExecutor
        from plexus.cli.shared.client_utils import create_client

        if not isinstance(raw_scorecards, (list, tuple)):
            raise ValueError(
                "plexus.feedback.alignment_batch scorecards must be a list"
            )
        scorecard_identifiers: list[str] = []
        for identifier in raw_scorecards:
            if not isinstance(identifier, str):
                raise ValueError(
                    "plexus.feedback.alignment_batch scorecards entries must be strings"
                )
            if not identifier.strip():
                raise ValueError(
                    "plexus.feedback.alignment_batch scorecards entries must not be blank"
                )
            scorecard_identifiers.append(identifier)
        if not scorecard_identifiers and portfolio_selection_rule is not None:
            return {
                "days": int(float(args.get("days", 7))),
                "selection_rule": portfolio_selection_rule,
                "scorecards_requested": 0,
                "scorecards_analyzed": 0,
                "scorecards": [],
                "coverage": {
                    "target_count": 0,
                    "completed_count": 0,
                    "failed_count": 0,
                    "complete": True,
                },
            }
        if not scorecard_identifiers:
            raise ValueError(
                "plexus.feedback.alignment_batch scorecards must not be empty"
            )
        single_args = dict(args)
        for key in (
            "scorecards",
            "scorecard",
            "scorecard_name",
            "scorecard_id",
            "scorecard_limit",
        ):
            single_args.pop(key, None)

        portfolio_client = create_client()
        if not portfolio_client:
            raise RuntimeError(
                "plexus.feedback.alignment_batch: could not create dashboard client"
            )
        portfolio_account_id = _resolve_runtime_account_id(
            portfolio_client,
            args,
            "plexus.feedback.alignment_batch",
        )
        portfolio_feedback_pair_counts = _aggregate_feedback_alignment_window(
            portfolio_client,
            account_id=portfolio_account_id,
            days=int(float(args.get("days", 7))),
            window_start=args.get("window_start"),
            window_end=args.get("window_end"),
        )

        def analyze_scorecard(identifier: str) -> dict[str, Any]:
            try:
                return _default_feedback_alignment_batch(
                    {**single_args, "scorecard": identifier},
                    _prefetched_feedback_pair_counts=portfolio_feedback_pair_counts,
                    _prefetched_account_id=portfolio_account_id,
                    _prefetched_scorecard_data=prefetched_scorecards_by_id.get(identifier),
                )
            except Exception as exc:
                return {
                    "scorecard_name": identifier,
                    "error": str(exc),
                }

        # scorecard_limit carries the selected scorecards (including their
        # score lists) into this branch, so its per-scorecard work is entirely
        # local after the single feedback-window read.  Avoid thread startup
        # and scheduling overhead on that latency-critical path.  Explicit
        # named scorecard lists still use bounded parallel reads below.
        if portfolio_selection_rule is not None:
            scorecard_results = [
                analyze_scorecard(identifier) for identifier in scorecard_identifiers
            ]
        else:
            with ThreadPoolExecutor(
                max_workers=min(
                    FEEDBACK_ALIGNMENT_SCORECARD_CONCURRENCY,
                    len(scorecard_identifiers),
                )
            ) as executor:
                scorecard_results = list(
                    executor.map(analyze_scorecard, scorecard_identifiers)
                )
        failed_count = sum(
            1 for scorecard_result in scorecard_results
            if scorecard_result.get("error")
        )
        completed_count = len(scorecard_results) - failed_count
        result = {
            "days": int(float(args.get("days", 7))),
            "scorecards_requested": len(scorecard_identifiers),
            "scorecards_analyzed": len(scorecard_results),
            "scorecards": scorecard_results,
            "coverage": {
                "target_count": len(scorecard_identifiers),
                "completed_count": completed_count,
                "failed_count": failed_count,
                "complete": completed_count == len(scorecard_identifiers),
            },
        }
        if portfolio_selection_rule is not None:
            result["selection_rule"] = portfolio_selection_rule
        return result

    from plexus.cli.feedback.feedback_service import FeedbackService
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.memoized_resolvers import (
        memoized_resolve_scorecard_identifier,
    )

    scorecard_name = (
        args.get("scorecard_name")
        or args.get("scorecard")
        or args.get("scorecard_id")
    )
    if not scorecard_name:
        raise ValueError("plexus.feedback.alignment_batch requires scorecard")

    days = int(float(args.get("days", 7)))
    accuracy_threshold = args.get("accuracy_threshold")
    include_scores = args.get("include_scores")
    exclude_scores = args.get("exclude_scores", [])

    client = None
    if _prefetched_scorecard_data is not None:
        data = _prefetched_scorecard_data
        scorecard_id = str(data.get("id") or "").strip()
        if not scorecard_id:
            raise ValueError(
                "plexus.feedback.alignment_batch prefetched scorecard data has no id"
            )
        account_id = _prefetched_account_id
        if not account_id:
            raise ValueError(
                "plexus.feedback.alignment_batch prefetched scorecard data has no account"
            )
        scorecard_name = data.get("name") or scorecard_name
    else:
        client = create_client()
        if not client:
            raise RuntimeError("plexus.feedback.alignment_batch: could not create dashboard client")

        account_id = _prefetched_account_id or _resolve_runtime_account_id(
            client,
            args,
            "plexus.feedback.alignment_batch",
        )
        scorecard_id = memoized_resolve_scorecard_identifier(client, str(scorecard_name))
        if not scorecard_id:
            raise ValueError(f"plexus.feedback.alignment_batch: scorecard {scorecard_name!r} not found")

        # Get all scores via the same GraphQL query pattern used by scorecards.info
        import json as _json
        query = (
            "query GetScorecard { "
            f'getScorecard(id: "{scorecard_id}") {{ '
            "id name sections { items { scores { items { id name } } } } "
            "} }"
        )
        response = client.execute(query)
        if "errors" in response:
            raise RuntimeError(
                "plexus.feedback.alignment_batch dashboard error: "
                + _json.dumps(response["errors"])
            )
        data = response.get("getScorecard")
        if not data:
            raise ValueError(f"plexus.feedback.alignment_batch: scorecard {scorecard_name!r} not found after query")
        scorecard_name = data.get("name") or scorecard_name

    # Flatten scores from all sections
    all_scores = []
    for section in (data.get("sections") or {}).get("items") or []:
        for score in (section.get("scores") or {}).get("items") or []:
            if score.get("id") and score.get("name"):
                all_scores.append({"id": score["id"], "name": score["name"]})

    if not all_scores:
        return {
            "scorecard_id": scorecard_id,
            "scorecard_name": scorecard_name,
            "days": days,
            "total_scores": 0,
            "scores_analyzed": 0,
            "scores": [],
        }

    # Filter scores based on include/exclude lists
    if include_scores:
        all_scores = [s for s in all_scores if s["name"] in include_scores]
    if exclude_scores:
        all_scores = [s for s in all_scores if s["name"] not in exclude_scores]

    prefetched_by_score: dict[str, list[Any]] | None = None
    prefetched_timestamps_by_score: dict[str, list[str]] = {}
    if _prefetched_feedback_items is not None:
        from types import SimpleNamespace

        prefetched_by_score = {}
        for item in _prefetched_feedback_items:
            if item.get("scorecardId") != scorecard_id:
                continue
            # The shared window loader already enforces this; keep the same
            # contract for injected/prefetched evidence used by portfolio and
            # runtime tests.
            if (
                item.get("isInvalid")
                or item.get("initialAnswerValue") is None
                or item.get("finalAnswerValue") is None
            ):
                continue
            item_score_id = str(item.get("scoreId") or "").strip()
            if not item_score_id:
                continue
            prefetched_by_score.setdefault(item_score_id, []).append(
                SimpleNamespace(
                    initialAnswerValue=item.get("initialAnswerValue"),
                    finalAnswerValue=item.get("finalAnswerValue"),
                    editedAt=item.get("editedAt"),
                )
            )
            if item.get("editedAt"):
                prefetched_timestamps_by_score.setdefault(item_score_id, []).append(
                    str(item["editedAt"])
                )

    prefetched_pair_counts_by_score: dict[str, dict[tuple[str, str], int]] | None = None
    if _prefetched_feedback_pair_counts is not None:
        prefetched_pair_counts_by_score = {
            score_id: counts
            for (item_scorecard_id, score_id), counts in _prefetched_feedback_pair_counts.items()
            if item_scorecard_id == scorecard_id
        }

    async def analyze_scores() -> list[dict[str, Any] | None]:
        semaphore = asyncio.Semaphore(FEEDBACK_ALIGNMENT_SCORE_CONCURRENCY)

        async def analyze_score(score: dict[str, str]) -> dict[str, Any] | None:
            score_name = score["name"]
            score_id = score["id"]

            try:
                if prefetched_pair_counts_by_score is not None:
                    from plexus.analysis.feedback_analyzer import analyze_feedback_pair_counts

                    analysis = analyze_feedback_pair_counts(
                        prefetched_pair_counts_by_score.get(score_id, {})
                    )
                elif prefetched_by_score is not None:
                    analysis = FeedbackService._analyze_feedback_items(
                        prefetched_by_score.get(score_id, [])
                    )
                else:
                    async with semaphore:
                        summary = await FeedbackService.summarize_feedback(
                            client=client,
                            scorecard_name=str(scorecard_name),
                            score_name=score_name,
                            scorecard_id=scorecard_id,
                            score_id=score_id,
                            account_id=account_id,
                            days=days,
                        )
                    summary_dict = FeedbackService.format_summary_result_as_dict(summary)
                    analysis = summary_dict.get("analysis", {})
                total_items = int(analysis.get("total_items") or 0)
                disagreements = int(analysis.get("disagreements") or 0)
                # The per-score analysis has historically exposed accuracy in
                # both ratio and percent forms.  Portfolio callers need one
                # stable, documented unit, so derive it from the reviewed
                # counts returned alongside every batch row.
                accuracy = (
                    100.0 * (total_items - disagreements) / total_items
                    if total_items > 0
                    else None
                )
                disagreement_rate = (
                    disagreements / total_items if total_items > 0 else None
                )
                reviewed_error_opportunity = (
                    total_items * disagreement_rate
                    if disagreement_rate is not None
                    else 0.0
                )
                weekly_disagreement_rates: list[float] = []
                weekly_ac1_values: list[float] = []
                weekly_bucket_counts: list[int] = []
                weekly_detail: list[dict[str, Any]] = []
                if prefetched_by_score is not None and args.get("window_end"):
                    from datetime import datetime, timezone
                    from plexus.optimization.decision import weekly_buckets

                    pairs = prefetched_by_score.get(score_id, [])
                    timestamps = [pair.editedAt for pair in pairs if getattr(pair, "editedAt", None)]
                    weekly_detail = weekly_buckets(timestamps, window_end=str(args["window_end"]), weeks=12)
                    for bucket in weekly_detail:
                        start = datetime.fromisoformat(bucket["start"].replace("Z", "+00:00")).astimezone(timezone.utc)
                        end = datetime.fromisoformat(bucket["end"].replace("Z", "+00:00")).astimezone(timezone.utc)
                        bucket_pairs = [
                            pair for pair in pairs
                            if getattr(pair, "editedAt", None)
                            and start <= datetime.fromisoformat(str(pair.editedAt).replace("Z", "+00:00")).astimezone(timezone.utc) < end
                        ]
                        bucket_analysis = FeedbackService._analyze_feedback_items(bucket_pairs)
                        bucket["valid_feedback_count"] = int(bucket_analysis.get("total_items") or 0)
                        bucket["disagreement_rate"] = (
                            float(bucket_analysis["disagreements"]) / bucket["valid_feedback_count"]
                            if bucket["valid_feedback_count"] else None
                        )
                        bucket["ac1"] = bucket_analysis.get("ac1")
                        weekly_bucket_counts.append(bucket["valid_feedback_count"])
                        if bucket["valid_feedback_count"]:
                            weekly_disagreement_rates.append(float(bucket["disagreement_rate"] or 0))
                            if bucket["ac1"] is not None:
                                weekly_ac1_values.append(float(bucket["ac1"]))

                if (
                    accuracy_threshold is not None
                    and accuracy is not None
                    and accuracy >= accuracy_threshold
                ):
                    return None

                return {
                    "score_id": score_id,
                    "score_name": score_name,
                    "accuracy": accuracy,
                    "ac1": analysis.get("ac1"),
                    "total_items": total_items,
                    "disagreements": disagreements,
                    "disagreement_rate": disagreement_rate,
                    "reviewed_error_opportunity": reviewed_error_opportunity,
                    # These distributions are computed after invalid rows and
                    # incomplete initial/final label pairs are excluded by the
                    # shared analyzer.  Preserve them for investment policy.
                    "class_distribution": analysis.get("class_distribution") or [],
                    "predicted_class_distribution": analysis.get("predicted_class_distribution") or [],
                    "feedback_timestamps": prefetched_timestamps_by_score.get(score_id, []),
                    "weekly_buckets": weekly_detail,
                    "weekly_bucket_counts": weekly_bucket_counts,
                    "weekly_disagreement_rates": weekly_disagreement_rates,
                    "weekly_ac1_values": weekly_ac1_values,
                    "confusion_matrix": analysis.get("confusion_matrix"),
                    "precision": analysis.get("precision"),
                    "recall": analysis.get("recall"),
                    "warning": analysis.get("warning"),
                }
            except Exception as exc:
                # Include errors in results so callers can distinguish a
                # failed read from a score with no feedback.
                return {
                    "score_id": score_id,
                    "score_name": score_name,
                    "error": str(exc),
                }

        return await asyncio.gather(*(analyze_score(score) for score in all_scores))

    results = [
        result
        for result in _run_async_from_sync(analyze_scores())
        if result is not None
    ]

    return {
        "scorecard_id": scorecard_id,
        "scorecard_name": scorecard_name,
        "days": days,
        "total_scores": len(all_scores),
        "scores_analyzed": len(results),
        "scores": results,
    }


def _default_feedback_finder(args: dict[str, Any]) -> dict[str, Any]:
    """Run the production plexus.feedback.find chain.

    Lifted from MCP/tools/feedback/feedback.py so the Tactus host module no
    longer has to bounce back through FastMCP for this read-only call.
    """

    from plexus.cli.feedback.feedback_service import FeedbackService
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.memoized_resolvers import (
        memoized_resolve_score_identifier,
        memoized_resolve_scorecard_identifier,
    )

    scorecard_name = args.get("scorecard_name") or args.get("scorecard")
    score_name = args.get("score_name") or args.get("score")
    if not scorecard_name or not score_name:
        raise ValueError("plexus.feedback.find requires scorecard_name and score_name")

    # A feedback lookup without an explicit window is typically initiated by a
    # conversational request for recent disagreements.  Seven days silently
    # hides too much evidence for that workflow; callers can still request a
    # narrower window explicitly.
    days = int(args["days"]) if args.get("days") is not None else 30
    limit = int(args["limit"]) if args.get("limit") is not None else None
    offset = int(args["offset"]) if args.get("offset") is not None else None
    prioritize_edit_comments = bool(args.get("prioritize_edit_comments", True))

    client = create_client()
    account_id = _resolve_runtime_account_id(client, args, "plexus.feedback.find")
    scorecard_id = memoized_resolve_scorecard_identifier(client, scorecard_name)
    score_id = memoized_resolve_score_identifier(client, scorecard_id, score_name)

    result = _run_async_from_sync(
        FeedbackService.search_feedback(
            client=client,
            scorecard_name=scorecard_name,
            score_name=score_name,
            scorecard_id=scorecard_id,
            score_id=score_id,
            account_id=account_id,
            days=days,
            initial_value=args.get("initial_value"),
            final_value=args.get("final_value"),
            limit=limit,
            offset=offset,
            prioritize_edit_comments=prioritize_edit_comments,
        )
    )
    return FeedbackService.format_search_result_as_dict(result)


def _default_evaluation_info(args: dict[str, Any]) -> dict[str, Any]:
    """Run the production plexus.evaluation.info chain directly.

    Bypasses MCP loopback by calling Evaluation.get_evaluation_info or
    Evaluation.get_latest_evaluation in plexus/Evaluation.py. Returns a
    structured dict; callers that need a JSON string should serialize it.

    include_examples is intentionally not implemented in this slice; that
    GraphQL example-loop logic lives in MCP/tools/evaluation/evaluations.py
    and will be lifted in a follow-up so it remains unit-testable.
    """

    from plexus.Evaluation import Evaluation

    raw_id = args.get("evaluation_id")
    evaluation_id = raw_id.strip() if isinstance(raw_id, str) else raw_id
    use_latest = bool(args.get("use_latest", False))

    if bool(evaluation_id) == use_latest:
        raise ValueError(
            "plexus.evaluation.info requires exactly one of evaluation_id or use_latest"
        )

    if args.get("include_examples"):
        raise ValueError(
            "plexus.evaluation.info include_examples is not yet supported in the "
            "Tactus runtime; use plexus.evaluation.info without include_examples or "
            "the MCP plexus_evaluation_info tool until the example-fetching helper "
            "is lifted out of MCP/tools/evaluation/evaluations.py."
        )

    include_score_results = bool(args.get("include_score_results", False))

    if use_latest:
        account_key = args.get("account_key") or os.environ.get("PLEXUS_ACCOUNT_KEY")
        if not account_key:
            raise ValueError(
                "plexus.evaluation.info use_latest requires account_key or "
                "PLEXUS_ACCOUNT_KEY environment variable"
            )
        evaluation_type = args.get("evaluation_type")
        if isinstance(evaluation_type, str):
            evaluation_type = evaluation_type.strip() or None
        return Evaluation.get_latest_evaluation(account_key, evaluation_type)

    return Evaluation.get_evaluation_info(evaluation_id, include_score_results)


def _default_optimization_persist(packet: dict[str, Any]) -> Any:
    """Persist one exact decision packet through the canonical Report/S3 path."""
    from plexus.cli.shared.client_utils import create_client
    from plexus.optimization.persistence import persist_decision_packet

    client = create_client()
    if client is None:
        raise RuntimeError(
            "plexus.optimization persistence could not create a dashboard client"
        )
    return persist_decision_packet(packet, client=client, persist=True)


def _default_evaluation_archive(args: dict[str, Any]) -> dict[str, Any]:
    """Archive an evaluation by setting status=ARCHIVED and recording archive metadata."""

    from plexus.cli.shared.client_utils import create_client

    evaluation_id = args.get("evaluation_id") or args.get("id")
    if not evaluation_id:
        raise ValueError("plexus.evaluation.archive requires id or evaluation_id")

    reason = args.get("reason")
    archived_by = args.get("archived_by") or args.get("archivedBy")

    client = create_client()
    if not client:
        raise RuntimeError(
            "plexus.evaluation.archive: could not create dashboard client"
        )

    query = """
    query GetEvaluationForArchive($id: ID!) {
      getEvaluation(id: $id) {
        id
        status
        metadata
      }
    }
    """
    fetched = client.execute(query, {"id": str(evaluation_id)})
    evaluation = (fetched or {}).get("getEvaluation")
    if not evaluation:
        raise ValueError(f"Evaluation not found: {evaluation_id}")

    previous_status = evaluation.get("status")
    merged_metadata, archived_at = _build_archived_metadata(
        evaluation.get("metadata"),
        previous_status=previous_status,
        reason=str(reason) if reason is not None else None,
        archived_by=str(archived_by) if archived_by is not None else None,
    )

    mutation = """
    mutation UpdateEvaluationArchive($input: UpdateEvaluationInput!) {
      updateEvaluation(input: $input) {
        id
        status
        metadata
        updatedAt
      }
    }
    """
    result = client.execute(
        mutation,
        {
            "input": {
                "id": str(evaluation_id),
                "status": "ARCHIVED",
                "metadata": json.dumps(merged_metadata),
            }
        },
    )
    updated = (result or {}).get("updateEvaluation")
    if not updated:
        raise RuntimeError(
            f"Failed to archive evaluation {evaluation_id}: missing updateEvaluation payload"
        )

    return {
        "success": True,
        "evaluation_id": str(evaluation_id),
        "status": updated.get("status") or "ARCHIVED",
        "previous_status": previous_status,
        "archived_at": archived_at,
        "metadata": merged_metadata,
        "updated_at": updated.get("updatedAt"),
    }


def _default_score_info(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.score.info directly — mirrors plexus_score_info."""

    import os as _os

    from plexus.cli.report.utils import resolve_account_id_for_command
    from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
    from plexus.cli.shared.client_utils import create_client

    score_identifier = (
        args.get("score_identifier")
        or args.get("id")
        or args.get("score")
        or args.get("name")
        or args.get("key")
    )
    if not score_identifier:
        raise ValueError("plexus.score.info requires score_identifier (id/name/key)")

    scorecard_identifier = (
        args.get("scorecard_identifier")
        or args.get("scorecard")
        or args.get("scorecard_id")
    )
    version_id = (
        args.get("version_id")
        or args.get("version")
        or args.get("score_version_id")
        or args.get("scoreVersionId")
    )

    plexus_url_base = _os.environ.get("PLEXUS_APP_URL", "https://capacity-plexus.anth.us").rstrip("/")

    def _plexus_url(path: str) -> str:
        return f"{plexus_url_base}/{path.lstrip('/')}"

    client = create_client()
    if not client:
        raise RuntimeError("plexus.score.info: could not create dashboard client")

    found_scores: list[dict] = []

    if scorecard_identifier:
        scorecard_id = resolve_scorecard_identifier(client, str(scorecard_identifier))
        if not scorecard_id:
            raise ValueError(
                f"plexus.score.info: scorecard {scorecard_identifier!r} not found"
            )
        result = client.execute(
            f"""query GetScorecardWithScores {{
                getScorecard(id: "{scorecard_id}") {{
                    id name key
                    sections {{ items {{ id name scores {{ items {{
                        id name key externalId description type
                        championVersionId isDisabled updatedAt
                    }} }} }} }}
                }}
            }}"""
        )
        scorecard_data = result.get("getScorecard")
        if scorecard_data:
            for section in scorecard_data.get("sections", {}).get("items", []):
                for score in section.get("scores", {}).get("items", []):
                    sid = str(score_identifier).lower()
                    if (
                        score.get("id") == str(score_identifier)
                        or score.get("name", "").lower() == sid
                        or score.get("key") == str(score_identifier)
                        or score.get("externalId") == str(score_identifier)
                        or sid in score.get("name", "").lower()
                    ):
                        found_scores.append({"score": score, "section": section, "scorecard": scorecard_data})
    else:
        account_id = resolve_account_id_for_command(client, None)
        if not account_id:
            raise RuntimeError(
                "plexus.score.info: no default account — is PLEXUS_ACCOUNT_KEY set?"
            )
        result = client.execute(
            f"""query ListScorecardsForSearch {{
                listScorecards(filter: {{ accountId: {{ eq: "{account_id}" }} }}, limit: 100) {{
                    items {{
                        id name key
                        sections {{ items {{ id name scores {{ items {{
                            id name key externalId description type
                            championVersionId isDisabled updatedAt
                        }} }} }} }}
                    }}
                }}
            }}"""
        )
        for scorecard in result.get("listScorecards", {}).get("items", []):
            for section in scorecard.get("sections", {}).get("items", []):
                for score in section.get("scores", {}).get("items", []):
                    sid = str(score_identifier).lower()
                    if (
                        score.get("id") == str(score_identifier)
                        or score.get("name", "").lower() == sid
                        or score.get("key") == str(score_identifier)
                        or score.get("externalId") == str(score_identifier)
                        or sid in score.get("name", "").lower()
                    ):
                        found_scores.append({"score": score, "section": section, "scorecard": scorecard})

    if not found_scores:
        scope = f" within scorecard {scorecard_identifier!r}" if scorecard_identifier else ""
        raise ValueError(
            f"plexus.score.info: no scores found matching {score_identifier!r}{scope}"
        )

    if len(found_scores) > 1:
        return {
            "found": True,
            "multiple": True,
            "count": len(found_scores),
            "matches": [
                {
                    "scoreId": m["score"]["id"],
                    "scoreName": m["score"]["name"],
                    "scorecardName": m["scorecard"]["name"],
                    "sectionName": m["section"]["name"],
                    "isDisabled": m["score"].get("isDisabled", False),
                    "dashboardUrl": _plexus_url(
                        f"lab/scorecards/{m['scorecard']['id']}/scores/{m['score']['id']}"
                    ),
                }
                for m in found_scores
            ],
            "message": (
                f"Found {len(found_scores)} scores matching {score_identifier!r}. "
                "Use a more specific identifier."
            ),
        }

    m = found_scores[0]
    score = m["score"]
    section = m["section"]
    scorecard = m["scorecard"]
    score_id = score["id"]
    scorecard_id = scorecard["id"]

    response: dict[str, Any] = {
        "found": True,
        "scoreId": score_id,
        "scoreName": score["name"],
        "scoreKey": score.get("key"),
        "externalId": score.get("externalId"),
        "type": score.get("type"),
        "championVersionId": score.get("championVersionId"),
        "updatedAt": score.get("updatedAt"),
        "isDisabled": score.get("isDisabled", False),
        "location": {
            "scorecardId": scorecard_id,
            "scorecardName": scorecard["name"],
            "sectionId": section["id"],
            "sectionName": section["name"],
        },
        "dashboardUrl": _plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score_id}"),
    }

    versions_result = client.execute(
        f"""query GetScoreVersions {{
            getScore(id: "{score_id}") {{
                id name key externalId championVersionId
                versions(sortDirection: DESC, limit: 20) {{
                    items {{ id createdAt isFeatured parentVersionId note metadata }}
                }}
            }}
        }}"""
    )
    if "errors" in versions_result:
        response["versions"] = []
        response["versionsError"] = str(versions_result["errors"])
    else:
        score_data = versions_result.get("getScore") or {}
        all_versions = score_data.get("versions", {}).get("items", []) or []
        response["versions"] = [
            {
                "id": v.get("id"),
                "createdAt": v.get("createdAt"),
                "note": v.get("note"),
                "isFeatured": v.get("isFeatured"),
                "parentVersionId": v.get("parentVersionId"),
                "isChampion": v.get("id") == score.get("championVersionId"),
                "metadata": v.get("metadata"),
            }
            for v in all_versions
        ]

    target_version_id = version_id or score.get("championVersionId")
    if target_version_id:
        ver_result = client.execute(
            f"""query GetScoreVersionForInfo {{
                getScoreVersion(id: "{target_version_id}") {{
                    id configuration guidelines createdAt updatedAt
                    note isFeatured parentVersionId metadata
                }}
            }}"""
        )
        version_data = ver_result.get("getScoreVersion") if "errors" not in ver_result else None
        if version_data:
            response["code"] = version_data.get("configuration")
            response["guidelines"] = version_data.get("guidelines")
            response["description"] = score.get("description")
            response["targetVersionId"] = target_version_id
            response["isChampionVersion"] = target_version_id == score.get("championVersionId")
            response["versionDetails"] = {
                "id": target_version_id,
                "createdAt": version_data.get("createdAt"),
                "updatedAt": version_data.get("updatedAt"),
                "note": version_data.get("note"),
                "isFeatured": version_data.get("isFeatured"),
                "parentVersionId": version_data.get("parentVersionId"),
                "metadata": version_data.get("metadata"),
                "isChampion": target_version_id == score.get("championVersionId"),
            }
            parent_version_id = str(version_data.get("parentVersionId") or "").strip()
            if parent_version_id:
                response["previousVersionId"] = parent_version_id
                response["previousVersionSource"] = "parent"
            else:
                version_ids = [str(version.get("id") or "").strip() for version in all_versions]
                try:
                    version_index = version_ids.index(target_version_id)
                except ValueError:
                    version_index = -1
                chronological_predecessor = (
                    version_ids[version_index + 1]
                    if version_index >= 0 and version_index + 1 < len(version_ids)
                    else ""
                )
                response["previousVersionId"] = chronological_predecessor or None
                response["previousVersionSource"] = (
                    "chronological" if chronological_predecessor else None
                )
            response["isSpecificVersion"] = bool(
                version_id and version_id != score.get("championVersionId")
            )
        else:
            response.update({"description": score.get("description"), "code": None,
                             "guidelines": None, "targetVersionId": None,
                             "isChampionVersion": False, "versionDetails": None})
    else:
        response.update({"description": score.get("description"), "code": None,
                         "guidelines": None, "targetVersionId": None,
                         "isChampionVersion": False, "versionDetails": None})

    return response


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def _default_score_evaluations(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.score.evaluations directly via OptimizerResultsService.

    Accepts either:
      - { id = "<score-uuid>" }  — direct score ID, no scorecard lookup needed
      - { scorecard = "...", score = "..." }  — resolved via memoized resolvers
    """
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.optimizer_results import OptimizerResultsService

    version_id = args.get("version_id")
    sort_by = str(args.get("sort_by") or "updated")
    limit = int(args.get("limit") or 25)

    client = create_client()
    if not client:
        raise RuntimeError(
            "plexus.score.evaluations: could not create dashboard client"
        )

    # Fast path: direct UUID provided — no resolution needed.
    direct_id = args.get("id")
    if direct_id and _UUID_RE.match(str(direct_id)):
        score_id = str(direct_id)
    else:
        from plexus.cli.shared.memoized_resolvers import (
            memoized_resolve_score_identifier,
            memoized_resolve_scorecard_identifier,
        )

        scorecard_identifier = args.get("scorecard_identifier") or args.get("scorecard")
        score_identifier = (
            args.get("score_identifier") or args.get("score") or direct_id
        )
        if not scorecard_identifier or not score_identifier:
            raise ValueError(
                "plexus.score.evaluations requires either { id = '<score-uuid>' } "
                "or { scorecard = '...', score = '...' }"
            )

        scorecard_id = memoized_resolve_scorecard_identifier(client, str(scorecard_identifier))
        if not scorecard_id:
            raise ValueError(
                f"plexus.score.evaluations: scorecard {scorecard_identifier!r} not found"
            )
        score_id = memoized_resolve_score_identifier(client, scorecard_id, str(score_identifier))
        if not score_id:
            raise ValueError(
                f"plexus.score.evaluations: score {score_identifier!r} not found"
            )

    service = OptimizerResultsService(client)
    evaluations = service.list_score_evaluations(
        score_id, version_id=version_id, sort_by=sort_by, limit=limit
    )
    return {"success": True, "score_id": score_id, "evaluations": evaluations}


def _default_score_predict(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.score.predict directly — mirrors plexus_predict."""

    import asyncio
    import json as _json
    import traceback as _traceback
    from decimal import Decimal

    from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
    from plexus.cli.shared.client_utils import create_client
    from plexus.dashboard.api.models.item import Item as PlexusItem
    from plexus.scores.Score import Score

    def _sanitize_dec(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, dict):
            return {k: _sanitize_dec(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_sanitize_dec(v) for v in obj]
        return obj

    scorecard_identifier = args.get("scorecard_identifier")
    score_identifier = args.get("score_identifier")
    if not scorecard_identifier or not score_identifier:
        raise ValueError(
            "plexus.score.predict requires scorecard_identifier and score_identifier"
        )

    item_id = args.get("item_id") or args.get("id") or args.get("item")
    item_ids_raw = args.get("item_ids")
    include_input = bool(args.get("include_input", False))
    include_trace = bool(args.get("include_trace", False))
    yaml_mode = bool(args.get("yaml", False))
    version = args.get("version") or args.get("version_id")
    latest = bool(args.get("latest", False))
    yaml_path = args.get("yaml_path")

    if not item_id and not item_ids_raw:
        raise ValueError("plexus.score.predict requires item_id or item_ids")
    if item_id and item_ids_raw:
        raise ValueError("plexus.score.predict: specify item_id or item_ids, not both")

    client = create_client()
    if not client:
        raise RuntimeError("plexus.score.predict: could not create dashboard client")
    account_id = None if yaml_mode else _resolve_runtime_account_id(
        client, args, "plexus.score.predict"
    )

    if yaml_mode:
        scorecard_id = "yaml-mode-scorecard"
        resolved_score: dict[str, Any] = {"id": "yaml-mode-score", "name": str(score_identifier),
                                           "key": str(score_identifier).lower().replace(" ", "-"),
                                           "championVersionId": "yaml-mode-version"}
    else:
        scorecard_id_resolved = resolve_scorecard_identifier(
            client, str(scorecard_identifier)
        )
        if not scorecard_id_resolved:
            raise ValueError(
                f"plexus.score.predict: scorecard {scorecard_identifier!r} not found"
            )
        scorecard_id = scorecard_id_resolved
        sc_result = client.execute(
            f"""query GetScorecardForPrediction {{
                getScorecard(id: "{scorecard_id}") {{
                    id name
                    sections {{ items {{ id scores {{ items {{
                        id name key externalId championVersionId isDisabled
                    }} }} }} }}
                }}
            }}"""
        )
        scorecard_data = sc_result.get("getScorecard")
        if not scorecard_data:
            raise ValueError(
                f"plexus.score.predict: could not load scorecard {scorecard_identifier!r}"
            )

        try:
            from plexus.cli.shared.identifier_resolution import (
                resolve_score_identifier as _rsi,
            )
            resolved_score_id = _rsi(client, scorecard_id, str(score_identifier))
        except Exception:
            resolved_score_id = None

        resolved_score = None
        for section in scorecard_data.get("sections", {}).get("items", []):
            for sc in section.get("scores", {}).get("items", []):
                if (
                    (resolved_score_id and sc.get("id") == resolved_score_id)
                    or sc.get("id") == str(score_identifier)
                    or sc.get("externalId") == str(score_identifier)
                    or sc.get("key") == str(score_identifier)
                    or sc.get("name") == str(score_identifier)
                ):
                    resolved_score = sc
                    break
            if resolved_score:
                break
        if not resolved_score:
            raise ValueError(
                f"plexus.score.predict: score {score_identifier!r} not found in "
                f"scorecard {scorecard_identifier!r}"
            )

    resolved_version = version if not latest else None
    if latest and not yaml_mode:
        try:
            from plexus.cli.evaluation.evaluations import get_latest_score_version
            v = get_latest_score_version(client, resolved_score["id"])
            if v:
                resolved_version = v
        except Exception:
            pass

    if item_id:
        target_item_ids: list[str] = [str(item_id)]
    else:
        target_item_ids = [x.strip() for x in str(item_ids_raw).split(",")]

    if not yaml_mode:
        try:
            from plexus.cli.shared.identifier_resolution import (
                resolve_item_identifier as _rii,
            )
            resolved_ids = []
            for raw_id in target_item_ids:
                try:
                    r = _rii(client, raw_id, account_id)
                except Exception:
                    r = None
                resolved_ids.append(r or raw_id)
            target_item_ids = resolved_ids
        except Exception:
            pass

    if yaml_mode and yaml_path:
        import yaml as _yaml
        from plexus.scores.Scorecard import Scorecard
        with open(yaml_path, "r") as f:
            sc_cfg = _yaml.safe_load(f.read())
        scorecard_instance = Scorecard({"name": scorecard_identifier, "sections": [{"name": "Custom", "scores": [sc_cfg]}]})
        scorecard_instance.yaml_only = True
    elif yaml_mode:
        from plexus.cli.evaluation.evaluations import load_scorecard_from_yaml_files
        scorecard_instance = load_scorecard_from_yaml_files(
            str(scorecard_identifier), score_names=[str(score_identifier)]
        )
        scorecard_instance.yaml_only = True
    else:
        from plexus.cli.evaluation.evaluations import load_scorecard_from_api
        scorecard_instance = load_scorecard_from_api(
            str(scorecard_identifier), score_names=[str(score_identifier)],
            use_cache=False, specific_version=resolved_version
        )

    resolved_score_name = str(score_identifier)
    if hasattr(scorecard_instance, "scores") and isinstance(scorecard_instance.scores, list):
        for s in scorecard_instance.scores:
            sn = s.get("name")
            if sn and (
                sn == str(score_identifier) or str(s.get("id", "")) == str(score_identifier)
                or str(s.get("key", "")) == str(score_identifier)
                or str(s.get("externalId", "")) == str(score_identifier)
            ):
                resolved_score_name = sn
                break

    try:
        _, name_to_id = scorecard_instance.build_dependency_graph([resolved_score_name])
    except Exception:
        name_to_id = {}

    item_query_fields = """id text description metadata attachedFiles externalId createdAt updatedAt"""

    async def _predict_one(target_id: str) -> dict:
        try:
            item_result = client.execute(
                f'query GetItem {{ getItem(id: "{target_id}") {{ {item_query_fields} }} }}'
            )
            item_data = item_result.get("getItem")
            if not item_data:
                return {"item_id": target_id, "error": f"Item {target_id!r} not found"}

            item_text = item_data.get("text", "") or item_data.get("description", "")
            if not item_text:
                return {"item_id": target_id, "error": "No text content found in item"}

            meta_raw = item_data.get("metadata", {})
            item_metadata: dict = {}
            if isinstance(meta_raw, dict):
                item_metadata = meta_raw
            else:
                try:
                    item_metadata = _json.loads(meta_raw)
                except Exception:
                    pass

            try:
                item_obj = PlexusItem.from_dict(item_data, client)
            except Exception:
                item_obj = None

            try:
                results = await scorecard_instance.score_entire_text(
                    text=item_text, metadata=item_metadata, modality=None,
                    subset_of_score_names=[resolved_score_name], item=item_obj
                )
                target_result_id = name_to_id.get(resolved_score_name)
                score_result_obj = None
                if results:
                    if target_result_id and target_result_id in results:
                        score_result_obj = results[target_result_id]
                    elif resolved_score_name in results:
                        score_result_obj = results[resolved_score_name]

                if score_result_obj is None:
                    if results and any(isinstance(v, Score.Result) and v.value == "SKIPPED" for v in results.values()):
                        return {"item_id": target_id, "scores": [{"name": score_identifier, "value": None,
                                "explanation": "Not applicable — unmet dependency conditions", "cost": {}}]}
                    return {"item_id": target_id, "error": f"No result for score {resolved_score_name!r}"}

                explanation = (
                    getattr(score_result_obj, "explanation", None)
                    or (score_result_obj.metadata.get("explanation", "") if hasattr(score_result_obj, "metadata") and score_result_obj.metadata else "")
                )
                costs = {}
                if hasattr(score_result_obj, "cost"):
                    costs = score_result_obj.cost
                elif hasattr(score_result_obj, "metadata") and score_result_obj.metadata:
                    costs = score_result_obj.metadata.get("cost", {})

                prediction_result: dict = {"item_id": target_id, "scores": [{
                    "name": score_identifier, "value": score_result_obj.value,
                    "explanation": explanation, "cost": costs
                }]}
                if include_trace:
                    trace = getattr(score_result_obj, "trace", None) or (
                        score_result_obj.metadata.get("trace") if hasattr(score_result_obj, "metadata") and score_result_obj.metadata else None
                    )
                    prediction_result["scores"][0]["trace"] = trace
            except Exception as exc:
                prediction_result = {"item_id": target_id, "scores": [{
                    "name": score_identifier, "value": "ERROR",
                    "explanation": f"Prediction failed: {exc}",
                    "error_details": {"error_message": str(exc), "error_type": type(exc).__name__,
                                      "traceback": _traceback.format_exc()},
                    "cost": {}
                }]}

            if include_input:
                prediction_result["input"] = {"description": item_data.get("description"),
                                               "metadata": item_data.get("metadata"),
                                               "attachedFiles": item_data.get("attachedFiles"),
                                               "externalId": item_data.get("externalId")}
            return prediction_result
        except Exception as e:
            return {"item_id": target_id, "error": str(e)}

    async def _gather_all() -> list:
        return list(await asyncio.gather(*[_predict_one(tid) for tid in target_item_ids]))

    prediction_results_list = _run_async_from_sync(_gather_all())
    return _sanitize_dec({
        "success": True,
        "scorecard_identifier": scorecard_identifier,
        "score_identifier": score_identifier,
        "scorecard_id": scorecard_id,
        "score_id": resolved_score["id"],
        "item_count": len(target_item_ids),
        "predictions": prediction_results_list,
    })


def _default_score_set_champion(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.score.set_champion directly — mirrors plexus_score_set_champion."""

    import uuid as _uuid
    from datetime import datetime, timezone

    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.optimizer_shadow_invalidation import (
        extract_shadow_invalid_feedback_item_ids_from_yaml_text,
    )

    score_id = args.get("score_id") or args.get("id")
    version_id = args.get("version_id") or args.get("version")
    if not score_id or not version_id:
        raise ValueError(
            "plexus.score.set_champion requires score_id and version_id"
        )

    client = create_client()
    if not client:
        raise RuntimeError(
            "plexus.score.set_champion: could not create dashboard client"
        )

    check_result = client.execute(
        """
        query GetScoreVersionForChampionGuard($scoreId: ID!, $versionId: ID!) {
            getScore(id: $scoreId) { id championVersionId }
            getScoreVersion(id: $versionId) { id scoreId configuration metadata createdAt }
        }
        """,
        {"scoreId": str(score_id), "versionId": str(version_id)},
    )
    score_data = check_result.get("getScore") or {}
    version_data = check_result.get("getScoreVersion") or {}

    shadow_ids = extract_shadow_invalid_feedback_item_ids_from_yaml_text(
        version_data.get("configuration") or ""
    )
    if shadow_ids:
        return {
            "success": False,
            "error": "SHADOW_INVALIDATION_PRESENT",
            "message": (
                "Cannot promote: version still contains "
                "optimizer_shadow_invalid_feedback_item_ids. "
                "Remove that field in a cleanup version first."
            ),
            "scoreId": str(score_id),
            "versionId": str(version_id),
            "optimizer_shadow_invalid_feedback_item_ids": shadow_ids,
        }
    if version_data.get("scoreId") != str(score_id):
        return {
            "success": False,
            "error": "VERSION_SCORE_MISMATCH",
            "message": (
                f"Version {version_id} belongs to score "
                f"{version_data.get('scoreId')}, not {score_id}."
            ),
            "scoreId": str(score_id),
            "versionId": str(version_id),
        }

    previous_champion_version_id = score_data.get("championVersionId")
    previous_version_meta: dict[str, Any] = {}
    if previous_champion_version_id and previous_champion_version_id != str(version_id):
        prev_result = client.execute(
            """
            query GetScoreVersionForManagement($id: ID!) {
              getScoreVersion(id: $id) { id scoreId configuration guidelines isFeatured
                note branch parentVersionId metadata createdAt updatedAt }
            }
            """,
            {"id": previous_champion_version_id},
        )
        previous_version_meta = prev_result.get("getScoreVersion") or {}

    promo_result = client.execute(
        "mutation UpdateScore($input: UpdateScoreInput!) { "
        "updateScore(input: $input) { id championVersionId } }",
        {"input": {"id": str(score_id), "championVersionId": str(version_id)}},
    )
    if not promo_result or "updateScore" not in promo_result:
        raise RuntimeError(
            f"plexus.score.set_champion: mutation failed: {promo_result}"
        )

    updated = promo_result["updateScore"]
    promoted_at = datetime.now(timezone.utc).isoformat()
    transition_id = str(_uuid.uuid4())

    def _metadata_dict(metadata: Any) -> dict:
        if not metadata:
            return {}
        if isinstance(metadata, str):
            parsed = json.loads(metadata)
            return dict(parsed or {})
        return dict(metadata or {})

    def _build_meta(
        metadata: Any,
        *,
        score_id: str,
        version_id: str,
        transition_id: str,
        incoming: bool,
        entered_at: str | None = None,
        exited_at: str | None = None,
        previous_champion_version_id: str | None = None,
        next_champion_version_id: str | None = None,
    ) -> dict:
        next_meta: dict = _metadata_dict(metadata)
        history: list = list(next_meta.get("championHistory") or [])
        if incoming:
            open_idx = next((
                i for i in range(len(history) - 1, -1, -1)
                if history[i].get("versionId") == version_id
                and not history[i].get("exitedAt")
            ), None)
            if open_idx is None:
                history.append({
                    "scoreId": score_id, "versionId": version_id,
                    "enteredAt": entered_at, "exitedAt": None,
                    "previousChampionVersionId": previous_champion_version_id,
                    "nextChampionVersionId": None, "transitionId": transition_id,
                })
        else:
            open_idx = next((i for i in range(len(history) - 1, -1, -1)
                             if not history[i].get("exitedAt")), None)
            if open_idx is None:
                history.append({
                    "scoreId": score_id, "versionId": version_id,
                    "enteredAt": None, "exitedAt": exited_at,
                    "previousChampionVersionId": None,
                    "nextChampionVersionId": next_champion_version_id,
                    "transitionId": transition_id, "inferred": True,
                })
            else:
                history[open_idx] = {
                    **history[open_idx],
                    "exitedAt": exited_at,
                    "nextChampionVersionId": next_champion_version_id,
                    "transitionId": transition_id,
                }
        next_meta["championHistory"] = history
        return next_meta

    update_version_mutation = (
        "mutation UpdateScoreVersionMetadata($input: UpdateScoreVersionInput!) { "
        "updateScoreVersion(input: $input) { id isFeatured metadata } }"
    )
    incoming_meta = _build_meta(
        version_data.get("metadata"),
        score_id=str(score_id), version_id=str(version_id),
        transition_id=transition_id, incoming=True, entered_at=promoted_at,
        previous_champion_version_id=(
            previous_champion_version_id
            if previous_champion_version_id != str(version_id) else None
        ),
    )
    client.execute(update_version_mutation, {"input": {
        "id": str(version_id),
        "scoreId": str(score_id),
        "createdAt": version_data.get("createdAt"),
        "metadata": json.dumps(incoming_meta),
        "isFeatured": "true",
    }})
    if previous_champion_version_id and previous_champion_version_id != str(version_id):
        outgoing_meta = _build_meta(
            previous_version_meta.get("metadata"),
            score_id=str(score_id), version_id=previous_champion_version_id,
            transition_id=transition_id, incoming=False, exited_at=promoted_at,
            next_champion_version_id=str(version_id),
        )
        client.execute(update_version_mutation, {"input": {
            "id": previous_champion_version_id,
            "metadata": json.dumps(outgoing_meta),
        }})

    return {
        "success": True,
        "scoreId": updated["id"],
        "championVersionId": updated["championVersionId"],
        "previousChampionVersionId": previous_champion_version_id,
        "transitionId": transition_id,
        "promotedAt": promoted_at,
    }


def _default_score_contradictions(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.score.contradictions — checks ScoreVersion code vs. rubric for consistency.

    Required args:
        scorecard (str): Scorecard name, key, or ID.
        score (str): Score name, key, or ID.
        version (str): ScoreVersion UUID to check.

    Optional args:
        item_id (str): Item UUID whose transcript text is included as spot-check context.
        output_format (str): 'json' (default) or 'markdown'.

    Returns dict with keys: status ('consistent'|'potential_conflict'|'inconclusive'),
    paragraph, scorecard_identifier, score_identifier, score_version_id,
    checked_at, model, diagnostics.
    """

    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.score.scores import (
        memoized_resolve_scorecard_identifier,
        memoized_resolve_score_identifier,
    )
    from plexus.score_rubric_consistency import ScoreRubricConsistencyService

    scorecard_identifier = args.get("scorecard") or args.get("scorecard_identifier") or args.get("scorecard_name")
    score_identifier = args.get("score") or args.get("score_identifier") or args.get("score_name")
    score_version_id = args.get("version") or args.get("version_id") or args.get("score_version_id")

    if not scorecard_identifier:
        raise ValueError("plexus.score.contradictions requires 'scorecard'")
    if not score_identifier:
        raise ValueError("plexus.score.contradictions requires 'score'")
    if not score_version_id:
        raise ValueError("plexus.score.contradictions requires 'version' (ScoreVersion UUID)")

    client = create_client()
    if not client:
        raise RuntimeError("plexus.score.contradictions: could not create dashboard client")

    scorecard_id = memoized_resolve_scorecard_identifier(client, str(scorecard_identifier))
    if not scorecard_id:
        raise ValueError(f"Could not resolve scorecard: {scorecard_identifier}")
    score_id = memoized_resolve_score_identifier(client, scorecard_id, str(score_identifier))
    if not score_id:
        raise ValueError(f"Could not resolve score '{score_identifier}' in scorecard '{scorecard_identifier}'")

    item_text = ""
    item_id = args.get("item_id") or args.get("item")
    if item_id:
        from MCP.tools.tactus_runtime._item_helpers import _get_identifiers_for_item
        from plexus.cli.shared.client_utils import create_client as _cc

        _client2 = _cc()
        try:
            item_data = _get_identifiers_for_item(_client2, str(item_id))
            item_text = item_data.get("text") or ""
        except Exception:
            pass

    result = ScoreRubricConsistencyService().generate_from_api(
        client=client,
        scorecard_identifier=str(scorecard_identifier),
        score_identifier=str(score_identifier),
        score_id=str(score_id),
        score_version_id=str(score_version_id),
        item_text=item_text,
    )
    return result.to_parameters_payload()


def _default_item_last(args: dict[str, Any]) -> Any:
    """Run plexus.item.last directly using Item dashboard API."""

    import asyncio

    from plexus.cli.report.utils import resolve_account_id_for_command
    from plexus.cli.shared.client_utils import create_client
    from plexus.dashboard.api.models.item import Item
    from MCP.tools.tactus_runtime._item_helpers import (
        _get_feedback_items_for_item,
        _get_identifiers_for_item,
        _get_score_results_for_item,
        _get_item_url,
    )

    minimal = bool(args.get("minimal", False))
    count = min(max(1, int(args.get("count", 1))), 20)

    client = create_client()
    if not client:
        raise RuntimeError("plexus.item.last: could not create dashboard client")

    account_id = resolve_account_id_for_command(client, None)
    if not account_id:
        raise RuntimeError(
            "plexus.item.last: could not resolve account ID — is PLEXUS_ACCOUNT_KEY set?"
        )

    query = f"""
    query ListItemByAccountIdAndCreatedAt($accountId: String!, $limit: Int!) {{
        listItemByAccountIdAndCreatedAt(
            accountId: $accountId, sortDirection: DESC, limit: $limit
        ) {{
            items {{ {Item.fields()} }}
        }}
    }}
    """
    response = client.execute(query, {"accountId": account_id, "limit": count})
    if "errors" in response:
        raise RuntimeError(
            f"plexus.item.last dashboard error: {response['errors']}"
        )

    items = (
        response.get("listItemByAccountIdAndCreatedAt") or {}
    ).get("items") or []

    if not items:
        return {"items": [], "count": 0}

    async def _build(item_data: dict) -> dict:
        item = Item.from_dict(item_data, client)
        d: dict = {
            "id": item.id,
            "accountId": item.accountId,
            "evaluationId": item.evaluationId,
            "scoreId": item.scoreId,
            "description": item.description,
            "externalId": item.externalId,
            "isEvaluation": item.isEvaluation,
            "createdByType": item.createdByType,
            "metadata": item.metadata,
            "identifiers": await _get_identifiers_for_item(item.id, client) or item.identifiers,
            "attachedFiles": item.attachedFiles,
            "createdAt": item.createdAt.isoformat() if item.createdAt else None,
            "updatedAt": item.updatedAt.isoformat() if item.updatedAt else None,
            "url": _get_item_url(item.id),
        }
        if not minimal:
            d["scoreResults"] = await _get_score_results_for_item(item.id, client)
            d["feedbackItems"] = await _get_feedback_items_for_item(item.id, client)
        return d

    async def _build_all() -> list:
        return [await _build(item_data) for item_data in items]

    built = _run_async_from_sync(_build_all())
    if count == 1:
        return built[0]
    return {"items": built, "count": len(built)}


def _default_item_info(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.item.info directly using Item dashboard API."""

    from datetime import datetime

    from plexus.cli.shared.client_utils import create_client
    from plexus.dashboard.api.models.item import Item
    from plexus.utils.identifier_search import find_item_by_identifier
    from MCP.tools.tactus_runtime._item_helpers import (
        _get_feedback_items_for_item,
        _get_identifiers_for_item,
        _get_score_results_for_item,
        _get_item_url,
        _get_default_account_id,
    )

    item_id = (
        args.get("item_id")
        or args.get("id")
        or args.get("item")
    )
    if not item_id:
        raise ValueError("plexus.item.info requires id or item_id")
    minimal = bool(args.get("minimal", False))

    client = create_client()
    if not client:
        raise RuntimeError("plexus.item.info: could not create dashboard client")

    item = None
    lookup_method = "unknown"

    try:
        item = Item.get_by_id(str(item_id), client)
        if item:
            lookup_method = "direct_id"
    except ValueError:
        pass
    except Exception:
        pass

    if not item:
        default_account_id = _get_default_account_id()
        if default_account_id:
            try:
                item = find_item_by_identifier(str(item_id), default_account_id, client)
                if item:
                    lookup_method = "identifier_search"
            except Exception:
                pass

    if not item:
        default_account_id = _get_default_account_id()
        if default_account_id:
            try:
                gsi_query = """
                query GetIdentifierByAccountAndValue($accountId: String!, $value: String!) {
                    listIdentifierByAccountIdAndValue(
                        accountId: $accountId, value: {eq: $value}, limit: 1
                    ) {
                        items {
                            itemId name value url position
                            item {
                                id accountId evaluationId scoreId description
                                externalId isEvaluation text metadata identifiers
                                attachedFiles createdAt updatedAt
                            }
                        }
                    }
                }
                """
                result = client.execute(gsi_query, {"accountId": default_account_id, "value": str(item_id)})
                identifiers = (
                    result.get("listIdentifierByAccountIdAndValue") or {}
                ).get("items") or []
                if identifiers:
                    ident_data = identifiers[0]
                    item_data = ident_data.get("item") or {}
                    if item_data:
                        class _MockItem:
                            def __init__(self, data: dict) -> None:
                                for k, v in data.items():
                                    setattr(self, k, v)
                                for ts_field in ("createdAt", "updatedAt"):
                                    raw = getattr(self, ts_field, None)
                                    if raw and isinstance(raw, str):
                                        try:
                                            setattr(self, ts_field, datetime.fromisoformat(raw.replace("Z", "+00:00")))
                                        except Exception:
                                            pass
                        item = _MockItem(item_data)
                        lookup_method = f"identifiers_table_gsi (name: {ident_data.get('name', 'N/A')})"
            except Exception:
                pass

    if not item:
        raise ValueError(
            f"plexus.item.info: item {item_id!r} not found "
            "(tried direct ID, identifier search, identifiers table GSI)"
        )

    def _trunc(value: Any, max_chars: int = 5000) -> Any:
        if isinstance(value, str) and len(value) > max_chars:
            return f"{value[:max_chars]}... (truncated from {len(value):,} to {max_chars:,} chars)"
        return value

    item_dict: dict = {
        "id": item.id,
        "accountId": item.accountId,
        "evaluationId": item.evaluationId,
        "scoreId": item.scoreId,
        "description": _trunc(item.description, 1000),
        "externalId": item.externalId,
        "isEvaluation": item.isEvaluation,
        "createdByType": getattr(item, "createdByType", None),
        "text": _trunc(getattr(item, "text", None), 5000),
        "metadata": item.metadata,
        "identifiers": _run_async_from_sync(
            _get_identifiers_for_item(item.id, client)
        ) or item.identifiers,
        "attachedFiles": item.attachedFiles,
        "createdAt": (
            item.createdAt.isoformat()
            if hasattr(item.createdAt, "isoformat")
            else item.createdAt
        ),
        "updatedAt": (
            item.updatedAt.isoformat()
            if hasattr(item.updatedAt, "isoformat")
            else item.updatedAt
        ),
        "url": _get_item_url(item.id),
        "lookupMethod": lookup_method,
    }

    if not minimal:
        item_dict["scoreResults"] = _run_async_from_sync(
            _get_score_results_for_item(item.id, client)
        )
        item_dict["feedbackItems"] = _run_async_from_sync(
            _get_feedback_items_for_item(item.id, client)
        )

    return item_dict


def _default_dataset_build_from_feedback_window(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.dataset.build_from_feedback_window directly via curation."""

    from plexus.cli.dataset.curation import (
        build_associated_dataset_from_feedback_window,
    )
    from plexus.cli.dataset.datasets import create_client
    from plexus.cli.evaluation.evaluations import validate_dataset_materialization
    from plexus.cli.shared.identifier_resolution import (
        resolve_score_identifier,
        resolve_scorecard_identifier,
    )

    scorecard = args.get("scorecard") or args.get("scorecard_identifier")
    score = args.get("score") or args.get("score_identifier")
    if not scorecard or not score:
        raise ValueError(
            "plexus.dataset.build_from_feedback_window requires scorecard and score"
        )

    max_items = int(args.get("max_items", 100))
    days = args.get("days")
    balance = bool(args.get("balance", True))
    score_version_id = args.get("score_version_id")

    client = create_client()
    scorecard_id = resolve_scorecard_identifier(client, str(scorecard))
    if not scorecard_id:
        raise ValueError(
            f"plexus.dataset.build_from_feedback_window: scorecard {scorecard!r} not found"
        )
    score_id = resolve_score_identifier(client, scorecard_id, str(score))
    if not score_id:
        raise ValueError(
            f"plexus.dataset.build_from_feedback_window: score {score!r} not found"
        )

    result = build_associated_dataset_from_feedback_window(
        client=client,
        scorecard_id=scorecard_id,
        score_id=score_id,
        max_items=max_items,
        days=days,
        balance=balance,
        class_source_score_version_id=score_version_id or None,
    )
    dataset_id = result.get("dataset_id")
    dataset_file = result.get("dataset_file") or result.get("s3_key")
    readiness = validate_dataset_materialization(
        {"id": dataset_id, "file": dataset_file}
    )
    if not readiness.get("is_materialized"):
        reason = readiness.get("materialization_error") or "unknown"
        raise RuntimeError(
            "plexus.dataset.build_from_feedback_window completed without a "
            f"materialized file pointer. dataset_id={dataset_id} reason={reason}"
        )

    result["dataset_file"] = dataset_file
    result["is_materialized"] = True
    result["materialization_error"] = None
    return result


def _default_dataset_check_associated(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.dataset.check_associated directly."""

    from plexus.cli.dataset.datasets import create_client
    from plexus.cli.evaluation.evaluations import (
        list_associated_datasets_for_score,
        validate_dataset_materialization,
    )
    from plexus.cli.shared.identifier_resolution import (
        resolve_score_identifier,
        resolve_scorecard_identifier,
    )
    from plexus.cli.shared.optimizer_shadow_invalidation import (
        resolve_score_version_shadow_invalidation_metadata,
    )

    scorecard = args.get("scorecard") or args.get("scorecard_identifier")
    score = args.get("score") or args.get("score_identifier")
    if not scorecard or not score:
        raise ValueError(
            "plexus.dataset.check_associated requires scorecard and score"
        )
    score_version_id = args.get("score_version_id")
    days = args.get("days")

    client = create_client()
    scorecard_id = resolve_scorecard_identifier(client, str(scorecard))
    if not scorecard_id:
        raise ValueError(
            f"plexus.dataset.check_associated: scorecard {scorecard!r} not found"
        )
    score_id = resolve_score_identifier(client, scorecard_id, str(score))
    if not score_id:
        raise ValueError(
            f"plexus.dataset.check_associated: score {score!r} not found"
        )

    expected_feedback_target_hash: str | None = None
    if score_version_id is not None or days is not None:
        target_metadata = resolve_score_version_shadow_invalidation_metadata(
            client,
            score_id=score_id,
            score_version_id=score_version_id,
            days=days,
        )
        expected_feedback_target_hash = target_metadata.get(
            "feedback_target_hash"
        )

    datasets = list_associated_datasets_for_score(client, score_id)
    if not datasets:
        return {
            "has_dataset": False,
            "dataset_id": None,
            "dataset_name": None,
            "created_at": None,
            "row_count": None,
            "is_materialized": False,
            "dataset_file": None,
            "materialization_error": None,
            "feedback_target_hash": expected_feedback_target_hash,
        }

    dataset = None
    row_count: Any = None
    stored_feedback_target_hash: str | None = None
    stored_requested_max_items: Any = None
    stored_qualifying_found: Any = None
    stored_source_exhausted: Any = None
    stored_balance_applied: Any = None
    stored_balance_complete: Any = None
    stored_lookback_extended: Any = None
    stored_resolved_final_classes: Any = None
    stored_class_coverage: Any = None
    for candidate in datasets:
        candidate_row_count: Any = None
        candidate_feedback_target_hash: str | None = None
        candidate_requested_max_items: Any = None
        candidate_qualifying_found: Any = None
        candidate_source_exhausted: Any = None
        candidate_balance_applied: Any = None
        candidate_balance_complete: Any = None
        candidate_lookback_extended: Any = None
        candidate_resolved_final_classes: Any = None
        candidate_class_coverage: Any = None
        if candidate.get("dataSourceVersionId"):
            try:
                dsv_result = client.execute(
                    """
                    query GetDataSourceVersion($id: ID!) {
                        getDataSourceVersion(id: $id) { id yamlConfiguration }
                    }
                    """,
                    {"id": candidate["dataSourceVersionId"]},
                )
                dsv = dsv_result.get("getDataSourceVersion")
                if dsv and dsv.get("yamlConfiguration"):
                    import yaml

                    config = yaml.safe_load(dsv["yamlConfiguration"])
                    if isinstance(config, dict):
                        stats = config.get("dataset_stats", {}) or {}
                        candidate_row_count = stats.get("row_count")
                        candidate_requested_max_items = stats.get("requested_max_items")
                        candidate_qualifying_found = stats.get("qualifying_found")
                        candidate_source_exhausted = stats.get("source_exhausted")
                        candidate_balance_applied = stats.get("balance_applied")
                        candidate_balance_complete = stats.get("balance_complete")
                        candidate_lookback_extended = stats.get("lookback_extended")
                        candidate_resolved_final_classes = stats.get(
                            "resolved_final_classes"
                        )
                        candidate_class_coverage = stats.get("class_coverage")
                        candidate_feedback_target_hash = stats.get(
                            "feedback_target_hash"
                        )
            except Exception:
                pass

        if (
            expected_feedback_target_hash
            and candidate_feedback_target_hash != expected_feedback_target_hash
        ):
            continue

        dataset = candidate
        row_count = candidate_row_count
        stored_feedback_target_hash = candidate_feedback_target_hash
        stored_requested_max_items = candidate_requested_max_items
        stored_qualifying_found = candidate_qualifying_found
        stored_source_exhausted = candidate_source_exhausted
        stored_balance_applied = candidate_balance_applied
        stored_balance_complete = candidate_balance_complete
        stored_lookback_extended = candidate_lookback_extended
        stored_resolved_final_classes = candidate_resolved_final_classes
        stored_class_coverage = candidate_class_coverage
        break

    if not dataset:
        return {
            "has_dataset": False,
            "dataset_id": None,
            "dataset_name": None,
            "created_at": None,
            "row_count": None,
            "is_materialized": False,
            "dataset_file": None,
            "materialization_error": None,
            "feedback_target_hash": expected_feedback_target_hash,
        }

    readiness = validate_dataset_materialization(dataset)
    return {
        "has_dataset": True,
        "dataset_id": dataset.get("id"),
        "dataset_name": dataset.get("name"),
        "created_at": dataset.get("createdAt"),
        "row_count": row_count,
        "requested_max_items": stored_requested_max_items,
        "qualifying_found": stored_qualifying_found,
        "source_exhausted": stored_source_exhausted,
        "balance_applied": stored_balance_applied,
        "balance_complete": stored_balance_complete,
        "lookback_extended": stored_lookback_extended,
        "resolved_final_classes": stored_resolved_final_classes,
        "class_coverage": stored_class_coverage,
        "is_materialized": bool(readiness.get("is_materialized")),
        "dataset_file": readiness.get("dataset_file"),
        "materialization_error": readiness.get("materialization_error"),
        "feedback_target_hash": stored_feedback_target_hash
        or expected_feedback_target_hash,
    }


def _default_report_configurations_list(args: dict[str, Any]) -> Any:
    """Run plexus.report.configurations_list directly via dashboard GraphQL."""

    from plexus.cli.shared.client_utils import create_client

    client = create_client()
    if not client:
        raise RuntimeError(
            "plexus.report.configurations_list: could not create dashboard client"
        )

    account_id = _resolve_runtime_account_id(
        client, args, "plexus.report.configurations_list"
    )

    query = (
        "query MyQuery { "
        f'listReportConfigurationByAccountIdAndUpdatedAt(accountId: "{account_id}", '
        "sortDirection: DESC) { items { description name id updatedAt } "
        "nextToken } }"
    )
    response = client.execute(query)
    if "errors" in response:
        raise RuntimeError(
            f"plexus.report.configurations_list dashboard error: {response['errors']}"
        )

    configs = (
        response.get("listReportConfigurationByAccountIdAndUpdatedAt") or {}
    ).get("items") or []

    if not configs:
        retry_query = (
            "query RetryQuery { "
            f'listReportConfigurations(filter: {{ accountId: {{ eq: "{account_id}" }} }}, '
            "limit: 20) { items { id name description updatedAt } } }"
        )
        retry_response = client.execute(retry_query)
        configs = (retry_response.get("listReportConfigurations") or {}).get(
            "items"
        ) or []

    return [
        {
            "id": cfg.get("id"),
            "name": cfg.get("name"),
            "description": cfg.get("description"),
            "updatedAt": cfg.get("updatedAt"),
        }
        for cfg in configs
    ]


def _serialize_datetime(value: Any) -> Any:
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    return value


def _serialize_report_model(report: Any) -> dict[str, Any]:
    return {
        "id": getattr(report, "id", None),
        "accountId": getattr(report, "accountId", None),
        "name": getattr(report, "name", None),
        "taskId": getattr(report, "taskId", None),
        "reportConfigurationId": getattr(report, "reportConfigurationId", None),
        "parameters": getattr(report, "parameters", None) or {},
        "output": getattr(report, "output", None),
        "createdAt": _serialize_datetime(getattr(report, "createdAt", None)),
        "updatedAt": _serialize_datetime(getattr(report, "updatedAt", None)),
        "createdByUserId": getattr(report, "createdByUserId", None),
    }


def _serialize_report_block_model(block: Any, *, include_output: bool) -> dict[str, Any]:
    result = {
        "id": getattr(block, "id", None),
        "reportId": getattr(block, "reportId", None),
        "position": getattr(block, "position", None),
        "type": getattr(block, "type", None),
        "name": getattr(block, "name", None),
        "log": getattr(block, "log", None),
        "attachedFiles": getattr(block, "attachedFiles", None),
        "dataSetId": getattr(block, "dataSetId", None),
        "createdAt": _serialize_datetime(getattr(block, "createdAt", None)),
        "updatedAt": _serialize_datetime(getattr(block, "updatedAt", None)),
    }
    if include_output:
        result["output"] = getattr(block, "output", None)
    return result


def _coerce_positive_int(value: Any, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))


def _default_report_list(args: dict[str, Any]) -> dict[str, Any]:
    """List persisted reports for the runtime account."""

    from plexus.cli.shared.client_utils import create_client
    from plexus.dashboard.api.models.report import Report

    client = create_client()
    if not client:
        raise RuntimeError("plexus.report.list: could not create dashboard client")

    account_id = _resolve_runtime_account_id(client, args, "plexus.report.list")
    limit = _coerce_positive_int(args.get("limit"), default=20, maximum=100)
    name_filter = str(args.get("name") or "").strip()
    configuration_id = str(
        args.get("configuration_id") or args.get("reportConfigurationId") or ""
    ).strip()
    fetch_limit = limit if not (name_filter or configuration_id) else max(limit, 100)
    reports = Report.list_by_account_id(
        account_id,
        client,
        limit=min(fetch_limit, 100),
        max_items=fetch_limit,
    )
    items: list[dict[str, Any]] = []
    for report in reports:
        if name_filter and name_filter.lower() not in str(report.name or "").lower():
            continue
        if configuration_id and getattr(report, "reportConfigurationId", None) != configuration_id:
            continue
        items.append(_serialize_report_model(report))
        if len(items) >= limit:
            break
    return {"account_id": account_id, "count": len(items), "items": items}


def _default_report_info(args: dict[str, Any]) -> dict[str, Any]:
    """Fetch one persisted report by id for the runtime account."""

    from plexus.cli.shared.client_utils import create_client
    from plexus.dashboard.api.models.report import Report

    report_id = str(args.get("id") or args.get("report_id") or "").strip()
    if not report_id:
        raise ValueError("plexus.report.info requires id or report_id")

    client = create_client()
    if not client:
        raise RuntimeError("plexus.report.info: could not create dashboard client")

    account_id = _resolve_runtime_account_id(client, args, "plexus.report.info")
    report = Report.get_by_id(report_id, client)
    if report is None:
        raise ValueError(f"Report not found: {report_id}")
    if getattr(report, "accountId", None) != account_id:
        raise PermissionError(
            f"Report {report_id} does not belong to the current runtime account"
        )
    return _serialize_report_model(report)


def _default_report_blocks(args: dict[str, Any]) -> dict[str, Any]:
    """List persisted blocks for one report after account ownership validation."""

    from plexus.cli.shared.client_utils import create_client
    from plexus.dashboard.api.models.report import Report
    from plexus.dashboard.api.models.report_block import ReportBlock

    report_id = str(args.get("report_id") or args.get("id") or "").strip()
    if not report_id:
        raise ValueError("plexus.report.blocks requires report_id or id")

    client = create_client()
    if not client:
        raise RuntimeError("plexus.report.blocks: could not create dashboard client")

    account_id = _resolve_runtime_account_id(client, args, "plexus.report.blocks")
    report = Report.get_by_id(report_id, client)
    if report is None:
        raise ValueError(f"Report not found: {report_id}")
    if getattr(report, "accountId", None) != account_id:
        raise PermissionError(
            f"Report {report_id} does not belong to the current runtime account"
        )

    limit = _coerce_positive_int(args.get("limit"), default=100, maximum=500)
    include_output = bool(args.get("include_output", True))
    blocks = ReportBlock.list_by_report_id(
        report_id,
        client,
        limit=min(limit, 100),
        max_items=limit,
    )
    items = [
        _serialize_report_block_model(block, include_output=include_output)
        for block in blocks
    ]
    return {"report_id": report_id, "count": len(items), "blocks": items}


def _default_evaluation_compare(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.evaluation.compare directly via Evaluation.get_evaluation_info."""

    from plexus.Evaluation import Evaluation

    evaluation_id = args.get("evaluation_id")
    baseline_evaluation_id = (
        args.get("baseline_evaluation_id") or args.get("baseline_id")
    )
    if not evaluation_id or not str(evaluation_id).strip():
        raise ValueError("plexus.evaluation.compare requires evaluation_id")
    if not baseline_evaluation_id or not str(baseline_evaluation_id).strip():
        raise ValueError(
            "plexus.evaluation.compare requires baseline_evaluation_id"
        )

    current_eval = Evaluation.get_evaluation_info(
        str(evaluation_id).strip(), include_score_results=False
    )
    baseline_eval = Evaluation.get_evaluation_info(
        str(baseline_evaluation_id).strip(), include_score_results=False
    )
    if not current_eval:
        raise ValueError(f"Current evaluation not found: {evaluation_id}")
    if not baseline_eval:
        raise ValueError(
            f"Baseline evaluation not found: {baseline_evaluation_id}"
        )

    def extract(eval_info: dict[str, Any]) -> dict[str, float]:
        out: dict[str, float] = {}
        metrics = eval_info.get("metrics")
        if isinstance(metrics, list):
            for metric in metrics:
                if (
                    isinstance(metric, dict)
                    and "name" in metric
                    and "value" in metric
                ):
                    try:
                        out[metric["name"]] = float(metric["value"])
                    except (TypeError, ValueError):
                        continue
        return out

    current_metrics = extract(current_eval)
    baseline_metrics = extract(baseline_eval)
    deltas = {
        k: current_metrics[k] - baseline_metrics[k]
        for k in current_metrics
        if k in baseline_metrics
    }
    return {
        "evaluation_id": str(evaluation_id),
        "baseline_evaluation_id": str(baseline_evaluation_id),
        "current_metrics": current_metrics,
        "baseline_metrics": baseline_metrics,
        "deltas": deltas,
        "improved": deltas.get("Alignment", 0) > 0,
    }


def _default_evaluation_find_recent(args: dict[str, Any]) -> dict[str, Any]:
    """Run plexus.evaluation.find_recent directly against the dashboard."""

    from datetime import datetime, timedelta, timezone

    from plexus.dashboard.api.client import PlexusDashboardClient
    from plexus.Evaluation import Evaluation

    score_version_id = args.get("score_version_id")
    evaluation_type = args.get("evaluation_type")

    # Auto-resolve score_version_id when scorecard/score names are supplied.
    if not score_version_id:
        scorecard_id_or_name = args.get("scorecard") or args.get("scorecard_identifier")
        score_id_or_name = args.get("score") or args.get("score_identifier") or args.get("id")
        if scorecard_id_or_name and score_id_or_name:
            try:
                from plexus.cli.shared.client_utils import create_client as _cc
                from plexus.cli.shared.memoized_resolvers import (
                    memoized_resolve_scorecard_identifier,
                )

                _client = _cc()
                if _client:
                    _sc_id = memoized_resolve_scorecard_identifier(_client, str(scorecard_id_or_name))
                    if _sc_id:
                        # Fetch championVersionId directly via GraphQL — it's a
                        # scorecard-level field not exposed on the Python Score model.
                        _sid_needle = str(score_id_or_name).lower()
                        _sc_result = _client.execute(
                            f"""query GetScorecardChampionVersion {{
                                getScorecard(id: "{_sc_id}") {{
                                    sections {{ items {{ scores {{ items {{
                                        id name key externalId championVersionId
                                    }} }} }} }}
                                }}
                            }}"""
                        )
                        _sc_data = _sc_result.get("getScorecard") or {}
                        for _sec in (_sc_data.get("sections") or {}).get("items", []):
                            for _s in (_sec.get("scores") or {}).get("items", []):
                                if (
                                    _s.get("id") == str(score_id_or_name)
                                    or _s.get("key") == str(score_id_or_name)
                                    or (_s.get("name") or "").lower() == _sid_needle
                                    or _sid_needle in (_s.get("name") or "").lower()
                                ):
                                    score_version_id = _s.get("championVersionId")
                                    break
                            if score_version_id:
                                break
            except Exception:
                pass

    if not score_version_id:
        raise ValueError(
            "plexus.evaluation.find_recent requires score_version_id "
            "(or { scorecard = '...', score = '...' } to auto-resolve it)"
        )
    if not evaluation_type:
        raise ValueError("plexus.evaluation.find_recent requires evaluation_type")

    max_age_hours = float(args.get("max_age_hours", 24.0))
    min_items = int(args.get("min_items", 0))
    dataset_id = args.get("dataset_id")
    days = args.get("days")
    max_feedback_items = args.get("max_feedback_items")
    sampling_mode = args.get("sampling_mode")
    latest_feedback_updated_at = args.get("latest_feedback_updated_at")
    feedback_start_at = args.get("feedback_start_at")
    feedback_end_at = args.get("feedback_end_at")

    client = PlexusDashboardClient()
    query = """
    query FindRecentEvalByVersion($scoreVersionId: String!, $limit: Int) {
      listEvaluationByScoreVersionIdAndCreatedAt(
        scoreVersionId: $scoreVersionId sortDirection: DESC limit: $limit
      ) { items { id type status scoreVersionId totalItems createdAt } }
    }
    """
    result = client.execute(
        query, {"scoreVersionId": str(score_version_id), "limit": 20}
    )
    items = (
        (result.get("listEvaluationByScoreVersionIdAndCreatedAt") or {})
        .get("items", [])
    )

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    normalized_eval_type = str(evaluation_type or "").strip().lower()
    normalized_sampling_mode = (
        str(sampling_mode or "").strip().lower()
        if sampling_mode is not None
        else None
    )
    latest_feedback_dt = None
    if latest_feedback_updated_at:
        try:
            latest_feedback_dt = datetime.fromisoformat(
                str(latest_feedback_updated_at).replace("Z", "+00:00")
            )
            if latest_feedback_dt.tzinfo is None:
                latest_feedback_dt = latest_feedback_dt.replace(tzinfo=timezone.utc)
        except Exception:
            latest_feedback_dt = None

    for item in items:
        if item.get("status") != "COMPLETED":
            continue
        if item.get("type", "").lower() != normalized_eval_type:
            continue
        if (item.get("totalItems") or 0) < min_items:
            continue
        created_raw = item.get("createdAt")
        if not created_raw:
            continue
        try:
            if isinstance(created_raw, str):
                created_at = datetime.fromisoformat(
                    created_raw.replace("Z", "+00:00")
                )
            else:
                created_at = created_raw
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at < cutoff:
                continue
        except Exception:
            continue

        eval_id = item["id"]
        try:
            eval_info = Evaluation.get_evaluation_info(eval_id)
        except Exception:
            continue

        parameters = eval_info.get("parameters") or {}
        if not isinstance(parameters, dict):
            parameters = {}

        if normalized_eval_type == "accuracy" and dataset_id is not None:
            eval_dataset_id = parameters.get("dataset_id")
            if (
                not eval_dataset_id
                and isinstance(parameters.get("metadata"), dict)
            ):
                eval_dataset_id = parameters["metadata"].get("dataset_id")
            if str(eval_dataset_id or "") != str(dataset_id):
                continue

        if normalized_eval_type == "feedback":
            if days is not None:
                try:
                    requested_days = int(days)
                    eval_days_int = (
                        int(parameters.get("days"))
                        if parameters.get("days") is not None
                        else None
                    )
                except Exception:
                    eval_days_int = None
                    requested_days = int(days)
                if eval_days_int is None or eval_days_int != requested_days:
                    continue
            if max_feedback_items is not None:
                try:
                    requested_max_items = int(max_feedback_items)
                    eval_max_items_int = (
                        int(parameters.get("max_feedback_items"))
                        if parameters.get("max_feedback_items") is not None
                        else None
                    )
                except Exception:
                    eval_max_items_int = None
                    requested_max_items = int(max_feedback_items)
                if (
                    eval_max_items_int is None
                    or eval_max_items_int != requested_max_items
                ):
                    continue
            if normalized_sampling_mode is not None:
                eval_sampling_mode = (
                    str(parameters.get("sampling_mode") or "").strip().lower()
                )
                if eval_sampling_mode != normalized_sampling_mode:
                    continue
            if latest_feedback_dt is not None:
                created_text = eval_info.get("created_at") or item.get("createdAt")
                try:
                    created_dt = datetime.fromisoformat(
                        str(created_text).replace("Z", "+00:00")
                    )
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                if created_dt < latest_feedback_dt:
                    continue
            if feedback_start_at is not None:
                if str(parameters.get("feedback_start_at") or "") != str(feedback_start_at):
                    continue
            if feedback_end_at is not None:
                if str(parameters.get("feedback_end_at") or "") != str(feedback_end_at):
                    continue

        return {
            "_from_cache": True,
            "evaluation_id": eval_id,
            "id": eval_id,
            "type": eval_info.get("type"),
            "status": eval_info.get("status"),
            "scorecard": eval_info.get("scorecard_name")
            or eval_info.get("scorecard_id"),
            "score": eval_info.get("score_name") or eval_info.get("score_id"),
            "score_version_id": eval_info.get("score_version_id"),
            "total_items": eval_info.get("total_items"),
            "processed_items": eval_info.get("processed_items"),
            "metrics": eval_info.get("metrics"),
            "accuracy": eval_info.get("accuracy"),
            "confusionMatrix": eval_info.get("confusion_matrix"),
            "predictedClassDistribution": eval_info.get(
                "predicted_class_distribution"
            ),
            "datasetClassDistribution": eval_info.get(
                "dataset_class_distribution"
            ),
            "baselineEvaluationId": eval_info.get("baseline_evaluation_id"),
            "currentBaselineEvaluationId": eval_info.get(
                "current_baseline_evaluation_id"
            ),
            "cost": eval_info.get("cost"),
            "cost_details": eval_info.get("cost_details"),
            "started_at": eval_info.get("started_at"),
            "created_at": eval_info.get("created_at"),
            "updated_at": eval_info.get("updated_at"),
            "root_cause": eval_info.get("root_cause"),
            "misclassification_analysis": eval_info.get(
                "misclassification_analysis"
            ),
        }

    return {"found": False}


def _default_evaluation_runner(args: dict[str, Any], mcp: "FastMCP | None") -> dict[str, Any]:
    """Dispatch evaluation.run directly through the Plexus CLI in async mode.

    Uses --emit-id-file to capture the evaluation_id from the subprocess so the
    handle store can poll the evaluation status via the dashboard API once the
    process exits.
    """

    import shutil
    import subprocess
    import tempfile

    scorecard_name = args.get("scorecard_name") or args.get("scorecard")
    if not scorecard_name:
        raise ValueError("plexus.evaluation.run requires scorecard_name")

    evaluation_type = str(args.get("evaluation_type") or "accuracy").strip().lower()
    plexus_bin = shutil.which("plexus") or "plexus"

    # Temp file for evaluation_id capture (read after process starts)
    id_tmpfile = tempfile.NamedTemporaryFile(
        prefix="plexus_eval_id_", suffix=".txt", delete=False
    )
    id_tmpfile.close()
    id_file_path = id_tmpfile.name

    if evaluation_type == "feedback":
        score_name = args.get("score_name") or args.get("score")
        if not score_name:
            raise ValueError("plexus.evaluation.run feedback requires score_name")
        cmd = [
            plexus_bin,
            "evaluate",
            "feedback",
            "--scorecard",
            str(scorecard_name),
            "--score",
            str(score_name),
            "--max-items",
            str(int(args.get("max_feedback_items") or 200)),
            "--sampling-mode",
            str(args.get("sampling_mode") or "newest"),
            "--emit-id-file",
            id_file_path,
        ]
        _append_optional_cli_arg(cmd, "--days", args.get("days"))
        _append_optional_cli_arg(cmd, "--version", args.get("version"))
        _append_optional_cli_arg(cmd, "--sample-seed", args.get("sample_seed"))
        _append_optional_cli_arg(cmd, "--feedback-start-at", args.get("feedback_start_at"))
        _append_optional_cli_arg(cmd, "--feedback-end-at", args.get("feedback_end_at"))
        for feedback_item_id in args.get("feedback_item_ids") or []:
            cmd.extend(["--feedback-item-id", str(feedback_item_id)])
        _append_optional_cli_arg(
            cmd, "--max-category-summary-items", args.get("max_category_summary_items")
        )
        if args.get("score_rubric_consistency_check"):
            cmd.append("--score-rubric-consistency-check")
    elif evaluation_type == "accuracy":
        cmd = [
            plexus_bin,
            "evaluate",
            "accuracy",
            "--scorecard",
            str(scorecard_name),
            "--number-of-samples",
            str(int(args.get("n_samples") or 10)),
            "--json-only",
            "--emit-id-file",
            id_file_path,
        ]
        _append_optional_cli_arg(
            cmd, "--score", args.get("score_name") or args.get("score")
        )
        _append_optional_cli_arg(cmd, "--version", args.get("version"))
        _append_optional_cli_arg(cmd, "--dataset-id", args.get("dataset_id"))
        if args.get("latest"):
            cmd.append("--latest")
        if args.get("fresh"):
            cmd.append("--fresh")
        if args.get("reload"):
            cmd.append("--reload")
        if args.get("allow_no_labels"):
            cmd.append("--allow-no-labels")
        if args.get("use_score_associated_dataset"):
            cmd.append("--use-score-associated-dataset")
        if args.get("yaml", False):
            cmd.append("--yaml")
    else:
        raise ValueError(
            "plexus.evaluation.run evaluation_type must be 'accuracy' or 'feedback'"
        )

    _append_optional_cli_arg(cmd, "--baseline", args.get("baseline"))
    _append_optional_cli_arg(cmd, "--current-baseline", args.get("current_baseline"))
    _append_optional_cli_arg(cmd, "--notes", args.get("notes"))
    _append_optional_cli_arg(cmd, "--procedure-id", args.get("procedure_id"))

    child_budget = args.get("budget")
    env = apply_actor_context_to_env(os.environ.copy())
    if isinstance(child_budget, dict):
        env["PLEXUS_CHILD_BUDGET"] = json.dumps(_jsonable(child_budget), sort_keys=True)

    stdout_tmp = tempfile.NamedTemporaryFile(
        prefix="plexus_eval_stdout_", suffix=".log", delete=False
    )
    stderr_tmp = tempfile.NamedTemporaryFile(
        prefix="plexus_eval_stderr_", suffix=".log", delete=False
    )
    stdout_log_path = stdout_tmp.name
    stderr_log_path = stderr_tmp.name

    process = subprocess.Popen(
        cmd,
        stdout=stdout_tmp,
        stderr=stderr_tmp,
        start_new_session=True,
        env=env,
    )
    stdout_tmp.close()
    stderr_tmp.close()
    _register_evaluation_process(process)

    # Poll briefly for the id file (evaluation record is created near the start)
    evaluation_id: str | None = None
    for _ in range(30):  # up to 30 × 2s = 60s
        time.sleep(2)
        try:
            with open(id_file_path, "r") as _f:
                content = _f.read().strip()
            if content:
                evaluation_id = content
                break
        except FileNotFoundError:
            pass
        # Also check if process already exited (fast-fail / error case)
        if process.poll() is not None:
            break

    if evaluation_id:
        try:
            os.unlink(id_file_path)
        except OSError:
            pass

    exit_code = process.poll()
    if evaluation_id is None and exit_code is not None:
        def _tail(path: str) -> str:
            try:
                with open(path, "rb") as log_file:
                    return log_file.read()[-3000:].decode("utf-8", errors="replace")
            except OSError:
                return ""

        return {
            "status": "error",
            "process_id": process.pid,
            "evaluation_id": None,
            "evaluation_id_file": id_file_path,
            "stdout_log": stdout_log_path,
            "stderr_log": stderr_log_path,
            "command": cmd,
            "evaluation_type": evaluation_type,
            "scorecard": scorecard_name,
            "score": args.get("score_name") or args.get("score"),
            "child_budget": _jsonable(child_budget),
            "error": (
                "Evaluation subprocess exited before creating an evaluation record "
                f"(exit={exit_code}). STDERR tail:\n{_tail(stderr_log_path)}\n"
                f"STDOUT tail:\n{_tail(stdout_log_path)}"
            ),
        }

    return {
        "status": "dispatched",
        "process_id": process.pid,
        "evaluation_id": evaluation_id,
        "evaluation_id_file": None if evaluation_id else id_file_path,
        "stdout_log": stdout_log_path,
        "stderr_log": stderr_log_path,
        "command": cmd,
        "evaluation_type": evaluation_type,
        "scorecard": scorecard_name,
        "score": args.get("score_name") or args.get("score"),
        "child_budget": _jsonable(child_budget),
        "message": "Evaluation dispatched in background.",
        "dashboard_url": (
            f"https://lab.callcriteria.com/lab/evaluations/{evaluation_id}"
            if evaluation_id
            else "https://lab.callcriteria.com/lab/evaluations"
        ),
    }


def _append_optional_cli_arg(cmd: list[str], flag: str, value: Any) -> None:
    if value is not None and value != "":
        cmd.extend([flag, str(value)])


def _resolve_report_dispatch_mode() -> str:
    mode = os.environ.get("PLEXUS_DISPATCH_MODE", "celery").strip().lower()
    if mode not in {"celery", "local"}:
        raise ValueError(
            f"Invalid PLEXUS_DISPATCH_MODE={mode!r}. Valid values: celery, local."
        )
    return mode


def _build_report_config_command(configuration_id: str, parameters: dict[str, Any]) -> str:
    parts = ["report", "run", "--config", str(configuration_id)]
    for key, value in (parameters or {}).items():
        parts.append(f"{key}={value}")
    return " ".join(shlex.quote(str(part)) for part in parts)


def _normalize_report_block_config(block_class: Any, block_config: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(block_config or {})
    if str(block_class) == "FeedbackAlignment" and "memory_analysis" not in normalized:
        normalized["memory_analysis"] = False
    return normalized


def _default_report_runner(args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch report.run async.

    PLEXUS_DISPATCH_MODE=celery (default) — enqueue via the remote task dispatcher.
    PLEXUS_DISPATCH_MODE=local            — run directly in a local subprocess.
    """
    import os
    import threading

    remote = _resolve_report_dispatch_mode() == "celery"

    from plexus.cli.shared.client_utils import create_client as create_dashboard_client

    client = create_dashboard_client()
    if not client:
        raise ValueError("Could not create dashboard client")
    account_id = _resolve_runtime_account_id(client, args, "plexus.report.run")

    configuration_id = args.get("configuration_id") or args.get("config_id")
    if configuration_id:
        parameters = args.get("parameters") or {}

        if remote:
            from plexus.dashboard.api.models.task import Task

            command = _build_report_config_command(str(configuration_id), parameters)
            task = Task.create(
                client=client,
                accountId=account_id,
                type="Report",
                target="report/configuration",
                command=command,
                description=f"Run report configuration {configuration_id}",
                metadata=json.dumps({
                    "report_configuration_id": str(configuration_id),
                    "report_parameters": parameters,
                    "account_id": account_id,
                    "trigger": "mcp_remote",
                }),
                dispatchStatus="PENDING",
                status="PENDING",
            )
            return {
                "status": "dispatched",
                "configuration_id": configuration_id,
                "parameters": parameters,
                "task_id": task.id,
            }
        else:
            import subprocess
            import sys

            cmd = [
                sys.executable, "-m", "plexus", "report", "run",
                "--config", configuration_id,
            ]
            for k, v in parameters.items():
                cmd.append(f"{k}={v}")

            env = apply_actor_context_to_env({**__import__("os").environ, "PYTHONUNBUFFERED": "1"})
            proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {
                "status": "running",
                "configuration_id": configuration_id,
                "parameters": parameters,
                "pid": proc.pid,
            }

    block_class = args.get("block_class")
    if not block_class:
        raise ValueError("plexus.report.run async requires block_class or configuration_id")

    from plexus.reports.service import run_block_cached

    block_config = _normalize_report_block_config(block_class, args.get("block_config") or {})
    cache_key = args.get("cache_key")
    ttl_hours = args.get("ttl_hours") if args.get("ttl_hours") is not None else 24
    fresh = bool(args.get("fresh", False))

    if remote:
        output_data, log_output, was_cached = run_block_cached(
            block_class=str(block_class),
            block_config=block_config,
            account_id=account_id,
            client=client,
            cache_key=cache_key,
            ttl_hours=ttl_hours,
            fresh=fresh,
            background=True,
            child_budget=_jsonable(args.get("budget")),
        )
        if not isinstance(output_data, dict):
            raise ValueError(log_output or "Report block remote dispatch failed")
        normalized_output: dict[str, Any] = dict(output_data)
        if "status" not in normalized_output:
            if not normalized_output:
                raise ValueError("Report block remote dispatch returned empty payload")
            normalized_output = {
                "status": "completed",
                "cached": bool(was_cached),
                "result": normalized_output,
            }
        elif was_cached:
            normalized_output["cached"] = True
        return {
            **normalized_output,
            "block_class": block_class,
            "child_budget": _jsonable(args.get("budget")),
        }
    else:
        import subprocess
        import sys
        import json as _json

        report_cli_by_block = {
            "FeedbackAlignment": "alignment",
            "FeedbackContradictions": "contradictions",
            "AcceptanceRate": "acceptance-rate",
            "CorrectionRate": "correction-rate",
            "ScoreChampionVersionTimeline": "score-champion-version-timeline",
        }
        report_cli_subcommand = report_cli_by_block.get(str(block_class))
        if not report_cli_subcommand:
            allowed = ", ".join(sorted(report_cli_by_block.keys()))
            raise ValueError(
                f"Unsupported block_class for local report dispatch: {block_class!r}. "
                f"Supported values: {allowed}"
            )

        cmd = [
            sys.executable,
            "-m",
            "plexus",
            "feedback",
            "report",
            report_cli_subcommand,
            "--scorecard",
            str(block_config.get("scorecard", "")),
        ]
        if block_config.get("score"):
            cmd += ["--score", str(block_config["score"])]
        if block_config.get("days"):
            cmd += ["--days", str(block_config["days"])]
        if block_config.get("start_date"):
            cmd += ["--start-date", str(block_config["start_date"])]
        if block_config.get("end_date"):
            cmd += ["--end-date", str(block_config["end_date"])]
        _append_optional_cli_arg(cmd, "--cache-key", cache_key)
        _append_optional_cli_arg(cmd, "--ttl-hours", args.get("ttl_hours"))
        if block_class == "AcceptanceRate":
            if block_config.get("include_item_acceptance_rate"):
                cmd.append("--include-item-acceptance-rate")
            if block_config.get("max_items") is not None:
                cmd += ["--max-items", str(block_config["max_items"])]
        if block_class == "FeedbackContradictions":
            _append_optional_cli_arg(cmd, "--score-version-id", block_config.get("score_version_id"))
            _append_optional_cli_arg(cmd, "--mode", block_config.get("mode"))
            _append_optional_cli_arg(cmd, "--max-feedback-items", block_config.get("max_feedback_items"))
            _append_optional_cli_arg(cmd, "--num-topics", block_config.get("num_topics"))
            _append_optional_cli_arg(cmd, "--max-concurrent", block_config.get("max_concurrent"))
            if block_config.get("include_rubric_memory"):
                cmd.append("--include-rubric-memory")
        if block_class == "ScoreChampionVersionTimeline":
            if block_config.get("include_unchanged"):
                cmd.append("--include-unchanged")
        if fresh:
            cmd.append("--fresh")

        env = apply_actor_context_to_env({**__import__("os").environ, "PYTHONUNBUFFERED": "1"})
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {
            "status": "running",
            "block_class": block_class,
            "pid": proc.pid,
        }


def _default_report_runner_sync(args: dict[str, Any]) -> dict[str, Any]:
    """Run a report block synchronously and return its output directly.

    Used inside procedures where blocking is acceptable (i.e. the Lua code
    needs the report output before continuing).  Passes background=False to
    run_block_cached so the block executes in the current process.
    """
    block_class = args.get("block_class")
    if not block_class:
        raise ValueError("plexus.report.run sync requires block_class")

    from plexus.cli.shared.client_utils import create_client as create_dashboard_client
    from plexus.reports.service import run_block_cached

    client = create_dashboard_client()
    if not client:
        raise ValueError("Could not create dashboard client")
    account_id = _resolve_runtime_account_id(client, args, "plexus.report.run")

    cache_key = args.get("cache_key")
    ttl_hours = args.get("ttl_hours")

    output_data, log_output, was_cached = run_block_cached(
        block_class=str(block_class),
        block_config=_normalize_report_block_config(block_class, args.get("block_config") or {}),
        account_id=account_id,
        client=client,
        cache_key=cache_key,
        ttl_hours=ttl_hours if ttl_hours is not None else 24,
        fresh=bool(args.get("fresh", False)),
        background=False,
    )

    if output_data is not None:
        return {
            "status": "success",
            "output": output_data,
            "log": log_output,
            "cached": was_cached,
            "block_class": block_class,
        }
    return {
        "status": "failed",
        "error": log_output or "Report block returned no output",
        "block_class": block_class,
    }


def _default_procedure_runner(args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch procedure.run as an independent subprocess."""

    procedure_id = args.get("procedure_id") or args.get("id")
    if not procedure_id:
        raise ValueError("plexus.procedure.run requires procedure_id")

    import sys

    cmd = [
        sys.executable, "-m", "plexus", "procedure", "run",
        str(procedure_id),
    ]
    if args.get("max_iterations") is not None:
        cmd += ["--max-iterations", str(int(args["max_iterations"]))]
    if args.get("dry_run"):
        cmd.append("--dry-run")

    proc, log_path = _launch_local_procedure_subprocess(cmd, str(procedure_id))
    return {
        "status": "running",
        "procedure_id": str(procedure_id),
        "pid": proc.pid,
        "log_path": log_path,
    }


def _default_procedure_optimize(args: dict[str, Any]) -> dict[str, Any]:
    """Start a Feedback Alignment Optimizer run for a given score.

    Creates a new procedure from the built-in feedback_alignment_optimizer.yaml,
    injects the supplied parameters, and dispatches it asynchronously.

    Required args:
        scorecard (str): Scorecard name, key, or ID.
        score (str): Score name, key, or ID.

    Optional args (all optimizer params):
        days (int): Feedback lookback window in days. Default 90.
        max_iterations (int): Maximum optimization cycles. Default 3.
        max_samples (int): Max feedback items per evaluation. Default 100.
        improvement_threshold (float): Min per-cycle AC1 gain. Default 0.02.
        target_accuracy (float): Stop early if AC1 reaches this. Default 0.95.
        num_candidates (int): Hypotheses per cycle. Default 3.
        optimization_objective (str): 'alignment'|'precision_safe'|'precision'|
            'recall_safe'|'recall'. Default 'alignment'.
        hint (str): Expert guidance injected into planning context.
        start_version (str): ScoreVersion UUID to start from instead of champion.
        resume_regression_eval (str): Reuse a prior regression baseline eval ID.
        resume_recent_eval (str): Reuse a prior recent baseline eval ID.
        prior_run_prescription (str): Prescription text from a prior run.
        dry_run (bool): Analyse only; never promote. Default false.
        context_window (int): Model context window in tokens. Default 180000.
        agent_models (dict): Per-agent model overrides.

    Returns dict with: procedure_id, status, message.
    """
    import os
    import yaml as yaml_lib

    from plexus.cli.procedure.service import ProcedureService
    from plexus.cli.shared.client_utils import create_client

    scorecard_identifier = args.get("scorecard") or args.get("scorecard_name") or args.get("scorecard_identifier")
    score_identifier = args.get("score") or args.get("score_name") or args.get("score_identifier")
    if not scorecard_identifier:
        raise ValueError("plexus.procedure.optimize requires 'scorecard'")
    if not score_identifier:
        raise ValueError("plexus.procedure.optimize requires 'score'")

    # Load the built-in optimizer YAML from the installed package.
    optimizer_yaml_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "plexus", "procedures", "feedback_alignment_optimizer.yaml",
    )
    optimizer_yaml_path = os.path.normpath(optimizer_yaml_path)
    if not os.path.exists(optimizer_yaml_path):
        raise FileNotFoundError(
            f"feedback_alignment_optimizer.yaml not found at {optimizer_yaml_path}"
        )
    with open(optimizer_yaml_path) as fh:
        yaml_text = fh.read()

    # Inject caller-supplied params into the YAML params block.
    OPTIMIZER_PARAMS = {
        "scorecard", "score", "days", "max_iterations", "max_samples",
        "improvement_threshold", "target_accuracy", "num_candidates",
        "optimization_objective", "hint", "start_version", "max_cost_usd",
        "resume_regression_eval", "resume_recent_eval",
        "prior_run_prescription", "dry_run", "context_window", "agent_models",
    }
    config = yaml_lib.safe_load(yaml_text)
    params_def = config.get("params", {}) if isinstance(config, dict) else {}
    for key in OPTIMIZER_PARAMS:
        val = args.get(key)
        if val is None:
            continue
        if key in params_def and isinstance(params_def[key], dict):
            params_def[key]["value"] = val
        else:
            params_def[key] = {"value": val}
    # Always inject the required scorecard/score.
    if "scorecard" in params_def and isinstance(params_def["scorecard"], dict):
        params_def["scorecard"]["value"] = str(scorecard_identifier)
    if "score" in params_def and isinstance(params_def["score"], dict):
        params_def["score"]["value"] = str(score_identifier)
    yaml_text = yaml_lib.dump(config, allow_unicode=True, default_flow_style=False)

    client = create_client()
    if not client:
        raise RuntimeError("plexus.procedure.optimize: could not create dashboard client")

    service = ProcedureService(client)
    account = os.environ.get("PLEXUS_ACCOUNT_KEY") or ""
    if not account:
        raise RuntimeError(
            "plexus.procedure.optimize: PLEXUS_ACCOUNT_KEY environment variable is required"
        )

    dispatch_mode = _resolve_report_dispatch_mode()
    result = service.create_procedure(
        account_identifier=account,
        scorecard_identifier=str(scorecard_identifier),
        score_identifier=str(score_identifier),
        yaml_config=yaml_text,
        featured=False,
        name=f"Optimizer: {scorecard_identifier}",
        dispatch_mode=dispatch_mode,
    )
    if not result.success:
        raise RuntimeError(f"plexus.procedure.optimize: failed to create procedure — {result.message}")

    procedure_id = result.procedure.id
    dashboard_url = f"https://lab.callcriteria.com/lab/procedures/{procedure_id}"

    if dispatch_mode == "celery":
        # Remote dispatch: procedure will be picked up by worker from task queue
        return {
            "procedure_id": procedure_id,
            "status": "dispatched",
            "message": "Optimizer procedure dispatched to remote worker queue.",
            "scorecard": str(scorecard_identifier),
            "score": str(score_identifier),
            "dashboard_url": dashboard_url,
        }
    else:
        # Local dispatch: launch subprocess
        import sys

        cmd = [
            sys.executable, "-m", "plexus", "procedure", "run",
            procedure_id,
        ]
        if args.get("max_iterations") is not None:
            cmd += ["--max-iterations", str(int(args["max_iterations"]))]
        if args.get("dry_run"):
            cmd.append("--dry-run")

        proc, log_path = _launch_local_procedure_subprocess(cmd, procedure_id)

        return {
            "procedure_id": procedure_id,
            "status": "running",
            "pid": proc.pid,
            "log_path": log_path,
            "message": "Optimizer procedure dispatched — running as independent subprocess.",
            "scorecard": str(scorecard_identifier),
            "score": str(score_identifier),
            "dashboard_url": dashboard_url,
        }


def _default_procedure_optimize_batch(args: dict[str, Any]) -> dict[str, Any]:
    """
    Start multiple Feedback Alignment Optimizer runs for multiple scores in parallel.

    Creates N procedures from the built-in feedback_alignment_optimizer.yaml,
    one per score, with shared parameters.

    RESOURCE CONSTRAINTS:
        - Maximum 5 scores per batch to prevent resource exhaustion
        - Each optimizer consumes ~1-2GB RAM during LLM-intensive phases
        - Concurrent optimizers can overwhelm shared infrastructure
        - For larger batches, dispatch in groups of 3-5 with delays between

    Required args:
        scorecard (str): Scorecard name, key, or ID.
        scores (list[str]): Array of score names, keys, or IDs (max 5).

    Optional args (applied to all optimizer runs):
        days (int): Feedback lookback window in days. Default 90.
        max_iterations (int): Maximum optimization cycles. Default 3.
        max_samples (int): Max feedback items per evaluation. Default 100.
        ... (all other optimizer params from _default_procedure_optimize)

    Returns dict with:
        {
            "scorecard": str,
            "total_scores": int,
            "dispatched": [
                {
                    "score": str,
                    "procedure_id": str,
                    "status": str,
                    "dashboard_url": str,
                },
                ...
            ],
            "failed": [
                {
                    "score": str,
                    "error": str,
                },
                ...
            ]
        }
    """
    MAX_BATCH_SIZE = 5

    scorecard_identifier = args.get("scorecard") or args.get("scorecard_name") or args.get("scorecard_identifier")
    scores = args.get("scores") or []

    if not scorecard_identifier:
        raise ValueError("plexus.procedure.optimize_batch requires 'scorecard'")
    if not scores or not isinstance(scores, list):
        raise ValueError("plexus.procedure.optimize_batch requires 'scores' as a non-empty array")
    if len(scores) > MAX_BATCH_SIZE:
        raise ValueError(
            f"plexus.procedure.optimize_batch: batch size {len(scores)} exceeds maximum of {MAX_BATCH_SIZE}. "
            f"Each optimizer consumes 1-2GB RAM during execution. For larger batches, dispatch multiple "
            f"smaller batches sequentially."
        )

    # Prepare shared parameters (everything except scorecard/score)
    shared_params = {k: v for k, v in args.items() if k not in ("scorecard", "scorecard_name", "scorecard_identifier", "scores", "score", "score_name", "score_identifier")}

    dispatched = []
    failed = []

    for score_identifier in scores:
        try:
            # Call the single-score optimizer with shared params
            single_args = {
                "scorecard": scorecard_identifier,
                "score": score_identifier,
                **shared_params,
            }
            result = _default_procedure_optimize(single_args)
            dispatched.append({
                "score": score_identifier,
                "procedure_id": result["procedure_id"],
                "status": result.get("status", "dispatched"),
                "dashboard_url": result.get("dashboard_url", ""),
            })
        except Exception as e:
            failed.append({
                "score": score_identifier,
                "error": str(e),
            })

    return {
        "scorecard": scorecard_identifier,
        "total_scores": len(scores),
        "dispatched": dispatched,
        "failed": failed,
    }


def _default_procedure_status_batch(args: dict[str, Any]) -> dict[str, Any]:
    """
    Check status of multiple procedures in a single call.

    Required args:
        procedure_ids (list[str]): Array of procedure IDs to check.

    Returns dict with:
        {
            "total": int,
            "procedures": [
                {
                    "id": str,
                    "status": str,
                    "scorecard_name": str,
                    "score_name": str,
                    ...
                },
                ...
            ]
        }
    """
    procedure_ids = args.get("procedure_ids") or []
    if not procedure_ids or not isinstance(procedure_ids, list):
        raise ValueError("plexus.procedure.status_batch requires 'procedure_ids' as a non-empty array")

    procedures = []
    for proc_id in procedure_ids:
        try:
            info = _default_procedure_info({"procedure_id": str(proc_id)})
            procedures.append(info)
        except Exception as e:
            procedures.append({
                "procedure_id": proc_id,
                "error": str(e),
            })

    return {
        "total": len(procedure_ids),
        "procedures": procedures,
    }


def _default_procedure_continue(args: dict[str, Any]) -> dict[str, Any]:
    """Continue a completed optimizer procedure for additional cycles.

    Required args:
        procedure_id (str): ID of the completed procedure to continue.

    Optional args:
        additional_cycles (int): Extra cycles to run. Default 3.
        hint (str): Expert guidance injected into planning context.
        target_accuracy (float): Override AC1 early-stop threshold (e.g. 1.0 to run to max).
    """
    import sys

    from plexus.cli.procedure.continuation_service import prepare_continuation
    from plexus.cli.shared.client_utils import create_client

    procedure_id = args.get("procedure_id") or args.get("id")
    if not procedure_id:
        raise ValueError("plexus.procedure.continue requires procedure_id")

    additional_cycles = int(args.get("additional_cycles") or 3)
    hint = args.get("hint") or None
    target_accuracy = args.get("target_accuracy")
    if target_accuracy is not None:
        target_accuracy = float(target_accuracy)

    client = create_client()
    if not client:
        raise RuntimeError("plexus.procedure.continue: could not create dashboard client")

    info = prepare_continuation(client, str(procedure_id), additional_cycles, hint, target_accuracy)

    cmd = [
        sys.executable, "-m", "plexus", "procedure", "run",
        str(procedure_id),
        "--max-iterations", str(info["new_max_iterations"]),
    ]
    proc, log_path = _launch_local_procedure_subprocess(cmd, str(procedure_id))

    return {
        "ok": True,
        "procedure_id": str(procedure_id),
        "status": "running",
        "pid": proc.pid,
        "log_path": log_path,
        "completed_cycles": info["completed_cycles"],
        "additional_cycles": additional_cycles,
        "new_max_iterations": info["new_max_iterations"],
        "message": (
            f"Continuation dispatched — {info['completed_cycles']} prior cycles, "
            f"running to {info['new_max_iterations']} total."
        ),
        "dashboard_url": f"https://lab.callcriteria.com/lab/procedures/{procedure_id}",
    }


def _default_procedure_branch(args: dict[str, Any]) -> dict[str, Any]:
    """Branch an optimizer procedure from a specific cycle into a new procedure.

    Required args:
        procedure_id (str): Source procedure ID.
        cycle (int): Branch from after this cycle number.

    Optional args:
        additional_cycles (int): Cycles to run in the branch. Default 3.
        hint (str): Expert guidance for the branch run.
        name (str): Name for the new branch procedure.
        target_accuracy (float): Override AC1 early-stop threshold.
    """
    import sys

    from plexus.cli.procedure.continuation_service import prepare_branch
    from plexus.cli.shared.client_utils import create_client

    source_id = args.get("procedure_id") or args.get("source_id") or args.get("id")
    if not source_id:
        raise ValueError("plexus.procedure.branch requires procedure_id")
    cycle = args.get("cycle")
    if cycle is None:
        raise ValueError("plexus.procedure.branch requires cycle")
    cycle = int(cycle)

    additional_cycles = int(args.get("additional_cycles") or 3)
    hint = args.get("hint") or None
    name = args.get("name") or None
    target_accuracy = args.get("target_accuracy")
    if target_accuracy is not None:
        target_accuracy = float(target_accuracy)

    client = create_client()
    if not client:
        raise RuntimeError("plexus.procedure.branch: could not create dashboard client")

    info = prepare_branch(client, str(source_id), cycle, additional_cycles, hint, name, target_accuracy)
    target_id = info["target_id"]

    cmd = [
        sys.executable, "-m", "plexus", "procedure", "run",
        str(target_id),
        "--max-iterations", str(info["new_max_iterations"]),
    ]
    proc, log_path = _launch_local_procedure_subprocess(cmd, str(target_id))

    return {
        "ok": True,
        "source_procedure_id": str(source_id),
        "procedure_id": str(target_id),
        "status": "running",
        "pid": proc.pid,
        "log_path": log_path,
        "branched_from_cycle": cycle,
        "additional_cycles": additional_cycles,
        "new_max_iterations": info["new_max_iterations"],
        "name": info["target_name"],
        "message": (
            f"Branch procedure {target_id} created from cycle {cycle}, "
            f"running to {info['new_max_iterations']} total cycles."
        ),
        "dashboard_url": f"https://lab.callcriteria.com/lab/procedures/{target_id}",
    }


def _plain_value(value: Any) -> Any:
    """Convert Tactus/Lupa table values into plain Python containers."""

    if isinstance(value, dict):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain_value(item) for item in value]
    items = getattr(value, "items", None)
    if callable(items):
        pairs = [(key, _plain_value(item)) for key, item in items()]
        if pairs and all(isinstance(key, int) for key, _ in pairs):
            keys = sorted(key for key, _ in pairs)
            if keys == list(range(1, len(keys) + 1)):
                by_key = dict(pairs)
                return [by_key[index] for index in keys]
        return {key: item for key, item in pairs}
    return value


def _args(value: Any = None) -> dict[str, Any]:
    if value is None:
        return {}
    converted = _plain_value(value)
    if not isinstance(converted, dict):
        raise ValueError(
            f"Expected Tactus table arguments, got {type(converted).__name__}"
        )
    return converted


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        sequence = _dict_as_lua_sequence(value)
        if sequence is not None:
            return [_jsonable(item) for item in sequence]
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    items = getattr(value, "items", None)
    if callable(items):
        try:
            pairs = list(items())
        except TypeError:
            return repr(value)
        as_dict = {key: item for key, item in pairs}
        return _jsonable(as_dict)
    return repr(value)


def _normalize_mcp_tool_args(
    namespace: str, method: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Translate runtime-friendly Tactus names to legacy MCP tool parameters."""

    normalized = dict(args)
    return normalized


def _public_handle(record: dict[str, Any]) -> dict[str, Any]:
    public = {
        "id": record["id"],
        "kind": record["kind"],
        "status": record["status"],
        "status_url": record.get("status_url"),
        "created_at": record["created_at"],
        "parent_trace_id": record["parent_trace_id"],
    }
    if record.get("child_budget") is not None:
        public["child_budget"] = record.get("child_budget")
    if record.get("dispatch_result") is not None:
        public["dispatch_result"] = record.get("dispatch_result")
    return public


TERMINAL_HANDLE_STATUSES = frozenset(
    {"completed", "completed_unknown", "failed", "cancelled"}
)


def _exited_process_status(process_id: Any) -> dict[str, Any] | None:
    try:
        pid = int(process_id)
    except (TypeError, ValueError):
        return None

    registered_process = _registered_evaluation_process(pid)
    if registered_process is not None:
        return_code = registered_process.poll()
        if return_code is None:
            return None
        _forget_evaluation_process(pid)
        return {
            "process_status": "exited",
            "process_exit_code": return_code,
        }

    try:
        waited_pid, status = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return {"process_status": "not_running", "process_exit_code": None}
        except PermissionError:
            return {"process_status": "running_unknown"}
        return None
    except ProcessLookupError:
        return {"process_status": "not_running", "process_exit_code": None}

    if waited_pid == 0:
        return None

    try:
        exit_code = os.waitstatus_to_exitcode(status)
    except ValueError:
        exit_code = None

    return {
        "process_status": "exited",
        "process_exit_status": status,
        "process_exit_code": exit_code,
    }


def _normalize_handle_status(status: Any) -> str:
    normalized = str(status or "running").strip().lower()
    status_map = {
        "complete": "completed",
        "completed": "completed",
        "failed": "failed",
        "error": "failed",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "running": "running",
        "pending": "running",
        "dispatched": "running",
    }
    return status_map.get(normalized, normalized or "running")


def _tail_text_file(path: Any, max_chars: int = 4000) -> str | None:
    if not path:
        return None
    try:
        with open(str(path), "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(size - max_chars, 0), os.SEEK_SET)
            return handle.read().decode("utf-8", errors="replace").strip()
    except OSError:
        return None


def _evaluation_process_diagnostics(
    dispatch_result: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {"error": message}
    stdout_tail = _tail_text_file(dispatch_result.get("stdout_log"))
    stderr_tail = _tail_text_file(dispatch_result.get("stderr_log"))
    if stdout_tail:
        diagnostics["stdout_tail"] = stdout_tail
    if stderr_tail:
        diagnostics["stderr_tail"] = stderr_tail
    return diagnostics


def _timeout_seconds(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, int | float):
        return max(float(value), 0.0)
    text = str(value).strip().upper()
    if not text:
        return default
    match = re.fullmatch(r"PT(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?", text)
    if match:
        minutes = float(match.group(1) or 0.0)
        seconds = float(match.group(2) or 0.0)
        return max((minutes * 60.0) + seconds, 0.0)
    return max(float(text), 0.0)


def _dict_as_lua_sequence(value: dict) -> list | None:
    """Detect string- or int-keyed dicts that represent 1-indexed Lua sequences."""

    if not value:
        return None
    indexed: list[tuple[int, Any]] = []
    for key, item in value.items():
        if isinstance(key, int):
            index = key
        elif isinstance(key, str) and key.isdigit():
            index = int(key)
        else:
            return None
        if index < 1:
            return None
        indexed.append((index, item))
    indexed.sort(key=lambda pair: pair[0])
    expected = list(range(1, len(indexed) + 1))
    if [pair[0] for pair in indexed] != expected:
        return None
    return [item for _, item in indexed]


def _extract_tool_value(result: Any) -> Any:
    def parse_json_string(value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    structured = getattr(result, "structured_content", None)
    if structured is not None:
        if (
            isinstance(structured, dict)
            and len(structured) == 1
            and "result" in structured
        ):
            value = structured["result"]
            return parse_json_string(value) if isinstance(value, str) else value
        if isinstance(structured, str):
            return parse_json_string(structured)
        return structured

    content = getattr(result, "content", None) or []
    if len(content) == 1 and hasattr(content[0], "text"):
        text = content[0].text
        return parse_json_string(text)
    return _jsonable(result)


def _structured_error(
    code: str, message: str, exc: BaseException | None = None
) -> dict[str, Any]:
    line_match = re.search(r":(\d+):", message)
    raw_lineno = int(line_match.group(1)) if line_match else None
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "type": type(exc).__name__ if exc is not None else None,
        "retryable": False,
        "traceback": None,
        "tactus_lineno": _user_tactus_lineno(raw_lineno),
    }
    if exc is not None:
        error["traceback"] = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
    return error


def _user_tactus_lineno(raw_lineno: int | None) -> int | None:
    if raw_lineno is None:
        return None
    prefix_lines = 5 + (3 * len(HELPER_BINDINGS)) + 1
    user_lineno = raw_lineno - prefix_lines
    return user_lineno if user_lineno > 0 else None


DEFAULT_BUDGET_USD = 0.25
DEFAULT_BUDGET_WALLCLOCK_SECONDS = 60.0
DEFAULT_BUDGET_DEPTH = 3
DEFAULT_BUDGET_TOOL_CALLS = 50


class BudgetExceeded(RuntimeError):
    """Raised when a Plexus runtime API call would exceed the active budget."""


class ChildBudgetRequired(ValueError):
    """Raised when async work is spawned without an explicit child budget."""


class AccountContextRequired(ValueError):
    """Raised when a runtime API needs an account but none is bound."""


_RUNTIME_API_ERROR_KEY = "__execute_tactus_runtime_error__"


def _exception_error_code(exc: BaseException) -> str:
    if isinstance(exc, AccountContextRequired):
        return "account_context_required"
    if isinstance(exc, PlanningModeToolNotAllowed):
        return "tool_not_allowed_in_planning_mode"
    if isinstance(exc, ConsoleScoreCodeUpdateRequiresSubagent):
        return "console_score_code_update_requires_subagent"
    if isinstance(exc, ConsoleGuidelinesUpdateRequiresGuidelinesIntent):
        return "console_guidelines_update_requires_guidelines_intent"
    if isinstance(exc, BudgetExceeded):
        return "budget_exceeded"
    if isinstance(exc, ChildBudgetRequired):
        return "child_budget_required"
    if isinstance(exc, RequiresHandleProtocol):
        return "requires_handle_protocol"
    if isinstance(exc, ValueError):
        return "invalid_request"
    return "runtime_api_error"


def _runtime_api_error_value(namespace: str, method: str, exc: BaseException) -> dict[str, Any]:
    api_call = f"plexus.{namespace}.{method}"
    message = str(exc) or f"{api_call} failed"
    return {
        _RUNTIME_API_ERROR_KEY: True,
        "api_call": api_call,
        "error": _structured_error(
            _exception_error_code(exc),
            f"{api_call} failed: {message}",
            exc,
        ),
    }


def _extract_runtime_api_error(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        try:
            value = _jsonable(value)
        except Exception:
            return None
    if isinstance(value, dict) and value.get(_RUNTIME_API_ERROR_KEY):
        error = value.get("error")
        return error if isinstance(error, dict) else None
    return None


def _context_account_id(context: dict[str, Any] | None) -> str | None:
    if not isinstance(context, dict):
        return None
    account_id = context.get("account_id") or context.get("accountId")
    if account_id is None:
        return None
    account_id = str(account_id).strip()
    return account_id or None


def _normalize_tool_access_mode(value: Any) -> str:
    mode = str(value or "execution").strip().lower()
    if mode in {"plan", "planning"}:
        return "planning"
    if mode in {"execute", "execution", ""}:
        return "execution"
    raise ValueError(
        "tool_access_mode must be 'planning' or 'execution'"
    )


def _merge_runtime_context_args(
    args: dict[str, Any], runtime_context: dict[str, Any] | None
) -> dict[str, Any]:
    if not isinstance(args, dict):
        args = {}
    merged = dict(args)
    if not any(merged.get(key) for key in ("account", "account_id", "accountId")):
        account_id = _context_account_id(runtime_context)
        if account_id:
            merged["account_id"] = account_id
    return merged


def _resolve_runtime_account_id(
    client: Any,
    args: dict[str, Any],
    api_name: str,
) -> str:
    account_id = args.get("account_id") or args.get("accountId")
    if account_id:
        account_id = str(account_id).strip()
        if account_id:
            if getattr(client, "context", None) is not None:
                try:
                    client.context.account_id = account_id
                except Exception as exc:
                    logger.debug(
                        "Unable to set client.context.account_id during runtime account resolution",
                        exc_info=exc,
                    )
            return account_id

    account_identifier = args.get("account")
    if account_identifier:
        from plexus.cli.report.utils import resolve_account_id_for_command

        return resolve_account_id_for_command(client, str(account_identifier))

    context = getattr(client, "context", None)
    if context is not None:
        existing_account_id = getattr(context, "account_id", None)
        if existing_account_id:
            return str(existing_account_id)
        if not getattr(context, "account_key", None):
            raise AccountContextRequired(
                f"{api_name} requires account context. Console calls must pass the "
                "triggering ChatMessage accountId into execute_tactus, or local calls "
                "must provide account/account_id or configure PLEXUS_ACCOUNT_KEY."
            )

    from plexus.cli.report.utils import resolve_account_id_for_command

    try:
        return resolve_account_id_for_command(client, None)
    except Exception as exc:
        raise AccountContextRequired(
            f"{api_name} could not resolve an account from the current runtime context. "
            "Pass account/account_id explicitly or configure PLEXUS_ACCOUNT_KEY."
        ) from exc


class BudgetSpec:
    """Conservative default budget for execute_tactus runs."""

    __slots__ = ("usd", "wallclock_seconds", "depth", "tool_calls")

    def __init__(
        self,
        *,
        usd: float = DEFAULT_BUDGET_USD,
        wallclock_seconds: float = DEFAULT_BUDGET_WALLCLOCK_SECONDS,
        depth: int = DEFAULT_BUDGET_DEPTH,
        tool_calls: int = DEFAULT_BUDGET_TOOL_CALLS,
    ) -> None:
        self.usd = float(usd)
        self.wallclock_seconds = float(wallclock_seconds)
        self.depth = int(depth)
        self.tool_calls = int(tool_calls)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BudgetSpec":
        spec = RuntimeBudgetSpec.from_dict(value)
        return cls(
            usd=spec.usd,
            wallclock_seconds=spec.wallclock_seconds,
            depth=spec.depth,
            tool_calls=spec.tool_calls,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "usd": self.usd,
            "wallclock_seconds": self.wallclock_seconds,
            "depth": self.depth,
            "tool_calls": self.tool_calls,
        }


class BudgetGate:
    """Single choke point that enforces a BudgetSpec around every Plexus runtime API call."""

    def __init__(
        self,
        spec: BudgetSpec | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.spec = spec or BudgetSpec()
        self._clock = clock or time.monotonic
        self._start = self._clock()
        self.spent_usd = 0.0
        self.tool_calls = 0
        self.reserved_wallclock_seconds = 0.0
        self.depth_max_observed = 0
        self.exceeded_reason: str | None = None
        self.child_budget_required_reason: str | None = None

    @property
    def exceeded(self) -> bool:
        return self.exceeded_reason is not None

    def elapsed_seconds(self) -> float:
        return self._clock() - self._start

    def _trip(self, reason: str) -> BudgetExceeded:
        self.exceeded_reason = reason
        return BudgetExceeded(reason)

    def check_before(
        self, namespace: str, method: str, *, estimated_usd: float = 0.0
    ) -> None:
        elapsed = self.elapsed_seconds()
        if elapsed + self.reserved_wallclock_seconds >= self.spec.wallclock_seconds:
            raise self._trip(
                f"wallclock budget exceeded before plexus.{namespace}.{method}: "
                f"{elapsed + self.reserved_wallclock_seconds:.3f}s >= "
                f"{self.spec.wallclock_seconds:.3f}s"
            )
        if self.spent_usd + estimated_usd > self.spec.usd:
            raise self._trip(
                f"USD budget exceeded before plexus.{namespace}.{method}: "
                f"${self.spent_usd + estimated_usd:.4f} > ${self.spec.usd:.4f}"
            )
        if self.tool_calls + 1 > self.spec.tool_calls:
            raise self._trip(
                f"tool_calls budget exceeded before plexus.{namespace}.{method}: "
                f"{self.tool_calls + 1} > {self.spec.tool_calls}"
            )

    def record_after(self, namespace: str, method: str, *, usd: float = 0.0) -> None:
        self.tool_calls += 1
        self.spent_usd += float(usd)

    def carve_child(
        self,
        namespace: str,
        method: str,
        budget_value: Any,
    ) -> dict[str, Any]:
        if not isinstance(budget_value, dict):
            # When the parent budget is effectively unlimited (e.g. chat embedded MCP),
            # auto-supply a generous default instead of requiring explicit budget.
            if (
                self.spec.wallclock_seconds == float("inf")
                and self.spec.usd == float("inf")
            ):
                budget_value = {
                    "usd": float("inf"),
                    "wallclock_seconds": 3600.0,
                    "depth": max(min(self.spec.depth - 1, 15), 1),
                    "tool_calls": max(self.spec.tool_calls - self.tool_calls - 1, 100),
                }
            else:
                self.child_budget_required_reason = (
                    f"plexus.{namespace}.{method} async requires explicit budget"
                )
                raise ChildBudgetRequired(self.child_budget_required_reason)
        child_spec = BudgetSpec.from_dict(budget_value)
        elapsed = self.elapsed_seconds()
        remaining_usd = max(self.spec.usd - self.spent_usd, 0.0)
        remaining_seconds = max(
            self.spec.wallclock_seconds - elapsed - self.reserved_wallclock_seconds,
            0.0,
        )
        remaining_tool_calls = max(self.spec.tool_calls - self.tool_calls - 1, 0)
        if child_spec.usd > remaining_usd:
            raise self._trip(
                f"child USD budget exceeded before plexus.{namespace}.{method}: "
                f"${child_spec.usd:.4f} > ${remaining_usd:.4f}"
            )
        if child_spec.wallclock_seconds > remaining_seconds:
            raise self._trip(
                f"child wallclock budget exceeded before plexus.{namespace}.{method}: "
                f"{child_spec.wallclock_seconds:.3f}s > {remaining_seconds:.3f}s"
            )
        if child_spec.tool_calls > remaining_tool_calls:
            raise self._trip(
                f"child tool_calls budget exceeded before plexus.{namespace}.{method}: "
                f"{child_spec.tool_calls} > {remaining_tool_calls}"
            )
        if child_spec.depth > max(self.spec.depth - 1, 0):
            raise self._trip(
                f"child depth budget exceeded before plexus.{namespace}.{method}: "
                f"{child_spec.depth} > {max(self.spec.depth - 1, 0)}"
            )
        self.spent_usd += child_spec.usd
        self.reserved_wallclock_seconds += child_spec.wallclock_seconds
        self.tool_calls += child_spec.tool_calls
        self.depth_max_observed = max(self.depth_max_observed, child_spec.depth)
        return child_spec.to_dict()


def _cost_envelope(
    api_calls: list[str],
    wallclock_seconds: float,
    *,
    budget: BudgetGate | None = None,
) -> dict[str, Any]:
    if budget is not None:
        return {
            "usd": round(budget.spent_usd, 6),
            "wallclock_seconds": wallclock_seconds,
            "tokens": 0,
            "llm_calls": 0,
            "tool_calls": budget.tool_calls,
            "workers": 0,
            "depth_max_observed": budget.depth_max_observed,
            "budget_remaining_usd": round(
                max(budget.spec.usd - budget.spent_usd, 0.0), 6
            ),
            "budget_remaining_seconds": round(
                max(
                    budget.spec.wallclock_seconds
                    - wallclock_seconds
                    - budget.reserved_wallclock_seconds,
                    0.0,
                ),
                3,
            ),
            "budget_remaining_tool_calls": max(
                budget.spec.tool_calls - budget.tool_calls, 0
            ),
        }
    return {
        "usd": 0.0,
        "wallclock_seconds": wallclock_seconds,
        "tokens": 0,
        "llm_calls": 0,
        "tool_calls": len(api_calls),
        "workers": 0,
        "depth_max_observed": 0,
        "budget_remaining_usd": DEFAULT_BUDGET_USD,
        "budget_remaining_seconds": DEFAULT_BUDGET_WALLCLOCK_SECONDS,
        "budget_remaining_tool_calls": DEFAULT_BUDGET_TOOL_CALLS,
    }


def _response_envelope(
    *,
    ok: bool,
    value: Any,
    trace_id: str,
    api_calls: list[str],
    started_at: float,
    error: dict[str, Any] | None = None,
    partial: bool = False,
    budget: BudgetGate | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "value": _jsonable(value),
        "error": error,
        "cost": _cost_envelope(api_calls, time.monotonic() - started_at, budget=budget),
        "trace_id": trace_id,
        "partial": partial,
        "api_calls": api_calls,
    }


def _run_async_from_sync(awaitable: Any) -> Any:
    """Run an async FastMCP call from synchronous Tactus host-module code."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    outcome: dict[str, Any] = {}

    def run_in_thread() -> None:
        try:
            outcome["value"] = asyncio.run(awaitable)
        except Exception as exc:  # noqa: BLE001
            outcome["error"] = exc

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()
    thread.join()
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


def _stream_event_payload(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        return _jsonable(event)
    model_dump = getattr(event, "model_dump", None)
    if callable(model_dump):
        try:
            return _jsonable(model_dump(mode="json"))
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Falling back after stream event JSON serialization failed: %s",
                exc,
            )
            try:
                return _jsonable(model_dump(mode="python"))
            except Exception:  # noqa: BLE001
                logger.debug("Falling back to stream event attributes", exc_info=True)
    if hasattr(event, "__dict__"):
        return _jsonable(vars(event))
    return {"message": str(event)}


def _stream_event_message(kind: str, payload: dict[str, Any]) -> str:
    if kind == "agent_stream_chunk":
        agent = payload.get("agent_name") or "agent"
        chunk = str(payload.get("chunk_text") or "")
        return f"{agent}: {chunk}" if chunk else f"{agent} streamed output"
    if kind == "agent_turn":
        agent = payload.get("agent_name") or "agent"
        stage = payload.get("stage") or "updated"
        return f"{agent} {stage}"
    if kind == "tool_call_started":
        tool = payload.get("tool_name") or "tool"
        agent = payload.get("agent_name") or "agent"
        return f"{agent} calling {tool}"
    if kind == "tool_call":
        tool = payload.get("tool_name") or "tool"
        agent = payload.get("agent_name") or "agent"
        return f"{agent} completed {tool}"
    if kind == "cost":
        agent = payload.get("agent_name") or "agent"
        cost = payload.get("total_cost")
        if isinstance(cost, int | float):
            return f"{agent} cost ${cost:.6f}"
        return f"{agent} cost update"
    if kind == "execution_summary":
        return "Tactus execution summary"
    return str(payload.get("message") or kind)


def _stream_event_cost(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("event_type") != "cost":
        return None
    cost_keys = (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cost",
        "completion_cost",
        "total_cost",
        "duration_ms",
    )
    return {key: payload.get(key) for key in cost_keys if key in payload}


class _MCPStreamEmitter:
    """Thread-safe bridge from Tactus runtime events to MCP progress messages."""

    supports_streaming = True

    def __init__(self, *, trace_id: str, loop: asyncio.AbstractEventLoop) -> None:
        self.trace_id = trace_id
        self._loop = loop
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._progress = 0

    def empty(self) -> bool:
        return self._queue.empty()

    async def get(self) -> dict[str, Any]:
        return await self._queue.get()

    def emit(
        self,
        *,
        kind: str,
        message: str,
        payload: dict[str, Any] | None = None,
        progress: float | None = None,
        total: float | None = None,
        cost: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "kind": kind,
            "message": message,
            "payload": _jsonable(payload or {}),
            "cost": _jsonable(cost),
            "trace_id": self.trace_id,
        }
        if progress is not None:
            event["progress"] = progress
        if total is not None:
            event["total"] = total
        self._loop.call_soon_threadsafe(self._queue.put_nowait, event)

    def log(self, event: Any) -> None:
        payload = _stream_event_payload(event)
        kind = str(payload.get("event_type") or "log")
        self.emit(
            kind=kind,
            message=_stream_event_message(kind, payload),
            payload=payload,
            cost=_stream_event_cost(payload),
        )

    def api_call(self, api_call: str) -> None:
        self._progress += 1
        self.emit(
            kind="api_call",
            message=f"Calling {api_call}",
            payload={"api_call": api_call},
            progress=self._progress,
        )


async def _maybe_await(value: Any) -> Any:
    if asyncio.iscoroutine(value):
        return await value
    return value


async def _send_mcp_stream_event(ctx: Context, event: dict[str, Any]) -> None:
    progress = event.get("progress")
    if isinstance(progress, int | float):
        try:
            await _maybe_await(
                ctx.report_progress(
                    float(progress),
                    total=event.get("total"),
                    message=str(event.get("message") or event.get("kind") or "progress"),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ignoring failed execute_tactus progress event: %s", exc)
    try:
        await _maybe_await(
            ctx.info(
                str(event.get("message") or event.get("kind") or "execute_tactus update"),
                logger_name="plexus.execute_tactus",
                extra={"event": event},
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Ignoring failed execute_tactus info event: %s", exc)


def _score_edit_format_candidates(candidates: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for candidate in candidates[:10]:
        rows.append(
            f"{candidate.get('id')} (name={candidate.get('name')!r}, "
            f"key={candidate.get('key')!r}, externalId={candidate.get('externalId')!r})"
        )
    if len(candidates) > 10:
        rows.append(f"... and {len(candidates) - 10} more")
    return "; ".join(rows)


def _score_edit_identifier_variants(identifier: Any) -> list[str]:
    """Return deterministic exact-match variants for score.edit identifiers.

    This keeps strict matching behavior while tolerating common LLM punctuation
    wrappers such as trailing periods and surrounding quotes.
    """
    raw = str(identifier or "").strip()
    if not raw:
        return []

    variants: list[str] = [raw]
    normalized = raw.strip().strip("\"'`").strip()
    normalized = normalized.rstrip(".,;:!?")
    normalized = normalized.strip()
    if normalized and normalized not in variants:
        variants.append(normalized)
    return variants


def _score_edit_canonical_identifier(value: Any) -> str:
    """Canonicalize identifiers for deterministic separator-insensitive matches."""
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _score_edit_matches_identifier(
    row: dict[str, Any], variants: list[str]
) -> bool:
    direct_values = [
        str(row.get("id") or ""),
        str(row.get("name") or ""),
        str(row.get("key") or ""),
        str(row.get("externalId") or ""),
    ]
    direct_value_set = {value for value in direct_values if value}
    canonical_value_set = {
        _score_edit_canonical_identifier(value)
        for value in direct_value_set
        if _score_edit_canonical_identifier(value)
    }

    for variant in variants:
        if variant in direct_value_set:
            return True
        canonical_variant = _score_edit_canonical_identifier(variant)
        if canonical_variant and canonical_variant in canonical_value_set:
            return True
    return False


def _score_edit_scorecard_candidates(client: Any, identifier: Any) -> list[dict[str, Any]]:
    needle = str(identifier or "").strip()
    variants = _score_edit_identifier_variants(identifier)
    if not needle:
        raise ValueError("plexus.score.edit requires scorecard_identifier")

    candidates: dict[str, dict[str, Any]] = {}

    id_query = """
    query GetScorecardById($id: ID!) {
        getScorecard(id: $id) {
            id
            name
            key
            externalId
        }
    }
    """
    for variant in variants:
        by_id = (client.execute(id_query, {"id": variant}) or {}).get("getScorecard")
        if by_id and by_id.get("id"):
            candidates[str(by_id["id"])] = {
                "id": str(by_id.get("id")),
                "name": by_id.get("name"),
                "key": by_id.get("key"),
                "externalId": by_id.get("externalId"),
            }

    list_query = """
    query ListScorecardsForExactIdentifier($limit: Int, $nextToken: String) {
        listScorecards(limit: $limit, nextToken: $nextToken) {
            items {
                id
                name
                key
                externalId
            }
            nextToken
        }
    }
    """
    next_token: Optional[str] = None
    while True:
        page = (client.execute(list_query, {"limit": 200, "nextToken": next_token}) or {}).get(
            "listScorecards", {}
        )
        items = page.get("items") or []
        for row in items:
            row_id = str(row.get("id") or "")
            if not row_id:
                continue
            if _score_edit_matches_identifier(row, variants):
                candidates[row_id] = {
                    "id": row_id,
                    "name": row.get("name"),
                    "key": row.get("key"),
                    "externalId": row.get("externalId"),
                }
        next_token = page.get("nextToken")
        if not next_token:
            break

    return list(candidates.values())


def _resolve_scorecard_for_score_edit(client: Any, identifier: Any) -> dict[str, Any]:
    needle = str(identifier or "").strip()
    resolved = _score_edit_scorecard_candidates(client, identifier)
    if not resolved:
        raise ValueError(
            "plexus.score.edit could not resolve scorecard_identifier "
            f"{needle!r}. Resolve it first with plexus.scorecards.search/info and retry."
        )
    if len(resolved) > 1:
        raise ValueError(
            "Clarification required before plexus.score.edit: scorecard_identifier is ambiguous for "
            f"{needle!r}. Reply with one exact target from candidates: "
            f"{_score_edit_format_candidates(resolved)}"
        )

    return resolved[0]


def _resolve_score_for_score_edit(
    client: Any, scorecard_id: str, score_identifier: Any
) -> dict[str, Any]:
    needle = str(score_identifier or "").strip()
    resolved = _score_edit_score_candidates(client, scorecard_id, score_identifier)
    if not resolved:
        raise ValueError(
            "plexus.score.edit could not resolve score_identifier "
            f"{needle!r} in scorecard {scorecard_id!r}. Resolve it first with "
            "plexus.score.info and retry."
        )
    if len(resolved) > 1:
        raise ValueError(
            "Clarification required before plexus.score.edit: score_identifier is ambiguous for "
            f"{needle!r} in scorecard {scorecard_id!r}. Reply with one exact target from candidates: "
            f"{_score_edit_format_candidates(resolved)}"
        )

    return resolved[0]


def _score_edit_score_candidates(
    client: Any, scorecard_id: str, score_identifier: Any
) -> list[dict[str, Any]]:
    needle = str(score_identifier or "").strip()
    variants = _score_edit_identifier_variants(score_identifier)
    if not needle:
        raise ValueError("plexus.score.edit requires score_identifier")

    candidates: dict[str, dict[str, Any]] = {}

    id_query = """
    query GetScoreByIdForEdit($id: ID!) {
        getScore(id: $id) {
            id
            name
            key
            externalId
            section {
                scorecard {
                    id
                }
            }
        }
    }
    """
    for variant in variants:
        by_id = (client.execute(id_query, {"id": variant}) or {}).get("getScore")
        if (
            by_id
            and str(by_id.get("id") or "")
            and str(((by_id.get("section") or {}).get("scorecard") or {}).get("id") or "")
            == str(scorecard_id)
        ):
            candidates[str(by_id["id"])] = {
                "id": str(by_id.get("id")),
                "name": by_id.get("name"),
                "key": by_id.get("key"),
                "externalId": by_id.get("externalId"),
            }

    section_ids_query = """
    query GetScorecardSectionIdsForEdit($id: ID!, $limit: Int, $nextToken: String) {
        getScorecard(id: $id) {
            sections(limit: $limit, nextToken: $nextToken) {
                items {
                    id
                }
                nextToken
            }
        }
    }
    """
    score_list_query = """
    query ListScoresBySectionForEdit($sectionId: String!, $limit: Int, $nextToken: String) {
        listScoreBySectionId(sectionId: $sectionId, limit: $limit, nextToken: $nextToken) {
            items {
                id
                name
                key
                externalId
            }
            nextToken
        }
    }
    """
    section_ids: list[str] = []
    seen_section_ids: set[str] = set()
    section_next_token: Optional[str] = None
    while True:
        section_page = (
            (client.execute(
                section_ids_query,
                {"id": str(scorecard_id), "limit": 200, "nextToken": section_next_token},
            ) or {})
            .get("getScorecard", {})
            .get("sections", {})
        )
        for row in section_page.get("items") or []:
            sid = str(row.get("id") or "")
            if sid and sid not in seen_section_ids:
                section_ids.append(sid)
                seen_section_ids.add(sid)
        section_next_token = section_page.get("nextToken")
        if not section_next_token:
            break

    for section_id in section_ids:
        score_next_token: Optional[str] = None
        while True:
            score_page = (client.execute(
                score_list_query,
                {
                    "sectionId": str(section_id),
                    "limit": 200,
                    "nextToken": score_next_token,
                },
            ) or {}).get("listScoreBySectionId", {})
            for row in score_page.get("items") or []:
                row_id = str(row.get("id") or "")
                if not row_id:
                    continue
                if _score_edit_matches_identifier(row, variants):
                    candidates[row_id] = {
                        "id": row_id,
                        "name": row.get("name"),
                        "key": row.get("key"),
                        "externalId": row.get("externalId"),
                    }
            score_next_token = score_page.get("nextToken")
            if not score_next_token:
                break

    return list(candidates.values())


def _default_score_resolve(args: dict[str, Any]) -> dict[str, Any]:
    """Resolve scorecard/score identifiers without mutating anything."""
    from plexus.cli.shared.client_utils import create_client

    scorecard_identifier = args.get("scorecard_identifier") or args.get("scorecard")
    score_identifier = args.get("score_identifier") or args.get("score")
    if not scorecard_identifier:
        raise ValueError("plexus.score.resolve requires scorecard_identifier")
    if not score_identifier:
        raise ValueError("plexus.score.resolve requires score_identifier")

    client = create_client()
    scorecard_candidates = _score_edit_scorecard_candidates(client, scorecard_identifier)
    if not scorecard_candidates:
        return {
            "status": "not_found",
            "target": "scorecard",
            "scorecard_identifier": scorecard_identifier,
            "score_identifier": score_identifier,
            "candidates": [],
        }
    if len(scorecard_candidates) > 1:
        return {
            "status": "ambiguous",
            "target": "scorecard",
            "scorecard_identifier": scorecard_identifier,
            "score_identifier": score_identifier,
            "candidates": scorecard_candidates,
        }

    scorecard = scorecard_candidates[0]
    score_candidates = _score_edit_score_candidates(
        client,
        str(scorecard["id"]),
        score_identifier,
    )
    if not score_candidates:
        return {
            "status": "not_found",
            "target": "score",
            "scorecard": scorecard,
            "scorecard_identifier": scorecard_identifier,
            "score_identifier": score_identifier,
            "candidates": [],
        }
    if len(score_candidates) > 1:
        return {
            "status": "ambiguous",
            "target": "score",
            "scorecard": scorecard,
            "scorecard_identifier": scorecard_identifier,
            "score_identifier": score_identifier,
            "candidates": score_candidates,
        }

    score = score_candidates[0]
    return {
        "status": "resolved",
        "scorecard": scorecard,
        "score": score,
        "scorecard_id": scorecard["id"],
        "score_id": score["id"],
        "scorecard_identifier": scorecard_identifier,
        "score_identifier": score_identifier,
    }


def _default_score_pull(args: dict[str, Any]) -> dict[str, Any]:
    """Return the champion (or specific version) YAML for a score in-memory.

    Unlike the old file-based plexus_score_pull, this returns the raw YAML
    string so Lua code can inspect or pass it directly without file I/O.
    """
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.direct_identifier_resolution import (
        direct_resolve_score_identifier,
        direct_resolve_scorecard_identifier,
    )

    scorecard_identifier = args.get("scorecard_identifier") or args.get("scorecard")
    score_identifier = args.get("score_identifier") or args.get("score")
    scorecard_id = args.get("scorecard_id")
    score_id = args.get("score_id")
    version_id = args.get("version_id") or args.get("version")
    if not scorecard_identifier and not scorecard_id:
        raise ValueError("plexus.score.pull requires scorecard_identifier")
    if not score_identifier and not score_id:
        raise ValueError("plexus.score.pull requires score_identifier")

    client = create_client()
    if not scorecard_id:
        scorecard_id = direct_resolve_scorecard_identifier(client, scorecard_identifier)
    if not scorecard_id:
        raise ValueError(f"Scorecard not found: {scorecard_identifier!r}")
    if not score_id:
        score_id = direct_resolve_score_identifier(client, scorecard_id, score_identifier)
    if not score_id:
        raise ValueError(f"Score not found: {score_identifier!r}")

    if version_id:
        query = """
        query GetScoreVersionYaml($id: ID!) {
            getScoreVersion(id: $id) {
                id
                configuration
                guidelines
                parentVersionId
                note
                createdAt
                isFeatured
            }
        }
        """
        resp = client.execute(query, {"id": version_id})
        sv = (resp or {}).get("getScoreVersion") or {}
        if not sv:
            raise ValueError(f"ScoreVersion not found: {version_id!r}")
    else:
        query = """
        query GetScoreChampion($id: ID!) {
            getScore(id: $id) {
                id
                name
                championVersionId
                championVersion {
                    id
                    configuration
                    guidelines
                    parentVersionId
                    note
                    createdAt
                    isFeatured
                }
            }
        }
        """
        resp = client.execute(query, {"id": score_id})
        score_data = (resp or {}).get("getScore") or {}
        sv = score_data.get("championVersion") or {}
        if not sv:
            raise ValueError(f"No champion version for score: {score_identifier!r}")
        version_id = sv.get("id")

    yaml_content = sv.get("configuration") or ""
    guidelines = sv.get("guidelines") or ""
    resolved_version_id = version_id or sv.get("id") or "unknown"

    # Write to temp files so sandboxed Lua code can read them via File.read()
    # without needing the io library (which is not available in Tactus sandboxes).
    import tempfile, os as _os
    code_path = _os.path.join(tempfile.gettempdir(), f"plexus_score_{resolved_version_id}.yaml")
    guide_path = _os.path.join(tempfile.gettempdir(), f"plexus_guide_{resolved_version_id}.md")
    try:
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        with open(guide_path, "w", encoding="utf-8") as f:
            f.write(guidelines)
    except OSError:
        code_path = None
        guide_path = None

    return {
        "success": True,
        "score_id": score_id,
        "scorecard_id": scorecard_id,
        "version_id": resolved_version_id,
        "yaml_content": yaml_content,
        "guidelines": guidelines,
        "parent_version_id": sv.get("parentVersionId") or "",
        "note": sv.get("note") or "",
        "created_at": sv.get("createdAt") or "",
        "is_featured": bool(sv.get("isFeatured")),
        "code_file_path": code_path,
        "guidelines_file_path": guide_path,
    }


def _default_score_update(args: dict[str, Any]) -> dict[str, Any]:
    """Update a score: create a new ScoreVersion and/or update Score metadata.

    Supports:
    - code: new YAML configuration string → creates a new ScoreVersion
    - guidelines: new guidelines text → creates a new ScoreVersion
    - description / name / key / external_id / ai_provider / ai_model: metadata-only
      updates that mutate the Score record directly (no new version needed)

    Any combination is valid. If only metadata fields are provided, no version is created.
    """
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.direct_identifier_resolution import (
        direct_resolve_score_identifier,
        direct_resolve_scorecard_identifier,
    )

    scorecard_identifier = args.get("scorecard_identifier") or args.get("scorecard")
    score_identifier = args.get("score_identifier") or args.get("score")
    code = args.get("code") or args.get("yaml_content")
    guidelines_provided = "guidelines" in args and args.get("guidelines") is not None
    guidelines = args.get("guidelines")
    parent_version_id = args.get("parent_version_id")
    version_note = args.get("version_note") or args.get("note") or "Updated via plexus.score.update"

    # Metadata fields that update the Score record (not a version)
    _META_FIELDS = ("description", "name", "key", "external_id", "ai_provider", "ai_model")
    metadata_updates = {f: args[f] for f in _META_FIELDS if f in args and args[f] is not None}

    if not scorecard_identifier:
        raise ValueError("plexus.score.update requires scorecard_identifier")
    if not score_identifier:
        raise ValueError("plexus.score.update requires score_identifier")
    if not code and not guidelines_provided and not metadata_updates:
        raise ValueError(
            "plexus.score.update requires at least one of: code, guidelines, or a metadata field "
            "(description, name, key, external_id, ai_provider, ai_model)"
        )

    client = create_client()
    scorecard_id = direct_resolve_scorecard_identifier(client, scorecard_identifier)
    if not scorecard_id:
        raise ValueError(f"Scorecard not found: {scorecard_identifier!r}")
    score_id = direct_resolve_score_identifier(client, scorecard_id, score_identifier)
    if not score_id:
        raise ValueError(f"Score not found: {score_identifier!r}")

    result: dict[str, Any] = {"success": True, "score_id": score_id, "scorecard_id": scorecard_id}

    def _load_score_version_snapshot(version_id: Any) -> dict[str, str]:
        normalized_version_id = str(version_id or "").strip()
        if not normalized_version_id:
            return {}
        query = """
        query GetScoreVersionForConsoleAudit($id: ID!) {
            getScoreVersion(id: $id) {
                id
                configuration
                guidelines
                parentVersionId
            }
        }
        """
        response = client.execute(query, {"id": normalized_version_id})
        score_version = (response or {}).get("getScoreVersion") or {}
        if not isinstance(score_version, dict):
            return {}
        return {
            "id": str(score_version.get("id") or normalized_version_id),
            "configuration": str(score_version.get("configuration") or ""),
            "guidelines": str(score_version.get("guidelines") or ""),
            "parent_version_id": str(score_version.get("parentVersionId") or ""),
        }

    # --- Metadata-only update (Score record fields) ---
    if metadata_updates:
        _FIELD_MAP = {
            "description": "description", "name": "name", "key": "key",
            "external_id": "externalId", "ai_provider": "aiProvider", "ai_model": "aiModel",
        }
        meta_input: dict[str, Any] = {"id": score_id}
        for py_field, gql_field in _FIELD_MAP.items():
            if py_field in metadata_updates:
                meta_input[gql_field] = metadata_updates[py_field]
        meta_mutation = """
        mutation UpdateScore($input: UpdateScoreInput!) {
            updateScore(input: $input) { id name description key externalId }
        }
        """
        meta_resp = client.execute(meta_mutation, {"input": meta_input})
        updated_score = (meta_resp or {}).get("updateScore") or {}
        if not updated_score.get("id"):
            return {"success": False, "error": f"updateScore returned no id: {meta_resp!r}"}
        result["metadata_updated"] = True
        result["metadata_changes"] = metadata_updates

    # --- Version update (code / guidelines) ---
    new_version_id: str | None = None
    if code or guidelines_provided:
        should_preserve_guidelines = bool(code) and not guidelines_provided and guidelines is None
        # The deployed CreateScoreVersion schema requires a configuration even
        # when the user changes only the written guidelines.  Preserve the
        # parent configuration for that storage constraint without treating it
        # as a user-requested code change in the result/diff.
        should_preserve_configuration = guidelines_provided and not code
        configuration_to_save = code
        changed_fields: list[str] = []
        if code:
            changed_fields.append("code")
        if guidelines_provided:
            changed_fields.append("guidelines")

        # Validate YAML if code provided
        if code:
            try:
                from plexus.linting.schemas import create_score_linter
                linter = create_score_linter()
                lint_result = linter.lint(code)
                if not lint_result.is_valid:
                    errors = [
                        f"{m.title}: {m.message}"
                        for m in lint_result.messages
                        if m.level == "error"
                    ]
                    return {"success": False, "error": "YAML validation failed", "validation_errors": errors}
            except ImportError:
                import yaml as _yaml
                _yaml.safe_load(code)

        # Resolve parent version
        if not parent_version_id:
            q = """
            query GetScoreChampionId($id: ID!) {
                getScore(id: $id) {
                    championVersionId
                    championVersion { guidelines }
                }
            }
            """
            resp = client.execute(q, {"id": score_id})
            score_data = (resp or {}).get("getScore") or {}
            parent_version_id = score_data.get("championVersionId")
            if should_preserve_guidelines:
                champion_version = score_data.get("championVersion") or {}
                if "guidelines" in champion_version:
                    # ``null`` is the API representation of an existing version
                    # with no written guidance.  It is still authoritative
                    # content for a code-only child: preserve it as the empty
                    # document rather than rejecting the update or inventing
                    # guidance from another source.
                    guidelines = str(champion_version.get("guidelines") or "")
                    result["guidelines_preserved"] = True
                    result["guidelines_source"] = "parent_version"
        elif should_preserve_guidelines:
            q = """
            query GetParentScoreVersionGuidelines($id: ID!) {
                getScoreVersion(id: $id) {
                    id
                    guidelines
                }
            }
            """
            resp = client.execute(q, {"id": parent_version_id})
            parent_version = (resp or {}).get("getScoreVersion") or {}
            if "guidelines" in parent_version:
                # See the champion-version path above: a null value denotes an
                # empty existing guidance document and must be carried forward
                # unchanged for a code-only candidate.
                guidelines = str(parent_version.get("guidelines") or "")
                result["guidelines_preserved"] = True
                result["guidelines_source"] = "parent_version"

        if should_preserve_guidelines and guidelines is None:
            return {
                "success": False,
                "error": "Unable to preserve guidelines for code-only score update",
                "error_code": "score_update_guidelines_preservation_failed",
                "parent_version_id": parent_version_id,
            }

        # Validate guidelines only when caller explicitly provided new guidelines.
        if guidelines_provided and guidelines is not None:
            from plexus.guidelines.validator import validate_guidelines_content

            guidelines_validation = validate_guidelines_content(str(guidelines)).to_dict()
            result["guidelines_validation"] = guidelines_validation
            if not guidelines_validation.get("is_valid"):
                return {
                    "success": False,
                    "error": "Guidelines validation failed",
                    "error_code": "guidelines_validation_failed",
                    "guidelines_validation": guidelines_validation,
                }

        parent_snapshot: dict[str, str] = {}
        if parent_version_id:
            parent_snapshot = _load_score_version_snapshot(parent_version_id)

        if should_preserve_configuration:
            preserved_configuration = parent_snapshot.get("configuration")
            if not preserved_configuration:
                return {
                    "success": False,
                    "error": "Unable to preserve configuration for guidelines-only score update",
                    "error_code": "score_update_configuration_preservation_failed",
                    "parent_version_id": parent_version_id,
                }
            configuration_to_save = preserved_configuration
            result["configuration_preserved"] = True
            result["configuration_source"] = "parent_version"

        version_mutation = """
        mutation CreateScoreVersion($input: CreateScoreVersionInput!) {
            createScoreVersion(input: $input) { id createdAt }
        }
        """
        input_obj: dict[str, Any] = {
            "scoreId": score_id,
            "note": version_note,
            "isFeatured": "false",
        }
        if configuration_to_save:
            input_obj["configuration"] = configuration_to_save
        if guidelines is not None:
            input_obj["guidelines"] = guidelines
        if parent_version_id:
            input_obj["parentVersionId"] = parent_version_id
        new_version_id = None
        version_errors: list[str] = []
        for use_attribution in (True, False):
            payload = dict(input_obj)
            if use_attribution:
                payload = apply_actor_attribution(
                    payload,
                    client_context=getattr(client, "context", None),
                    source="execute_tactus",
                )
            if isinstance(payload.get("metadata"), (dict, list)):
                payload["metadata"] = json.dumps(payload["metadata"], default=str)
            try:
                resp = client.execute(version_mutation, {"input": payload})
                new_version = (resp or {}).get("createScoreVersion") or {}
                new_version_id = new_version.get("id")
                if new_version_id:
                    result["created_at"] = new_version.get("createdAt") or ""
                    break
                version_errors.append(
                    f"attribution={use_attribution} payload={payload!r} -> missing id in response {resp!r}"
                )
            except Exception as exc:
                version_errors.append(
                    f"attribution={use_attribution} payload={payload!r} -> {exc}"
                )
        if not new_version_id:
            return {
                "success": False,
                "error": "createScoreVersion failed after compatibility attempts: "
                + " | ".join(version_errors),
            }
        result["version_id"] = new_version_id
        result["parent_version_id"] = parent_version_id
        result["version_created"] = True
        result["changed_fields"] = changed_fields
        result["version_url"] = _score_version_relative_path(
            scorecard_id=scorecard_id,
            score_id=score_id,
            version_id=new_version_id,
        )
        result["parent_version_url"] = _score_version_relative_path(
            scorecard_id=scorecard_id,
            score_id=score_id,
            version_id=parent_version_id,
        )

        try:
            candidate_snapshot = _load_score_version_snapshot(new_version_id)
            if not parent_snapshot and parent_version_id:
                parent_snapshot = _load_score_version_snapshot(parent_version_id)
            diffs = _build_score_change_diffs(
                scorecard_id=scorecard_id,
                score_id=score_id,
                parent_version_id=parent_version_id,
                version_id=new_version_id,
                changed_fields=changed_fields,
                original_code=parent_snapshot.get("configuration") or "",
                modified_code=candidate_snapshot.get("configuration") or "",
                original_guidelines=parent_snapshot.get("guidelines") or "",
                modified_guidelines=candidate_snapshot.get("guidelines") or "",
            )
            if diffs:
                result["diffs"] = diffs

            if guidelines_provided and not code:
                # A guidelines-only candidate intentionally has no behavior
                # change to smoke-test.  Still prove the safety invariant
                # after persistence: the full candidate document remains
                # syntactically valid and the stored configuration is exactly
                # the parent configuration that the adapter preserved.
                from plexus.guidelines.validator import validate_guidelines_content

                persisted_guidelines = candidate_snapshot.get("guidelines") or ""
                persisted_configuration = candidate_snapshot.get("configuration") or ""
                expected_configuration = parent_snapshot.get("configuration") or ""
                persisted_validation = validate_guidelines_content(
                    persisted_guidelines
                ).to_dict()
                configuration_unchanged = (
                    bool(expected_configuration)
                    and persisted_configuration == expected_configuration
                )
                guidelines_persisted = persisted_guidelines == str(guidelines or "")
                verification_passed = (
                    bool(persisted_validation.get("is_valid"))
                    and configuration_unchanged
                    and guidelines_persisted
                )
                result["post_submit_test"] = {
                    "status": "skipped",
                    "reason": "guidelines_only_no_behavior_change",
                }
                result["post_submit_verification"] = {
                    "status": "passed" if verification_passed else "failed",
                    "kind": "guidelines_only_persistence",
                    "guidelines_valid": bool(persisted_validation.get("is_valid")),
                    "guidelines_persisted": guidelines_persisted,
                    "configuration_unchanged": configuration_unchanged,
                }
        except Exception as diff_error:  # noqa: BLE001
            logger.warning(
                "Could not generate score.update diff payload for %s/%s: %s",
                scorecard_id,
                score_id,
                diff_error,
            )
            if guidelines_provided and not code:
                result["post_submit_test"] = {
                    "status": "skipped",
                    "reason": "guidelines_only_no_behavior_change",
                }
                result["post_submit_verification"] = {
                    "status": "failed",
                    "kind": "guidelines_only_persistence",
                    "error": str(diff_error),
                }

    result["message"] = (
        f"Score updated: version {new_version_id}" if new_version_id
        else f"Score metadata updated: {list(metadata_updates.keys())}"
    )
    return result


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
        if match:
            cleaned = match.group(1).strip()
    object_match = re.search(r"\{[\s\S]*\}", cleaned)
    if object_match:
        cleaned = object_match.group(0)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object")
    return parsed


@dataclass
class _ScoreEditAttemptError(Exception):
    error_code: str
    stage: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


def _score_edit_model_sequence(args: dict[str, Any]) -> list[str]:
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    primary = _clean(args.get("model")) or _clean(
        os.environ.get("PLEXUS_SCORE_EDIT_MODEL")
    ) or "gpt-5.3-codex"
    fallback = _clean(args.get("fallback_model")) or _clean(
        os.environ.get("PLEXUS_SCORE_EDIT_FALLBACK_MODEL")
    ) or "gpt-5.4"

    raw_max_attempts = args.get("max_attempts")
    if raw_max_attempts is None:
        raw_max_attempts = os.environ.get("PLEXUS_SCORE_EDIT_MAX_ATTEMPTS")
    try:
        max_attempts = int(raw_max_attempts) if raw_max_attempts is not None else 2
    except (TypeError, ValueError):
        max_attempts = 2
    max_attempts = max(1, min(max_attempts, 4))

    models = [primary]
    if max_attempts > 1:
        models.append(fallback or primary)
    while len(models) < max_attempts:
        models.append(models[-1])
    return models


def _score_edit_llm_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "code": {"type": "string"},
            # Responses strict JSON Schema requires every declared property in
            # `required`.  Null preserves the existing guidelines when a code
            # edit does not intentionally revise them.
            "guidelines": {"type": ["string", "null"]},
            "note": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["code", "guidelines", "note", "summary"],
    }


def _score_edit_output_token_budget(*, code: str, guidelines: str) -> int:
    """Allow a complete structured rewrite of the source score documents.

    The score editor returns the full YAML document, not a patch.  Budget from
    the serialized response shape so JSON escaping is included.  UTF-8 byte
    length is a conservative upper bound for BPE tokens; extra headroom covers
    the note, summary, and low-effort reasoning without imposing another fixed
    ceiling on valid score size.
    """
    serialized = json.dumps(
        {
            "code": code,
            "guidelines": guidelines,
            "note": "",
            "summary": "",
        },
        ensure_ascii=False,
    )
    return max(5_000, len(serialized.encode("utf-8")) + 4_096)


def _create_score_edit_response(
    *,
    client: Any,
    model: str,
    prompt: str,
    max_output_tokens: int = 5000,
) -> tuple[dict[str, Any], bool]:
    request_args: dict[str, Any] = {
        "model": model,
        "reasoning": {"effort": "low"},
        "input": [{"role": "user", "content": prompt}],
        "max_output_tokens": max_output_tokens,
    }

    try:
        structured = client.responses.create(
            **request_args,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "score_edit_payload",
                    "schema": _score_edit_llm_schema(),
                    "strict": True,
                }
            },
        )
        return _extract_json_object(getattr(structured, "output_text", "") or ""), True
    except Exception as exc:
        message = str(exc).lower()
        if not any(
            token in message
            for token in (
                "json_schema",
                "text.format",
                "response_format",
                "unknown parameter",
                "unsupported",
            )
        ):
            raise
        logger.info(
            "Structured score.edit output unavailable for model %s; using text JSON fallback: %s",
            model,
            exc,
        )

    fallback = client.responses.create(**request_args)
    return _extract_json_object(getattr(fallback, "output_text", "") or ""), False


def _validate_score_edit_payload(payload: dict[str, Any]) -> None:
    for key in ("code", "note", "summary"):
        value = payload.get(key)
        if not isinstance(value, str):
            raise ValueError(f"score.edit model payload missing string `{key}`")
    guidelines_value = payload.get("guidelines")
    if guidelines_value is not None and not isinstance(guidelines_value, str):
        raise ValueError("score.edit model payload `guidelines` must be a string when present")


def _run_score_edit_job(args: dict[str, Any], result_path: str) -> None:
    os.makedirs(os.path.dirname(result_path), exist_ok=True)
    output: dict[str, Any]
    try:
        from openai import OpenAI
        from plexus.cli.shared.client_utils import create_client
        from plexus.cli.procedure.tactus_adapters.score_editor_toolset import (
            GUIDELINES_PATH,
            ScoreEditorToolset,
            VIRTUAL_PATH,
        )

        scorecard_identifier = args.get("scorecard_identifier") or args.get("scorecard")
        score_identifier = args.get("score_identifier") or args.get("score")
        instruction = str(args.get("instruction") or "").strip()
        if not scorecard_identifier:
            raise ValueError("plexus.score.edit requires scorecard_identifier")
        if not score_identifier:
            raise ValueError("plexus.score.edit requires score_identifier")
        if not instruction:
            raise ValueError("plexus.score.edit requires instruction")

        resolved_scorecard_id = str(args.get("scorecard_id") or "").strip()
        resolved_score_id = str(args.get("score_id") or "").strip()
        if resolved_scorecard_id and resolved_score_id:
            resolved_scorecard = {"id": resolved_scorecard_id}
            resolved_score = {"id": resolved_score_id}
        else:
            resolver_client = create_client()
            resolved_scorecard = _resolve_scorecard_for_score_edit(
                resolver_client, scorecard_identifier
            )
            resolved_score = _resolve_score_for_score_edit(
                resolver_client,
                str(resolved_scorecard["id"]),
                score_identifier,
            )

        pull_args: dict[str, Any] = {
            "scorecard_id": resolved_scorecard["id"],
            "score_id": resolved_score["id"],
        }
        version_id = args.get("version_id") or args.get("version")
        if version_id:
            pull_args["version_id"] = version_id

        pull_data = _default_score_pull(pull_args)
        base_code = str(pull_data.get("yaml_content") or "")
        base_guidelines = str(pull_data.get("guidelines") or "")
        parent_version_id = str(pull_data.get("version_id") or "")

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        allow_guidelines_edit = bool(args.get("allow_guidelines_edit", False))
        prompt = (
            "You are editing a Plexus score version.\n"
            "Apply the user instruction to the score YAML.\n"
            "Return ONLY JSON with keys: code, guidelines, note, summary.\n"
            "Keep YAML valid and preserve behavior unless the instruction requires change.\n"
            + (
                "Guidelines edits are allowed only when explicitly requested.\n"
                if allow_guidelines_edit
                else "Do not change guidelines; keep them exactly as-is.\n"
            )
            + "\n"
            f"Instruction:\n{instruction}\n\n"
            f"Current YAML:\n{base_code}\n\n"
            f"Current Guidelines:\n{base_guidelines}\n"
        )
        attempts: list[dict[str, Any]] = []
        models = _score_edit_model_sequence(args)
        output = {
            "success": False,
            "error_code": "score_edit_no_attempts",
            "error": "No score edit attempts were executed.",
        }
        for attempt_index, model in enumerate(models, start=1):
            attempt: dict[str, Any] = {"attempt": attempt_index, "model": model}
            try:
                parsed, structured_output = _create_score_edit_response(
                    client=client,
                    model=model,
                    prompt=prompt,
                    max_output_tokens=_score_edit_output_token_budget(
                        code=base_code,
                        guidelines=base_guidelines,
                    ),
                )
                attempt["structured_output"] = structured_output
                _validate_score_edit_payload(parsed)
            except Exception as exc:
                attempt.update(
                    {
                        "status": "failed",
                        "stage": "model_parse",
                        "error_code": "score_edit_model_parse_failed",
                        "error": str(exc),
                    }
                )
                attempts.append(attempt)
                continue

            candidate_code = str(parsed.get("code") or base_code)
            candidate_guidelines = (
                str(parsed.get("guidelines"))
                if parsed.get("guidelines") is not None
                else base_guidelines
            )
            if not allow_guidelines_edit:
                candidate_guidelines = base_guidelines
            note = str(
                parsed.get("note") or f"Edited via plexus.score.edit: {instruction[:180]}"
            )
            summary = str(parsed.get("summary") or "")

            try:
                toolset = ScoreEditorToolset()
                setup_result = toolset.setup(
                    {
                        "scorecard_identifier": resolved_scorecard["id"],
                        "score_identifier": resolved_score["id"],
                        "yaml_content": base_code,
                        "guidelines_content": base_guidelines,
                        "parent_version_id": parent_version_id or None,
                        "hypothesis": instruction[:200],
                    }
                )
                if not setup_result.get("success"):
                    raise _ScoreEditAttemptError(
                        "score_edit_setup_failed",
                        "setup",
                        str(setup_result.get("message") or "score editor setup failed"),
                    )

                if candidate_code != base_code:
                    toolset.str_replace_editor(
                        {"command": "create", "path": VIRTUAL_PATH, "new_str": candidate_code}
                    )
                if candidate_guidelines != base_guidelines:
                    toolset.str_replace_editor(
                        {
                            "command": "create",
                            "path": GUIDELINES_PATH,
                            "new_str": candidate_guidelines,
                        }
                    )
                submit = asyncio.run(toolset.submit_score_version({"version_note": note}))
                if not submit.get("success"):
                    raise _ScoreEditAttemptError(
                        "score_edit_submit_failed",
                        "submit",
                        str(submit.get("error") or "score edit submit failed"),
                    )

                changed_fields = list(submit.get("changed_fields") or [])
                submitted_parent_version_id = str(
                    submit.get("parent_version_id") or parent_version_id or ""
                )
                version_id = str(submit.get("version_id") or "")
                attempt["version_id"] = version_id or None
                attempt["parent_version_id"] = submitted_parent_version_id or None
                attempt["changed_fields"] = changed_fields

                if not version_id:
                    raise _ScoreEditAttemptError(
                        "score_edit_missing_version_id",
                        "submit",
                        "Score edit did not return an updated score version_id",
                        details={
                            "post_submit_test": {"status": "skipped", "reason": "missing_version_id"}
                        },
                    )

                post_submit_test: dict[str, Any]
                if "code" in changed_fields:
                    raw_test = args.get("test")
                    test_config = raw_test if isinstance(raw_test, dict) else {}
                    test_args: dict[str, Any] = {
                        "scorecard_identifier": str(resolved_scorecard["id"]),
                        "score_identifier": str(resolved_score["id"]),
                        "version": version_id,
                        "samples": int(test_config.get("samples") or 3),
                        "days": int(test_config.get("days") or 90),
                    }
                    if test_config.get("item_ids") is not None:
                        test_args["item_ids"] = test_config.get("item_ids")
                    if test_config.get("fallback_scorecard_identifier") is not None:
                        test_args["fallback_scorecard_identifier"] = test_config.get(
                            "fallback_scorecard_identifier"
                        )
                    try:
                        smoke_result = _default_score_test(test_args)
                    except Exception as exc:
                        raise _ScoreEditAttemptError(
                            "score_edit_post_submit_test_failed",
                            "post_submit_test",
                            f"Post-submit score smoke test failed: {exc}",
                            details={
                                "post_submit_test": {"status": "failed", "error": str(exc)},
                            },
                        ) from exc

                    post_submit_test = {"status": "passed", "result": smoke_result}
                    # `success` means the smoke-test runner completed.  A
                    # completed run with `passed: false` still found a broken
                    # or untestable candidate and must not be reported as a
                    # successful post-submit verification.
                    if not _score_edit_smoke_test_passed(smoke_result):
                        raise _ScoreEditAttemptError(
                            "score_edit_post_submit_test_failed",
                            "post_submit_test",
                            "Post-submit score smoke test reported failure",
                            details={
                                "post_submit_test": {"status": "failed", "result": smoke_result},
                            },
                        )
                else:
                    post_submit_test = {
                        "status": "skipped",
                        "reason": "no_code_change",
                    }

                try:
                    candidate_pull = _default_score_pull(
                        {
                            "scorecard_id": resolved_scorecard["id"],
                            "score_id": resolved_score["id"],
                            "version_id": version_id,
                        }
                    )
                    persisted_code = str(candidate_pull.get("yaml_content") or "")
                    persisted_guidelines = str(candidate_pull.get("guidelines") or "")
                    actual_parent_version_id = str(
                        candidate_pull.get("parent_version_id") or ""
                    )

                    if (
                        submitted_parent_version_id
                        and actual_parent_version_id
                        and actual_parent_version_id != submitted_parent_version_id
                    ):
                        raise ValueError(
                            "Updated score version parent_version_id mismatch: "
                            f"expected {submitted_parent_version_id}, got {actual_parent_version_id}"
                        )
                    if "code" in changed_fields and persisted_code == base_code:
                        raise ValueError(
                            "Updated score version code matches parent code; expected a code change."
                        )
                    if not allow_guidelines_edit and persisted_guidelines != base_guidelines:
                        raise ValueError(
                            "Unexpected guidelines change detected in updated score version."
                        )
                except Exception as exc:
                    raise _ScoreEditAttemptError(
                        "score_edit_post_submit_verification_failed",
                        "post_submit_verification",
                        f"Post-submit score version verification failed: {exc}",
                        details={
                            "post_submit_verification": {
                                "status": "failed",
                                "error": str(exc),
                            },
                        },
                    ) from exc

                post_submit_verification = {
                    "status": "passed",
                    "expected_parent_version_id": submitted_parent_version_id or None,
                    "actual_parent_version_id": actual_parent_version_id or None,
                    "guidelines_preserved": persisted_guidelines == base_guidelines,
                }
                attempt["status"] = "succeeded"
                attempts.append(attempt)
                output = {
                    "success": True,
                    "version_id": version_id,
                    "parent_version_id": submitted_parent_version_id or None,
                    "changed_fields": changed_fields,
                    "note": note,
                    "summary": summary,
                    "scorecard_identifier": scorecard_identifier,
                    "score_identifier": score_identifier,
                    "scorecard_id": resolved_scorecard["id"],
                    "score_id": resolved_score["id"],
                    "version_url": _score_version_relative_path(
                        scorecard_id=resolved_scorecard["id"],
                        score_id=resolved_score["id"],
                        version_id=version_id,
                    ),
                    "parent_version_url": _score_version_relative_path(
                        scorecard_id=resolved_scorecard["id"],
                        score_id=resolved_score["id"],
                        version_id=submitted_parent_version_id or None,
                    ),
                    "diffs": _build_score_change_diffs(
                        scorecard_id=resolved_scorecard["id"],
                        score_id=resolved_score["id"],
                        parent_version_id=submitted_parent_version_id or None,
                        version_id=version_id,
                        changed_fields=changed_fields,
                        original_code=base_code,
                        modified_code=persisted_code,
                        original_guidelines=base_guidelines,
                        modified_guidelines=persisted_guidelines,
                    ),
                    "post_submit_test": post_submit_test,
                    "post_submit_verification": post_submit_verification,
                    "attempts": attempts,
                }
                break
            except _ScoreEditAttemptError as exc:
                attempt.update(
                    {
                        "status": "failed",
                        "stage": exc.stage,
                        "error_code": exc.error_code,
                        "error": str(exc),
                    }
                )
                details = exc.details or {}
                if isinstance(details.get("post_submit_test"), dict):
                    attempt["post_submit_test"] = details["post_submit_test"]
                if isinstance(details.get("post_submit_verification"), dict):
                    attempt["post_submit_verification"] = details[
                        "post_submit_verification"
                    ]
                attempts.append(attempt)
                output = {
                    "success": False,
                    "error": str(exc),
                    "error_code": exc.error_code,
                    "version_id": attempt.get("version_id"),
                    "parent_version_id": attempt.get("parent_version_id"),
                    "changed_fields": attempt.get("changed_fields") or [],
                    "note": note,
                    "summary": summary,
                    "scorecard_identifier": scorecard_identifier,
                    "score_identifier": score_identifier,
                    "scorecard_id": resolved_scorecard["id"],
                    "score_id": resolved_score["id"],
                    "post_submit_test": attempt.get("post_submit_test"),
                    "post_submit_verification": attempt.get("post_submit_verification"),
                    "attempts": attempts,
                }
                continue
            except Exception as exc:
                attempt.update(
                    {
                        "status": "failed",
                        "stage": "worker",
                        "error_code": "score_edit_worker_failed",
                        "error": str(exc),
                    }
                )
                attempts.append(attempt)
                output = {
                    "success": False,
                    "error": str(exc),
                    "error_code": "score_edit_worker_failed",
                    "scorecard_identifier": scorecard_identifier,
                    "score_identifier": score_identifier,
                    "scorecard_id": resolved_scorecard["id"],
                    "score_id": resolved_score["id"],
                    "attempts": attempts,
                }
                continue

        output.setdefault("attempts", attempts)
    except Exception as exc:  # noqa: BLE001
        output = {"success": False, "error": str(exc)}

    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2, sort_keys=True, default=str)


def _default_score_delete(args: dict[str, Any]) -> dict[str, Any]:
    """Delete an explicitly confirmed score by its unambiguous ID."""
    from plexus.cli.shared.client_utils import create_client

    if args.get("confirmed") is not True:
        raise ValueError(
            "plexus.score.delete is destructive and requires confirmed = true"
        )
    score_id = str(args.get("id") or args.get("score_id") or "").strip()
    if not score_id:
        raise ValueError(
            "plexus.score.delete requires the exact score id; resolve the score before deleting"
        )

    client = create_client()
    if not client:
        raise RuntimeError("plexus.score.delete: could not create dashboard client")
    mutation = """
    mutation DeleteScore($input: DeleteScoreInput!) {
      deleteScore(input: $input) { id }
    }
    """
    response = client.execute(
        mutation,
        {"input": {"id": score_id}},
    )
    deleted = (response or {}).get("deleteScore") or {}
    if not deleted.get("id"):
        raise RuntimeError("plexus.score.delete returned no score")
    return {"success": True, "id": deleted["id"]}


def _default_score_edit_runner(args: dict[str, Any]) -> dict[str, Any]:
    import tempfile

    run_dir = tempfile.mkdtemp(prefix="plexus_score_edit_")
    run_id = str(uuid.uuid4())
    result_path = os.path.join(run_dir, f"{run_id}.json")

    worker = threading.Thread(
        target=_run_score_edit_job,
        args=(dict(args), result_path),
        daemon=True,
        name=f"score-edit-{run_id[:8]}",
    )
    worker.start()

    return {
        "status": "dispatched",
        "run_id": run_id,
        "temp_dir": run_dir,
        "result_file": result_path,
        "scorecard_identifier": args.get("scorecard_identifier") or args.get("scorecard"),
        "score_identifier": args.get("score_identifier") or args.get("score"),
        "message": "Score edit dispatched in background.",
    }


def _cleanup_score_edit_artifacts(dispatch_result: dict[str, Any]) -> None:
    result_file = dispatch_result.get("result_file")
    temp_dir = dispatch_result.get("temp_dir")
    try:
        if result_file and os.path.isfile(str(result_file)):
            os.unlink(str(result_file))
    except OSError:
        logger.debug(
            "Failed to remove score edit result file during cleanup: %s",
            result_file,
            exc_info=True,
        )
    try:
        if temp_dir and os.path.isdir(str(temp_dir)):
            os.rmdir(str(temp_dir))
    except OSError:
        logger.debug(
            "Failed to remove score edit temp dir during cleanup: %s",
            temp_dir,
            exc_info=True,
        )


def _default_score_create(args: dict[str, Any]) -> dict[str, Any]:
    """Create a score under a scorecard section."""
    from plexus.attribution.actor_context import apply_actor_attribution
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.direct_identifier_resolution import (
        direct_resolve_scorecard_identifier,
    )

    def _slugify(value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower())
        return cleaned.strip("-") or "score"

    scorecard_identifier = (
        args.get("scorecard_identifier") or args.get("scorecard") or args.get("scorecard_id")
    )
    if not scorecard_identifier:
        raise ValueError("plexus.score.create requires scorecard_identifier")

    name = str(args.get("name") or "").strip()
    if not name:
        raise ValueError("plexus.score.create requires name")

    key = str(args.get("key") or "").strip() or _slugify(name)
    external_id = (
        str(args.get("external_id") or args.get("externalId") or "").strip() or key
    )
    score_type = str(args.get("score_type") or args.get("type") or "LangGraphScore").strip()
    description = args.get("description")

    try:
        order = int(args.get("order") or 1)
    except (TypeError, ValueError) as exc:
        raise ValueError("plexus.score.create order must be an integer") from exc

    client = create_client()
    if not client:
        raise RuntimeError("plexus.score.create: could not create dashboard client")

    scorecard_id = direct_resolve_scorecard_identifier(client, scorecard_identifier)
    if not scorecard_id:
        raise ValueError(f"Scorecard not found: {scorecard_identifier!r}")

    section_id = args.get("section_id") or args.get("sectionId")
    if not section_id:
        section_identifier = args.get("section_identifier") or args.get("section")
        sections_query = """
        query ListScorecardSections($scorecardId: String!, $limit: Int) {
          listScorecardSections(filter: { scorecardId: { eq: $scorecardId } }, limit: $limit) {
            items {
              id
              name
              order
            }
          }
        }
        """
        sections_resp = client.execute(sections_query, {"scorecardId": scorecard_id, "limit": 200})
        sections = (sections_resp.get("listScorecardSections") or {}).get("items") or []

        if section_identifier:
            wanted = str(section_identifier).strip().lower()
            for section in sections:
                if (
                    str(section.get("id") or "").lower() == wanted
                    or str(section.get("name") or "").strip().lower() == wanted
                ):
                    section_id = section.get("id")
                    break

        if not section_id and sections:
            section_id = sections[0].get("id")

        if not section_id:
            section_name = str(args.get("section_name") or "General").strip() or "General"
            create_section_mutation = """
            mutation CreateScorecardSection($input: CreateScorecardSectionInput!) {
              createScorecardSection(input: $input) {
                id
                name
                order
                }
            }
            """
            base_section_input = {
                "scorecardId": scorecard_id,
                "name": section_name,
                "order": 1,
            }
            section_errors: list[str] = []
            for use_attribution in (False, True):
                section_input = dict(base_section_input)
                if use_attribution:
                    section_input = apply_actor_attribution(
                        section_input,
                        client_context=getattr(client, "context", None),
                        source="execute_tactus",
                    )
                try:
                    section_resp = client.execute(
                        create_section_mutation,
                        {"input": section_input},
                    )
                    created_section = (section_resp or {}).get("createScorecardSection") or {}
                    section_id = created_section.get("id")
                    if section_id:
                        break
                    section_errors.append(
                        f"attribution={use_attribution} payload={section_input!r} -> missing id in response {section_resp!r}"
                    )
                except Exception as exc:
                    section_errors.append(
                        f"attribution={use_attribution} payload={section_input!r} -> {exc}"
                    )
            if not section_id:
                raise RuntimeError(
                    "plexus.score.create failed to create section: "
                    + " | ".join(section_errors)
                )

    score_input: dict[str, Any] = {
        "scorecardId": scorecard_id,
        "sectionId": section_id,
        "name": name,
        "key": key,
        "externalId": external_id,
        "type": score_type,
        "order": order,
    }
    if description is not None and str(description).strip():
        score_input["description"] = str(description).strip()

    create_score_mutation = """
    mutation CreateScore($input: CreateScoreInput!) {
      createScore(input: $input) {
        id
        name
        key
        externalId
        description
        type
        order
        sectionId
      }
    }
    """
    score_id = None
    created_score: dict[str, Any] = {}
    score_errors: list[str] = []
    for use_attribution in (False, True):
        payload = dict(score_input)
        if use_attribution:
            payload = apply_actor_attribution(
                payload,
                client_context=getattr(client, "context", None),
                source="execute_tactus",
            )
        try:
            score_resp = client.execute(create_score_mutation, {"input": payload})
            created_score = (score_resp or {}).get("createScore") or {}
            score_id = created_score.get("id")
            if score_id:
                break
            score_errors.append(
                f"attribution={use_attribution} payload={payload!r} -> missing id in response {score_resp!r}"
            )
        except Exception as exc:
            score_errors.append(
                f"attribution={use_attribution} payload={payload!r} -> {exc}"
            )
    if not score_id:
        raise RuntimeError(
            "plexus.score.create failed after compatibility attempts: "
            + " | ".join(score_errors)
        )

    return {
        "success": True,
        "id": score_id,
        "scorecard_id": scorecard_id,
        "section_id": created_score.get("sectionId") or section_id,
        "name": created_score.get("name"),
        "key": created_score.get("key"),
        "externalId": created_score.get("externalId"),
        "type": created_score.get("type"),
        "order": created_score.get("order"),
        "description": created_score.get("description"),
    }


def _default_score_test(args: dict[str, Any]) -> dict[str, Any]:
    """Run a mechanical smoke-test on a score version against sampled items."""
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.score_version_test import run_score_version_test

    scorecard_identifier = args.get("scorecard_identifier") or args.get("scorecard")
    score_identifier = args.get("score_identifier") or args.get("score")
    version = args.get("version")
    samples = int(args.get("samples") or 3)
    item_ids = args.get("item_ids")
    fallback_scorecard_identifier = (
        args.get("fallback_scorecard_identifier")
        or args.get("source_scorecard_identifier")
        or args.get("item_source_scorecard_identifier")
    )
    days = int(args.get("days") or 90)

    if not scorecard_identifier:
        raise ValueError("plexus.score.test requires scorecard_identifier")
    if not score_identifier:
        raise ValueError("plexus.score.test requires score_identifier")

    parsed_item_ids = None
    if item_ids:
        if isinstance(item_ids, str):
            parsed_item_ids = [v.strip() for v in item_ids.split(",") if v.strip()]
        elif isinstance(item_ids, list):
            parsed_item_ids = item_ids

    client = create_client()
    return _run_async_from_sync(
        run_score_version_test(
            client=client,
            scorecard_identifier=scorecard_identifier,
            score_identifier=score_identifier,
            version=version,
            samples=samples,
            item_identifiers=parsed_item_ids,
            fallback_scorecard_identifier=fallback_scorecard_identifier,
            days=days,
        )
    )


def _score_edit_smoke_test_passed(result: Any) -> bool:
    """Return whether a post-save mechanical score test actually passed.

    The test runner uses ``success`` for successful execution and ``passed``
    for the score-version result. Older callers returned only ``success``;
    preserve that contract while treating an explicit ``passed: false`` as a
    failed verification.
    """
    if not isinstance(result, dict) or result.get("success") is not True:
        return False
    return result.get("passed") is not False


def _default_feedback_latest_update(args: dict[str, Any]) -> dict[str, Any]:
    """Return the latest feedback updatedAt watermark for a score."""
    import asyncio
    from datetime import datetime, timedelta, timezone
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.memoized_resolvers import (
        memoized_resolve_scorecard_identifier,
        memoized_resolve_score_identifier,
    )
    from plexus.cli.report.utils import resolve_account_id_for_command

    scorecard_name = args.get("scorecard_name") or args.get("scorecard")
    score_name = args.get("score_name") or args.get("score")
    days = args.get("days")
    if not scorecard_name:
        raise ValueError("plexus.feedback.latest_update requires scorecard_name")
    if not score_name:
        raise ValueError("plexus.feedback.latest_update requires score_name")

    days_int = int(float(str(days))) if days is not None else None
    client = create_client()
    account_id = resolve_account_id_for_command(client, None)
    scorecard_id = memoized_resolve_scorecard_identifier(client, scorecard_name)
    score_id = memoized_resolve_score_identifier(client, scorecard_id, score_name)

    now = datetime.now(timezone.utc)
    window_start = (
        (now - timedelta(days=days_int))
        if days_int is not None
        else datetime(1970, 1, 1, tzinfo=timezone.utc)
    )
    window_end = now + timedelta(minutes=5)

    query = """
    query ListFeedbackUpdatesByEditedWindow(
        $accountId: String!,
        $composite_sk_condition: ModelFeedbackItemByAccountScorecardScoreEditedAtCompositeKeyConditionInput,
        $limit: Int,
        $nextToken: String,
        $sortDirection: ModelSortDirection
    ) {
        listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt(
            accountId: $accountId,
            scorecardIdScoreIdEditedAt: $composite_sk_condition,
            limit: $limit,
            nextToken: $nextToken,
            sortDirection: $sortDirection
        ) {
            items { id editedAt updatedAt isInvalid }
            nextToken
        }
    }
    """
    variables: dict[str, Any] = {
        "accountId": account_id,
        "composite_sk_condition": {
            "between": [
                {
                    "scorecardId": str(scorecard_id),
                    "scoreId": str(score_id),
                    "editedAt": window_start.isoformat(),
                },
                {
                    "scorecardId": str(scorecard_id),
                    "scoreId": str(score_id),
                    "editedAt": window_end.isoformat(),
                },
            ]
        },
        "limit": 200,
        "nextToken": None,
        "sortDirection": "DESC",
    }

    def _parse_dt(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    latest_item_id = None
    latest_updated_at: datetime | None = None

    while True:
        resp = client.execute(query, variables)
        page = (
            (resp or {}).get(
                "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt"
            )
            or {}
        )
        for row in page.get("items") or []:
            updated = _parse_dt((row or {}).get("updatedAt"))
            if updated and (latest_updated_at is None or updated > latest_updated_at):
                latest_updated_at = updated
                latest_item_id = (row or {}).get("id")
        next_token = page.get("nextToken")
        if not next_token:
            break
        variables["nextToken"] = next_token

    def _fmt(dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return dt.isoformat().replace("+00:00", "Z")

    return {
        "found": latest_updated_at is not None,
        "latest_feedback_updated_at": _fmt(latest_updated_at),
        "latest_feedback_item_id": latest_item_id,
        "window_start": _fmt(window_start),
        "window_end": _fmt(window_end),
        "scorecard_name": scorecard_name,
        "score_name": score_name,
        "scorecard_id": scorecard_id,
        "score_id": score_id,
        "days": days_int,
    }


# ---------------------------------------------------------------------------
# rubric_memory helpers
# ---------------------------------------------------------------------------

def _resolve_rubric_memory_score_id(
    client: Any, scorecard_identifier: str, score_identifier: str, score_id: str | None
) -> str:
    if score_id:
        return score_id
    from plexus.cli.shared.direct_identifier_resolution import (
        direct_resolve_score_identifier,
        direct_resolve_scorecard_identifier,
    )
    sc_id = direct_resolve_scorecard_identifier(client, scorecard_identifier)
    if not sc_id:
        raise ValueError(f"Scorecard not found: {scorecard_identifier!r}")
    resolved = direct_resolve_score_identifier(client, sc_id, score_identifier)
    if not resolved:
        raise ValueError(f"Score not found: {score_identifier!r}")
    return resolved


def _default_rubric_memory_recent_entries(args: dict[str, Any]) -> dict[str, Any]:
    """Retrieve recent rubric-memory citation context for one score."""
    import asyncio

    from plexus.cli.shared.client_utils import create_client
    from plexus.rubric_memory import RubricMemoryRecentBriefingProvider

    scorecard_identifier = args.get("scorecard_identifier") or args.get("scorecard")
    score_identifier = args.get("score_identifier") or args.get("score")
    score_id_hint = args.get("score_id")
    score_version_id = args.get("score_version_id")
    query_text = args.get("query") or ""
    days = int(args.get("days") or 30)
    since = args.get("since")
    limit = int(args.get("limit") or 16)

    if not scorecard_identifier:
        raise ValueError("plexus.rubric_memory.recent_entries requires scorecard_identifier")
    if not score_identifier:
        raise ValueError("plexus.rubric_memory.recent_entries requires score_identifier")

    client = create_client()
    resolved_score_id = _resolve_rubric_memory_score_id(
        client, scorecard_identifier, score_identifier, score_id_hint
    )

    async def _run() -> Any:
        return await RubricMemoryRecentBriefingProvider(api_client=client).retrieve_recent(
            scorecard_identifier=scorecard_identifier,
            score_identifier=score_identifier,
            score_id=resolved_score_id,
            score_version_id=score_version_id,
            query=query_text,
            days=days,
            since=since,
            limit=limit,
        )

    context = _run_async_from_sync(_run())
    return {
        "success": True,
        "score_id": resolved_score_id,
        "markdown_context": context.markdown_context,
        "citation_index": [c.model_dump(mode="json") for c in context.citation_index],
        "machine_context": context.machine_context,
        "diagnostics": context.diagnostics,
    }


def _default_rubric_memory_evidence_pack(args: dict[str, Any]) -> dict[str, Any]:
    """Generate rubric-memory citation context for a disputed score item."""
    from plexus.cli.shared.client_utils import create_client
    from plexus.rubric_memory import RubricMemoryContextProvider

    scorecard_identifier = args.get("scorecard_identifier") or args.get("scorecard")
    score_identifier = args.get("score_identifier") or args.get("score")
    score_id_hint = args.get("score_id")
    score_version_id = args.get("score_version_id")
    transcript_text = args.get("transcript_text") or ""
    model_value = args.get("model_value") or ""
    model_explanation = args.get("model_explanation") or ""
    feedback_value = args.get("feedback_value") or ""
    feedback_comment = args.get("feedback_comment") or ""
    topic_hint = args.get("topic_hint")
    synthesize = bool(args.get("synthesize", False))

    if not scorecard_identifier:
        raise ValueError("plexus.rubric_memory.evidence_pack requires scorecard_identifier")
    if not score_identifier:
        raise ValueError("plexus.rubric_memory.evidence_pack requires score_identifier")

    client = create_client()
    resolved_score_id = _resolve_rubric_memory_score_id(
        client, scorecard_identifier, score_identifier, score_id_hint
    )

    provider = RubricMemoryContextProvider(api_client=client)
    method = provider.generate_for_score_item if synthesize else provider.retrieve_for_score_item

    context = _run_async_from_sync(
        method(
            scorecard_identifier=scorecard_identifier,
            score_identifier=score_identifier,
            score_id=resolved_score_id,
            score_version_id=score_version_id,
            transcript_text=transcript_text,
            model_value=model_value,
            model_explanation=model_explanation,
            feedback_value=feedback_value,
            feedback_comment=feedback_comment,
            topic_hint=topic_hint,
        )
    )
    return {
        "success": True,
        "synthesized": synthesize,
        "score_id": resolved_score_id,
        "markdown_context": context.markdown_context,
        "citation_index": [c.model_dump(mode="json") for c in context.citation_index],
        "machine_context": context.machine_context,
        "diagnostics": context.diagnostics,
    }


def _default_rubric_memory_sme_question_gate(args: dict[str, Any]) -> dict[str, Any]:
    """Gate proposed SME agenda questions against rubric-memory citations."""
    from plexus.rubric_memory import (
        RubricMemoryCitationContext,
        RubricMemorySMEQuestionGateRequest,
        RubricMemorySMEQuestionGateService,
        candidate_agenda_items_from_markdown,
    )

    scorecard_identifier = args.get("scorecard_identifier") or args.get("scorecard")
    score_identifier = args.get("score_identifier") or args.get("score")
    score_version_id = args.get("score_version_id") or ""
    candidate_agenda_markdown = args.get("candidate_agenda_markdown") or ""
    rubric_memory_context = args.get("rubric_memory_context") or {}
    optimizer_context = args.get("optimizer_context") or ""

    if not scorecard_identifier:
        raise ValueError("plexus.rubric_memory.sme_question_gate requires scorecard_identifier")
    if not score_identifier:
        raise ValueError("plexus.rubric_memory.sme_question_gate requires score_identifier")

    if isinstance(rubric_memory_context, str):
        import json as _json
        rubric_memory_context = _json.loads(rubric_memory_context) if rubric_memory_context.strip() else {}

    context = RubricMemoryCitationContext.model_validate({
        "markdown_context": rubric_memory_context.get("markdown_context") or "",
        "citation_index": rubric_memory_context.get("citation_index") or [],
        "machine_context": rubric_memory_context.get("machine_context") or {},
        "diagnostics": rubric_memory_context.get("diagnostics") or [],
    })
    candidate_items = candidate_agenda_items_from_markdown(candidate_agenda_markdown)
    request = RubricMemorySMEQuestionGateRequest(
        scorecard_identifier=scorecard_identifier,
        score_identifier=score_identifier,
        score_version_id=score_version_id,
        rubric_memory_context=context,
        candidate_agenda_items=candidate_items,
        optimizer_context=optimizer_context,
    )
    result = _run_async_from_sync(RubricMemorySMEQuestionGateService().gate(request))
    return {"success": True, **result.model_dump(mode="json")}


class _Namespace:
    def __init__(
        self,
        dispatcher: Callable[[str, str, Any], Any],
        name: str,
        methods: set[str],
        *,
        catch_runtime_errors: bool = False,
    ) -> None:
        self._dispatcher = dispatcher
        self._name = name
        self._catch_runtime_errors = catch_runtime_errors
        for method_name in methods:
            setattr(self, method_name, self._make_call(method_name))

    def _make_call(self, method_name: str) -> Callable[[Any], Any]:
        def call(args: Any = None) -> Any:
            try:
                return self._dispatcher(self._name, method_name, args)
            except Exception as exc:
                if not self._catch_runtime_errors:
                    raise
                return _runtime_api_error_value(self._name, method_name, exc)

        return call


class PlexusRuntimeModule:
    """Tactus host module exposing curated Plexus runtime namespaces.

    All namespaces use native Python implementations (no MCP loopback).
    """

    def __init__(
        self,
        mcp: "FastMCP | None" = None,
        trace_id: str | None = None,
        docs_dir: str | None = None,
        skills_dir: str | None = None,
        budget: BudgetGate | None = None,
        handle_store: TactusHandleStore | None = None,
        scorecards_lister: Callable[[dict[str, Any]], Any] | None = None,
        scorecards_infoer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        scorecards_searcher: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        scorecards_creator: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        scorecards_updater: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        scorecards_deleter: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_create: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_searcher: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_evaluations: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_predict: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_contradictions: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_pull: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_update: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_delete: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_edit_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_test: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        score_set_champion: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        feedback_latest_update: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        rubric_memory_recent_entries: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        rubric_memory_evidence_pack: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        rubric_memory_sme_question_gate: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        item_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        item_last: Callable[[dict[str, Any]], Any] | None = None,
        procedure_listers: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
        feedback_finder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        feedback_aligner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        evaluation_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        evaluation_compare: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        evaluation_find_recent: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        evaluation_archive: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        evaluation_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        report_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        report_configurations_list: Callable[[dict[str, Any]], Any] | None = None,
        report_readers: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
        dataset_handlers: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
        procedure_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        procedure_optimize: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        procedure_archive: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        optimization_handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] | None = None,
        optimization_persister: Callable[[dict[str, Any]], Any] | None = None,
        guidelines_validator: Callable[[str], dict[str, Any]] | None = None,
        terminal_class_resolver: Callable[[str], Any] | None = None,
        review_evidence_loader: Callable[[str], dict[str, Any]] | None = None,
        stream_handler: _MCPStreamEmitter | None = None,
        runtime_context: dict[str, Any] | None = None,
        catch_runtime_errors: bool = False,
    ) -> None:
        self._mcp = mcp
        self._trace_id = trace_id or str(uuid.uuid4())
        self._docs_dir = docs_dir if docs_dir is not None else PLEXUS_DOCS_DIR
        self._skills_dir = skills_dir if skills_dir is not None else PLEXUS_SKILLS_DIR
        self._budget = budget if budget is not None else BudgetGate()
        self._shared_runtime_context = (
            runtime_context if isinstance(runtime_context, dict) else None
        )
        self._runtime_context = dict(runtime_context or {})
        self._tool_access_mode = _normalize_tool_access_mode(
            self._runtime_context.get("tool_access_mode")
        )
        self._catch_runtime_errors = catch_runtime_errors
        self._handle_store = (
            handle_store if handle_store is not None else _default_handle_store()
        )
        self._scorecards_lister = (
            scorecards_lister
            if scorecards_lister is not None
            else _default_scorecards_list
        )
        self._scorecards_infoer = (
            scorecards_infoer
            if scorecards_infoer is not None
            else _default_scorecards_info
        )
        self._scorecards_searcher = (
            scorecards_searcher
            if scorecards_searcher is not None
            else _default_scorecards_search
        )
        self._scorecards_creator = (
            scorecards_creator
            if scorecards_creator is not None
            else _default_scorecards_create
        )
        self._scorecards_updater = (
            scorecards_updater
            if scorecards_updater is not None
            else _default_scorecards_update
        )
        self._scorecards_deleter = (
            scorecards_deleter
            if scorecards_deleter is not None
            else _default_scorecards_delete
        )
        self._score_info = score_info if score_info is not None else _default_score_info
        self._score_create = (
            score_create if score_create is not None else _default_score_create
        )
        self._score_searcher = (
            score_searcher if score_searcher is not None else _default_score_search
        )
        self._score_evaluations = (
            score_evaluations if score_evaluations is not None else _default_score_evaluations
        )
        self._score_predict = score_predict if score_predict is not None else _default_score_predict
        self._score_contradictions = (
            score_contradictions if score_contradictions is not None else _default_score_contradictions
        )
        self._score_pull = score_pull if score_pull is not None else _default_score_pull
        self._score_update = score_update if score_update is not None else _default_score_update
        self._score_delete = score_delete if score_delete is not None else _default_score_delete
        self._score_edit_runner = (
            score_edit_runner if score_edit_runner is not None else _default_score_edit_runner
        )
        self._score_test = score_test if score_test is not None else _default_score_test
        self._score_set_champion = (
            score_set_champion
            if score_set_champion is not None
            else _default_score_set_champion
        )
        self._feedback_latest_update = (
            feedback_latest_update
            if feedback_latest_update is not None
            else _default_feedback_latest_update
        )
        self._rubric_memory_recent_entries = (
            rubric_memory_recent_entries
            if rubric_memory_recent_entries is not None
            else _default_rubric_memory_recent_entries
        )
        self._rubric_memory_evidence_pack = (
            rubric_memory_evidence_pack
            if rubric_memory_evidence_pack is not None
            else _default_rubric_memory_evidence_pack
        )
        self._rubric_memory_sme_question_gate = (
            rubric_memory_sme_question_gate
            if rubric_memory_sme_question_gate is not None
            else _default_rubric_memory_sme_question_gate
        )
        self._item_info = (
            item_info if item_info is not None else _default_item_info
        )
        self._item_last = (
            item_last if item_last is not None else _default_item_last
        )
        default_procedure_readers = {
            "list": _default_procedure_list,
            "info": _default_procedure_info,
            "status_batch": _default_procedure_status_batch,
            "chat_sessions": _default_procedure_chat_sessions,
            "chat_messages": _default_procedure_chat_messages,
            "steering_messages": _default_procedure_steering_messages,
        }
        if procedure_listers:
            default_procedure_readers.update(procedure_listers)
        self._procedure_readers: dict[str, Callable[[dict[str, Any]], Any]] = (
            default_procedure_readers
        )
        self._feedback_finder = (
            feedback_finder if feedback_finder is not None else _default_feedback_finder
        )
        self._feedback_aligner = (
            feedback_aligner
            if feedback_aligner is not None
            else _default_feedback_alignment
        )
        self._feedback_aligner_batch = _default_feedback_alignment_batch
        self._evaluation_info = (
            evaluation_info if evaluation_info is not None else _default_evaluation_info
        )
        self._evaluation_compare = (
            evaluation_compare
            if evaluation_compare is not None
            else _default_evaluation_compare
        )
        self._evaluation_find_recent = (
            evaluation_find_recent
            if evaluation_find_recent is not None
            else _default_evaluation_find_recent
        )
        self._evaluation_archive = (
            evaluation_archive
            if evaluation_archive is not None
            else _default_evaluation_archive
        )
        self._evaluation_runner = (
            evaluation_runner
            if evaluation_runner is not None
            else lambda args: _default_evaluation_runner(args, None)
        )
        self._report_runner = (
            report_runner if report_runner is not None else _default_report_runner
        )
        self._report_configurations_list = (
            report_configurations_list
            if report_configurations_list is not None
            else _default_report_configurations_list
        )
        default_report_readers = {
            "configurations_list": self._report_configurations_list,
            "list": _default_report_list,
            "info": _default_report_info,
            "blocks": _default_report_blocks,
        }
        if report_readers:
            default_report_readers.update(report_readers)
        self._report_readers: dict[str, Callable[[dict[str, Any]], Any]] = (
            default_report_readers
        )
        default_dataset_handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "build_from_feedback_window": _default_dataset_build_from_feedback_window,
            "check_associated": _default_dataset_check_associated,
        }
        if dataset_handlers:
            default_dataset_handlers.update(dataset_handlers)
        self._dataset_handlers = default_dataset_handlers
        self._procedure_runner = (
            procedure_runner
            if procedure_runner is not None
            else _default_procedure_runner
        )
        self._procedure_optimize = (
            procedure_optimize
            if procedure_optimize is not None
            else _default_procedure_optimize
        )
        self._procedure_optimize_batch = _default_procedure_optimize_batch
        self._procedure_archive = (
            procedure_archive
            if procedure_archive is not None
            else _default_procedure_archive
        )
        self._procedure_continue = _default_procedure_continue
        self._procedure_branch = _default_procedure_branch
        self._optimization_persister = (
            optimization_persister
            if optimization_persister is not None
            else _default_optimization_persist
        )
        self._guidelines_validator = guidelines_validator
        self._terminal_class_resolver = terminal_class_resolver
        self._review_evidence_loader = review_evidence_loader
        self._optimization_handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            method: self._default_optimization_handler(method)
            for method in ("rank", "assess", "diagnose", "run", "review", "summary")
        }
        if optimization_handlers:
            self._optimization_handlers.update(optimization_handlers)
        self._stream_handler = stream_handler
        self._api_calls: list[str] = []
        self._latest_score_versions: dict[tuple[str, str], dict[str, Any]] = {}
        self.handle_protocol_required: tuple[str, str] | None = None
        methods_by_namespace: dict[str, set[str]] = {}
        for namespace_name, method_name in MCP_TOOL_MAP.keys():
            methods_by_namespace.setdefault(namespace_name, set()).add(method_name)
        for namespace_name, method_name in DIRECT_HANDLERS.keys():
            methods_by_namespace.setdefault(namespace_name, set()).add(method_name)
        for namespace, methods in methods_by_namespace.items():
            setattr(
                self,
                namespace,
                _Namespace(
                    self._call,
                    namespace,
                    methods,
                    catch_runtime_errors=self._catch_runtime_errors,
                ),
            )
        self.docs = _Namespace(
            self._call_docs,
            "docs",
            {"list", "get"},
            catch_runtime_errors=self._catch_runtime_errors,
        )
        self.api = _Namespace(
            self._call_api,
            "api",
            {"list"},
            catch_runtime_errors=self._catch_runtime_errors,
        )

    @property
    def api_calls(self) -> list[str]:
        return list(self._api_calls)

    @property
    def budget(self) -> BudgetGate:
        return self._budget

    def _record_api_call(self, namespace: str, method: str) -> None:
        api_call = f"plexus.{namespace}.{method}"
        self._api_calls.append(api_call)
        if self._stream_handler is not None:
            self._stream_handler.api_call(api_call)

    def _score_version_cache_key(
        self, scorecard_id: Any, score_id: Any
    ) -> tuple[str, str] | None:
        if not scorecard_id or not score_id:
            return None
        return (str(scorecard_id), str(score_id))

    def _cache_latest_score_version(
        self,
        *,
        scorecard_id: Any,
        score_id: Any,
        version_id: Any,
        parent_version_id: Any = None,
        source: str,
    ) -> None:
        key = self._score_version_cache_key(scorecard_id, score_id)
        if key is None or not version_id:
            return
        self._latest_score_versions[key] = {
            "scorecard_id": key[0],
            "score_id": key[1],
            "version_id": str(version_id),
            "parent_version_id": str(parent_version_id) if parent_version_id else None,
            "source": source,
        }

    def _cached_latest_score_version(
        self, scorecard_id: Any, score_id: Any
    ) -> dict[str, Any] | None:
        key = self._score_version_cache_key(scorecard_id, score_id)
        if key is None:
            return None
        return self._latest_score_versions.get(key)

    def _resolve_score_identity_for_latest_cache(
        self,
        parsed: dict[str, Any],
        *,
        scorecard_arg_names: tuple[str, ...],
        score_arg_names: tuple[str, ...],
    ) -> tuple[str, str]:
        from plexus.cli.shared.client_utils import create_client

        scorecard_id = str(parsed.get("scorecard_id") or "").strip()
        score_id = str(parsed.get("score_id") or "").strip()
        if scorecard_id and score_id:
            return scorecard_id, score_id

        scorecard_identifier = next(
            (parsed.get(name) for name in scorecard_arg_names if parsed.get(name)),
            None,
        )
        score_identifier = next(
            (parsed.get(name) for name in score_arg_names if parsed.get(name)),
            None,
        )
        resolver_client = create_client()
        resolved_scorecard = (
            {"id": scorecard_id}
            if scorecard_id
            else _resolve_scorecard_for_score_edit(resolver_client, scorecard_identifier)
        )
        resolved_score = (
            {"id": score_id}
            if score_id
            else _resolve_score_for_score_edit(
                resolver_client,
                str(resolved_scorecard["id"]),
                score_identifier,
            )
        )
        return str(resolved_scorecard["id"]), str(resolved_score["id"])

    def _apply_latest_score_edit_start(
        self, parsed: dict[str, Any], scorecard_id: str, score_id: str
    ) -> str:
        explicit_version = parsed.get("version_id") or parsed.get("version")
        if explicit_version and str(explicit_version).strip().lower() != "latest":
            parsed["base_version_source"] = "explicit"
            return "explicit"
        if explicit_version and str(explicit_version).strip().lower() == "latest":
            parsed.pop("version", None)
            parsed.pop("version_id", None)
        elif str(parsed.get("start_version") or "").strip().lower() == "champion":
            parsed["base_version_source"] = "champion"
            return "champion"

        cached = self._cached_latest_score_version(scorecard_id, score_id)
        if cached:
            parsed["version_id"] = cached["version_id"]
            parsed["base_version_source"] = "session_latest"
            return "session_latest"
        parsed["base_version_source"] = "champion"
        return "champion"

    def _apply_latest_score_update_parent(
        self, parsed: dict[str, Any], scorecard_id: str, score_id: str
    ) -> str:
        explicit_parent = parsed.get("parent_version_id")
        explicit_version = parsed.get("version_id") or parsed.get("version")
        if explicit_parent:
            parsed["base_version_source"] = "explicit"
            return "explicit"
        if explicit_version and str(explicit_version).strip().lower() != "latest":
            parsed["parent_version_id"] = explicit_version
            parsed["base_version_source"] = "explicit"
            return "explicit"
        if explicit_version and str(explicit_version).strip().lower() == "latest":
            parsed.pop("version", None)
            parsed.pop("version_id", None)
        elif str(parsed.get("start_version") or "").strip().lower() == "champion":
            parsed["base_version_source"] = "champion"
            return "champion"

        cached = self._cached_latest_score_version(scorecard_id, score_id)
        if cached:
            parsed["parent_version_id"] = cached["version_id"]
            parsed["base_version_source"] = "session_latest"
            return "session_latest"
        parsed["base_version_source"] = "champion"
        return "champion"

    def _apply_latest_score_evaluation_version(self, parsed: dict[str, Any]) -> None:
        explicit_version = parsed.get("version")
        explicit_version_id = parsed.get("version_id") or parsed.get("score_version_id")
        version_value = explicit_version or explicit_version_id
        if version_value and str(version_value).strip().lower() != "latest":
            if explicit_version_id and not explicit_version:
                parsed["version"] = explicit_version_id
            return
        if version_value and str(version_value).strip().lower() == "latest":
            parsed.pop("version", None)
            parsed.pop("version_id", None)
            parsed.pop("score_version_id", None)

        scorecard_identifier = (
            parsed.get("scorecard_name")
            or parsed.get("scorecard_identifier")
            or parsed.get("scorecard")
            or parsed.get("scorecard_id")
        )
        score_identifier = (
            parsed.get("score_name")
            or parsed.get("score_identifier")
            or parsed.get("score")
            or parsed.get("score_id")
        )
        if not scorecard_identifier or not score_identifier:
            return
        try:
            scorecard_id, score_id = self._resolve_score_identity_for_latest_cache(
                parsed,
                scorecard_arg_names=(
                    "scorecard_id",
                    "scorecard_name",
                    "scorecard_identifier",
                    "scorecard",
                ),
                score_arg_names=(
                    "score_id",
                    "score_name",
                    "score_identifier",
                    "score",
                ),
            )
        except Exception:
            if version_value and str(version_value).strip().lower() == "latest":
                raise
            return
        cached = self._cached_latest_score_version(scorecard_id, score_id)
        if cached:
            parsed["version"] = cached["version_id"]
            parsed["scorecard_id"] = scorecard_id
            parsed["score_id"] = score_id
            parsed["base_version_source"] = "session_latest"

    def _is_console_runtime(self) -> bool:
        return any(
            key in self._runtime_context
            for key in (
                "console_tool_access_mode",
                "console_trigger_message_id",
                "chat_session_id",
            )
        )

    def _append_console_audit_event(self, event: dict[str, Any]) -> None:
        targets = [self._runtime_context]
        if isinstance(self._shared_runtime_context, dict):
            targets.append(self._shared_runtime_context)

        for target in targets:
            existing = target.get(CONSOLE_AUDIT_EVENTS_KEY)
            if isinstance(existing, list):
                existing.append(event)
            elif existing is None:
                target[CONSOLE_AUDIT_EVENTS_KEY] = [event]

    def _build_score_edit_audit_event(
        self, parsed: dict[str, Any], completed: dict[str, Any]
    ) -> dict[str, Any]:
        def _compact_step(step_value: Any) -> dict[str, Any]:
            if not isinstance(step_value, dict):
                return {"status": "unknown"}

            status = str(step_value.get("status") or "").strip().lower() or "unknown"
            compact: dict[str, Any] = {"status": status}

            for source in (step_value, step_value.get("result")):
                if not isinstance(source, dict):
                    continue
                for key in ("evaluation_id", "evaluationId"):
                    value = str(source.get(key) or "").strip()
                    if value and "evaluation_id" not in compact:
                        compact["evaluation_id"] = value
                for key in ("validation_id", "validationId"):
                    value = str(source.get(key) or "").strip()
                    if value and "validation_id" not in compact:
                        compact["validation_id"] = value
                for key in ("task_id", "taskId"):
                    value = str(source.get(key) or "").strip()
                    if value and "task_id" not in compact:
                        compact["task_id"] = value
                for key in ("run_id", "runId"):
                    value = str(source.get(key) or "").strip()
                    if value and "run_id" not in compact:
                        compact["run_id"] = value

            reason = str(step_value.get("reason") or "").strip()
            if reason:
                compact["reason"] = reason

            guidelines_preserved = step_value.get("guidelines_preserved")
            if isinstance(guidelines_preserved, bool):
                compact["guidelines_preserved"] = guidelines_preserved

            error_text = str(
                step_value.get("error") or step_value.get("message") or ""
            ).strip()
            if error_text:
                compact["error"] = error_text[:240]
            return compact

        result = completed.get("result")
        if not isinstance(result, dict):
            result = {}
        error_text = str(completed.get("error") or result.get("error") or "").strip()
        version_id = str(result.get("version_id") or "").strip()
        parent_version_id = str(result.get("parent_version_id") or "").strip()
        scorecard_id = str(result.get("scorecard_id") or parsed.get("scorecard_id") or "").strip()
        score_id = str(result.get("score_id") or parsed.get("score_id") or "").strip()
        smoke = result.get("post_submit_test")
        verification = result.get("post_submit_verification")
        attempts = result.get("attempts")
        version_url = _score_version_relative_path(
            scorecard_id=scorecard_id,
            score_id=score_id,
            version_id=version_id,
        )
        parent_version_url = _score_version_relative_path(
            scorecard_id=scorecard_id,
            score_id=score_id,
            version_id=parent_version_id,
        )
        return {
            "kind": "score_edit",
            "handle_status": str(completed.get("status") or "").strip().lower(),
            "success": bool(result.get("success", completed.get("status") == "completed")),
            "error": error_text or None,
            "version_id": version_id or None,
            "parent_version_id": parent_version_id or None,
            "scorecard_id": scorecard_id or None,
            "score_id": score_id or None,
            "version_url": version_url,
            "parent_version_url": parent_version_url,
            "changed_fields": list(result.get("changed_fields") or []),
            "diffs": _jsonable(result.get("diffs")) if isinstance(result.get("diffs"), dict) else None,
            "post_submit_test": _compact_step(smoke),
            "post_submit_verification": _compact_step(verification),
            "push_outcome": str(result.get("push_outcome") or "not_pushed"),
            "promoted": bool(result.get("promoted")),
            "error_code": str(result.get("error_code") or "").strip() or None,
            "attempts": _jsonable(attempts) if isinstance(attempts, list) else None,
            "base_version_source": str(
                result.get("base_version_source")
                or parsed.get("base_version_source")
                or ""
            ).strip()
            or None,
        }

    def _console_user_request_text(self) -> str:
        parts: list[str] = []
        latest = self._runtime_context.get("console_user_message")
        if isinstance(latest, str):
            parts.append(latest)
        history = self._runtime_context.get("console_session_history")
        if isinstance(history, list):
            for message in reversed(history):
                if not isinstance(message, dict):
                    continue
                if str(message.get("role") or "").upper() != "USER":
                    continue
                content = message.get("content")
                if isinstance(content, str):
                    parts.append(content)
                    break
        return "\n".join(part for part in parts if part).lower()

    def _console_request_allows_guidelines_update(self) -> bool:
        text = self._console_user_request_text()
        if not text:
            return False
        explicit_guidelines_markers = (
            "guideline",
            "guidelines",
            "rubric",
            "policy wording",
            "wording",
            "written rule",
            "written rules",
            "criteria document",
            "guidance text",
        )
        return any(marker in text for marker in explicit_guidelines_markers)

    def _console_request_is_guidelines_only(self) -> bool:
        text = self._console_user_request_text()
        if not self._console_request_allows_guidelines_update():
            return False
        behavior_preserving_markers = (
            "keep behavior",
            "behavior stays",
            "no behavior change",
            "keep the current behavior",
            "keep current behavior",
            # Human requests commonly describe the score's observable outcome
            # rather than calling it "behavior".  These phrases still mean
            # the instruction must never enter the code-edit workflow.
            "don't change how it scores",
            "do not change how it scores",
            "dont change how it scores",
            "don't change scoring",
            "do not change scoring",
            "dont change scoring",
            "scoring stays the same",
            "scoring should stay the same",
        )
        return any(marker in text for marker in behavior_preserving_markers)

    @staticmethod
    def _score_edit_instruction_is_candidate_only(instruction: Any) -> bool:
        """Return true for dispatch text that describes version status but no edit.

        The Console model sometimes expands a human's bare "yes" into an edit
        instruction that only says to save a non-champion candidate.  That is an
        approval boundary, not a requested behavior/code change, and dispatching
        it makes the score editor invent one.
        """
        if not isinstance(instruction, str):
            return False
        normalized = instruction.lower().strip()
        if not normalized:
            return True
        status_phrases = (
            "candidate-only",
            "candidate only",
            "do not change the champion",
            "don't change the champion",
            "do not change champion",
            "don't change champion",
            "do not promote",
            "keep it non-champion",
        )
        if not any(phrase in normalized for phrase in status_phrases):
            return False
        for phrase in status_phrases:
            normalized = normalized.replace(phrase, " ")
        normalized = re.sub(r"[^a-z]+", " ", normalized).strip()
        return normalized in {"", "make this score", "make it", "do it", "save it"}

    def _enforce_console_score_update_policy(self, parsed: dict[str, Any]) -> None:
        if not self._is_console_runtime():
            return
        if parsed.get("code") or parsed.get("yaml_content"):
            raise ConsoleScoreCodeUpdateRequiresSubagent()
        if parsed.get("guidelines") is not None and not self._console_request_allows_guidelines_update():
            raise ConsoleGuidelinesUpdateRequiresGuidelinesIntent()

    def _enforce_tool_access(self, namespace: str, method: str) -> None:
        if self._tool_access_mode != "planning":
            return
        spec = RUNTIME_METHOD_SPECS.get((namespace, method))
        if spec is not None and spec.planning_allowed:
            return
        raise PlanningModeToolNotAllowed(namespace, method)

    def _call(self, namespace: str, method: str, args: Any = None) -> Any:
        self._enforce_tool_access(namespace, method)
        direct_handler = DIRECT_HANDLERS.get((namespace, method))
        if direct_handler is not None:
            return getattr(self, direct_handler)(namespace, method, args)
        tool_name = MCP_TOOL_MAP.get((namespace, method))
        if tool_name is None:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        if (namespace, method) in LONG_RUNNING_METHODS:
            self._record_api_call(namespace, method)
            self.handle_protocol_required = (namespace, method)
            raise RequiresHandleProtocol(namespace, method)
        self._budget.check_before(namespace, method)
        self._record_api_call(namespace, method)
        try:
            result = _run_async_from_sync(
                self._mcp.call_tool(
                    tool_name,
                    _normalize_mcp_tool_args(namespace, method, _args(args)),
                )
            )
        finally:
            self._budget.record_after(namespace, method)
        return _extract_tool_value(result)

    def _call_score(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "score" or method not in {
            "info",
            "create",
            "search",
            "evaluations",
            "predict",
            "contradictions",
            "pull",
            "resolve",
            "update",
            "delete",
            "edit",
            "test",
            "set_champion",
        }:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("score", method)
        self._record_api_call("score", method)
        try:
            parsed = _merge_runtime_context_args(_args(args), self._runtime_context)
            if method == "info":
                return self._score_info(parsed)
            if method == "create":
                return self._score_create(parsed)
            if method == "search":
                return self._score_searcher(parsed)
            if method == "evaluations":
                return self._score_evaluations(parsed)
            if method == "predict":
                return self._score_predict(parsed)
            if method == "contradictions":
                return self._score_contradictions(parsed)
            if method == "pull":
                return self._score_pull(parsed)
            if method == "resolve":
                return _default_score_resolve(parsed)
            if method == "update":
                self._enforce_console_score_update_policy(parsed)
                creates_version = bool(
                    parsed.get("code")
                    or parsed.get("yaml_content")
                    or parsed.get("guidelines") is not None
                )
                scorecard_id: str | None = None
                score_id: str | None = None
                if creates_version:
                    scorecard_id, score_id = self._resolve_score_identity_for_latest_cache(
                        parsed,
                        scorecard_arg_names=(
                            "scorecard_id",
                            "scorecard_identifier",
                            "scorecard",
                        ),
                        score_arg_names=("score_id", "score_identifier", "score"),
                    )
                    parsed["scorecard_id"] = scorecard_id
                    parsed["score_id"] = score_id
                    self._apply_latest_score_update_parent(parsed, scorecard_id, score_id)
                result = self._score_update(parsed)
                if (
                    creates_version
                    and isinstance(result, dict)
                    and result.get("success")
                    and result.get("version_id")
                ):
                    result.setdefault("scorecard_id", scorecard_id)
                    result.setdefault("score_id", score_id)
                    result.setdefault("parent_version_id", parsed.get("parent_version_id"))
                    result.setdefault(
                        "changed_fields",
                        [
                            field
                            for field in ("code", "guidelines")
                            if (
                                (field == "code" and bool(parsed.get("code") or parsed.get("yaml_content")))
                                or (field == "guidelines" and parsed.get("guidelines") is not None)
                            )
                        ],
                    )
                    result.setdefault(
                        "version_url",
                        _score_version_relative_path(
                            scorecard_id=result.get("scorecard_id"),
                            score_id=result.get("score_id"),
                            version_id=result.get("version_id"),
                        ),
                    )
                    result.setdefault(
                        "parent_version_url",
                        _score_version_relative_path(
                            scorecard_id=result.get("scorecard_id"),
                            score_id=result.get("score_id"),
                            version_id=result.get("parent_version_id"),
                        ),
                    )
                    result.setdefault("promoted", False)
                    result.setdefault("push_outcome", "not_pushed")
                    result.setdefault("base_version_source", parsed.get("base_version_source"))
                    self._cache_latest_score_version(
                        scorecard_id=result.get("scorecard_id"),
                        score_id=result.get("score_id"),
                        version_id=result.get("version_id"),
                        parent_version_id=result.get("parent_version_id"),
                        source="score.update",
                    )
                    score_edit_audit_event = self._build_score_edit_audit_event(
                        parsed,
                        {"status": "completed", "result": result},
                    )
                    result[SCORE_EDIT_AUDIT_EVENT_KEY] = _compact_score_edit_audit_event(
                        score_edit_audit_event
                    )
                    self._append_console_audit_event(score_edit_audit_event)
                return result
            if method == "delete":
                if parsed.get("confirmed") is not True:
                    raise ValueError(
                        "plexus.score.delete is destructive and requires confirmed = true"
                    )
                return self._score_delete(parsed)
            if method == "edit":
                if self._is_console_runtime() and self._console_request_is_guidelines_only():
                    raise ConsoleScoreEditBlockedForGuidelinesOnly()
                if (
                    self._is_console_runtime()
                    and self._score_edit_instruction_is_candidate_only(parsed.get("instruction"))
                ):
                    raise ConsoleScoreEditRequiresConcreteInstruction()
                if not bool(parsed.get("async")):
                    self.handle_protocol_required = ("score", "edit")
                    raise RequiresHandleProtocol("score", "edit")
                # Hard orchestration gate: resolve targets before dispatch so
                # ambiguous/non-resolved identifiers fail deterministically.
                from plexus.cli.shared.client_utils import create_client

                scorecard_identifier = parsed.get("scorecard_identifier") or parsed.get("scorecard")
                score_identifier = parsed.get("score_identifier") or parsed.get("score")
                resolver_client = create_client()
                resolved_scorecard = _resolve_scorecard_for_score_edit(
                    resolver_client, scorecard_identifier
                )
                resolved_score = _resolve_score_for_score_edit(
                    resolver_client,
                    str(resolved_scorecard["id"]),
                    score_identifier,
                )
                parsed["scorecard_id"] = str(resolved_scorecard["id"])
                parsed["score_id"] = str(resolved_score["id"])
                self._apply_latest_score_edit_start(
                    parsed,
                    str(resolved_scorecard["id"]),
                    str(resolved_score["id"]),
                )
                child_budget = self._budget.carve_child("score", "edit", parsed.get("budget"))
                dispatch_result = self._score_edit_runner(parsed)
                handle = self._handle_store.create(
                    kind="score_edit",
                    parent_trace_id=self._trace_id,
                    api_call="plexus.score.edit",
                    args=parsed,
                    dispatch_result=dispatch_result,
                    child_budget=child_budget,
                )
                await_timeout = (
                    parsed.get("await_timeout")
                    or parsed.get("timeout")
                    or "PT10M"
                )
                await_args: dict[str, Any] = {
                    "id": handle["id"],
                    "timeout": await_timeout,
                }
                await_poll = parsed.get("await_poll_interval") or parsed.get(
                    "poll_interval"
                )
                if await_poll is not None:
                    await_args["poll_interval"] = await_poll
                completed = self._call_handle("handle", "await", await_args)
                if isinstance(completed, dict) and completed.get("status") == "completed":
                    result = completed.get("result") or {}
                    if isinstance(result, dict) and result.get("version_id"):
                        result.setdefault("scorecard_id", parsed.get("scorecard_id"))
                        result.setdefault("score_id", parsed.get("score_id"))
                        result.setdefault(
                            "version_url",
                            _score_version_relative_path(
                                scorecard_id=result.get("scorecard_id"),
                                score_id=result.get("score_id"),
                                version_id=result.get("version_id"),
                            ),
                        )
                        result.setdefault(
                            "parent_version_url",
                            _score_version_relative_path(
                                scorecard_id=result.get("scorecard_id"),
                                score_id=result.get("score_id"),
                                version_id=result.get("parent_version_id"),
                            ),
                        )
                        result.setdefault("promoted", False)
                        result.setdefault("push_outcome", "not_pushed")
                        result.setdefault("base_version_source", parsed.get("base_version_source"))
                        self._cache_latest_score_version(
                            scorecard_id=result.get("scorecard_id"),
                            score_id=result.get("score_id"),
                            version_id=result.get("version_id"),
                            parent_version_id=result.get("parent_version_id"),
                            source="score.edit",
                        )
                if isinstance(completed, dict):
                    score_edit_audit_event = self._build_score_edit_audit_event(
                        parsed, completed
                    )
                    completed[SCORE_EDIT_AUDIT_EVENT_KEY] = _compact_score_edit_audit_event(
                        score_edit_audit_event
                    )
                    self._append_console_audit_event(score_edit_audit_event)
                return completed
            if method == "test":
                return self._score_test(parsed)
            if method == "set_champion":
                return self._score_set_champion(parsed)
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        finally:
            self._budget.record_after("score", method)

    def _call_item(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "item" or method not in {"info", "last"}:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("item", method)
        self._record_api_call("item", method)
        try:
            parsed = _merge_runtime_context_args(_args(args), self._runtime_context)
            if method == "info":
                return self._item_info(parsed)
            return self._item_last(parsed)
        finally:
            self._budget.record_after("item", method)

    def _call_procedure_read(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if namespace != "procedure" or method not in self._procedure_readers:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("procedure", method)
        self._record_api_call("procedure", method)
        try:
            parsed = _merge_runtime_context_args(_args(args), self._runtime_context)
            return self._procedure_readers[method](parsed)
        finally:
            self._budget.record_after("procedure", method)

    def _call_procedure_write(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if (namespace, method) != ("procedure", "archive"):
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("procedure", method)
        self._record_api_call("procedure", method)
        try:
            parsed = _merge_runtime_context_args(_args(args), self._runtime_context)
            return self._procedure_archive(parsed)
        finally:
            self._budget.record_after("procedure", method)

    def _call_scorecards(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "scorecards" or method not in {
            "list", "info", "search", "create", "update", "delete"
        }:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("scorecards", method)
        self._record_api_call("scorecards", method)
        try:
            parsed = _merge_runtime_context_args(_args(args), self._runtime_context)
            if method == "list":
                return self._scorecards_lister(parsed)
            if method == "create":
                return self._scorecards_creator(parsed)
            if method == "update":
                return self._scorecards_updater(parsed)
            if method == "delete":
                if parsed.get("confirmed") is not True:
                    raise ValueError(
                        "plexus.scorecards.delete is destructive and requires confirmed = true"
                    )
                return self._scorecards_deleter(parsed)
            if method == "search":
                return self._scorecards_searcher(parsed)
            return self._scorecards_infoer(parsed)
        finally:
            self._budget.record_after("scorecards", method)

    def _call_feedback(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "feedback" or method not in {"find", "alignment", "alignment_batch", "latest_update"}:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("feedback", method)
        self._record_api_call("feedback", method)
        try:
            parsed = _merge_runtime_context_args(_args(args), self._runtime_context)
            if method == "find":
                return self._feedback_finder(parsed)
            if method == "latest_update":
                return self._feedback_latest_update(parsed)
            if method == "alignment_batch":
                return self._feedback_aligner_batch(parsed)
            return self._feedback_aligner(parsed)
        finally:
            self._budget.record_after("feedback", method)

    def _optimization_dependencies(self) -> dict[str, Any]:
        """Capabilities supplied to the shared optimization decision service.

        Keeping these adapters here lets the service reuse the canonical
        score/feedback/report/procedure paths without importing the Tactus
        runtime or duplicating any network-facing implementation.
        """
        return {
            "scorecards_list": self._scorecards_lister,
            "score_info": self._score_info,
            "feedback_alignment": self._feedback_aligner,
            "feedback_alignment_batch": self._feedback_aligner_batch,
            "feedback_latest_update": self._feedback_latest_update,
            "score_contradictions": self._score_contradictions,
            "rubric_memory_recent_entries": self._rubric_memory_recent_entries,
            "rubric_memory_evidence_pack": self._rubric_memory_evidence_pack,
            "rubric_memory_sme_question_gate": self._rubric_memory_sme_question_gate,
            "report_info": self._report_readers.get("info"),
            "report_blocks": self._report_readers.get("blocks"),
            "procedure_info": self._procedure_readers.get("info"),
            "procedure_optimize": self._procedure_optimize,
            # Persistence is deliberately injected.  There is no inline
            # ReportBlock/DynamoDB fallback in the runtime.
            "persist_packet": self._optimization_persister,
        }

    def _rank_payload_from_runtime(self, args: dict[str, Any]) -> dict[str, Any]:
        """Collect a frozen, optionally scorecard-scoped input for `optimization.rank`.

        Pagination belongs to this transport adapter because it is the layer
        that owns the scorecard list API.  Each cursor is retried exactly once;
        a failed page is retained as coverage evidence, never turned into a
        sampled/exact portfolio claim.
        """
        from datetime import datetime, timezone

        as_of_datetime = datetime.now(timezone.utc).replace(microsecond=0)
        as_of = as_of_datetime.isoformat().replace("+00:00", "Z")
        cards: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        next_token: Any = None
        pages = 0
        while True:
            page_args = {
                "return_metadata": True,
                "_include_scores": True,
                "next_token": next_token,
                "account_id": args.get("account_id"),
                "as_of": as_of,
            }
            page: Any = None
            for attempt in range(2):
                try:
                    page = self._scorecards_lister(page_args)
                    break
                except Exception as exc:  # noqa: BLE001 - preserve coverage evidence
                    if attempt:
                        failures.append({"page": pages + 1, "error": str(exc)})
            if page is None:
                break
            pages += 1
            if isinstance(page, dict):
                items = page.get("items") or []
                next_token = page.get("nextToken") or page.get("next_token")
            else:
                items, next_token = page, None
            cards.extend(item for item in items if isinstance(item, dict))
            if not next_token:
                break

        coverage: dict[str, Any] = {
            "complete": not failures,
            "pages_completed": pages,
            "failures": failures,
            "scorecards_discovered": len(cards),
        }
        from plexus.optimization.decision import (
            evaluate_score_activity,
            frozen_utc_window,
            normalize_rank_scope,
            rank_scope_matches,
        )

        scope = normalize_rank_scope(args)
        requested_ids = list(args.get("scorecard_ids", scope.get("scorecard_ids", ())))
        requested_prefixes = list(
            args.get(
                "scorecard_name_prefixes",
                scope.get("scorecard_name_prefixes", ()),
            )
        )
        matched_ids: list[str] = []
        selected_cards: list[dict[str, Any]] = []
        for card in cards:
            card_id = card.get("id")
            if not isinstance(card_id, str) or not card_id:
                continue
            if card_id in matched_ids:
                continue
            if not rank_scope_matches(card_id, card.get("name"), scope):
                continue
            matched_ids.append(card_id)
            selected_cards.append(card)

        discovered_ids = {
            card.get("id")
            for card in cards
            if isinstance(card.get("id"), str) and card.get("id")
        }
        unmatched_ids = [card_id for card_id in requested_ids if card_id not in discovered_ids]
        unmatched_prefixes = [
            prefix
            for prefix in requested_prefixes
            if not any(
                isinstance(card.get("name"), str)
                and card["name"].casefold().startswith(prefix.casefold())
                for card in cards
            )
        ]
        scope_evidence = {
            "requested_scorecard_ids": requested_ids,
            "requested_scorecard_name_prefixes": requested_prefixes,
            "matched_scorecard_ids": matched_ids,
            "matched_scorecard_count": len(matched_ids),
            "unmatched_scorecard_ids": unmatched_ids,
            "unmatched_scorecard_name_prefixes": unmatched_prefixes,
            "total_scorecards_inspected": len(cards),
        }
        coverage["scope"] = scope_evidence
        coverage["activity"] = {
            "policy_version": "score-activity-cooldown-v1",
            "as_of": as_of,
            "complete": True,
        }
        window = frozen_utc_window(now=as_of_datetime, complete_days=90)
        base_payload = {
            "scores": [],
            "coverage": coverage,
            "window": window,
            "scope": scope,
        }
        # Complete enumeration is a prerequisite for scoped analysis.  A
        # partial collection cannot prove either inclusion or exclusion.
        if failures or not matched_ids:
            return base_payload

        try:
            alignment = self._feedback_aligner_batch({
                "scorecards": matched_ids,
                "days": 90,
                "window_start": window["start"],
                "window_end": window["end"],
                "account_id": args.get("account_id"),
                "as_of": as_of,
            })
        except Exception as exc:  # noqa: BLE001 - partial is observable, never exact
            coverage["complete"] = False
            coverage["failures"].append({"stage": "feedback_alignment", "error": str(exc)})
            return base_payload

        downstream_coverage = alignment.get("coverage") if isinstance(alignment, dict) else None
        expected_targets = len(matched_ids)
        if not isinstance(downstream_coverage, dict):
            coverage["complete"] = False
            coverage["failures"].append({
                "stage": "feedback_alignment",
                "error": "missing analysis coverage evidence",
            })
        else:
            reported_targets = downstream_coverage.get("target_count")
            completed_targets = downstream_coverage.get("completed_count")
            if downstream_coverage.get("complete") is not True:
                coverage["complete"] = False
                coverage["failures"].extend(
                    downstream_coverage.get("failures")
                    or [{"stage": "feedback_alignment", "error": "incomplete"}]
                )
            # Exact portfolio rankings require the analysis batch to attest to
            # the same target set discovered by exhaustive pagination.  A
            # truthy `complete` flag alone cannot prove that it analyzed every
            # discovered scorecard.
            if reported_targets != expected_targets or completed_targets != expected_targets:
                coverage["complete"] = False
                coverage["failures"].append({
                    "stage": "feedback_alignment",
                    "error": "analysis coverage does not match discovered scope",
                    "discovered_target_count": expected_targets,
                    "reported_target_count": reported_targets,
                    "reported_completed_count": completed_targets,
                })
        inventory_scores: dict[tuple[str, str], dict[str, Any]] = {}
        scorecards_with_inventory_scores: set[str] = set()
        for card in selected_cards:
            card_id = str(card.get("id") or "")
            for section in (card.get("sections") or {}).get("items") or []:
                for score in (section.get("scores") or {}).get("items") or []:
                    if isinstance(score, dict) and score.get("id"):
                        inventory_scores[(card_id, str(score["id"]))] = score
                        scorecards_with_inventory_scores.add(card_id)

        rows: list[dict[str, Any]] = []
        matched_id_set = set(matched_ids)
        unexpected_scorecard_ids: list[str] = []
        unexpected_score_rows: list[dict[str, str]] = []
        for card_result in (alignment.get("scorecards") or []) if isinstance(alignment, dict) else []:
            if not isinstance(card_result, dict):
                continue
            result_card_id = str(
                card_result.get("scorecard_id") or card_result.get("scorecardId") or ""
            )
            if result_card_id not in matched_id_set:
                if result_card_id and result_card_id not in unexpected_scorecard_ids:
                    unexpected_scorecard_ids.append(result_card_id)
                continue
            for score in card_result.get("scores") or []:
                if isinstance(score, dict):
                    nested_card_id = str(score.get("scorecard_id") or result_card_id)
                    score_id = str(score.get("score_id") or "")
                    if nested_card_id != result_card_id:
                        unexpected_score_rows.append({
                            "scorecard_id": nested_card_id,
                            "score_id": score_id,
                            "reason": "scorecard attribution mismatch",
                        })
                        continue
                    inventory = inventory_scores.get((result_card_id, score_id))
                    if inventory is None and result_card_id in scorecards_with_inventory_scores:
                        unexpected_score_rows.append({
                            "scorecard_id": result_card_id,
                            "score_id": score_id,
                            "reason": "score is absent from selected inventory",
                        })
                        continue
                    inventory = inventory or {}
                    score_activity = evaluate_score_activity(inventory, as_of=as_of)
                    champion_id = inventory.get("championVersionId")
                    champion_relationship_valid: bool | None = None
                    if champion_id and "championVersion" in inventory:
                        champion_relationship = inventory.get("championVersion")
                        champion_relationship_valid = bool(
                            isinstance(champion_relationship, Mapping)
                            and champion_relationship.get("id") == champion_id
                            and champion_relationship.get("scoreId") == score_id
                        )
                    rows.append({
                        **score,
                        # The feedback analyzer calls these total_items and
                        # disagreements.  The decision packet calls them
                        # valid feedback and reviewed disagreements.
                        "valid_feedback_count": score.get("valid_feedback_count", score.get("total_items", 0)),
                        "reviewed_disagreements": score.get("reviewed_disagreements", score.get("disagreements", 0)),
                        "champion_version": score.get("champion_version") or champion_id,
                        "champion_relationship_valid": champion_relationship_valid,
                        "enabled": score.get("enabled", not bool(inventory.get("isDisabled", False))),
                        "scorecard_id": result_card_id,
                        "scorecard_name": score.get("scorecard_name") or card_result.get("scorecard_name"),
                        "score_updated_at": inventory.get("updatedAt"),
                        "newest_version_id": score_activity.get("newest_version_id"),
                        "newest_version_created_at": score_activity.get("newest_version_created_at"),
                        "score_activity": score_activity,
                    })
        if unexpected_scorecard_ids or unexpected_score_rows:
            coverage["complete"] = False
            coverage["failures"].append({
                "stage": "feedback_alignment",
                "error": "analysis result included unexpected out-of-scope or malformed rows",
                "scorecard_ids": unexpected_scorecard_ids,
                "score_rows": unexpected_score_rows,
            })
        analyzed_scorecards = {
            str(card_result.get("scorecard_id") or card_result.get("scorecardId") or "")
            for card_result in (alignment.get("scorecards") or [])
            if (
                isinstance(card_result, dict)
                and not card_result.get("error")
                and str(card_result.get("scorecard_id") or card_result.get("scorecardId") or "")
                in matched_id_set
            )
        }
        missing_scorecards = sorted(matched_id_set - analyzed_scorecards)
        if missing_scorecards:
            coverage["complete"] = False
            coverage["failures"].append({
                "stage": "feedback_alignment",
                "error": "analysis result omitted discovered scorecards",
                "scorecard_ids": missing_scorecards,
            })
        return {
            "scores": rows,
            "coverage": coverage,
            "window": window,
            "scope": scope,
        }

    def _current_optimization_freshness(
        self, targets: Any
    ) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
        """Read current champion, feedback, and score-activity evidence."""
        evidence_by_target: dict[tuple[str, str], dict[str, Any]] = {}
        failures: list[dict[str, Any]] = []
        from datetime import datetime, timezone

        as_of = datetime.now(timezone.utc).replace(microsecond=0)
        for source in targets if isinstance(targets, list) else []:
            if not isinstance(source, dict):
                continue
            scorecard_id = str(source.get("scorecard_id") or "")
            score_id = str(source.get("score_id") or "")
            if not scorecard_id or not score_id:
                continue
            try:
                info = self._score_info({
                    "scorecard_identifier": scorecard_id,
                    "score_identifier": score_id,
                })
                watermark = self._feedback_latest_update({
                    "scorecard_name": scorecard_id,
                    "score_name": score_id,
                    "days": 90,
                })
                from plexus.optimization.decision import evaluate_score_activity

                activity = evaluate_score_activity(info or {}, as_of=as_of)
                if activity.get("complete") is not True:
                    raise RuntimeError(
                        "live score activity evidence is incomplete: "
                        + str(activity.get("failure") or "unknown activity failure")
                    )
                if activity.get("recent") is True:
                    failures.append({
                        "target": source,
                        "reason": "recent_score_activity",
                        "score_updated_at": activity.get("score_updated_at"),
                        "newest_version_id": activity.get("newest_version_id"),
                        "newest_version_created_at": activity.get("newest_version_created_at"),
                        "activity_timestamp": activity.get("activity_timestamp"),
                        "activity_as_of": activity.get("as_of"),
                    })
                    continue
                evidence = {
                    "scorecard_id": scorecard_id,
                    "score_id": score_id,
                    "champion_version": (info or {}).get("championVersionId"),
                    "feedback_watermark": (watermark or {}).get("latest_feedback_updated_at"),
                    "score_updated_at": activity.get("score_updated_at"),
                    "newest_version_id": activity.get("newest_version_id"),
                    "newest_version_created_at": activity.get("newest_version_created_at"),
                    "activity_timestamp": activity.get("activity_timestamp"),
                    "activity_as_of": activity.get("as_of"),
                }
                evidence_by_target[(scorecard_id, score_id)] = evidence
            except Exception as exc:  # noqa: BLE001 - a failed recheck must not dispatch
                failures.append({
                    "target": source,
                    "reason": "freshness_check_failed",
                    "error": str(exc),
                })
        return evidence_by_target, failures

    @staticmethod
    def _current_assessment_fingerprint(target: Mapping[str, Any]) -> str | None:
        """Recompute the canonical fingerprint from the embedded assessment.

        The dispatcher independently validates this packet.  Computing the
        current-fingerprint map here as well ensures the transport never
        substitutes a caller-controlled fingerprint for that evidence.
        """
        assessment = target.get("assessment")
        if not isinstance(assessment, Mapping):
            return None
        evidence = assessment.get("evidence")
        if not isinstance(evidence, Mapping):
            return None
        from plexus.optimization.decision import evidence_fingerprint

        return evidence_fingerprint({
            "account_id": assessment.get("account_id"),
            "scope": assessment.get("scope") or {},
            "window": assessment.get("window") or {},
            "policy_version": assessment.get("policy_version"),
            "champion_version": assessment.get("champion_version"),
            "feedback_watermark": assessment.get("feedback_watermark"),
            "evidence": dict(evidence),
        })

    def _optimization_assessment_payload(self, args: dict[str, Any]) -> dict[str, Any]:
        scorecard_id = str(args.get("scorecard_id") or "")
        score_id = str(args.get("score_id") or "")
        if not scorecard_id or not score_id:
            raise ValueError("plexus.optimization.assess requires exact scorecard_id and score_id")
        # Assessment composes a frozen rank row with configuration facts.  If
        # a caller already has that row/packet, reuse it exactly; otherwise an
        # exact-ID request builds the canonical account-wide frozen rank input
        # and selects this score's row.  It never treats empty evidence as
        # complete.
        supplied = args.get("rank_evidence") or args.get("evidence") or args.get("rank_packet")
        if supplied is None:
            supplied = self._rank_payload_from_runtime(args)
        source = dict(supplied) if isinstance(supplied, dict) else {}
        rank_rows: list[Any] = []
        for key in ("scores", "ranked", "unranked"):
            values = source.get(key)
            if isinstance(values, list):
                rank_rows.extend(values)
        packet_evidence = source.get("evidence")
        if isinstance(packet_evidence, dict):
            for key in ("scores", "ranked", "unranked"):
                values = packet_evidence.get(key)
                if isinstance(values, list):
                    rank_rows.extend(values)
        selected = next(
            (
                dict(row)
                for row in rank_rows
                if isinstance(row, dict)
                and str(row.get("scorecard_id") or row.get("scorecardId") or "") == scorecard_id
                and str(row.get("score_id") or row.get("scoreId") or row.get("id") or "") == score_id
            ),
            None,
        )
        if selected is not None:
            evidence = {
                **source,
                **selected,
                "scope": {"scorecard_id": scorecard_id, "score_id": score_id},
                "coverage": source.get("coverage") or {},
                "window": source.get("window") or packet_evidence.get("window", {}) if isinstance(packet_evidence, dict) else source.get("window") or {},
            }
        else:
            evidence = source
        failures: list[Any] = list((evidence.get("coverage") or {}).get("failures") or [])
        evidence_scope = dict(evidence.get("scope") or {})
        evidence_scorecard_id = evidence.get("scorecard_id") or evidence_scope.get("scorecard_id")
        evidence_score_id = evidence.get("score_id") or evidence_scope.get("score_id")
        if not evidence:
            failures.append("frozen rank evidence is required")
        elif selected is None and any(rank_rows):
            failures.append("exact score is absent from frozen rank evidence")
        elif (
            (evidence_scorecard_id is not None and str(evidence_scorecard_id) != scorecard_id)
            or (evidence_score_id is not None and str(evidence_score_id) != score_id)
        ):
            failures.append("rank evidence does not match exact score identifiers")
        window = evidence.get("window") or args.get("window") or {}
        if not isinstance(window, dict) or not window.get("start") or not window.get("end"):
            failures.append("frozen feedback window is required")
        if not any(
            key in evidence
            for key in ("valid_feedback_count", "total_items", "totalItems")
        ):
            failures.append("frozen feedback metrics are required")
        try:
            info = self._score_info({"scorecard_identifier": scorecard_id, "score_identifier": score_id})
        except Exception as exc:  # noqa: BLE001
            return {"scorecard_id": scorecard_id, "score_id": score_id, "coverage": {"complete": False, "failures": [str(exc)]}, "coverage_complete": False}
        code = info.get("code") if isinstance(info, dict) else None
        guidelines = info.get("guidelines") if isinstance(info, dict) else None
        terminal_classes: list[str] = []
        terminal_resolved = False
        if code:
            try:
                resolver = self._terminal_class_resolver
                if resolver is None:
                    from plexus.rca_analysis import resolve_final_output_classes_from_yaml_text
                    resolver = resolve_final_output_classes_from_yaml_text
                resolved = resolver(str(code))
                terminal_classes = list((resolved or {}).get("classes") or resolved or [])
                terminal_resolved = bool(terminal_classes)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"terminal class resolution failed: {exc}")
        guideline_state = "missing"
        if guidelines:
            try:
                validator = self._guidelines_validator
                if validator is None:
                    from plexus.guidelines.validator import validate_guidelines_content
                    validation = validate_guidelines_content(str(guidelines)).to_dict()
                else:
                    validation = validator(str(guidelines))
                guideline_state = "consistent" if validation.get("is_valid", validation.get("valid", False)) else "invalid"
            except Exception as exc:  # noqa: BLE001
                guideline_state = "invalid"
                failures.append(f"guidelines validation failed: {exc}")
        counts = {
            str(row.get("label")): int(row.get("count") or 0)
            for row in evidence.get("class_distribution") or []
            if isinstance(row, dict) and row.get("label") is not None
        }
        for label in terminal_classes:
            counts.setdefault(str(label), 0)
        if evidence.get("feedback_timestamps") and (evidence.get("window") or args.get("window")):
            try:
                from plexus.optimization.decision import weekly_buckets
                weekly = weekly_buckets(
                    evidence["feedback_timestamps"],
                    window_end=(evidence.get("window") or args["window"])["end"],
                )
                evidence.setdefault("weekly_bucket_counts", [bucket["count"] for bucket in weekly])
                evidence.setdefault("weekly_buckets", weekly)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"weekly metrics unavailable: {exc}")
        coverage = dict(evidence.get("coverage") or {})
        # Do not default absent coverage to complete: a score may only be
        # assessed from rank evidence that explicitly attests complete frozen
        # coverage for this exact target.
        complete = bool(coverage.get("complete", evidence.get("coverage_complete", False))) and not failures
        return {
            **evidence,
            "account_id": args.get("account_id"), "scorecard_id": scorecard_id, "score_id": score_id,
            "scope": {"scorecard_id": scorecard_id, "score_id": score_id},
            "window": window,
            "coverage": {**coverage, "complete": complete, "failures": failures},
            "coverage_complete": complete, "coverage_failures": failures,
            "champion_version": info.get("championVersionId"),
            "configuration_readable": bool(code), "terminal_classes_resolved": terminal_resolved,
            "reachable_classes": terminal_classes, "final_label_counts": counts,
            "guideline_state": guideline_state,
            "feedback_watermark": evidence.get("feedback_watermark"),
        }

    def _optimization_diagnosis_payload(self, args: dict[str, Any]) -> dict[str, Any]:
        scorecard_id, score_id = str(args.get("scorecard_id") or ""), str(args.get("score_id") or "")
        if not scorecard_id or not score_id:
            raise ValueError("plexus.optimization.diagnose requires exact scorecard_id and score_id")
        failures: list[str] = []
        info: dict[str, Any] = {}
        try:
            info = self._score_info({"scorecard_identifier": scorecard_id, "score_identifier": score_id})
        except Exception as exc:  # noqa: BLE001
            failures.append(str(exc))
        score_version_id = str(info.get("championVersionId") or "")
        if not score_version_id:
            failures.append("missing champion version for semantic diagnosis")
        base = {
            "scorecard": scorecard_id,
            "score": score_id,
            "scorecard_id": scorecard_id,
            "score_id": score_id,
            "version": score_version_id,
            "score_version_id": score_version_id,
        }
        results: dict[str, Any] = {}
        for name, handler in (
            ("contradictions", self._score_contradictions),
            ("rubric_memory", self._rubric_memory_recent_entries),
            ("rubric_evidence", self._rubric_memory_evidence_pack),
        ):
            try:
                value = handler(base)
                results[name] = value
                if isinstance(value, dict) and (value.get("pending") or value.get("handle_id")):
                    failures.append(f"{name} pending")
            except Exception as exc:  # noqa: BLE001
                failures.append(str(exc))
        rubric_context = results.get("rubric_evidence") or results.get("rubric_memory") or {}
        gate_args = {
            **base,
            "rubric_memory_context": rubric_context,
            "candidate_agenda_markdown": args.get("candidate_agenda_markdown") or "",
            # Keep the gate's input tied to the exact semantic evidence rather
            # than asking it to rediscover or infer prior results.
            "optimizer_context": args.get("optimizer_context") or str({
                "contradictions": results.get("contradictions") or {},
                "rubric_memory": results.get("rubric_memory") or {},
                "rubric_evidence": results.get("rubric_evidence") or {},
            }),
        }
        try:
            value = self._rubric_memory_sme_question_gate(gate_args)
            results["sme_gate"] = value
            if isinstance(value, dict) and (value.get("pending") or value.get("handle_id")):
                failures.append("sme_gate pending")
        except Exception as exc:  # noqa: BLE001
            failures.append(str(exc))
        contradictions = results.get("contradictions") or {}
        sme = results.get("sme_gate") or {}
        stakeholder_questions: list[str] = []
        if isinstance(sme, dict):
            # The typed SME gate publishes final agenda items, not a generic
            # `questions` field.  Surface only retained/transformed items that
            # are explicitly classified as true open questions; answered or
            # suppressed candidates must not block optimization.
            for item in sme.get("final_items") or []:
                if not isinstance(item, dict):
                    continue
                if str(item.get("answer_status") or "").lower() != "true_open_question":
                    continue
                question = str(item.get("final_text") or item.get("original_text") or "").strip()
                if question:
                    stakeholder_questions.append(question)
        return {
            "account_id": args.get("account_id"), "scorecard_id": scorecard_id, "score_id": score_id,
            "scope": {"scorecard_id": scorecard_id, "score_id": score_id},
            "assessment": args.get("assessment") or args.get("assessment_packet") or {},
            "window": args.get("window") or {},
            "feedback_watermark": args.get("feedback_watermark"),
            "champion_version": info.get("championVersionId"),
            "guideline_state": (
                "potential_code_conflict"
                if isinstance(contradictions, dict) and contradictions.get("status") == "potential_conflict"
                else contradictions.get("status", "inconclusive") if isinstance(contradictions, dict) else "inconclusive"
            ),
            "feedback_rubric_consistent": isinstance(contradictions, dict) and contradictions.get("status") == "consistent",
            "stakeholder_questions": stakeholder_questions,
            "complete": not failures, "coverage": {"complete": not failures, "failures": failures},
            "coverage_complete": not failures, "coverage_failures": failures,
            "evidence_ids": [value.get("id") for value in results.values() if isinstance(value, dict) and value.get("id")],
        }

    def _optimization_review_payload(self, args: dict[str, Any]) -> dict[str, Any]:
        procedure_id = str(args.get("procedure_id") or "")
        if not procedure_id:
            # Public callers cannot turn unverified boolean fields into a
            # promotion decision.  Only indexed optimizer evidence is a valid
            # review input.
            return {"evidence": {
                "terminal": False,
                "incomplete": True,
                "error": "procedure_id is required for indexed optimizer review",
            }}
        try:
            if self._review_evidence_loader is not None:
                manifest = self._review_evidence_loader(procedure_id)
            else:
                from plexus.cli.shared.client_utils import create_client
                from plexus.cli.shared.optimizer_results import OptimizerResultsService
                manifest = OptimizerResultsService(create_client()).summarize_optimizer_procedure(procedure_id)
            from plexus.optimization.orchestration import (
                build_indexed_optimizer_review_evidence,
            )

            evidence = build_indexed_optimizer_review_evidence(
                manifest,
                procedure_id=procedure_id,
                read_evaluation=lambda evaluation_id: self._evaluation_info(
                    {"evaluation_id": evaluation_id}
                ),
            )
            return {"evidence": evidence}
        except Exception as exc:  # indexed evidence is mandatory for promotion review
            return {"evidence": {"procedure_id": procedure_id, "terminal": False, "incomplete": True, "error": str(exc)}}

    def _default_optimization_handler(
        self, method: str
    ) -> Callable[[dict[str, Any]], Any]:
        """Return a thin adapter to the shared decision service.

        The import remains lazy so existing Tactus surfaces keep working while
        the optional optimization package is not installed in a deployment.
        """
        def invoke(args: dict[str, Any]) -> Any:
            try:
                from plexus.optimization import decision
            except ImportError as exc:
                raise RuntimeError(
                    "plexus.optimization decision service is unavailable"
                ) from exc
            helper = getattr(decision, "dispatch_optimization_operation", None)
            if not callable(helper):
                raise RuntimeError(
                    "plexus.optimization.decision.dispatch_optimization_operation is unavailable"
                )
            dependencies = self._optimization_dependencies()
            if method == "rank":
                # Validate selectors before the injected-evidence bypass so an
                # explicitly empty or malformed scope can never widen to an
                # account-wide rank.
                normalized_scope = decision.normalize_rank_scope(args)
                if not args.get("scores"):
                    args = {**args, **self._rank_payload_from_runtime(args)}
                else:
                    args = {**args, "scope": normalized_scope}
            elif method == "assess":
                args = self._optimization_assessment_payload(args)
            elif method == "diagnose":
                args = self._optimization_diagnosis_payload(args)
            elif method == "review":
                args = self._optimization_review_payload(args)
            freshness_evidence: dict[tuple[str, str], dict[str, Any]] = {}
            freshness_failures: list[dict[str, Any]] = []
            if method == "run" and args.get("approved") is True:
                freshness_evidence, freshness_failures = (
                    self._current_optimization_freshness(args.get("targets"))
                )
                fresh_targets: list[dict[str, Any]] = []
                current_fingerprints: dict[str, str] = {}
                for source in args.get("targets") or []:
                    if not isinstance(source, dict):
                        continue
                    scorecard_id = str(source.get("scorecard_id") or "")
                    score_id = str(source.get("score_id") or "")
                    current = freshness_evidence.get((scorecard_id, score_id))
                    if current is None:
                        continue
                    if (
                        source.get("champion_version") != current["champion_version"]
                        or source.get("feedback_watermark") != current["feedback_watermark"]
                    ):
                        # Retain the target for the common public validator so
                        # it returns the precise stale-assessment reason rather
                        # than a misleading empty-batch error.
                        fresh_targets.append(source)
                        current_fingerprints[
                            f"{scorecard_id}:{score_id}"
                        ] = "live-evidence-changed"
                        continue
                    fresh_targets.append(source)
                    fingerprint = self._current_assessment_fingerprint(source)
                    if fingerprint:
                        current_fingerprints[f"{scorecard_id}:{score_id}"] = fingerprint
                # Ignore caller-provided current_fingerprints.  The pure
                # decision layer will validate the embedded assessment packet
                # against this independently recomputed map.
                args = {
                    **args,
                    "targets": fresh_targets,
                    "current_fingerprints": current_fingerprints,
                }
            result = helper(method, args, **dependencies)
            if method != "run" or not isinstance(result, dict):
                return result

            accepted_targets: list[dict[str, Any]] = []
            rejected = freshness_failures + list(result.get("rejected") or [])
            for target in result.get("accepted_targets") or []:
                if not isinstance(target, dict):
                    continue
                key = (str(target.get("scorecard_id") or ""), str(target.get("score_id") or ""))
                current = freshness_evidence.get(key)
                if current is None:
                    rejected.append({"target": target, "reason": "freshness_check_failed"})
                    continue
                if (
                    target.get("champion_version") not in (None, current["champion_version"])
                    or target.get("feedback_watermark") not in (None, current["feedback_watermark"])
                ):
                    rejected.append({"target": target, "reason": "stale_assessment"})
                    continue
                accepted_targets.append(target)

            # Validation is pure and returns only explicitly accepted opaque
            # targets.  Dispatch each accepted target through the existing
            # optimizer entry point; never create score versions or promote a
            # champion here.
            dispatches: list[dict[str, Any]] = []
            for target in accepted_targets:
                if not isinstance(target, dict):
                    continue
                dispatch_args = {
                    key: value
                    for key, value in args.items()
                    if key not in {"approved", "targets", "current_fingerprints", "persist", "concurrency", "max_concurrency"}
                }
                dispatch_args.update({
                    "scorecard": target["scorecard_id"],
                    "score": target["score_id"],
                })
                dispatch_row = {
                    "target": {
                        "scorecard_id": target["scorecard_id"],
                        "score_id": target["score_id"],
                    },
                }
                try:
                    dispatch_row.update({
                        "status": "dispatched",
                        "result": self._procedure_optimize(dispatch_args),
                    })
                except Exception as exc:  # noqa: BLE001 - preserve per-target coverage
                    dispatch_row.update({"status": "failed", "error": str(exc)})
                dispatches.append(dispatch_row)
            failed_dispatches = sum(
                row.get("status") == "failed" for row in dispatches
            )
            return {
                **result,
                "accepted": bool(accepted_targets) and not rejected,
                "accepted_targets": accepted_targets,
                "rejected": rejected,
                "dispatches": dispatches,
                "dispatch_coverage": {
                    "target_count": len(dispatches),
                    "dispatched_count": len(dispatches) - failed_dispatches,
                    "failed_count": failed_dispatches,
                    "complete": failed_dispatches == 0,
                },
            }

        return invoke

    def _call_optimization(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if namespace != "optimization" or method not in self._optimization_handlers:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("optimization", method)
        self._record_api_call("optimization", method)
        try:
            parsed = _merge_runtime_context_args(_args(args), self._runtime_context)
            result = self._optimization_handlers[method](parsed)
            if parsed.get("persist") is True:
                if self._optimization_persister is None:
                    raise RuntimeError(
                        "plexus.optimization persistence requires a configured Report/S3 handler"
                    )
                # The persistence path receives precisely the caller-visible
                # packet.  Its return is intentionally ignored: no inline
                # fallback or alternate response representation is permitted.
                self._optimization_persister(result)
            return result
        finally:
            self._budget.record_after("optimization", method)

    def _call_rubric_memory(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "rubric_memory" or method not in {
            "recent_entries", "evidence_pack", "sme_question_gate"
        }:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("rubric_memory", method)
        self._record_api_call("rubric_memory", method)
        try:
            parsed = _args(args)
            if method == "recent_entries":
                return self._rubric_memory_recent_entries(parsed)
            if method == "evidence_pack":
                return self._rubric_memory_evidence_pack(parsed)
            return self._rubric_memory_sme_question_gate(parsed)
        finally:
            self._budget.record_after("rubric_memory", method)

    def _call_evaluation_read(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if namespace != "evaluation" or method not in {
            "info",
            "compare",
            "find_recent",
        }:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("evaluation", method)
        self._record_api_call("evaluation", method)
        try:
            parsed = _merge_runtime_context_args(_args(args), self._runtime_context)
            if method == "info":
                return self._evaluation_info(parsed)
            if method == "compare":
                return self._evaluation_compare(parsed)
            return self._evaluation_find_recent(parsed)
        finally:
            self._budget.record_after("evaluation", method)

    def _call_evaluation_write(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if (namespace, method) != ("evaluation", "archive"):
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("evaluation", method)
        self._record_api_call("evaluation", method)
        try:
            parsed = _merge_runtime_context_args(_args(args), self._runtime_context)
            return self._evaluation_archive(parsed)
        finally:
            self._budget.record_after("evaluation", method)

    def _call_evaluation_run(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if (namespace, method) != ("evaluation", "run"):
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        parsed = _merge_runtime_context_args(_args(args), self._runtime_context)
        if not parsed.get("procedure_id") and self._trace_id:
            parsed["procedure_id"] = self._trace_id
        self._apply_latest_score_evaluation_version(parsed)
        if not bool(parsed.get("async")):
            self._record_api_call("evaluation", "run")
            self.handle_protocol_required = ("evaluation", "run")
            raise RequiresHandleProtocol("evaluation", "run")

        self._record_api_call("evaluation", "run")
        child_budget = self._budget.carve_child("evaluation", "run", parsed.get("budget"))
        try:
            dispatch_result = self._evaluation_runner(parsed)
            return self._handle_store.create(
                kind="evaluation",
                parent_trace_id=self._trace_id,
                api_call="plexus.evaluation.run",
                args=parsed,
                dispatch_result=dispatch_result,
                child_budget=child_budget,
            )
        finally:
            self._budget.record_after("evaluation", "run")

    def _call_dataset(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "dataset" or method not in self._dataset_handlers:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("dataset", method)
        self._record_api_call("dataset", method)
        try:
            return self._dataset_handlers[method](_args(args))
        finally:
            self._budget.record_after("dataset", method)

    def _call_model_frontier(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if namespace != "model_frontier" or method not in {
            "plan",
            "build_result_row",
            "finalize",
        }:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("model_frontier", method)
        self._record_api_call("model_frontier", method)
        try:
            parsed = _args(args)
            from plexus.cli.procedure.model_performance_frontier import (
                build_result_row,
                build_variants,
                compact_report_envelope,
                render_artifacts,
            )

            if method == "plan":
                variants = build_variants(
                    parsed.get("yaml_content") or "",
                    parsed.get("candidate_matrix") or {},
                    include_current=parsed.get("include_current"),
                )
                return {"variants": variants, "count": len(variants)}

            if method == "build_result_row":
                return build_result_row(
                    parsed.get("variant") or {},
                    feedback_evaluation=parsed.get("feedback_evaluation"),
                    regression_evaluation=parsed.get("regression_evaluation"),
                )

            rows = parsed.get("rows") or []
            title = parsed.get("title") or "Model Performance Frontier"
            artifacts = render_artifacts(rows, title=title)
            artifact_paths: list[str] = []
            report_block_id = parsed.get("report_block_id")
            if report_block_id:
                from plexus.cli.shared.client_utils import create_client
                from plexus.reports.s3_utils import add_file_to_report_block

                client = create_client()
                content_types = {
                    "frontier.json": "application/json",
                    "frontier.csv": "text/csv",
                    "frontier.html": "text/html",
                }
                for filename, content in artifacts.items():
                    attached = add_file_to_report_block(
                        str(report_block_id),
                        filename,
                        content.encode("utf-8"),
                        content_type=content_types.get(filename),
                        client=client,
                    )
                    if attached:
                        artifact_paths = list(attached)
            else:
                artifact_paths = [f"reportblocks/unpersisted/{filename}" for filename in artifacts]

            rows_with_frontier = json.loads(artifacts["frontier.json"])["rows"]
            return {
                "rows": rows_with_frontier,
                "artifacts": artifacts,
                "artifact_paths": artifact_paths,
                "report_output": compact_report_envelope(
                    artifact_paths=artifact_paths,
                    rows=rows_with_frontier,
                ),
                "persisted": bool(report_block_id),
            }
        finally:
            self._budget.record_after("model_frontier", method)

    def _call_scorecard_retarget(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if namespace != "scorecard_retarget" or method != "plan_score":
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("scorecard_retarget", method)
        self._record_api_call("scorecard_retarget", method)
        try:
            parsed = _args(args)
            from plexus.cli.procedure.scorecard_model_retarget import (
                plan_score_retarget,
            )

            return plan_score_retarget(
                yaml_content=parsed.get("yaml_content") or "",
                target=parsed.get("target") or {},
            )
        finally:
            self._budget.record_after("scorecard_retarget", method)

    def _call_report_read(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if namespace != "report" or method not in self._report_readers:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("report", method)
        self._record_api_call("report", method)
        try:
            parsed = _merge_runtime_context_args(_args(args), self._runtime_context)
            return self._report_readers[method](parsed)
        finally:
            self._budget.record_after("report", method)

    @staticmethod
    def _parse_acceptance_rate_result(raw: Any, *, include_items: bool = False) -> dict:
        """Parse AcceptanceRate sync output into a clean dict for LLM consumption.

        The block returns a string of the form ``# header\\n\\n{...json...}``.
        We parse the JSON portion, drop the verbose log, and optionally strip
        the per-item rows (which can be thousands of entries).
        """
        import json as _json

        output_str = None
        if isinstance(raw, dict):
            out = raw.get("output")
            if isinstance(out, str):
                output_str = out
            elif isinstance(out, dict):
                data = dict(out)
                if not include_items:
                    data.pop("items", None)
                data.pop("raw_counts", None)
                return {"status": "success", "cached": raw.get("cached"), **data}
        if output_str is None:
            return raw  # can't parse, pass through

        # Strip the comment-header lines (lines starting with #) to get raw JSON
        json_lines = [l for l in output_str.splitlines() if not l.startswith("#")]
        json_str = "\n".join(json_lines).strip()
        try:
            data = _json.loads(json_str)
        except Exception:
            return {"status": "success", "output": output_str}

        if not include_items:
            data.pop("items", None)
        data.pop("raw_counts", None)
        return {"status": "success", "cached": raw.get("cached") if isinstance(raw, dict) else None, **data}

    def _call_report_run(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "report" or method not in {"run", "acceptance_rate", "score_champion_version_timeline"}:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        parsed = _merge_runtime_context_args(_args(args), self._runtime_context)

        # Convenience shorthand: plexus.report.acceptance_rate{...} pre-fills block_class.
        if method == "acceptance_rate":
            parsed = {**parsed, "block_class": "AcceptanceRate",
                      "block_config": {**parsed.get("block_config", {}), **{
                          k: parsed[k] for k in (
                              "scorecard", "score", "days", "start_date", "end_date",
                              "include_item_acceptance_rate", "max_items",
                          ) if k in parsed
                      }}}
        if method == "score_champion_version_timeline":
            parsed = {**parsed, "block_class": "ScoreChampionVersionTimeline",
                      "block_config": {**parsed.get("block_config", {}), **{
                          k: parsed[k] for k in (
                              "scorecard", "score", "days", "start_date", "end_date",
                              "include_unchanged",
                          ) if k in parsed
                      }}}

        # Synchronous inline mode: run the block in the current process and
        # return the output directly.  Used by procedures that need the report
        # result before continuing (e.g. contradictions analysis).
        if bool(parsed.get("sync")):
            self._budget.check_before("report", "run")
            self._record_api_call("report", "run")
            try:
                raw = _default_report_runner_sync(parsed)
                # For AcceptanceRate: parse the output string and return a clean
                # dict (drop the verbose shard-fetch log and strip items unless
                # the caller explicitly asked for them via include_items=true).
                if parsed.get("block_class") == "AcceptanceRate":
                    return self._parse_acceptance_rate_result(
                        raw, include_items=bool(parsed.get("include_items", False))
                    )
                return raw
            finally:
                self._budget.record_after("report", "run")

        if not bool(parsed.get("async")):
            self._record_api_call("report", "run")
            self.handle_protocol_required = ("report", "run")
            raise RequiresHandleProtocol("report", "run")

        self._record_api_call("report", "run")
        child_budget = self._budget.carve_child("report", "run", parsed.get("budget"))
        try:
            dispatch_result = self._report_runner(parsed)
            return self._handle_store.create(
                kind="report",
                parent_trace_id=self._trace_id,
                api_call="plexus.report.run",
                args=parsed,
                dispatch_result=dispatch_result,
                child_budget=child_budget,
            )
        finally:
            self._budget.record_after("report", "run")

    def _call_procedure_run(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "procedure" or method not in {"run", "optimize", "optimize_batch", "continue", "branch"}:
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        parsed = _args(args)

        if method == "optimize":
            # plexus.procedure.optimize always runs asynchronously — no handle protocol needed.
            self._record_api_call("procedure", "optimize")
            return self._procedure_optimize(parsed)

        if method == "optimize_batch":
            # plexus.procedure.optimize_batch dispatches multiple optimizers.
            self._record_api_call("procedure", "optimize_batch")
            return self._procedure_optimize_batch(parsed)

        if method == "continue":
            self._record_api_call("procedure", "continue")
            return self._procedure_continue(parsed)

        if method == "branch":
            self._record_api_call("procedure", "branch")
            return self._procedure_branch(parsed)

        if not bool(parsed.get("async")):
            self._record_api_call("procedure", "run")
            self.handle_protocol_required = ("procedure", "run")
            raise RequiresHandleProtocol("procedure", "run")

        self._record_api_call("procedure", "run")
        child_budget = self._budget.carve_child("procedure", "run", parsed.get("budget"))
        try:
            dispatch_result = self._procedure_runner(parsed)
            return self._handle_store.create(
                kind="procedure",
                parent_trace_id=self._trace_id,
                api_call="plexus.procedure.run",
                args=parsed,
                dispatch_result=dispatch_result,
                child_budget=child_budget,
            )
        finally:
            self._budget.record_after("procedure", "run")

    def _call_handle(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "handle":
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        parsed = _args(args)
        handle_id = parsed.get("id")
        task_id = parsed.get("task_id") or parsed.get("taskId")
        if not handle_id and not task_id:
            raise ValueError(f"plexus.handle.{method} requires id or task_id")

        self._budget.check_before("handle", method)
        self._record_api_call("handle", method)
        try:
            # Lambda-local handle files cannot be recovered by a later chat
            # turn running on another worker.  Report dispatch already returns
            # a durable dashboard task id, so make that id directly pollable.
            if task_id:
                if method not in {"peek", "status", "await"}:
                    raise ValueError(
                        f"plexus.handle.{method} requires an ephemeral handle id"
                    )
                return self._refresh_task_handle(str(task_id))
            if method in {"peek", "status"}:
                return self._refresh_handle(str(handle_id))
            if method == "cancel":
                return self._cancel_handle(str(handle_id))
            if method == "await":
                timeout = _timeout_seconds(parsed.get("timeout"), default=0.0)
                poll_interval = _timeout_seconds(
                    parsed.get("poll_interval"), default=2.0
                )
                deadline = time.monotonic() + timeout
                while True:
                    record = self._refresh_handle(str(handle_id))
                    if record["status"] in TERMINAL_HANDLE_STATUSES:
                        return record
                    if time.monotonic() >= deadline:
                        return record
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return record
                    time.sleep(min(max(poll_interval, 0.1), remaining))
            raise ValueError(f"Unsupported Plexus runtime API: plexus.handle.{method}")
        finally:
            self._budget.record_after("handle", method)

    @staticmethod
    def _refresh_task_handle(task_id: str) -> dict[str, Any]:
        """Return a stable handle-shaped status for a persisted dashboard task."""
        try:
            from plexus.cli.shared.client_utils import create_client
            from plexus.dashboard.api.models.task import Task

            task = Task.get_by_id(task_id, create_client())
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to refresh durable report task status task_id=%s", task_id)
            return {
                "id": task_id,
                "durable_id": task_id,
                "kind": "report",
                "status": "running_unknown",
                "last_status_error": str(exc),
            }

        if not task:
            return {
                "id": task_id,
                "durable_id": task_id,
                "kind": "report",
                "status": "not_found",
            }

        raw_status = str(getattr(task, "status", "") or "").strip().lower()
        status = _normalize_handle_status(raw_status)
        return {
            "id": task_id,
            "durable_id": task_id,
            "kind": "report",
            "status": status,
            "task": {
                "id": task_id,
                "status": getattr(task, "status", None),
                "status_message": getattr(task, "statusMessage", None),
                "error": getattr(task, "errorMessage", None),
                "updated_at": getattr(task, "updatedAt", None),
                "completed_at": getattr(task, "completedAt", None),
            },
        }

    def _cancel_handle(self, handle_id: str) -> dict[str, Any]:
        record = self._handle_store.get(handle_id)
        dispatch_result = record.get("dispatch_result") or {}
        actions: list[dict[str, Any]] = []

        process_id = dispatch_result.get("process_id")
        if process_id:
            try:
                os.kill(int(process_id), signal.SIGTERM)
                actions.append(
                    {"kind": "process", "id": str(process_id), "status": "terminated"}
                )
            except ProcessLookupError:
                actions.append(
                    {"kind": "process", "id": str(process_id), "status": "not_running"}
                )
            except Exception as exc:  # noqa: BLE001
                actions.append(
                    {
                        "kind": "process",
                        "id": str(process_id),
                        "status": "error",
                        "error": str(exc),
                    }
                )

        task_id = dispatch_result.get("task_id")
        if task_id:
            actions.append(self._cancel_dashboard_task(str(task_id)))

        evaluation_id = dispatch_result.get("evaluation_id") or dispatch_result.get(
            "id"
        )
        if record.get("kind") == "evaluation" and evaluation_id:
            actions.append(self._cancel_evaluation_record(str(evaluation_id)))

        return self._handle_store.update(
            handle_id,
            {
                "status": "cancelled",
                "cancel_requested": True,
                "cancelled_at": _iso(time.time()),
                "cancel_actions": actions,
                "cancel_propagated": any(
                    action.get("status") in {"cancelled", "terminated", "not_running"}
                    for action in actions
                ),
            },
        )

    def _cancel_dashboard_task(self, task_id: str) -> dict[str, Any]:
        try:
            from plexus.cli.shared.client_utils import create_client
            from plexus.dashboard.api.models.task import Task

            client = create_client()
            task = Task.get_by_id(task_id, client)
            if not task:
                return {"kind": "task", "id": task_id, "status": "not_found"}
            task.update(
                status="CANCELLED",
                errorMessage="Cancellation requested by execute_tactus handle.",
                completedAt=_iso(time.time()),
            )
            return {"kind": "task", "id": task_id, "status": "cancelled"}
        except Exception as exc:  # noqa: BLE001
            return {"kind": "task", "id": task_id, "status": "error", "error": str(exc)}

    def _cancel_evaluation_record(self, evaluation_id: str) -> dict[str, Any]:
        try:
            from plexus.cli.shared.client_utils import create_client
            from plexus.dashboard.api.models.evaluation import (
                Evaluation as DashboardEvaluation,
            )

            evaluation = DashboardEvaluation.get_by_id(evaluation_id, create_client())
            if not evaluation:
                return {
                    "kind": "evaluation",
                    "id": evaluation_id,
                    "status": "not_found",
                }
            evaluation.update(
                status="CANCELLED",
                errorMessage="Cancellation requested by execute_tactus handle.",
            )
            return {"kind": "evaluation", "id": evaluation_id, "status": "cancelled"}
        except Exception as exc:  # noqa: BLE001
            return {
                "kind": "evaluation",
                "id": evaluation_id,
                "status": "error",
                "error": str(exc),
            }

    def _refresh_handle(self, handle_id: str) -> dict[str, Any]:
        record = self._handle_store.get(handle_id)
        dispatch_result = record.get("dispatch_result") or {}
        if record.get("kind") == "score_edit":
            result_file = dispatch_result.get("result_file")
            if result_file and os.path.isfile(str(result_file)):
                try:
                    with open(str(result_file), "r", encoding="utf-8") as handle:
                        score_edit_result = json.load(handle)
                except Exception as exc:  # noqa: BLE001
                    return self._handle_store.update(
                        handle_id,
                        {"status": "failed", "error": f"Could not read score edit result: {exc}"},
                    )
                if score_edit_result.get("success"):
                    updated = self._handle_store.update(
                        handle_id,
                        {"status": "completed", "result": score_edit_result},
                    )
                    _cleanup_score_edit_artifacts(dispatch_result)
                    return updated
                updated = self._handle_store.update(
                    handle_id,
                    {
                        "status": "failed",
                        "error": score_edit_result.get("error") or "Score edit failed",
                        "result": score_edit_result,
                    },
                )
                _cleanup_score_edit_artifacts(dispatch_result)
                return updated
            return self._handle_store.update(handle_id, {"status": "running"})
        evaluation_id = dispatch_result.get("evaluation_id") or dispatch_result.get(
            "id"
        )
        if record.get("kind") == "evaluation" and not evaluation_id:
            id_file_path = dispatch_result.get("evaluation_id_file")
            if id_file_path:
                try:
                    with open(str(id_file_path), "r", encoding="utf-8") as id_file:
                        late_evaluation_id = id_file.read().strip()
                except FileNotFoundError:
                    late_evaluation_id = ""
                if late_evaluation_id:
                    try:
                        os.unlink(str(id_file_path))
                    except OSError:
                        pass
                    dispatch_result = {
                        **dispatch_result,
                        "evaluation_id": late_evaluation_id,
                        "evaluation_id_file": None,
                        "dashboard_url": f"https://lab.callcriteria.com/lab/evaluations/{late_evaluation_id}",
                    }
                    record = self._handle_store.update(
                        handle_id,
                        {
                            "dispatch_result": dispatch_result,
                            "status_url": dispatch_result["dashboard_url"],
                        },
                    )
                    evaluation_id = late_evaluation_id
        if record.get("kind") == "evaluation" and not evaluation_id:
            process_id = dispatch_result.get("process_id")
            if process_id:
                process_status = _exited_process_status(process_id)
                if process_status:
                    update = {
                        "status": "failed",
                        **process_status,
                        **_evaluation_process_diagnostics(
                            dispatch_result,
                            "Evaluation subprocess exited before emitting an evaluation ID.",
                        ),
                    }
                    return self._handle_store.update(handle_id, update)
                try:
                    os.kill(int(process_id), 0)
                except ProcessLookupError:
                    return self._handle_store.update(
                        handle_id,
                        {
                            "status": "failed",
                            "process_status": "not_running",
                            **_evaluation_process_diagnostics(
                                dispatch_result,
                                "Evaluation subprocess is no longer running and did not emit an evaluation ID.",
                            ),
                        },
                    )
                except PermissionError:
                    return self._handle_store.update(
                        handle_id, {"status": "running_unknown"}
                    )
                return self._handle_store.update(handle_id, {"status": "running"})
        if record.get("kind") != "evaluation" or not evaluation_id:
            return record

        try:
            evaluation = self._evaluation_info({"evaluation_id": evaluation_id})
        except Exception as exc:  # noqa: BLE001
            return self._handle_store.update(handle_id, {"last_status_error": str(exc)})

        status = _normalize_handle_status(evaluation.get("status"))
        if dispatch_result.get("process_id"):
            process_status = _exited_process_status(dispatch_result.get("process_id"))
            if process_status:
                evaluation = {**evaluation, **process_status}
            if process_status and status not in TERMINAL_HANDLE_STATUSES:
                status = "failed"
                evaluation = {
                    **evaluation,
                    "error": (
                        "Evaluation subprocess exited before the evaluation reached a terminal status."
                    ),
                }
            elif not process_status and status in TERMINAL_HANDLE_STATUSES:
                # An evaluation record becomes COMPLETED before the CLI process
                # finishes post-evaluation work such as RCA and artifact upload.
                # Do not release a bounded optimizer batch until that process is
                # gone; otherwise the next batch can exceed its concurrency cap.
                status = "running"
                evaluation = {
                    **evaluation,
                    "completion_pending_process_exit": True,
                }
        return self._handle_store.update(
            handle_id,
            {
                "status": status,
                "evaluation_id": evaluation_id,
                "evaluation": evaluation,
                "status_url": record.get("status_url")
                or evaluation.get("dashboard_url")
                or f"https://lab.callcriteria.com/lab/evaluations/{evaluation_id}",
            },
        )

    def _call_docs(self, namespace: str, method: str, args: Any = None) -> Any:
        if method == "list":
            parsed = _args(args) if args else {}
            ns_filter = parsed.get("namespace") if isinstance(parsed, dict) else None
            self._budget.check_before("docs", "list")
            self._record_api_call("docs", "list")
            try:
                return self._docs_list(namespace=ns_filter)
            finally:
                self._budget.record_after("docs", "list")
        if method == "get":
            parsed = _args(args)
            key = parsed.get("key") or parsed.get("id") or parsed.get("name") or parsed.get("filename")
            if not key:
                raise ValueError("plexus.docs.get requires key, id, name, or filename")
            self._budget.check_before("docs", "get")
            self._record_api_call("docs", "get")
            try:
                metadata, body = self._docs_read(key)
            finally:
                self._budget.record_after("docs", "get")
            return {
                "key": key,
                "id": metadata.get("id", key),
                "metadata": metadata,
                "content": body,
            }
        raise ValueError(f"Unsupported Plexus runtime API: plexus.docs.{method}")

    def _call_skills(self, namespace: str, method: str, args: Any = None) -> Any:
        if method == "list":
            parsed = _args(args) if args else {}
            tags_value = parsed.get("tags") if isinstance(parsed, dict) else None
            if isinstance(tags_value, str):
                tags = [tags_value]
            elif isinstance(tags_value, list):
                tags = tags_value
            else:
                tags = []
            self._budget.check_before("skills", "list")
            self._record_api_call("skills", "list")
            try:
                return self._skills_list(
                    query=parsed.get("query") if isinstance(parsed, dict) else None,
                    tags=tags,
                    mode=parsed.get("mode") if isinstance(parsed, dict) else None,
                )
            finally:
                self._budget.record_after("skills", "list")
        if method == "get":
            parsed = _args(args)
            skill_id = parsed.get("id") or parsed.get("key") or parsed.get("name")
            if not skill_id:
                raise ValueError("plexus.skills.get requires id, key, or name")
            mode = parsed.get("mode")
            self._budget.check_before("skills", "get")
            self._record_api_call("skills", "get")
            try:
                metadata, body, resources = self._skills_read(str(skill_id), mode=mode)
            finally:
                self._budget.record_after("skills", "get")
            return {
                "id": metadata.get("id", skill_id),
                "metadata": metadata,
                "content": body,
                "resources": resources,
            }
        raise ValueError(f"Unsupported Plexus runtime API: plexus.skills.{method}")

    def _call_guidelines(self, namespace: str, method: str, args: Any = None) -> Any:
        if namespace != "guidelines" or method != "validate":
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        parsed = _args(args)
        guidelines = parsed.get("guidelines")
        if guidelines is None:
            guidelines = parsed.get("content")
        if not isinstance(guidelines, str):
            raise ValueError("plexus.guidelines.validate requires guidelines markdown text")
        self._budget.check_before("guidelines", "validate")
        self._record_api_call("guidelines", "validate")
        try:
            from plexus.guidelines.validator import validate_guidelines_content

            return validate_guidelines_content(guidelines).to_dict()
        finally:
            self._budget.record_after("guidelines", "validate")

    def _call_api(self, namespace: str, method: str, args: Any = None) -> Any:
        if method != "list":
            raise ValueError(f"Unsupported Plexus runtime API: plexus.api.{method}")
        self._budget.check_before("api", "list")
        self._record_api_call("api", "list")
        try:
            api: dict[str, list[str]] = {}
            for namespace_name, method_name in MCP_TOOL_MAP:
                api.setdefault(f"plexus.{namespace_name}", []).append(method_name)
            for namespace_name, method_name in DIRECT_HANDLERS:
                api.setdefault(f"plexus.{namespace_name}", []).append(method_name)
            api.setdefault("plexus.docs", []).extend(["list", "get"])
            api.setdefault("plexus.skills", []).extend(["list", "get"])
            api.setdefault("plexus.api", []).append("list")
            return {key: sorted(set(values)) for key, values in sorted(api.items())}
        finally:
            self._budget.record_after("api", "list")

    def _docs_list(self, namespace: str | None = None) -> list[dict[str, Any]]:
        from plexus.documentation.repository import DocumentationRepository

        if not os.path.isdir(self._docs_dir):
            raise FileNotFoundError(
                f"Plexus docs directory not found: {self._docs_dir}"
            )
        repo = DocumentationRepository(self._docs_dir)
        result = repo.list_docs(namespace=namespace)
        return list(result.entries)

    def _docs_read(self, key: str) -> tuple[dict[str, Any], str]:
        from plexus.documentation.repository import (
            DocumentationRepository,
            InvalidDocumentationKeyError,
        )

        repo = DocumentationRepository(self._docs_dir)
        try:
            doc = repo.get_doc(key)
        except InvalidDocumentationKeyError as exc:
            message = str(exc)
            if "Unknown" in message:
                raise FileNotFoundError(message) from exc
            raise ValueError(f"Invalid plexus.docs key: {key!r}") from exc
        return doc.metadata, doc.body

    def _skills_list(
        self,
        *,
        query: str | None = None,
        tags: list[Any] | None = None,
        mode: str | None = None,
    ) -> list[dict[str, Any]]:
        from plexus.skills.repository import SkillRepository

        if not os.path.isdir(self._skills_dir):
            raise FileNotFoundError(
                f"Plexus skills directory not found: {self._skills_dir}"
            )
        repo = SkillRepository(self._skills_dir)
        result = repo.list_skills(query=query, tags=tags or [], mode=mode)
        return list(result.entries)

    def _skills_read(
        self,
        skill_id: str,
        *,
        mode: str | None = None,
    ) -> tuple[dict[str, Any], str, list[str]]:
        from plexus.skills.repository import InvalidSkillKeyError, SkillRepository

        repo = SkillRepository(self._skills_dir)
        try:
            skill = repo.get_skill(skill_id, mode=mode)
        except InvalidSkillKeyError as exc:
            message = str(exc)
            if "Unknown" in message:
                raise FileNotFoundError(message) from exc
            raise ValueError(f"Invalid plexus.skills id: {skill_id!r}") from exc
        return skill.metadata, skill.body, skill.resources


def _wrap_tactus_snippet(tactus: str) -> str:
    helper_lines = [
        'local plexus = require("plexus")',
        "local __plexus_last_result = nil",
        "local function __plexus_capture(value)",
        "  __plexus_last_result = value",
        "  return value",
        "end",
    ]
    for helper_name, namespace, method in HELPER_BINDINGS:
        helper_lines.extend(
            [
                f"function {helper_name}(args)",
                f"  return __plexus_capture(plexus.{namespace}.{method}(args))",
                "end",
            ]
        )
    return "\n".join(
        [
            *helper_lines,
            "local function __execute_tactus_user_snippet()",
            tactus,
            "end",
            "local __plexus_explicit_result = __execute_tactus_user_snippet()",
            "if __plexus_explicit_result ~= nil then",
            "  return __plexus_explicit_result",
            "end",
            "return __plexus_last_result",
            "",
        ]
    )


def _run_tactus_sync(
    tactus: str,
    mcp: FastMCP,
    *,
    trace_id: str,
    trace_store: TactusTraceStore,
    budget: BudgetGate | None = None,
    handle_store: TactusHandleStore | None = None,
    feedback_finder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    evaluation_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    evaluation_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    report_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    procedure_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    stream_handler: _MCPStreamEmitter | None = None,
    score_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gate = budget if budget is not None else BudgetGate()

    async def run() -> dict[str, Any]:
        from tactus.adapters.memory import MemoryStorage
        from tactus.core import TactusRuntime

        started_mono = time.monotonic()
        started_wall = time.time()
        wrapped = _wrap_tactus_snippet(tactus)
        runtime_result: Any = None
        envelope: dict[str, Any]
        try:
            runtime = TactusRuntime(
                procedure_id=f"execute_tactus_{trace_id}",
                storage_backend=MemoryStorage(),
                log_handler=stream_handler,
                run_id=trace_id,
            )
            if not hasattr(runtime, "register_python_module"):
                raise RuntimeError(
                    "execute_tactus requires TactusRuntime.register_python_module; "
                    "update the installed tactus package to the version specified by pyproject.toml."
                )
            plexus = PlexusRuntimeModule(
                mcp,
                trace_id=trace_id,
                budget=gate,
                handle_store=handle_store,
                feedback_finder=feedback_finder,
                evaluation_info=evaluation_info,
                evaluation_runner=evaluation_runner,
                report_runner=report_runner,
                procedure_runner=procedure_runner,
                stream_handler=stream_handler,
                score_info=score_info,
                runtime_context=runtime_context,
                catch_runtime_errors=True,
            )
            runtime.register_python_module("plexus", plexus)
            if stream_handler is not None:
                stream_handler.emit(
                    kind="execution",
                    message="execute_tactus runtime started",
                    payload={"stage": "started"},
                    progress=0,
                    total=1,
                )
            runtime_result = await runtime.execute(wrapped, context={}, format="lua")
            api_calls = plexus.api_calls
            if plexus.handle_protocol_required is not None:
                ns, mt = plexus.handle_protocol_required
                envelope = _response_envelope(
                    ok=False,
                    value=None,
                    trace_id=trace_id,
                    api_calls=api_calls,
                    started_at=started_mono,
                    error=_structured_error(
                        "requires_handle_protocol",
                        f"plexus.{ns}.{mt} requires the long-running handle/streaming "
                        "protocol from Kanbus epic plx-247588 and is not enabled in "
                        "this execute_tactus build.",
                    ),
                    budget=gate,
                )
            elif gate.child_budget_required_reason:
                envelope = _response_envelope(
                    ok=False,
                    value=None,
                    trace_id=trace_id,
                    api_calls=api_calls,
                    started_at=started_mono,
                    error=_structured_error(
                        "child_budget_required",
                        gate.child_budget_required_reason,
                    ),
                    budget=gate,
                )
            elif gate.exceeded:
                envelope = _response_envelope(
                    ok=False,
                    value=None,
                    trace_id=trace_id,
                    api_calls=api_calls,
                    started_at=started_mono,
                    error=_structured_error(
                        "budget_exceeded", gate.exceeded_reason or "Budget exceeded"
                    ),
                    budget=gate,
                )
            elif not isinstance(runtime_result, dict):
                envelope = _response_envelope(
                    ok=True,
                    value=runtime_result,
                    trace_id=trace_id,
                    api_calls=api_calls,
                    started_at=started_mono,
                    budget=gate,
                )
            else:
                ok = bool(runtime_result.get("success"))
                value = _jsonable(runtime_result.get("result"))
                if ok:
                    runtime_api_error = _extract_runtime_api_error(value)
                    if runtime_api_error is not None:
                        envelope = _response_envelope(
                            ok=False,
                            value=None,
                            trace_id=trace_id,
                            api_calls=api_calls,
                            started_at=started_mono,
                            error=runtime_api_error,
                            budget=gate,
                        )
                    else:
                        envelope = _response_envelope(
                            ok=True,
                            value=value,
                            trace_id=trace_id,
                            api_calls=api_calls,
                            started_at=started_mono,
                            budget=gate,
                        )
                else:
                    message = str(
                        runtime_result.get("error") or "Tactus execution failed"
                    )
                    envelope = _response_envelope(
                        ok=False,
                        value=value,
                        trace_id=trace_id,
                        api_calls=api_calls,
                        started_at=started_mono,
                        error=_structured_error("tactus_execution_failed", message),
                        budget=gate,
                    )
            envelope = _attach_console_audit_events(
                envelope,
                (
                    runtime_context
                    if isinstance(runtime_context, dict)
                    else getattr(plexus, "_runtime_context", None)
                ),
                score_edit_events=_extract_score_edit_audit_events_from_value(
                    envelope.get("value")
                ),
            )
        finally:
            ended_wall = time.time()
            record = _build_trace_record(
                trace_id=trace_id,
                envelope=locals().get(
                    "envelope",
                    _response_envelope(
                        ok=False,
                        value=None,
                        trace_id=trace_id,
                        api_calls=[],
                        started_at=started_mono,
                        error=_structured_error(
                            "runtime_error",
                            "execute_tactus aborted before envelope was built",
                        ),
                        budget=gate,
                    ),
                ),
                submitted_tactus=tactus,
                wrapped_tactus=wrapped,
                runtime_result=runtime_result,
                started_at_wall=started_wall,
                ended_at_wall=ended_wall,
            )
            _safe_write_trace(trace_store, record)
            if stream_handler is not None:
                envelope_for_stream = locals().get("envelope")
                stream_handler.emit(
                    kind="execution",
                    message="execute_tactus runtime completed",
                    payload={
                        "stage": "completed",
                        "ok": bool(
                            isinstance(envelope_for_stream, dict)
                            and envelope_for_stream.get("ok")
                        ),
                    },
                    progress=1,
                    total=1,
                )
        return envelope

    return asyncio.run(run())


_EXECUTE_TACTUS_MAX_RESPONSE_CHARS = 40_000


def _truncate_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Cap the serialized response to avoid filling LLM context windows."""
    try:
        serialized = json.dumps(envelope)
        if len(serialized) <= _EXECUTE_TACTUS_MAX_RESPONSE_CHARS:
            return envelope
        # Re-encode with the value field truncated
        trunc = dict(envelope)
        value = trunc.get("value")
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value)
            if len(value_str) > _EXECUTE_TACTUS_MAX_RESPONSE_CHARS // 2:
                trunc["value"] = {
                    "__truncated__": True,
                    "preview": value_str[: _EXECUTE_TACTUS_MAX_RESPONSE_CHARS // 2],
                    "original_bytes": len(value_str),
                    "hint": "Response was too large for LLM context. Refine the query to fetch less data.",
                }
        elif isinstance(value, str) and len(value) > _EXECUTE_TACTUS_MAX_RESPONSE_CHARS // 2:
            trunc["value"] = (
                value[: _EXECUTE_TACTUS_MAX_RESPONSE_CHARS // 2]
                + f"\n[...truncated, {len(value)} chars total]"
            )
        return trunc
    except Exception:
        return envelope


_UNTERMINATED_STRING_MARKERS = (
    "unterminated string",
    "unfinished string",
)


def _is_unterminated_string_error(envelope: dict[str, Any]) -> bool:
    error = envelope.get("error")
    if not isinstance(error, dict):
        return False
    if str(error.get("code") or "").strip().lower() != "tactus_execution_failed":
        return False
    message = str(error.get("message") or "").strip().lower()
    return any(marker in message for marker in _UNTERMINATED_STRING_MARKERS)


def _to_lua_long_bracket_string(value: str) -> str:
    equals = ""
    while f"]{equals}]" in value:
        equals += "="
    return f"[{equals}[{value}]{equals}]"


def _sanitize_instruction_string_literals(tactus: str) -> str:
    """Normalize `instruction = '...'` / `"..."` to Lua long-bracket strings.

    This avoids quote-escaping parse failures in generated execute_tactus snippets.
    """

    assignment_re = re.compile(
        r'(?P<prefix>\binstruction\s*=\s*)(?P<quote>[\'"])(?P<body>.*)(?P=quote)(?P<suffix>\s*(?:,.*|}.*)?)$'
    )
    changed = False
    out_lines: list[str] = []
    for line in tactus.splitlines(keepends=True):
        match = assignment_re.search(line)
        if not match:
            out_lines.append(line)
            continue
        replacement = (
            f"{match.group('prefix')}"
            f"{_to_lua_long_bracket_string(match.group('body'))}"
            f"{match.group('suffix')}"
        )
        out_lines.append(
            f"{line[: match.start()]}{replacement}{line[match.end() :]}"
        )
        changed = True
    if not changed:
        return tactus
    return "".join(out_lines)


async def _execute_tactus_tool(
    tactus: str,
    mcp: FastMCP,
    *,
    ctx: Context | None = None,
    trace_store: TactusTraceStore | None = None,
    budget: BudgetGate | None = None,
    handle_store: TactusHandleStore | None = None,
    feedback_finder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    evaluation_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    evaluation_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    report_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    procedure_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    score_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    store = trace_store if trace_store is not None else _default_trace_store()
    started_mono = time.monotonic()
    started_wall = time.time()
    trace_id = str(uuid.uuid4())
    request_user_id = extract_request_user_id_from_mcp_context(ctx) if ctx is not None else None
    actor_context = resolve_actor_context(
        request_user_id=request_user_id,
        explicit_source="execute_tactus",
    )

    if not isinstance(tactus, str) or not tactus.strip():
        envelope = _response_envelope(
            ok=False,
            value=None,
            trace_id=trace_id,
            api_calls=[],
            started_at=started_mono,
            error=_structured_error(
                "invalid_request",
                "tactus must be a non-empty string",
            ),
        )
        record = _build_trace_record(
            trace_id=trace_id,
            envelope=envelope,
            submitted_tactus=tactus if isinstance(tactus, str) else "",
            wrapped_tactus=None,
            started_at_wall=started_wall,
            ended_at_wall=time.time(),
        )
        _safe_write_trace(store, record)
        return envelope

    try:
        with set_runtime_actor_context(actor_context):
            stream_handler = None
            if ctx is not None:
                stream_handler = _MCPStreamEmitter(
                    trace_id=trace_id, loop=asyncio.get_running_loop()
                )

            async def _run_once(snippet: str) -> dict[str, Any]:
                run_task = asyncio.create_task(
                    asyncio.to_thread(
                        _run_tactus_sync,
                        snippet,
                        mcp,
                        trace_id=trace_id,
                        trace_store=store,
                        budget=budget,
                        handle_store=handle_store,
                        feedback_finder=feedback_finder,
                        evaluation_info=evaluation_info,
                        evaluation_runner=evaluation_runner,
                        report_runner=report_runner,
                        procedure_runner=procedure_runner,
                        stream_handler=stream_handler,
                        score_info=score_info,
                        runtime_context=runtime_context,
                    )
                )
                if stream_handler is None:
                    return _truncate_envelope(await run_task)

                while True:
                    if run_task.done():
                        await asyncio.sleep(0)
                        if stream_handler.empty():
                            break
                    try:
                        event = await asyncio.wait_for(
                            stream_handler.get(), timeout=0.05
                        )
                    except asyncio.TimeoutError:
                        continue
                    await _send_mcp_stream_event(ctx, event)

                return _truncate_envelope(await run_task)

            result = await _run_once(tactus)
            if _is_unterminated_string_error(result):
                sanitized_tactus = _sanitize_instruction_string_literals(tactus)
                if sanitized_tactus != tactus:
                    if stream_handler is not None:
                        stream_handler.emit(
                            kind="execution",
                            message="Retrying after quote-safe instruction rewrite",
                            payload={"stage": "retrying_quote_safe_instruction"},
                            progress=0,
                            total=1,
                        )
                    result = await _run_once(sanitized_tactus)
            return result
    except Exception as exc:
        logger.error("execute_tactus failed: %s", exc, exc_info=True)
        envelope = _response_envelope(
            ok=False,
            value=None,
            trace_id=trace_id,
            api_calls=[],
            started_at=started_mono,
            error=_structured_error("runtime_error", str(exc), exc),
        )
        record = _build_trace_record(
            trace_id=trace_id,
            envelope=envelope,
            submitted_tactus=tactus,
            wrapped_tactus=None,
            started_at_wall=started_wall,
            ended_at_wall=time.time(),
        )
        _safe_write_trace(store, record)
        return envelope


EXECUTE_TACTUS_DESCRIPTION = """\
Execute a short Tactus (Lua) snippet inside the Plexus runtime. This is the
single Plexus MCP tool; use it for every Plexus operation.

Runtime ground rules:
- `plexus` is a global. Do NOT write `local plexus = require("plexus")`.
- The runtime captures the result of the last Plexus operation your snippet
  calls and returns it as the value of this tool call. Use an explicit
  `return` only when you want a custom output shape.
- Always use table arguments: `plexus.score.info{ id = "..." }`.
- Errors are structured (`error.code`, `error.message`, `error.retryable`).
- Destructive ops (champion promotion, score updates, deletes, feedback
  invalidation) request `Human.approve` automatically; pass
  `no_confirm = true` only when the user explicitly approved.
- Long-running calls (`plexus.evaluation.run`, `plexus.report.run`,
  `plexus.procedure.run`) must use `async = true`. They dispatch immediately
  and return a handle — no `budget` table needed.

Complete coverage contract:
- Never silently reduce complete requested coverage to a sample.
- Exhaust canonical collection metadata pagination (for example,
  `plexus.scorecards.list`), keep IDs opaque, and pass every target to one
  bounded `plexus.feedback.alignment_batch` call.
- Return collection and downstream coverage; incomplete is never exact.
- Never return the unaggregated alignment batch payload for complete research.
  Aggregate every row in Lua into compact totals, all failures, and bounded
  highlights with `ranked_from_count`; this is not sampling.
- Bound the sample only when the user explicitly requests or approves one.
- Feedback alignment rows expose `reviewed_error_opportunity` as
  `total_items * disagreement_rate`. Rank it descending first; report class
  coverage, drift, rubric clarity, and fixability separately.

Optimization: `plexus.optimization.rank/assess/diagnose/review/summary` plan;
`plexus.optimization.run` needs `approved = true`, at most five exact targets,
and never promotes a champion; `persist = true` has no inline output fallback.
Rank scope: opaque `scorecard_ids` or literal case-insensitive
`scorecard_name_prefixes`; empty arrays are invalid.
`score-activity-cooldown-v1`: frozen UTC `as_of`; 168-hour inclusive cutoff on
the later of `score.updatedAt` or newest score-version `createdAt`;
`recent_score_activity`; missing evidence is incomplete; assessment returns
`cooldown_active`/`wait_for_cooldown`; run rechecks live activity before dispatch.
An unresolved scalar champion ID is structurally unranked as
`unresolved_champion_reference`,
not misreported as missing cooldown evidence.

Helper aliases are injected before the snippet: high-frequency short names and
canonical `namespace_method` forms, including `docs_list/docs_get`,
`skills_list/skills_get`, handle operations, and one helper per advertised API.
- Fall back to `plexus.<namespace>.<method>{...}` for anything else.

The complete account-wide research program is documented outside this
always-present schema. Load
`evaluation-feedback.batch-operations-cookbook` for the full metadata
pagination, retry, bounded batch, compact aggregation, and coverage example.

Examples:

1) Find a scorecard by name:
```tactus
local cards = scorecards{}
for _, card in ipairs(cards) do
  if card.name == "Example Scorecard" then
    return { id = card.id, key = card.key, external_id = card.externalId }
  end
end
return { error = { code = "SCORECARD_NOT_FOUND", retryable = false } }
```

Fuzzy discovery (RapidFuzz `WRatio` — use when names are partial, typo-prone,
or you need scores ranked across every scorecard):
```tactus
return scorecards_search{ query = "operations quality", limit = 10, min_score = 55 }
return score_search{ query = "refund", limit = 20, min_score = 55 }
return score_search{ query = "tone", scorecard = "My Scorecard", limit = 10 }
```

2) Inspect a score:
```tactus
return score{ id = "score_compliance_tone" }
```

3) Get an item's info:
```tactus
return item{ id = "item_1007" }
```

4) Run a single prediction:
```tactus
return predict{
  scorecard_identifier = "My Scorecard",
  score_identifier = "Compliance Tone",
  item_id = "item_1007",
}
```

5) Run a bounded synchronous evaluation:
```tactus
evaluate{ score_id = "score_compliance_tone", item_count = 200 }
```

6) Documentation research (progressive disclosure - always do this when
unsure how a feature works):
The docs knowledge base is split into two cheap calls.
`docs_list()` returns only METADATA for every topic (`id`, `title`,
`summary`, `namespace`, `status`, `disclosure`, `tags`, `related`) - it
does NOT return markdown bodies, so it is safe to call freely. Pick the
right `id` from those summaries, then call `docs_get{ id = "..." }` to
load that one topic's full body. Filter by namespace once you know the
area. Pair with `api_list()` to see which `plexus.<namespace>.<method>`
calls exist. Always start a new investigation at the canonical overview:
```tactus
local apis     = api_list()
local overview = docs_get{ id = "mcp.execute-tactus-overview" }
local index    = docs_list{ namespace = "score-authoring" }
-- pick the entry whose summary matches the question, then:
local topic    = docs_get{ id = "score-authoring.score-yaml-format" }
return { apis = apis, overview = overview.content,
         index = index, topic = topic.content }
```

6b) Operational skill lookup for Console workflows:
Skills are operational instructions, separate from reference docs. Use the same
progressive disclosure pattern: `skills_list{}` returns metadata only, then
`skills_get{ id = "..." }` loads exactly one skill body. Use skills for how to
run a workflow; use docs for API/YAML/reference details.
```tactus
local skill_index = skills_list{ query = "score edit", mode = "execution" }
local skill = skills_get{ id = "score-code-editor" }
return { index = skill_index, skill_id = skill.id, body = skill.content }
```

6c) Guidelines validation before guidelines-only updates:
```tactus
local pulled = plexus.score.pull{
  scorecard_identifier = "<scorecard-id>",
  score_identifier = "<score-id>",
  version = "<version-id>",
}
return guidelines_validate{ guidelines = pulled.guidelines }
```

6d) Resolve score workflow targets before editing:
```tactus
local target = score_resolve{
  scorecard_identifier = "Example Scorecard",
  score_identifier = "Example Score",
}
if target.status ~= "resolved" then return target end
return {
  scorecard_id = target.scorecard_id,
  score_id = target.score_id,
  score_name = target.score.name,
}
```

7) Dispatch a long-running report (fire-and-forget, returns a handle immediately):
```tactus
local handle = plexus.report.run{
  configuration_id = "44c97c07-...",
  parameters = { days = 60 },
  async = true,
  budget = { usd = 1.0, wallclock_seconds = 600, depth = 1, tool_calls = 5 },
}
return { handle_id = handle.id, status = handle.status }
```

Then poll, await, or cancel from a later `execute_tactus` call:
`handle_status{ id = "<id>" }`,
`handle_await{ id = "<id>", timeout = "PT10M" }`,
`handle_cancel{ id = "<id>" }`.

Documentation research uses PROGRESSIVE DISCLOSURE in two steps:
1. `plexus.docs.list{}` (or `docs_list{}`) is cheap and returns only
   metadata summaries (`id`, `title`, `summary`, `namespace`, `status`,
   `disclosure`, `tags`, `related`). Browse this first to find the
   right topic by reading the summaries.
2. `plexus.docs.get{ id = "<canonical-id>" }` (or
   `docs_get{ id = "..." }`) then loads the full markdown body for one
   topic. Use the `id` from step 1 - never invent ids.
Start every investigation at `mcp.execute-tactus-overview`. Filter the
index with `plexus.docs.list{ namespace = "<name>" }`. Available
namespaces: `mcp`, `score-authoring`, `evaluation-feedback`,
`procedures`, `reports`, `optimizer`, `repo-workflows`. Cite the topic
ids you used in your reply so the user can re-fetch them.

Operational skills also use PROGRESSIVE DISCLOSURE:
1. `plexus.skills.list{}` (or `skills_list{}`) returns only skill metadata:
   `id`, `name`, `description`, `tags`, `applies_to`, `console_supported`,
   `requires_subagent`, and `allowed_modes`.
2. `plexus.skills.get{ id = "<skill-id>" }` (or `skills_get{ id = "..." }`)
   loads one full skill body plus resource references. Cite the skill id(s)
   you used. Do not preload every skill.

The response envelope always has `ok`, `value`, `error`, `cost`, `trace_id`,
`partial`, and `api_calls`.
"""


def register_tactus_tools(mcp: FastMCP) -> None:
    """Register Tactus runtime tools with the MCP server."""

    tactus_parameter = Annotated[
        str,
        Field(
            description=(
                "Tactus (Lua) snippet to execute. `plexus` is global; helper "
                "aliases like `evaluate`, `predict`, `score`, `item`, "
                "`scorecards`, `api_list`, `docs_list`, `docs_get`, "
                "`skills_list`, `skills_get`, `handle_status` are injected. "
                "Async long-running calls "
                "(`evaluation.run`, `report.run`, `procedure.run` with "
                "`async = true`) require an explicit child `budget = { usd, "
                "wallclock_seconds, depth, tool_calls }`. Read "
                "`plexus.docs.get{ key = \"mcp.execute-tactus-overview\" }` for the full guide."
            )
        ),
    ]

    async def execute_tactus(tactus, ctx):
        return await _execute_tactus_tool(tactus, mcp, ctx=ctx)

    # This module uses postponed annotations. FastMCP wraps tool functions in
    # its own module, where string annotations such as ``Annotated`` and
    # ``Context`` cannot be resolved reliably. Give the public tool concrete
    # runtime types before registration so schema construction is deterministic
    # in a clean process and independent of test/import order.
    execute_tactus.__annotations__ = {
        "tactus": tactus_parameter,
        "ctx": Context,
        "return": dict[str, Any],
    }
    mcp.tool(description=EXECUTE_TACTUS_DESCRIPTION)(execute_tactus)
