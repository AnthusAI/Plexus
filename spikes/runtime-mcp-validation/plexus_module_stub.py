"""Stub Plexus module for the runtime MCP validation spike.

This module intentionally mirrors the proposed Tactus-facing surface without
touching real Plexus services. The later harness can register a PlexusModule
instance with Tactus so Tactus code can do:

    score{ id = "score_compliance_tone" }

The implementation is fixture-backed and deterministic.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "plexus_stub_data.json"
)


class PlexusStubError(Exception):
    """Structured error surfaced to the validation harness."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }


@dataclass
class StubBudget:
    usd_limit: float = 10.0
    usd_spent: float = 0.0
    tokens_spent: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)

    def debit(
        self,
        *,
        operation: str,
        usd: float = 0.0,
        tokens: int = 0,
        llm_calls: int = 0,
        tool_calls: int = 1,
    ) -> None:
        self.usd_spent += usd
        self.tokens_spent += tokens
        self.llm_calls += llm_calls
        self.tool_calls += tool_calls
        event = {
            "operation": operation,
            "usd": usd,
            "tokens": tokens,
            "llm_calls": llm_calls,
            "tool_calls": tool_calls,
            "usd_spent": round(self.usd_spent, 6),
            "usd_remaining": round(max(self.usd_limit - self.usd_spent, 0.0), 6),
        }
        self.events.append(event)
        if self.usd_spent > self.usd_limit:
            raise PlexusStubError(
                "BUDGET_EXHAUSTED",
                f"Budget exhausted while running {operation}",
                retryable=False,
                details=event,
            )

    def remaining(self) -> dict[str, Any]:
        return {
            "usd_limit": self.usd_limit,
            "usd_spent": round(self.usd_spent, 6),
            "usd_remaining": round(max(self.usd_limit - self.usd_spent, 0.0), 6),
            "tokens_spent": self.tokens_spent,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
        }


@dataclass
class StubContext:
    data: dict[str, Any]
    budget: StubBudget = field(default_factory=StubBudget)
    call_log: list[dict[str, Any]] = field(default_factory=list)
    approvals: list[dict[str, Any]] = field(default_factory=list)
    handles: dict[str, dict[str, Any]] = field(default_factory=dict)
    stream_events: list[dict[str, Any]] = field(default_factory=list)

    def record_call(self, api: str, args: dict[str, Any]) -> None:
        self.call_log.append({"api": api, "args": copy.deepcopy(args)})
        self.budget.debit(operation=api, usd=0.0, tool_calls=1)

    def emit_stream(self, event: dict[str, Any]) -> None:
        self.stream_events.append(copy.deepcopy(event))


def load_fixture(path: str | Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def create_plexus_module(
    *,
    fixture_path: str | Path = DEFAULT_FIXTURE_PATH,
    usd_limit: float = 10.0,
) -> "PlexusModule":
    data = load_fixture(fixture_path)
    context = StubContext(data=data, budget=StubBudget(usd_limit=usd_limit))
    return PlexusModule(context)


def _plain_value(value: Any) -> Any:
    """Convert Tactus tables and nested containers into plain Python values."""

    if isinstance(value, dict):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, list):
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


def _args(value: Any = None, **defaults: Any) -> dict[str, Any]:
    """Normalize Python dicts and Tactus tables into plain dictionaries."""

    result: dict[str, Any] = dict(defaults)
    if value is None:
        return result
    if isinstance(value, dict):
        result.update(_plain_value(value))
        return result
    items = getattr(value, "items", None)
    if callable(items):
        converted = _plain_value(value)
        if not isinstance(converted, dict):
            raise PlexusStubError(
                "INVALID_ARGUMENTS",
                f"Expected table/dict arguments, got {type(converted).__name__}",
                retryable=False,
            )
        result.update(converted)
        return result
    raise PlexusStubError(
        "INVALID_ARGUMENTS",
        f"Expected table/dict arguments, got {type(value).__name__}",
        retryable=False,
    )


def _copy(value: Any) -> Any:
    return copy.deepcopy(value)


def _first(items: Iterable[dict[str, Any]], key: str, value: Any, code: str) -> dict[str, Any]:
    for item in items:
        if item.get(key) == value:
            return item
    raise PlexusStubError(code, f"No fixture found where {key}={value!r}")


def _score_by_identifier(data: dict[str, Any], identifier: str) -> dict[str, Any]:
    for score in data["scores"]:
        if identifier in {score["id"], score["key"], score["name"]}:
            return score
    raise PlexusStubError("SCORE_NOT_FOUND", f"No score found for {identifier!r}")


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "y"}
    return bool(value)


