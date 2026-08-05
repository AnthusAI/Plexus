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


def test_stakeholder_presentation_keeps_guideline_code_conflicts_actionable():
    view = {
        "overview": {"lifecycle_status": "complete", "analysis_coverage_status": "complete"},
        "portfolio": [{
            "scorecard_name": "Example portfolio",
            "score_name": "Eligibility score",
            "primary_disposition": "guideline_or_code_repair",
            "next_action": "repair_guideline_and_code_alignment",
            "valid_feedback_count": 27,
        }],
        "priorities": [],
        "feedback_investment": [],
        "optimization_outcomes": [],
        "questions_and_issues": [{
            "scorecard_name": "Example portfolio",
            "score_name": "Eligibility score",
            "issue_flag": "potential_code_conflict",
            "guideline_state": "potential_code_conflict",
            "finding": "The guideline requires an explicit confirmation, but the score code accepts an implied answer.",
            "evidence_references": "semantic diagnosis",
            "evidence_reference_tokens": ["semantic-evidence-1234abcd"],
            "affected_evidence_count": 27,
            "affected_disagreement_rate": 0.31,
            "next_action": "repair_guideline_and_code_alignment",
        }],
    }

    presentation = build_stakeholder_presentation(view, scorecard_artifacts=[])

    assert presentation["guideline_code_conflict_workstream"] == {
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
            "dashboard_url": None,
        }],
    }
