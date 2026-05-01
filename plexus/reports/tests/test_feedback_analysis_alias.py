from plexus.reports import service
from plexus.reports import blocks
from unittest.mock import patch
import pytest


def test_feedback_analysis_block_class_registered() -> None:
    assert "FeedbackAnalysis" in service.BLOCK_CLASSES
    assert service.BLOCK_CLASSES["FeedbackAnalysis"] is blocks.FeedbackAnalysis


@pytest.mark.asyncio
async def test_feedback_analysis_defaults_memory_analysis_disabled() -> None:
    instance = blocks.FeedbackAnalysis(config={"scorecard": "1481"}, params={}, api_client=None)

    async def _fake_generate(self):
        return {"ok": True}, "log"

    with patch.object(blocks.FeedbackAlignment, "generate", _fake_generate):
        output, _log = await instance.generate()

    assert output == {"ok": True}
    assert instance.config["memory_analysis"] is False


@pytest.mark.asyncio
async def test_feedback_analysis_preserves_explicit_memory_analysis_setting() -> None:
    instance = blocks.FeedbackAnalysis(
        config={"scorecard": "1481", "memory_analysis": True},
        params={},
        api_client=None,
    )

    async def _fake_generate(self):
        return {"ok": True}, "log"

    with patch.object(blocks.FeedbackAlignment, "generate", _fake_generate):
        output, _log = await instance.generate()

    assert output == {"ok": True}
    assert instance.config["memory_analysis"] is True