class Namespace:
    def __init__(self, context: StubContext, prefix: str) -> None:
        self._ctx = context
        self._prefix = prefix

    def _call(self, name: str, args: dict[str, Any]) -> None:
        self._ctx.record_call(f"{self._prefix}.{name}", args)


class ScorecardsNamespace(Namespace):
    def list(self, args: Any = None) -> list[dict[str, Any]]:
        parsed = _args(args)
        self._call("list", parsed)
        scorecards = self._ctx.data["scorecards"]
        account = parsed.get("account")
        if account:
            scorecards = [s for s in scorecards if s["account"] == account]
        return _copy(scorecards)

    def info(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("info", parsed)
        scorecard = _first(
            self._ctx.data["scorecards"],
            "id",
            parsed.get("id") or parsed.get("scorecard_id"),
            "SCORECARD_NOT_FOUND",
        )
        result = _copy(scorecard)
        result["scores"] = [
            _copy(score)
            for score in self._ctx.data["scores"]
            if score["id"] in scorecard["scores"]
        ]
        return result


class ScoreNamespace(Namespace):
    def info(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("info", parsed)
        identifier = parsed.get("id") or parsed.get("score_id") or parsed.get("key") or parsed.get("name")
        return _copy(_score_by_identifier(self._ctx.data, identifier))

    def evaluations(self, args: Any = None) -> list[dict[str, Any]]:
        parsed = _args(args)
        self._call("evaluations", parsed)
        score = _score_by_identifier(
            self._ctx.data,
            parsed.get("id") or parsed.get("score_id") or parsed.get("score"),
        )
        evaluations = [
            item for item in self._ctx.data["evaluations"] if item["score_id"] == score["id"]
        ]
        evaluations.sort(key=lambda item: item["created_at"], reverse=True)
        limit = parsed.get("limit")
        return _copy(evaluations[: int(limit)] if limit else evaluations)

    def predict(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("predict", parsed)
        score = _score_by_identifier(
            self._ctx.data,
            parsed.get("id") or parsed.get("score_id") or parsed.get("score"),
        )
        item_id = parsed.get("item_id") or parsed.get("item")
        _first(self._ctx.data["items"], "id", item_id, "ITEM_NOT_FOUND")
        for prediction in self._ctx.data["predictions"]:
            if prediction["score_id"] == score["id"] and prediction["item_id"] == item_id:
                cost = prediction.get("cost", {})
                self._ctx.budget.debit(
                    operation="plexus.score.predict.cost",
                    usd=float(cost.get("usd", 0.0)),
                    tokens=int(cost.get("tokens", 0)),
                    llm_calls=int(cost.get("llm_calls", 0)),
                    tool_calls=0,
                )
                return _copy(prediction)
        raise PlexusStubError(
            "PREDICTION_NOT_FOUND",
            f"No prediction fixture for score={score['id']} item={item_id}",
        )

    def set_champion(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("set_champion", parsed)
        score = _score_by_identifier(
            self._ctx.data,
            parsed.get("id") or parsed.get("score_id") or parsed.get("score"),
        )
        target = parsed.get("version_id") or parsed.get("version")
        if not parsed.get("no_confirm"):
            approval = {
                "operation": "plexus.score.set_champion",
                "score_id": score["id"],
                "current_version_id": score["champion_version_id"],
                "target_version_id": target,
                "status": "requested",
            }
            self._ctx.approvals.append(approval)
            return {"approval_requested": True, "mutation": approval}
        return {
            "approval_requested": False,
            "changed": True,
            "score_id": score["id"],
            "previous_version_id": score["champion_version_id"],
            "champion_version_id": target,
        }


class ItemNamespace(Namespace):
    def info(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("info", parsed)
        return _copy(
            _first(
                self._ctx.data["items"],
                "id",
                parsed.get("id") or parsed.get("item_id"),
                "ITEM_NOT_FOUND",
            )
        )

    def last(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("last", parsed)
        return _copy(self._ctx.data["items"][-1])


class FeedbackNamespace(Namespace):
    def find(self, args: Any = None) -> list[dict[str, Any]]:
        parsed = _args(args)
        self._call("find", parsed)
        score = _score_by_identifier(
            self._ctx.data,
            parsed.get("score_id") or parsed.get("score") or "score_compliance_tone",
        )
        kind = parsed.get("kind")
        approved = parsed.get("approved")
        items = [item for item in self._ctx.data["feedback_items"] if item["score_id"] == score["id"]]
        if kind:
            items = [item for item in items if item["kind"] == kind]
        if approved is not None:
            items = [item for item in items if item["approved"] == approved]
        return _copy(items)

    def alignment(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("alignment", parsed)
        score = _score_by_identifier(
            self._ctx.data,
            parsed.get("score_id") or parsed.get("score") or "score_compliance_tone",
        )
        return _copy(self._ctx.data["feedback_alignment"][score["id"]])


class EvaluationNamespace(Namespace):
    def info(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("info", parsed)
        return _copy(
            _first(
                self._ctx.data["evaluations"],
                "id",
                parsed.get("id") or parsed.get("evaluation_id"),
                "EVALUATION_NOT_FOUND",
            )
        )

    def find_recent(self, args: Any = None) -> list[dict[str, Any]]:
        parsed = _args(args)
        self._call("find_recent", parsed)
        score_id = parsed.get("score_id")
        items = self._ctx.data["evaluations"]
        if score_id:
            items = [item for item in items if item["score_id"] == score_id]
        items = sorted(items, key=lambda item: item["created_at"], reverse=True)
        return _copy(items[: int(parsed.get("limit", 5))])

    def compare(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("compare", parsed)
        baseline = self.info({"id": parsed.get("baseline_id") or parsed.get("baseline_evaluation_id")})
        candidate = self.info({"id": parsed.get("candidate_id") or parsed.get("candidate_evaluation_id")})
        deltas = {
            metric: round(candidate[metric] - baseline[metric], 6)
            for metric in ("ac1", "accuracy", "recall", "precision")
        }
        biggest_metric = max(deltas, key=lambda key: abs(deltas[key]))
        assessment = "improvement" if deltas["ac1"] > 0 and deltas["recall"] >= 0 else "regression"
        if deltas["accuracy"] > 0 and deltas["recall"] < 0:
            assessment = "regression"
        return {
            "baseline_evaluation_id": baseline["id"],
            "candidate_evaluation_id": candidate["id"],
            "deltas": deltas,
            "biggest_metric_movement": biggest_metric,
            "assessment": assessment,
        }

    def run(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("run", parsed)
        score = _score_by_identifier(
            self._ctx.data,
            parsed.get("score_id") or parsed.get("score") or "score_compliance_tone",
        )
        item_count = int(
            parsed.get("item_count")
            or parsed.get("limit")
            or parsed.get("max_items")
            or parsed.get("last_n")
            or 200
        )
        async_requested = _as_bool(parsed.get("async") or parsed.get("async_"))
        evaluation_id = f"eval_stub_{score['key']}_{item_count}"
        if async_requested:
            handle_id = f"handle_{evaluation_id}"
            handle = {
                "id": handle_id,
                "kind": "evaluation",
                "status": "running",
                "evaluation_id": evaluation_id,
                "score_id": score["id"],
                "items_total": item_count,
                "items_done": 0,
                "cost_so_far": 0.0,
            }
            self._ctx.handles[handle_id] = handle
            self._ctx.emit_stream(
                {
                    "event": "handle_created",
                    "handle_id": handle_id,
                    "kind": "evaluation",
                    "status": "running",
                }
            )
            return _copy(handle)

        return self._run_synchronously(score, evaluation_id, item_count)

    def _run_synchronously(
        self,
        score: dict[str, Any],
        evaluation_id: str,
        item_count: int,
    ) -> dict[str, Any]:
        progress_events: list[dict[str, Any]] = []
        processed = 0
        cost_per_item = 0.0002
        progress_interval = max(item_count // 4, 1)
        try:
            for index in range(1, item_count + 1):
                self._ctx.budget.debit(
                    operation="plexus.evaluation.run.item",
                    usd=cost_per_item,
                    tokens=12,
                    llm_calls=0,
                    tool_calls=0,
                )
                processed = index
                if index == 1 or index % progress_interval == 0 or index == item_count:
                    event = {
                        "event": "progress",
                        "evaluation_id": evaluation_id,
                        "score_id": score["id"],
                        "items_done": index,
                        "items_total": item_count,
                        "current_metric": round(0.75 + 0.15 * (index / item_count), 4),
                        "cost_so_far": round(processed * cost_per_item, 6),
                    }
                    progress_events.append(event)
                    self._ctx.emit_stream(event)
        except PlexusStubError as exc:
            if exc.code != "BUDGET_EXHAUSTED":
                raise
            return {
                "id": evaluation_id,
                "score_id": score["id"],
                "status": "budget_exhausted",
                "partial": True,
                "processed_items": processed,
                "items_total": item_count,
                "final_ac1": None,
                "total_cost": round(processed * cost_per_item, 6),
                "progress_events": progress_events,
                "error": exc.to_dict(),
            }

        return {
            "id": evaluation_id,
            "score_id": score["id"],
            "status": "completed",
            "partial": False,
            "processed_items": processed,
            "items_total": item_count,
            "final_ac1": 0.9,
            "total_cost": round(processed * cost_per_item, 6),
            "progress_events": progress_events,
        }


class DocsNamespace(Namespace):
    def list(self, args: Any = None) -> list[dict[str, str]]:
        parsed = _args(args)
        self._call("list", parsed)
        return [
            {"key": key, "summary": value.split(".")[0] + "."}
            for key, value in sorted(self._ctx.data["docs"].items())
        ]

    def get(self, args: Any = None) -> dict[str, str]:
        parsed = _args(args)
        self._call("get", parsed)
        key = parsed.get("key") or parsed.get("name") or parsed.get("id")
        if key not in self._ctx.data["docs"]:
            raise PlexusStubError("DOC_NOT_FOUND", f"No doc fixture for {key!r}")
        return {"key": key, "content": self._ctx.data["docs"][key]}


class BudgetNamespace(Namespace):
    def __init__(self, context: StubContext) -> None:
        super().__init__(context, "plexus.budget")
        # Tactus wants `plexus.budget.with{...}`; Python cannot define `with`.
        setattr(self, "with", self.with_)

    def remaining(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("remaining", parsed)
        return self._ctx.budget.remaining()

    def with_(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("with", parsed)
        return {
            "sub_budget": {
                "usd": parsed.get("usd"),
                "note": "Spike stub records sub-budget requests but does not execute callbacks.",
            },
            "remaining": self._ctx.budget.remaining(),
        }


class CostNamespace(Namespace):
    def analysis(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("analysis", parsed)
        score_id = parsed.get("score_id") or parsed.get("score")
        if score_id:
            score = _score_by_identifier(self._ctx.data, score_id)
            return {
                "score_id": score["id"],
                "typical_cost_usd": score["typical_cost_usd"],
                "typical_latency_ms": score["typical_latency_ms"],
            }
        return {"total_spent_usd": self._ctx.budget.usd_spent}


class DatasetNamespace(Namespace):
    def build_from_feedback_window(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("build_from_feedback_window", parsed)
        score = _score_by_identifier(
            self._ctx.data,
            parsed.get("score_id") or parsed.get("score") or "score_compliance_tone",
        )
        days = int(parsed.get("window_days") or parsed.get("window") or 14)
        for dataset in self._ctx.data["datasets"]:
            if dataset["score_id"] == score["id"] and dataset["source_window_days"] == days:
                self._ctx.budget.debit(
                    operation="plexus.dataset.build_from_feedback_window.cost",
                    usd=round(dataset["row_count"] * 0.00001, 6),
                    tool_calls=0,
                )
                return _copy(dataset)
        raise PlexusStubError(
            "DATASET_NOT_FOUND",
            f"No dataset fixture for score={score['id']} window_days={days}",
        )

    def check_associated(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("check_associated", parsed)
        dataset = _first(
            self._ctx.data["datasets"],
            "id",
            parsed.get("dataset_id") or parsed.get("id"),
            "DATASET_NOT_FOUND",
        )
        return {"dataset_id": dataset["id"], "associated": dataset["associated"]}


class ReportNamespace(Namespace):
    def configurations_list(self, args: Any = None) -> list[dict[str, Any]]:
        parsed = _args(args)
        self._call("configurations_list", parsed)
        return _copy(self._ctx.data["report_configurations"])

    def run(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("run", parsed)
        configuration_id = parsed.get("configuration_id")
        report = _first(
            self._ctx.data["reports"],
            "configuration_id",
            configuration_id,
            "REPORT_CONFIGURATION_NOT_FOUND",
        )
        return _copy(report)


class HandleNamespace(Namespace):
    def __init__(self, context: StubContext, prefix: str) -> None:
        super().__init__(context, prefix)
        # Tactus wants `plexus.handle.await{...}`; Python reserves `await`.
        setattr(self, "await", self.await_)

    def status(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("status", parsed)
        handle_id = parsed.get("id") or parsed.get("handle_id")
        if handle_id not in self._ctx.handles:
            raise PlexusStubError("HANDLE_NOT_FOUND", f"No handle fixture for {handle_id!r}")
        return _copy(self._ctx.handles[handle_id])

    def await_(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("await", parsed)
        handle = self.status(parsed)
        if handle["kind"] != "evaluation":
            raise PlexusStubError("UNSUPPORTED_HANDLE_KIND", f"Cannot await {handle['kind']}")
        score = _score_by_identifier(self._ctx.data, handle["score_id"])
        result = EvaluationNamespace(self._ctx, "plexus.evaluation")._run_synchronously(
            score,
            handle["evaluation_id"],
            int(handle["items_total"]),
        )
        self._ctx.handles[handle["id"]] = {
            **handle,
            "status": result["status"],
            "items_done": result["processed_items"],
            "cost_so_far": result["total_cost"],
            "result": result,
        }
        return _copy(self._ctx.handles[handle["id"]])

    def cancel(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("cancel", parsed)
        handle_id = parsed.get("id") or parsed.get("handle_id")
        if handle_id not in self._ctx.handles:
            raise PlexusStubError("HANDLE_NOT_FOUND", f"No handle fixture for {handle_id!r}")
        self._ctx.handles[handle_id]["status"] = "cancelled"
        self._ctx.emit_stream(
            {"event": "handle_cancelled", "handle_id": handle_id, "status": "cancelled"}
        )
        return _copy(self._ctx.handles[handle_id])


class ProcedureNamespace(Namespace):
    def info(self, args: Any = None) -> dict[str, Any]:
        parsed = _args(args)
        self._call("info", parsed)
        return _copy(
            _first(
                self._ctx.data["procedures"],
                "id",
                parsed.get("id") or parsed.get("procedure_id"),
                "PROCEDURE_NOT_FOUND",
            )
        )

    def chat_sessions(self, args: Any = None) -> list[dict[str, Any]]:
        parsed = _args(args)
        self._call("chat_sessions", parsed)
        procedure_id = parsed.get("procedure_id") or parsed.get("id")
        return _copy(
            [
                session
                for session in self._ctx.data["chat_sessions"]
                if session["procedure_id"] == procedure_id
            ]
        )

    def chat_messages(self, args: Any = None) -> list[dict[str, Any]]:
        parsed = _args(args)
        self._call("chat_messages", parsed)
        session_id = parsed.get("session_id") or parsed.get("id")
        messages = [
            message
            for message in self._ctx.data["chat_messages"]
            if message["session_id"] == session_id
        ]
        messages.sort(key=lambda item: item["created_at"], reverse=True)
        limit = int(parsed.get("limit", len(messages)))
        return _copy(list(reversed(messages[:limit])))


class ApiNamespace(Namespace):
    def list(self, args: Any = None) -> dict[str, list[str]]:
        parsed = _args(args)
        self._call("list", parsed)
        return {
            "plexus.scorecards": ["list", "info"],
            "plexus.score": ["info", "evaluations", "predict", "set_champion"],
            "plexus.item": ["info", "last"],
            "plexus.feedback": ["find", "alignment"],
            "plexus.evaluation": ["info", "find_recent", "compare", "run"],
            "plexus.docs": ["list", "get"],
            "plexus.budget": ["remaining", "with"],
            "plexus.cost": ["analysis"],
            "plexus.dataset": ["build_from_feedback_window", "check_associated"],
            "plexus.report": ["configurations_list", "run"],
            "plexus.handle": ["status", "await", "cancel"],
            "plexus.procedure": ["info", "chat_sessions", "chat_messages"],
        }


class PlexusModule:
    """Fixture-backed Plexus module exposed to Tactus during the spike."""

    def __init__(self, context: StubContext) -> None:
        self._ctx = context
        self.scorecards = ScorecardsNamespace(context, "plexus.scorecards")
        self.score = ScoreNamespace(context, "plexus.score")
        self.item = ItemNamespace(context, "plexus.item")
        self.feedback = FeedbackNamespace(context, "plexus.feedback")
        self.evaluation = EvaluationNamespace(context, "plexus.evaluation")
        self.docs = DocsNamespace(context, "plexus.docs")
        self.budget = BudgetNamespace(context)
        self.cost = CostNamespace(context, "plexus.cost")
        self.dataset = DatasetNamespace(context, "plexus.dataset")
        self.report = ReportNamespace(context, "plexus.report")
        self.handle = HandleNamespace(context, "plexus.handle")
        self.procedure = ProcedureNamespace(context, "plexus.procedure")
        self.api = ApiNamespace(context, "plexus.api")

    def call_log(self) -> list[dict[str, Any]]:
        return _copy(self._ctx.call_log)

    def approvals(self) -> list[dict[str, Any]]:
        return _copy(self._ctx.approvals)

    def budget_events(self) -> list[dict[str, Any]]:
        return _copy(self._ctx.budget.events)

    def stream_events(self) -> list[dict[str, Any]]:
        return _copy(self._ctx.stream_events)


__all__ = [
    "DEFAULT_FIXTURE_PATH",
    "PlexusModule",
    "PlexusStubError",
    "StubBudget",
    "StubContext",
    "create_plexus_module",
    "load_fixture",
]
