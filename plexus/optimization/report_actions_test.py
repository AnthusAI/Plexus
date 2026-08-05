from plexus.optimization.report_actions import (
    build_action_projection,
    build_decision_summary,
    build_guideline_code_conflict_workstream,
)


def _row(name, disposition, action, *, flags=(), evidence=0, scorecard="Portfolio"):
    return {
        "scorecard_name": scorecard,
        "score_name": name,
        "primary_disposition": disposition,
        "next_action": action,
        "secondary_issue_flags": list(flags),
        "valid_feedback_count": evidence,
        "rationale": f"Reason for {name}",
    }


def test_action_projection_assigns_each_score_to_one_deterministic_workstream():
    rows = [
        _row("A", "guideline_or_code_repair", "repair_guidelines", flags=("missing_guidelines",), evidence=12),
        _row("B", "guideline_or_code_repair", "repair_guidelines", flags=("missing_guidelines",), evidence=8),
        _row("C", "cooldown", "wait_for_cooldown", evidence=20),
        _row("D", "promotion_ready", "request_promotion_approval", evidence=5),
    ]

    projection = build_action_projection(rows)

    assert projection["score_count"] == 4
    assert sum(item["score_count"] for item in projection["action_workstreams"]) == 4
    assert projection["action_counts"] == {
        "automatic_work": 0,
        "human_decisions": 1,
        "repairs_and_evidence": 2,
        "monitor_later": 1,
        "no_action": 0,
    }
    repair = next(item for item in projection["action_workstreams"] if item["action_group"] == "technical_repair")
    assert repair["score_count"] == 2
    assert repair["scorecard_count"] == 1
    assert repair["evidence_count"] == 20
    assert repair["owner_role"] == "score_maintainer"
    assert repair["queue_state"] == "open"
    assert repair["dominant_issue"] == "missing_guidelines"
    assert [row["score_name"] for row in repair["representative_rows"]] == ["A", "B"]


def test_action_projection_keeps_monitoring_and_history_out_of_open_queue():
    projection = build_action_projection([
        _row("Cooling", "cooldown", "wait_for_cooldown"),
        _row("Done", "not_selected", "consider_next_portfolio_run"),
        _row("Broken", "failed_or_incomplete", "repair_evidence"),
    ])

    states = {item["action_group"]: item["queue_state"] for item in projection["action_workstreams"]}
    assert states == {
        "incomplete_evidence": "open",
        "monitor": "monitor",
        "no_action": "history",
    }


def test_guideline_code_conflicts_become_a_stakeholder_safe_repair_workstream():
    workstream = build_guideline_code_conflict_workstream([
        {
            "issue_flag": "potential_code_conflict",
            "scorecard_name": "Example portfolio",
            "score_name": "Eligibility score",
            "finding": "The guideline requires an explicit confirmation, but the score code accepts an implied answer.",
            "evidence_references": "semantic diagnosis",
            "evidence_reference_tokens": ["semantic-evidence-1234abcd"],
            "affected_evidence_count": 27,
            "affected_disagreement_rate": 0.31,
            "next_action": "repair_guideline_and_code_alignment",
            "dashboard_url": "https://dashboard.example/lab/scores/example",
        },
        {
            "issue_flag": "feedback_rubric_contradiction",
            "scorecard_name": "Example portfolio",
            "score_name": "Other score",
            "finding": "Do not include this different issue type.",
        },
    ])

    assert workstream == {
        "title": "Potential guideline and code conflicts",
        "conflict_count": 1,
        "score_count": 1,
        "why_optimization_is_blocked": (
            "A potential mismatch between the guideline and score code blocks automatic "
            "optimization until a score maintainer verifies it and either repairs the "
            "definition or records why the behavior is intentional."
        ),
        "owner_role": "score_maintainer",
        "next_action": "review_and_repair_guideline_code_alignment",
        "items": [{
            "scorecard_name": "Example portfolio",
            "score_name": "Eligibility score",
            "conflict_claim": "The guideline requires an explicit confirmation, but the score code accepts an implied answer.",
            "supporting_evidence": "Model-backed comparison of the current ScoreVersion guideline and score configuration (semantic diagnosis).",
            "evidence_references": ["semantic-evidence-1234abcd"],
            "affected_evidence_count": 27,
            "affected_disagreement_rate": 0.31,
            "why_optimization_is_blocked": (
                "A potential mismatch between the guideline and score code blocks automatic "
                "optimization until a score maintainer verifies it and either repairs the "
                "definition or records why the behavior is intentional."
            ),
            "owner_role": "score_maintainer",
            "next_action": "review_and_repair_guideline_code_alignment",
            "dashboard_url": "https://dashboard.example/lab/scores/example",
        }],
    }


