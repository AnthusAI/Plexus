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
    report: Any = field(default_factory=lambda: type("Report", (), {"id": "report-1"})())

    def start_or_resume(self, run_spec):
        self.started.append(dict(run_spec))
        return type("State", (), {"report": self.report})()

    def publish_milestone(self, milestone, evidence, *, stakeholder_view):
        self.milestones.append((milestone, dict(evidence), dict(stakeholder_view)))
        return object()

    def finalize(self, *, status="COMPLETED"):
        self.terminal.append(status)

    def fail(self, message):
        self.failures.append(str(message))


def _dependencies(
    *, rank, assess, diagnose, summary, dispatch, review, report, human_review,
    create_action=None,
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
    )


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
        "started", "ranking_assessment", "diagnosis", "approval", "optimization_review", "finalization"
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
    assert [row[0] for row in report.milestones] == ["started", "ranking_assessment", "finalization"]


def test_all_assessments_are_published_before_semantic_diagnosis_begins():
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
        assessed.append(request["score_id"])
        return _assessment(request["scorecard_id"], request["score_id"])

    def diagnose(request):
        assert assessed == ["one", "two"]
        assert [row[0] for row in report.milestones] == ["started", "ranking_assessment"]
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
    assert [row[0] for row in report.milestones[:3]] == [
        "started", "ranking_assessment", "diagnosis"
    ]


def test_diagnosis_failure_preserves_the_published_assessment_milestone():
    from plexus.optimization.portfolio_run import OptimizationPortfolioRunner

    report = _ReportService()
    runner = OptimizationPortfolioRunner(_dependencies(
        rank=lambda _request: {
            "coverage": {"complete": True},
            "ranked": [{"scorecard_id": "card", "score_id": "score"}],
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
    assert [row[0] for row in report.milestones] == ["started", "ranking_assessment"]
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
