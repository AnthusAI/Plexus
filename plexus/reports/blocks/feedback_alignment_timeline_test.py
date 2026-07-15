from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.reports.blocks.feedback_scope_resolver import ResolvedScoreRef
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


def _score_ref(
    score_id: str,
    name: str,
    *,
    key: str | None = None,
    external_id: str | None = None,
) -> ResolvedScoreRef:
    return ResolvedScoreRef(id=score_id, name=name, key=key, external_id=external_id)


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
            "rolling_min_items": 1,
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
    assert output["fetched_feedback_items"] == 2
    assert output["ignored_invalid_feedback_items"] == 0
    assert output["analyzed_feedback_items"] == 2
    assert output["show_bucket_details"] is False


@pytest.mark.asyncio
async def test_generate_exact_window_ignores_bucket_count_and_sets_show_details(mock_api_client):
    block = FeedbackAlignmentTimeline(
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
async def test_rolling_sample_uses_only_bucket_items_when_bucket_meets_minimum(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={
            "scorecard": "sc-1",
            "bucket_type": "calendar_day",
            "bucket_count": 1,
            "rolling_min_items": 2,
            "timezone": "UTC",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    fixed_now = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)
    scorecard = MagicMock(id="sc-1", name="Test Scorecard")

    with (
        patch.object(block, "_now_utc", return_value=fixed_now),
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(
            block,
            "_fetch_feedback_items_for_score",
            new=AsyncMock(
                return_value=[
                    _make_feedback_item(
                        item_id="older",
                        initial="yes",
                        final="no",
                        edited_at=datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc),
                    ),
                    _make_feedback_item(
                        item_id="bucket-1",
                        initial="yes",
                        final="yes",
                        edited_at=datetime(2026, 4, 5, 7, 0, tzinfo=timezone.utc),
                    ),
                    _make_feedback_item(
                        item_id="bucket-2",
                        initial="no",
                        final="no",
                        edited_at=datetime(2026, 4, 5, 8, 0, tzinfo=timezone.utc),
                    ),
                ]
            ),
        ),
    ):
        output, _ = await block.generate()

    point = output["overall"]["points"][0]
    assert output["sample_policy"]["rolling_min_items"] == 2
    assert output["sample_policy"]["lookback"] == "unbounded"
    assert output["sample_policy"]["prediction_value"] == "FeedbackItem.initialAnswerValue"
    assert output["sample_policy"]["reference_value"] == "FeedbackItem.finalAnswerValue"
    assert point["bucket_item_count"] == 2
    assert point["sample_item_count"] == 2
    assert point["lookback_item_count"] == 0
    assert point["sample_extended"] is False
    assert point["sample_underfilled"] is False
    assert point["accuracy"] == 100.0


@pytest.mark.asyncio
async def test_rolling_sample_adds_older_items_when_bucket_is_sparse(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={
            "scorecard": "sc-1",
            "bucket_type": "calendar_day",
            "bucket_count": 1,
            "rolling_min_items": 3,
            "timezone": "UTC",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    fixed_now = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)
    scorecard = MagicMock(id="sc-1", name="Test Scorecard")

    with (
        patch.object(block, "_now_utc", return_value=fixed_now),
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(
            block,
            "_fetch_feedback_items_for_score",
            new=AsyncMock(
                return_value=[
                    _make_feedback_item(
                        item_id="older-1",
                        initial="yes",
                        final="yes",
                        edited_at=datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc),
                    ),
                    _make_feedback_item(
                        item_id="older-2",
                        initial="yes",
                        final="yes",
                        edited_at=datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc),
                    ),
                    _make_feedback_item(
                        item_id="bucket-1",
                        initial="yes",
                        final="no",
                        edited_at=datetime(2026, 4, 5, 7, 0, tzinfo=timezone.utc),
                    ),
                ]
            ),
        ),
    ):
        output, _ = await block.generate()

    point = output["overall"]["points"][0]
    assert point["bucket_item_count"] == 1
    assert point["sample_item_count"] == 3
    assert point["lookback_item_count"] == 2
    assert point["sample_extended"] is True
    assert point["sample_underfilled"] is False
    assert point["sample_start"].startswith("2026-04-02T12:00:00")
    assert point["sample_end"].startswith("2026-04-05T07:00:00")


