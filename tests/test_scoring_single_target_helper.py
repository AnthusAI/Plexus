import importlib.util
import sys
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from pathlib import Path

import pytest

def _load_scoring_module():
    scoring_path = Path(__file__).resolve().parents[1] / "plexus" / "utils" / "scoring.py"
    spec = importlib.util.spec_from_file_location("plexus_utils_scoring_test", scoring_path)
    module = importlib.util.module_from_spec(spec)
    if "boto3" not in sys.modules:
        sys.modules["boto3"] = SimpleNamespace(client=lambda *_args, **_kwargs: None)
    spec.loader.exec_module(module)
    return module


def _make_result(value="ok", name="Target Score"):
    return SimpleNamespace(
        value=value,
        metadata={},
        parameters=SimpleNamespace(name=name, key=name),
    )


def test_helper_passes_subset_and_returns_target_by_id():
    scoring = _load_scoring_module()
    result = _make_result()
    scorecard = SimpleNamespace(
        score_entire_text=AsyncMock(return_value={"score-id": result})
    )
    item = SimpleNamespace(id="item-1")

    outcome = asyncio.run(
        scoring.score_single_target_with_dependencies(
            scorecard,
            text="hello",
            metadata={"a": 1},
            modality="API",
            item=item,
            target_score_id="score-id",
            target_score_name="Target Score",
        )
    )

    assert outcome.dependency_unmet is False
    assert outcome.result is result
    call_kwargs = scorecard.score_entire_text.call_args.kwargs
    assert call_kwargs["subset_of_score_names"] == ["Target Score"]
    assert call_kwargs["item"] is item


def test_helper_falls_back_to_parameter_name_when_id_lookup_misses():
    scoring = _load_scoring_module()
    result = _make_result(name="Target Score")
    scorecard = SimpleNamespace(
        score_entire_text=AsyncMock(return_value={"other-id": result})
    )

    outcome = asyncio.run(
        scoring.score_single_target_with_dependencies(
            scorecard,
            text="hello",
            metadata={},
            modality="API",
            item=None,
            target_score_id="score-id",
            target_score_name="Target Score",
        )
    )

    assert outcome.dependency_unmet is False
    assert outcome.result is result


def test_helper_marks_dependency_unmet_when_target_is_skipped():
    scoring = _load_scoring_module()
    scorecard = SimpleNamespace(
        score_entire_text=AsyncMock(return_value={"score-id": "SKIPPED"})
    )

    outcome = asyncio.run(
        scoring.score_single_target_with_dependencies(
            scorecard,
            text="hello",
            metadata={},
            modality="API",
            item=None,
            target_score_id="score-id",
            target_score_name="Target Score",
        )
    )

    assert outcome.dependency_unmet is True
    assert outcome.result is None


def test_helper_marks_dependency_unmet_when_scorecard_raises_skipped_exception():
    scoring = _load_scoring_module()
    SkippedScoreException = type("SkippedScoreException", (Exception,), {})
    scorecard = SimpleNamespace(
        score_entire_text=AsyncMock(
            side_effect=SkippedScoreException("condition unmet")
        )
    )

    outcome = asyncio.run(
        scoring.score_single_target_with_dependencies(
            scorecard,
            text="hello",
            metadata={},
            modality="API",
            item=None,
            target_score_id="score-id",
            target_score_name="Target Score",
        )
    )

    assert outcome.dependency_unmet is True
    assert outcome.result is None
