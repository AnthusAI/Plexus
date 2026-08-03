from plexus.optimization.run_report import build_stakeholder_presentation


def test_stakeholder_presentation_carries_backend_decision_and_action_contract():
    view = {
        "overview": {
            "lifecycle_status": "running",
            "analysis_coverage_status": "pending",
            "next_checkpoint": "Finish diagnosis.",
        },
        "portfolio": [
            {
                "scorecard_ref": "card-1",
                "scorecard_name": "Example Portfolio",
                "score_name": "First",
                "primary_disposition": "guideline_or_code_repair",
                "secondary_issue_flags": ["missing_guidelines"],
                "next_action": "repair_guidelines",
                "valid_feedback_count": 12,
            },
            {
                "scorecard_ref": "card-1",
                "scorecard_name": "Example Portfolio",
                "score_name": "Second",
                "primary_disposition": "guideline_or_code_repair",
                "secondary_issue_flags": ["missing_guidelines"],
                "next_action": "repair_guidelines",
                "valid_feedback_count": 8,
            },
        ],
        "priorities": [],
        "questions_and_issues": [],
        "optimization_outcomes": [],
    }

    presentation = build_stakeholder_presentation(view, scorecard_artifacts=[])

    assert presentation["decision_summary"]["state"] == "analysis_pending"
    assert presentation["action_counts"]["repairs_and_evidence"] == 2
    assert len(presentation["action_workstreams"]) == 1
    assert presentation["action_workstreams"][0]["score_count"] == 2
    assert presentation["score_count"] == sum(
        item["score_count"] for item in presentation["action_workstreams"]
    )
