from click.testing import CliRunner
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from plexus.cli.feedback.feedback_report import report
from plexus.cli.feedback.report_runner import build_feedback_alignment_timeline_report_blocks
from plexus.reports.service import encode_programmatic_run_payload


def test_acceptance_rate_help_describes_durable_task_background_mode():
    runner = CliRunner()

    result = runner.invoke(report, ["acceptance-rate", "--help"])

    assert result.exit_code == 0
    assert "--background" in result.output
    assert "Queue as a durable task for dispatcher" in result.output
    assert "background thread" not in result.output


def test_build_feedback_alignment_timeline_report_blocks_splits_score_series():
    output = {
        "mode": "all_scores",
        "scorecard_name": "Example Scorecard",
        "show_bucket_details": True,
        "bucket_policy": {"bucket_type": "calendar_month"},
        "sample_policy": {"rolling_min_items": 100},
        "overall": {"score_id": "overall", "score_name": "Overall", "points": [{"bucket_index": 0}]},
        "scores": [
            {"score_id": "score-1", "score_name": "First Score", "points": [{"bucket_index": 0}]},
            {"score_id": "score-2", "score_name": "Second Score", "points": [{"bucket_index": 0}]},
        ],
    }

    blocks = build_feedback_alignment_timeline_report_blocks(
        output_data=output,
        block_config={"scorecard": "sc-1", "show_bucket_details": True},
        log_output="generated",
    )

    assert [block["block_name"] for block in blocks] == [
        "Overall Alignment Timeline",
        "First Score Alignment Timeline",
        "Second Score Alignment Timeline",
    ]
    assert [block["output"]["overall"]["score_id"] for block in blocks] == [
        "overall",
        "score-1",
        "score-2",
    ]
    assert all(block["config"]["show_bucket_details"] is False for block in blocks)
    assert all(block["output"]["show_bucket_details"] is False for block in blocks)
    assert all(block["output"]["scores"] == [] for block in blocks)
    assert all("message" not in block["output"] for block in blocks)
    assert blocks[0]["output"]["show_methodology"] is True
    assert [block["output"]["show_methodology"] for block in blocks[1:]] == [False, False]


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


@patch("plexus.cli.feedback.feedback_report.run_feedback_alignment_timeline_report")
def test_feedback_alignment_timeline_show_bucket_details_flag_pass_through(mock_run_feedback_alignment_timeline_report):
    runner = CliRunner()
    mock_run_feedback_alignment_timeline_report.return_value = {"status": "success", "output": {"points": []}}

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
    _, kwargs = mock_run_feedback_alignment_timeline_report.call_args
    assert kwargs["extra_config"]["show_bucket_details"] is True
    assert kwargs["extra_config"]["rolling_min_items"] == 100
    assert kwargs["split_score_timelines"] is True


