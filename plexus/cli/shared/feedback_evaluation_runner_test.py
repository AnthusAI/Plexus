from __future__ import annotations

from unittest.mock import Mock

import pytest

from plexus.cli.shared.feedback_evaluation_runner import (
    FeedbackRunnerRequest,
    build_feedback_command,
    build_feedback_run_summary,
    find_feedback_evaluation_id_by_task_id,
    format_feedback_run_kanbus_comment,
    wait_for_feedback_evaluation_terminal_status,
)


def test_build_feedback_command_includes_required_runner_fields():
    request = FeedbackRunnerRequest(
        scorecard="1039",
        score="45425",
        days=60,
        version="ver-1",
        baseline="eval-0",
        max_samples=50,
        sample_seed=42,
        max_category_summary_items=10,
        use_yaml=True,
    )
    cmd = build_feedback_command(
        plexus_bin="plexus",
        request=request,
        resolved_task_id="runner-task-1",
    )
    command_string = " ".join(cmd)
    assert "--task-id runner-task-1" in command_string
    assert "--version ver-1" in command_string
    assert "--baseline eval-0" in command_string
    assert "--max-samples 50" in command_string
    assert "--sample-seed 42" in command_string
    assert "--max-category-summary-items 10" in command_string
    assert "--yaml" in command_string


def test_find_feedback_evaluation_id_by_task_id_filters_by_type_and_task():
    client = Mock()
    client.execute.return_value = {
        "listEvaluationByAccountIdAndUpdatedAt": {
            "items": [
                {"id": "eval-non-feedback", "taskId": "runner-task-1", "type": "accuracy"},
                {"id": "eval-target", "taskId": "runner-task-1", "type": "feedback"},
            ],
            "nextToken": None,
        }
    }
    evaluation_id = find_feedback_evaluation_id_by_task_id(
        client=client,
        account_id="acct-1",
        task_id="runner-task-1",
    )
    assert evaluation_id == "eval-target"


def test_build_summary_extracts_metrics_and_root_cause_fields():
    request = FeedbackRunnerRequest(
        scorecard="sc",
        score="score",
        days=180,
        max_samples=100,
        sample_seed=7,
    )
    evaluation_info = {
        "status": "COMPLETED",
        "scorecard_name": "My Scorecard",
        "score_name": "My Score",
        "score_version_id": "ver-123",
        "baseline_evaluation_id": "eval-base",
        "processed_items": 50,
        "total_items": 50,
        "metrics": [
            {"name": "Alignment", "value": 0.73},
            {"name": "Accuracy", "value": 91.0},
            {"name": "Precision", "value": 89.0},
            {"name": "Recall", "value": 95.0},
        ],
        "root_cause": {"topics": [{"label": "A"}, {"label": "B"}]},
        "misclassification_analysis": {
            "primary_next_action": {"action": "score_configuration_optimization"},
            "optimization_applicability": "applicable",
        },
    }
    summary = build_feedback_run_summary(
        request=request,
        evaluation_id="eval-123",
        evaluation_info=evaluation_info,
        resolved_task_id="runner-task-2",
    )
    assert summary["metrics"]["ac1"] == 0.73
    assert summary["metrics"]["accuracy"] == 91.0
    assert summary["root_cause"]["present"] is True
    assert summary["root_cause"]["topic_count"] == 2
    assert summary["root_cause"]["primary_next_action"] == "score_configuration_optimization"


def test_format_feedback_run_kanbus_comment_contains_core_identifiers():
    comment = format_feedback_run_kanbus_comment(
        {
            "evaluation_id": "eval-123",
            "status": "COMPLETED",
            "scorecard": "sc",
            "score": "score",
            "score_version_id": "ver-1",
            "task_id": "runner-task-1",
            "window_days": 180,
            "max_samples": 100,
            "sample_seed": 11,
            "processed_items": 100,
            "total_items": 100,
            "metrics": {"ac1": 0.7, "accuracy": 90.0, "precision": 89.0, "recall": 91.0},
            "root_cause": {
                "present": True,
                "topic_count": 5,
                "primary_next_action": "score_configuration_optimization",
                "optimization_applicability": "applicable",
            },
            "dashboard_url": "https://app.plexusanalytics.com/evaluations/eval-123",
        }
    )
    assert "Feedback Evaluation Runner Result" in comment
    assert "`evaluation_id`: `eval-123`" in comment
    assert "`task_id`: `runner-task-1`" in comment
    assert "Dashboard: https://app.plexusanalytics.com/evaluations/eval-123" in comment


def test_wait_for_feedback_evaluation_terminal_status_returns_completed(monkeypatch):
    responses = [
        {"status": "RUNNING"},
        {"status": "COMPLETED", "id": "eval-9"},
    ]

    def fake_get_info(_evaluation_id):
        return responses.pop(0)

    monkeypatch.setattr(
        "plexus.cli.shared.feedback_evaluation_runner.Evaluation.get_evaluation_info",
        fake_get_info,
    )
    monkeypatch.setattr("plexus.cli.shared.feedback_evaluation_runner.time.sleep", lambda _s: None)
    info = wait_for_feedback_evaluation_terminal_status(
        evaluation_id="eval-9",
        timeout_seconds=2,
        poll_interval_seconds=0,
    )
    assert info["status"] == "COMPLETED"


def test_wait_for_feedback_evaluation_terminal_status_times_out(monkeypatch):
    monkeypatch.setattr(
        "plexus.cli.shared.feedback_evaluation_runner.Evaluation.get_evaluation_info",
        lambda _evaluation_id: {"status": "RUNNING"},
    )
    monkeypatch.setattr("plexus.cli.shared.feedback_evaluation_runner.time.sleep", lambda _s: None)
    with pytest.raises(TimeoutError, match="Timed out waiting for evaluation"):
        wait_for_feedback_evaluation_terminal_status(
            evaluation_id="eval-10",
            timeout_seconds=0,
            poll_interval_seconds=0,
        )

