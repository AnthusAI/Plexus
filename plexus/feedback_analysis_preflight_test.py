from __future__ import annotations

import pytest

from plexus.feedback_analysis_preflight import (
    FeedbackAnalysisPreflightError,
    validate_feedback_analysis_preflight,
)


class _StubClient:
    def __init__(self, *, scorecard=None, score=None, score_version=None):
        self._scorecard = scorecard
        self._score = score
        self._score_version = score_version

    def execute(self, query, variables):
        if "GetScorecardPreflight" in query:
            return {"getScorecard": self._scorecard}
        if "GetScorePreflight" in query:
            return {"getScore": self._score}
        if "GetScoreVersionPreflight" in query:
            return {"getScoreVersion": self._score_version}
        raise AssertionError(f"Unexpected query: {query} variables={variables}")


@pytest.mark.asyncio
async def test_validate_feedback_analysis_preflight_passes_when_inputs_valid():
    client = _StubClient(
        scorecard={"id": "scorecard-1"},
        score={"id": "score-1", "scorecardId": "scorecard-1", "championVersionId": "sv-1"},
        score_version={
            "id": "sv-1",
            "scoreId": "score-1",
            "guidelines": "Always follow guideline text.",
            "configuration": {"class": "SomeScore"},
        },
    )

    result = await validate_feedback_analysis_preflight(
        api_client=client,
        scorecard_id="scorecard-1",
        score_id="score-1",
        score_version_id=None,
    )

    assert result.score_version_id == "sv-1"
    assert "Always follow guideline" in result.score_guidelines_text


@pytest.mark.asyncio
async def test_validate_feedback_analysis_preflight_fails_when_scorecard_missing():
    client = _StubClient(
        scorecard=None,
        score={"id": "score-1", "scorecardId": "scorecard-1", "championVersionId": "sv-1"},
        score_version={"id": "sv-1", "scoreId": "score-1", "guidelines": "g", "configuration": {"x": 1}},
    )

    with pytest.raises(FeedbackAnalysisPreflightError) as exc:
        await validate_feedback_analysis_preflight(
            api_client=client,
            scorecard_id="scorecard-1",
            score_id="score-1",
            score_version_id="sv-1",
        )

    assert exc.value.error_code == "SCORECARD_NOT_FOUND"


@pytest.mark.asyncio
async def test_validate_feedback_analysis_preflight_fails_when_version_configuration_missing():
    client = _StubClient(
        scorecard={"id": "scorecard-1"},
        score={"id": "score-1", "scorecardId": "scorecard-1", "championVersionId": "sv-1"},
        score_version={"id": "sv-1", "scoreId": "score-1", "guidelines": "Guideline text", "configuration": None},
    )

    with pytest.raises(FeedbackAnalysisPreflightError) as exc:
        await validate_feedback_analysis_preflight(
            api_client=client,
            scorecard_id="scorecard-1",
            score_id="score-1",
            score_version_id="sv-1",
        )

    assert exc.value.error_code == "SCORE_VERSION_CONFIGURATION_MISSING"


@pytest.mark.asyncio
async def test_validate_feedback_analysis_preflight_fails_when_guidelines_missing():
    client = _StubClient(
        scorecard={"id": "scorecard-1"},
        score={"id": "score-1", "scorecardId": "scorecard-1", "championVersionId": "sv-1"},
        score_version={"id": "sv-1", "scoreId": "score-1", "guidelines": "", "configuration": ""},
    )

    with pytest.raises(FeedbackAnalysisPreflightError) as exc:
        await validate_feedback_analysis_preflight(
            api_client=client,
            scorecard_id="scorecard-1",
            score_id="score-1",
            score_version_id="sv-1",
            require_version_configuration=False,
            require_guidelines_text=True,
        )

    assert exc.value.error_code == "SCORE_GUIDELINES_MISSING"
