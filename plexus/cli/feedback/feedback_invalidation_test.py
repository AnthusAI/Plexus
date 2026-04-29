from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from plexus.cli.feedback.commands import feedback
from plexus.cli.feedback.feedback_invalidation import (
    FeedbackInvalidationError,
    invalidate_feedback_item,
    list_invalid_feedback_items_for_score,
    reinstate_feedback_item,
    reinstate_invalid_feedback_items_for_score,
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


def test_reinstate_feedback_item_by_direct_feedback_id():
    client = Mock()
    existing = _feedback_item("feedback-123", is_invalid=True)
    updated = _feedback_item("feedback-123", is_invalid=False)

    with patch(
        "plexus.cli.feedback.feedback_invalidation.FeedbackItem.get",
        return_value=existing,
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.FeedbackItem.reinstate",
        return_value=updated,
    ):
        result = reinstate_feedback_item(client=client, identifier="feedback-123")

    assert result["status"] == "reinstated"
    assert result["updated"] is True
    assert result["resolution"]["method"] == "feedback_item_id"
    assert result["feedback_item"]["id"] == "feedback-123"
    assert result["feedback_item"]["is_invalid"] is False


def test_reinstate_feedback_item_already_valid_is_noop():
    client = Mock()
    existing = _feedback_item("feedback-123", is_invalid=False)

    with patch(
        "plexus.cli.feedback.feedback_invalidation.FeedbackItem.get",
        return_value=existing,
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.FeedbackItem.reinstate",
    ) as reinstate_mock:
        result = reinstate_feedback_item(client=client, identifier="feedback-123")

    reinstate_mock.assert_not_called()
    assert result["status"] == "already_valid"
    assert result["updated"] is False


def test_list_invalid_feedback_items_for_score_filters_invalid_rows():
    client = Mock()
    client.execute.return_value = {
        "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt": {
            "items": [
                {
                    "id": "feedback-1",
                    "accountId": "account-1",
                    "scorecardId": "scorecard-1",
                    "scoreId": "score-1",
                    "itemId": "item-1",
                    "cacheKey": "score-1:item-1",
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
                },
                {
                    "id": "feedback-2",
                    "accountId": "account-1",
                    "scorecardId": "scorecard-1",
                    "scoreId": "score-1",
                    "itemId": "item-2",
                    "isInvalid": False,
                },
            ],
            "nextToken": None,
        }
    }

    with patch(
        "plexus.cli.feedback.feedback_invalidation.resolve_account_id_for_command",
        return_value="account-1",
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.resolve_scorecard_identifier",
        return_value="scorecard-1",
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.resolve_score_identifier",
        return_value="score-1",
    ):
        result = list_invalid_feedback_items_for_score(
            client=client,
            scorecard_identifier="Scorecard",
            score_identifier="Score",
        )

    variables = client.execute.call_args.kwargs["variables"]
    between = variables["composite_sk_condition"]["between"]
    assert between[0]["scorecardId"] == "scorecard-1"
    assert between[0]["scoreId"] == "score-1"
    assert result["count"] == 1
    assert result["feedback_items"][0]["id"] == "feedback-1"


def test_reinstate_invalid_feedback_items_for_score_dry_run_does_not_mutate():
    client = Mock()
    invalid_item = _feedback_item("feedback-1", is_invalid=True)

    with patch(
        "plexus.cli.feedback.feedback_invalidation.list_invalid_feedback_items_for_score",
        return_value={
            "scorecard_identifier": "Scorecard",
            "score_identifier": "Score",
            "account_id": "account-1",
            "scorecard_id": "scorecard-1",
            "score_id": "score-1",
            "count": 1,
            "feedback_items": [
                {
                    "id": invalid_item.id,
                    "item_id": invalid_item.itemId,
                    "is_invalid": True,
                }
            ],
        },
    ), patch(
        "plexus.cli.feedback.feedback_invalidation.reinstate_feedback_item",
    ) as reinstate_mock:
        result = reinstate_invalid_feedback_items_for_score(
            client=client,
            scorecard_identifier="Scorecard",
            score_identifier="Score",
            dry_run=True,
        )

    reinstate_mock.assert_not_called()
    assert result["status"] == "dry_run"
    assert result["inventory"]["count"] == 1


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


def test_feedback_uninvalidate_cli_command_displays_result():
    runner = CliRunner()
    result_payload = {
        "status": "reinstated",
        "updated": True,
        "already_invalid": True,
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
            "is_invalid": False,
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
        "plexus.cli.feedback.feedback_invalidation_command.reinstate_feedback_item",
        return_value=result_payload,
    ):
        result = runner.invoke(feedback, ["uninvalidate", "feedback-1"])

    assert result.exit_code == 0
    assert "Reinstated feedback item feedback-1" in result.output


def test_feedback_uninvalidate_all_for_score_requires_yes_when_executing():
    runner = CliRunner()
    result = runner.invoke(
        feedback,
        [
            "uninvalidate",
            "--all-for-score",
            "--scorecard",
            "Scorecard",
            "--score",
            "Score",
            "--execute",
        ],
    )

    assert result.exit_code != 0
    assert "--all-for-score --execute requires --yes" in result.output
