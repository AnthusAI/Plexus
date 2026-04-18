from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plexus.reports.blocks.correction_rate import CorrectionRate


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.account_id = "acct-1"
    return client


@pytest.mark.asyncio
async def test_correction_rate_computes_item_and_corpus_rates(mock_api_client):
    block = CorrectionRate(
        config={"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    scorecard = MagicMock(id="sc-1", name="Test Scorecard")
    score_results = [
        {
            "id": "sr-1",
            "itemId": "item-a",
            "scoreId": "score-1",
            "value": "yes",
            "type": "prediction",
            "status": "COMPLETED",
            "code": "200",
            "evaluationId": None,
            "updatedAt": "2026-04-10T10:00:00+00:00",
            "score": {"id": "score-1", "name": "Score 1"},
        },
        {
            "id": "sr-2",
            "itemId": "item-a",
            "scoreId": "score-2",
            "value": "no",
            "type": "prediction",
            "status": "COMPLETED",
            "code": "200",
            "evaluationId": None,
            "updatedAt": "2026-04-10T10:01:00+00:00",
            "score": {"id": "score-2", "name": "Score 2"},
        },
        {
            "id": "sr-3",
            "itemId": "item-b",
            "scoreId": "score-1",
            "value": "yes",
            "type": "prediction",
            "status": "COMPLETED",
            "code": "200",
            "evaluationId": None,
            "updatedAt": "2026-04-10T10:02:00+00:00",
            "score": {"id": "score-1", "name": "Score 1"},
        },
    ]
    feedback_items = [
        {
            "id": "fi-1",
            "itemId": "item-a",
            "scoreId": "score-1",
            "initialAnswerValue": "yes",
            "finalAnswerValue": "no",
            "isInvalid": False,
            "editedAt": "2026-04-11T10:00:00+00:00",
        },
        {
            "id": "fi-2",
            "itemId": "item-a",
            "scoreId": "score-2",
            "initialAnswerValue": "no",
            "finalAnswerValue": "no",
            "isInvalid": False,
            "editedAt": "2026-04-11T10:01:00+00:00",
        },
        {
            "id": "fi-3",
            "itemId": "item-b",
            "scoreId": "score-1",
            "initialAnswerValue": "yes",
            "finalAnswerValue": "no",
            "isInvalid": True,
            "editedAt": "2026-04-11T10:02:00+00:00",
        },
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_fetch_score_results_window", new=AsyncMock(return_value=score_results)),
        patch.object(block, "_fetch_feedback_items_window", new=AsyncMock(return_value=feedback_items)),
    ):
        output, _ = await block.generate()

    summary = output["summary"]
    assert summary["total_items"] == 2
    assert summary["total_score_results"] == 3
    assert summary["corrected_score_results"] == 1
    assert summary["uncorrected_score_results"] == 2
    assert summary["corpus_correction_rate"] == pytest.approx(1 / 3)

    items = {item["item_id"]: item for item in output["items"]}
    assert items["item-a"]["correction_rate"] == pytest.approx(0.5)
    assert items["item-b"]["correction_rate"] == 0.0


@pytest.mark.asyncio
async def test_score_results_window_applies_optional_score_filter(mock_api_client):
    block = CorrectionRate(
        config={"scorecard": "sc-1", "days": 1},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    captured: dict = {}

    def _execute(query, variables):
        captured["query"] = query
        captured["variables"] = variables
        return {"listScoreResultByScorecardIdAndUpdatedAt": {"items": [], "nextToken": None}}

    mock_api_client.execute.side_effect = _execute

    results = await block._fetch_score_results_window(
        account_id="acct-1",
        scorecard_id="sc-1",
        start_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 4, 2, tzinfo=timezone.utc),
        score_id="score-1",
    )

    assert results == []
    assert "listScoreResultByScorecardIdAndUpdatedAt" in captured["query"]
    assert captured["variables"]["filter"]["accountId"] == {"eq": "acct-1"}
    assert captured["variables"]["filter"]["scoreId"] == {"eq": "score-1"}


@pytest.mark.asyncio
async def test_same_day_explicit_range_is_allowed(mock_api_client):
    block = CorrectionRate(
        config={"scorecard": "sc-1", "start_date": "2026-04-08", "end_date": "2026-04-08"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    scorecard = MagicMock(id="sc-1", name="Test Scorecard")

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_fetch_score_results_window", new=AsyncMock(return_value=[])),
        patch.object(block, "_fetch_feedback_items_window", new=AsyncMock(return_value=[])),
    ):
        output, _ = await block.generate()

    assert "error" not in output
    assert output["summary"]["total_score_results"] == 0
    assert output["date_range"]["start"].startswith("2026-04-08T00:00:00")
    assert output["date_range"]["end"].startswith("2026-04-08T23:59:59")
