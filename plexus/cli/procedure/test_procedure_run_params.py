"""Contracts for typed ``plexus procedure run --set`` values."""

from click.testing import CliRunner

from plexus.cli.procedure import procedures
from plexus.cli.procedure.procedures import _parse_set_parameter_value


def test_set_parameter_parser_preserves_json_arrays_and_nested_objects():
    assert _parse_set_parameter_value(
        '["opaque-one", "opaque-two"]'
    ) == ["opaque-one", "opaque-two"]
    assert _parse_set_parameter_value(
        '{"targets":[{"id":"one"},{"id":"two"}]}'
    ) == {"targets": [{"id": "one"}, {"id": "two"}]}


def test_set_parameter_parser_preserves_existing_scalar_coercion():
    assert _parse_set_parameter_value("true") is True
    assert _parse_set_parameter_value("false") is False
    assert _parse_set_parameter_value("12") == 12
    assert _parse_set_parameter_value("1.25") == 1.25
    assert _parse_set_parameter_value("opaque-value") == "opaque-value"


def test_set_parameter_parser_leaves_malformed_structured_text_visible():
    assert _parse_set_parameter_value('["unfinished"') == '["unfinished"'


def test_existing_procedure_run_enters_direct_local_continuation_path(monkeypatch):
    async def completed_run(**_kwargs):
        return {
            "status": "COMPLETED",
            "procedure_id": "procedure-1",
            "task_id": "task-1",
            "message": "Completed",
        }

    monkeypatch.delenv("PLEXUS_DISPATCH_TASK_ID", raising=False)
    monkeypatch.setattr(procedures, "create_client", lambda: object())
    monkeypatch.setattr(
        "plexus.cli.report.utils.resolve_account_id_for_command",
        lambda _client, _account: "account-1",
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.run_procedure_with_task_tracking",
        completed_run,
    )

    result = CliRunner().invoke(
        procedures.procedure,
        ["run", "procedure-1", "--output", "json"],
    )

    assert result.exit_code == 0, result.output
    assert '"status": "COMPLETED"' in result.output
