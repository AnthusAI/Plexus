import importlib.util
import sys
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from pathlib import Path

def _scoring_module_path() -> Path:
    return Path(__file__).resolve().parents[1] / "plexus" / "utils" / "scoring.py"


def _load_scoring_module():
    scoring_path = _scoring_module_path()
    spec = importlib.util.spec_from_file_location("plexus_utils_scoring_test", scoring_path)
    module = importlib.util.module_from_spec(spec)
    if "boto3" not in sys.modules:
        sys.modules["boto3"] = SimpleNamespace(client=lambda *_args, **_kwargs: None)
    spec.loader.exec_module(module)
    return module


def test_scoring_module_does_not_use_client_specific_cloudwatch_namespace():
    """Scoring must not ship client-branded CloudWatch metrics (issue #84)."""
    source = _scoring_module_path().read_text(encoding="utf-8")

    assert "CallCriteria/API" not in source
    assert "CloudWatchLogger" not in source
    assert "cloudwatch_logger" not in source


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


def test_create_score_result_persists_structured_timestamps():
    scoring = _load_scoring_module()

    class FakeScoreResult:
        create = Mock(
            return_value=SimpleNamespace(
                id="score-result-1",
                createdAt="2026-05-21T00:00:00Z",
            )
        )

    scoring.ScoreResult = FakeScoreResult

    result_id = asyncio.run(
        scoring.create_score_result(
            item_id="item-1",
            scorecard_id="scorecard-1",
            score_id="score-1",
            account_id="account-1",
            scoring_job_id="job-1",
            external_id="external-1",
            value="Yes",
            explanation='The agent said "General Kenobi" [0:01.20-0:02.00].',
            start_time_seconds=5,
            end_time_seconds=6,
            client=Mock(),
        )
    )

    assert result_id == "score-result-1"
    call_kwargs = FakeScoreResult.create.call_args.kwargs
    assert call_kwargs["startTimeSeconds"] == 5.0
    assert call_kwargs["endTimeSeconds"] == 6.0


def test_create_score_result_parses_bracketed_timestamps_when_structured_missing():
    scoring = _load_scoring_module()

    class FakeScoreResult:
        create = Mock(
            return_value=SimpleNamespace(
                id="score-result-1",
                createdAt="2026-05-21T00:00:00Z",
            )
        )

    scoring.ScoreResult = FakeScoreResult

    asyncio.run(
        scoring.create_score_result(
            item_id="item-1",
            scorecard_id="scorecard-1",
            score_id="score-1",
            account_id="account-1",
            scoring_job_id="job-1",
            external_id="external-1",
            value="Yes",
            explanation='The agent said "General Kenobi" [0:01.20-0:02.00].',
            client=Mock(),
        )
    )

    call_kwargs = FakeScoreResult.create.call_args.kwargs
    assert call_kwargs["startTimeSeconds"] == 1.2
    assert call_kwargs["endTimeSeconds"] == 2.0
