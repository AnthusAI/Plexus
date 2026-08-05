"""Contract tests for the compact optimization-survey agent handoff."""

from __future__ import annotations

import json

from plexus.optimization.agent_handoff import build_agent_handoff_artifacts


def _row(name, disposition, action, *, score_id, flags=(), evidence=4):
    return {
        "scorecard_id": "card-1",
        "score_id": score_id,
        "scorecard_name": "Quality card",
        "score_name": name,
        "primary_disposition": disposition,
        "next_action": action,
        "secondary_issue_flags": list(flags),
        "valid_feedback_count": evidence,
        "rationale": f"Reason for {name}",
    }


def _packet(score_id, **extra):
    return {
        "scorecard_id": "card-1",
        "score_id": score_id,
        "champion_version": f"champion-{score_id}",
        "feedback_watermark": f"watermark-{score_id}",
        "configuration_digest": f"config-{score_id}",
        "guideline_digest": f"guideline-{score_id}",
        "evidence_fingerprint": f"fingerprint-{score_id}",
        **extra,
    }


def _build(rows, evidence=None, *, finalized=False):
    return build_agent_handoff_artifacts(
        decision_evidence=evidence or {},
        stakeholder_view={
            "overview": {
                "conclusion": "The survey found follow-up work.",
                "coverage_status": "complete",
                "limitations": ["No automatic champion promotion."],
                "next_checkpoint": "Review the handoff.",
            },
            "portfolio": rows,
        },
        report_metadata={"report_id": "report-1", "revision": 7, "milestone": "review"},
        finalized=finalized,
    )


def test_orders_all_followup_categories_and_keeps_exact_resource_references():
    rows = [
        _row("Promotion evidence", "validated_improvement", "complete_promotion_evidence", score_id="s1"),
        _row("Promotion review", "promotion_ready", "request_promotion_approval", score_id="s2"),
        _row("Failure", "failed_or_incomplete", "review_optimizer_failure", score_id="s3"),
        _row("Conflict", "guideline_or_code_repair", "repair_guidelines", score_id="s4", flags=("potential_code_conflict",)),
        _row("Guidelines", "guideline_or_code_repair", "repair_guidelines", score_id="s5", flags=("missing_guidelines",)),
        _row("Evidence", "targeted_feedback_collection", "collect_targeted_feedback", score_id="s6"),
        _row("Cooldown", "cooldown", "wait_for_cooldown", score_id="s7"),
    ]
    evidence = {
        "assessments": [_packet(f"s{number}") for number in range(1, 8)],
        "reviews": [
            _packet("s1", post_run_state="validated_improvement", promotion_ready=False,
                    missing_evidence=["rca_complete"], candidate_version_id="candidate-s1",
                    procedure_id="procedure-s1", evaluation_id="evaluation-s1",
                    alignment_evidence={
                        "recent": {
                            "baseline": 0.4,
                            "candidate": 0.7,
                            "delta": 0.3,
                            "raw_feedback": "must not be projected",
                        },
                        "regression": {"baseline": True, "candidate": "0.9"},
                        "raw": {"transcript": "must not be projected"},
                    }),
            _packet("s2", post_run_state="promotion_ready", promotion_ready=True,
                    candidate_version_id="candidate-s2", procedure_id="procedure-s2", evaluation_id="evaluation-s2"),
            _packet("s3", post_run_state="failed_or_incomplete", failed=True,
                    procedure_id="procedure-s3", task_id="task-s3"),
        ],
    }

    result = _build(rows, evidence)
    items = result["followup_pages"][0]["items"]

    assert [item["kind"] for item in items] == [
        "complete_promotion_evidence", "review_promotion", "investigate_optimizer_failure",
        "resolve_guideline_code_conflict", "add_missing_guidelines",
        "collect_more_evidence", "monitor_after_cooldown",
    ]
    incomplete, ready = items[:2]
    assert incomplete["promotion_ready"] is False
    assert incomplete["resource_refs"]["candidate_version_id"] == "candidate-s1"
    assert incomplete["evidence_gaps"] == ["rca_complete"]
    assert incomplete["frozen_preconditions"] == {
        "champion_version_id": "champion-s1",
        "feedback_watermark": "watermark-s1",
        "configuration_digest": "config-s1",
        "guideline_digest": "guideline-s1",
        "evidence_fingerprint": "fingerprint-s1",
    }
    assert incomplete["optimizer_metrics"] == {
        "recent": {"baseline": 0.4, "candidate": 0.7, "delta": 0.3}
    }
    assert ready["promotion_ready"] is True
    assert ready["resource_refs"]["evaluation_ids"] == ["evaluation-s2"]
    assert ready["suggested_calls"]["mutation"]["name"] == "plexus.score.set_champion"
    assert ready["suggested_calls"]["mutation"]["arguments"]["version_id"] == "candidate-s2"
    assert "candidate_version_id" not in ready["suggested_calls"]["mutation"]["arguments"]
    assert ready["suggested_calls"]["mutation"]["arguments"]["expected_champion_version_id"] == "champion-s2"
    assert {item["reference"] for item in items} == {
        "followup:card-1:s1", "followup:card-1:s2", "followup:card-1:s3",
        "followup:card-1:s4", "followup:card-1:s5", "followup:card-1:s6", "followup:card-1:s7",
    }
    assert list(result["agent_handoff"]["workstream_counts"]) == [
        "complete_promotion_evidence",
        "review_promotion",
        "investigate_optimizer_failure",
        "resolve_guideline_code_conflict",
        "add_missing_guidelines",
        "collect_more_evidence",
        "monitor_after_cooldown",
    ]


