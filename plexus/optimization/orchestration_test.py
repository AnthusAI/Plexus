from __future__ import annotations


def test_refresh_target_freshness_preserves_full_assessment_fingerprint_only_when_live_evidence_matches() -> None:
    from plexus.optimization.orchestration import refresh_target_freshness

    targets = [
        {
            "scorecard_id": "card",
            "score_id": "good",
            "champion_version": "champion-1",
            "feedback_watermark": "2026-01-02T00:00:00Z",
            "assessment_fingerprint": "full-assessment-fingerprint",
        },
        {"scorecard_id": "card", "score_id": "broken"},
    ]

    def score_reader(_scorecard_id, score_id):
        if score_id == "broken":
            raise RuntimeError("score read failed")
        return {"championVersionId": "champion-1"}

    def feedback_reader(_scorecard_id, _score_id):
        return {"latest_feedback_updated_at": "2026-01-02T00:00:00Z"}

    fingerprints, evidence, failures = refresh_target_freshness(
        targets,
        read_score_info=score_reader,
        read_feedback_latest=feedback_reader,
    )

    expected = {
        "scorecard_id": "card",
        "score_id": "good",
        "champion_version": "champion-1",
        "feedback_watermark": "2026-01-02T00:00:00Z",
    }
    assert fingerprints == {"card:good": "full-assessment-fingerprint"}
    assert evidence == {("card", "good"): expected}
    assert failures[0]["target"]["score_id"] == "broken"
    assert failures[0]["reason"] == "freshness_check_failed"


def _completed_evaluation(evaluation_id: str, baseline_id: str) -> dict:
    return {
        "id": evaluation_id,
        "status": "COMPLETED",
        "score_version_id": "candidate",
        "baseline_evaluation_id": baseline_id,
        "total_items": 100,
        "processed_items": 100,
        "confusion_matrix": {"matrix": {"Yes": {"Yes": 40, "No": 10}}},
        "dataset_class_distribution": [
            {"label": "Yes", "count": 50},
            {"label": "No", "count": 50},
        ],
        "predicted_class_distribution": [
            {"label": "Yes", "count": 48},
            {"label": "No", "count": 52},
        ],
        "root_cause": {"misclassification_analysis": {}},
    }


def test_indexed_review_requires_exact_terminal_matched_safe_evidence() -> None:
    from plexus.optimization.orchestration import (
        build_indexed_optimizer_review_evidence,
    )

    indexed = {
        "summary": {"effective_status": "COMPLETED"},
        "baseline": {
            "original_feedback_evaluation_id": "recent-baseline",
            "original_accuracy_evaluation_id": "historical-baseline",
            "feedback_alignment": 0.60,
            "accuracy_alignment": 0.75,
        },
        "best": {
            "winning_version_id": "candidate",
            "best_feedback_evaluation_id": "recent",
            "best_accuracy_evaluation_id": "historical",
            "feedback_alignment": 0.72,
            "accuracy_alignment": 0.76,
        },
        "review_artifacts": {"artifacts_complete": True, "rca_complete": True},
    }
    evaluations = {
        "recent": _completed_evaluation("recent", "recent-baseline"),
        "historical": _completed_evaluation("historical", "historical-baseline"),
    }

    evidence = build_indexed_optimizer_review_evidence(
        indexed,
        procedure_id="procedure",
        read_evaluation=evaluations.__getitem__,
    )

    assert evidence["matched_recent_evaluation"] is True
    assert evidence["historical_regression_evidence"] is True
    assert evidence["class_specific_metrics"] is True
    assert evidence["prediction_collapse"] is False
    assert evidence["rca_complete"] is True
    assert evidence["artifacts_complete"] is True
    assert evidence["measurable_safe_improvement"] is True


def test_indexed_review_unknown_or_mismatched_evidence_fails_closed() -> None:
    from plexus.optimization.orchestration import (
        build_indexed_optimizer_review_evidence,
    )

    indexed = {
        "summary": {"effective_status": "COMPLETED"},
        "baseline": {
            "original_feedback_evaluation_id": "recent-baseline",
            "original_accuracy_evaluation_id": "historical-baseline",
            "feedback_alignment": 0.60,
            "accuracy_alignment": 0.75,
        },
        "best": {
            "winning_version_id": "candidate",
            "best_feedback_evaluation_id": "recent",
            "best_accuracy_evaluation_id": "historical",
            "feedback_alignment": 0.72,
            "accuracy_alignment": 0.70,
        },
        "review_artifacts": {"artifacts_complete": False, "rca_complete": False},
    }
    recent = _completed_evaluation("recent", "wrong-baseline")
    historical = _completed_evaluation("historical", "historical-baseline")
    historical["predicted_class_distribution"] = [{"label": "Yes", "count": 100}]

    evidence = build_indexed_optimizer_review_evidence(
        indexed,
        procedure_id="procedure",
        read_evaluation={"recent": recent, "historical": historical}.__getitem__,
    )

    assert evidence["matched_recent_evaluation"] is False
    assert evidence["prediction_collapse"] is True
    assert evidence["rca_complete"] is False
    assert evidence["artifacts_complete"] is False
    assert evidence["measurable_safe_improvement"] is False