@pytest.mark.asyncio
async def test_rolling_sample_marks_underfilled_when_not_enough_history_exists(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={
            "scorecard": "sc-1",
            "bucket_type": "calendar_day",
            "bucket_count": 1,
            "rolling_min_items": 3,
            "timezone": "UTC",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    fixed_now = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)
    scorecard = MagicMock(id="sc-1", name="Test Scorecard")

    with (
        patch.object(block, "_now_utc", return_value=fixed_now),
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch.object(
            block,
            "_resolve_scores_for_mode",
            new=AsyncMock(return_value=[{"score_id": "score-1", "score_name": "Score 1"}]),
        ),
        patch.object(
            block,
            "_fetch_feedback_items_for_score",
            new=AsyncMock(
                return_value=[
                    _make_feedback_item(
                        item_id="bucket-1",
                        initial="yes",
                        final="yes",
                        edited_at=datetime(2026, 4, 5, 7, 0, tzinfo=timezone.utc),
                    ),
                ]
            ),
        ),
    ):
        output, _ = await block.generate()

    point = output["overall"]["points"][0]
    assert point["bucket_item_count"] == 1
    assert point["sample_item_count"] == 1
    assert point["lookback_item_count"] == 0
    assert point["sample_extended"] is False
    assert point["sample_underfilled"] is True


@pytest.mark.asyncio
async def test_rolling_samples_are_independent_per_score(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={
            "scorecard": "sc-1",
            "bucket_type": "calendar_day",
            "bucket_count": 1,
            "rolling_min_items": 2,
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
                    item_id="s1-old",
                    initial="yes",
                    final="yes",
                    edited_at=datetime(2026, 4, 3, 7, 0, tzinfo=timezone.utc),
                ),
                _make_feedback_item(
                    item_id="s1-bucket",
                    initial="yes",
                    final="yes",
                    edited_at=datetime(2026, 4, 5, 7, 0, tzinfo=timezone.utc),
                ),
            ]
        return [
            _make_feedback_item(
                item_id="s2-bucket",
                initial="yes",
                final="no",
                edited_at=datetime(2026, 4, 5, 8, 0, tzinfo=timezone.utc),
            )
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

    score_1_point = output["scores"][0]["points"][0]
    score_2_point = output["scores"][1]["points"][0]
    overall_point = output["overall"]["points"][0]
    assert score_1_point["sample_item_count"] == 2
    assert score_1_point["lookback_item_count"] == 1
    assert score_2_point["sample_item_count"] == 1
    assert score_2_point["sample_underfilled"] is True
    assert overall_point["sample_item_count"] == 2


@pytest.mark.asyncio
async def test_generate_include_scores_filters_before_overall_calculation(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={
            "scorecard": "sc-1",
            "include_scores": ["Score 2"],
            "bucket_type": "calendar_day",
            "bucket_count": 1,
            "timezone": "UTC",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    fixed_now = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)
    scorecard = MagicMock(id="sc-1", name="Test Scorecard")
    fetch_mock = AsyncMock(
        return_value=[
            _make_feedback_item(
                item_id="fi-2",
                initial="yes",
                final="no",
                edited_at=datetime(2026, 4, 5, 7, 0, tzinfo=timezone.utc),
            )
        ]
    )

    with (
        patch.object(block, "_now_utc", return_value=fixed_now),
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch(
            "plexus.reports.blocks.feedback_alignment_timeline.list_scores_for_scorecard",
            new=AsyncMock(
                return_value=[
                    _score_ref("score-1", "Score 1"),
                    _score_ref("score-2", "Score 2"),
                ]
            ),
        ),
        patch.object(block, "_fetch_feedback_items_for_score", new=fetch_mock),
    ):
        output, _ = await block.generate()

    assert [score["score_id"] for score in output["scores"]] == ["score-2"]
    assert output["overall"]["points"][0]["item_count"] == 1
    assert output["overall"]["points"][0]["mismatches"] == 1
    assert output["score_filter"]["requested_include_scores"] == ["Score 2"]
    assert output["score_filter"]["resolved_included_scores"] == [
        {"score_id": "score-2", "score_name": "Score 2"}
    ]
    assert fetch_mock.await_args.kwargs["score_id"] == "score-2"


@pytest.mark.asyncio
async def test_generate_exclude_scores_filters_before_overall_calculation(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={
            "scorecard": "sc-1",
            "exclude_scores": ["Score 2"],
            "bucket_type": "calendar_day",
            "bucket_count": 1,
            "timezone": "UTC",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    fixed_now = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)
    scorecard = MagicMock(id="sc-1", name="Test Scorecard")
    fetch_mock = AsyncMock(
        return_value=[
            _make_feedback_item(
                item_id="fi-1",
                initial="yes",
                final="yes",
                edited_at=datetime(2026, 4, 5, 7, 0, tzinfo=timezone.utc),
            )
        ]
    )

    with (
        patch.object(block, "_now_utc", return_value=fixed_now),
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch(
            "plexus.reports.blocks.feedback_alignment_timeline.list_scores_for_scorecard",
            new=AsyncMock(
                return_value=[
                    _score_ref("score-1", "Score 1"),
                    _score_ref("score-2", "Score 2"),
                ]
            ),
        ),
        patch.object(block, "_fetch_feedback_items_for_score", new=fetch_mock),
    ):
        output, _ = await block.generate()

    assert [score["score_id"] for score in output["scores"]] == ["score-1"]
    assert output["overall"]["points"][0]["item_count"] == 1
    assert output["overall"]["points"][0]["accuracy"] == 100.0
    assert output["score_filter"]["requested_exclude_scores"] == ["Score 2"]
    assert output["score_filter"]["resolved_excluded_scores"] == [
        {"score_id": "score-2", "score_name": "Score 2"}
    ]
    assert fetch_mock.await_args.kwargs["score_id"] == "score-1"


@pytest.mark.asyncio
async def test_include_then_exclude_applies_filters_in_order(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={
            "scorecard": "sc-1",
            "include_scores": ["Score 1", "Score 2"],
            "exclude_scores": ["Score 1"],
            "bucket_type": "calendar_day",
            "bucket_count": 1,
            "timezone": "UTC",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    fixed_now = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)
    scorecard = MagicMock(id="sc-1", name="Test Scorecard")

    with (
        patch.object(block, "_now_utc", return_value=fixed_now),
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch(
            "plexus.reports.blocks.feedback_alignment_timeline.list_scores_for_scorecard",
            new=AsyncMock(
                return_value=[
                    _score_ref("score-1", "Score 1"),
                    _score_ref("score-2", "Score 2"),
                    _score_ref("score-3", "Score 3"),
                ]
            ),
        ),
        patch.object(block, "_fetch_feedback_items_for_score", new=AsyncMock(return_value=[])),
    ):
        output, _ = await block.generate()

    assert [score["score_id"] for score in output["scores"]] == ["score-2"]
    assert output["score_filter"]["resolved_included_scores"] == [
        {"score_id": "score-2", "score_name": "Score 2"}
    ]
    assert output["score_filter"]["resolved_excluded_scores"] == [
        {"score_id": "score-1", "score_name": "Score 1"}
    ]


@pytest.mark.asyncio
async def test_generate_unknown_score_filter_returns_clear_error_without_fetch(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={
            "scorecard": "sc-1",
            "include_scores": ["Missing Score"],
            "bucket_type": "calendar_day",
            "bucket_count": 1,
            "timezone": "UTC",
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    scorecard = MagicMock(id="sc-1", name="Test Scorecard")
    fetch_mock = AsyncMock(return_value=[])

    with (
        patch.object(block, "_resolve_scorecard", new=AsyncMock(return_value=scorecard)),
        patch(
            "plexus.reports.blocks.feedback_alignment_timeline.list_scores_for_scorecard",
            new=AsyncMock(return_value=[_score_ref("score-1", "Score 1")]),
        ),
        patch.object(block, "_fetch_feedback_items_for_score", new=fetch_mock),
    ):
        output, logs = await block.generate()

    assert logs is not None
    assert "error" in output
    assert "include_scores identifier 'Missing Score' did not match any score" in output["error"]
    fetch_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_rejects_single_score_with_score_filters(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={
            "scorecard": "sc-1",
            "score": "Score 1",
            "exclude_scores": ["Score 2"],
        },
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    output, _ = await block.generate()

    assert "error" in output
    assert "cannot be combined" in output["error"]


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
async def test_fetch_feedback_items_for_score_stores_invalid_filter_stats(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={"scorecard": "sc-1"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )
    expected_items = [_make_feedback_item(
        item_id="fi-1",
        initial="yes",
        final="no",
        edited_at=datetime(2026, 4, 5, 11, 0, tzinfo=timezone.utc),
    )]
    expected_stats = {"fetched_total": 3, "ignored_invalid": 2, "analyzed_total": 1}

    with patch(
        "plexus.reports.blocks.feedback_alignment_timeline.feedback_utils.fetch_feedback_items_for_score_with_stats",
        new=AsyncMock(return_value=(expected_items, expected_stats)),
    ):
        items = await block._fetch_feedback_items_for_score(
            scorecard_id="sc-1",
            score_id="score-1",
            start_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 4, 6, tzinfo=timezone.utc),
        )

    assert items == expected_items
    assert block._last_feedback_fetch_stats == expected_stats


@pytest.mark.asyncio
async def test_resolve_scores_for_mode_uuid_checks_section_scorecard_membership(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={"scorecard": "sc-1"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    with (
        patch(
            "plexus.reports.blocks.feedback_alignment_timeline.resolve_score_for_scorecard",
            new=AsyncMock(
                return_value=SimpleNamespace(id="score-1", name="Score 1")
            ),
        ),
    ):
        output = await block._resolve_scores_for_mode(
            scorecard_id="sc-1",
            score_identifier="123e4567-e89b-12d3-a456-426614174000",
        )

    assert output == [{"score_id": "score-1", "score_name": "Score 1"}]


@pytest.mark.asyncio
async def test_resolve_scorecard_accepts_hyphenated_name(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={"scorecard": "Example Scorecard"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    with (
        patch("plexus.reports.blocks.feedback_scope_resolver.Scorecard.get_by_key", return_value=None),
        patch(
            "plexus.reports.blocks.feedback_scope_resolver.Scorecard.get_by_name",
            return_value=SimpleNamespace(id="sc-1", name="Example Scorecard"),
        ),
        patch("plexus.reports.blocks.feedback_scope_resolver.Scorecard.get_by_external_id", return_value=None),
    ):
        resolved = await block._resolve_scorecard("Example Scorecard")

    assert resolved.id == "sc-1"
    assert resolved.name == "Example Scorecard"


@pytest.mark.asyncio
async def test_resolve_scores_for_mode_uuid_rejects_other_scorecard(mock_api_client):
    block = FeedbackAlignmentTimeline(
        config={"scorecard": "sc-1"},
        params={"account_id": "acct-1"},
        api_client=mock_api_client,
    )

    with patch(
        "plexus.reports.blocks.feedback_alignment_timeline.resolve_score_for_scorecard",
        new=AsyncMock(side_effect=ValueError("Score 'id' does not belong to scorecard 'sc-1'.")),
    ):
        with pytest.raises(ValueError, match="does not belong to scorecard"):
            await block._resolve_scores_for_mode(
                scorecard_id="sc-1",
                score_identifier="123e4567-e89b-12d3-a456-426614174000",
            )
