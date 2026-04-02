from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from plexus.cli.score.scores import score


def test_score_dataset_curate_success():
    runner = CliRunner()
    with patch("plexus.cli.score.scores.create_client", return_value=MagicMock()), patch(
        "plexus.cli.score.scores.memoized_resolve_scorecard_identifier",
        return_value="scorecard-1",
    ), patch(
        "plexus.cli.score.scores.memoized_resolve_score_identifier",
        return_value="score-1",
    ), patch(
        "plexus.cli.score.scores.build_associated_dataset_from_feedback_window",
        return_value={
            "dataset_id": "dataset-1",
            "requested_max_items": 100,
            "qualifying_found": 42,
            "rows_written": 42,
            "score_id": "score-1",
            "scorecard_id": "scorecard-1",
            "s3_key": "datasets/account-1/dataset-1/dataset.parquet",
        },
    ):
        result = runner.invoke(
            score,
            [
                "dataset-curate",
                "--scorecard",
                "1039",
                "--score",
                "45425",
            ],
        )

    assert result.exit_code == 0
    assert '"dataset_id": "dataset-1"' in result.output


def test_score_dataset_curate_explicit_feedback_ids_path():
    runner = CliRunner()
    with patch("plexus.cli.score.scores.create_client", return_value=MagicMock()), patch(
        "plexus.cli.score.scores.build_associated_dataset_from_feedback_ids",
        return_value={
            "dataset_id": "dataset-2",
            "row_count": 2,
            "feedback_item_count": 2,
            "score_id": "score-1",
            "scorecard_id": "scorecard-1",
            "s3_key": "datasets/account-1/dataset-2/dataset.parquet",
        },
    ) as mock_build:
        result = runner.invoke(
            score,
            [
                "dataset-curate",
                "--scorecard",
                "1039",
                "--score",
                "45425",
                "--feedback-item-ids",
                "fi-2,fi-1",
            ],
        )

    assert result.exit_code == 0
    assert '"dataset_id": "dataset-2"' in result.output
    mock_build.assert_called_once()
    kwargs = mock_build.call_args.kwargs
    assert kwargs["feedback_item_ids"] == ["fi-2", "fi-1"]
    assert kwargs["eligibility_rule"] == "explicit vetted feedback labels"


def test_score_dataset_curate_rejects_days_with_explicit_feedback_ids():
    runner = CliRunner()
    with patch("plexus.cli.score.scores.create_client", return_value=MagicMock()):
        result = runner.invoke(
            score,
            [
                "dataset-curate",
                "--scorecard",
                "1039",
                "--score",
                "45425",
                "--feedback-item-ids",
                "fi-1",
                "--days",
                "30",
            ],
        )

    assert result.exit_code != 0
    assert "--days cannot be combined with --feedback-item-ids." in result.output


def test_score_dataset_curate_invalid_max_items():
    runner = CliRunner()
    with patch("plexus.cli.score.scores.create_client", return_value=MagicMock()):
        result = runner.invoke(
            score,
            [
                "dataset-curate",
                "--scorecard",
                "1039",
                "--score",
                "45425",
                "--max-items",
                "0",
            ],
        )
    assert result.exit_code != 0
    assert "--max-items must be greater than 0." in result.output