def test_decision_summary_never_claims_zero_result_while_analysis_is_pending():
    summary = build_decision_summary(
        {
            "lifecycle_status": "running",
            "analysis_coverage_status": "pending",
            "diagnosis_scheduled_count": 4,
            "diagnosis_completed_count": 0,
            "execution_selected_count": 0,
            "execution_launched_count": 0,
            "next_checkpoint": "Publish diagnosis results.",
        },
        {},
    )

    assert summary == {
        "state": "analysis_pending",
        "headline": "No optimization decision yet",
        "explanation": "Analysis is still determining which scores are safe and worthwhile to optimize.",
        "next_action": "Publish diagnosis results.",
    }


def test_decision_summary_explains_a_configured_count_limit_without_implying_failure():
    summary = build_decision_summary(
        {
            "lifecycle_status": "incomplete",
            "inventory_coverage_status": "complete",
            "analysis_coverage_status": "incomplete",
            "diagnosis_selected_count": 22,
            "diagnosis_scheduled_count": 4,
            "diagnosis_completed_count": 4,
            "diagnosis_deferred_count": 18,
            "diagnosis_max_count": 4,
            "diagnosis_incomplete_count": 0,
            "diagnosis_execution_failure_count": 0,
            "diagnosis_prerequisite_failure_count": 0,
        },
        {},
    )

    assert summary == {
        "state": "incomplete_evidence",
        "headline": "The configured run limit left 18 candidates unanalyzed",
        "explanation": (
            "Deterministic ranking and all 4 scheduled diagnoses completed. The run "
            "selected 22 candidates, but its configured diagnosis limit was 4, so 18 "
            "were deferred without being judged safe or unsafe."
        ),
        "next_action": (
            "Increase the diagnosis limit or review the 18 deferred candidates in a "
            "follow-up run."
        ),
    }


def test_decision_summary_distinguishes_budget_exhaustion_from_a_count_limit():
    summary = build_decision_summary(
        {
            "lifecycle_status": "incomplete",
            "inventory_coverage_status": "complete",
            "analysis_coverage_status": "incomplete",
            "diagnosis_scheduled_count": 4,
            "diagnosis_completed_count": 3,
            "diagnosis_execution_failure_count": 1,
            "semantic_budget_exhausted_count": 1,
        },
        {},
    )

    assert summary["headline"] == (
        "The semantic-analysis budget ended diagnosis before full coverage"
    )
    assert "frozen budget left 1 diagnosis without complete evidence" in summary["explanation"]
    assert "not judged safe or unsafe" in summary["explanation"]


def test_decision_summary_distinguishes_incomplete_results_and_execution_failures():
    incomplete = build_decision_summary(
        {
            "lifecycle_status": "incomplete",
            "inventory_coverage_status": "complete",
            "analysis_coverage_status": "incomplete",
            "diagnosis_incomplete_count": 2,
        },
        {},
    )
    failed = build_decision_summary(
        {
            "lifecycle_status": "incomplete",
            "inventory_coverage_status": "complete",
            "analysis_coverage_status": "incomplete",
            "diagnosis_execution_failure_count": 1,
        },
        {},
    )

    assert "2 returned incomplete evidence" in incomplete["explanation"]
    assert "1 failed during execution" in failed["explanation"]
    assert "configured run limit" not in incomplete["headline"]
    assert "configured run limit" not in failed["headline"]


def test_decision_summary_keeps_actual_run_failure_distinct_from_incomplete_coverage():
    summary = build_decision_summary(
        {
            "lifecycle_status": "failed",
            "inventory_coverage_status": "complete",
            "analysis_coverage_status": "incomplete",
            "diagnosis_deferred_count": 18,
        },
        {},
    )

    assert summary["state"] == "failure"
    assert summary["headline"] == "The optimization run could not complete"


