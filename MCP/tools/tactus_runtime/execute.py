#!/usr/bin/env python3
"""Single-tool Tactus execution prototype for the Plexus MCP server."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import signal
import threading
import time
import traceback
import uuid
from typing import Annotated, Any, Callable

from fastmcp import Context, FastMCP
from pydantic import Field
from plexus.runtime_budget import RuntimeBudgetSpec

logger = logging.getLogger(__name__)


PLEXUS_DOCS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "plexus", "docs")
)

PLEXUS_TACTUS_TRACE_DIR_DEFAULT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "tmp", "tactus_traces")
)


def _resolve_trace_dir() -> str:
    return os.environ.get("PLEXUS_TACTUS_TRACE_DIR", PLEXUS_TACTUS_TRACE_DIR_DEFAULT)


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
    return FileTactusTraceStore(_resolve_trace_dir())


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
    return FileTactusHandleStore(os.path.join(_resolve_trace_dir(), "handles"))


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
    ("score_info", "score", "info"),
    ("score_evaluations", "score", "evaluations"),
    ("score_predict", "score", "predict"),
    ("score_set_champion", "score", "set_champion"),
    ("set_champion", "score", "set_champion"),
    ("item_info", "item", "info"),
    ("item_last", "item", "last"),
    ("feedback_find", "feedback", "find"),
    ("feedback_alignment", "feedback", "alignment"),
    ("evaluation_info", "evaluation", "info"),
    ("evaluation_find_recent", "evaluation", "find_recent"),
    ("evaluation_compare", "evaluation", "compare"),
    ("evaluation_run", "evaluation", "run"),
    ("dataset_build_from_feedback_window", "dataset", "build_from_feedback_window"),
    ("dataset_check_associated", "dataset", "check_associated"),
    ("report_configurations_list", "report", "configurations_list"),
    ("report_run", "report", "run"),
    ("procedure_info", "procedure", "info"),
    ("procedure_list", "procedure", "list"),
    ("procedure_chat_sessions", "procedure", "chat_sessions"),
    ("procedure_chat_messages", "procedure", "chat_messages"),
    ("procedure_run", "procedure", "run"),
    ("handle_peek", "handle", "peek"),
    ("handle_status", "handle", "status"),
    ("handle_await", "handle", "await"),
    ("handle_cancel", "handle", "cancel"),
    ("docs_list", "docs", "list"),
    ("docs_get", "docs", "get"),
    ("api_list", "api", "list"),
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


MCP_TOOL_MAP: dict[tuple[str, str], str] = {
    ("scorecards", "list"): "plexus_scorecards_list",
    ("scorecards", "info"): "plexus_scorecard_info",
    ("score", "info"): "plexus_score_info",
    ("score", "evaluations"): "plexus_score_evaluations",
    ("score", "predict"): "plexus_predict",
    ("score", "set_champion"): "plexus_score_set_champion",
    ("item", "info"): "plexus_item_info",
    ("item", "last"): "plexus_item_last",
    ("feedback", "alignment"): "plexus_feedback_alignment",
    ("evaluation", "find_recent"): "plexus_evaluation_find_recent",
    ("evaluation", "compare"): "plexus_evaluation_compare",
    (
        "dataset",
        "build_from_feedback_window",
    ): "plexus_dataset_build_from_feedback_window",
    ("dataset", "check_associated"): "plexus_dataset_check_associated",
    ("report", "configurations_list"): "plexus_report_configurations_list",
    ("procedure", "info"): "plexus_procedure_info",
    ("procedure", "list"): "plexus_procedure_list",
    ("procedure", "chat_sessions"): "plexus_procedure_chat_sessions",
    ("procedure", "chat_messages"): "plexus_procedure_chat_messages",
}


# Per-method handlers implemented directly on PlexusRuntimeModule (no MCP loopback).
# Each (namespace, method) here MUST NOT also appear in MCP_TOOL_MAP — every
# method has exactly one dispatcher.
DIRECT_HANDLERS: dict[tuple[str, str], str] = {
    ("feedback", "find"): "_call_feedback",
    ("evaluation", "info"): "_call_evaluation_info",
    ("evaluation", "run"): "_call_evaluation_run",
    ("report", "run"): "_call_report_run",
    ("procedure", "run"): "_call_procedure_run",
    ("handle", "peek"): "_call_handle",
    ("handle", "status"): "_call_handle",
    ("handle", "await"): "_call_handle",
    ("handle", "cancel"): "_call_handle",
}


def _default_feedback_finder(args: dict[str, Any]) -> dict[str, Any]:
    """Run the production plexus.feedback.find chain.

    Lifted from MCP/tools/feedback/feedback.py so the Tactus host module no
    longer has to bounce back through FastMCP for this read-only call.
    """

    from plexus.cli.feedback.feedback_service import FeedbackService
    from plexus.cli.report.utils import resolve_account_id_for_command
    from plexus.cli.shared.client_utils import create_client
    from plexus.cli.shared.memoized_resolvers import (
        memoized_resolve_score_identifier,
        memoized_resolve_scorecard_identifier,
    )

    scorecard_name = args.get("scorecard_name") or args.get("scorecard")
    score_name = args.get("score_name") or args.get("score")
    if not scorecard_name or not score_name:
        raise ValueError("plexus.feedback.find requires scorecard_name and score_name")

    days = int(args["days"]) if args.get("days") is not None else 7
    limit = int(args["limit"]) if args.get("limit") is not None else None
    offset = int(args["offset"]) if args.get("offset") is not None else None
    prioritize_edit_comments = bool(args.get("prioritize_edit_comments", True))

    client = create_client()
    account_id = resolve_account_id_for_command(client, None)
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


def _default_evaluation_runner(args: dict[str, Any], mcp: FastMCP) -> dict[str, Any]:
    """Dispatch evaluation.run directly through the Plexus CLI in async mode."""

    import shutil
    import subprocess

    scorecard_name = args.get("scorecard_name") or args.get("scorecard")
    if not scorecard_name:
        raise ValueError("plexus.evaluation.run requires scorecard_name")

    evaluation_type = str(args.get("evaluation_type") or "accuracy").strip().lower()
    plexus_bin = shutil.which("plexus") or "plexus"

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
        ]
        _append_optional_cli_arg(cmd, "--days", args.get("days"))
        _append_optional_cli_arg(cmd, "--version", args.get("version"))
        _append_optional_cli_arg(cmd, "--sample-seed", args.get("sample_seed"))
        _append_optional_cli_arg(
            cmd, "--max-category-summary-items", args.get("max_category_summary_items")
        )
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
        if args.get("yaml", True):
            cmd.append("--yaml")
    else:
        raise ValueError(
            "plexus.evaluation.run evaluation_type must be 'accuracy' or 'feedback'"
        )

    _append_optional_cli_arg(cmd, "--baseline", args.get("baseline"))
    _append_optional_cli_arg(cmd, "--current-baseline", args.get("current_baseline"))
    _append_optional_cli_arg(cmd, "--notes", args.get("notes"))

    child_budget = args.get("budget")
    env = os.environ.copy()
    if isinstance(child_budget, dict):
        env["PLEXUS_CHILD_BUDGET"] = json.dumps(_jsonable(child_budget), sort_keys=True)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )
    return {
        "status": "dispatched",
        "process_id": process.pid,
        "command": cmd,
        "evaluation_type": evaluation_type,
        "scorecard": scorecard_name,
        "score": args.get("score_name") or args.get("score"),
        "child_budget": _jsonable(child_budget),
        "message": "Evaluation dispatched in background.",
        "dashboard_url": "https://lab.callcriteria.com/lab/evaluations",
    }


def _append_optional_cli_arg(cmd: list[str], flag: str, value: Any) -> None:
    if value is not None and value != "":
        cmd.extend([flag, str(value)])


def _default_report_runner(args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch report.run directly for durable background report-block work."""

    if args.get("config_id"):
        raise ValueError(
            "plexus.report.run async handles currently require block_class; "
            "configuration report handles need a dedicated report task dispatch path"
        )
    block_class = args.get("block_class")
    if not block_class:
        raise ValueError("plexus.report.run async requires block_class")

    from plexus.cli.report.utils import resolve_account_id_for_command
    from plexus.cli.shared.client_utils import create_client as create_dashboard_client
    from plexus.reports.service import run_block_cached

    client = create_dashboard_client()
    if not client:
        raise ValueError("Could not create dashboard client")
    account_id = resolve_account_id_for_command(client, args.get("account"))
    if not account_id:
        raise ValueError("Could not determine default account ID")

    output_data, log_output, was_cached = run_block_cached(
        block_class=str(block_class),
        block_config=args.get("block_config") or {},
        account_id=account_id,
        client=client,
        cache_key=args.get("cache_key"),
        ttl_hours=args.get("ttl_hours") if args.get("ttl_hours") is not None else 24,
        fresh=bool(args.get("fresh", False)),
        background=True,
        child_budget=args.get("budget"),
    )
    if not isinstance(output_data, dict):
        raise ValueError(log_output or "Report block background dispatch failed")
    if output_data.get("status") not in {"dispatched", "already_dispatched"}:
        raise ValueError(f"Unexpected report dispatch status: {output_data!r}")
    return {
        **output_data,
        "cached": was_cached,
        "block_class": block_class,
        "child_budget": _jsonable(args.get("budget")),
    }