@patch("plexus.cli.feedback.feedback_report.run_feedback_alignment_timeline_report")
def test_feedback_alignment_timeline_rolling_min_items_pass_through(mock_run_feedback_alignment_timeline_report):
    runner = CliRunner()
    mock_run_feedback_alignment_timeline_report.return_value = {"status": "success", "output": {"points": []}}

    result = runner.invoke(
        report,
        [
            "timeline",
            "--scorecard",
            "1438",
            "--days",
            "30",
            "--rolling-min-items",
            "25",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_alignment_timeline_report.call_args
    assert kwargs["extra_config"]["rolling_min_items"] == 25


@patch("plexus.cli.feedback.feedback_report.run_feedback_alignment_timeline_report")
def test_feedback_alignment_timeline_score_filter_flags_pass_through(mock_run_feedback_alignment_timeline_report):
    runner = CliRunner()
    mock_run_feedback_alignment_timeline_report.return_value = {"status": "success", "output": {"points": []}}

    result = runner.invoke(
        report,
        [
            "timeline",
            "--scorecard",
            "1438",
            "--days",
            "30",
            "--include-score",
            "Score 1",
            "--include-score",
            "Score 2",
            "--exclude-score",
            "Score 3",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_alignment_timeline_report.call_args
    assert kwargs["extra_config"]["include_scores"] == ["Score 1", "Score 2"]
    assert kwargs["extra_config"]["exclude_scores"] == ["Score 3"]


@patch("plexus.cli.feedback.feedback_report.run_feedback_alignment_timeline_report")
def test_feedback_alignment_timeline_single_block_flag_pass_through(mock_run_feedback_alignment_timeline_report):
    runner = CliRunner()
    mock_run_feedback_alignment_timeline_report.return_value = {"status": "success", "output": {"points": []}}

    result = runner.invoke(
        report,
        [
            "timeline",
            "--scorecard",
            "1438",
            "--days",
            "30",
            "--single-block",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_alignment_timeline_report.call_args
    assert kwargs["split_score_timelines"] is False


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


@patch("plexus.cli.feedback.feedback_report.run_feedback_report_block")
def test_score_champion_version_timeline_uses_dedicated_block(mock_run_feedback_report_block):
    runner = CliRunner()
    mock_run_feedback_report_block.return_value = {"status": "success", "output": {"scores": []}}

    result = runner.invoke(
        report,
        [
            "score-champion-version-timeline",
            "--scorecard",
            "1438",
            "--days",
            "21",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_report_block.call_args
    assert kwargs["block_class"] == "ScoreChampionVersionTimeline"
    assert kwargs["scorecard"] == "1438"
    assert kwargs["score"] is None
    assert kwargs["days"] == 21
    assert kwargs["extra_config"] == {"include_unchanged": False}


@patch("plexus.cli.feedback.feedback_report.run_feedback_report_block")
def test_score_champion_version_timeline_supports_single_score_explicit_window(mock_run_feedback_report_block):
    runner = CliRunner()
    mock_run_feedback_report_block.return_value = {"status": "success", "output": {"scores": []}}

    result = runner.invoke(
        report,
        [
            "score-champion-version-timeline",
            "--scorecard",
            "1438",
            "--score",
            "48059",
            "--start-date",
            "2026-04-01",
            "--end-date",
            "2026-05-01",
            "--include-unchanged",
            "--fresh",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_report_block.call_args
    assert kwargs["block_class"] == "ScoreChampionVersionTimeline"
    assert kwargs["score"] == "48059"
    assert kwargs["start_date"] == "2026-04-01"
    assert kwargs["end_date"] == "2026-05-01"
    assert kwargs["extra_config"] == {"include_unchanged": True}
    assert kwargs["fresh"] is True


@patch("plexus.cli.feedback.feedback_report.run_feedback_report_block")
def test_scorecard_history_uses_dedicated_block(mock_run_feedback_report_block):
    runner = CliRunner()
    mock_run_feedback_report_block.return_value = {"status": "success", "output": {"scores": []}}

    result = runner.invoke(
        report,
        [
            "scorecard-history",
            "--scorecard",
            "Select Quote HCS Medium Risk",
            "--days",
            "10",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_report_block.call_args
    assert kwargs["block_class"] == "ScorecardHistory"
    assert kwargs["scorecard"] == "Select Quote HCS Medium Risk"
    assert kwargs["score"] is None
    assert kwargs["days"] == 10
    assert kwargs["extra_config"] == {}


@patch("plexus.cli.feedback.feedback_report.run_feedback_report_block")
def test_scorecard_history_supports_single_score_explicit_window_and_summary_model(mock_run_feedback_report_block):
    runner = CliRunner()
    mock_run_feedback_report_block.return_value = {"status": "success", "output": {"scores": []}}

    result = runner.invoke(
        report,
        [
            "scorecard-history",
            "--scorecard",
            "1438",
            "--score",
            "48059",
            "--start-date",
            "2026-04-01",
            "--end-date",
            "2026-05-01",
            "--summary-llm-provider",
            "openai",
            "--summary-llm-model",
            "gpt-5-mini",
            "--fresh",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_report_block.call_args
    assert kwargs["block_class"] == "ScorecardHistory"
    assert kwargs["score"] == "48059"
    assert kwargs["start_date"] == "2026-04-01"
    assert kwargs["end_date"] == "2026-05-01"
    assert kwargs["extra_config"] == {
        "summary_llm_provider": "openai",
        "summary_llm_model": "gpt-5-mini",
    }
    assert kwargs["fresh"] is True


@patch("plexus.cli.feedback.feedback_report.collect_feedback_score_integrity")
@patch("plexus.cli.feedback.feedback_report.resolve_account_id_for_command")
@patch("plexus.cli.feedback.feedback_report.create_client")
def test_integrity_command_emits_orphaned_feedback_diagnostics(
    mock_create_client,
    mock_resolve_account_id,
    mock_collect_feedback_score_integrity,
):
    runner = CliRunner()
    mock_create_client.return_value = MagicMock()
    mock_resolve_account_id.return_value = "acct-1"
    mock_collect_feedback_score_integrity.return_value = {
        "account_id": "acct-1",
        "feedback_total": 10,
        "orphaned_feedback_items": 4,
        "orphaned_percentage": 40.0,
        "orphaned_by_scorecard_score": [],
    }

    result = runner.invoke(
        report,
        [
            "integrity",
            "--start-date",
            "2026-05-01",
            "--end-date",
            "2026-05-07",
        ],
    )

    assert result.exit_code == 0
    assert '"orphaned_feedback_items": 4' in result.output
    _, kwargs = mock_collect_feedback_score_integrity.call_args
    assert kwargs["account_id"] == "acct-1"
    assert kwargs["start_at"] == datetime(2026, 5, 1, tzinfo=timezone.utc)
    assert kwargs["end_at"] == datetime(2026, 5, 7, 23, 59, 59, 999999, tzinfo=timezone.utc)


@patch("plexus.cli.feedback.feedback_report.run_feedback_report_block")
def test_score_results_report_supports_ids_and_repeated_id_flags(mock_run_feedback_report_block):
    runner = CliRunner()
    mock_run_feedback_report_block.return_value = {"status": "success", "output": {"scores": []}}

    result = runner.invoke(
        report,
        [
            "score-results-report",
            "--scorecard",
            "1562",
            "--score",
            "48059",
            "--ids",
            "311434634,311432364",
            "--id",
            "311432363",
            "--id",
            "311432364",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_run_feedback_report_block.call_args
    assert kwargs["block_class"] == "ScoreResultsReport"
    assert kwargs["scorecard"] == "1562"
    assert kwargs["score"] == "48059"
    assert kwargs["extra_config"] == {"ids": ["311434634", "311432364", "311432363"]}


def test_score_results_report_requires_at_least_one_identifier():
    runner = CliRunner()
    result = runner.invoke(
        report,
        [
            "score-results-report",
            "--scorecard",
            "1562",
        ],
    )

    assert result.exit_code != 0
    assert "At least one item identifier is required" in result.output


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
        "scorecard_name": "Example Scorecard",
        "score_name": "Example Score",
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
    assert kwargs["display_title"] == "Example Scorecard - Example Score - Feedback Overview"
    assert "Includes contradiction analysis." in kwargs["display_description"]
    assert "Example Scorecard - Example Score - Feedback Overview" in kwargs["report_name"]


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
        "scorecard_name": "Example Scorecard",
        "score_name": "Example Score",
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
        "scorecard_name": "Example Scorecard",
        "score_name": "Example Score",
    }
    mock_run_programmatic_report_and_persist.return_value = ("report-123", None)

    result = runner.invoke(
        report,
        [
            "overview",
            "--scorecard",
            "Example Scorecard",
            "--score",
            "Example Score",
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
