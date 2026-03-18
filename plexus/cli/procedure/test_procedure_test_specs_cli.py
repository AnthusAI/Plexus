from click.testing import CliRunner
from unittest.mock import Mock

from plexus.cli.procedure.procedures import procedure


def test_test_specs_cli_with_procedure_id(monkeypatch):
    runner = CliRunner()

    mock_service = Mock()
    mock_service.test_procedure_specs.return_value = {
        "success": True,
        "mode": "mock",
        "summary": {
            "total_scenarios": 1,
            "passed_scenarios": 1,
            "failed_scenarios": 0,
            "duration_seconds": 0.1,
        },
        "features": [],
        "metadata": {
            "procedure_id": "proc-1",
            "parallel": True,
            "workers": None,
            "scenario_filter": None,
        },
    }

    monkeypatch.setattr("plexus.cli.procedure.procedures.create_client", Mock)

    def _mock_procedure_service(_client):
        return mock_service

    monkeypatch.setattr(
        "plexus.cli.procedure.procedures.ProcedureService", _mock_procedure_service
    )

    result = runner.invoke(procedure, ["test-specs", "proc-1", "--output", "json"])

    assert result.exit_code == 0
    assert '"success": true' in result.output.lower()
    mock_service.test_procedure_specs.assert_called_once()


def test_test_specs_cli_with_yaml_file(monkeypatch):
    runner = CliRunner()

    mock_service = Mock()
    mock_service.test_procedure_specs.return_value = {
        "success": True,
        "mode": "mock",
        "summary": {
            "total_scenarios": 1,
            "passed_scenarios": 1,
            "failed_scenarios": 0,
            "duration_seconds": 0.1,
        },
        "features": [],
        "metadata": {
            "procedure_id": None,
            "parallel": True,
            "workers": None,
            "scenario_filter": None,
        },
    }

    monkeypatch.setattr("plexus.cli.procedure.procedures.create_client", Mock)

    def _mock_procedure_service(_client):
        return mock_service

    monkeypatch.setattr(
        "plexus.cli.procedure.procedures.ProcedureService", _mock_procedure_service
    )

    with runner.isolated_filesystem():
        with open("proc.yaml", "w") as f:
            f.write(
                "name: t\nversion: 1\nclass: Tactus\ncode: |\n  Specification([[Feature: Example]])\n"
            )

        result = runner.invoke(
            procedure, ["test-specs", "--yaml", "proc.yaml", "--output", "json"]
        )

    assert result.exit_code == 0
    assert '"success": true' in result.output.lower()
    mock_service.test_procedure_specs.assert_called_once()


def test_test_specs_cli_rejects_invalid_input_combination():
    runner = CliRunner()

    result = runner.invoke(procedure, ["test-specs"])  # neither
    assert result.exit_code == 0
    assert "provide either a procedure id or --yaml" in result.output.lower()

    result = runner.invoke(
        procedure, ["test-specs", "proc-1", "--yaml", "x.yaml"]
    )  # both
    assert result.exit_code == 0
    assert "cannot specify both procedure id and --yaml" in result.output.lower()
