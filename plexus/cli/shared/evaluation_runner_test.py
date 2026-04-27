from __future__ import annotations

from types import SimpleNamespace


def test_create_tracker_and_evaluation_includes_procedure_id_in_task_metadata(monkeypatch):
    captured = {}

    class DummyTask:
        id = "task-123"
        accountId = "acct-1"
        type = "Accuracy Evaluation"
        status = "PENDING"
        target = "evaluation/accuracy/Test Scorecard"
        command = "evaluate accuracy --scorecard Test Scorecard"

        def update(self, **kwargs):
            captured["task_update"] = kwargs

    class DummyTracker:
        def __init__(self, **kwargs):
            captured["tracker_kwargs"] = kwargs
            self.task = DummyTask()

    dummy_evaluation = SimpleNamespace(id="eval-123")

    monkeypatch.setattr(
        "plexus.cli.shared.evaluation_runner.TaskProgressTracker",
        DummyTracker,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.evaluation_runner.DashboardEvaluation.create",
        lambda client, **kwargs: dummy_evaluation,
    )

    from plexus.cli.shared.evaluation_runner import create_tracker_and_evaluation

    tracker, evaluation = create_tracker_and_evaluation(
        client=SimpleNamespace(),
        account_id="acct-1",
        scorecard_name="Test Scorecard",
        score_name="Test Score",
        number_of_samples=25,
        sampling_method="random",
        procedure_id="procedure-999",
    )

    assert tracker.task.id == "task-123"
    assert evaluation.id == "eval-123"
    assert captured["tracker_kwargs"]["metadata"]["procedure_id"] == "procedure-999"
    assert captured["tracker_kwargs"]["metadata"]["score"] == "Test Score"
