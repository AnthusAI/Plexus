from click.testing import CliRunner
from unittest.mock import MagicMock, patch

from plexus.cli.feedback.feedback_report import report
from plexus.reports.service import encode_programmatic_run_payload


def test_acceptance_rate_help_describes_durable_task_background_mode():
    runner = CliRunner()

    result = runner.invoke(report, ["acceptance-rate", "--help"])

    assert result.exit_code == 0
    assert "--background" in result.output
    assert "Queue as a durable task for dispatcher" in result.output
    assert "background thread" not in result.output


@patch("plexus.cli.feedback.feedback_report.run_programmatic_block_and_persist")
@patch("plexus.cli.feedback.feedback_report.create_client")
def test_run_programmatic_block_executes_hidden_dispatcher_entrypoint(
    mock_create_client,
    mock_run_and_persist,
):
    runner = CliRunner()
    mock_create_client.return_value = MagicMock()
    mock_run_and_persist.return_value = ({"summary": {"total_items": 3}}, "log-lines")
    payload = encode_programmatic_run_payload(
        {
            "cache_key": "cache-1",
            "block_class": "AcceptanceRate",
            "block_config": {"scorecard": "sc-1"},
            "account_id": "acct-1",
            "ttl_hours": 24,
            "fresh": False,
        }
    )

    result = runner.invoke(report, ["run-programmatic-block", "--payload-base64", payload])

    assert result.exit_code == 0
    assert '"status": "success"' in result.output
    mock_run_and_persist.assert_called_once()


@patch("plexus.cli.feedback.feedback_report.run_feedback_report_block")
def test_acceptance_rate_passes_parallel_fetch_options(mock_run_feedback_report_block):
    runner = CliRunner()
    mock_run_feedback_report_block.return_value = {"status": "success", "output": {"summary": {}}}

    result = runner.invoke(
        report,
        [
            "acceptance-rate",
            "--scorecard",
            "1438",
            "--days",
            "30",
            "--fetch-shard-days",
            "14",
            "--fetch-shard-concurrency",
            "3",
            "--fetch-max-inflight-process",
            "5",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_report_block.call_args
    assert kwargs["extra_config"]["max_items"] == 0
    assert kwargs["extra_config"]["fetch_shard_days"] == 14
    assert kwargs["extra_config"]["fetch_shard_concurrency"] == 3
    assert kwargs["extra_config"]["fetch_max_inflight_process"] == 5


@patch("plexus.cli.feedback.feedback_report.run_feedback_report_block")
def test_acceptance_rate_timeline_uses_default_parallel_fetch_options(mock_run_feedback_report_block):
    runner = CliRunner()
    mock_run_feedback_report_block.return_value = {"status": "success", "output": {"points": []}}

    result = runner.invoke(
        report,
        [
            "acceptance-rate-timeline",
            "--scorecard",
            "1438",
            "--days",
            "30",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_report_block.call_args
    assert kwargs["extra_config"]["fetch_shard_days"] == 30
    assert kwargs["extra_config"]["fetch_shard_concurrency"] == 4
    assert kwargs["extra_config"]["fetch_max_inflight_process"] == 8


@patch("plexus.cli.feedback.feedback_report.run_feedback_report_block")
def test_feedback_alignment_timeline_show_bucket_details_flag_pass_through(mock_run_feedback_report_block):
    runner = CliRunner()
    mock_run_feedback_report_block.return_value = {"status": "success", "output": {"points": []}}

    result = runner.invoke(
        report,
        [
            "timeline",
            "--scorecard",
            "1438",
            "--days",
            "30",
            "--show-bucket-details",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_report_block.call_args
    assert kwargs["extra_config"]["show_bucket_details"] is True


@patch("plexus.cli.feedback.feedback_report.run_feedback_report_block")
def test_acceptance_rate_timeline_show_bucket_details_flag_pass_through(mock_run_feedback_report_block):
    runner = CliRunner()
    mock_run_feedback_report_block.return_value = {"status": "success", "output": {"points": []}}

    result = runner.invoke(
        report,
        [
            "acceptance-rate-timeline",
            "--scorecard",
            "1438",
            "--days",
            "30",
            "--show-bucket-details",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_report_block.call_args
    assert kwargs["extra_config"]["show_bucket_details"] is True


@patch("plexus.cli.feedback.feedback_report.resolve_account_id_for_command")
@patch("plexus.cli.feedback.feedback_report.run_programmatic_report_and_persist")
@patch("plexus.cli.feedback.feedback_report.create_client")
def test_overview_builds_three_blocks_in_required_order_with_shared_window(
    mock_create_client,
    mock_run_programmatic_report_and_persist,
    mock_resolve_account_id_for_command,
):
    runner = CliRunner()
    mock_client = MagicMock()
    mock_client.generate_deep_link.return_value = "https://app.plexus.ai/lab/reports/report-123"
    mock_create_client.return_value = mock_client
    mock_resolve_account_id_for_command.return_value = "acct-1"
    mock_run_programmatic_report_and_persist.return_value = ("report-123", None)

    result = runner.invoke(
        report,
        [
            "overview",
            "--scorecard",
            "1438",
            "--score",
            "45813",
            "--days",
            "90",
            "--show-bucket-details",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_programmatic_report_and_persist.call_args
    block_definitions = kwargs["block_definitions"]
    assert [block["class_name"] for block in block_definitions] == [
        "FeedbackAlignmentTimeline",
        "AcceptanceRate",
        "FeedbackContradictions",
    ]

    for block in block_definitions:
        assert block["config"]["scorecard"] == "1438"
        assert block["config"]["score"] == "45813"
        assert block["config"]["days"] == 90

    assert block_definitions[0]["config"]["show_bucket_details"] is True
    assert block_definitions[1]["config"]["include_item_acceptance_rate"] is True
