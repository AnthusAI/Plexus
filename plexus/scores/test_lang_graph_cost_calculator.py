import sys
from unittest.mock import patch

from plexus.scores.LangGraphScore import _CostCalculator


def test_cost_calculator_falls_back_when_optional_calculator_is_unavailable():
    with (
        patch.dict(
            sys.modules,
            {
                "openai_cost_calculator": None,
                "openai_cost_calculator.openai_cost_calculator": None,
            },
        ),
        patch("litellm.cost_per_token", return_value=(0.12, 0.34)) as fallback,
    ):
        result = _CostCalculator.cost_per_token(
            model="test-model",
            prompt_tokens=10,
            completion_tokens=5,
        )

    assert result == (0.12, 0.34)
    fallback.assert_called_once_with(
        model="test-model",
        prompt_tokens=10,
        completion_tokens=5,
    )
