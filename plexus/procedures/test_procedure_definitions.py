"""Definition-level tests for Tactus procedure YAML files."""

from pathlib import Path

import yaml

from plexus.cli.procedure.service import _validate_yaml_template


def _load_yaml(path: str) -> dict:
    file_path = Path(path)
    data = yaml.safe_load(file_path.read_text())
    assert isinstance(data, dict)
    return data


def test_scorecard_create_definition_is_valid_tactus_template():
    """scorecard_create should remain a valid Tactus procedure definition."""
    data = _load_yaml("plexus/procedures/scorecard_create.yaml")

    assert data.get("name") == "scorecard_create"
    assert data.get("class") == "Tactus"
    assert isinstance(data.get("code"), str)
    assert data["code"].strip() != ""
    assert "Specification([[" in data["code"]
    assert "Procedure {" in data["code"]
    assert _validate_yaml_template(data) is True


def test_score_code_create_definition_is_valid_tactus_template():
    """score_code_create should remain a valid Tactus procedure definition."""
    data = _load_yaml("plexus/procedures/score_code_create.yaml")

    assert data.get("name") == "score_code_create"
    assert data.get("class") == "Tactus"
    assert isinstance(data.get("code"), str)
    assert data["code"].strip() != ""
    assert "Specification([[" in data["code"]
    assert "Procedure {" in data["code"]
    assert _validate_yaml_template(data) is True


def test_score_code_create_has_required_agents_and_tools():
    """score_code_create should expose the expected OODA agents and tool wiring."""
    data = _load_yaml("plexus/procedures/score_code_create.yaml")
    agents = data.get("agents", {})

    assert "observer" in agents
    assert "orienter" in agents
    assert "planner" in agents
    assert "code_drafter" in agents
    assert "validator" in agents
    assert "actor" in agents

    observer_tools = set(agents["observer"].get("tools", []))
    assert "plexus_scorecards_list" in observer_tools
    assert "plexus_scorecard_info" in observer_tools
    assert "plexus_score_info" in observer_tools

    validator_tools = set(agents["validator"].get("tools", []))
    assert "plexus_predict" in validator_tools

    actor_tools = set(agents["actor"].get("tools", []))
    assert "plexus_score_update" in actor_tools
