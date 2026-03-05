"""Tests for VectorTopicMemory ReportBlock."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from plexus.reports.blocks.vector_topic_memory import VectorTopicMemory


@pytest.fixture
def mock_api_client():
    return MagicMock()


@pytest.fixture
def vector_topic_memory_block(mock_api_client):
    return VectorTopicMemory(config={}, params={}, api_client=mock_api_client)


@pytest.mark.asyncio
async def test_vector_topic_memory_generate_returns_well_formed_tuple(vector_topic_memory_block):
    """generate() returns Tuple[Optional[Dict], Optional[str]]."""
    vector_topic_memory_block.config = {}  # No s3_vectors -> shell mode
    output_data, log_string = await vector_topic_memory_block.generate()

    assert output_data is not None
    assert isinstance(output_data, dict)
    assert output_data.get("type") == "VectorTopicMemory"
    assert output_data.get("status") in ("shell", "error", "ok")
    assert log_string is not None
    assert isinstance(log_string, str)


@pytest.mark.asyncio
async def test_vector_topic_memory_dataset_resolution_error_with_s3_defaults(
    vector_topic_memory_block,
):
    """Block returns dataset-resolution error even when relying on S3 defaults."""
    vector_topic_memory_block.config = {"data": {"dataset": "ds-1"}}
    with patch(
        "plexus.reports.blocks.vector_topic_memory.DatasetResolver"
    ) as mock_resolver:
        mock_resolver.return_value.resolve_and_cache_dataset = AsyncMock(
            return_value=(None, None)
        )
        output_data, _ = await vector_topic_memory_block.generate()
    assert output_data["status"] == "error"
    assert "Dataset resolution failed" in output_data.get("summary", "")


def test_vector_topic_memory_resolves_default_s3_vectors_from_environment(
    vector_topic_memory_block, monkeypatch
):
    """Defaults bucket/index from ENVIRONMENT when explicit values are missing."""
    monkeypatch.delenv("S3_VECTOR_BUCKET_NAME", raising=False)
    monkeypatch.delenv("S3_VECTOR_INDEX_NAME", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")

    vector_topic_memory_block.config = {"s3_vectors": {"region": "us-west-2"}}
    cfg = vector_topic_memory_block._resolve_s3_vectors_config()

    assert cfg["bucket_name"] == "plexus-vectors-development"
    assert cfg["index_name"] == "topic-memory-idx-development"
    assert cfg["region"] == "us-west-2"


@pytest.mark.asyncio
async def test_vector_topic_memory_error_when_no_data_config(vector_topic_memory_block):
    """Block returns error when data config missing."""
    vector_topic_memory_block.config = {
        "s3_vectors": {"bucket_name": "test-bucket", "index_name": "test-index", "region": "us-west-2"}
    }
    output_data, _ = await vector_topic_memory_block.generate()
    assert output_data["status"] == "error"
    assert "Missing data config" in output_data.get("summary", "")


@pytest.mark.asyncio
async def test_vector_topic_memory_is_base_report_block():
    """VectorTopicMemory subclasses BaseReportBlock."""
    from plexus.reports.blocks.base import BaseReportBlock

    assert issubclass(VectorTopicMemory, BaseReportBlock)


def test_vector_topic_memory_normal_prediction_score_result_filter(vector_topic_memory_block):
    """Normal-production filter accepts only prediction/completed/200/non-evaluation rows."""
    keep = {
        "type": "prediction",
        "status": "COMPLETED",
        "code": "200",
        "evaluationId": None,
    }
    drop_eval = {
        "type": "prediction",
        "status": "COMPLETED",
        "code": "200",
        "evaluationId": "eval-1",
    }
    drop_status = {
        "type": "prediction",
        "status": "RUNNING",
        "code": "200",
        "evaluationId": None,
    }

    assert vector_topic_memory_block._is_normal_prediction_score_result(keep) is True
    assert vector_topic_memory_block._is_normal_prediction_score_result(drop_eval) is False
    assert vector_topic_memory_block._is_normal_prediction_score_result(drop_status) is False


def test_vector_topic_memory_lifecycle_flags_new(vector_topic_memory_block):
    """new = short && !medium && !long."""
    end_date = datetime(2026, 3, 5, tzinfo=timezone.utc)
    timestamps = [
        datetime(2026, 3, 4, tzinfo=timezone.utc),
        datetime(2026, 2, 28, tzinfo=timezone.utc),
    ]

    flags = vector_topic_memory_block._derive_lifecycle_flags(timestamps, end_date)

    assert flags["has_short_term_memory"] is True
    assert flags["has_medium_term_memory"] is False
    assert flags["has_long_term_memory"] is False
    assert flags["is_new"] is True
    assert flags["is_trending"] is True
    assert flags["lifecycle_tier"] == "new"


def test_vector_topic_memory_lifecycle_flags_trending(vector_topic_memory_block):
    """trending = (short || medium) && !long."""
    end_date = datetime(2026, 3, 5, tzinfo=timezone.utc)
    timestamps = [
        datetime(2026, 3, 4, tzinfo=timezone.utc),
        datetime(2026, 2, 15, tzinfo=timezone.utc),
    ]

    flags = vector_topic_memory_block._derive_lifecycle_flags(timestamps, end_date)

    assert flags["has_short_term_memory"] is True
    assert flags["has_medium_term_memory"] is True
    assert flags["has_long_term_memory"] is False
    assert flags["is_new"] is False
    assert flags["is_trending"] is True
    assert flags["lifecycle_tier"] == "trending"


def test_vector_topic_memory_lifecycle_flags_established(vector_topic_memory_block):
    """Long-window presence marks topic as established."""
    end_date = datetime(2026, 3, 5, tzinfo=timezone.utc)
    timestamps = [
        datetime(2026, 3, 4, tzinfo=timezone.utc),
        datetime(2026, 1, 10, tzinfo=timezone.utc),
    ]

    flags = vector_topic_memory_block._derive_lifecycle_flags(timestamps, end_date)

    assert flags["has_short_term_memory"] is True
    assert flags["has_long_term_memory"] is True
    assert flags["is_new"] is False
    assert flags["is_trending"] is False
    assert flags["lifecycle_tier"] == "established"


def test_vector_topic_memory_resolve_effective_min_topic_size():
    """Effective min topic size scales to avoid over-fragmentation."""
    effective = VectorTopicMemory._resolve_effective_min_topic_size(
        item_count=1000,
        configured_min_topic_size=8,
        min_topic_fraction=0.01,
        target_max_topics_per_score=30,
    )
    # max(8, 10, ceil(1000/30)=34) => 34
    assert effective == 34


def test_vector_topic_memory_select_llm_label_topic_ids():
    """LLM labels are bounded by size threshold and max label budget."""
    selected = VectorTopicMemory._select_llm_label_topic_ids(
        cluster_member_counts={0: 50, 1: 20, 2: 11, 3: 5, 4: 2},
        max_topics_to_label=2,
        label_min_member_count=10,
    )
    assert selected == {0, 1}


def test_vector_topic_memory_fallback_topic_label():
    """Fallback label uses top keywords when LLM labels are disabled/skipped."""
    label = VectorTopicMemory._fallback_topic_label(
        keywords=["shipping address", "confirmation issue", "patient details"],
        cluster_id=7,
    )
    assert label == "shipping address / confirmation issue"


@pytest.mark.asyncio
async def test_vector_topic_memory_resolves_score_result_no_explanation_source(
    vector_topic_memory_block,
):
    """content_source=score_result_no_explanation uses only normal 'No' ScoreResult explanations."""
    vector_topic_memory_block.config = {"data": {"content_source": "score_result_no_explanation"}}
    vector_topic_memory_block.params = {"account_id": "acct-1"}

    scorecard = MagicMock()
    scorecard.id = "scorecard-1"
    scorecard.name = "Test Scorecard"

    with patch(
        "plexus.dashboard.api.models.scorecard.Scorecard.get_by_external_id",
        return_value=scorecard,
    ), patch(
        "plexus.reports.blocks.feedback_utils.fetch_scores_for_scorecard",
        new=AsyncMock(
            return_value=[
                {
                    "plexus_score_id": "score-1",
                    "plexus_score_name": "Program Match",
                    "cc_question_id": "44245",
                }
            ]
        ),
    ), patch(
        "plexus.reports.blocks.feedback_utils.fetch_score_results_for_score",
        new=AsyncMock(
            return_value=[
                {
                    "id": "sr-keep",
                    "value": "No",
                    "explanation": "Retain this explanation.",
                    "type": "prediction",
                    "status": "COMPLETED",
                    "code": "200",
                    "evaluationId": None,
                    "updatedAt": "2026-03-04T19:00:00Z",
                },
                {
                    "id": "sr-skip-value",
                    "value": "Yes",
                    "explanation": "Do not keep.",
                    "type": "prediction",
                    "status": "COMPLETED",
                    "code": "200",
                    "evaluationId": None,
                    "updatedAt": "2026-03-04T19:00:00Z",
                },
                {
                    "id": "sr-skip-eval",
                    "value": "No",
                    "explanation": "Do not keep.",
                    "type": "prediction",
                    "status": "COMPLETED",
                    "code": "200",
                    "evaluationId": "eval-1",
                    "updatedAt": "2026-03-04T19:00:00Z",
                },
                {
                    "id": "sr-skip-empty",
                    "value": "No",
                    "explanation": "",
                    "type": "prediction",
                    "status": "COMPLETED",
                    "code": "200",
                    "evaluationId": None,
                    "updatedAt": "2026-03-04T19:00:00Z",
                },
            ]
        ),
    ):
        datasets = await vector_topic_memory_block._resolve_feedback_datasets("97", 14)

    assert len(datasets) == 1
    assert datasets[0]["score_id"] == "44245"
    assert datasets[0]["texts"] == ["Retain this explanation."]
    assert datasets[0]["doc_ids"] == ["sr-keep"]
    assert datasets[0]["timestamps"] == [datetime(2026, 3, 4, 19, 0, tzinfo=timezone.utc)]