def test_decision_summary_reports_terminal_zero_target_and_validated_improvement():
    zero = build_decision_summary(
        {"lifecycle_status": "complete", "analysis_coverage_status": "complete"},
        {"guideline_or_code_repair": 9},
    )
    improved = build_decision_summary(
        {
            "lifecycle_status": "complete",
            "analysis_coverage_status": "complete",
            "execution_launched_count": 1,
            "optimizer_review_count": 1,
        },
        {"promotion_ready": 1},
    )

    assert zero["state"] == "no_safe_target"
    assert zero["headline"] == "No score was safe to optimize automatically"
    assert improved["state"] == "validated_improvement"
    assert improved["headline"] == "1 validated improvement requires review"


def test_validated_improvement_is_repair_evidence_work_and_counts_as_an_improvement():
    projection = build_action_projection([{
        "scorecard_name": "Example portfolio",
        "score_name": "Example score",
        "primary_disposition": "validated_improvement",
        "next_action": "complete_promotion_evidence",
        "valid_feedback_count": 12,
    }])
    summary = build_decision_summary(
        {
            "lifecycle_status": "completed",
            "analysis_coverage_status": "complete",
            "execution_launched_count": 1,
            "optimizer_review_count": 1,
        },
        {"validated_improvement": 1},
    )

    assert projection["action_counts"]["repairs_and_evidence"] == 1
    assert projection["action_workstreams"][0]["action_group"] == "incomplete_evidence"
    assert summary["state"] == "validated_improvement"
    assert summary["headline"] == "1 validated improvement requires review"


def test_decision_summary_leads_with_validated_improvement_when_other_terminal_outcomes_are_incomplete():
    summary = build_decision_summary(
        {
            "lifecycle_status": "incomplete",
            "analysis_coverage_status": "incomplete",
            "execution_launched_count": 3,
            "optimizer_review_count": 3,
        },
        {"validated_improvement": 1, "failed_or_incomplete": 2},
    )

    assert summary == {
        "state": "validated_improvement",
        "headline": "1 validated improvement requires review",
        "explanation": (
            "Evaluation evidence supports 1 improvement, while 2 other optimizer "
            "outcomes require repair; the overall run remains incomplete. No champion "
            "was promoted."
        ),
        "next_action": "Complete promotion evidence for the validated improvement and repair incomplete optimizer outcomes.",
    }

    singular = build_decision_summary(
        {"lifecycle_status": "incomplete", "analysis_coverage_status": "incomplete"},
        {"validated_improvement": 1, "failed_or_incomplete": 1},
    )
    assert "1 other optimizer outcome requires repair" in singular["explanation"]


def test_decision_summary_reports_zero_target_after_execution_policy_finishes():
    summary = build_decision_summary(
        {
            "lifecycle_status": "running",
            "analysis_coverage_status": "complete",
            "execution_decision_status": "complete",
            "execution_selected_count": 0,
            "execution_launched_count": 0,
        },
        {"guideline_or_code_repair": 4},
    )

    assert summary["state"] == "no_safe_target"
    assert summary["headline"] == "No score was safe to optimize automatically"


def test_not_selected_score_cannot_become_automatic_work_from_a_stale_next_action():
    projection = build_action_projection([
        {
            "scorecard_name": "Example portfolio",
            "score_name": "Example score",
            "primary_disposition": "not_selected",
            "next_action": "run_approved_optimization",
            "valid_feedback_count": 12,
        },
    ])

    assert projection["action_counts"] == {
        "automatic_work": 0,
        "human_decisions": 0,
        "repairs_and_evidence": 0,
        "monitor_later": 0,
        "no_action": 1,
    }
    assert projection["action_workstreams"][0]["action_group"] == "no_action"


def test_decision_summary_treats_completed_with_unresolved_actions_as_terminal():
    summary = build_decision_summary(
        {
            "lifecycle_status": "completed_with_unresolved_actions",
            "analysis_coverage_status": "complete",
        },
        {},
    )

    assert summary["state"] == "no_safe_target"
