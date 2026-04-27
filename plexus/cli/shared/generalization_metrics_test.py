from plexus.cli.shared.candidate_assessment_bundle import (
    STAGE_DETERMINISTIC,
    STAGE_RANDOM_GATE,
    STAGE_RANDOM_LOOP,
)
from plexus.cli.shared.generalization_metrics import compute_generalization_metrics


def _stage_pair(base: float, cand: float):
    return {
        "baseline": {"metrics": {"ac1": base}},
        "candidate": {"metrics": {"ac1": cand}},
    }


def test_compute_generalization_metrics_with_two_random_stages():
    stage_runs = {
        STAGE_DETERMINISTIC: _stage_pair(0.60, 0.66),
        STAGE_RANDOM_LOOP: _stage_pair(0.55, 0.58),
        STAGE_RANDOM_GATE: _stage_pair(0.54, 0.57),
    }
    metrics = compute_generalization_metrics(stage_runs)
    assert metrics["random_stage_count"] == 2
    assert round(metrics["baseline_random_mean_ac1"], 4) == 0.545
    assert round(metrics["candidate_random_mean_ac1"], 4) == 0.575
    assert round(metrics["baseline_generalization_gap"], 4) == 0.055
    assert round(metrics["candidate_generalization_gap"], 4) == 0.085
    assert round(metrics["generalization_gap_delta"], 4) == 0.03
    assert metrics["random_delta_stddev"] is not None


def test_compute_generalization_metrics_with_single_random_stage():
    stage_runs = {
        STAGE_DETERMINISTIC: _stage_pair(0.60, 0.63),
        STAGE_RANDOM_LOOP: _stage_pair(0.56, 0.58),
    }
    metrics = compute_generalization_metrics(stage_runs)
    assert metrics["random_stage_count"] == 1
    assert metrics["random_delta_stddev"] == 0.0
    assert metrics["baseline_random_stddev"] == 0.0
    assert metrics["candidate_random_stddev"] == 0.0
