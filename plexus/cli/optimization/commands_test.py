from __future__ import annotations

import json

import pytest
from click.testing import CliRunner


def _ready_target(
    scorecard_id: str, score_id: str, champion_version: str = "champion",
    feedback_watermark: str = "watermark",
) -> dict:
    from plexus.optimization.decision import assess_investment

    assessment = assess_investment({
        "scorecard_id": scorecard_id, "score_id": score_id,
        "complete": True, "champion_version": champion_version,
        "feedback_watermark": feedback_watermark,
        "terminal_classes_resolved": True, "guideline_state": "consistent",
        "valid_feedback_count": 250, "reviewed_disagreements": 200,
        "reachable_classes": ["Yes", "No"],
        "final_label_counts": {"Yes": 125, "No": 125},
        "weekly_disagreement_rates": [0.8] * 4,
        "weekly_ac1_values": [0.7] * 4,
        "weekly_bucket_counts": [20] * 4,
    })
    assert assessment["readiness_state"] == "ready_to_optimize"
    return {
        "scorecard_id": scorecard_id, "score_id": score_id,
        "assessment": assessment,
        "assessment_fingerprint": assessment["evidence_fingerprint"],
        "champion_version": champion_version,
        "feedback_watermark": feedback_watermark,
    }


@pytest.mark.parametrize(
    "operation",
    ["rank", "assess", "diagnose", "run", "review", "summary"],
)
def test_optimization_commands_delegate_json_payload_to_handler(monkeypatch, operation) -> None:
    from plexus.cli.optimization import commands

    observed = {}

    def fake_dispatch(actual_operation, payload):
        observed["operation"] = actual_operation
        observed["payload"] = payload
        return {"operation": actual_operation, "ok": True}

    monkeypatch.setattr(commands, "dispatch_optimization_operation", fake_dispatch)
    persisted = []
    monkeypatch.setattr(
        commands,
        "_persist_returned_packet",
        lambda result, request: persisted.append((result, request)),
    )

    result = CliRunner().invoke(
        commands.optimization,
        [operation, "--input", '{"account_id":"account-1"}', "--persist"],
    )

    assert result.exit_code == 0, result.output
    assert observed == {
        "operation": operation,
        "payload": {"account_id": "account-1", "persist": True},
    }
    assert json.loads(result.output) == {"operation": operation, "ok": True}
    assert persisted == [
        ({"operation": operation, "ok": True}, {"account_id": "account-1", "persist": True})
    ]


def test_optimization_commands_merge_typed_options_and_reject_non_object_input(monkeypatch) -> None:
    from plexus.cli.optimization import commands

    observed = {}
    monkeypatch.setattr(
        commands,
        "dispatch_optimization_operation",
        lambda operation, payload: observed.update(operation=operation, payload=payload) or {},
    )

    result = CliRunner().invoke(
        commands.optimization,
        ["rank", "--input", "{}", "--option", "limit=5", "--option", "approved=true"],
    )
    assert result.exit_code == 0, result.output
    assert observed == {
        "operation": "rank",
        "payload": {"limit": 5, "approved": True, "persist": False},
    }

    bad_result = CliRunner().invoke(commands.optimization, ["rank", "--input", "[]"])
    assert bad_result.exit_code != 0
    assert "JSON object" in bad_result.output


def test_persist_false_does_not_invoke_cli_persistence(monkeypatch) -> None:
    from plexus.cli.optimization import commands

    monkeypatch.setattr(commands, "dispatch_optimization_operation", lambda _operation, _payload: {})
    monkeypatch.setattr(
        commands,
        "_persist_returned_packet",
        lambda _result, _request: pytest.fail("persistence should not run"),
    )

    result = CliRunner().invoke(commands.optimization, ["summary", "--input", "{}"])

    assert result.exit_code == 0, result.output


