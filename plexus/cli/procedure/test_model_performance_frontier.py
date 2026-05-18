from __future__ import annotations

import json
from pathlib import Path

import yaml

from plexus.cli.procedure.model_performance_frontier import (
    apply_override,
    build_result_row,
    build_variants,
    compact_report_envelope,
    mark_pareto_frontier,
    render_artifacts,
)


PROCEDURE_PATH = Path(__file__).resolve().parents[2] / "procedures" / "model_performance_frontier.yaml"


BASE_SCORE_YAML = """\
name: Test Score
class: LangGraphScore
model_provider: ChatOpenAI
model_name: gpt-5-mini
base_model_name: gpt-5-mini
reasoning_effort: medium
verbosity: low
max_tokens: 3000
graph:
  - name: classifier
    class: Classifier
    model_name: gpt-5-mini
    valid_classes: ["Yes", "No"]
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


def test_build_variants_includes_current_first_and_deduplicates_semantic_matches():
    variants = build_variants(
        BASE_SCORE_YAML,
        {
            "include_current": True,
            "models": [
                {"label": "current duplicate", "model_provider": "ChatOpenAI", "model_name": "gpt-5-mini"},
                {"label": "nano", "model_provider": "ChatOpenAI", "model_name": "gpt-5.4-nano"},
            ],
            "parameter_sets": [{"label": "default", "reasoning_effort": "medium", "max_tokens": 3000}],
        },
    )

    assert [variant["label"] for variant in variants] == ["current", "nano"]
    assert variants[0]["is_current"] is True
    assert variants[1]["is_current"] is False
    assert variants[1]["model_name"] == "gpt-5.4-nano"
    assert variants[1]["base_model_name"] == "gpt-5.4-nano"


def test_build_variants_accepts_json_string_candidate_matrix_from_cli_params():
    variants = build_variants(
        BASE_SCORE_YAML,
        json.dumps(
            {
                "include_current": True,
                "models": [{"label": "nano", "model_name": "gpt-5.4-nano"}],
                "parameter_sets": [{"label": "medium", "reasoning_effort": "medium", "verbosity": "medium"}],
            }
        ),
    )

    assert [variant["label"] for variant in variants] == ["current", "nano / medium"]
    generated = yaml.safe_load(variants[1]["yaml_content"])
    assert generated["model_name"] == "gpt-5.4-nano"
    assert generated["base_model_name"] == "gpt-5.4-nano"
    assert generated["verbosity"] == "medium"


def test_build_variants_supports_project_type_ai_root_model_fields():
    variants = build_variants(
        BASE_SCORE_YAML,
        {
            "models": [{"label": "mini", "model_provider": "ChatOpenAI", "model_name": "gpt-5.4-mini"}],
            "parameter_sets": [
                {
                    "label": "low",
                    "reasoning_effort": "low",
                    "verbosity": "medium",
                    "temperature": 0,
                }
            ],
        },
        include_current=False,
    )

    generated = yaml.safe_load(variants[0]["yaml_content"])
    assert generated["model_name"] == "gpt-5.4-mini"
    assert generated["base_model_name"] == "gpt-5.4-mini"
    assert generated["reasoning_effort"] == "low"
    assert generated["verbosity"] == "medium"
    assert generated["temperature"] == 0
    assert generated["graph"][0]["model_name"] == "gpt-5-mini"
    assert generated["graph"][0]["class"] == "Classifier"


def test_build_variants_supports_tactus_score_default_model_and_runtime_controls():
    variants = build_variants(
        TACTUS_SCORE_YAML,
        {
            "models": [{"label": "mini", "model_provider": "openai", "model_name": "gpt-5.4-mini"}],
            "parameter_sets": [
                {
                    "label": "high",
                    "reasoning_effort": "high",
                    "verbosity": "medium",
                    "temperature": 0,
                    "max_tokens": 1200,
                }
            ],
        },
        include_current=False,
    )

    generated = yaml.safe_load(variants[0]["yaml_content"])
    assert generated["class"] == "TactusScore"
    assert 'default_model "openai/gpt-5.4-mini"' in generated["code"]
    assert "temperature = 0," in generated["code"]
    assert "max_tokens = 1200," in generated["code"]
    assert generated["reasoning_effort"] == "high"
    assert generated["verbosity"] == "medium"
    assert "model_provider" not in generated
    assert "model_name" not in generated
    assert variants[0]["model_provider"] == "openai"
    assert variants[0]["model_name"] == "gpt-5.4-mini"


def test_build_variants_extracts_current_tactus_score_model_from_code():
    variants = build_variants(
        TACTUS_SCORE_YAML,
        {
            "include_current": True,
            "models": [{"label": "same", "model_provider": "openai", "model_name": "gpt-5.4-nano"}],
            "parameter_sets": [{"label": "default"}],
        },
    )

    assert [variant["label"] for variant in variants] == ["current"]
    assert variants[0]["model_provider"] == "openai"
    assert variants[0]["model_name"] == "gpt-5.4-nano"


def test_build_variants_allows_explicit_node_overrides():
    variants = build_variants(
        BASE_SCORE_YAML,
        {
            "models": [{"label": "mini", "model_provider": "ChatOpenAI", "model_name": "gpt-5.4-mini"}],
            "parameter_sets": [
                {
                    "label": "node",
                    "extra_overrides": {"graph[0].model_name": "gpt-5.4-mini"},
                }
            ],
        },
        include_current=False,
    )

    generated = yaml.safe_load(variants[0]["yaml_content"])
    assert generated["graph"][0]["model_name"] == "gpt-5.4-mini"


def test_apply_override_rejects_wrong_container_type():
    data = {"graph": [{"name": "classifier"}]}

    try:
        apply_override(data, "graph.name", "bad")
    except ValueError as exc:
        assert "expected a mapping" in str(exc) or "expected a list" in str(exc)
    else:
        raise AssertionError("Expected invalid override path to raise")


def test_build_result_row_combines_cost_per_processed_item_and_feedback_ac1_axis():
    row = build_result_row(
        {
            "label": "candidate",
            "score_version_id": "sv-1",
            "model_name": "gpt-5.4-mini",
            "base_model_name": "gpt-5.4-mini",
            "verbosity": "medium",
        },
        feedback_evaluation={
            "id": "fb-1",
            "cost": 0.6,
            "processed_items": 30,
            "metrics": [
                {"name": "Alignment", "value": 0.32},
                {"name": "Accuracy", "value": 0.72},
            ],
        },
        regression_evaluation={
            "id": "acc-1",
            "cost": 0.4,
            "processed_items": 20,
            "metrics": [
                {"name": "Alignment", "value": 0.28},
                {"name": "Accuracy", "value": 0.68},
            ],
        },
    )

    assert row["accuracy_axis"] == 0.32
    assert row["feedback_metrics"]["alignment"] == 0.32
    assert row["feedback_metrics"]["accuracy"] == 0.72
    assert row["cost_axis"] == 0.02
    assert row["total_cost"] == 1.0
    assert row["processed_items"] == 50
    assert row["base_model_name"] == "gpt-5.4-mini"
    assert row["verbosity"] == "medium"
    assert row["feedback_evaluation_id"] == "fb-1"
    assert row["regression_evaluation_id"] == "acc-1"


def test_mark_pareto_frontier_marks_only_non_dominated_rows():
    rows = mark_pareto_frontier(
        [
            {"label": "cheap-good", "cost_axis": 0.01, "accuracy_axis": 0.80},
            {"label": "expensive-worse", "cost_axis": 0.02, "accuracy_axis": 0.75},
            {"label": "expensive-best", "cost_axis": 0.03, "accuracy_axis": 0.90},
        ]
    )

    by_label = {row["label"]: row["is_pareto_frontier"] for row in rows}
    assert by_label == {
        "cheap-good": True,
        "expensive-worse": False,
        "expensive-best": True,
    }


def test_render_artifacts_and_compact_envelope_are_report_attachment_ready():
    artifacts = render_artifacts(
        [{"label": "current", "cost_axis": 0.01, "accuracy_axis": 0.8}],
        title="Frontier",
    )
    assert set(artifacts) == {"frontier.json", "frontier.csv", "frontier.html"}
    assert "is_pareto_frontier" in artifacts["frontier.json"]
    assert "current" in artifacts["frontier.csv"]
    assert "<svg" in artifacts["frontier.html"]

    envelope = compact_report_envelope(
        artifact_paths=["reportblocks/rb/frontier.json", "reportblocks/rb/frontier.csv"],
        rows=[{"is_pareto_frontier": True}],
    )
    assert envelope["output_compacted"] is True
    assert envelope["attached_files"] == ["reportblocks/rb/frontier.json", "reportblocks/rb/frontier.csv"]
    assert envelope["preview"]["frontier_count"] == 1


def test_procedure_yaml_declares_contract_and_specification():
    config = yaml.safe_load(PROCEDURE_PATH.read_text(encoding="utf-8"))

    assert config["params"]["scorecard"]["required"] is True
    assert config["params"]["score"]["required"] is True
    assert config["params"]["candidate_matrix"]["type"] == "object"
    assert "base_model_name" in config["params"]["candidate_matrix"]["description"]
    assert "TactusScore" in config["params"]["candidate_matrix"]["description"]
    assert "verbosity" in config["params"]["candidate_matrix"]["description"]
    assert config["params"]["evaluation_budget_usd"]["default"] == 5.0
    assert config["outputs"]["report_output"]["type"] == "object"
    assert config["agents"]["placeholder"]["system_prompt"]
    assert config["agents"]["placeholder"]["initial_message"] == "Ready."

    code = config["code"]
    assert "Feature: Model performance frontier" in code
    assert "plexus.model_frontier.plan" in code
    assert "plexus.score.update" in code
    assert "plexus.evaluation.run" in code
    assert "Step.checkpoint(function()" in code
    assert "local build_ok, build = pcall(function()" in code
    assert "local unbalanced_ok, unbalanced = pcall(function()" in code
    assert "has_text(check.feedback_target_hash)" in code
    assert "No eligible labeled feedback-derived records are available" in code
    assert "budget = args.budget or eval_budget()" in code
    assert "plexus.model_frontier.finalize" in code
