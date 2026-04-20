import pytest

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
