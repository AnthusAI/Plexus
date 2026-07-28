from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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
        return {
            "championVersionId": "champion-1",
            "updatedAt": "2024-01-02T00:00:00Z",
            "versions": [{"id": "version-1", "createdAt": "2024-01-01T00:00:00Z"}],
        }

    def feedback_reader(_scorecard_id, _score_id):
        return {"latest_feedback_updated_at": "2026-01-02T00:00:00Z"}

    fingerprints, evidence, failures = refresh_target_freshness(
        targets,
        read_score_info=score_reader,
        read_feedback_latest=feedback_reader,
        now=datetime(2026, 7, 28, 12, tzinfo=timezone.utc),
    )

    expected = {
        "scorecard_id": "card",
        "score_id": "good",
        "champion_version": "champion-1",
        "feedback_watermark": "2026-01-02T00:00:00Z",
        "score_updated_at": "2024-01-02T00:00:00Z",
        "newest_version_id": "version-1",
        "newest_version_created_at": "2024-01-01T00:00:00Z",
        "activity_timestamp": "2024-01-02T00:00:00Z",
        "activity_as_of": "2026-07-28T12:00:00Z",
    }
    assert fingerprints == {"card:good": "full-assessment-fingerprint"}
    assert evidence == {("card", "good"): expected}
    assert failures[0]["target"]["score_id"] == "broken"
    assert failures[0]["reason"] == "freshness_check_failed"


def test_refresh_target_freshness_rejects_recent_score_activity_after_assessment() -> None:
    """A newly touched score must not immediately trigger another optimizer run."""
    from plexus.optimization.orchestration import refresh_target_freshness

    now = datetime(2026, 7, 28, 12, tzinfo=timezone.utc)
    fingerprints, evidence, failures = refresh_target_freshness(
        [{
            "scorecard_id": "card",
            "score_id": "score",
            "champion_version": "champion-1",
            "feedback_watermark": "2026-07-01T00:00:00Z",
            "assessment_fingerprint": "assessment-fingerprint",
        }],
        read_score_info=lambda _scorecard_id, _score_id: {
            "championVersionId": "champion-2",
            "updatedAt": _utc_timestamp(now - timedelta(days=1)),
            "versions": [{
                "id": "new-version",
                "createdAt": _utc_timestamp(now - timedelta(hours=1)),
            }],
        },
        read_feedback_latest=lambda _scorecard_id, _score_id: {
            "latest_feedback_updated_at": "2026-07-01T00:00:00Z",
        },
        now=now,
    )

    assert fingerprints == {}
    assert evidence == {}
    assert failures == [{
        "target": {
            "scorecard_id": "card",
            "score_id": "score",
            "champion_version": "champion-1",
            "feedback_watermark": "2026-07-01T00:00:00Z",
            "assessment_fingerprint": "assessment-fingerprint",
        },
        "reason": "recent_score_activity",
        "score_updated_at": "2026-07-27T12:00:00Z",
        "newest_version_id": "new-version",
        "newest_version_created_at": "2026-07-28T11:00:00Z",
        "activity_timestamp": "2026-07-28T11:00:00Z",
        "activity_as_of": "2026-07-28T12:00:00Z",
    }]


def test_refresh_target_freshness_accepts_unchanged_score_activity_older_than_seven_days() -> None:
    from plexus.optimization.orchestration import refresh_target_freshness

    now = datetime(2026, 7, 28, 12, tzinfo=timezone.utc)
    target = {
        "scorecard_id": "card",
        "score_id": "score",
        "champion_version": "champion-1",
        "feedback_watermark": "2026-07-01T00:00:00Z",
        "assessment_fingerprint": "assessment-fingerprint",
    }
    fingerprints, evidence, failures = refresh_target_freshness(
        [target],
        read_score_info=lambda _scorecard_id, _score_id: {
            "championVersionId": "champion-1",
            "updatedAt": _utc_timestamp(now - timedelta(days=8)),
            "versions": [{
                "id": "old-version",
                "createdAt": _utc_timestamp(now - timedelta(days=9)),
            }],
        },
        read_feedback_latest=lambda _scorecard_id, _score_id: {
            "latest_feedback_updated_at": "2026-07-01T00:00:00Z",
        },
        now=now,
    )

    assert fingerprints == {"card:score": "assessment-fingerprint"}
    assert evidence == {
        ("card", "score"): {
            "scorecard_id": "card",
            "score_id": "score",
            "champion_version": "champion-1",
            "feedback_watermark": "2026-07-01T00:00:00Z",
            "score_updated_at": "2026-07-20T12:00:00Z",
            "newest_version_id": "old-version",
            "newest_version_created_at": "2026-07-19T12:00:00Z",
            "activity_timestamp": "2026-07-20T12:00:00Z",
            "activity_as_of": "2026-07-28T12:00:00Z",
        }
    }
    assert failures == []


def test_refresh_target_freshness_fails_closed_when_live_score_activity_is_missing() -> None:
    from plexus.optimization.orchestration import refresh_target_freshness

    fingerprints, evidence, failures = refresh_target_freshness(
        [{
            "scorecard_id": "card",
            "score_id": "score",
            "champion_version": "champion-1",
            "feedback_watermark": "2026-07-01T00:00:00Z",
            "assessment_fingerprint": "assessment-fingerprint",
        }],
        read_score_info=lambda _scorecard_id, _score_id: {
            "championVersionId": "champion-1",
        },
        read_feedback_latest=lambda _scorecard_id, _score_id: {
            "latest_feedback_updated_at": "2026-07-01T00:00:00Z",
        },
    )

    assert fingerprints == {}
    assert evidence == {}
    assert failures[0]["reason"] == "freshness_check_failed"
    assert "score activity" in failures[0]["error"].lower()


def test_refresh_target_freshness_freezes_one_activity_time_for_the_batch() -> None:
    from plexus.optimization.orchestration import refresh_target_freshness

    targets = [
        {
            "scorecard_id": "card",
            "score_id": score_id,
            "champion_version": "champion-1",
            "feedback_watermark": "2026-01-01T00:00:00Z",
            "assessment_fingerprint": f"fingerprint-{score_id}",
        }
        for score_id in ("one", "two")
    ]
    _, evidence, failures = refresh_target_freshness(
        targets,
        read_score_info=lambda _card, score_id: {
            "championVersionId": "champion-1",
            "updatedAt": "2024-01-02T00:00:00Z",
            "versions": [{
                "id": f"version-{score_id}",
                "createdAt": "2024-01-01T00:00:00Z",
            }],
        },
        read_feedback_latest=lambda _card, _score: {
            "latest_feedback_updated_at": "2026-01-01T00:00:00Z",
        },
    )

    assert failures == []
    assert len({row["activity_as_of"] for row in evidence.values()}) == 1


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
