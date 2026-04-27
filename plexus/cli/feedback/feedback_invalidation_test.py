from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from plexus.cli.feedback.commands import feedback
from plexus.cli.feedback.feedback_invalidation import (
    FeedbackInvalidationError,
    invalidate_feedback_item,
)


def _feedback_item(
    feedback_id: str,
    *,
    item_id: str = "item-1",
    scorecard_id: str = "scorecard-1",
    score_id: str = "score-1",
    is_invalid: bool = False,
):
    item = Mock()
    item.id = feedback_id
    item.accountId = "account-1"
    item.scorecardId = scorecard_id
    item.scoreId = score_id
    item.itemId = item_id
    item.cacheKey = f"{score_id}:{item_id}"
    item.initialAnswerValue = "Yes"
    item.finalAnswerValue = "No"
    item.initialCommentValue = "initial"
    item.finalCommentValue = "final"
    item.editCommentValue = "edit"
    item.isAgreement = False
    item.isInvalid = is_invalid
    item.editorName = "tester"
    item.editedAt = None
    item.createdAt = None
    item.updatedAt = None
    return item


def test_invalidate_feedback_item_by_direct_feedback_id():
    client = Mock()
    existing = _feedback_item("feedback-123", is_invalid=False)
    updated = _feedback_item("feedback-123", is_invalid=True)

    with patch(
        "plexus.cli.feedback.feedback_invalidation.FeedbackItem.get",
        return_value=existing,
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.FeedbackItem.invalidate",
        return_value=updated,
    ):
        result = invalidate_feedback_item(client=client, identifier="feedback-123")

    assert result["status"] == "invalidated"
    assert result["updated"] is True
    assert result["resolution"]["method"] == "feedback_item_id"
    assert result["feedback_item"]["id"] == "feedback-123"
    assert result["feedback_item"]["is_invalid"] is True


def test_invalidate_feedback_item_requires_disambiguation_for_multiple_feedback_items():
    client = Mock()
    first = _feedback_item("feedback-1", scorecard_id="scorecard-a", score_id="score-a")
    second = _feedback_item("feedback-2", scorecard_id="scorecard-b", score_id="score-b")

    with patch(
        "plexus.cli.feedback.feedback_invalidation.FeedbackItem.get",
        return_value=None,
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.resolve_account_id_for_command",
        return_value="account-1",
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.resolve_item_reference",
        return_value=("item-1", "identifier_value"),
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.FeedbackItem.list",
        side_effect=[([first, second], None)],
    ):
        with pytest.raises(FeedbackInvalidationError) as excinfo:
            invalidate_feedback_item(client=client, identifier="CUSTOMER-42")

    assert excinfo.value.code == "ambiguous_feedback_items"
    assert len(excinfo.value.details["candidates"]) == 2
    assert "Re-run with --scorecard <scorecardId> and --score <scoreId>" in str(excinfo.value)


def test_invalidate_feedback_item_filters_by_scorecard_and_score():
    client = Mock()
    first = _feedback_item("feedback-1", scorecard_id="scorecard-a", score_id="score-a")
    second = _feedback_item("feedback-2", scorecard_id="scorecard-b", score_id="score-b")
    updated = _feedback_item(
        "feedback-1",
        scorecard_id="scorecard-a",
        score_id="score-a",
        is_invalid=True,
    )

    with patch(
        "plexus.cli.feedback.feedback_invalidation.FeedbackItem.get",
        return_value=None,
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.resolve_account_id_for_command",
        return_value="account-1",
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.resolve_item_reference",
        return_value=("item-1", "external_id"),
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.FeedbackItem.list",
        side_effect=[([first, second], None)],
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.resolve_scorecard_identifier",
        return_value="scorecard-a",
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.resolve_score_identifier",
        return_value="score-a",
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.FeedbackItem.invalidate",
        return_value=updated,
    ) as invalidate_mock:
        result = invalidate_feedback_item(
            client=client,
            identifier="CUSTOMER-42",
            scorecard_identifier="Test Scorecard",
            score_identifier="Eligibility",
        )

    invalidate_mock.assert_called_once_with(client, "feedback-1")
    assert result["feedback_item"]["id"] == "feedback-1"
    assert result["resolution"]["scorecard_filter"] == "scorecard-a"
    assert result["resolution"]["score_filter"] == "score-a"


def test_feedback_invalidate_cli_command_displays_result():
    runner = CliRunner()
    result_payload = {
        "status": "invalidated",
        "updated": True,
        "already_invalid": False,
        "resolution": {
            "requested_identifier": "feedback-1",
            "method": "feedback_item_id",
            "resolved_item_id": "item-1",
            "scorecard_filter": None,
            "score_filter": None,
        },
        "feedback_item": {
            "id": "feedback-1",
            "account_id": "account-1",
            "scorecard_id": "scorecard-1",
            "score_id": "score-1",
            "item_id": "item-1",
            "cache_key": "score-1:item-1",
            "initial_answer_value": "Yes",
            "final_answer_value": "No",
            "initial_comment_value": None,
            "final_comment_value": None,
            "edit_comment_value": None,
            "is_agreement": False,
            "is_invalid": True,
            "editor_name": None,
            "edited_at": None,
            "created_at": None,
            "updated_at": None,
        },
    }

    with patch(
        "plexus.cli.feedback.feedback_invalidation_command.create_client",
        return_value=Mock(),
    ), patch(
        "plexus.cli.feedback.feedback_invalidation_command.invalidate_feedback_item",
        return_value=result_payload,
    ):
        result = runner.invoke(feedback, ["invalidate", "feedback-1"])

    assert result.exit_code == 0
    assert "Invalidated feedback item feedback-1" in result.output
    assert "Feedback Item ID" in result.output
    assert "score-1:item-1" in result.output
