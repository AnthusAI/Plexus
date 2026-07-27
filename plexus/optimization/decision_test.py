from __future__ import annotations

from datetime import datetime, timezone

import pytest

from plexus.optimization.decision import (
    OptimizationDecisionPacket,
    POLICY_PROFILE_V1,
    assess_investment,
    classify_post_run_review,
    dispatch_optimization_operation,
    evidence_fingerprint,
    frozen_utc_window,
    normalize_guideline_state,
    normalize_structural_state,
    rank_portfolio,
    summarize_packets,
    validate_approved_batch,
    validate_run_limits,
    weekly_buckets,
    wilson_interval,
)


def test_packet_has_versioned_transport_independent_contract():
    packet = OptimizationDecisionPacket(
        account_id="account-1",
        scope={"score_id": "score-1"},
        window={"start": "2026-01-01T00:00:00Z", "end": "2026-01-02T00:00:00Z"},
        evidence={"coverage_complete": True},
        states={"readiness": "ready_to_optimize"},
        primary_next_action="run_approved_optimization",
    ).to_dict()

    assert packet["version"] == "optimization-decision-packet-v1"
    assert packet["account_id"] == "account-1"
    assert packet["evidence"]["coverage_complete"] is True
    assert packet["secondary_actions"] == []
    assert packet["blockers"] == []
    assert packet["policy"]["version"] == packet["policy_version"]
    assert packet["fingerprint"] == packet["evidence_fingerprint"]


def test_frozen_utc_window_excludes_current_partial_day():
    window = frozen_utc_window(datetime(2026, 7, 27, 15, 30, tzinfo=timezone.utc))

    assert window == {
        "start": "2026-04-28T00:00:00Z",
        "end": "2026-07-27T00:00:00Z",
        "timezone": "UTC",
        "complete_days": 90,
    }


def test_wilson_interval_and_equality_boundary_are_deterministic():
    lower, upper = wilson_interval(10, 100)

    assert lower == pytest.approx(0.05523, abs=0.00001)
    assert upper == pytest.approx(0.17437, abs=0.00001)
    decision = assess_investment(
        {
            "coverage_complete": True,
            "champion_version": "1",
            "valid_feedback_count": 200,
            "disagreement_count": 0,
            "reachable_classes": ["yes", "no"],
            "final_label_counts": {"yes": 100, "no": 100},
            "weekly_disagreement_rates": [0.10, 0.10, 0.10, 0.10],
            "weekly_ac1_values": [0.80, 0.80, 0.80, 0.80],
            "guideline_state": "consistent",
        }
    )
    assert decision["readiness_state"] == "monitoring_candidate"


def test_weekly_buckets_are_complete_monday_weeks_with_volume_warnings_only():
    buckets = weekly_buckets(
        ["2026-07-20T12:00:00Z", "2026-07-26T23:59:59Z", "2026-07-27T01:00:00Z"],
        window_end="2026-07-27T00:00:00Z",
        weeks=2,
    )

    assert buckets[0]["count"] == 0
    assert buckets[1]["count"] == 2
    assert buckets[1]["low_volume_warning"] is True


def test_low_volume_complete_weekly_metrics_warn_without_blocking_monitoring():
    result = assess_investment(
        {
            "coverage_complete": True,
            "champion_version": "1",
            "valid_feedback_count": 200,
            "disagreement_count": 0,
            "reachable_classes": ["yes", "no"],
            "final_label_counts": {"yes": 100, "no": 100},
            "weekly_buckets": [
                {
                    "valid_feedback_count": 1,
                    "disagreement_rate": 0.0,
                    "ac1": 1.0,
                }
                for _ in range(4)
            ],
            "guideline_state": "consistent",
        }
    )

    assert result["readiness_state"] == "monitoring_candidate"
    assert result["weekly_stability"]["weekly_low_volume_warning"] is True


def test_rank_portfolio_is_stable_and_never_claims_incomplete_coverage_is_exact():
    result = rank_portfolio(
        [
            {"scorecard_id": "a", "score_id": "b", "scorecard_name": "A", "score_name": "Z", "valid_feedback_count": 20, "disagreement_rate": 0.5, "champion_version": "1"},
            {"scorecard_id": "a", "score_id": "a", "scorecard_name": "A", "score_name": "A", "valid_feedback_count": 20, "disagreement_rate": 0.5, "champion_version": "1"},
            {"scorecard_id": "a", "score_id": "disabled", "scorecard_name": "A", "score_name": "D", "valid_feedback_count": 99, "disagreement_rate": 1.0, "champion_version": "1", "enabled": False},
            {"scorecard_id": "a", "score_id": "none", "scorecard_name": "A", "score_name": "N", "valid_feedback_count": 99, "disagreement_rate": 1.0},
        ],
        coverage={"complete": False, "failures": ["page 2 failed"]},
    )

    assert [row["score_id"] for row in result["ranked"]] == ["a", "b"]
    assert result["ranked"][0]["reviewed_error_opportunity"] == 10
    assert result["exact"] is False
    assert {row["unranked_reason"] for row in result["unranked"]} == {"disabled", "missing_champion"}
    assert result["coverage"]["failures"] == ["page 2 failed"]


