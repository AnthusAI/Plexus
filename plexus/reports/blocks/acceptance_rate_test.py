from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plexus.reports.blocks.acceptance_rate import AcceptanceRate


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.account_id = "acct-1"
    return client


@pytest.mark.asyncio
async def test_acceptance_rate_computes_item_and_score_result_acceptance(mock_api_client):
    block = AcceptanceRate(
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
            "id": "fi-1b",
            "itemId": "item-a",
            "scoreId": "score-1",
            "initialAnswerValue": "yes",
            "finalAnswerValue": "yes",
            "isInvalid": False,
            "editedAt": "2026-04-11T09:00:00+00:00",
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
    assert summary["accepted_items"] == 1
    assert summary["corrected_items"] == 1
    assert summary["item_acceptance_rate"] == 0.5
    assert summary["total_score_results"] == 3
    assert summary["accepted_score_results"] == 2
    assert summary["corrected_score_results"] == 1
    assert summary["score_result_acceptance_rate"] == pytest.approx(2 / 3)

    items = {item["item_id"]: item for item in output["items"]}
    assert items["item-a"]["item_accepted"] is False
    assert items["item-b"]["item_accepted"] is True
    assert items["item-a"]["feedback_items_total"] == 3
    assert items["item-a"]["feedback_items_valid"] == 3


@pytest.mark.asyncio
async def test_feedback_items_window_fans_out_by_score_ids_and_dedupes(mock_api_client):
    block = AcceptanceRate(
        config={"scorecard": "sc-1", "days": 1},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    seen_score_ids = []

    def _execute(query, variables):
        score_id = variables["compositeCondition"]["between"][0]["scoreId"]
        seen_score_ids.append(score_id)
        if score_id == "score-1":
            return {
                "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
                    "items": [
                        {
                            "id": "fi-dup",
                            "itemId": "item-a",
                            "scoreId": "score-1",
                            "editedAt": "2026-04-01T10:00:00+00:00",
                            "isInvalid": False,
                        }
                    ],
                    "nextToken": None,
                }
            }
        return {
            "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
                "items": [
                    {
                        "id": "fi-dup",
                        "itemId": "item-a",
                        "scoreId": "score-2",
                        "editedAt": "2026-04-01T11:00:00+00:00",
                        "isInvalid": False,
                    },
                    {
                        "id": "fi-2",
                        "itemId": "item-b",
                        "scoreId": "score-2",
                        "editedAt": "2026-04-01T12:00:00+00:00",
                        "isInvalid": False,
                    },
                ],
                "nextToken": None,
            }
        }

    mock_api_client.execute.side_effect = _execute

    items = await block._fetch_feedback_items_window(
        account_id="acct-1",
        scorecard_id="sc-1",
        start_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 4, 2, tzinfo=timezone.utc),
        score_id=None,
        score_ids=["score-1", "score-2", "score-1"],
    )

    assert sorted(seen_score_ids) == ["score-1", "score-2"]
    assert sorted(item["id"] for item in items) == ["fi-2", "fi-dup"]
    deduped = next(item for item in items if item["id"] == "fi-dup")
    assert deduped["scoreId"] == "score-2"


@pytest.mark.asyncio
async def test_feedback_items_window_uses_composite_index_when_score_is_present(mock_api_client):
    block = AcceptanceRate(
        config={"scorecard": "sc-1", "days": 1},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    captured: dict = {}

    def _execute(query, variables):
        captured["query"] = query
        captured["variables"] = variables
        return {"listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {"items": [], "nextToken": None}}

    mock_api_client.execute.side_effect = _execute

    items = await block._fetch_feedback_items_window(
        account_id="acct-1",
        scorecard_id="sc-1",
        start_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 4, 2, tzinfo=timezone.utc),
        score_id="score-1",
    )

    assert items == []
    assert "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt" in captured["query"]
    assert captured["variables"]["sortDirection"] == "DESC"
