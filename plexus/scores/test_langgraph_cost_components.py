from types import SimpleNamespace
from unittest.mock import patch

import pytest

from plexus.scores.LangGraphScore import LangGraphScore


def test_langgraph_get_accumulated_costs_returns_model_components_per_node():
    score = object.__new__(LangGraphScore)
    score.parameters = SimpleNamespace(model_provider="ChatOpenAI", model_name="gpt-4o-mini")

    node_a = SimpleNamespace(
        parameters=SimpleNamespace(model_provider="ChatOpenAI", model_name="gpt-4o-mini"),
        get_token_usage=lambda: {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "successful_requests": 2,
            "cached_tokens": 10,
        },
    )
    node_b = SimpleNamespace(
        parameters=SimpleNamespace(model_provider="BedrockChat", model_name="anthropic.claude-3-haiku-20240307-v1:0"),
        get_token_usage=lambda: {
            "prompt_tokens": 200,
            "completion_tokens": 40,
            "total_tokens": 240,
            "successful_requests": 3,
            "cached_tokens": 0,
        },
    )
    score.node_instances = [("node_a", node_a), ("node_b", node_b)]
    score.get_token_usage = lambda: {
        "prompt_tokens": 300,
        "completion_tokens": 90,
        "total_tokens": 390,
        "successful_requests": 5,
        "cached_tokens": 10,
    }

    with patch("plexus.scores.LangGraphScore._litellm.cost_per_token") as mock_cost_per_token:
        mock_cost_per_token.side_effect = [(0.01, 0.02), (0.03, 0.01)]
        costs = score.get_accumulated_costs()

    assert costs["total_cost"] == pytest.approx(0.07)
    assert costs["llm_calls"] == 5
    assert isinstance(costs.get("components"), list)
    assert len(costs["components"]) == 2

    components = {(c.get("provider"), c.get("model")): c for c in costs["components"]}
    first = components[("openai", "gpt-4o-mini")]
    assert first["llm_calls"] == 2
    assert first["prompt_tokens"] == 100
    assert first["completion_tokens"] == 50

    second = components[("bedrock", "anthropic.claude-3-haiku-20240307-v1:0")]
    assert second["llm_calls"] == 3
    assert second["prompt_tokens"] == 200
    assert second["completion_tokens"] == 40