def test_rank_without_enumeration_evidence_is_never_exact():
    result = rank_portfolio([])

    assert result["exact"] is False
    assert result["coverage"]["complete"] is False


def test_rank_supports_alignment_aliases_and_excludes_declared_unusable_pairs():
    result = rank_portfolio(
        [
            {
                "scorecardId": "card",
                "scoreId": "eligible",
                "scorecardName": "Card",
                "scoreName": "Eligible",
                "total_items": 10,
                "disagreements": 3,
                "invalid_feedback_count": 1,
                "incomplete_label_pair_count": 2,
                "championVersionId": "version",
            },
            {
                "scorecardId": "card",
                "scoreId": "disabled",
                "total_items": 20,
                "disagreements": 20,
                "championVersionId": "version",
                "isDisabled": True,
            },
        ],
        coverage={"complete": False, "retries": 2, "failures": ["retry exhausted"]},
    )

    assert result["ranked"][0]["score_id"] == "eligible"
    assert result["ranked"][0]["valid_feedback_count"] == 7
    assert result["ranked"][0]["reviewed_error_opportunity"] == 3
    assert result["unranked"][0]["unranked_reason"] == "disabled"
    assert result["coverage"]["retries"] == 2


def test_assessment_orders_structural_and_evidence_gates_before_readiness():
    structural = assess_investment({"coverage_complete": False, "champion_version": None})
    scarce = assess_investment(
        {
            "coverage_complete": True,
            "champion_version": "1",
            "valid_feedback_count": 200,
            "reachable_classes": ["yes", "no"],
            "final_label_counts": {"yes": 200, "no": 0},
            "guideline_state": "consistent",
        }
    )

    assert structural["readiness_state"] == "incomplete"
    assert scarce["readiness_state"] == "insufficient_evidence"
    assert scarce["feedback_collection_state"] == "collect_targeted_classes"
    assert "no" in scarce["blockers"][0]


def test_assessment_high_stable_disagreement_is_ready_and_low_stable_is_monitoring():
    common = {
        "coverage_complete": True,
        "champion_version": "1",
        "valid_feedback_count": 200,
        "reachable_classes": ["yes", "no"],
        "final_label_counts": {"yes": 100, "no": 100},
        "weekly_disagreement_rates": [0.20] * 4,
        "weekly_ac1_values": [0.70] * 4,
        "guideline_state": "consistent",
    }
    high = assess_investment({**common, "disagreement_count": 40})
    low = assess_investment({**common, "disagreement_count": 0})

    assert high["readiness_state"] == "ready_to_optimize"
    assert high["feedback_collection_state"] == "pause_pending_repair_or_clarification"
    assert low["readiness_state"] == "monitoring_candidate"
    assert low["feedback_collection_state"] == "reduce_to_periodic_monitoring"


def test_established_high_disagreement_pauses_broad_collection_without_weekly_gate():
    result = assess_investment(
        {
            "coverage_complete": True,
            "champion_version": "1",
            "valid_feedback_count": 200,
            "disagreement_count": 80,
            "reachable_classes": ["yes", "no"],
            "final_label_counts": {"yes": 100, "no": 100},
            "weekly_disagreement_rates": [],
            "weekly_ac1_values": [],
            "weekly_bucket_counts": [0, 0, 0, 0],
            "guideline_state": "consistent",
        }
    )

    assert result["readiness_state"] == "ready_to_optimize"
    assert result["feedback_collection_state"] == "pause_pending_repair_or_clarification"
    assert result["primary_next_action"] == "run_approved_optimization"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, "missing"), ("syntax_error", "invalid"), ("code_conflict", "potential_code_conflict"), ("ok", "consistent")],
)
def test_guideline_normalization(raw, expected):
    assert normalize_guideline_state(raw) == expected