def test_pages_are_deterministic_bounded_and_reconcile_every_recommendation_once():
    rows = [
        _row(f"Score {number:02}", "guideline_or_code_repair", "repair_guidelines",
             score_id=f"s{number:02}", flags=("missing_guidelines",), evidence=number)
        for number in range(60)
    ]
    evidence = {"assessments": [_packet(f"s{number:02}") for number in range(60)]}

    first = _build(rows, evidence)
    second = _build(list(reversed(rows)), evidence)

    assert first == second
    pages = first["followup_pages"]
    items = [item for page in pages for item in page["items"]]
    assert len(items) == 60
    assert len({item["reference"] for item in items}) == 60
    assert all(len(page["items"]) <= 25 for page in pages)
    assert all(len(json.dumps(page, separators=(",", ":"), ensure_ascii=False).encode()) <= 24 * 1024 for page in pages)
    assert first["agent_handoff"]["followup_page_logical_ids"] == [page["logical_id"] for page in pages]
    assert list(first["agent_handoff"]["workstream_counts"]) == ["add_missing_guidelines"]


def test_provisional_handoff_uses_hashed_refs_and_excludes_raw_packets():
    # Older stakeholder projections deliberately omit real identifiers.
    import hashlib

    card_id, score_id = "legacy-card", "legacy-score"
    row = {
        "scorecard_ref": hashlib.sha256(card_id.encode()).hexdigest()[:16],
        "score_ref": hashlib.sha256(score_id.encode()).hexdigest()[:16],
        "scorecard_name": "Legacy quality", "score_name": "Legacy score",
        "primary_disposition": "guideline_or_code_repair", "next_action": "repair_guidelines",
        "secondary_issue_flags": ["feedback_rubric_contradiction"],
    }
    result = _build([row], {"diagnoses": [_packet(score_id, scorecard_id=card_id, raw_feedback="do not leak", prompt="do not leak")]})

    handoff = result["agent_handoff"]
    item = result["followup_pages"][0]["items"][0]
    encoded = json.dumps(result)
    assert handoff["provisional"] is True
    assert item["kind"] == "resolve_feedback_guideline_question"
    assert item["resource_refs"]["scorecard_id"] == card_id
    assert item["resource_refs"]["score_id"] == score_id
    assert "do not leak" not in encoded
    assert _build([row], {}, finalized=True)["agent_handoff"]["provisional"] is False


def test_classifies_remaining_guideline_structure_collection_and_monitoring_categories():
    rows = [
        _row("Invalid", "guideline_or_code_repair", "repair_guidelines", score_id="invalid", flags=("invalid_guidelines",)),
        _row("Structure", "guideline_or_code_repair", "repair_score_structure", score_id="structure"),
        _row("Policy", "feedback_curation_review", "review_collection_policy", score_id="policy"),
        _row("Monitor", "monitoring_or_diminishing_returns", "retain_champion", score_id="monitor"),
    ]

    items = _build(rows, {"assessments": [_packet(row["score_id"]) for row in rows]})["followup_pages"][0]["items"]

    assert [item["kind"] for item in items] == [
        "repair_invalid_guidelines",
        "repair_score_structure",
        "review_collection_policy",
        "monitor_no_improvement",
    ]


