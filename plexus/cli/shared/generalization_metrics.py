from __future__ import annotations

from math import sqrt
from typing import Any, Dict, List, Optional

from plexus.cli.shared.candidate_assessment_bundle import (
    STAGE_DETERMINISTIC,
    STAGE_RANDOM_GATE,
    STAGE_RANDOM_LOOP,
)


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_ac1(metrics: Any) -> Optional[float]:
    if isinstance(metrics, dict):
        return _to_float(metrics.get("ac1"))
    if isinstance(metrics, list):
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            name = str(metric.get("name", "")).lower()
            if name in {"ac1", "alignment"}:
                return _to_float(metric.get("value"))
    return None


def _mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _stddev(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return 0.0 if len(values) == 1 else None
    m = _mean(values)
    if m is None:
        return None
    variance = sum((v - m) ** 2 for v in values) / len(values)
    return sqrt(variance)


def compute_generalization_metrics(stage_runs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute generalization-gap and stability signals from staged run data.
    """
    if not isinstance(stage_runs, dict):
        raise ValueError("stage_runs must be a dictionary.")

    deterministic = stage_runs.get(STAGE_DETERMINISTIC) or {}
    random_loop = stage_runs.get(STAGE_RANDOM_LOOP) or {}
    random_gate = stage_runs.get(STAGE_RANDOM_GATE) or {}

    baseline_ref_ac1 = _extract_ac1(
        ((deterministic.get("baseline") or {}).get("metrics"))
    )
    candidate_ref_ac1 = _extract_ac1(
        ((deterministic.get("candidate") or {}).get("metrics"))
    )

    baseline_random_values = []
    candidate_random_values = []
    random_delta_values = []
    random_stage_count = 0

    for stage in (random_loop, random_gate):
        if not stage:
            continue
        random_stage_count += 1
        baseline_ac1 = _extract_ac1(((stage.get("baseline") or {}).get("metrics")))
        candidate_ac1 = _extract_ac1(((stage.get("candidate") or {}).get("metrics")))
        if baseline_ac1 is not None:
            baseline_random_values.append(baseline_ac1)
        if candidate_ac1 is not None:
            candidate_random_values.append(candidate_ac1)
        if baseline_ac1 is not None and candidate_ac1 is not None:
            random_delta_values.append(candidate_ac1 - baseline_ac1)

    baseline_random_mean = _mean(baseline_random_values)
    candidate_random_mean = _mean(candidate_random_values)
    baseline_gap = (
        baseline_ref_ac1 - baseline_random_mean
        if baseline_ref_ac1 is not None and baseline_random_mean is not None
        else None
    )
    candidate_gap = (
        candidate_ref_ac1 - candidate_random_mean
        if candidate_ref_ac1 is not None and candidate_random_mean is not None
        else None
    )
    gap_delta = (
        candidate_gap - baseline_gap
        if candidate_gap is not None and baseline_gap is not None
        else None
    )

    return {
        "random_stage_count": random_stage_count,
        "baseline_reference_ac1": baseline_ref_ac1,
        "candidate_reference_ac1": candidate_ref_ac1,
        "baseline_random_mean_ac1": baseline_random_mean,
        "candidate_random_mean_ac1": candidate_random_mean,
        "baseline_generalization_gap": baseline_gap,
        "candidate_generalization_gap": candidate_gap,
        "generalization_gap_delta": gap_delta,
        "random_delta_mean": _mean(random_delta_values),
        "random_delta_stddev": _stddev(random_delta_values),
        "baseline_random_stddev": _stddev(baseline_random_values),
        "candidate_random_stddev": _stddev(candidate_random_values),
    }