def test_semantic_diagnosis_state_is_preserved_in_common_packet_fields():
    diagnosis = dispatch_optimization_operation(
        "diagnose",
        {
            "account_id": "account",
            "diagnosis": {
                "guideline_state": "code_conflict",
                "feedback_contradiction": True,
                "stakeholder_questions": ["clarify policy"],
                "complete": True,
            },
        },
    )

    assert diagnosis["guideline_state"] == "potential_code_conflict"
    assert diagnosis["feedback_rubric_state"] == "inconsistent"
    assert diagnosis["states"]["guideline_health"] == "potential_code_conflict"
    assert diagnosis["states"]["feedback_rubric_health"] == "inconsistent"


def test_complete_semantic_diagnosis_preserves_ready_assessment_only_without_blockers():
    ready = dispatch_optimization_operation(
        "diagnose",
        {
            "diagnosis": {
                "guideline_state": "consistent",
                "feedback_rubric_consistent": True,
                "complete": True,
                "assessment": {"readiness_state": "ready_to_optimize"},
            }
        },
    )
    blocked = dispatch_optimization_operation(
        "diagnose",
        {
            "diagnosis": {
                "guideline_state": "consistent",
                "feedback_rubric_consistent": True,
                "complete": True,
                "assessment": {"readiness_state": "ready_to_optimize"},
                "stakeholder_questions": ["Which policy applies?"],
            }
        },
    )

    assert ready["readiness_state"] == "ready_to_optimize"
    assert ready["primary_next_action"] == "request_optimization_approval"
    assert blocked["readiness_state"] == "stakeholder_clarification_required"


def test_structural_normalization_covers_unreadable_and_unresolved_configuration():
    assert normalize_structural_state({"configuration_readable": False}) == "unreadable_configuration"
    assert normalize_structural_state({"terminal_classes_resolved": False}) == "unresolved_terminal_classes"


def test_evidence_fingerprint_is_order_independent_and_changes_with_watermark():
    first = evidence_fingerprint({"champion_version": "1", "feedback_watermark": "f-2", "scope": {"a": 1, "b": 2}})
    reordered = evidence_fingerprint({"scope": {"b": 2, "a": 1}, "feedback_watermark": "f-2", "champion_version": "1"})
    changed = evidence_fingerprint({"champion_version": "1", "feedback_watermark": "f-3", "scope": {"a": 1, "b": 2}})

    assert first == reordered
    assert first != changed


def _ready_assessment_packet(*, scorecard_id: str = "sc", score_id: str = "s") -> dict:
    """Build the exact, complete assessment artifact required for a launch."""
    return assess_investment(
        {
            "account_id": "account",
            "scope": {"scorecard_id": scorecard_id, "score_id": score_id},
            "window": {
                "start": "2026-01-01T00:00:00Z",
                "end": "2026-04-01T00:00:00Z",
            },
            "coverage_complete": True,
            "champion_version": "champion",
            "feedback_watermark": "watermark",
            "valid_feedback_count": 200,
            "disagreement_count": 80,
            "reachable_classes": ["yes", "no"],
            "final_label_counts": {"yes": 100, "no": 100},
            "guideline_state": "consistent",
        }
    )


def _ready_target(packet: dict) -> dict:
    return {
        "scorecard_id": packet["scope"]["scorecard_id"],
        "score_id": packet["scope"]["score_id"],
        "assessment": packet,
        "assessment_fingerprint": packet["evidence_fingerprint"],
        "assessment_complete": True,
        "readiness_state": "ready_to_optimize",
        "champion_version": "champion",
        "feedback_watermark": "watermark",
    }


def test_approved_batch_requires_exact_approved_unique_maximum_five_targets():
    packet = _ready_assessment_packet()
    target = _ready_target(packet)
    accepted = validate_approved_batch(
        [target],
        approved=True,
        current_fingerprints={"sc:s": packet["evidence_fingerprint"]},
    )
    stale = validate_approved_batch(
        [{**target, "assessment_fingerprint": "old"}],
        approved=True,
        current_fingerprints={"sc:s": packet["evidence_fingerprint"]},
    )

    assert accepted["accepted"] is True
    assert stale["accepted"] is False
    assert stale["rejected"][0]["reason"] == "assessment_fingerprint_mismatch"
    assert validate_approved_batch([], approved=True)["accepted"] is False
    assert validate_approved_batch([{"scorecard_id": "x", "score_id": str(i)} for i in range(6)], approved=True)["accepted"] is False


