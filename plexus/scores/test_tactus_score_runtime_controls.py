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


@pytest.mark.asyncio
async def test_tactus_score_enriches_explanation_with_timestamps_when_deepgram_present(monkeypatch):
    """Test that TactusScore automatically enriches explanations with timestamps."""

    execution_count = []

    class FakeRuntime:
        def __init__(self, **kwargs):
            self.log_handler = None

        async def execute(self, code, context, format):
            execution_count.append(len(execution_count) + 1)

            # First execution: main score, returns explanation with quotes
            if len(execution_count) == 1:
                return {
                    "result": {
                        "value": "Yes",
                        "explanation": 'The agent said "hello world" to the customer.'
                    }
                }
            # Second execution: enrichment call
            else:
                # Simulate deepgram.enrich_timestamps() adding brackets
                text = context['text']
                enriched = text.replace('"hello world"', '"hello world" [0:00.00-0:01.00]')
                return {"result": enriched}

    module = importlib.import_module("plexus.scores.TactusScore")
    monkeypatch.setattr(module, "TactusRuntime", FakeRuntime)

    score = TactusScore(
        name="Test Score",
        code='ClassifyProcedure { classes = {"Yes", "No"} }',
        valid_classes=["Yes", "No"],
    )

    # Create input with mock deepgram data
    mock_deepgram = {
        "results": {
            "channels": [{
                "alternatives": [{
                    "words": [
                        {"word": "hello", "punctuated_word": "hello", "start": 0.0, "end": 0.5},
                        {"word": "world", "punctuated_word": "world", "start": 0.5, "end": 1.0}
                    ]
                }]
            }]
        }
    }

    result = await score.predict(Score.Input(
        text="transcript text",
        metadata={"deepgram": mock_deepgram}
    ))

    assert result.value == "Yes"
    assert "[0:00.00-0:01.00]" in result.explanation
    assert result.start_time_seconds == 0.0
    assert result.end_time_seconds == 1.0


@pytest.mark.asyncio
async def test_tactus_score_skips_enrichment_when_no_deepgram_data(monkeypatch):
    """Test that enrichment is skipped gracefully when no deepgram data present."""

    enrichment_called = []

    class FakeRuntime:
        def __init__(self, **kwargs):
            self.log_handler = None

        async def execute(self, code, context, format):
            # Track if enrichment was called
            if 'data' in context:
                enrichment_called.append(True)

            return {
                "result": {
                    "value": "Yes",
                    "explanation": "Simple explanation without quotes."
                }
            }

    module = importlib.import_module("plexus.scores.TactusScore")
    monkeypatch.setattr(module, "TactusRuntime", FakeRuntime)

    score = TactusScore(
        name="Test Score",
        code='ClassifyProcedure { classes = {"Yes", "No"} }',
        valid_classes=["Yes", "No"],
    )

    result = await score.predict(Score.Input(
        text="transcript text",
        metadata={}  # No deepgram data
    ))

    assert result.value == "Yes"
    assert len(enrichment_called) == 0  # Enrichment should not be called


@pytest.mark.asyncio
async def test_tactus_score_enrichment_handles_nested_metadata_deepgram(monkeypatch):
    """Test that enrichment handles metadata.metadata.deepgram pattern."""

    enrichment_context_captured = {}
    execution_count = []

    class FakeRuntime:
        def __init__(self, **kwargs):
            self.log_handler = None

        async def execute(self, code, context, format):
            execution_count.append(len(execution_count) + 1)

            # First execution: main score
            if len(execution_count) == 1:
                return {
                    "result": {
                        "value": "Yes",
                        "explanation": 'Found "test quote" in transcript.'
                    }
                }
            # Second execution: enrichment
            else:
                enrichment_context_captured.update(context)
                text = context['text']
                return {"result": text.replace('"test quote"', '"test quote" [1:00.00-1:05.00]')}

    module = importlib.import_module("plexus.scores.TactusScore")
    monkeypatch.setattr(module, "TactusRuntime", FakeRuntime)

    score = TactusScore(
        name="Test Score",
        code='ClassifyProcedure { classes = {"Yes", "No"} }',
        valid_classes=["Yes", "No"],
    )

    mock_deepgram = {"results": {"channels": []}}

    # Test with nested metadata.metadata.deepgram
    result = await score.predict(Score.Input(
        text="transcript",
        metadata={"metadata": {"deepgram": mock_deepgram}}
    ))

    assert result.value == "Yes"
    assert "[1:00.00-1:05.00]" in result.explanation
    assert enrichment_context_captured["data"] == mock_deepgram


@pytest.mark.asyncio
async def test_tactus_score_enrichment_fails_gracefully_on_error(monkeypatch):
    """Test that enrichment failures don't break scoring."""

    class FakeRuntime:
        def __init__(self, **kwargs):
            self.log_handler = None

        async def execute(self, code, context, format):
            # Main score execution
            if 'text' in context:
                return {
                    "result": {
                        "value": "Yes",
                        "explanation": 'Quote "not found in transcript" here.'
                    }
                }
            # Enrichment execution - simulate error
            if 'data' in context:
                raise Exception("Quote not found in transcript")
            raise ValueError(f"Unexpected runtime context keys: {sorted(context.keys())}")

    module = importlib.import_module("plexus.scores.TactusScore")
    monkeypatch.setattr(module, "TactusRuntime", FakeRuntime)

    score = TactusScore(
        name="Test Score",
        code='ClassifyProcedure { classes = {"Yes", "No"} }',
        valid_classes=["Yes", "No"],
    )

    mock_deepgram = {"results": {"channels": []}}

    # Should not raise, should return original explanation
    result = await score.predict(Score.Input(
        text="transcript",
        metadata={"deepgram": mock_deepgram}
    ))

    assert result.value == "Yes"
    assert result.explanation == 'Quote "not found in transcript" here.'
    # No timestamps extracted since enrichment failed
    assert result.start_time_seconds is None
    assert result.end_time_seconds is None


@pytest.mark.asyncio
async def test_tactus_score_enrichment_skipped_when_no_explanation(monkeypatch):
    """Test that enrichment is skipped when score returns no explanation."""

    enrichment_called = []

    class FakeRuntime:
        def __init__(self, **kwargs):
            self.log_handler = None

        async def execute(self, code, context, format):
            if 'data' in context:
                enrichment_called.append(True)

            return {
                "result": {
                    "value": "Yes",
                    "explanation": None  # No explanation
                }
            }

    module = importlib.import_module("plexus.scores.TactusScore")
    monkeypatch.setattr(module, "TactusRuntime", FakeRuntime)

    score = TactusScore(
        name="Test Score",
        code='ClassifyProcedure { classes = {"Yes", "No"} }',
        valid_classes=["Yes", "No"],
    )

    result = await score.predict(Score.Input(
        text="transcript",
        metadata={"deepgram": {"results": {}}}
    ))

    assert result.value == "Yes"
    assert len(enrichment_called) == 0  # Should skip enrichment when no explanation
