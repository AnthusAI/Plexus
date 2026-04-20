from plexus.cli.shared.experiment_runner import _extract_run_parameters_from_procedure_yaml


def test_extract_run_parameters_prefers_value_then_default_for_params_mapping():
    yaml_text = """
name: Example
class: Tactus
params:
  scorecard:
    type: string
    default: scorecard-default
  max_samples:
    type: number
    default: 100
    value: 200
  dry_run:
    type: boolean
    default: false
"""
    result = _extract_run_parameters_from_procedure_yaml(yaml_text)
    assert result["scorecard"] == "scorecard-default"
    assert result["max_samples"] == 200
    assert result["dry_run"] is False


def test_extract_run_parameters_supports_parameters_array():
    yaml_text = """
name: Example
parameters:
  - name: days
    type: number
    default: 365
  - name: hint
    type: string
    value: focus on transfer language
"""
    result = _extract_run_parameters_from_procedure_yaml(yaml_text)
    assert result["days"] == 365
    assert result["hint"] == "focus on transfer language"
