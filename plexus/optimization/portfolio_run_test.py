"""Outside-in specifications for the reported optimization portfolio runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _assessment(scorecard_id: str, score_id: str) -> dict[str, Any]:
    """A minimal, complete assessment packet accepted by the existing runner."""
    return {
        "scope": {"scorecard_id": scorecard_id, "score_id": score_id},
        "coverage": {"complete": True, "failures": []},
        "states": {"optimization": "ready_to_optimize"},
        "champion_version": f"champion-{score_id}",
        "feedback_watermark": "2026-07-01T00:00:00Z",
        "evidence_fingerprint": f"fingerprint-{score_id}",
        "fingerprint": f"fingerprint-{score_id}",
        "evidence": {
            "score_activity": {
                "policy_version": "score-activity-cooldown-v1",
                "recent": False,
                "complete": True,
            }
        },
    }


@dataclass
class _ReportService:
    started: list[dict[str, Any]] = field(default_factory=list)
    milestones: list[tuple[str, dict[str, Any], dict[str, Any]]] = field(default_factory=list)
    terminal: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    progress_updates: list[dict[str, Any]] = field(default_factory=list)
    report: Any = field(default_factory=lambda: type("Report", (), {"id": "report-1"})())

    def start_or_resume(self, run_spec):
        self.started.append(dict(run_spec))
        return type("State", (), {"report": self.report})()

    def publish_milestone(self, milestone, evidence, *, stakeholder_view):
        self.milestones.append((milestone, dict(evidence), dict(stakeholder_view)))
        return object()

    def publish_progress(self, **progress):
        self.progress_updates.append(dict(progress))

    def finalize(self, *, status="COMPLETED"):
        self.terminal.append(status)

    def fail(self, message):
        self.failures.append(str(message))


def _dependencies(
    *, rank, assess, diagnose, summary, dispatch, review, report, human_review,
    create_action=None, publish_update=None,
):
    from plexus.optimization.portfolio_run import PortfolioRunDependencies

    return PortfolioRunDependencies(
        rank=rank,
        assess=assess,
        diagnose=diagnose,
        summary=summary,
        dispatch=dispatch,
        review=review,
        report_service=lambda _run_key, _request: report,
        human_review=human_review,
        create_action=create_action,
        publish_update=publish_update,
    )


def test_portfolio_run_publishes_idempotent_operator_milestones_after_report_updates():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    updates: list[dict[str, Any]] = []
    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {"coverage": {"complete": True}, "ranked": []},
        assess=lambda _request: {},
        diagnose=lambda _request: {},
        summary=lambda _request: {"coverage": {"complete": True}},
        dispatch=lambda _request: {},
        review=lambda _request: {},
        report=report,
        human_review=lambda _request: {},
        publish_update=lambda update: updates.append(update) or {"created": True},
    ))

    result = runner.run({"account_id": "account-1", "run_key": "daily-run"})

    assert result["status"] == "COMPLETED"
    assert [update["event_key"] for update in updates] == [
        "optimization:daily-run:started",
        "optimization:daily-run:analysis_ready",
        "optimization:daily-run:completed",
    ]
    assert updates[0]["milestone"] == "STARTED"
    assert updates[1]["milestone"] == "COMPLETED"
    assert updates[2]["milestone"] == "COMPLETED"
    terminal_view = report.milestones[-1][2]
    assert terminal_view["overview"]["lifecycle_status"] == "completed"
    assert "complete" in terminal_view["overview"]["current_activity"].lower()
    assert "Finalizing" not in terminal_view["overview"]["current_activity"]
    assert all(update["resource_refs"] == [{
        "system": "plexus", "kind": "report", "id": "report-1",
        "relation": "optimization_run",
    }] for update in updates)


def test_long_analysis_exposes_incremental_progress_without_extra_report_revisions(monkeypatch):
    import plexus.optimization.portfolio_run as portfolio_run
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    # Keep this synthetic progress run bounded to two semantic diagnoses while
    # retaining a larger deterministic assessment batch.  The production
    # policy diagnoses the top ten; the fixture deliberately uses a smaller
    # policy-sized batch so its assertions cover progress through both phases.
    monkeypatch.setattr(portfolio_run, "MAX_PRIORITY_DIAGNOSES", 2)

    report = _ReportService()
    ranked = [
        {
            "scorecard_id": "card-1",
            "score_id": f"score-{index}",
            "scorecard_name": "Example Portfolio",
            "score_name": f"Example Score {index}",
        }
        for index in range(12)
    ]

    def assess(request):
        packet = _assessment(request["scorecard_id"], request["score_id"])
        packet["states"]["optimization"] = "insufficient_evidence"
        return packet

    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {"coverage": {"complete": True}, "ranked": ranked},
        assess=assess,
        diagnose=lambda request: request["assessment"],
        summary=lambda _request: {"coverage": {"complete": True}},
        dispatch=lambda _request: {},
        review=lambda _request: {},
        report=report,
        human_review=lambda _request: {"decisions": []},
    ))

    result = runner.run({
        "account_id": "account-1",
        "run_key": "progress-run",
        "max_semantic_diagnoses": 2,
    })

    assert result["status"] == "COMPLETED"
    assert [
        (row["phase"], row["current"], row["total"])
        for row in report.progress_updates
    ] == [
        ("assessment", 0, 12),
        ("assessment", 10, 12),
        ("assessment", 12, 12),
        ("diagnosis", 12, 14),
        ("diagnosis", 13, 14),
        ("diagnosis", 14, 14),
    ]
    assert "Example Score 9" in report.progress_updates[1]["message"]
    assert "semantic diagnosis" in report.progress_updates[-1]["message"].lower()
    assert [milestone for milestone, _, _ in report.milestones] == [
        "started", "ranking", "assessment", "diagnosis", "approval",
        "optimization", "optimization", "optimization_review", "finalization",
    ]


def test_portfolio_run_creates_the_living_report_before_analysis_and_only_launches_independently_approved_exact_targets():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    dispatches: list[dict[str, Any]] = []
    review_requests: list[dict[str, Any]] = []
    rank_packet = {
        "coverage": {"complete": True, "failures": []},
        "window": {"start": "2026-04-01T00:00:00Z", "end": "2026-07-01T00:00:00Z"},
        "ranked": [
            {"scorecard_id": "opaque-card", "score_id": "opaque-one", "scorecard_name": "Example", "score_name": "One"},
            {"scorecard_id": "opaque-card", "score_id": "opaque-two", "scorecard_name": "Example", "score_name": "Two"},
        ],
    }

    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda request: rank_packet,
        assess=lambda request: _assessment(request["scorecard_id"], request["score_id"]),
        diagnose=lambda request: {**request["assessment"], "states": {"optimization": "ready_to_optimize"}},
        summary=lambda request: {"coverage": {"complete": True}, "per_score_outcomes": []},
        dispatch=lambda request: dispatches.append(request) or {
            "accepted": True,
            "dispatches": [{"status": "dispatched", "procedure_id": "procedure-one"}],
            "dispatch_coverage": {"complete": True},
        },
        review=lambda request: {"coverage": {"complete": True}, "post_run_state": "promotion_ready", "promotion_ready": True},
        report=report,
        human_review=lambda request: review_requests.append(request) or {
            "decisions": [
                {"scorecard_id": "opaque-card", "score_id": "opaque-one", "decision": "approve", "comment": "go"},
                {"scorecard_id": "opaque-card", "score_id": "opaque-two", "decision": "reject", "comment": "not today"},
            ]
        },
    ))

    result = runner.run({
        "account_id": "account-1",
        "run_key": "daily-account-1-2026-07-01",
        "toolchain_version": "test-v1",
        "max_cost_usd": 5.0,
        "max_samples": 50,
        "max_iterations": 2,
        "max_concurrency": 1,
    })

    assert len(report.started) == 1
    assert report.milestones[0][0] == "started"
    assert [milestone[0] for milestone in report.milestones] == [
        "started", "ranking", "assessment", "diagnosis", "approval",
        "optimization", "optimization", "optimization_review", "finalization",
    ]
    assert review_requests[0]["action_key"] == "optimization-approval:daily-account-1-2026-07-01:1"
    assert review_requests[0]["response_schema"]["type"] == "object"
    assert review_requests[0]["expires_in_seconds"] == 24 * 60 * 60
    assert len(review_requests[0]["targets"]) == 2
    assert review_requests[0]["preconditions"]["targets"][0]["scorecard_name"] == "Example"
    assert review_requests[0]["preconditions"]["targets"][0]["score_name"] == "One"
    assert review_requests[0]["resource_refs"][0]["kind"] == "report"
    assert dispatches[0]["approved"] is True
    assert [(row["scorecard_id"], row["score_id"]) for row in dispatches[0]["targets"]] == [("opaque-card", "opaque-one")]
    assert dispatches[0]["max_samples"] == 50
    assert result["promotion_candidates"] == [{"scorecard_id": "opaque-card", "score_id": "opaque-one"}]
    assert report.terminal == ["COMPLETED"]


def test_incomplete_ranking_is_published_and_finalized_incomplete_without_assessment_or_optimizer_dispatch():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    calls = {"assess": 0, "review": 0, "dispatch": 0}
    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {"coverage": {"complete": False, "failures": ["page failed"]}, "ranked": []},
        assess=lambda _request: calls.__setitem__("assess", calls["assess"] + 1),
        diagnose=lambda _request: None,
        summary=lambda _request: {"coverage": {"complete": False}},
        dispatch=lambda _request: calls.__setitem__("dispatch", calls["dispatch"] + 1),
        review=lambda _request: calls.__setitem__("review", calls["review"] + 1),
        report=report,
        human_review=lambda _request: (_ for _ in ()).throw(AssertionError("must not ask for approval")),
    ))

    result = runner.run({"account_id": "account-1", "run_key": "incomplete", "limits": {"max_cost_usd": 1.0, "max_samples": 1, "max_iterations": 1, "max_concurrency": 1}})

    assert result["status"] == "INCOMPLETE"
    assert calls == {"assess": 0, "review": 0, "dispatch": 0}
    assert report.terminal == ["INCOMPLETE"]
    assert [row[0] for row in report.milestones] == ["started", "ranking", "finalization"]
    assert report.milestones[-1][2]["overview"]["lifecycle_status"] == "incomplete"


def test_ranking_and_all_assessments_are_published_as_distinct_milestones_before_semantic_diagnosis_begins():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    rank_packet = {
        "coverage": {"complete": True},
        "ranked": [
            {"scorecard_id": "card", "score_id": "one"},
            {"scorecard_id": "card", "score_id": "two"},
        ],
    }
    assessed: list[str] = []

    def assess(request):
        if not assessed:
            assert [row[0] for row in report.milestones] == ["started", "ranking"]
            ranking_evidence = report.milestones[-1][1]
            assert ranking_evidence["rank"]["ranked"] == rank_packet["ranked"]
            assert ranking_evidence["assessments"] == []
        assessed.append(request["score_id"])
        return _assessment(request["scorecard_id"], request["score_id"])

    def diagnose(request):
        assert assessed == ["one", "two"]
        assert [row[0] for row in report.milestones] == ["started", "ranking", "assessment"]
        published = report.milestones[-1][1]
        assert len(published["assessments"]) == 2
        assert published["diagnoses"] == []
        return {
            **request["assessment"],
            "states": {"optimization": "monitoring_candidate"},
        }

    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: rank_packet,
        assess=assess,
        diagnose=diagnose,
        summary=lambda _request: {"coverage": {"complete": True}},
        dispatch=lambda _request: (_ for _ in ()).throw(AssertionError("must not dispatch")),
        review=lambda _request: {},
        report=report,
        human_review=lambda _request: (_ for _ in ()).throw(AssertionError("must not request approval")),
    ))

    result = runner.run({"account_id": "account-1", "run_key": "assessment-first"})

    assert result["status"] == "COMPLETED"
    assert [row[0] for row in report.milestones[:4]] == [
        "started", "ranking", "assessment", "diagnosis"
    ]


def test_semantic_diagnosis_is_bounded_to_top_ten_plus_monitoring_candidates_in_rank_order():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    ranked = [
        {
            "scorecard_id": "card",
            "score_id": f"score-{index:02d}",
            "scorecard_name": "Example Portfolio",
            "score_name": f"Score {index:02d}",
        }
        for index in range(14)
    ]
    diagnosed: list[str] = []

    def assess(request):
        packet = _assessment(request["scorecard_id"], request["score_id"])
        if request["score_id"] in {"score-04", "score-11"}:
            packet["states"] = {"optimization": "monitoring_candidate"}
        return packet

    def diagnose(request):
        diagnosed.append(request["score_id"])
        return dict(request["assessment"])

    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {"coverage": {"complete": True}, "ranked": ranked},
        assess=assess,
        diagnose=diagnose,
        summary=lambda _request: {"coverage": {"complete": True}},
        dispatch=lambda _request: (_ for _ in ()).throw(AssertionError("must wait for approval")),
        review=lambda _request: {},
        report=report,
        human_review=lambda _request: {"decisions": []},
    ))

    result = runner.run({
        "account_id": "account-1",
        "run_key": "bounded-diagnosis",
        "wait_for_human": True,
        "max_semantic_diagnoses": 12,
    })

    assert diagnosed == [
        "score-00", "score-01", "score-02", "score-03", "score-04",
        "score-05", "score-06", "score-07", "score-08", "score-09",
        "score-11",
    ]
    diagnosis_evidence = next(
        evidence for milestone, evidence, _view in report.milestones
        if milestone == "diagnosis"
    )
    assert diagnosis_evidence["diagnosis_coverage"] == {
        "policy_version": "portfolio-diagnosis-scope-v1",
        "ranked_count": 14,
        "top_priority_count": 10,
        "monitoring_candidate_count": 2,
        "overlap_count": 1,
        "selected_count": 11,
        "scheduled_count": 11,
        "deferred_by_cap_count": 0,
        "completed_count": 11,
        "failed_count": 0,
        "skipped_count": 3,
        "max_semantic_diagnoses": 12,
        "scheduled_scope_complete": True,
        "selected_scope_complete": True,
        "portfolio_semantic_complete": False,
        "blockers": [],
    }
    approval_target_ids = {
        target["score_id"]
        for request in result["approval_requests"]
        for target in request["targets"]
    }
    assert approval_target_ids == {
        "score-00", "score-01", "score-02", "score-03",
        "score-05", "score-06", "score-07", "score-08", "score-09",
    }
    diagnosis_view = next(
        view for milestone, _evidence, view in report.milestones
        if milestone == "diagnosis"
    )
    assert diagnosis_view["portfolio"][10]["readiness"] == "incomplete"
    assert diagnosis_view["portfolio"][10]["next_action"] == "await_semantic_diagnosis"


def test_semantic_diagnosis_limit_runs_the_highest_priority_subset_and_reports_deferred_coverage():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    diagnosed: list[str] = []
    ranked = [
        {"scorecard_id": "card", "score_id": f"score-{index:02d}"}
        for index in range(10)
    ]
    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {"coverage": {"complete": True}, "ranked": ranked},
        assess=lambda request: _assessment(request["scorecard_id"], request["score_id"]),
        diagnose=lambda request: diagnosed.append(request["score_id"]) or {
            **request["assessment"],
            "states": {"optimization": "repair_required"},
        },
        summary=lambda _request: {"coverage": {"complete": True}},
        dispatch=lambda _request: (_ for _ in ()).throw(AssertionError("must not dispatch")),
        review=lambda _request: {},
        report=report,
        human_review=lambda _request: (_ for _ in ()).throw(AssertionError("must not request approval")),
    ))

    result = runner.run({
        "account_id": "account-1",
        "run_key": "semantic-limit",
        "max_semantic_diagnoses": 2,
    })

    assert result["status"] == "INCOMPLETE"
    assert diagnosed == ["score-00", "score-01"]
    assert report.terminal == ["INCOMPLETE"]
    coverage = result["diagnosis_coverage"]
    assert coverage["selected_count"] == 10
    assert coverage["scheduled_count"] == 2
    assert coverage["deferred_by_cap_count"] == 8
    assert coverage["completed_count"] == 2
    assert coverage["scheduled_scope_complete"] is True
    assert coverage["selected_scope_complete"] is False
    assert coverage["blockers"] == []

    diagnosis_view = next(
        view for milestone, _evidence, view in report.milestones
        if milestone == "diagnosis"
    )
    assert diagnosis_view["overview"]["diagnosis_coverage"] == (
        "2 of 2 scheduled diagnoses returned; 0 incomplete results; "
        "0 execution failures; 8 deferred by the safety cap"
    )
    assert diagnosis_view["overview"]["diagnosis_scheduled_count"] == 2
    assert diagnosis_view["overview"]["diagnosis_deferred_count"] == 8


def test_zero_semantic_diagnosis_limit_defers_selected_work_without_invoking_a_model():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    diagnosed: list[str] = []
    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {
            "coverage": {"complete": True},
            "ranked": [{"scorecard_id": "card", "score_id": "score-00"}],
        },
        assess=lambda request: _assessment(request["scorecard_id"], request["score_id"]),
        diagnose=lambda request: diagnosed.append(request["score_id"]) or request["assessment"],
        summary=lambda _request: {"coverage": {"complete": True}},
        dispatch=lambda _request: (_ for _ in ()).throw(AssertionError("must not dispatch")),
        review=lambda _request: {},
        report=report,
        human_review=lambda _request: (_ for _ in ()).throw(AssertionError("must not request approval")),
    ))

    result = runner.run({
        "account_id": "account-1",
        "run_key": "zero-semantic-limit",
        "max_semantic_diagnoses": 0,
    })

    assert result["status"] == "INCOMPLETE"
    assert diagnosed == []
    assert result["diagnosis_coverage"]["scheduled_count"] == 0
    assert result["diagnosis_coverage"]["deferred_by_cap_count"] == 1
    assert result["diagnosis_coverage"]["failed_count"] == 0


def test_diagnosis_failure_preserves_the_published_assessment_milestone():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {
            "coverage": {"complete": True},
            "ranked": [{
                "scorecard_id": "card",
                "score_id": "score",
                "scorecard_name": "Example Portfolio",
                "score_name": "Priority Score",
            }],
        },
        assess=lambda request: _assessment(request["scorecard_id"], request["score_id"]),
        diagnose=lambda _request: (_ for _ in ()).throw(RuntimeError("diagnosis unavailable")),
        summary=lambda _request: {},
        dispatch=lambda _request: (_ for _ in ()).throw(AssertionError("must not dispatch")),
        review=lambda _request: {},
        report=report,
        human_review=lambda _request: (_ for _ in ()).throw(AssertionError("must not request approval")),
    ))

    result = runner.run({"account_id": "account-1", "run_key": "diagnosis-failure"})

    assert result["status"] == "FAILED"
    assert result["error"] == "diagnosis unavailable"
    assert [row[0] for row in report.milestones] == ["started", "ranking", "assessment"]
    assert report.milestones[-1][1]["assessments"]
    assert report.milestones[-1][1]["diagnoses"] == []
    assert report.failures == ["Optimization portfolio run failed: diagnosis unavailable"]


def test_stale_or_rejected_targets_are_reported_and_never_receive_terminal_review_or_promotion():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    reviews: list[dict[str, Any]] = []
    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {"coverage": {"complete": True}, "window": {"start": "a", "end": "b"}, "ranked": [{"scorecard_id": "card", "score_id": "score"}]},
        assess=lambda request: _assessment(request["scorecard_id"], request["score_id"]),
        diagnose=lambda request: request["assessment"],
        summary=lambda _request: {"coverage": {"complete": True}},
        dispatch=lambda _request: {"accepted": False, "rejected": [{"reason": "stale_assessment"}], "dispatches": []},
        review=lambda request: reviews.append(request) or {},
        report=report,
        human_review=lambda _request: {"decisions": [{"scorecard_id": "card", "score_id": "score", "decision": "approve"}]},
    ))

    result = runner.run({"account_id": "account-1", "run_key": "stale", "limits": {"max_cost_usd": 1.0, "max_samples": 1, "max_iterations": 1, "max_concurrency": 1}})

    assert result["status"] == "INCOMPLETE"
    assert result["promotion_candidates"] == []
    assert reviews == []
    assert report.terminal == ["INCOMPLETE"]


def test_tactus_checkpoint_mode_leaves_the_same_report_running_until_an_authoritative_review_response_arrives():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {"coverage": {"complete": True}, "window": {"start": "a", "end": "b"}, "ranked": [{"scorecard_id": "card", "score_id": "score"}]},
        assess=lambda request: _assessment(request["scorecard_id"], request["score_id"]),
        diagnose=lambda request: request["assessment"],
        summary=lambda _request: {},
        dispatch=lambda _request: (_ for _ in ()).throw(AssertionError("dispatch must wait for Human.review")),
        review=lambda _request: None,
        report=report,
        human_review=lambda _request: {"decisions": []},
    ))

    result = runner.run({"account_id": "account-1", "run_key": "wait", "wait_for_human": True, "limits": {"max_cost_usd": 1.0, "max_samples": 1, "max_iterations": 1, "max_concurrency": 1}})

    assert result["status"] == "WAITING_FOR_APPROVAL"
    assert report.terminal == []
    assert result["approval_requests"][0]["action_key"] == "optimization-approval:wait:1"


def test_tactus_suspension_happens_only_after_pending_approval_is_durable_in_the_report():
    import pytest
    from tactus.core.exceptions import ProcedureWaitingForHuman
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {
            "coverage": {"complete": True},
            "ranked": [{
                "scorecard_id": "card",
                "score_id": "score",
                "scorecard_name": "Example Portfolio",
                "score_name": "Priority Score",
            }],
        },
        assess=lambda request: _assessment(request["scorecard_id"], request["score_id"]),
        diagnose=lambda request: request["assessment"],
        summary=lambda _request: {},
        dispatch=lambda _request: (_ for _ in ()).throw(AssertionError("must not dispatch")),
        review=lambda _request: {},
        report=report,
        human_review=lambda _request: (_ for _ in ()).throw(
            ProcedureWaitingForHuman("procedure-1", "message-1")
        ),
    ))

    with pytest.raises(ProcedureWaitingForHuman):
        runner.run({"account_id": "account-1", "run_key": "suspend"})

    assert report.milestones[-1][0] == "approval"
    approval_evidence = report.milestones[-1][1]
    assert approval_evidence["approval_requests"][0]["action_key"] == "optimization-approval:suspend:1"
    assert report.terminal == []


def test_saved_approval_cannot_authorize_recomputed_evidence():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    dispatches: list[dict[str, Any]] = []
    fingerprint = {"value": "fingerprint-before-review"}
    human_response = {"value": {"decisions": []}}

    def assess(request):
        packet = _assessment(request["scorecard_id"], request["score_id"])
        packet["evidence_fingerprint"] = fingerprint["value"]
        packet["fingerprint"] = fingerprint["value"]
        return packet

    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {
            "coverage": {"complete": True},
            "ranked": [{"scorecard_id": "card", "score_id": "score"}],
        },
        assess=assess,
        diagnose=lambda request: request["assessment"],
        summary=lambda _request: {},
        dispatch=lambda request: dispatches.append(request) or {},
        review=lambda _request: {},
        report=report,
        human_review=lambda _request: human_response["value"],
    ))

    prepared = runner.run({
        "account_id": "account-1",
        "run_key": "frozen-approval",
        "wait_for_human": True,
    })
    original_request = prepared["approval_requests"][0]
    fingerprint["value"] = "fingerprint-after-review"
    human_response["value"] = {
        "decisions": [
            {"scorecard_id": "card", "score_id": "score", "decision": "approve"}
        ]
    }

    resumed = runner.run({
        "account_id": "account-1",
        "run_key": "frozen-approval",
        "wait_for_human": True,
        "approval_responses": {
            original_request["action_key"]: {
                "request": original_request,
                "response": {
                    "decisions": [
                        {"scorecard_id": "card", "score_id": "score", "decision": "approve"}
                    ]
                },
            }
        },
    })

    assert resumed["status"] == "WAITING_FOR_APPROVAL"
    assert dispatches == []
    assert resumed["approval_requests"][0]["preconditions"]["targets"][0][
        "assessment_fingerprint"
    ] == "fingerprint-after-review"


def test_every_five_target_approval_batch_is_resolved_before_any_dispatch():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    dispatches: list[dict[str, Any]] = []
    ranked = [
        {"scorecard_id": "card", "score_id": f"score-{index}"}
        for index in range(6)
    ]
    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {"coverage": {"complete": True}, "ranked": ranked},
        assess=lambda request: _assessment(request["scorecard_id"], request["score_id"]),
        diagnose=lambda request: request["assessment"],
        summary=lambda _request: {},
        dispatch=lambda request: dispatches.append(request) or {
            "accepted": True,
            "dispatches": [],
        },
        review=lambda _request: {},
        report=report,
        human_review=lambda _request: {"decisions": []},
    ))

    prepared = runner.run({
        "account_id": "account-1",
        "run_key": "two-batches",
        "wait_for_human": True,
    })
    first, second = prepared["approval_requests"]
    first_response = {
        "decisions": [
            {
                "scorecard_id": row["scorecard_id"],
                "score_id": row["score_id"],
                "decision": "approve" if index == 0 else "reject",
            }
            for index, row in enumerate(first["targets"])
        ]
    }
    approvals = {
        first["action_key"]: {"request": first, "response": first_response},
    }

    after_first = runner.run({
        "account_id": "account-1",
        "run_key": "two-batches",
        "wait_for_human": True,
        "approval_responses": approvals,
    })

    assert after_first["status"] == "WAITING_FOR_APPROVAL"
    assert [row["action_key"] for row in after_first["approval_requests"]] == [
        second["action_key"]
    ]
    assert dispatches == []

    approvals[second["action_key"]] = {
        "request": second,
        "response": {
            "decisions": [
                {
                    "scorecard_id": row["scorecard_id"],
                    "score_id": row["score_id"],
                    "decision": "reject",
                }
                for row in second["targets"]
            ]
        },
    }
    completed = runner.run({
        "account_id": "account-1",
        "run_key": "two-batches",
        "wait_for_human": True,
        "approval_responses": approvals,
    })

    assert completed["status"] == "COMPLETED"
    assert len(dispatches) == 1
    assert [row["score_id"] for row in dispatches[0]["targets"]] == ["score-0"]


def test_report_publication_failure_stops_the_run_before_any_optimizer_dispatch():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner
    from plexus.optimization.run_report import OptimizationRunPublicationError

    class _FailingReport(_ReportService):
        def publish_milestone(self, milestone, evidence, *, stakeholder_view):
            raise OptimizationRunPublicationError(f"cannot publish {milestone}")

    report = _FailingReport()
    dispatched = []
    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {"coverage": {"complete": True}, "ranked": []},
        assess=lambda _request: None,
        diagnose=lambda _request: None,
        summary=lambda _request: {},
        dispatch=lambda request: dispatched.append(request),
        review=lambda _request: None,
        report=report,
        human_review=lambda _request: None,
    ))

    result = runner.run({"account_id": "account-1", "run_key": "publication-failure", "limits": {"max_cost_usd": 1.0, "max_samples": 1, "max_iterations": 1, "max_concurrency": 1}})

    assert result["status"] == "FAILED"
    assert dispatched == []
    assert report.failures


def test_nonblocking_findings_are_persisted_as_existing_chat_messages_and_report_their_authoritative_state():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    action_inputs: list[dict[str, Any]] = []
    assessment = _assessment("card", "score")
    assessment["scorecard_name"] = "Example Portfolio"
    assessment["score_name"] = "Priority Score"
    diagnosis = {
        **assessment,
        "states": {"optimization": "stakeholder_clarification_required"},
        "stakeholder_questions": ["Which policy should apply?"],
    }
    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {
            "coverage": {"complete": True},
            "ranked": [{"scorecard_id": "card", "score_id": "score"}],
        },
        assess=lambda _request: assessment,
        diagnose=lambda _request: diagnosis,
        summary=lambda _request: {"coverage": {"complete": True}},
        dispatch=lambda _request: (_ for _ in ()).throw(AssertionError("must not dispatch")),
        review=lambda _request: {},
        report=report,
        human_review=lambda _request: (_ for _ in ()).throw(AssertionError("must not request launch approval")),
        create_action=lambda action: action_inputs.append(action) or {
            "action": {"id": "chat-message-1", "responseStatus": "COMPLETED", "responseOwner": "response-1"},
            "created": False,
            "resolution": {"response_message_id": "response-1", "response": {"response": "Use the documented policy."}},
        },
    ))

    result = runner.run({"account_id": "account-1", "run_key": "questions"})

    assert action_inputs[0]["action_key"].startswith("stakeholder_clarification:questions:")
    assert action_inputs[0]["title"] == "Clarify policy for Priority Score"
    assert action_inputs[0]["message"] == "Which policy should apply?"
    assert action_inputs[0]["payload"]["scorecard_name"] == "Example Portfolio"
    assert action_inputs[0]["payload"]["score_name"] == "Priority Score"
    assert action_inputs[0]["resource_refs"][1]["label"] == "Example Portfolio — Priority Score"
    assert result["actions"][0]["message_id"] == "chat-message-1"
    assert result["actions"][0]["response_status"] == "COMPLETED"
    assert result["actions"][0]["response_message_id"] == "response-1"


def test_stakeholder_projection_preserves_available_counts_states_trends_and_actions_without_opaque_ids():
    from plexus.optimization.portfolio_run import _stakeholder_view

    view = _stakeholder_view({
        "rank": {
            "coverage": {"complete": True},
            "window": {"start": "2026-04-01T00:00:00Z", "end": "2026-07-01T00:00:00Z"},
            "ranked": [{
                "scorecard_id": "opaque-card",
                "score_id": "opaque-score",
                "scorecard_name": "Example Portfolio",
                "score_name": "Priority Score",
                "valid_feedback_count": 240,
                "reviewed_disagreements": 48,
                "disagreement_rate": 0.2,
                "reviewed_error_opportunity": 48,
                "dashboard_url": "https://dashboard.example/scores/summary",
            }],
        },
        "assessments": [{
            "scope": {"scorecard_id": "opaque-card", "score_id": "opaque-score"},
            "coverage": {"complete": True},
            "states": {
                "optimization": "ready_to_optimize",
                "feedback_collection": "continue_broad_collection",
                "guideline_health": "consistent",
                "feedback_rubric_health": "consistent",
                "promotion_readiness": "not_evaluated",
            },
            "weekly_stability": {
                "weekly_disagreement_range": 0.03,
                "weekly_ac1_range": 0.04,
                "weekly_bucket_counts": [20, 24, 22, 26],
            },
            "rationale": "Reviewed errors show a safe improvement opportunity.",
            "primary_next_action": "request_optimization_approval",
        }],
        "diagnoses": [],
        "reviews": [],
        "dispatch": None,
    }, milestone="assessment")

    row = view["portfolio"][0]
    assert row["coverage_status"] == "complete"
    assert row["collection_state"] == "continue_broad_collection"
    assert row["guideline_state"] == "consistent"
    assert row["feedback_rubric_state"] == "consistent"
    assert row["promotion_readiness"] == "not_evaluated"
    assert row["rationale"] == "Reviewed errors show a safe improvement opportunity."
    assert row["next_action"] == "request_optimization_approval"
    assert "20, 24, 22, 26" in row["trend"]
    assert row["dashboard_url"].startswith("https://")
    assert "opaque-card" not in str(view)
    assert "opaque-score" not in str(view)
    assert view["priorities"][0]["evidence_count"] == 240
    assert view["feedback_investment"][0]["coverage_status"] == "complete"


def test_stakeholder_overview_explains_current_work_and_next_durable_checkpoint():
    from plexus.optimization.portfolio_run import _stakeholder_view

    started = _stakeholder_view({
        "rank": None,
        "assessments": [],
        "diagnoses": [],
        "reviews": [],
        "approval_requests": [],
        "diagnosis_coverage": {"selected_count": 0, "completed_count": 0, "failed_count": 0},
    }, milestone="started")
    assert started["overview"]["coverage_status"] == "pending"
    assert started["overview"]["inventory_coverage_status"] == "pending"
    assert started["overview"]["analysis_coverage_status"] == "pending"
    assert "Enumerating every scorecard" in started["overview"]["current_activity"]
    assert "ranked portfolio" in started["overview"]["next_checkpoint"]

    ranked = _stakeholder_view({
        "rank": {
            "coverage": {
                "complete": True,
                "scope": {
                    "total_scorecards_inspected": 12,
                    "matched_scorecard_count": 1,
                },
                "activity": {"recent_activity_excluded_count": 3},
            },
            "ranked": [{"scorecard_id": "card", "score_id": "score"}],
            "unranked": [{}, {}],
            "window": {"start": "a", "end": "b"},
        },
        "assessments": [],
        "diagnoses": [],
        "reviews": [],
        "approval_requests": [],
        "diagnosis_coverage": {"selected_count": 1, "completed_count": 0, "failed_count": 0},
    }, milestone="ranking")
    assert ranked["overview"]["scorecards_inspected"] == 12
    assert ranked["overview"]["scorecards_in_scope"] == 1
    assert ranked["overview"]["ranked_score_count"] == 1
    assert ranked["overview"]["unranked_score_count"] == 2
    assert ranked["overview"]["cooldown_excluded_count"] == 3
    assert ranked["overview"]["assessment_progress"] == "0 of 1 eligible candidates assessed"
    assert "deterministic readiness" in ranked["overview"]["current_activity"]


def test_stakeholder_overview_does_not_imply_optimizer_work_when_no_targets_were_approved():
    from plexus.optimization.portfolio_run import _stakeholder_view

    state = {
        "rank": {"coverage": {"complete": True}, "ranked": []},
        "assessments": [],
        "diagnoses": [],
        "reviews": [],
        "approved_targets": [],
        "dispatch": {"batches": [], "rejected": []},
        "approval_requests": [],
        "diagnosis_coverage": {
            "selected_count": 0,
            "scheduled_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "deferred_by_cap_count": 0,
        },
    }

    optimization = _stakeholder_view(state, milestone="optimization")["overview"]
    assert "no optimizations were launched" in optimization["current_activity"].lower()
    assert "evaluations will be reviewed" not in optimization["next_checkpoint"].lower()

    review = _stakeholder_view(state, milestone="optimization_review")["overview"]
    assert "no optimization results" in review["current_activity"].lower()
    assert "reviewing completed optimizer" not in review["current_activity"].lower()


def test_stakeholder_overview_retains_active_narration_for_dispatched_optimizer_work():
    from plexus.optimization.portfolio_run import _stakeholder_view

    state = {
        "rank": {"coverage": {"complete": True}, "ranked": []},
        "assessments": [],
        "diagnoses": [],
        "reviews": [{"procedure_id": "procedure-1"}],
        "approved_targets": [{"scorecard_id": "card", "score_id": "score"}],
        "dispatch": {
            "batches": [{
                "dispatches": [{"status": "dispatched", "procedure_id": "procedure-1"}],
            }],
            "rejected": [],
        },
        "approval_requests": [],
        "diagnosis_coverage": {
            "selected_count": 0,
            "scheduled_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "deferred_by_cap_count": 0,
        },
    }

    optimization = _stakeholder_view(state, milestone="optimization")["overview"]
    assert "approved optimization" in optimization["current_activity"].lower()
    review = _stakeholder_view(state, milestone="optimization_review")["overview"]
    assert "optimizer and evaluation evidence" in review["current_activity"].lower()


def test_stakeholder_overview_separates_complete_inventory_from_incomplete_diagnosis_results():
    from plexus.optimization.portfolio_run import _stakeholder_view
    from plexus.optimization.run_report import _validate_view

    base_state = {
        "rank": {
            "coverage": {"complete": True},
            "ranked": [{
                "scorecard_id": "card",
                "score_id": "score",
                "scorecard_name": "Example Portfolio",
                "score_name": "Priority Score",
                "valid_feedback_count": 240,
                "reviewed_disagreements": 48,
                "disagreement_rate": 0.2,
                "reviewed_error_opportunity": 48,
            }],
        },
        "assessments": [{
            "scope": {"scorecard_id": "card", "score_id": "score"},
            "coverage": {"complete": True},
            "states": {"optimization": "ready_to_optimize"},
        }],
        "reviews": [],
        "approval_requests": [],
        "diagnosis_coverage": {
            "selected_count": 1,
            "scheduled_count": 1,
            "completed_count": 1,
            "failed_count": 0,
            "deferred_by_cap_count": 0,
        },
    }
    incomplete = _stakeholder_view({
        **base_state,
        "diagnoses": [{
            "scope": {"scorecard_id": "card", "score_id": "score"},
            "states": {"optimization": "incomplete", "readiness": "incomplete"},
            "outcome": "incomplete",
            "failures": ["Required evidence could not be read."],
        }],
        "terminal_status": "INCOMPLETE",
    }, milestone="finalization")

    overview = incomplete["overview"]
    assert overview["coverage_status"] == "complete"
    assert overview["inventory_coverage_status"] == "complete"
    assert overview["analysis_coverage_status"] == "incomplete"
    assert overview["diagnosis_incomplete_count"] == 1
    assert overview["diagnosis_coverage"] == (
        "1 of 1 scheduled diagnoses returned; 1 incomplete result; "
        "0 execution failures; 0 deferred by the safety cap"
    )
    _validate_view(incomplete)

    complete = _stakeholder_view({
        **base_state,
        "diagnoses": [{
            "scope": {"scorecard_id": "card", "score_id": "score"},
            "coverage": {"complete": True},
            "states": {"optimization": "ready_to_optimize"},
            "outcome": "ready_to_optimize",
        }],
    }, milestone="diagnosis")
    assert complete["overview"]["inventory_coverage_status"] == "complete"
    assert complete["overview"]["analysis_coverage_status"] == "complete"
    assert complete["overview"]["diagnosis_incomplete_count"] == 0


def test_stakeholder_overview_explains_ranking_and_semantic_diagnosis_cutoffs():
    from plexus.optimization.portfolio_run import _stakeholder_view
    from plexus.optimization.run_report import _validate_view

    ranked_rows = [
        {
            "scorecard_id": "card",
            "score_id": f"score-{index:02d}",
            "scorecard_name": "Example Portfolio",
            "score_name": f"Score {index:02d}",
            "valid_feedback_count": 200 + index,
            "reviewed_disagreements": 30 - index,
            "disagreement_rate": (30 - index) / (200 + index),
            "reviewed_error_opportunity": 30 - index,
        }
        for index in range(12)
    ]
    view = _stakeholder_view({
        "rank": {
            "coverage": {"complete": True},
            "ranked": ranked_rows,
            "unranked": [],
            "window": {"start": "a", "end": "b"},
        },
        "assessments": [],
        "diagnoses": [],
        "reviews": [],
        "approval_requests": [],
        "diagnosis_coverage": {
            "top_priority_count": 10,
            "monitoring_candidate_count": 1,
            "selected_count": 11,
            "scheduled_count": 5,
            "deferred_by_cap_count": 6,
            "completed_count": 0,
            "failed_count": 0,
            "skipped_count": 1,
            "max_semantic_diagnoses": 5,
        },
    }, milestone="assessment")

    overview = view["overview"]
    assert overview["ranking_cutoff"] == "none"
    assert overview["priority_display_limit"] == 10
    assert overview["priority_displayed_count"] == 10
    assert overview["priority_cutoff_rank"] == 10
    assert overview["priority_cutoff_opportunity"] == 21
    assert overview["ranked_below_priority_cutoff"] == 2
    assert overview["diagnosis_selected_count"] == 11
    assert overview["diagnosis_scheduled_count"] == 5
    assert overview["diagnosis_deferred_count"] == 6
    assert overview["diagnosis_skipped_count"] == 1
    assert overview["diagnosis_max_count"] == 5
    assert overview["diagnosis_coverage"] == (
        "0 of 5 scheduled diagnoses returned; 0 incomplete results; "
        "0 execution failures; 6 deferred by the safety cap"
    )
    assert view["priorities"][0]["rank"] == 1
    assert view["priorities"][0]["disagreement_rate"] == 0.15
    assert view["feedback_investment"][0]["rank"] == 1
    assert view["optimization_outcomes"][0]["rank"] == 1
    _validate_view(view)

    zero_cap_view = _stakeholder_view({
        "rank": {
            "coverage": {"complete": True},
            "ranked": ranked_rows,
            "unranked": [],
        },
        "diagnosis_coverage": {
            "selected_count": 10,
            "scheduled_count": 0,
            "deferred_by_cap_count": 10,
            "max_semantic_diagnoses": 0,
        },
    }, milestone="assessment")
    assert zero_cap_view["overview"]["diagnosis_max_count"] == 0
    assert zero_cap_view["overview"]["diagnosis_scheduled_count"] == 0
    assert zero_cap_view["overview"]["diagnosis_deferred_count"] == 10


def test_stakeholder_view_preserves_pre_policy_rank_and_visible_cooldown_disposition():
    from plexus.optimization.portfolio_run import _stakeholder_view

    view = _stakeholder_view({
        "rank": {
            "coverage": {
                "complete": True,
                "activity": {"recent_activity_excluded_count": 1},
            },
            "ranked": [{
                "scorecard_id": "card",
                "score_id": "eligible",
                "scorecard_name": "Example Portfolio",
                "score_name": "Eligible Score",
                "valid_feedback_count": 100,
                "reviewed_disagreements": 20,
                "disagreement_rate": 0.2,
                "reviewed_error_opportunity": 20,
                "evidence_rank": 2,
                "candidate_rank": 1,
                "policy_disposition": "eligible",
                "policy_reason": "meets_rank_policy",
                "eligible_for_optimization": True,
            }],
            "unranked": [{
                "scorecard_id": "card",
                "score_id": "cooldown",
                "scorecard_name": "Example Portfolio",
                "score_name": "Recently Changed Score",
                "valid_feedback_count": 100,
                "reviewed_disagreements": 80,
                "disagreement_rate": 0.8,
                "reviewed_error_opportunity": 80,
                "evidence_rank": 1,
                "policy_disposition": "cooldown",
                "policy_reason": "recent_score_activity",
                "eligible_for_optimization": False,
                "score_activity": {"eligible_at": "2026-08-05T00:00:00Z"},
                "unranked_reason": "recent_score_activity",
            }],
        },
        "assessments": [],
        "diagnoses": [],
        "reviews": [],
        "approval_requests": [],
        "diagnosis_coverage": {"selected_count": 0, "max_semantic_diagnoses": 10},
    }, milestone="ranking")

    assert [row["score_name"] for row in view["priorities"]] == [
        "Recently Changed Score",
        "Eligible Score",
    ]
    cooldown = view["priorities"][0]
    assert cooldown["rank"] == 1
    assert cooldown["candidate_rank"] is None
    assert cooldown["policy_disposition"] == "cooldown"
    assert cooldown["policy_reason"] == "recent_score_activity"
    assert cooldown["next_action"] == "wait_for_cooldown"
    assert cooldown["eligibility_timestamp"] == "2026-08-05T00:00:00Z"
    assert view["overview"]["evidence_ranked_score_count"] == 2
    assert view["overview"]["ranked_score_count"] == 1
