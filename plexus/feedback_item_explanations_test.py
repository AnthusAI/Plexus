from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from plexus.feedback_item_explanations import (
    EXPLANATION_CACHE_METADATA_KEY,
    get_or_generate_feedback_item_explanation,
    hydrate_feedback_item_explanations,
)


@pytest.mark.asyncio
async def test_get_or_generate_feedback_item_explanation_uses_cache_hit():
    cached_entry = {
        "provider": "heuristic",
        "model": "feedback-item-explainer-v1",
        "ground_truth_value": "Yes",
        "explanation": "Cached explanation text.",
        "generated_at": "2026-05-01T00:00:00+00:00",
    }
    item = SimpleNamespace(
        id="fi-1",
        itemId="item-1",
        initialAnswerValue="No",
        finalAnswerValue="Yes",
        editCommentValue="",
        initialCommentValue="",
        finalCommentValue="",
        metadata={
            EXPLANATION_CACHE_METADATA_KEY: {
                "entries": {
                    "heuristic::feedback-item-explainer-v1": cached_entry,
                }
            }
        },
    )

    result = await get_or_generate_feedback_item_explanation(
        feedback_item=item,
        api_client=None,
        predicted_value="No",
        correct_value="Yes",
        score_explanation="",
        original_explanation="",
        score_guidelines_text="",
        scorecard_guidance_text="",
        transcript_text="",
        item_metadata_snapshot="",
        initial_comment="",
        final_comment="",
        provider="heuristic",
        model="feedback-item-explainer-v1",
    )

    assert result["cache_hit"] is True
    assert result["explanation"] == "Cached explanation text."
    assert result["ground_truth_value"] == "Yes"


@pytest.mark.asyncio
async def test_get_or_generate_feedback_item_explanation_persists_generated_entry():
    item = SimpleNamespace(
        id="fi-2",
        itemId="item-2",
        initialAnswerValue="No",
        finalAnswerValue="Yes",
        editCommentValue="Reviewer says this should be yes.",
        initialCommentValue="",
        finalCommentValue="",
        metadata={},
    )
    mock_client = Mock()

    with patch(
        "plexus.dashboard.api.models.feedback_item.FeedbackItem._update_feedback_item",
        return_value=SimpleNamespace(id="fi-2", metadata=item.metadata),
    ) as mock_update:
        result = await get_or_generate_feedback_item_explanation(
            feedback_item=item,
            api_client=mock_client,
            predicted_value="No",
            correct_value="Yes",
            score_explanation="",
            original_explanation="",
            score_guidelines_text="Guidelines",
            scorecard_guidance_text="",
            transcript_text="",
            item_metadata_snapshot="",
            initial_comment="",
            final_comment="",
            provider="heuristic",
            model="feedback-item-explainer-v1",
        )

    assert result["cache_hit"] is False
    assert result["explanation"]
    persisted_metadata = mock_update.call_args.args[2]["metadata"]
    assert persisted_metadata[EXPLANATION_CACHE_METADATA_KEY]["entries"][
        "heuristic::feedback-item-explainer-v1"
    ]["explanation"] == result["explanation"]
    assert mock_update.call_count == 1


@pytest.mark.asyncio
async def test_hydrate_feedback_item_explanations_only_generates_missing():
    cached_item = SimpleNamespace(
        id="fi-cached",
        itemId="item-cached",
        initialAnswerValue="No",
        finalAnswerValue="Yes",
        editCommentValue="",
        initialCommentValue="",
        finalCommentValue="",
        metadata={
            EXPLANATION_CACHE_METADATA_KEY: {
                "entries": {
                    "heuristic::feedback-item-explainer-v1": {
                        "provider": "heuristic",
                        "model": "feedback-item-explainer-v1",
                        "ground_truth_value": "Yes",
                        "explanation": "Already cached",
                        "generated_at": "2026-05-01T00:00:00+00:00",
                    }
                }
            }
        },
    )
    uncached_item = SimpleNamespace(
        id="fi-new",
        itemId="item-new",
        initialAnswerValue="No",
        finalAnswerValue="Yes",
        editCommentValue="Needs correction",
        initialCommentValue="",
        finalCommentValue="",
        metadata={},
    )

    with patch(
        "plexus.dashboard.api.models.feedback_item.FeedbackItem._update_feedback_item",
        side_effect=lambda _client, _id, feedback_data: SimpleNamespace(id=_id, metadata=feedback_data["metadata"]),
    ) as mock_update:
        result = await hydrate_feedback_item_explanations(
            feedback_items=[cached_item, uncached_item],
            api_client=Mock(),
            score_results_by_item_id={
                "item-cached": {"value": "No", "human_label": "Yes", "explanation": ""},
                "item-new": {"value": "No", "human_label": "Yes", "explanation": ""},
            },
            provider="heuristic",
            model="feedback-item-explainer-v1",
            max_concurrent=2,
        )

    assert set(result.keys()) == {"fi-cached", "fi-new"}
    assert result["fi-cached"]["cache_hit"] is True
    assert result["fi-new"]["cache_hit"] is False
    assert mock_update.call_count == 1
