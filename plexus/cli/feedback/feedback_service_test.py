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
