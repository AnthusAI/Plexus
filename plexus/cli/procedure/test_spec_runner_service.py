import types
from pathlib import Path
from unittest.mock import Mock

import pytest

from plexus.cli.procedure.service import ProcedureService


class _FakeStep:
    def __init__(self, keyword, message, status, duration=0.01, error_message=None):
        self.keyword = keyword
        self.message = message
        self.status = status
        self.duration = duration
        self.error_message = error_message


class _FakeScenario:
    def __init__(self, name, status, steps):
        self.name = name
        self.status = status
        self.duration = 0.1
        self.steps = steps


class _FakeFeature:
    def __init__(self, name, scenarios):
        self.name = name
        self.description = ""
        self.status = "passed"
        self.duration = 0.2
        self.scenarios = scenarios


class _FakeTestResult:
    def __init__(self):
        self.features = [
            _FakeFeature(
                "Feature A",
                [
                    _FakeScenario(
                        "Scenario A",
                        "passed",
                        [_FakeStep("Given", "a precondition", "passed")],
                    )
                ],
            )
        ]
        self.total_scenarios = 1
        self.passed_scenarios = 1
        self.failed_scenarios = 0
        self.total_duration = 0.42


class _FakeValidatorResult:
    def __init__(self, valid=True, gherkin="Feature: X"):
        self.valid = valid
        self.errors = []
        self.warnings = []
        self.registry = types.SimpleNamespace(gherkin_specifications=gherkin)


class _FakeValidator:
    def __init__(self, result):
        self._result = result

    def validate(self, source, mode=None):
        return self._result


class _FakeRunner:
    last_mocked = None
    last_parallel = None
    last_scenario = None

    def __init__(
        self,
        procedure_file,
        mock_tools=None,
        params=None,
        mcp_servers=None,
        tool_paths=None,
        mocked=False,
    ):
        self.procedure_file = procedure_file
        _FakeRunner.last_mocked = mocked

    def setup(self, gherkin_text, custom_steps_dict=None):
        return None

    def run_tests(self, parallel=True, scenario_filter=None):
        _FakeRunner.last_parallel = parallel
        _FakeRunner.last_scenario = scenario_filter
        return _FakeTestResult()

    def cleanup(self):
        return None


@pytest.fixture
def service():
    return ProcedureService(Mock())


def _patch_tactus(monkeypatch, validator_result=None):
    validator_result = validator_result or _FakeValidatorResult()
    monkeypatch.setattr(
        "tactus.validation.validator.TactusValidator",
        lambda: _FakeValidator(validator_result),
    )
    monkeypatch.setattr(
        "tactus.testing.test_runner.TactusTestRunner",
        _FakeRunner,
    )


def test_spec_runner_runs_embedded_specs_from_yaml(service, monkeypatch):
    _patch_tactus(monkeypatch)
    yaml_config = """
name: test
version: 1
class: Tactus
code: |
  Description([[test]])
  Specification([[Feature: Example]])
"""

    result = service.test_procedure_specs(
        yaml_config=yaml_config,
        mode="mock",
        scenario="Scenario A",
        parallel=False,
    )

    assert result["success"] is True
    assert result["mode"] == "mock"
    assert result["summary"]["total_scenarios"] == 1
    assert _FakeRunner.last_mocked is True
    assert _FakeRunner.last_parallel is False
    assert _FakeRunner.last_scenario == "Scenario A"


def test_spec_runner_propagates_integration_mode(service, monkeypatch):
    _patch_tactus(monkeypatch)
    yaml_config = """
name: test
version: 1
class: Tactus
code: |
  Description([[test]])
  Specification([[Feature: Example]])
"""

    result = service.test_procedure_specs(yaml_config=yaml_config, mode="integration")

    assert result["mode"] == "integration"
    assert _FakeRunner.last_mocked is False


def test_spec_runner_fails_on_invalid_yaml(service):
    with pytest.raises(ValueError, match="Invalid YAML configuration"):
        service.test_procedure_specs(yaml_config="not: [valid", mode="mock")


def test_spec_runner_fails_when_code_missing(service):
    with pytest.raises(ValueError, match="non-empty 'code' field"):
        service.test_procedure_specs(
            yaml_config="name: x\nversion: 1\nclass: Tactus\n",
            mode="mock",
        )


def test_spec_runner_fails_when_no_spec_block(service, monkeypatch):
    _patch_tactus(
        monkeypatch, validator_result=_FakeValidatorResult(valid=True, gherkin=None)
    )

    yaml_config = """
name: test
version: 1
class: Tactus
code: |
  Description([[test]])
"""

    with pytest.raises(ValueError, match="No embedded Specification"):
        service.test_procedure_specs(yaml_config=yaml_config, mode="mock")


def test_spec_runner_loads_yaml_from_procedure_id(service, monkeypatch):
    _patch_tactus(monkeypatch)
    yaml_config = """
name: test
version: 1
class: Tactus
code: |
  Description([[test]])
  Specification([[Feature: Example]])
"""
    monkeypatch.setattr(service, "get_procedure_yaml", lambda _id: yaml_config)

    result = service.test_procedure_specs(procedure_id="proc-123")

    assert result["success"] is True
    assert result["metadata"]["procedure_id"] == "proc-123"


@pytest.mark.parametrize(
    "path",
    [
        "plexus/procedures/scorecard_create.yaml",
        "plexus/procedures/score_code_create.yaml",
    ],
)
def test_acceptance_procedure_specs_pass_in_mock_mode(path):
    try:
        from tactus.testing.test_runner import TactusTestRunner  # noqa: F401
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Tactus test runner unavailable: {exc}")

    yaml_text = Path(path).read_text()
    service = ProcedureService(Mock())

    result = service.test_procedure_specs(
        yaml_config=yaml_text,
        mode="mock",
        parallel=False,
    )

    assert result["summary"]["total_scenarios"] > 0
    assert result["summary"]["failed_scenarios"] == 0
