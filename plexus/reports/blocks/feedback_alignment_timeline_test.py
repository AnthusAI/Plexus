from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.reports.blocks.feedback_alignment_timeline import FeedbackAlignmentTimeline


def _make_feedback_item(
    *,
    item_id: str,
    initial: str,
    final: str,
    edited_at: datetime,
) -> FeedbackItem:
    item = MagicMock(spec=FeedbackItem)
    item.id = item_id
    item.initialAnswerValue = initial
    item.finalAnswerValue = final
    item.editedAt = edited_at
    item.updatedAt = None
    item.createdAt = None
    return item


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.account_id = "acct-1"
    return client


def test_build_buckets_calendar_week_excludes_current_week(mock_api_client):
    block = FeedbackAlignmentTimeline(config={"scorecard": "sc-1"}, params={}, api_client=mock_api_client)

    now_local = datetime(2026, 4, 8, 12, 0, tzinfo=ZoneInfo("UTC"))
    buckets = block._build_buckets(
        now_local=now_local,
        bucket_type="calendar_week",
        bucket_count=2,
        week_start="monday",
    )

    assert len(buckets) == 2
    assert buckets[0].start_local == datetime(2026, 3, 23, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert buckets[0].end_local == datetime(2026, 3, 30, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert buckets[1].start_local == datetime(2026, 3, 30, 0, 0, tzinfo=ZoneInfo("UTC"))
    # Current week (starting 2026-04-06) is excluded, so last complete bucket ends at 2026-04-06.
    assert buckets[1].end_local == datetime(2026, 4, 6, 0, 0, tzinfo=ZoneInfo("UTC"))


@pytest.mark.asyncio
async def test_generate_single_score_mode(mock_api_client):
    block = FeedbackAlignmentTimeline(
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
    assert output["mode"] == "single_score"
    assert len(output["scores"]) == 1
    assert output["overall"]["score_id"] == "score-1"
    assert len(output["scores"][0]["points"]) == 2
    assert output["scores"][0]["points"][0]["item_count"] == 1
    assert output["scores"][0]["points"][1]["item_count"] == 1


@pytest.mark.asyncio
async def test_generate_all_scores_mode_keeps_empty_bucket_with_null_metrics(mock_api_client):
    block = FeedbackAlignmentTimeline(
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
        return []

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

    assert output["mode"] == "all_scores"
    assert len(output["scores"]) == 2
    assert len(output["overall"]["points"]) == 2

    empty_bucket_point = output["overall"]["points"][0]
    assert empty_bucket_point["item_count"] == 0
    assert empty_bucket_point["ac1"] is None
    assert empty_bucket_point["accuracy"] is None

    populated_bucket_point = output["overall"]["points"][1]
    assert populated_bucket_point["item_count"] == 1
    assert populated_bucket_point["ac1"] is not None
    assert populated_bucket_point["accuracy"] == 100.0


@pytest.mark.asyncio
async def test_generate_with_invalid_bucket_type_returns_error(mock_api_client):
    block = FeedbackAlignmentTimeline(
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


@pytest.mark.asyncio
async def test_generate_with_explicit_date_range_uses_requested_window(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={
            "scorecard": "sc-1",
            "bucket_type": "calendar_day",
            "bucket_count": 12,  # Explicit date windows should not rely on this value.
            "start_date": "2026-04-01",
            "end_date": "2026-04-02",
            "timezone": "UTC",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    scorecard = MagicMock(id="sc-1", name="Test Scorecard")
    score_items = [
        _make_feedback_item(
            item_id="fi-1",
            initial="yes",
            final="yes",
            edited_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        ),
        _make_feedback_item(
            item_id="fi-2",
            initial="yes",
            final="no",
            edited_at=datetime(2026, 4, 2, 11, 0, tzinfo=timezone.utc),
        ),
    ]

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(block, "_fetch_feedback_items_for_score", new=AsyncMock(return_value=score_items)) as fetch_mock,
    ):
        output, _ = await block.generate()

    assert output["bucket_policy"]["window_mode"] == "explicit_range"
    assert output["bucket_policy"]["complete_only"] is False
    assert output["bucket_policy"]["bucket_count"] == 2
    assert len(output["scores"][0]["points"]) == 2
    assert output["scores"][0]["points"][0]["item_count"] == 1
    assert output["scores"][0]["points"][1]["item_count"] == 1

    call_kwargs = fetch_mock.await_args.kwargs
    assert call_kwargs["start_date"] == datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
    assert call_kwargs["end_date"] == datetime(2026, 4, 2, 23, 59, 59, 999999, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_generate_with_days_window_uses_explicit_mode(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={
            "scorecard": "sc-1",
            "bucket_type": "calendar_day",
            "days": 2,
            "timezone": "UTC",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    fixed_now = datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc)
    scorecard = MagicMock(id="sc-1", name="Test Scorecard")

    with (
        patch.object(block, "_now_utc", return_value=fixed_now),
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(block, "_fetch_feedback_items_for_score", new=AsyncMock(return_value=[])),
    ):
        output, _ = await block.generate()

    assert output["bucket_policy"]["window_mode"] == "explicit_range"
    assert output["bucket_policy"]["complete_only"] is False
    assert output["bucket_policy"]["bucket_count"] == 3
    assert output["date_range"]["start"] == "2026-04-04T00:00:00+00:00"
    assert output["date_range"]["end"] == "2026-04-06T12:00:00+00:00"


@pytest.mark.asyncio
async def test_generate_with_partial_explicit_range_returns_error(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={
            "scorecard": "sc-1",
            "start_date": "2026-04-01",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    output, _ = await block.generate()

    assert "error" in output
    assert "Both 'start_date' and 'end_date'" in output["error"]


@pytest.mark.asyncio
async def test_resolve_scores_for_mode_uuid_checks_section_scorecard_membership(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={"scorecard": "sc-1"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    score = MagicMock()
    score.id = "score-1"
    score.name = "Score 1"
    score.sectionId = "section-1"

    with (
        patch(
            "plexus.reports.blocks.feedback_alignment_timeline.Score.get_by_id",
            return_value=score,
        ),
        patch.object(
            block,
            "_fetch_scorecard_id_for_section_id",
            new=AsyncMock(return_value="sc-1"),
        ),
    ):
        output = await block._resolve_scores_for_mode(
            scorecard_id="sc-1",
            score_identifier="123e4567-e89b-12d3-a456-426614174000",
        )

    assert output == [{"score_id": "score-1", "score_name": "Score 1"}]


@pytest.mark.asyncio
async def test_resolve_scores_for_mode_uuid_rejects_other_scorecard(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={"scorecard": "sc-1"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    score = MagicMock()
    score.id = "score-1"
    score.name = "Score 1"
    score.sectionId = "section-1"

    with (
        patch(
            "plexus.reports.blocks.feedback_alignment_timeline.Score.get_by_id",
            return_value=score,
        ),
        patch.object(
            block,
            "_fetch_scorecard_id_for_section_id",
            new=AsyncMock(return_value="sc-2"),
        ),
    ):
        with pytest.raises(ValueError, match="does not belong to scorecard"):
            await block._resolve_scores_for_mode(
                scorecard_id="sc-1",
                score_identifier="123e4567-e89b-12d3-a456-426614174000",
            )
