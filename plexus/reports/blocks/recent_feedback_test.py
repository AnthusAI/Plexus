from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plexus.reports.blocks.recent_feedback import RecentFeedback


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.account_id = "acct-1"
    return client


@pytest.mark.asyncio
async def test_recent_feedback_lists_items_and_summary(mock_api_client):
    block = RecentFeedback(
        config={"scorecard": "sc-1", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    scorecard = MagicMock(id="sc-1", name="Test Scorecard")
    feedback_items = [
        {
            "id": "fi-1",
            "itemId": "item-a",
            "scoreId": "score-1",
            "initialAnswerValue": "yes",
            "finalAnswerValue": "no",
            "isInvalid": False,
            "editedAt": "2026-04-11T10:00:00+00:00",
            "editCommentValue": "changed",
        },
        {
            "id": "fi-2",
            "itemId": "item-b",
            "scoreId": "score-2",
            "initialAnswerValue": "no",
            "finalAnswerValue": "no",
            "isInvalid": True,
            "editedAt": "2026-04-11T11:00:00+00:00",
        },
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_fetch_feedback_items_window",
            new=AsyncMock(return_value=feedback_items),
        ),
        patch(
            "plexus.reports.blocks.recent_feedback.feedback_utils.fetch_scores_for_scorecard",
            new=AsyncMock(
                return_value=[
                    {"plexus_score_id": "score-1", "plexus_score_name": "Score One"},
                    {"plexus_score_id": "score-2", "plexus_score_name": "Score Two"},
                ]
            ),
        ),
    ):
        output, _ = await block.generate()

    assert output["report_type"] == "recent_feedback"
    assert output["scope"] == "scorecard_all_scores"
    assert output["summary"]["total_feedback_items"] == 2
    assert output["summary"]["overturned_feedback_items"] == 1
    assert output["summary"]["invalid_feedback_items"] == 1
    assert output["summary"]["distinct_items_count"] == 2
    assert output["summary"]["distinct_score_count"] == 2
    assert output["items"][0]["score_name"] == "Score Two"


@pytest.mark.asyncio
async def test_recent_feedback_uses_single_score_when_requested(mock_api_client):
    block = RecentFeedback(
        config={"scorecard": "sc-1", "score": "score-1", "days": 1},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    scorecard = MagicMock(id="sc-1", name="Test Scorecard")
    score = MagicMock(id="score-1", name="Score One")
    captured_kwargs = {}

    async def _fetch_feedback_items_window(**kwargs):
        captured_kwargs.update(kwargs)
        return []

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(block, "_resolve_score", new=AsyncMock(return_value=score)),
        patch.object(block, "_fetch_feedback_items_window", new=_fetch_feedback_items_window),
    ):
        output, _ = await block.generate()

    assert output["scope"] == "single_score"
    assert output["score_id"] == "score-1"
    assert captured_kwargs["score_id"] == "score-1"
    assert captured_kwargs["score_ids"] is None
