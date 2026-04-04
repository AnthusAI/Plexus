from types import SimpleNamespace

import pytest

from plexus.reports.blocks.guideline_vetting import GuidelineVettingService


@pytest.mark.asyncio
async def test_analyze_items_marks_unanimous_non_contradiction_as_reference_eligible():
    def bedrock_vote(_prompt: str, _use_thinking: bool = False):
        return {
            "contradicts": False,
            "category": None,
            "reason": "Aligned with guideline.",
            "guideline_quote": "Allows this behavior.",
        }

    def openai_vote(_prompt: str, _reasoning_effort: str = "low"):
        return {
            "contradicts": False,
            "category": None,
            "reason": "Consistent with policy.",
            "guideline_quote": "Allows this behavior.",
        }

    item = SimpleNamespace(
        id="fi-1",
        itemId="item-1",
        initialAnswerValue="No",
        finalAnswerValue="No",
        editCommentValue="Reviewer confirms no issue.",
        editorName="Reviewer",
        editedAt=None,
        isInvalid=False,
        item=None,
    )

    service = GuidelineVettingService(invoke_bedrock=bedrock_vote, invoke_openai=openai_vote)
    results = await service.analyze_items(
        items=[item],
        guidelines="Guideline text",
        max_concurrent=2,
        score_results_by_item={},
    )

    assert len(results) == 1
    result = results[0]
    assert result["verdict"] == "aligned"
    assert result["associated_dataset_eligible"] is True
    assert result["confidence"] == "high"


@pytest.mark.asyncio
async def test_analyze_items_marks_contradiction_as_not_reference_eligible():
    def bedrock_vote(_prompt: str, _use_thinking: bool = False):
        return {
            "contradicts": True,
            "category": "contradiction",
            "reason": "Violates explicit policy.",
            "guideline_quote": "Do not make this claim.",
        }

    def openai_vote(_prompt: str, _reasoning_effort: str = "low"):
        return {
            "contradicts": False,
            "category": None,
            "reason": "No violation.",
            "guideline_quote": "",
        }

    item = SimpleNamespace(
        id="fi-2",
        itemId="item-2",
        initialAnswerValue="No",
        finalAnswerValue="Yes",
        editCommentValue="Reviewer changed label.",
        editorName="Reviewer",
        editedAt=None,
        isInvalid=False,
        item=None,
    )

    service = GuidelineVettingService(invoke_bedrock=bedrock_vote, invoke_openai=openai_vote)
    results = await service.analyze_items(
        items=[item],
        guidelines="Guideline text",
        max_concurrent=2,
        score_results_by_item={},
    )

    assert len(results) == 1
    result = results[0]
    assert result["verdict"] == "contradiction"
    assert result["associated_dataset_eligible"] is False