def test_champion_assignment_and_score_status_actions_are_structure_followups():
    rows = [
        _row(
            "Champion missing",
            "guideline_or_code_repair",
            "assign_champion",
            score_id="assign",
        ),
        _row(
            "Status review",
            "guideline_or_code_repair",
            "review_score_status",
            score_id="status",
        ),
    ]

    result = _build(
        rows,
        {"assessments": [_packet(row["score_id"]) for row in rows]},
    )
    items = [
        item
        for page in result["followup_pages"]
        for item in page["items"]
    ]

    assert [item["kind"] for item in items] == [
        "repair_score_structure",
        "repair_score_structure",
    ]
    assert result["agent_handoff"]["workstream_counts"] == {
        "repair_score_structure": 2,
    }


def test_preserves_multiple_scalar_evaluation_ids_and_true_artifact_ids_only():
    row = _row("Ready", "promotion_ready", "request_promotion_approval", score_id="ready")
    row["artifact_logical_ids"] = ["score_brief:actual-publisher-id"]
    evidence = {
        "reviews": [
            _packet(
                "ready",
                promotion_ready=True,
                post_run_state="promotion_ready",
                candidate_version_id="candidate-ready",
                procedure_id="procedure-ready",
                evaluation_id="evaluation-one",
                matched_recent_evaluation={"not": "an id"},
                historical_regression_evidence=True,
                evidence_ids=["procedure-ready", "evaluation-two", "evaluation-one"],
            )
        ]
    }

    item = _build([row], evidence)["followup_pages"][0]["items"][0]

    assert item["resource_refs"]["evaluation_ids"] == ["evaluation-one", "evaluation-two"]
    evaluation_reads = [
        call for call in item["suggested_calls"]["read"]
        if call["name"] == "plexus.evaluation.info"
    ]
    assert evaluation_reads == [
        {"name": "plexus.evaluation.info", "arguments": {"id": "evaluation-one"}},
        {"name": "plexus.evaluation.info", "arguments": {"id": "evaluation-two"}},
    ]
    assert item["artifact_logical_ids"] == ["score_brief:actual-publisher-id"]


def test_legacy_promotion_claim_fails_toward_evidence_completion_and_handoff_is_under_20kb():
    row = _row("Legacy", "promotion_ready", "request_promotion_approval", score_id="legacy")
    stakeholder_row = _row(
        "Question",
        "stakeholder_clarification_required",
        "resolve_stakeholder_questions",
        score_id="question",
        flags=("stakeholder_question",),
    )
    result = build_agent_handoff_artifacts(
        decision_evidence={},
        stakeholder_view={
            "overview": {
                "conclusion": "x" * 100_000,
                "limitations": ["y" * 100_000 for _ in range(100)],
            },
            "portfolio": [row, stakeholder_row],
        },
        report_metadata={"report_id": "report-1", "revision": 1},
    )

    items = result["followup_pages"][0]["items"]
    assert [item["kind"] for item in items] == [
        "complete_promotion_evidence",
        "resolve_feedback_guideline_question",
    ]
    assert items[0]["promotion_ready"] is False
    assert "mutation" not in items[0]["suggested_calls"]
    assert len(json.dumps(result["agent_handoff"], separators=(",", ":"), ensure_ascii=False).encode()) < 20 * 1024


def test_production_shaped_overview_preserves_backend_no_safe_target_conclusion():
    result = build_agent_handoff_artifacts(
        decision_evidence={},
        stakeholder_view={
            "overview": {
                "headline": "Optimization portfolio run",
                "lifecycle_status": "complete",
                "coverage_status": "complete",
                "inventory_coverage_status": "complete",
                "analysis_coverage_status": "complete",
                "execution_decision_status": "complete",
                "execution_selected_count": 0,
                "execution_launched_count": 0,
                "next_checkpoint": "Repair the identified definitions.",
                "limitations": "Detailed score artifacts are pending.",
                "diagnosis_blockers": ["A required definition was unavailable."],
                "notes": "Latest milestone: finalization. Nothing changes automatically.",
            },
            "portfolio": [
                _row(
                    "Repair",
                    "guideline_or_code_repair",
                    "repair_guidelines",
                    score_id="repair",
                    flags=("missing_guidelines",),
                )
            ],
        },
        report_metadata={"report_id": "report-production", "revision": 41},
        finalized=True,
    )

    handoff = result["agent_handoff"]
    assert handoff["conclusion"] == {
        "state": "no_safe_target",
        "headline": "No score was safe to optimize automatically",
        "explanation": (
            "The run found portfolio work, but no target passed every "
            "execution policy gate."
        ),
        "next_action": "Repair the identified definitions.",
    }
    assert handoff["coverage"] == {
        "inventory": "complete",
        "analysis": "complete",
        "complete": True,
        "provisional": False,
    }
    assert handoff["limitations"] == [
        "Detailed score artifacts are pending.",
        "A required definition was unavailable.",
    ]


