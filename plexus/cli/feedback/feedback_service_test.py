import asyncio
import pytest
from unittest.mock import Mock, patch

from plexus.cli.feedback.feedback_service import FeedbackService
from plexus.dashboard.api.models.feedback_item import FeedbackItem


def test_find_feedback_items_all_time_requests_item_relationship_fields():
    client = Mock()

    with patch.object(FeedbackItem, "list", return_value=([], None)) as mock_list:
        results = asyncio.run(
            FeedbackService.find_feedback_items(
                client=client,
                scorecard_id="scorecard-123",
                score_id="score-456",
                account_id="account-789",
                days=None,
            )
        )

    assert results == []
    _, kwargs = mock_list.call_args
    assert kwargs["relationship_fields"] == {"item": list(FeedbackItem.GRAPHQL_ITEM_FIELDS)}


@pytest.mark.asyncio
async def test_find_feedback_items_gsi_failure_raises_without_fallback_query():
    client = Mock()
    client.execute.return_value = {"errors": [{"message": "boom"}]}

    with patch.object(FeedbackItem, "list") as mock_list:
        with pytest.raises(RuntimeError, match="Failed to load feedback items with related item metadata"):
            await FeedbackService.find_feedback_items(
                client=client,
                scorecard_id="scorecard-123",
                score_id="score-456",
                account_id="account-789",
                days=30,
            )

    mock_list.assert_not_called()


@pytest.mark.asyncio
async def test_find_feedback_items_gsi_excludes_invalid_items():
    client = Mock()
    client.execute.return_value = {
        "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
            "items": [
                {
                    "id": "valid-1",
                    "accountId": "account-789",
                    "scorecardId": "scorecard-123",
                    "scoreId": "score-456",
                    "itemId": "item-valid-1",
                    "initialAnswerValue": "No",
                    "finalAnswerValue": "Yes",
                    "isInvalid": False,
                    "editedAt": "2026-04-22T00:00:00Z",
                    "createdAt": "2026-04-22T00:00:00Z",
                    "updatedAt": "2026-04-22T00:00:00Z",
                    "item": {"id": "item-valid-1", "text": "text", "metadata": "{}", "identifiers": []},
                },
                {
                    "id": "invalid-1",
                    "accountId": "account-789",
                    "scorecardId": "scorecard-123",
                    "scoreId": "score-456",
                    "itemId": "item-invalid-1",
                    "initialAnswerValue": "No",
                    "finalAnswerValue": "Yes",
                    "isInvalid": True,
                    "editedAt": "2026-04-22T00:00:00Z",
                    "createdAt": "2026-04-22T00:00:00Z",
                    "updatedAt": "2026-04-22T00:00:00Z",
                    "item": {"id": "item-invalid-1", "text": "text", "metadata": "{}", "identifiers": []},
                },
            ],
            "nextToken": None,
        }
    }

    results = await FeedbackService.find_feedback_items(
        client=client,
        scorecard_id="scorecard-123",
        score_id="score-456",
        account_id="account-789",
        days=30,
    )

    assert [item.id for item in results] == ["valid-1"]
