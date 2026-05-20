import importlib
import time
import asyncio

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
        max_tokens=1200,
        temperature=0.0,
    )

    result = await score.predict(Score.Input(text="hello", metadata={}))

    assert result.value == "Yes"
    assert captured["reasoning_effort"] == "high"
    assert captured["verbosity"] == "medium"
    assert captured["max_tokens"] == 1200
    assert captured["temperature"] == 0.0
    assert captured["reset_state_on_execute"] is True


@pytest.mark.asyncio
async def test_tactus_score_uses_fresh_runtime_per_prediction_by_default(monkeypatch):
    seen_runtime_ids = []

    class FakeRuntime:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            seen_runtime_ids.append(id(self))

        async def execute(self, code, context, format):
            return {
                "result": {
                    "value": context["text"],
                    "explanation": f"echo:{context['text']}",
                }
            }

    module = importlib.import_module("plexus.scores.TactusScore")
    monkeypatch.setattr(module, "TactusRuntime", FakeRuntime)

    score = TactusScore(
        name="Reused Runtime",
        code='default_model "openai/gpt-5.4-nano"\nClassifyProcedure {}',
        valid_classes=["alpha", "beta"],
    )

    first = await score.predict(Score.Input(text="alpha", metadata={}))
    second = await score.predict(Score.Input(text="beta", metadata={}))

    assert first.value == "alpha"
    assert second.value == "beta"
    assert len(seen_runtime_ids) == 2


@pytest.mark.asyncio
async def test_tactus_score_can_reuse_runtime_when_explicitly_enabled(monkeypatch):
    seen_runtime_ids = []

    class FakeRuntime:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            seen_runtime_ids.append(id(self))

        async def execute(self, code, context, format):
            return {
                "result": {
                    "value": context["text"],
                    "explanation": f"echo:{context['text']}",
                }
            }

    monkeypatch.setenv("PLEXUS_TACTUS_RUNTIME_ISOLATION_MODE", "reuse")
    module = importlib.import_module("plexus.scores.TactusScore")
    monkeypatch.setattr(module, "TactusRuntime", FakeRuntime)

    score = TactusScore(
        name="Reused Runtime",
        code='default_model "openai/gpt-5.4-nano"\nClassifyProcedure {}',
        valid_classes=["alpha", "beta"],
    )

    first = await score.predict(Score.Input(text="alpha", metadata={}))
    second = await score.predict(Score.Input(text="beta", metadata={}))

    assert first.value == "alpha"
    assert second.value == "beta"
    assert len(seen_runtime_ids) == 1


@pytest.mark.asyncio
async def test_tactus_score_runtime_pool_allows_parallel_predictions(monkeypatch):
    seen_runtime_ids = []

    class FakeRuntime:
        def __init__(self, **kwargs):
            seen_runtime_ids.append(id(self))
            self.agents = {}
            self.log_handler = None
            self.storage_backend = None
            self.tool_primitive = None
            self.message_history_manager = None

        async def execute(self, code, context, format):
            await asyncio.sleep(0.05)
            return {
                "result": {
                    "value": context["text"],
                    "explanation": f"echo:{context['text']}",
                }
            }

    monkeypatch.setenv("PLEXUS_TACTUS_RUNTIME_POOL_SIZE", "2")
    module = importlib.import_module("plexus.scores.TactusScore")
    monkeypatch.setattr(module, "TactusRuntime", FakeRuntime)

    score = TactusScore(
        name="Runtime Pool",
        code='default_model "openai/gpt-5.4-nano"\nClassifyProcedure {}',
        valid_classes=["a", "b"],
    )

    start = time.perf_counter()
    first, second = await asyncio.gather(
        score.predict(Score.Input(text="a", metadata={})),
        score.predict(Score.Input(text="b", metadata={})),
    )
    elapsed = time.perf_counter() - start

    assert first.value == "a"
    assert second.value == "b"
    assert len(seen_runtime_ids) == 2
    assert elapsed < 0.09


@pytest.mark.asyncio
async def test_tactus_score_parallel_predictions_with_blocking_runtime_execute(monkeypatch):
    seen_runtime_ids = []

    class FakeRuntime:
        def __init__(self, **kwargs):
            seen_runtime_ids.append(id(self))
            self.agents = {}
            self.log_handler = None
            self.storage_backend = None
            self.tool_primitive = None
            self.message_history_manager = None

        async def execute(self, code, context, format):
            time.sleep(0.05)
            return {
                "result": {
                    "value": context["text"],
                    "explanation": f"echo:{context['text']}",
                }
            }

    monkeypatch.setenv("PLEXUS_TACTUS_RUNTIME_POOL_SIZE", "2")
    module = importlib.import_module("plexus.scores.TactusScore")
    monkeypatch.setattr(module, "TactusRuntime", FakeRuntime)

    score = TactusScore(
        name="Runtime Pool Blocking Execute",
        code='default_model "openai/gpt-5.4-nano"\nClassifyProcedure {}',
        valid_classes=["a", "b"],
    )

    start = time.perf_counter()
    first, second = await asyncio.gather(
        score.predict(Score.Input(text="a", metadata={})),
        score.predict(Score.Input(text="b", metadata={})),
    )
    elapsed = time.perf_counter() - start

    assert first.value == "a"
    assert second.value == "b"
    assert len(seen_runtime_ids) == 2
    assert elapsed < 0.095
