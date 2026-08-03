from plexus.optimization.report_actions import build_action_projection, build_decision_summary


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