def test_approved_batch_rejects_absent_or_arbitrary_current_assessment_fingerprints():
    packet = _ready_assessment_packet()
    target = _ready_target(packet)

    missing = validate_approved_batch([target], approved=True)
    arbitrary = validate_approved_batch(
        [{**target, "assessment_fingerprint": "arbitrary"}],
        approved=True,
        current_fingerprints={"sc:s": "arbitrary"},
    )

    assert missing["accepted"] is False
    assert missing["rejected"][0]["reason"] == "current_assessment_fingerprint_required"
    assert arbitrary["accepted"] is False
    assert arbitrary["rejected"][0]["reason"] == "assessment_fingerprint_mismatch"


def test_post_run_promotion_requires_every_safety_gate():
    base = {
        "terminal": True,
        "indexed_optimizer_review": True,
        "candidate_version_id": "candidate-version",
        "matched_recent_evaluation": True,
        "historical_regression_evidence": True,
        "class_specific_metrics": True,
        "prediction_collapse": False,
        "rca_complete": True,
        "artifacts_complete": True,
        "measurable_safe_improvement": True,
    }
    assert classify_post_run_review(base)["post_run_state"] == "promotion_ready"
    assert classify_post_run_review({**base, "prediction_collapse": True})["post_run_state"] == "no_safe_improvement"
    assert classify_post_run_review({**base, "terminal": False})["post_run_state"] == "failed_or_incomplete"


def test_post_run_promotion_requires_explicit_no_collapse_and_candidate_identity():
    base = {
        "terminal": True,
        "indexed_optimizer_review": True,
        "candidate_version_id": "candidate-version",
        "matched_recent_evaluation": True,
        "historical_regression_evidence": True,
        "class_specific_metrics": True,
        "rca_complete": True,
        "artifacts_complete": True,
        "measurable_safe_improvement": True,
    }

    missing_collapse = classify_post_run_review(base)
    unknown_collapse = classify_post_run_review({**base, "prediction_collapse": None})
    missing_candidate = classify_post_run_review(
        {**base, "prediction_collapse": False, "candidate_version_id": None}
    )
    missing_indexed_evidence = classify_post_run_review(
        {**base, "prediction_collapse": False, "indexed_optimizer_review": False}
    )

    for result in (
        missing_collapse,
        unknown_collapse,
        missing_candidate,
        missing_indexed_evidence,
    ):
        assert result["post_run_state"] == "continue_optimization"
        assert result["promotion_ready"] is False
    assert "prediction_collapse" in missing_collapse["missing_evidence"]
    assert "candidate_version_id" in missing_candidate["missing_evidence"]
    assert "indexed_optimizer_review" in missing_indexed_evidence["missing_evidence"]


def test_summary_aggregates_actions_questions_failures_and_approval_requests():
    summary = summarize_packets(
        [
            {"states": {"post_run": "promotion_ready"}, "primary_next_action": "request_promotion_approval", "stakeholder_questions": ["confirm policy"]},
            {"states": {"readiness": "incomplete"}, "blockers": ["coverage failed"], "primary_next_action": "repair_coverage"},
        ]
    )

    assert summary["packet_count"] == 2
    assert summary["promotion_approval_requests"] == 1
    assert summary["stakeholder_questions"] == ["confirm policy"]
    assert summary["failures"] == ["coverage failed"]
    assert POLICY_PROFILE_V1["weekly_minimum_count"] is None


def test_summary_retains_compact_per_score_outcomes_in_input_order():
    summary = summarize_packets(
        [
            {
                "scope": {"scorecard_id": "card-a", "score_id": "score-a"},
                "states": {"optimization": "ready_to_optimize", "feedback_collection": "continue_broad_collection"},
                "primary_next_action": "run_approved_optimization",
                "blockers": [],
                "stakeholder_questions": [],
            },
            {
                "scope": {"scorecard_id": "card-b", "score_id": "score-b"},
                "states": {"post_run": "promotion_ready", "feedback_collection": "reduce_to_periodic_monitoring"},
                "primary_next_action": "request_promotion_approval",
                "blockers": ["coverage failed"],
                "stakeholder_questions": ["confirm exception"],
                "coverage": {"failures": ["retry exhausted"]},
            },
        ]
    )

    outcomes = summary["per_score_outcomes"]
    assert [outcome["score_id"] for outcome in outcomes] == ["score-a", "score-b"]
    assert outcomes[0]["scope"] == {"scorecard_id": "card-a", "score_id": "score-a"}
    assert outcomes[0]["outcome"] == "ready_to_optimize"
    assert outcomes[0]["collection_recommendation"] == "continue_broad_collection"
    assert outcomes[1]["approval_request"] is True
    assert outcomes[1]["stakeholder_questions"] == ["confirm exception"]
    assert outcomes[1]["failures"] == ["coverage failed", "retry exhausted"]


