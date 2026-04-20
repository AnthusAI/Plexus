from unittest.mock import MagicMock, patch

import pytest

from plexus.cli.feedback.report_runner import (
    build_window_config,
    run_feedback_report_block,
)


def test_build_window_config_rejects_mixed_selectors():
    with pytest.raises(ValueError, match="Use either 'days' or 'start_date'\\+'end_date'"):
        build_window_config(days=7, start_date="2026-04-01", end_date="2026-04-07")


def test_build_window_config_rejects_partial_explicit_window():
    with pytest.raises(ValueError, match="Both 'start_date' and 'end_date' are required"):
        build_window_config(start_date="2026-04-01")


def test_build_window_config_supports_days_and_explicit():
    assert build_window_config(days=14) == {"days": 14}
    assert build_window_config(start_date="2026-04-01", end_date="2026-04-30") == {
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
    }


@patch("plexus.cli.feedback.report_runner.run_block_cached")
@patch("plexus.cli.feedback.report_runner.resolve_account_id_for_command")
@patch("plexus.cli.feedback.report_runner.create_client")
def test_run_feedback_report_block_success(mock_create_client, mock_resolve_account, mock_run_block_cached):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_resolve_account.return_value = "acct-1"
    mock_run_block_cached.return_value = ({"summary": {"total_items": 10}}, "log-lines", False)

    result = run_feedback_report_block(
        block_class="CorrectionRate",
        scorecard="sc-1",
        score="score-1",
        days=30,
    )

    assert result["status"] == "success"
    assert result["output"]["summary"]["total_items"] == 10
    assert result["block_config"]["scorecard"] == "sc-1"
    assert result["block_config"]["score"] == "score-1"
    assert result["block_config"]["days"] == 30


@patch("plexus.cli.feedback.report_runner.run_block_cached")
@patch("plexus.cli.feedback.report_runner.resolve_account_id_for_command")
@patch("plexus.cli.feedback.report_runner.create_client")
def test_run_feedback_report_block_dispatched_returns_task_id(
    mock_create_client,
    mock_resolve_account,
    mock_run_block_cached,
):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_resolve_account.return_value = "acct-1"
    mock_run_block_cached.return_value = (
        {"status": "dispatched", "cache_key": "cache-1", "task_id": "task-1"},
        None,
        False,
    )

    result = run_feedback_report_block(
        block_class="AcceptanceRate",
        scorecard="sc-1",
        days=30,
        background=True,
    )

    assert result["status"] == "dispatched"
    assert result["cache_key"] == "cache-1"
    assert result["task_id"] == "task-1"
