from unittest.mock import Mock, patch

from plexus.dashboard.api.models.feedback_item import FeedbackItem


def test_feedback_item_invalidate_delegates_to_update_mutation():
    client = Mock()
    updated_item = Mock(id="feedback-123")

    with patch.object(
        FeedbackItem,
        "_update_feedback_item",
        return_value=updated_item,
    ) as update_mock:
        result = FeedbackItem.invalidate(client, "feedback-123")

    update_mock.assert_called_once_with(
        client=client,
        feedback_item_id="feedback-123",
        feedback_data={"isInvalid": True},
        debug=False,
    )
    assert result == updated_item


def test_update_feedback_item_mutation_requests_is_invalid_field():
    client = Mock()
    client.execute.return_value = {
        "updateFeedbackItem": {
            "id": "feedback-123",
            "accountId": "account-1",
            "scorecardId": "scorecard-1",
            "scoreId": "score-1",
            "cacheKey": "score-1:item-1",
            "itemId": "item-1",
            "initialAnswerValue": "Yes",
            "finalAnswerValue": "No",
            "initialCommentValue": None,
            "finalCommentValue": None,
            "editCommentValue": None,
            "isAgreement": False,
            "isInvalid": True,
            "editedAt": None,
            "editorName": None,
            "createdAt": None,
            "updatedAt": None,
        }
    }

    updated = FeedbackItem._update_feedback_item(
        client,
        "feedback-123",
        {"isInvalid": True},
    )

    mutation = client.execute.call_args.kwargs["query"]
    assert "isInvalid" in mutation
    assert updated.isInvalid is True
