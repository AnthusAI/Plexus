from plexus.reports import service
from plexus.reports import blocks


def test_feedback_analysis_block_class_registered() -> None:
    assert "FeedbackAnalysis" in service.BLOCK_CLASSES
    assert service.BLOCK_CLASSES["FeedbackAnalysis"] is blocks.FeedbackAnalysis

