from __future__ import annotations

import yaml
from pathlib import Path

import pytest

from plexus.cli.procedure.scorecard_model_retarget import plan_score_retarget


PROCEDURE_PATH = Path(__file__).resolve().parents[2] / "procedures" / "scorecard_model_retarget.yaml"


LANGGRAPH_SCORE_YAML = """\
name: Test Score
class: LangGraphScore
model_provider: ChatOpenAI
model_name: gpt-5-mini
base_model_name: gpt-5-mini
reasoning_effort: low
verbosity: low
max_tokens: 1200
"""


TACTUS_SCORE_YAML = """\
name: Acknowledges Before Redirecting
class: TactusScore
valid_classes:
  - Yes
  - No
code: |-
  default_model "openai/gpt-5.4-nano"

  ClassifyProcedure {
    classes = {"Yes", "No"},
    system_message = [[Classify the text.]],
    user_message = [[{{ text }}]]
  }
"""


def test_plan_score_retarget_updates_langgraph_root_model_fields():
    plan = plan_score_retarget(
        yaml_content=LANGGRAPH_SCORE_YAML,
        target={
            "model_name": "gpt-5.4-nano",
            "reasoning_effort": "medium",
            "verbosity": "medium",
            "max_tokens": 2000,
        },
    )

    generated = yaml.safe_load(plan["yaml_content"])
    assert plan["changed"] is True
    assert plan["score_class"] == "LangGraphScore"
    assert generated["model_provider"] == "ChatOpenAI"
    assert generated["model_name"] == "gpt-5.4-nano"
    assert generated["base_model_name"] == "gpt-5.4-nano"
    assert generated["reasoning_effort"] == "medium"
    assert generated["verbosity"] == "medium"
    assert generated["max_tokens"] == 2000


def test_plan_score_retarget_updates_tactus_default_model_and_runtime_controls():
    plan = plan_score_retarget(
        yaml_content=TACTUS_SCORE_YAML,
        target={
            "model_name": "gpt-5.4-mini",
            "reasoning_effort": "medium",
            "verbosity": "medium",
        },
    )

    generated = yaml.safe_load(plan["yaml_content"])
    assert plan["changed"] is True
    assert plan["score_class"] == "TactusScore"
    assert 'default_model "openai/gpt-5.4-mini"' in generated["code"]
    assert generated["reasoning_effort"] == "medium"
    assert generated["verbosity"] == "medium"
    assert "model_provider" not in generated
    assert "model_name" not in generated


def test_plan_score_retarget_returns_unchanged_when_target_matches_current():
    plan = plan_score_retarget(
        yaml_content=TACTUS_SCORE_YAML,
        target={"model_name": "gpt-5.4-nano"},
    )

    assert plan["changed"] is False
    assert plan["message"] == "Score already matches target model configuration."


def test_plan_score_retarget_fails_for_unsupported_classes():
    with pytest.raises(ValueError, match="Unsupported score class"):
        plan_score_retarget(
            yaml_content="name: Unsupported\nclass: OtherScore\n",
            target={"model_name": "gpt-5.4-nano"},
        )


def test_plan_score_retarget_rejects_tactus_max_tokens_until_runtime_support_exists():
    with pytest.raises(ValueError, match="max_tokens is not supported"):
        plan_score_retarget(
            yaml_content=TACTUS_SCORE_YAML,
            target={"model_name": "gpt-5.4-mini", "max_tokens": 1000},
        )


def test_scorecard_model_retarget_procedure_declares_contract_and_behavior():
    config = yaml.safe_load(PROCEDURE_PATH.read_text(encoding="utf-8"))

    assert config["name"] == "Scorecard Model Retarget"
    assert config["params"]["scorecard"]["required"] is True
    assert config["params"]["model_name"]["required"] is True
    assert config["params"]["dry_run"]["default"] is True
    assert config["params"]["langgraph_model_provider"]["default"] == "ChatOpenAI"
    assert config["params"]["tactus_model_provider"]["default"] == "openai"
    assert config["outputs"]["created_count"]["type"] == "number"
    assert config["agents"]["placeholder"]["initial_message"] == "Ready."

    code = config["code"]
    assert "Feature: Scorecard model retargeting" in code
    assert "plexus.scorecards.info" in code
    assert "plexus.score.pull" in code
    assert "plexus.scorecard_retarget.plan_score" in code
    assert "plexus.score.update" in code
    assert "plexus.score.set_champion" not in code
    assert "dry_run=true so no ScoreVersions were created" in code
