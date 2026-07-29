"""Contract tests for the reported, human-governed portfolio procedure."""

from __future__ import annotations

from pathlib import Path

import yaml


PROCEDURE_PATH = Path(__file__).resolve().parents[2] / "procedures" / "optimization_portfolio_run.yaml"


def test_portfolio_run_procedure_uses_the_single_runtime_orchestrator_and_structured_human_review():
    parsed = yaml.safe_load(PROCEDURE_PATH.read_text())

    assert parsed["class"] == "Tactus"
    assert parsed["name"] == "Optimization Portfolio Run"
    assert "plexus.optimization.portfolio_run" in parsed["code"]
    assert "Human.review" in parsed["code"]
    assert "action_key" in parsed["code"]
    assert "resource_refs" in parsed["code"]
    assert "preconditions" in parsed["code"]
    assert "response_schema" in parsed["code"]
    assert "approval_responses" in parsed["code"]
    assert "while true do" in parsed["code"]
    assert "set_champion" not in parsed["code"]
    assert "score.update" not in parsed["code"]
