from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


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


def _completed_evaluation(
    evaluation_id: str,
    baseline_id: str,
    *,
    version_id: str = "candidate",
) -> dict:
    return {
        "id": evaluation_id,
        "status": "COMPLETED",
        "score_version_id": version_id,
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
    assert evidence["alignment_evidence"] == {
        "recent": {"baseline": 0.60, "candidate": 0.72, "delta": 0.12},
        "regression": {"baseline": 0.75, "candidate": 0.76, "delta": 0.01},
    }


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


def test_indexed_review_uses_winning_candidate_accuracy_reference_after_stale_best_baseline() -> None:
    from plexus.optimization.decision import classify_post_run_review
    from plexus.optimization.orchestration import (
        build_indexed_optimizer_review_evidence,
    )

    indexed = {
        "summary": {"effective_status": "COMPLETED"},
        "baseline": {
            "version_id": "champion",
            "original_feedback_evaluation_id": "recent-baseline",
            "original_accuracy_evaluation_id": "historical-baseline",
            "feedback_alignment": 0.60,
            "accuracy_alignment": 0.75,
        },
        "best": {
            "winning_version_id": "winner",
            "best_feedback_evaluation_id": "winner-recent",
            "best_accuracy_evaluation_id": "historical-baseline",
            "feedback_alignment": 0.72,
            "accuracy_alignment": 0.75,
        },
        "cycles": [{
            "cycle": 1,
            "status": "accepted",
            "accepted": True,
            "candidates": [{
                "version_id": "winner",
                "accuracy_evaluation_id": "winner-historical",
            }],
        }],
        "review_artifacts": {"artifacts_complete": True, "rca_complete": True},
    }
    evaluations = {
        "winner-recent": _completed_evaluation(
            "winner-recent", "recent-baseline", version_id="winner"
        ),
        "historical-baseline": _completed_evaluation(
            "historical-baseline", "prior-historical", version_id="champion"
        ),
        "winner-historical": _completed_evaluation(
            "winner-historical", "historical-baseline", version_id="winner"
        ),
    }
    evaluation_calls: list[str] = []

    evidence = build_indexed_optimizer_review_evidence(
        indexed,
        procedure_id="procedure",
        read_evaluation=lambda evaluation_id: evaluation_calls.append(evaluation_id)
        or evaluations[evaluation_id],
    )
    review = classify_post_run_review(evidence)

    assert evaluation_calls == ["winner-recent", "winner-historical"]
    assert evidence["historical_regression_evidence"] is True
    assert evidence["measurable_safe_improvement"] is True
    assert review["post_run_state"] == "promotion_ready"


@pytest.mark.parametrize(
    "candidate",
    [
        {},
        {"version_id": "other", "accuracy_evaluation_id": "winner-historical"},
    ],
    ids=["missing_candidate", "mismatched_candidate_version"],
)
def test_indexed_review_stale_best_baseline_without_exact_winner_candidate_fails_closed(
    candidate: dict,
) -> None:
    from plexus.optimization.orchestration import (
        build_indexed_optimizer_review_evidence,
    )

    indexed = {
        "summary": {"effective_status": "COMPLETED"},
        "baseline": {
            "version_id": "champion",
            "original_feedback_evaluation_id": "recent-baseline",
            "original_accuracy_evaluation_id": "historical-baseline",
            "feedback_alignment": 0.60,
            "accuracy_alignment": 0.75,
        },
        "best": {
            "winning_version_id": "winner",
            "best_feedback_evaluation_id": "winner-recent",
            "best_accuracy_evaluation_id": "historical-baseline",
            "feedback_alignment": 0.72,
            "accuracy_alignment": 0.75,
        },
        "cycles": [{"candidates": [candidate]}],
        "review_artifacts": {"artifacts_complete": True, "rca_complete": True},
    }
    evaluations = {
        "winner-recent": _completed_evaluation(
            "winner-recent", "recent-baseline", version_id="winner"
        ),
        "historical-baseline": _completed_evaluation(
            "historical-baseline", "prior-historical", version_id="champion"
        ),
    }

    evidence = build_indexed_optimizer_review_evidence(
        indexed,
        procedure_id="procedure",
        read_evaluation=evaluations.__getitem__,
    )

    assert evidence["measurable_safe_improvement"] is False
    assert evidence["historical_regression_evidence"] is False


def _already_good_indexed() -> dict:
    return {
        "summary": {
            "effective_status": "COMPLETED",
            "completion_reason": "baselines_already_good",
            "stop_reason": "already_good",
            "completed_cycles": 0,
        },
        "procedure": {"status": "COMPLETED", "task_status": "COMPLETED"},
        "baseline": {
            "version_id": "champion",
            "original_feedback_evaluation_id": "recent-baseline",
            "original_accuracy_evaluation_id": "historical-baseline",
            "feedback_alignment": 0.99,
            "accuracy_alignment": 0.99,
        },
        "best": {
            "winning_version_id": "champion",
            "last_accepted_version_id": "champion",
        },
        "cycles": [],
        "review_artifacts": {"artifacts_complete": True, "rca_complete": True},
    }


def _already_good_evaluations() -> dict[str, dict]:
    return {
        "recent-baseline": _completed_evaluation(
            "recent-baseline", "prior-recent", version_id="champion"
        ),
        "historical-baseline": _completed_evaluation(
            "historical-baseline", "prior-historical", version_id="champion"
        ),
    }


def test_indexed_review_classifies_exact_completed_already_good_baselines_as_no_safe_improvement() -> None:
    from plexus.optimization.decision import classify_post_run_review
    from plexus.optimization.orchestration import (
        build_indexed_optimizer_review_evidence,
    )

    evidence = build_indexed_optimizer_review_evidence(
        _already_good_indexed(),
        procedure_id="procedure",
        read_evaluation=_already_good_evaluations().__getitem__,
    )
    review = classify_post_run_review(evidence)

    assert evidence["measurable_safe_improvement"] is False
    assert review["post_run_state"] == "no_safe_improvement"


def test_indexed_review_classifies_legacy_completed_already_good_baselines_as_no_safe_improvement() -> None:
    from plexus.optimization.decision import classify_post_run_review
    from plexus.optimization.orchestration import (
        build_indexed_optimizer_review_evidence,
    )

    indexed = _already_good_indexed()
    indexed["summary"]["completion_reason"] = "legacy_baselines_already_good"
    indexed["summary"].pop("stop_reason")
    evidence = build_indexed_optimizer_review_evidence(
        indexed,
        procedure_id="procedure",
        read_evaluation=_already_good_evaluations().__getitem__,
    )
    review = classify_post_run_review(evidence)

    assert evidence["measurable_safe_improvement"] is False
    assert review["post_run_state"] == "no_safe_improvement"


@pytest.mark.parametrize(
    ("mutate_indexed", "mutate_evaluations"),
    [
        (
            lambda indexed: indexed["summary"].update(
                {"completion_reason": "converged", "stop_reason": "converged"}
            ),
            lambda _evaluations: None,
        ),
        (
            lambda indexed: (
                indexed["summary"].pop("completion_reason"),
                indexed["summary"].update(
                    {"procedure_summary": "The baselines are already good."}
                ),
            ),
            lambda _evaluations: None,
        ),
        (
            lambda indexed: indexed["procedure"].update({"task_status": "RUNNING"}),
            lambda _evaluations: None,
        ),
        (
            lambda indexed: indexed["baseline"].update({"accuracy_alignment": 0.98}),
            lambda _evaluations: None,
        ),
        (
            lambda indexed: indexed["baseline"].update(
                {"original_accuracy_evaluation_id": None}
            ),
            lambda _evaluations: None,
        ),
        (
            lambda _indexed: None,
            lambda evaluations: evaluations["historical-baseline"].update(
                {"score_version_id": "wrong-version"}
            ),
        ),
        (
            lambda _indexed: None,
            lambda evaluations: evaluations["historical-baseline"].update(
                {"status": "RUNNING", "processed_items": 99}
            ),
        ),
    ],
    ids=[
        "generic_converged",
        "prose_without_marker",
        "incomplete_task",
        "baseline_below_threshold",
        "regression_baseline_unavailable",
        "mismatched_baseline_version",
        "incomplete_baseline_evaluation",
    ],
)
def test_indexed_review_already_good_counterexamples_fail_closed(
    mutate_indexed,
    mutate_evaluations,
) -> None:
    from plexus.optimization.decision import classify_post_run_review
    from plexus.optimization.orchestration import (
        build_indexed_optimizer_review_evidence,
    )

    indexed = _already_good_indexed()
    evaluations = _already_good_evaluations()
    mutate_indexed(indexed)
    mutate_evaluations(evaluations)

    evidence = build_indexed_optimizer_review_evidence(
        indexed,
        procedure_id="procedure",
        read_evaluation=evaluations.__getitem__,
    )
    review = classify_post_run_review(evidence)

    assert evidence["measurable_safe_improvement"] is None
    assert review["post_run_state"] == "failed_or_incomplete"


def _all_rejected_indexed(
    *,
    stop_reason: str = "max_iterations",
    completed_cycles: int = 1,
) -> dict:
    return {
        "summary": {
            "effective_status": "COMPLETED",
            "completed_cycles": completed_cycles,
            "stop_reason": stop_reason,
        },
        "baseline": {
            "version_id": "champion",
            "original_feedback_evaluation_id": "recent-baseline",
            "original_accuracy_evaluation_id": "historical-baseline",
            "feedback_alignment": 0.60,
            "accuracy_alignment": 0.75,
        },
        "best": {
            "winning_version_id": "champion",
            "last_accepted_version_id": "champion",
            "best_feedback_evaluation_id": "champion-recent",
            "best_accuracy_evaluation_id": "champion-historical",
            "feedback_alignment": 0.60,
            "accuracy_alignment": 0.75,
        },
        "cycles": [{
            "cycle": 1,
            "status": "rejected",
            "accepted": False,
            "candidates": [
                {
                    "version_id": "candidate-a",
                    "feedback_evaluation_id": "candidate-a-recent",
                    "accuracy_evaluation_id": "candidate-a-historical",
                },
                {
                    "version_id": "candidate-b",
                    "feedback_evaluation_id": "candidate-b-recent",
                    "accuracy_evaluation_id": "candidate-b-historical",
                },
            ],
        }],
        "review_artifacts": {"artifacts_complete": True, "rca_complete": True},
    }


def _all_rejected_evaluations() -> dict[str, dict]:
    return {
        "champion-recent": _completed_evaluation(
            "champion-recent", "recent-baseline", version_id="champion"
        ),
        "champion-historical": _completed_evaluation(
            "champion-historical", "historical-baseline", version_id="champion"
        ),
        "candidate-a-recent": _completed_evaluation(
            "candidate-a-recent", "recent-baseline", version_id="candidate-a"
        ),
        "candidate-a-historical": _completed_evaluation(
            "candidate-a-historical", "historical-baseline", version_id="candidate-a"
        ),
        "candidate-b-recent": _completed_evaluation(
            "candidate-b-recent", "recent-baseline", version_id="candidate-b"
        ),
        "candidate-b-historical": _completed_evaluation(
            "candidate-b-historical", "historical-baseline", version_id="candidate-b"
        ),
    }


def test_indexed_review_classifies_terminal_all_rejected_candidates_as_no_safe_improvement() -> None:
    from plexus.optimization.decision import classify_post_run_review
    from plexus.optimization.orchestration import (
        build_indexed_optimizer_review_evidence,
    )

    evaluation_calls: list[str] = []
    evaluations = _all_rejected_evaluations()

    evidence = build_indexed_optimizer_review_evidence(
        _all_rejected_indexed(),
        procedure_id="procedure",
        read_evaluation=lambda evaluation_id: evaluation_calls.append(evaluation_id)
        or evaluations[evaluation_id],
    )
    review = classify_post_run_review(evidence)

    assert evaluation_calls == [
        "candidate-a-recent",
        "candidate-a-historical",
        "candidate-b-recent",
        "candidate-b-historical",
    ]
    assert evidence["terminal"] is True
    assert evidence["incomplete"] is False
    assert evidence["measurable_safe_improvement"] is False
    assert review["post_run_state"] == "no_safe_improvement"
    assert review["primary_next_action"] == "retain_champion"


@pytest.mark.parametrize(
    ("stop_reason", "completed_cycles", "mutate_evaluations"),
    [
        ("user_stopped", 1, lambda _evaluations: None),
        ("dry_run", 1, lambda _evaluations: None),
        ("error", 1, lambda _evaluations: None),
        ("interrupted", 1, lambda _evaluations: None),
        ("partial_failure", 1, lambda _evaluations: None),
        ("unknown", 1, lambda _evaluations: None),
        ("max_iterations", 2, lambda _evaluations: None),
        (
            "max_iterations",
            1,
            lambda evaluations: evaluations["candidate-b-historical"].update(
                {"status": "RUNNING", "processed_items": 99}
            ),
        ),
        (
            "max_iterations",
            1,
            lambda evaluations: evaluations["candidate-b-recent"].update(
                {"score_version_id": "champion"}
            ),
        ),
        (
            "max_iterations",
            1,
            lambda evaluations: evaluations["candidate-b-historical"].update(
                {"baseline_evaluation_id": "wrong-historical-baseline"}
            ),
        ),
    ],
    ids=[
        "user_stopped",
        "dry_run",
        "error",
        "interrupted",
        "partial_failure",
        "unknown_stop_reason",
        "completed_cycle_count_mismatch",
        "incomplete_candidate_evaluation",
        "wrong_candidate_version",
        "mismatched_frozen_baseline",
    ],
)
def test_indexed_review_all_rejected_counterexamples_fail_closed(
    stop_reason: str,
    completed_cycles: int,
    mutate_evaluations,
) -> None:
    from plexus.optimization.decision import classify_post_run_review
    from plexus.optimization.orchestration import (
        build_indexed_optimizer_review_evidence,
    )

    evaluations = _all_rejected_evaluations()
    mutate_evaluations(evaluations)

    evidence = build_indexed_optimizer_review_evidence(
        _all_rejected_indexed(
            stop_reason=stop_reason,
            completed_cycles=completed_cycles,
        ),
        procedure_id="procedure",
        read_evaluation=evaluations.__getitem__,
    )
    review = classify_post_run_review(evidence)

    assert evidence["measurable_safe_improvement"] is None
    assert review["post_run_state"] == "failed_or_incomplete"
