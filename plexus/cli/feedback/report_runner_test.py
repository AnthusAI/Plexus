from unittest.mock import MagicMock, patch

import pytest

from plexus.cli.feedback.report_runner import (
    build_window_config,
    run_feedback_report_block,
    summarize_timeline_feedback_volume,
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
        block_class="OverturnRate",
        scorecard="sc-1",
        score="score-1",
        days=30,
    )

    assert result["status"] == "success"
    assert result["output"]["summary"]["total_items"] == 10
    assert result["block_config"]["scorecard"] == "sc-1"
    assert result["block_config"]["score"] == "score-1"
    assert result["block_config"]["days"] == 30


def test_summarize_timeline_feedback_volume():
    timeline_output = {
        "scorecard_id": "sc-1",
        "scorecard_name": "Scorecard",
        "mode": "all_scores",
        "date_range": {"start": "2026-04-01T00:00:00+00:00", "end": "2026-04-30T23:59:59+00:00"},
        "bucket_policy": {"bucket_type": "calendar_week", "bucket_count": 4},
        "overall": {
            "points": [
                {"bucket_index": 0, "label": "W1", "start": "a", "end": "b", "item_count": 3, "agreements": 2, "mismatches": 1},
                {"bucket_index": 1, "label": "W2", "start": "c", "end": "d", "item_count": 0, "agreements": 0, "mismatches": 0},
            ]
        },
    }

    summary = summarize_timeline_feedback_volume(timeline_output)
    assert summary["report_type"] == "feedback_volume"
    assert summary["summary"]["total_feedback_items"] == 3
    assert summary["summary"]["bucket_count"] == 2
    assert summary["summary"]["buckets_with_feedback"] == 1
