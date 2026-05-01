from plexus.cli.evaluation.evaluations import _build_evaluation_task_metadata


def test_build_evaluation_task_metadata_includes_procedure_id_when_present() -> None:
    metadata = _build_evaluation_task_metadata(
        task_type="Feedback Accuracy Evaluation",
        scorecard="Test Scorecard",
        score="Test Score",
        procedure_id="proc-123",
    )

    assert metadata["type"] == "Feedback Accuracy Evaluation"
    assert metadata["scorecard"] == "Test Scorecard"
    assert metadata["score"] == "Test Score"
    assert metadata["procedure_id"] == "proc-123"


def test_build_evaluation_task_metadata_omits_procedure_id_when_absent() -> None:
    metadata = _build_evaluation_task_metadata(
        task_type="Accuracy Evaluation",
        scorecard="Test Scorecard",
    )

    assert metadata["type"] == "Accuracy Evaluation"
    assert metadata["scorecard"] == "Test Scorecard"
    assert "score" not in metadata
    assert "procedure_id" not in metadata
