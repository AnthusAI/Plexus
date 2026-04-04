from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ValueFunctionConfig:
    min_recall: float = 0.40
    min_precision: float = 0.40
    protocol_mismatch_tolerance: float = 0.0
    rca_missing_penalty: float = 0.30
    recall_penalty_weight: float = 0.50
    precision_penalty_weight: float = 0.50


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_metric(metrics: Any, *names: str) -> Optional[float]:
    if isinstance(metrics, dict):
        for name in names:
            if name in metrics:
                return _to_float(metrics.get(name))
    if isinstance(metrics, list):
        target = {n.lower() for n in names}
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            metric_name = str(metric.get("name", "")).lower()
            if metric_name in target:
                return _to_float(metric.get("value"))
            if metric_name == "alignment" and "ac1" in target:
                return _to_float(metric.get("value"))
    return None


def _extract_parameters(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    params = evaluation.get("parameters")
    return params if isinstance(params, dict) else {}


def _has_usable_root_cause(evaluation: Dict[str, Any]) -> bool:
    params = _extract_parameters(evaluation)
    payload = params.get("root_cause")
    return isinstance(payload, dict) and len(payload) > 0


def _root_cause_required(evaluation: Dict[str, Any]) -> bool:
    params = _extract_parameters(evaluation)
    required = params.get("root_cause_required")
    if isinstance(required, bool):
        return required
    incorrect_items = params.get("incorrect_items")
    try:
        return int(incorrect_items or 0) > 0
    except (TypeError, ValueError):
        return False


def is_comparable_protocol(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    pa = _extract_parameters(a)
    pb = _extract_parameters(b)
    fields = ("mode", "days", "max_samples", "sample_seed", "scoreVersionId", "score_id", "scorecard_id")
    for field in fields:
        if pa.get(field) != pb.get(field):
            return False
    return True


def value(evaluation: Dict[str, Any], config: ValueFunctionConfig = ValueFunctionConfig()) -> Dict[str, Any]:
    metrics = evaluation.get("metrics")
    ac1 = _extract_metric(metrics, "ac1", "alignment")
    recall = _extract_metric(metrics, "recall")
    precision = _extract_metric(metrics, "precision")

    penalties = 0.0
    reasons = []

    if ac1 is None:
        return {
            "value": None,
            "status": "inconclusive",
            "reason": "missing_ac1",
            "details": {
                "ac1": ac1,
                "recall": recall,
                "precision": precision,
                "config": asdict(config),
            },
        }

    if recall is not None and recall < config.min_recall:
        gap = config.min_recall - recall
        penalties += gap * config.recall_penalty_weight
        reasons.append("low_recall")
    if precision is not None and precision < config.min_precision:
        gap = config.min_precision - precision
        penalties += gap * config.precision_penalty_weight
        reasons.append("low_precision")

    if _root_cause_required(evaluation) and not _has_usable_root_cause(evaluation):
        penalties += config.rca_missing_penalty
        reasons.append("missing_root_cause")

    return {
        "value": ac1 - penalties,
        "status": "ok",
        "reason": ",".join(reasons) if reasons else "none",
        "details": {
            "ac1": ac1,
            "recall": recall,
            "precision": precision,
            "penalties": penalties,
            "config": asdict(config),
        },
    }


def best_of(a: Dict[str, Any], b: Dict[str, Any], config: ValueFunctionConfig = ValueFunctionConfig()) -> Dict[str, Any]:
    if not is_comparable_protocol(a, b):
        return {"status": "inconclusive", "reason": "protocol_mismatch", "winner": None}

    va = value(a, config=config)
    vb = value(b, config=config)

    if va.get("status") != "ok" or vb.get("status") != "ok":
        return {
            "status": "inconclusive",
            "reason": "insufficient_metrics",
            "winner": None,
            "a": va,
            "b": vb,
        }

    aval = va["value"]
    bval = vb["value"]
    if aval > bval:
        return {"status": "ok", "winner": "a", "a": va, "b": vb}
    if bval > aval:
        return {"status": "ok", "winner": "b", "a": va, "b": vb}
    return {"status": "inconclusive", "reason": "tie", "winner": None, "a": va, "b": vb}
