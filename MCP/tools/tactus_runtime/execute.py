#!/usr/bin/env python3
"""Single-tool Tactus execution prototype for the Plexus MCP server."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
import traceback
import uuid
from typing import Annotated, Any, Callable

from fastmcp import FastMCP
from pydantic import Field

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
    ("evaluate", "evaluation", "run"),
    ("predict", "score", "predict"),
    ("score", "score", "info"),
    ("item", "item", "info"),
    ("feedback", "feedback", "find"),
    ("dataset", "dataset", "build_from_feedback_window"),
    ("report", "report", "run"),
    ("procedure", "procedure", "info"),
)

# Long-running operations require handle/streaming semantics that the v0 prototype
# does not yet implement. See Kanbus epic plx-247588 (streaming + handle ergonomics)
# for the contract these will follow. Until that lands, these calls short-circuit
# with a structured `requires_handle_protocol` error rather than blocking the
# synchronous Tactus runtime for tens of minutes or hours.
LONG_RUNNING_METHODS: frozenset[tuple[str, str]] = frozenset(
    {
        ("evaluation", "run"),
        ("report", "run"),
        ("procedure", "run"),
    }
)


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
    ("evaluation", "run"): "plexus_evaluation_run",
    (
        "dataset",
        "build_from_feedback_window",
    ): "plexus_dataset_build_from_feedback_window",
    ("dataset", "check_associated"): "plexus_dataset_check_associated",
    ("report", "configurations_list"): "plexus_report_configurations_list",
    ("report", "run"): "plexus_report_run",
    ("procedure", "info"): "plexus_procedure_info",
    ("procedure", "list"): "plexus_procedure_list",
    ("procedure", "run"): "plexus_procedure_run",
    ("procedure", "chat_sessions"): "plexus_procedure_chat_sessions",
    ("procedure", "chat_messages"): "plexus_procedure_chat_messages",
}


# Per-method handlers implemented directly on PlexusRuntimeModule (no MCP loopback).
# Each (namespace, method) here MUST NOT also appear in MCP_TOOL_MAP — every
# method has exactly one dispatcher.
DIRECT_HANDLERS: dict[tuple[str, str], str] = {
    ("feedback", "find"): "_call_feedback",
    ("evaluation", "info"): "_call_evaluation_info",
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
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        if (
            isinstance(structured, dict)
            and len(structured) == 1
            and "result" in structured
        ):
            return structured["result"]
        return structured

    content = getattr(result, "content", None) or []
    if len(content) == 1 and hasattr(content[0], "text"):
        text = content[0].text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
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
        self.depth_max_observed = 0
        self.exceeded_reason: str | None = None

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
        if elapsed >= self.spec.wallclock_seconds:
            raise self._trip(
                f"wallclock budget exceeded before plexus.{namespace}.{method}: "
                f"{elapsed:.3f}s >= {self.spec.wallclock_seconds:.3f}s"
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
                max(budget.spec.wallclock_seconds - wallclock_seconds, 0.0), 3
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
        docs_dir: str | None = None,
        budget: BudgetGate | None = None,
        feedback_finder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        evaluation_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self._mcp = mcp
        self._docs_dir = docs_dir if docs_dir is not None else PLEXUS_DOCS_DIR
        self._budget = budget if budget is not None else BudgetGate()
        self._feedback_finder = (
            feedback_finder if feedback_finder is not None else _default_feedback_finder
        )
        self._evaluation_info = (
            evaluation_info if evaluation_info is not None else _default_evaluation_info
        )
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
            self._api_calls.append(f"plexus.{namespace}.{method}")
            self.handle_protocol_required = (namespace, method)
            raise RequiresHandleProtocol(namespace, method)
        self._budget.check_before(namespace, method)
        self._api_calls.append(f"plexus.{namespace}.{method}")
        try:
            result = _run_async_from_sync(self._mcp.call_tool(tool_name, _args(args)))
        finally:
            self._budget.record_after(namespace, method)
        return _extract_tool_value(result)

    def _call_feedback(self, namespace: str, method: str, args: Any = None) -> Any:
        if (namespace, method) != ("feedback", "find"):
            raise ValueError(
                f"Unsupported Plexus runtime API: plexus.{namespace}.{method}"
            )
        self._budget.check_before("feedback", "find")
        self._api_calls.append("plexus.feedback.find")
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
        self._api_calls.append("plexus.evaluation.info")
        try:
            return self._evaluation_info(_args(args))
        finally:
            self._budget.record_after("evaluation", "info")

    def _call_docs(self, namespace: str, method: str, args: Any = None) -> Any:
        if method == "list":
            self._budget.check_before("docs", "list")
            self._api_calls.append("plexus.docs.list")
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
            self._api_calls.append("plexus.docs.get")
            try:
                return {"key": key, "content": self._docs_read(key)}
            finally:
                self._budget.record_after("docs", "get")
        raise ValueError(f"Unsupported Plexus runtime API: plexus.docs.{method}")

    def _call_api(self, namespace: str, method: str, args: Any = None) -> Any:
        if method != "list":
            raise ValueError(f"Unsupported Plexus runtime API: plexus.api.{method}")
        self._budget.check_before("api", "list")
        self._api_calls.append("plexus.api.list")
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
    feedback_finder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    evaluation_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
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
                run_id=trace_id,
            )
            if not hasattr(runtime, "register_python_module"):
                raise RuntimeError(
                    "execute_tactus requires TactusRuntime.register_python_module; "
                    "update the installed tactus package to the version specified by pyproject.toml."
                )
            plexus = PlexusRuntimeModule(
                mcp,
                budget=gate,
                feedback_finder=feedback_finder,
                evaluation_info=evaluation_info,
            )
            runtime.register_python_module("plexus", plexus)
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
        return envelope

    return asyncio.run(run())


async def _execute_tactus_tool(
    tactus: str,
    mcp: FastMCP,
    *,
    trace_store: TactusTraceStore | None = None,
    budget: BudgetGate | None = None,
    feedback_finder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    evaluation_info: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
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
        return await asyncio.to_thread(
            _run_tactus_sync,
            tactus,
            mcp,
            trace_id=trace_id,
            trace_store=store,
            budget=budget,
            feedback_finder=feedback_finder,
            evaluation_info=evaluation_info,
        )
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
                    "injects `plexus` plus helper aliases such as evaluate, predict, "
                    "score, item, feedback, dataset, report, and procedure."
                )
            ),
        ],
    ) -> dict[str, Any]:
        """
        Execute Tactus code inside the Plexus runtime.

        This single tool is the prototype replacement for broad Plexus MCP tool
        catalogs. The submitted Tactus code receives a host-provided `plexus`
        module and common helper aliases. The response envelope returns a single
        structured contract with ok/value/error, conservative cost metadata,
        a trace identifier, partial status, and called Plexus APIs.
        """

        return await _execute_tactus_tool(tactus, mcp)