def test_dispatch_routes_dict_payloads_without_runtime_dependencies():
    packet = _ready_assessment_packet(scorecard_id="sc", score_id="score")
    target = _ready_target(packet)
    result = dispatch_optimization_operation(
        "optimization.run",
        {
            "approved": True,
            "max_cost_usd": 1.0,
            "max_samples": 10,
            "max_iterations": 2,
            "max_concurrency": 1,
            "targets": [target],
            "current_fingerprints": {"sc:score": packet["evidence_fingerprint"]},
        },
    )

    assert result["accepted"] is True
    assert result["accepted_targets"][0]["score_id"] == "score"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_cost_usd", None),
        ("max_cost_usd", 0),
        ("max_samples", 0),
        ("max_iterations", -1),
        ("max_concurrency", 0),
        ("max_concurrency", 6),
    ],
)
def test_run_limits_are_explicit_positive_and_concurrency_is_bounded(field, value):
    payload = {"max_cost_usd": 1, "max_samples": 1, "max_iterations": 1, "max_concurrency": 1}
    payload[field] = value

    result = validate_run_limits(payload)

    assert result["valid"] is False
    assert field in result["invalid_fields"]


def test_public_run_dispatch_rejects_missing_ready_assessment_provenance():
    packet = _ready_assessment_packet(scorecard_id="sc", score_id="score")
    target = _ready_target(packet)
    limits = {"max_cost_usd": 1, "max_samples": 1, "max_iterations": 1, "max_concurrency": 1}
    fingerprints = {"sc:score": packet["evidence_fingerprint"]}
    accepted = dispatch_optimization_operation("run", {"approved": True, "targets": [target], **limits, "current_fingerprints": fingerprints})
    incomplete_packet = {**packet, "coverage": {"complete": False, "failures": ["retry exhausted"]}}
    missing_marker = dispatch_optimization_operation("run", {"approved": True, "targets": [{**target, "assessment": incomplete_packet}], **limits, "current_fingerprints": fingerprints})
    missing_limit = dispatch_optimization_operation("run", {"approved": True, "targets": [target], "max_cost_usd": 1, "max_samples": 1, "max_iterations": 1, "current_fingerprints": fingerprints})

    assert accepted["accepted"] is True
    assert missing_marker["accepted"] is False
    assert missing_marker["rejected"][0]["reason"] == "assessment_not_ready"
    assert missing_limit["accepted"] is False
    assert missing_limit["rejected"][0]["reason"] == "invalid_run_limits"


def test_every_stage_returns_common_packet_contract_with_caller_context():
    context = {
        "account_id": "account",
        "scope": {"scorecard_id": "card", "score_id": "score"},
        "window": {"start": "2026-01-01T00:00:00Z", "end": "2026-04-01T00:00:00Z"},
        "champion_version": "champion",
        "feedback_watermark": "watermark",
    }
    common = {
        "coverage_complete": True,
        "champion_version": "champion",
        "valid_feedback_count": 200,
        "disagreement_count": 0,
        "reachable_classes": ["yes"],
        "final_label_counts": {"yes": 200},
        "weekly_disagreement_rates": [0, 0, 0, 0],
        "weekly_ac1_values": [1, 1, 1, 1],
        "guideline_state": "consistent",
    }
    calls = [
        ("rank", {"scores": [{"score_id": "score", "champion_version": "champion"}], "coverage": {"complete": False, "retries": 1}}),
        ("assess", {"evidence": common}),
        ("diagnose", {"diagnosis": {"guideline_state": "consistent", "complete": True}}),
        ("run", {"approved": True, "max_cost_usd": 1, "max_samples": 1, "max_iterations": 1, "max_concurrency": 1, "targets": [{"scorecard_id": "card", "score_id": "score", "assessment_complete": True, "readiness_state": "ready_to_optimize", "champion_version": "champion", "feedback_watermark": "watermark", "assessment_fingerprint": "fp"}]}),
        ("review", {"evidence": {"terminal": False}}),
        ("summary", {"packets": []}),
    ]
    required = {"version", "account_id", "scope", "window", "policy_version", "champion_version", "feedback_watermark", "coverage", "evidence", "states", "primary_next_action", "secondary_actions", "blockers", "evidence_ids", "rationale", "evidence_fingerprint"}

    for operation, payload in calls:
        result = dispatch_optimization_operation(operation, {**context, **payload})
        assert required <= result.keys()
        assert result["version"] == "optimization-decision-packet-v1"
        assert result["account_id"] == "account"
        assert result["scope"] == context["scope"]
        assert result["window"] == context["window"]
