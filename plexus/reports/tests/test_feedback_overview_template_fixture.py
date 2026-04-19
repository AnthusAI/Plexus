from pathlib import Path

from plexus.reports.parameter_utils import render_configuration_with_parameters
from plexus.reports.service import _parse_report_configuration


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "reports" / "feedback_score_overview_template.md"


def test_feedback_overview_template_days_window_renders_three_blocks_with_shared_scope() -> None:
    template = FIXTURE_PATH.read_text()
    rendered = render_configuration_with_parameters(
        template,
        {
            "scorecard": "1438",
            "score": "45813",
            "days": 90,
            "start_date": "",
            "end_date": "",
            "bucket_type": "trailing_7d",
            "timezone": "UTC",
            "week_start": "monday",
            "show_bucket_details": False,
            "max_items": 200,
            "mode": "contradictions",
            "max_feedback_items": 400,
            "num_topics": 8,
            "max_concurrent": 20,
        },
    )

    blocks = _parse_report_configuration(rendered)
    assert [block["class_name"] for block in blocks] == [
        "FeedbackAlignmentTimeline",
        "AcceptanceRate",
        "FeedbackContradictions",
    ]

    for block in blocks:
        assert block["config"]["scorecard"] == 1438
        assert block["config"]["score"] == 45813
        assert block["config"]["days"] == 90
        assert "start_date" not in block["config"]
        assert "end_date" not in block["config"]


def test_feedback_overview_template_explicit_window_overrides_days() -> None:
    template = FIXTURE_PATH.read_text()
    rendered = render_configuration_with_parameters(
        template,
        {
            "scorecard": "1438",
            "score": "45813",
            "days": "",
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "bucket_type": "calendar_month",
            "timezone": "UTC",
            "week_start": "monday",
            "show_bucket_details": True,
            "max_items": 200,
            "mode": "contradictions",
            "max_feedback_items": 400,
            "num_topics": 8,
            "max_concurrent": 20,
        },
    )

    blocks = _parse_report_configuration(rendered)
    assert len(blocks) == 3

    for block in blocks:
        assert str(block["config"]["start_date"]) == "2026-01-01"
        assert str(block["config"]["end_date"]) == "2026-03-31"
        assert "days" not in block["config"]
