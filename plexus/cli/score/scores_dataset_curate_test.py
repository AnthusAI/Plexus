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
    ) as mock_build:
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
    assert mock_build.call_args.kwargs["balance"] is True
    assert mock_build.call_args.kwargs["class_source_score_version_id"] is None


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
                "--source-report-block-id",
                "block-123",
                "--eligibility-rule",
                "unanimous non-contradiction",
            ],
        )

    assert result.exit_code == 0
    assert '"dataset_id": "dataset-2"' in result.output
    mock_build.assert_called_once()
    kwargs = mock_build.call_args.kwargs
    assert kwargs["feedback_item_ids"] == ["fi-2", "fi-1"]
    assert kwargs["source_report_block_id"] == "block-123"
    assert kwargs["eligibility_rule"] == "unanimous non-contradiction"


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


def test_score_dataset_curate_rejects_provenance_options_without_feedback_ids():
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
                "--source-report-block-id",
                "block-123",
            ],
        )

    assert result.exit_code != 0
    assert "--source-report-block-id and --eligibility-rule require --feedback-item-ids." in result.output


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


def test_score_dataset_curate_no_balance_flag_passes_false():
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
    ) as mock_build:
        result = runner.invoke(
            score,
            [
                "dataset-curate",
                "--scorecard",
                "1039",
                "--score",
                "45425",
                "--no-balance",
            ],
        )

    assert result.exit_code == 0
    assert mock_build.call_args.kwargs["balance"] is False


def test_score_dataset_curate_passes_explicit_score_version_for_class_source():
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
    ) as mock_build:
        result = runner.invoke(
            score,
            [
                "dataset-curate",
                "--scorecard",
                "1039",
                "--score",
                "45425",
                "--score-version-id",
                "sv-abc",
            ],
        )

    assert result.exit_code == 0
    assert mock_build.call_args.kwargs["class_source_score_version_id"] == "sv-abc"


def test_score_dataset_curate_rejects_score_version_with_explicit_feedback_ids():
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
                "--score-version-id",
                "sv-abc",
            ],
        )

    assert result.exit_code != 0
    assert "--score-version-id cannot be combined with --feedback-item-ids." in result.output


def test_score_dataset_curate_vetted_success():
    runner = CliRunner()
    with patch("plexus.cli.score.scores.create_client", return_value=MagicMock()), patch(
        "plexus.cli.score.scores.memoized_resolve_scorecard_identifier",
        return_value="scorecard-1",
    ), patch(
        "plexus.cli.score.scores.memoized_resolve_score_identifier",
        return_value="score-1",
    ), patch(
        "plexus.cli.score.scores.build_associated_dataset_from_vetted_report",
        return_value={
            "report_id": "report-1",
            "report_block_id": "block-1",
            "dataset_id": "dataset-1",
            "requested_max_items": 100,
            "vetted_eligible_count": 88,
            "selected_vetted_count": 88,
            "rows_written": 88,
            "score_id": "score-1",
            "scorecard_id": "scorecard-1",
        },
    ) as mock_build:
        result = runner.invoke(
            score,
            [
                "dataset-curate-vetted",
                "--scorecard",
                "1039",
                "--score",
                "45425",
            ],
        )

    assert result.exit_code == 0
    assert '"dataset_id": "dataset-1"' in result.output
    kwargs = mock_build.call_args.kwargs
    assert kwargs["max_items"] == 100
    assert kwargs["days"] == 180
    assert kwargs["class_source_score_version_id"] is None


def test_score_dataset_curate_vetted_rejects_non_positive_days():
    runner = CliRunner()
    with patch("plexus.cli.score.scores.create_client", return_value=MagicMock()):
        result = runner.invoke(
            score,
            [
                "dataset-curate-vetted",
                "--scorecard",
                "1039",
                "--score",
                "45425",
                "--days",
                "0",
            ],
        )
    assert result.exit_code != 0
    assert "--days must be greater than 0." in result.output
