"""Contracts for typed ``plexus procedure run --set`` values."""

from click.testing import CliRunner
import pytest

from plexus.cli.procedure import procedures
from plexus.cli.procedure.procedures import (
    _parse_set_parameter_value,
    _resolve_procedure_yaml_path,
)


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


def test_resolve_procedure_yaml_path_finds_repository_asset_from_runtime_directory(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)

    resolved = _resolve_procedure_yaml_path(
        "plexus/procedures/feedback_alignment_optimizer.yaml"
    )

    assert resolved.name == "feedback_alignment_optimizer.yaml"
    assert resolved.is_file()


def test_resolve_procedure_yaml_path_fails_for_missing_file():
    with pytest.raises(Exception, match="Procedure YAML file was not found"):
        _resolve_procedure_yaml_path("plexus/procedures/does-not-exist.yaml")


def test_yaml_procedure_run_executes_from_worker_runtime_directory(monkeypatch, tmp_path):
    """A dispatched run can create and execute a bundled procedure after cwd becomes /tmp."""
    created: dict[str, object] = {}
    executed: dict[str, object] = {}

    class FakeProcedureService:
        def __init__(self, _client):
            pass

        def create_procedure(self, **kwargs):
            created.update(kwargs)
            return type(
                "CreateResult",
                (),
                {"success": True, "procedure": type("Procedure", (), {"id": "proc-1"})()},
            )()

    async def completed_run(**kwargs):
        executed.update(kwargs)
        return {
            "status": "COMPLETED",
            "procedure_id": "proc-1",
            "task_id": "task-1",
            "message": "Completed",
        }

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLEXUS_ACCOUNT_KEY", "account-key")
    monkeypatch.delenv("PLEXUS_DISPATCH_TASK_ID", raising=False)
    monkeypatch.setattr(procedures, "create_client", lambda: object())
    monkeypatch.setattr(procedures, "ProcedureService", FakeProcedureService)
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
        [
            "run",
            "--yaml",
            "plexus/procedures/feedback_alignment_optimizer.yaml",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert created["account_identifier"] == "account-key"
    assert "class:" in str(created["yaml_config"])
    assert executed["procedure_id"] == "proc-1"


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