def _default_procedure_runner(args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch procedure.run directly through ProcedureService async mode."""

    procedure_id = args.get("procedure_id") or args.get("id")
    if not procedure_id:
        raise ValueError("plexus.procedure.run requires procedure_id")

    from plexus.cli.procedure.service import ProcedureService
    from plexus.cli.shared.client_utils import create_client

    client = create_client()
    if not client:
        raise ValueError("Could not create API client")

    options: dict[str, Any] = {
        "async_mode": True,
        "dry_run": bool(args.get("dry_run", False)),
    }
    if args.get("max_iterations") is not None:
        options["max_iterations"] = int(args["max_iterations"])
    if args.get("timeout") is not None:
        options["timeout"] = int(args["timeout"])
    if isinstance(args.get("budget"), dict):
        context = args.get("context") if isinstance(args.get("context"), dict) else {}
        options["context"] = {
            **context,
            "_plexus_child_budget": _jsonable(args["budget"]),
        }

    service = ProcedureService(client)
    result = _run_async_from_sync(service.run_procedure(str(procedure_id), **options))
    if not isinstance(result, dict):
        raise ValueError(
            f"plexus.procedure.run async dispatch returned {type(result).__name__}"
        )
    if result.get("status") == "error" or result.get("error"):
        raise ValueError(str(result.get("error") or result))
    return result


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
    if (namespace, method) == ("scorecards", "info"):
        if "scorecard_identifier" not in normalized:
            for key in ("id", "name", "key", "external_id", "externalId"):
                if normalized.get(key):
                    normalized["scorecard_identifier"] = normalized[key]
                    break
        for key in ("id", "name", "key", "external_id", "externalId"):
            normalized.pop(key, None)
    elif (namespace, method) == ("score", "info"):
        if "score_identifier" not in normalized:
            for key in ("id", "score_id", "score", "name", "key", "external_id", "externalId"):
                if normalized.get(key):
                    normalized["score_identifier"] = normalized[key]
                    break
        if "scorecard_identifier" not in normalized:
            for key in (
                "scorecard_id",
                "scorecard",
                "scorecard_name",
                "scorecard_key",
            ):
                if normalized.get(key):
                    normalized["scorecard_identifier"] = normalized[key]
                    break
        for key in (
            "id",
            "score_id",
            "score",
            "name",
            "key",
            "external_id",
            "externalId",
            "scorecard_id",
            "scorecard",
            "scorecard_name",
            "scorecard_key",
        ):
            normalized.pop(key, None)
    elif (namespace, method) == ("item", "info"):
        if "item_id" not in normalized:
            for key in ("id", "item"):
                if normalized.get(key):
                    normalized["item_id"] = normalized[key]
                    break
        for key in ("id", "item"):
            normalized.pop(key, None)
    elif namespace == "procedure" and method in {
        "list",
        "info",
        "chat_sessions",
        "chat_messages",
    }:
        if "request" in normalized and isinstance(normalized["request"], dict):
            return normalized
        if method == "list":
            account_identifier = (
                normalized.get("account_identifier")
                or normalized.get("account")
                or os.environ.get("PLEXUS_ACCOUNT_KEY")
            )
            if not account_identifier:
                raise ValueError(
                    "plexus.procedure.list requires account_identifier or "
                    "PLEXUS_ACCOUNT_KEY"
                )
            request = {
                "account_identifier": account_identifier,
                "scorecard_identifier": normalized.get("scorecard_identifier")
                or normalized.get("scorecard"),
                "limit": int(normalized.get("limit") or 20),
            }
            normalized = {"request": request}
        elif method == "info":
            procedure_id = normalized.get("procedure_id") or normalized.get("id")
            normalized = {
                "request": {
                    "procedure_id": procedure_id,
                    "include_yaml": bool(normalized.get("include_yaml", False)),
                }
            }
        elif method == "chat_sessions":
            procedure_id = normalized.get("procedure_id") or normalized.get("id")
            normalized = {
                "request": {
                    "procedure_id": procedure_id,
                    "limit": int(normalized.get("limit") or 10),
                }
            }
        elif method == "chat_messages":
            procedure_id = normalized.get("procedure_id") or normalized.get("id")
            normalized = {
                "request": {
                    "procedure_id": procedure_id,
                    "session_id": normalized.get("session_id"),
                    "limit": int(normalized.get("limit") or 50),
                    "show_tool_calls": bool(normalized.get("show_tool_calls", True)),
                    "show_tool_responses": bool(
                        normalized.get("show_tool_responses", True)
                    ),
                }
            }
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
    return public


TERMINAL_HANDLE_STATUSES = frozenset(
    {"completed", "completed_unknown", "failed", "cancelled"}
)


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


class _Namespace:
    def __init__(
        self,
        dispatcher: Callable[[str, str, Any], Any],
        name: str,
        methods: set[str],
    ) -> None:
        self._dispatcher = dispatcher
        self._name = name
        for method_name in methods:
            setattr(self, method_name, self._make_call(method_name))

    def _make_call(self, method_name: str) -> Callable[[Any], Any]:
        def call(args: Any = None) -> Any:
            return self._dispatcher(self._name, method_name, args)

        return call


class PlexusRuntimeModule:
    """Tactus host module exposing curated Plexus runtime namespaces.

    Read-only namespaces with no service-layer dependency are implemented
    directly inside this module (no MCP loopback). The remaining namespaces
    delegate to existing FastMCP tools while the broader service-layer
    refactor is in progress.
    """

    def __init__(
        self,
        mcp: FastMCP,
        trace_id: str | None = None,
        docs_dir: str | None = None,
        budget: BudgetGate | None = None,
        handle_store: TactusHandleStore | None = None,
        feedback_finder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        evaluation_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        evaluation_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        report_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        procedure_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        stream_handler: _MCPStreamEmitter | None = None,
    ) -> None:
        self._mcp = mcp
        self._trace_id = trace_id or str(uuid.uuid4())
        self._docs_dir = docs_dir if docs_dir is not None else PLEXUS_DOCS_DIR
        self._budget = budget if budget is not None else BudgetGate()
        self._handle_store = (
            handle_store if handle_store is not None else _default_handle_store()
        )
        self._feedback_finder = (
            feedback_finder if feedback_finder is not None else _default_feedback_finder
        )
        self._evaluation_info = (
            evaluation_info if evaluation_info is not None else _default_evaluation_info
        )
        self._evaluation_runner = (
            evaluation_runner
            if evaluation_runner is not None
            else lambda args: _default_evaluation_runner(args, self._mcp)
        )
        self._report_runner = (
            report_runner if report_runner is not None else _default_report_runner
        )
        self._procedure_runner = (
            procedure_runner
            if procedure_runner is not None
            else _default_procedure_runner
        )
        self._stream_handler = stream_handler
        self._api_calls: list[str] = []
        self.handle_protocol_required: tuple[str, str] | None = None
        methods_by_namespace: dict[str, set[str]] = {}
        for namespace_name, method_name in MCP_TOOL_MAP.keys():
            methods_by_namespace.setdefault(namespace_name, set()).add(method_name)
        for namespace_name, method_name in DIRECT_HANDLERS.keys():
            methods_by_namespace.setdefault(namespace_name, set()).add(method_name)
        for namespace, methods in methods_by_namespace.items():
            setattr(self, namespace, _Namespace(self._call, namespace, methods))
        self.docs = _Namespace(self._call_docs, "docs", {"list", "get"})
        self.api = _Namespace(self._call_api, "api", {"list"})

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

    def _call(self, namespace: str, method: str, args: Any = None) -> Any:
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

    def _call_feedback(self, namespace: str, method: str, args: Any = None) -> Any:
        if (namespace, method) != ("feedback", "find"):
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("feedback", "find")
        self._record_api_call("feedback", "find")
        try:
            return self._feedback_finder(_args(args))
        finally:
            self._budget.record_after("feedback", "find")

    def _call_evaluation_info(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if (namespace, method) != ("evaluation", "info"):
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("evaluation", "info")
        self._record_api_call("evaluation", "info")
        try:
            return self._evaluation_info(_args(args))
        finally:
            self._budget.record_after("evaluation", "info")

    def _call_evaluation_run(
        self, namespace: str, method: str, args: Any = None
    ) -> Any:
        if (namespace, method) != ("evaluation", "run"):
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        parsed = _args(args)
        if not bool(parsed.get("async")):
            self._record_api_call("evaluation", "run")
            self.handle_protocol_required = ("evaluation", "run")
            raise RequiresHandleProtocol("evaluation", "run")

        self._budget.check_before("evaluation", "run")
        self._record_api_call("evaluation", "run")
        child_budget = self._budget.carve_child(
            "evaluation", "run", parsed.get("budget")
        )
        parsed["budget"] = child_budget
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

    def _call_report_run(self, namespace: str, method: str, args: Any = None) -> Any:
        if (namespace, method) != ("report", "run"):
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        parsed = _args(args)
        if not bool(parsed.get("async")):
            self._record_api_call("report", "run")
            self.handle_protocol_required = ("report", "run")
            raise RequiresHandleProtocol("report", "run")

        self._budget.check_before("report", "run")
        self._record_api_call("report", "run")
        child_budget = self._budget.carve_child("report", "run", parsed.get("budget"))
        parsed["budget"] = child_budget
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
        if (namespace, method) != ("procedure", "run"):
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        parsed = _args(args)
        if not bool(parsed.get("async")):
            self._record_api_call("procedure", "run")
            self.handle_protocol_required = ("procedure", "run")
            raise RequiresHandleProtocol("procedure", "run")

        self._budget.check_before("procedure", "run")
        self._record_api_call("procedure", "run")
        child_budget = self._budget.carve_child(
            "procedure", "run", parsed.get("budget")
        )
        parsed["budget"] = child_budget
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
        if not handle_id:
            raise ValueError(f"plexus.handle.{method} requires id")

        self._budget.check_before("handle", method)
        self._record_api_call("handle", method)
        try:
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
        evaluation_id = dispatch_result.get("evaluation_id") or dispatch_result.get(
            "id"
        )
        if record.get("kind") == "evaluation" and not evaluation_id:
            process_id = dispatch_result.get("process_id")
            if process_id:
                try:
                    os.kill(int(process_id), 0)
                except ProcessLookupError:
                    return self._handle_store.update(
                        handle_id, {"status": "completed_unknown"}
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
            self._budget.check_before("docs", "list")
            self._record_api_call("docs", "list")
            try:
                return self._docs_list()
            finally:
                self._budget.record_after("docs", "list")
        if method == "get":
            parsed = _args(args)
            key = parsed.get("key") or parsed.get("name") or parsed.get("filename")
            if not key:
                raise ValueError("plexus.docs.get requires key, name, or filename")
            self._budget.check_before("docs", "get")
            self._record_api_call("docs", "get")
            try:
                return {"key": key, "content": self._docs_read(key)}
            finally:
                self._budget.record_after("docs", "get")
        raise ValueError(f"Unsupported Plexus runtime API: plexus.docs.{method}")

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
            api.setdefault("plexus.api", []).append("list")
            return {key: sorted(set(values)) for key, values in sorted(api.items())}
        finally:
            self._budget.record_after("api", "list")

    def _docs_list(self) -> list[str]:
        if not os.path.isdir(self._docs_dir):
            raise FileNotFoundError(
                f"Plexus docs directory not found: {self._docs_dir}"
            )
        entries = []
        for name in os.listdir(self._docs_dir):
            stem, ext = os.path.splitext(name)
            if ext.lower() != ".md" or stem.lower() == "readme":
                continue
            entries.append(stem)
        return sorted(entries)

    def _docs_read(self, key: str) -> str:
        if "/" in key or "\\" in key or key.startswith(".") or key == "":
            raise ValueError(f"Invalid plexus.docs key: {key!r}")
        path = os.path.join(self._docs_dir, f"{key}.md")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Unknown plexus docs key: {key}")
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()


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
                value = runtime_result.get("result")
                if ok:
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
) -> dict[str, Any]:
    store = trace_store if trace_store is not None else _default_trace_store()
    started_mono = time.monotonic()
    started_wall = time.time()
    trace_id = str(uuid.uuid4())

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
        stream_handler = (
            _MCPStreamEmitter(trace_id=trace_id, loop=asyncio.get_running_loop())
            if ctx is not None
            else None
        )
        run_task = asyncio.create_task(
            asyncio.to_thread(
                _run_tactus_sync,
                tactus,
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
            )
        )
        if stream_handler is None:
            return await run_task

        while True:
            if run_task.done():
                await asyncio.sleep(0)
                if stream_handler.empty():
                    break
            try:
                event = await asyncio.wait_for(stream_handler.get(), timeout=0.05)
            except asyncio.TimeoutError:
                continue
            await _send_mcp_stream_event(ctx, event)

        return await run_task
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


def register_tactus_tools(mcp: FastMCP) -> None:
    """Register Tactus runtime tools with the MCP server."""

    @mcp.tool()
    async def execute_tactus(
        tactus: Annotated[
            str,
            Field(
                description=(
                    "Tactus code to execute inside the Plexus runtime. The runtime "
                    "injects `plexus`, short helper aliases such as evaluate and "
                    "predict, and canonical namespace_method helpers such as "
                    "evaluation_info, handle_status, docs_get, and api_list."
                )
            ),
        ],
        ctx: Context,
    ) -> dict[str, Any]:
        """
        Execute Tactus code inside the Plexus runtime.

        This single tool is the prototype replacement for broad Plexus MCP tool
        catalogs. The submitted Tactus code receives a host-provided `plexus`
        module, short helper aliases, and canonical namespace_method helper aliases
        for the advertised Plexus runtime APIs. The response envelope returns a
        single structured contract with ok/value/error, conservative cost metadata,
        a trace identifier, partial status, and called Plexus APIs.
        """

        return await _execute_tactus_tool(tactus, mcp, ctx=ctx)
