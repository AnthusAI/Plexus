from __future__ import annotations

from unittest.mock import Mock

import pytest

from plexus.cli.shared.feedback_evaluation_runner import (
    FeedbackRunnerRequest,
    build_feedback_command,
    build_feedback_run_summary,
    ensure_feedback_runner_task,
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
        max_items=50,
        sampling_mode="random",
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
    assert "--max-items 50" in command_string
    assert "--sampling-mode random" in command_string
    assert "--sample-seed 42" in command_string
    assert "--max-category-summary-items 10" in command_string
    assert "--yaml" in command_string


def test_build_feedback_command_omits_days_when_not_provided():
    request = FeedbackRunnerRequest(
        scorecard="1039",
        score="45425",
        days=None,
        max_items=200,
        sampling_mode="newest",
    )
    cmd = build_feedback_command(
        plexus_bin="plexus",
        request=request,
        resolved_task_id="runner-task-9",
    )
    command_string = " ".join(cmd)
    assert "--days" not in command_string
    assert "--max-items 200" in command_string
    assert "--sampling-mode newest" in command_string


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
        max_items=100,
        sampling_mode="newest",
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
    assert summary["selection_shortfall_count"] == 50
    assert summary["warnings"]


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
            "max_items": 100,
            "sampling_mode": "newest",
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


def test_build_feedback_command_seed_only_with_random_mode():
    request = FeedbackRunnerRequest(
        scorecard="1039",
        score="45425",
        days=30,
        max_items=100,
        sampling_mode="newest",
        sample_seed=5,
    )
    # Validation happens in run_feedback_evaluation_orchestrated; command builder itself is a pure formatter.
    cmd = build_feedback_command(
        plexus_bin="plexus",
        request=request,
        resolved_task_id="runner-task-11",
    )
    assert "--sample-seed" in " ".join(cmd)


def test_ensure_feedback_runner_task_validates_explicit_task_id(monkeypatch):
    mock_client = Mock()
    fetched = Mock()
    fetched.id = "existing-task-1"
    monkeypatch.setattr(
        "plexus.cli.shared.feedback_evaluation_runner.Task.get_by_id",
        lambda task_id, client: fetched,
    )

    task_id = ensure_feedback_runner_task(
        client=mock_client,
        account_id="acct-1",
        scorecard="1039",
        score="45425",
        version=None,
        task_id="existing-task-1",
    )
    assert task_id == "existing-task-1"


def test_ensure_feedback_runner_task_creates_task_with_stages(monkeypatch):
    mock_client = Mock()
    created_task = Mock()
    created_task.id = "created-task-1"
    created_task.create_stage = Mock()

    monkeypatch.setattr(
        "plexus.cli.shared.feedback_evaluation_runner.Task.create",
        lambda **kwargs: created_task,
    )

    task_id = ensure_feedback_runner_task(
        client=mock_client,
        account_id="acct-1",
        scorecard="1039",
        score="45425",
        version="ver-1",
        task_id=None,
    )
    assert task_id == "created-task-1"
    assert created_task.create_stage.call_count == 3
