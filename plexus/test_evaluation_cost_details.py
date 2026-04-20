import pytest
from datetime import datetime, timezone

from plexus.Evaluation import Evaluation


def test_build_cost_details_from_expenses_single_model():
    expenses = {
        "total_cost": 1.25,
        "llm_calls": 2,
        "prompt_tokens": 500,
        "completion_tokens": 100,
        "cached_tokens": 0,
        "components": [
            {
                "type": "api_call",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "prompt_tokens": 300,
                "completion_tokens": 60,
                "cached_tokens": 0,
                "usd": 0.75,
            },
            {
                "type": "api_call",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "prompt_tokens": 200,
                "completion_tokens": 40,
                "cached_tokens": 0,
                "usd": 0.50,
            },
        ],
    }

    details = Evaluation.build_cost_details_from_expenses(expenses)
    assert details["schema_version"] == 1
    assert details["total_usd"] == pytest.approx(1.25)
    assert details["llm_calls"] == 2
    assert len(details["breakdown"]) == 1
    row = details["breakdown"][0]
    assert row["provider"] == "openai"
    assert row["model"] == "gpt-4o-mini"
    assert row["spent_usd"] == pytest.approx(1.25)
    assert row["total_tokens"] == 600


def test_build_cost_details_from_expenses_multi_model():
    expenses = {
        "total_cost": 3.0,
        "llm_calls": 3,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_tokens": 0,
        "components": [
            {"type": "api_call", "provider": "openai", "model": "gpt-4o-mini", "usd": 1.0, "prompt_tokens": 100, "completion_tokens": 10},
            {"type": "api_call", "provider": "openai", "model": "gpt-4o", "usd": 2.0, "prompt_tokens": 50, "completion_tokens": 5},
            {"type": "http_call", "service": "irrelevant", "usd": 99.0},
        ],
    }
    details = Evaluation.build_cost_details_from_expenses(expenses)
    assert len(details["breakdown"]) == 2
    models = {(row["provider"], row["model"]): row for row in details["breakdown"]}
    assert models[("openai", "gpt-4o-mini")]["spent_usd"] == pytest.approx(1.0)
    assert models[("openai", "gpt-4o")]["spent_usd"] == pytest.approx(2.0)


def test_update_variables_preserves_notes_and_baselines_when_adding_cost_details():
    class _Scorecard:
        @staticmethod
        def get_accumulated_costs():
            return {
                "total_cost": 0.42,
                "llm_calls": 2,
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "cached_tokens": 0,
                "components": [
                    {
                        "type": "api_call",
                        "provider": "openai",
                        "model": "gpt-5.4",
                        "prompt_tokens": 100,
                        "completion_tokens": 20,
                        "cached_tokens": 0,
                        "usd": 0.42,
                    }
                ],
            }

    class _DashboardClient:
        @staticmethod
        def execute(_query, _variables):
            return {
                "getEvaluation": {
                    "parameters": {
                        "notes": "Hypothesis 2: tighten ambiguous cost language",
                        "metadata": {
                            "baseline": "eval-baseline",
                            "current_baseline": "eval-current",
                        },
                    }
                }
            }

    evaluation = object.__new__(Evaluation)
    evaluation.started_at = datetime.now(timezone.utc)
    evaluation.processed_items = 5
    evaluation.number_of_texts_to_sample = 200
    evaluation.experiment_id = "eval-123"
    evaluation.scorecard = _Scorecard()
    evaluation.dashboard_client = _DashboardClient()
    evaluation.parameters = None
    evaluation.score_id = None
    evaluation.score_version_id = None
    evaluation.logging = __import__("logging").getLogger("test")

    running_variables = evaluation._get_update_variables(
        metrics={"alignment": 0.51, "accuracy": 0.75, "precision": 0.8, "recall": 0.7},
        status="RUNNING",
    )
    running_input = running_variables["input"]
    assert running_input["cost"] == pytest.approx(0.42)
    assert running_input.get("parameters") is None

    evaluation.parameters = {
        "notes": "Hypothesis 2: tighten ambiguous cost language",
        "metadata": {
            "baseline": "eval-baseline",
            "current_baseline": "eval-current",
        },
    }

    variables = evaluation._get_update_variables(
        metrics={"alignment": 0.51, "accuracy": 0.75, "precision": 0.8, "recall": 0.7},
        status="COMPLETED",
    )
    update_input = variables["input"]
    assert update_input["cost"] == pytest.approx(0.42)
    params = update_input.get("parameters")
    assert isinstance(params, str)
    parsed = __import__("json").loads(params)
    assert parsed.get("notes") == "Hypothesis 2: tighten ambiguous cost language"
    metadata = parsed.get("metadata") or {}
    assert metadata.get("baseline") == "eval-baseline"
    assert metadata.get("current_baseline") == "eval-current"
    assert isinstance(metadata.get("cost_details"), dict)
