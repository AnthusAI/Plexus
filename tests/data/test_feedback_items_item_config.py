import pytest
from types import SimpleNamespace
from datetime import datetime

from plexus.data.FeedbackItems import FeedbackItems


def test_feedback_items_requires_item_when_item_config_present():
    feedback_items = FeedbackItems.__new__(FeedbackItems)
    feedback_items.parameters = SimpleNamespace(
        item_config={"class": "DeepgramInputSource", "options": {"pattern": ".*deepgram.*\\.json$"}},
        column_mappings=None,
    )
    feedback_items.identifier_extractor = None

    feedback_item = SimpleNamespace(
        itemId="item-123",
        id="feedback-123",
        scorecardId="scorecard-1",
        scoreId="score-1",
        accountId="account-1",
        createdAt=datetime.utcnow(),
        updatedAt=datetime.utcnow(),
        editedAt=None,
        editorName=None,
        isAgreement=False,
        cacheKey="cache-1",
        initialAnswerValue="no",
        initialCommentValue="",
        finalAnswerValue="no",
        finalCommentValue="",
        editCommentValue="",
        item=None,
    )

    with pytest.raises(ValueError, match="Item is required"):
        feedback_items._create_dataset_rows([feedback_item], "Test Score")


def test_feedback_items_does_not_fallback_when_item_config_fails():
    feedback_items = FeedbackItems.__new__(FeedbackItems)
    feedback_items.parameters = SimpleNamespace(
        item_config={"class": "DeepgramInputSource", "options": {"pattern": ".*deepgram.*\\.json$"}},
        column_mappings=None,
    )
    feedback_items.identifier_extractor = None

    failing_item = SimpleNamespace(
        id="item-123",
        to_score_input=lambda item_config: (_ for _ in ()).throw(ValueError("No Deepgram file")),
    )

    feedback_item = SimpleNamespace(
        itemId="item-123",
        id="feedback-123",
        scorecardId="scorecard-1",
        scoreId="score-1",
        accountId="account-1",
        createdAt=datetime.utcnow(),
        updatedAt=datetime.utcnow(),
        editedAt=None,
        editorName=None,
        isAgreement=False,
        cacheKey="cache-1",
        initialAnswerValue="no",
        initialCommentValue="",
        finalAnswerValue="no",
        finalCommentValue="",
        editCommentValue="",
        item=failing_item,
    )

    with pytest.raises(ValueError, match="No Deepgram file"):
        feedback_items._create_dataset_rows([feedback_item], "Test Score")
