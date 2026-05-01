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


@patch("plexus.cli.feedback.feedback_report.run_programmatic_block_and_persist")
@patch("plexus.cli.feedback.feedback_report.create_client")
def test_run_programmatic_block_rejects_invalid_child_budget(
    mock_create_client,
    mock_run_and_persist,
):
    runner = CliRunner()
    mock_create_client.return_value = MagicMock()
    payload = encode_programmatic_run_payload(
        {
            "cache_key": "cache-1",
            "block_class": "AcceptanceRate",
            "block_config": {"scorecard": "sc-1"},
            "account_id": "acct-1",
            "ttl_hours": 24,
            "fresh": False,
            "child_budget": {"usd": 0.1, "depth": 1, "tool_calls": 2},
        }
    )

    result = runner.invoke(report, ["run-programmatic-block", "--payload-base64", payload])

    assert result.exit_code != 0
    assert "wallclock_seconds" in result.output
    mock_run_and_persist.assert_not_called()


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
def test_contradictions_passes_include_rubric_memory_flag(mock_run_feedback_report_block):
    runner = CliRunner()
    mock_run_feedback_report_block.return_value = {
        "status": "success",
        "output": {"contradictions_found": 0},
    }

    result = runner.invoke(
        report,
        [
            "contradictions",
            "--scorecard",
            "1438",
            "--score",
            "48059",
            "--days",
            "30",
            "--include-rubric-memory",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_report_block.call_args
    assert kwargs["extra_config"]["include_rubric_memory"] is True


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


@patch("plexus.cli.feedback.feedback_report.run_feedback_report_block")
def test_feedback_volume_uses_dedicated_block_and_show_bucket_details(mock_run_feedback_report_block):
    runner = CliRunner()
    mock_run_feedback_report_block.return_value = {"status": "success", "output": {"points": []}}

    result = runner.invoke(
        report,
        [
            "volume",
            "--scorecard",
            "1438",
            "--days",
            "30",
            "--show-bucket-details",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_report_block.call_args
    assert kwargs["block_class"] == "FeedbackVolumeTimeline"
    assert kwargs["extra_config"]["show_bucket_details"] is True


@patch("plexus.cli.feedback.feedback_report.resolve_account_id_for_command")
@patch("plexus.cli.feedback.feedback_report.enrich_parameters_with_names")
@patch("plexus.cli.feedback.feedback_report.memoized_resolve_score_identifier")
@patch("plexus.cli.feedback.feedback_report.memoized_resolve_scorecard_identifier")
@patch("plexus.cli.feedback.feedback_report._score_has_nonempty_champion_guidelines")
@patch("plexus.cli.feedback.feedback_report.run_programmatic_report_and_persist")
@patch("plexus.cli.feedback.feedback_report.create_client")
def test_overview_builds_three_blocks_in_required_order_with_shared_window(
    mock_create_client,
    mock_run_programmatic_report_and_persist,
    mock_score_has_nonempty_champion_guidelines,
    mock_memoized_resolve_scorecard_identifier,
    mock_memoized_resolve_score_identifier,
    mock_enrich_parameters_with_names,
    mock_resolve_account_id_for_command,
):
    runner = CliRunner()
    mock_client = MagicMock()
    mock_client.generate_deep_link.return_value = "https://app.plexus.ai/lab/reports/report-123"
    mock_create_client.return_value = mock_client
    mock_resolve_account_id_for_command.return_value = "acct-1"
    mock_memoized_resolve_scorecard_identifier.return_value = "1438"
    mock_memoized_resolve_score_identifier.return_value = "45813"
    mock_score_has_nonempty_champion_guidelines.return_value = (True, None)
    mock_enrich_parameters_with_names.return_value = {
        "scorecard": "1438",
        "score": "45813",
        "days": 90,
        "scorecard_name": "SelectQuote HCS Medium-Risk",
        "score_name": "Agent Misrepresentation",
    }
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
        "FeedbackVolumeTimeline",
        "FeedbackAlignment",
        "FeedbackContradictions",
    ]

    for block in block_definitions:
        assert block["config"]["scorecard"] == "1438"
        assert block["config"]["score"] == "45813"
        assert block["config"]["days"] == 90

    assert block_definitions[0]["config"]["show_bucket_details"] is True
    assert block_definitions[0]["config"]["bucket_type"] == "trailing_7d"
    assert "show_bucket_details" not in block_definitions[1]["config"]
    assert kwargs["display_title"] == "SelectQuote HCS Medium-Risk - Agent Misrepresentation - Feedback Overview"
    assert "Includes contradiction analysis." in kwargs["display_description"]
    assert "SelectQuote HCS Medium-Risk - Agent Misrepresentation - Feedback Overview" in kwargs["report_name"]


@patch("plexus.cli.feedback.feedback_report.resolve_account_id_for_command")
@patch("plexus.cli.feedback.feedback_report.enrich_parameters_with_names")
@patch("plexus.cli.feedback.feedback_report.memoized_resolve_score_identifier")
@patch("plexus.cli.feedback.feedback_report.memoized_resolve_scorecard_identifier")
@patch("plexus.cli.feedback.feedback_report._score_has_nonempty_champion_guidelines")
@patch("plexus.cli.feedback.feedback_report.run_programmatic_report_and_persist")
@patch("plexus.cli.feedback.feedback_report.create_client")
def test_overview_skips_contradictions_when_champion_guidelines_missing(
    mock_create_client,
    mock_run_programmatic_report_and_persist,
    mock_score_has_nonempty_champion_guidelines,
    mock_memoized_resolve_scorecard_identifier,
    mock_memoized_resolve_score_identifier,
    mock_enrich_parameters_with_names,
    mock_resolve_account_id_for_command,
):
    runner = CliRunner()
    mock_client = MagicMock()
    mock_client.generate_deep_link.return_value = "https://app.plexus.ai/lab/reports/report-123"
    mock_create_client.return_value = mock_client
    mock_resolve_account_id_for_command.return_value = "acct-1"
    mock_memoized_resolve_scorecard_identifier.return_value = "1438"
    mock_memoized_resolve_score_identifier.return_value = "45813"
    mock_enrich_parameters_with_names.return_value = {
        "scorecard": "1438",
        "score": "45813",
        "days": 90,
        "scorecard_name": "SelectQuote HCS Medium-Risk",
        "score_name": "Agent Misrepresentation",
    }
    mock_score_has_nonempty_champion_guidelines.return_value = (
        False,
        "Skipped Feedback Contradictions: champion version guidelines are empty.",
    )
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
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_programmatic_report_and_persist.call_args
    block_definitions = kwargs["block_definitions"]
    assert [block["class_name"] for block in block_definitions] == [
        "FeedbackVolumeTimeline",
        "FeedbackAlignment",
    ]
    assert "skipped because champion guidelines are missing" in kwargs["display_description"]


@patch("plexus.cli.feedback.feedback_report.resolve_account_id_for_command")
@patch("plexus.cli.feedback.feedback_report.enrich_parameters_with_names")
@patch("plexus.cli.feedback.feedback_report.memoized_resolve_score_identifier")
@patch("plexus.cli.feedback.feedback_report.memoized_resolve_scorecard_identifier")
@patch("plexus.cli.feedback.feedback_report._score_has_nonempty_champion_guidelines")
@patch("plexus.cli.feedback.feedback_report.run_programmatic_report_and_persist")
@patch("plexus.cli.feedback.feedback_report.create_client")
def test_overview_uses_canonical_resolved_ids_in_block_configs(
    mock_create_client,
    mock_run_programmatic_report_and_persist,
    mock_score_has_nonempty_champion_guidelines,
    mock_memoized_resolve_scorecard_identifier,
    mock_memoized_resolve_score_identifier,
    mock_enrich_parameters_with_names,
    mock_resolve_account_id_for_command,
):
    runner = CliRunner()
    mock_client = MagicMock()
    mock_client.generate_deep_link.return_value = "https://app.plexus.ai/lab/reports/report-123"
    mock_create_client.return_value = mock_client
    mock_resolve_account_id_for_command.return_value = "acct-1"
    mock_memoized_resolve_scorecard_identifier.return_value = "sc-canonical"
    mock_memoized_resolve_score_identifier.return_value = "score-canonical"
    mock_score_has_nonempty_champion_guidelines.return_value = (True, None)
    mock_enrich_parameters_with_names.return_value = {
        "scorecard": "sc-canonical",
        "score": "score-canonical",
        "days": 30,
        "scorecard_name": "SelectQuote HCS Medium-Risk",
        "score_name": "Agent Misrepresentation",
    }
    mock_run_programmatic_report_and_persist.return_value = ("report-123", None)

    result = runner.invoke(
        report,
        [
            "overview",
            "--scorecard",
            "SelectQuote HCS Medium-Risk",
            "--score",
            "Agent Misrepresentation",
            "--days",
            "30",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_programmatic_report_and_persist.call_args
    block_definitions = kwargs["block_definitions"]
    for block in block_definitions:
        assert block["config"]["scorecard"] == "sc-canonical"
        assert block["config"]["score"] == "score-canonical"
