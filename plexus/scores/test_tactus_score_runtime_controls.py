import importlib

import pytest

from plexus.scores.Score import Score
from plexus.scores.TactusScore import TactusScore


@pytest.mark.asyncio
async def test_tactus_score_passes_runtime_gpt5_controls_to_prediction_runtime(monkeypatch):
    captured = {}

    class FakeRuntime:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def execute(self, code, context, format):
            return {"result": {"value": "Yes", "explanation": "acknowledged"}}

    module = importlib.import_module("plexus.scores.TactusScore")
    monkeypatch.setattr(module, "TactusRuntime", FakeRuntime)

    score = TactusScore(
        name="Acknowledges Before Redirecting",
        code='default_model "openai/gpt-5.4-nano"\nClassifyProcedure {}',
        valid_classes=["Yes", "No"],
        reasoning_effort="high",
        verbosity="medium",
    )

    result = await score.predict(Score.Input(text="hello", metadata={}))

    assert result.value == "Yes"
    assert captured["reasoning_effort"] == "high"
    assert captured["verbosity"] == "medium"
