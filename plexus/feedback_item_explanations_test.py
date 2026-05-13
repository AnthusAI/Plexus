from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from plexus.feedback_item_explanations import (
    EXPLANATION_CACHE_METADATA_KEY,
    FeedbackItemExplanationTimeoutError,
    get_or_generate_feedback_item_explanation,
    hydrate_feedback_item_explanations,
)


@pytest.mark.asyncio
async def test_get_or_generate_feedback_item_explanation_uses_cache_hit():
    cached_entry = {
        "provider": "openai",
        "model": "gpt-5.4-mini",
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
                    "openai::gpt-5.4-mini": cached_entry,
                }
            }
        },
    )

    with patch(
        "plexus.feedback_item_explanations._invoke_openai_explanation_model",
        side_effect=AssertionError("cache hit must not invoke provider"),
    ):
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
            provider="openai",
            model="gpt-5.4-mini",
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
async def test_get_or_generate_feedback_item_explanation_retries_and_recovers(monkeypatch):
    item = SimpleNamespace(
        id="fi-openai-retry",
        itemId="item-openai-retry",
        initialAnswerValue="No",
        finalAnswerValue="Yes",
        editCommentValue="Reviewer says yes",
        initialCommentValue="",
        finalCommentValue="",
        metadata={},
    )
    mock_client = Mock()

    monkeypatch.setenv("PLEXUS_FEEDBACK_EXPLANATION_TOTAL_TIMEOUT_SECONDS", "0.5")
    monkeypatch.setenv("PLEXUS_FEEDBACK_EXPLANATION_ATTEMPT_TIMEOUT_SECONDS", "0.05")
    monkeypatch.setenv("PLEXUS_FEEDBACK_EXPLANATION_RETRY_INITIAL_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("PLEXUS_FEEDBACK_EXPLANATION_RETRY_MAX_BACKOFF_SECONDS", "0")

    side_effects = [
        TimeoutError("provider timeout"),
        {
            "ground_truth_value": "Yes",
            "explanation": "Recovered explanation.",
            "key_evidence": ["evidence-1"],
        },
    ]

    with patch(
        "plexus.feedback_item_explanations._invoke_openai_explanation_model",
        side_effect=side_effects,
    ) as mock_invoke:
        with patch(
            "plexus.dashboard.api.models.feedback_item.FeedbackItem._update_feedback_item",
            side_effect=lambda _client, _id, feedback_data: SimpleNamespace(
                id=_id,
                metadata=feedback_data["metadata"],
            ),
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
                provider="openai",
                model="gpt-5.4-mini",
            )

    assert result["cache_hit"] is False
    assert result["explanation"] == "Recovered explanation."
    assert mock_invoke.call_count == 2
    assert mock_update.call_count == 1


@pytest.mark.asyncio
async def test_get_or_generate_feedback_item_explanation_timeout_raises_typed_error(monkeypatch):
    item = SimpleNamespace(
        id="fi-openai-timeout",
        itemId="item-openai-timeout",
        initialAnswerValue="No",
        finalAnswerValue="Yes",
        editCommentValue="Needs correction",
        initialCommentValue="",
        finalCommentValue="",
        metadata={},
    )

    monkeypatch.setenv("PLEXUS_FEEDBACK_EXPLANATION_TOTAL_TIMEOUT_SECONDS", "0.05")
    monkeypatch.setenv("PLEXUS_FEEDBACK_EXPLANATION_ATTEMPT_TIMEOUT_SECONDS", "0.02")
    monkeypatch.setenv("PLEXUS_FEEDBACK_EXPLANATION_RETRY_INITIAL_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("PLEXUS_FEEDBACK_EXPLANATION_RETRY_MAX_BACKOFF_SECONDS", "0")

    with patch(
        "plexus.feedback_item_explanations._invoke_openai_explanation_model",
        side_effect=TimeoutError("provider timeout"),
    ):
        with pytest.raises(FeedbackItemExplanationTimeoutError) as exc_info:
            await get_or_generate_feedback_item_explanation(
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
                provider="openai",
                model="gpt-5.4-mini",
            )

    timeout_error = exc_info.value
    assert timeout_error.provider == "openai"
    assert timeout_error.model == "gpt-5.4-mini"
    assert timeout_error.attempt_count >= 1
    assert timeout_error.elapsed_seconds >= 0
    assert "timeout" in timeout_error.last_error_type.lower()


@pytest.mark.asyncio
async def test_provider_auto_does_not_fallback_to_heuristic_on_model_failure(monkeypatch):
    item = SimpleNamespace(
        id="fi-auto-failure",
        itemId="item-auto-failure",
        initialAnswerValue="No",
        finalAnswerValue="Yes",
        editCommentValue="",
        initialCommentValue="",
        finalCommentValue="",
        metadata={},
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("PLEXUS_FEEDBACK_EXPLANATION_TOTAL_TIMEOUT_SECONDS", "0.05")
    monkeypatch.setenv("PLEXUS_FEEDBACK_EXPLANATION_ATTEMPT_TIMEOUT_SECONDS", "0.02")
    monkeypatch.setenv("PLEXUS_FEEDBACK_EXPLANATION_RETRY_INITIAL_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("PLEXUS_FEEDBACK_EXPLANATION_RETRY_MAX_BACKOFF_SECONDS", "0")

    with patch(
        "plexus.feedback_item_explanations._invoke_openai_explanation_model",
        side_effect=TimeoutError("provider timeout"),
    ):
        with pytest.raises(FeedbackItemExplanationTimeoutError) as exc_info:
            await get_or_generate_feedback_item_explanation(
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
                provider="auto",
                model=None,
            )

    assert exc_info.value.provider == "openai"


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
