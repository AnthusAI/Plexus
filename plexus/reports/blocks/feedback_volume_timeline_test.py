from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.reports.blocks.feedback_volume_timeline import FeedbackVolumeTimeline


def _make_feedback_item(
    *,
    item_id: str,
    initial: str | None,
    final: str | None,
    edited_at: datetime,
    is_invalid: bool = False,
) -> FeedbackItem:
    item = MagicMock(spec=FeedbackItem)
    item.id = item_id
    item.initialAnswerValue = initial
    item.finalAnswerValue = final
    item.editedAt = edited_at
    item.updatedAt = None
    item.createdAt = None
    item.isInvalid = is_invalid
    return item


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.account_id = "acct-1"
    return client


@pytest.mark.asyncio
async def test_generate_single_score_mode_classifies_bucket_counts(mock_api_client):
    block = FeedbackVolumeTimeline(
        config={
            "scorecard": "sc-1",
            "score": "score-ext-1",
            "bucket_type": "calendar_day",
            "bucket_count": 2,
            "timezone": "UTC",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    fixed_now = datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc)
    scorecard = MagicMock(id="sc-1", name="Test Scorecard")
    score_items = [
        _make_feedback_item(
            item_id="fi-1",
            initial="yes",
            final="yes",
            edited_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
        ),
        _make_feedback_item(
            item_id="fi-2",
            initial="yes",
            final="no",
            edited_at=datetime(2026, 4, 5, 11, 0, tzinfo=timezone.utc),
        ),
        _make_feedback_item(
            item_id="fi-3",
            initial="yes",
            final=None,
            edited_at=datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc),
        ),
    ]

    with (
        patch.object(block, "_now_utc", return_value=fixed_now),
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(block, "_fetch_feedback_items_for_score", new=AsyncMock(return_value=score_items)),
    ):
        output, logs = await block.generate()

    assert logs is not None
    assert output["scope"] == "single_score"
    assert output["score_id"] == "score-1"
    assert output["score_name"] == "Score 1"
    assert output["show_bucket_details"] is False
    assert len(output["points"]) == 2
    assert output["points"][0]["feedback_items_total"] == 1
    assert output["points"][0]["feedback_items_unchanged"] == 1
    assert output["points"][1]["feedback_items_total"] == 2
    assert output["points"][1]["feedback_items_changed"] == 1
    assert output["points"][1]["feedback_items_invalid_or_unclassified"] == 1
    assert output["summary"]["feedback_items_total"] == 3
    assert output["summary"]["feedback_items_valid"] == 2


@pytest.mark.asyncio
async def test_generate_exact_window_ignores_bucket_count_and_sets_show_details(mock_api_client):
    block = FeedbackVolumeTimeline(
        config={
            "scorecard": "sc-1",
            "score": "score-ext-1",
            "start_date": "2026-04-01",
            "end_date": "2026-04-19",
            "bucket_type": "calendar_week",
            "bucket_count": 1,
            "timezone": "UTC",
            "show_bucket_details": True,
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    scorecard = MagicMock(id="sc-1", name="Test Scorecard")
    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(block, "_fetch_feedback_items_for_score", new=AsyncMock(return_value=[])),
    ):
        output, _ = await block.generate()

    assert output["show_bucket_details"] is True
    assert output["bucket_policy"]["window_mode"] == "exact_window"
    assert output["bucket_policy"]["bucket_count_ignored"] is True
    assert output["bucket_policy"]["bucket_count"] == 3
    assert output["date_range"]["start"].startswith("2026-04-01T00:00:00")
    assert output["date_range"]["end"].startswith("2026-04-19T23:59:59")


@pytest.mark.asyncio
async def test_generate_scorecard_scope_aggregates_scores(mock_api_client):
    block = FeedbackVolumeTimeline(
        config={
            "scorecard": "sc-1",
            "bucket_type": "calendar_day",
            "bucket_count": 2,
            "timezone": "UTC",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    fixed_now = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)
    scorecard = MagicMock(id="sc-1", name="Test Scorecard")

    def _fetch_side_effect(scorecard_id, score_id, start_date, end_date):
        if score_id == "score-1":
            return [
                _make_feedback_item(
                    item_id="fi-1",
                    initial="yes",
                    final="yes",
                    edited_at=datetime(2026, 4, 5, 7, 0, tzinfo=timezone.utc),
                )
            ]
        return [
            _make_feedback_item(
                item_id="fi-2",
                initial="yes",
                final="no",
                edited_at=datetime(2026, 4, 5, 8, 0, tzinfo=timezone.utc),
                is_invalid=True,
            ),
            _make_feedback_item(
                item_id="fi-3",
                initial="yes",
                final="no",
                edited_at=datetime(2026, 4, 5, 9, 0, tzinfo=timezone.utc),
            ),
        ]

    with (
        patch.object(block, "_now_utc", return_value=fixed_now),
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(
                return_value=[
                    {"score_id": "score-1", "score_name": "Score 1"},
                    {"score_id": "score-2", "score_name": "Score 2"},
                ]
            ),
        ),
        patch.object(
            block,
            "_fetch_feedback_items_for_score",
            new=AsyncMock(side_effect=_fetch_side_effect),
        ),
    ):
        output, _ = await block.generate()

    assert output["scope"] == "scorecard_all_scores"
    assert output["score_id"] is None
    assert output["score_name"] is None
    populated_bucket_point = output["points"][1]
    assert populated_bucket_point["feedback_items_total"] == 3
    assert populated_bucket_point["feedback_items_valid"] == 2
    assert populated_bucket_point["feedback_items_unchanged"] == 1
    assert populated_bucket_point["feedback_items_changed"] == 1
    assert populated_bucket_point["feedback_items_invalid_or_unclassified"] == 1
    assert output["summary"]["feedback_items_total"] == 3


@pytest.mark.asyncio
async def test_generate_with_invalid_bucket_type_returns_error(mock_api_client):
    block = FeedbackVolumeTimeline(
        config={
            "scorecard": "sc-1",
            "bucket_type": "invalid_policy",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    output, logs = await block.generate()

    assert logs is not None
    assert isinstance(output, dict)
    assert "error" in output
    assert "Unsupported bucket_type" in output["error"]
