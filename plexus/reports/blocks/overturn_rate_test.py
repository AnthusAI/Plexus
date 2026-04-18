from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plexus.reports.blocks.overturn_rate import OverturnRate


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.account_id = "acct-1"
    return client


@pytest.mark.asyncio
async def test_overturn_rate_computes_item_and_corpus_rates(mock_api_client):
    block = OverturnRate(
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
    assert summary["overturned_score_results"] == 1
    assert summary["upheld_score_results"] == 2
    assert summary["corpus_overturn_rate"] == pytest.approx(1 / 3)

    items = {item["item_id"]: item for item in output["items"]}
    assert items["item-a"]["overturn_rate"] == pytest.approx(0.5)
    assert items["item-b"]["overturn_rate"] == 0.0
