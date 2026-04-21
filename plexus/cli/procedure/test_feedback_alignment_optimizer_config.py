from pathlib import Path

import yaml


OPTIMIZER_YAML_PATH = (
    Path(__file__).resolve().parents[2] / "procedures" / "feedback_alignment_optimizer.yaml"
)


def _load_optimizer_config():
    with OPTIMIZER_YAML_PATH.open() as f:
        return yaml.safe_load(f)


def test_optimizer_yaml_defines_dedicated_reporting_agents():
    config = _load_optimizer_config()
    agents = config["agents"]

    assert agents["code_editor"]["model"] == "gpt-5.4"

    assert agents["cycle_analyst"]["model"] == "gpt-5.4"
    assert agents["cycle_analyst"]["max_tokens"] == 1200
    assert agents["cycle_analyst"]["verbosity"] == "low"

    assert agents["report_writer"]["model"] == "gpt-5.2"
    assert agents["report_writer"]["max_tokens"] == 900
    assert agents["report_writer"]["verbosity"] == "low"


def test_optimizer_yaml_routes_report_generation_to_reporting_agents():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'safe_agent_call(cycle_analyst, "cycle_analyst"' in code
    assert 'safe_agent_call(report_writer, "report_writer"' in code
    assert "report_writer.history:add({role = \"system\", content = full_ctx})" in code
    assert "Write a complete technical analysis" not in code


def test_optimizer_yaml_bounds_report_context_and_output_shapes():
    config = _load_optimizer_config()
    code = config["code"]

    assert "Keep the entire report under 450 words." in code
    assert "Exactly 4 bullets, one sentence each." in code
    assert "Exactly 3 short subsections. Each must be exactly 2 sentences." in code
    assert "HARD LIMIT: max 3 agenda items. Under 150 words total." in code
    assert 'trunc(history_text, 2000)' in code
    assert 'trunc(ins.analysis, 800)' in code
    assert 'render_items("FALSE POSITIVES (predicted YES, should be NO)", fp_items, 2)' in code
    assert 'render_items("FALSE NEGATIVES (predicted NO, should be YES)", fn_items, 2)' in code
    assert 'render_items("OTHER MISCLASSIFICATIONS", other_items, 1)' in code
