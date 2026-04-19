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