def test_agent_handoff_explains_configured_diagnosis_limit_with_structured_counts():
    result = build_agent_handoff_artifacts(
        stakeholder_view={
            "overview": {
                "lifecycle_status": "incomplete",
                "inventory_coverage_status": "complete",
                "analysis_coverage_status": "incomplete",
                "analysis_incomplete_reason": "configured_count_limit",
                "diagnosis_selected_count": 22,
                "diagnosis_scheduled_count": 4,
                "diagnosis_completed_count": 4,
                "diagnosis_deferred_count": 18,
                "diagnosis_max_count": 4,
                "diagnosis_incomplete_count": 0,
                "diagnosis_execution_failure_count": 0,
                "diagnosis_limit_explanation": (
                    "This run was configured to diagnose at most 4 candidates. "
                    "The remaining 18 selected candidates were not examined and "
                    "were not judged safe or unsafe."
                ),
            },
            "portfolio": [],
        },
        decision_evidence={},
        report_metadata={"report_id": "report-limit", "revision": 1},
        finalized=True,
    )

    handoff = result["agent_handoff"]
    assert handoff["conclusion"]["headline"] == (
        "The configured run limit left 18 candidates unanalyzed"
    )
    assert handoff["coverage"] == {
        "inventory": "complete",
        "analysis": "incomplete",
        "complete": False,
        "provisional": False,
        "incomplete_reason": "configured_count_limit",
        "diagnosis": {
            "selected": 22,
            "scheduled": 4,
            "completed": 4,
            "deferred": 18,
            "configured_limit": 4,
        },
    }
    assert handoff["limitations"] == [
        "This run was configured to diagnose at most 4 candidates. The remaining "
        "18 selected candidates were not examined and were not judged safe or unsafe."
    ]


def test_rank_envelope_and_nested_running_child_preserve_exact_resource_ids():
    import hashlib

    card_id, score_id = "ranked-card", "ranked-score"
    row = {
        "scorecard_ref": hashlib.sha256(card_id.encode()).hexdigest()[:16],
        "score_ref": hashlib.sha256(score_id.encode()).hexdigest()[:16],
        "scorecard_name": "Ranked card",
        "score_name": "Ranked score",
        "primary_disposition": "failed_or_incomplete",
        "next_action": "review_optimizer_failure",
    }
    result = _build(
        [row],
        {
            "rank": {
                "ranked": [
                    {
                        "scorecard_id": card_id,
                        "score_id": score_id,
                        "evidence_fingerprint": "rank-fingerprint",
                    }
                ]
            },
            "dispatch": {
                "children": [
                    {
                        "target": {
                            "scorecard_id": card_id,
                            "score_id": score_id,
                        },
                        "procedure_id": "child-procedure",
                        "task_id": "child-task",
                        "launch_state": {"phase": "running"},
                    }
                ]
            },
        },
    )

    item = result["followup_pages"][0]["items"][0]
    assert item["resource_refs"] == {
        "scorecard_id": card_id,
        "score_id": score_id,
        "procedure_id": "child-procedure",
        "task_id": "child-task",
    }


def test_diagnosis_evidence_ids_never_become_evaluation_references():
    row = _row(
        "Conflict",
        "guideline_or_code_repair",
        "repair_guidelines",
        score_id="diagnosis",
        flags=("potential_code_conflict",),
    )
    result = _build(
        [row],
        {
            "diagnoses": [
                _packet(
                    "diagnosis",
                    evidence_ids=["semantic-memory", "restricted-diagnosis-packet"],
                )
            ]
        },
    )

    item = result["followup_pages"][0]["items"][0]
    assert "evaluation_ids" not in item["resource_refs"]
    assert all(
        call["name"] != "plexus.evaluation.info"
        for call in item["suggested_calls"]["read"]
    )