def test_review_loads_procedure_evidence_through_injected_indexed_service(monkeypatch) -> None:
    from plexus.cli.optimization import commands

    observed = []
    monkeypatch.setattr(
        commands,
        "_load_indexed_optimizer_review_evidence",
        lambda procedure_id: observed.append(procedure_id) or {
            "indexed_optimizer_review": True,
            "candidate_version_id": "candidate-1",
            "terminal": True,
            "matched_recent_evaluation": True,
            "historical_regression_evidence": True,
            "class_specific_metrics": True,
            "prediction_collapse": False,
            "rca_complete": True,
            "artifacts_complete": True,
            "measurable_safe_improvement": True,
        },
    )

    result = CliRunner().invoke(
        commands.optimization, ["review", "--input", '{"procedure_id":"proc-1"}']
    )

    assert result.exit_code == 0, result.output
    assert observed == ["proc-1"]
    assert json.loads(result.output)["post_run_state"] == "promotion_ready"


def test_review_procedure_with_missing_or_unindexed_artifacts_fails_closed(monkeypatch) -> None:
    from plexus.cli.optimization import commands

    monkeypatch.setattr(
        commands,
        "_load_indexed_optimizer_review_evidence",
        lambda procedure_id: {
            "terminal": False,
            "incomplete": True,
            "artifacts_complete": False,
            "procedure_id": procedure_id,
        },
    )

    result = CliRunner().invoke(
        commands.optimization, ["review", "--input", '{"procedure_id":"proc-unindexed"}']
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["post_run_state"] == "failed_or_incomplete"
    assert payload["promotion_ready"] is False


def test_review_ignores_caller_supplied_promotion_booleans_without_indexed_procedure() -> None:
    from plexus.cli.optimization import commands

    result = CliRunner().invoke(
        commands.optimization,
        [
            "review",
            "--input",
            json.dumps({
                "evidence": {
                    "terminal": True,
                    "matched_recent_evaluation": True,
                    "historical_regression_evidence": True,
                    "class_specific_metrics": True,
                    "prediction_collapse": False,
                    "rca_complete": True,
                    "artifacts_complete": True,
                    "measurable_safe_improvement": True,
                },
            }),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["post_run_state"] == "failed_or_incomplete"
    assert payload["promotion_ready"] is False


def test_indexed_review_normalization_does_not_claim_unknown_safety_evidence() -> None:
    from plexus.cli.optimization.commands import _normalize_indexed_optimizer_review

    evidence = _normalize_indexed_optimizer_review(
        {
            "summary": {"effective_status": "COMPLETED"},
            "baseline": {
                "original_accuracy_evaluation_id": "historical",
                "feedback_alignment": 0.6,
            },
            "best": {
                "winning_version_id": "candidate",
                "best_feedback_evaluation_id": "recent",
                "best_accuracy_evaluation_id": "regression",
                "feedback_alignment": 0.8,
            },
            "artifact_pointer": {"manifest": "tasks/task/optimizer/manifest.json"},
        },
        "proc-1",
    )

    assert evidence["terminal"] is True
    assert evidence["matched_recent_evaluation"] is False
    assert evidence["historical_regression_evidence"] is False
    assert evidence["class_specific_metrics"] is False
    assert evidence["prediction_collapse"] is None
    assert evidence["rca_complete"] is False


def test_run_dispatches_only_exact_approved_non_stale_targets_with_explicit_limits(monkeypatch) -> None:
    from plexus.cli.optimization import commands

    launched = []
    monkeypatch.setattr(
        commands,
        "_launch_optimizer_procedure",
        lambda arguments: launched.append(arguments) or {"procedure_id": "proc-1", "status": "dispatched"},
    )
    monkeypatch.setattr(
        commands,
        "_refresh_live_target_freshness",
        lambda _request: (
            {"scorecard-1:score-1": "current"},
            {("scorecard-1", "score-1"): {"champion_version": "champion", "feedback_watermark": "watermark"}},
            [],
        ),
    )

    result = CliRunner().invoke(
        commands.optimization,
        [
            "run",
            "--input",
            json.dumps(
                {
                    "approved": True,
                    "targets": [_ready_target("scorecard-1", "score-1")],
                    "current_fingerprints": {"scorecard-1:score-1": "current"},
                    "max_cost_usd": 4.5,
                    "max_samples": 80,
                    "max_iterations": 2,
                    "max_concurrency": 1,
                }
            ),
        ],
    )

    assert result.exit_code == 0, result.output
    assert launched == [
        {
            "scorecard": "scorecard-1",
            "score": "score-1",
            "max_cost_usd": 4.5,
            "max_samples": 80,
            "max_iterations": 2,
            "max_concurrency": 1,
        }
    ]
    body = json.loads(result.output)
    assert body["accepted_targets"][0]["score_id"] == "score-1"
    assert body["dispatches"] == [
        {
            "target": {"scorecard_id": "scorecard-1", "score_id": "score-1"},
            "status": "dispatched",
            "result": {"procedure_id": "proc-1", "status": "dispatched"},
        }
    ]
    assert body["dispatch_coverage"] == {
        "target_count": 1,
        "dispatched_count": 1,
        "failed_count": 0,
        "complete": True,
    }


def test_run_preserves_successful_dispatches_when_one_target_launch_fails(monkeypatch) -> None:
    from plexus.cli.optimization import commands

    monkeypatch.setattr(
        commands,
        "_refresh_live_target_freshness",
        lambda request: (
            {f"card:{target['score_id']}": target["assessment_fingerprint"] for target in request["targets"]},
            {
                ("card", target["score_id"]): {
                    "champion_version": "champion",
                    "feedback_watermark": "watermark",
                }
                for target in request["targets"]
            },
            [],
        ),
    )
    monkeypatch.setattr(
        commands,
        "_launch_optimizer_procedure",
        lambda arguments: (
            (_ for _ in ()).throw(RuntimeError("launch failed"))
            if arguments["score"] == "broken"
            else {"procedure_id": f"procedure-{arguments['score']}"}
        ),
    )
    targets = [_ready_target("card", score_id) for score_id in ("good", "broken")]

    result = commands.dispatch_optimization_operation(
        "run",
        {
            "approved": True,
            "account_id": "account",
            "targets": targets,
            "max_cost_usd": 2.0,
            "max_samples": 40,
            "max_iterations": 2,
            "max_concurrency": 2,
        },
    )

    assert [row["status"] for row in result["dispatches"]] == ["dispatched", "failed"]
    assert result["dispatches"][0]["result"]["procedure_id"] == "procedure-good"
    assert result["dispatch_coverage"] == {
        "target_count": 2,
        "dispatched_count": 1,
        "failed_count": 1,
        "complete": False,
    }


@pytest.mark.parametrize(
    "approved,current_fingerprint,reason",
    [
        (False, "current", "approval_required"),
        (True, "changed", "stale_assessment"),
    ],
)
def test_run_never_launches_rejected_or_stale_targets(
    monkeypatch, approved, current_fingerprint, reason
) -> None:
    from plexus.cli.optimization import commands

    monkeypatch.setattr(
        commands,
        "_launch_optimizer_procedure",
        lambda _arguments: pytest.fail("rejected targets must never launch"),
    )
    monkeypatch.setattr(
        commands,
        "_refresh_live_target_freshness",
        lambda _request: (
            {"scorecard-1:score-1": current_fingerprint},
            {("scorecard-1", "score-1"): {
                "champion_version": (
                    "changed" if current_fingerprint == "changed" else "champion"
                ),
                "feedback_watermark": "watermark",
            }},
            [],
        ),
    )
    payload = {
        "approved": approved,
        "targets": [
            _ready_target("scorecard-1", "score-1")
        ],
        # This caller-provided value is deliberately ignored by the CLI.
        "current_fingerprints": {"scorecard-1:score-1": "caller-controlled"},
        "max_cost_usd": 4.5,
        "max_samples": 80,
        "max_iterations": 2,
        "max_concurrency": 1,
    }

    result = CliRunner().invoke(commands.optimization, ["run", "--input", json.dumps(payload)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["rejected"][0]["reason"] == reason


def test_run_requires_all_explicit_execution_limits_before_any_launch(monkeypatch) -> None:
    from plexus.cli.optimization import commands

    monkeypatch.setattr(
        commands,
        "_launch_optimizer_procedure",
        lambda _arguments: pytest.fail("incomplete run configuration must not launch"),
    )

    result = CliRunner().invoke(
        commands.optimization,
        ["run", "--input", '{"approved": true, "targets": [{"scorecard_id":"sc", "score_id":"s"}]}'],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["rejected"][0]["reason"] == "invalid_run_limits"


def test_run_persists_the_final_dispatch_packet_exactly_once(monkeypatch) -> None:
    from plexus.cli.optimization import commands

    monkeypatch.setattr(
        commands,
        "_launch_optimizer_procedure",
        lambda _arguments: {"procedure_id": "proc-1", "status": "dispatched"},
    )
    monkeypatch.setattr(
        commands,
        "_refresh_live_target_freshness",
        lambda _request: (
            {"sc:s": "current"},
            {("sc", "s"): {"champion_version": "champion", "feedback_watermark": "watermark"}},
            [],
        ),
    )
    persisted = []
    monkeypatch.setattr(
        commands,
        "_persist_returned_packet",
        lambda result, request: persisted.append((result, request)),
    )
    payload = {
        "account_id": "account-1",
        "approved": True,
        "targets": [_ready_target("sc", "s")],
        "max_cost_usd": 4.5,
        "max_samples": 80,
        "max_iterations": 2,
        "max_concurrency": 1,
    }

    result = CliRunner().invoke(
        commands.optimization, ["run", "--input", json.dumps(payload), "--persist"]
    )

    assert result.exit_code == 0, result.output
    assert len(persisted) == 1
    assert persisted[0][0] == json.loads(result.output)


def test_run_rejects_live_champion_or_watermark_change_before_dispatch(monkeypatch) -> None:
    from plexus.cli.optimization import commands

    monkeypatch.setattr(
        commands,
        "_launch_optimizer_procedure",
        lambda _arguments: pytest.fail("stale live evidence must never launch"),
    )
    monkeypatch.setattr(
        commands,
        "_refresh_live_target_freshness",
        lambda _request: (
            {"sc:s": "fresh"},
            {("sc", "s"): {"champion_version": "changed", "feedback_watermark": "watermark"}},
            [],
        ),
    )
    payload = {
        "account_id": "account-1",
        "approved": True,
        "targets": [_ready_target("sc", "s")],
        "max_cost_usd": 1.0, "max_samples": 1, "max_iterations": 1, "max_concurrency": 1,
    }

    result = CliRunner().invoke(commands.optimization, ["run", "--input", json.dumps(payload)])

    assert result.exit_code == 0, result.output
    assert "stale_assessment" in {item["reason"] for item in json.loads(result.output)["rejected"]}


def test_run_rejects_target_when_live_freshness_read_fails(monkeypatch) -> None:
    from plexus.cli.optimization import commands

    monkeypatch.setattr(
        commands,
        "_launch_optimizer_procedure",
        lambda _arguments: pytest.fail("unreadable live evidence must never launch"),
    )
    target = _ready_target("sc", "s")
    monkeypatch.setattr(
        commands,
        "_refresh_live_target_freshness",
        lambda _request: ({}, {}, [{"target": target, "reason": "freshness_check_failed", "error": "offline"}]),
    )

    result = CliRunner().invoke(commands.optimization, ["run", "--input", json.dumps({
        "account_id": "account-1", "approved": True, "targets": [target],
        "max_cost_usd": 1.0, "max_samples": 1, "max_iterations": 1, "max_concurrency": 1,
    })])

    assert result.exit_code == 0, result.output
    assert "freshness_check_failed" in {item["reason"] for item in json.loads(result.output)["rejected"]}


def test_live_feedback_watermark_scans_all_pages_and_uses_latest_update() -> None:
    from plexus.cli.optimization.commands import _read_live_feedback_watermark

    class Client:
        def __init__(self):
            self.tokens = []

        def execute(self, _query, variables):
            self.tokens.append(variables.get("nextToken"))
            if variables.get("nextToken") is None:
                return {
                    "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
                        "items": [{
                            "editedAt": "2026-01-03T00:00:00Z",
                            "updatedAt": "2026-01-04T00:00:00Z",
                        }],
                        "nextToken": "page-2",
                    }
                }
            return {
                "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
                    "items": [{
                        "editedAt": "2026-01-02T00:00:00Z",
                        "updatedAt": "2026-01-05T00:00:00Z",
                    }],
                    "nextToken": None,
                }
            }

    client = Client()
    result = _read_live_feedback_watermark(client, "account", "card", "score")

    assert client.tokens == [None, "page-2"]
    assert result == {"latest_feedback_updated_at": "2026-01-05T00:00:00Z"}
