"""Tests for VectorTopicMemory ReportBlock."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone
from types import SimpleNamespace

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


def test_given_no_explicit_clustering_caps_when_resolving_controls_then_defaults_are_coarse():
    """Given no explicit min fraction/target max, when controls resolve, then coarse defaults are applied."""
    controls = VectorTopicMemory._resolve_clustering_controls({})

    assert controls["min_topic_fraction"] == pytest.approx(0.02)
    assert controls["target_max_topics_per_score"] == 12


def test_given_explicit_clustering_caps_when_resolving_controls_then_explicit_values_win():
    """Given explicit clustering controls, when controls resolve, then user settings are preserved."""
    controls = VectorTopicMemory._resolve_clustering_controls(
        {
            "min_topic_fraction": 0.01,
            "target_max_topics_per_score": 30,
            "coarse_min_topic_fraction": 0.05,
            "coarse_target_max_topics_per_score": 6,
        }
    )

    assert controls["min_topic_fraction"] == pytest.approx(0.01)
    assert controls["target_max_topics_per_score"] == 30


def test_given_many_documents_when_effective_min_topic_size_is_computed_then_result_is_coarser():
    """Given many docs, when coarse defaults are applied, then min_topic_size increases to reduce fragmentation."""
    controls = VectorTopicMemory._resolve_clustering_controls({})
    effective = VectorTopicMemory._resolve_effective_min_topic_size(
        item_count=600,
        configured_min_topic_size=8,
        min_topic_fraction=controls["min_topic_fraction"],
        target_max_topics_per_score=controls["target_max_topics_per_score"],
    )

    # max(8, ceil(600*0.02)=12, ceil(600/12)=50) => 50
    assert effective == 50


def test_given_topic_inputs_when_building_batch_prompt_then_prompt_enforces_distinct_names(
    vector_topic_memory_block,
):
    """Given bucket metadata, when prompt is built, then it explicitly requires nuanced distinct naming."""
    prompt_parts = vector_topic_memory_block._build_batch_topic_naming_prompt(
        [
            {
                "topic_key": "score-1::1",
                "cluster_id": 1,
                "score_name": "Program Match",
                "keywords": ["address", "confirm", "spelling"],
                "exemplars": ["I corrected the address verification section."],
            }
        ]
    )

    system_prompt = prompt_parts["system"]
    user_prompt = prompt_parts["user"]
    assert "distinct" in system_prompt.lower()
    assert "nuance" in system_prompt.lower()
    assert "topic_key" in user_prompt


def test_given_multiple_topics_when_batch_labeling_then_labels_are_resolved_in_one_call(
    vector_topic_memory_block,
):
    """Given many buckets, when batched naming runs, then one LLM call returns all labels."""
    topic_inputs = [
        {
            "topic_key": "score-1::1",
            "cluster_id": 1,
            "score_name": "Program Match",
            "keywords": ["address", "confirm", "spelling"],
            "exemplars": ["I corrected the address verification section."],
        },
        {
            "topic_key": "score-1::2",
            "cluster_id": 2,
            "score_name": "Program Match",
            "keywords": ["copay", "estimate", "benefits"],
            "exemplars": ["Rep did not explain the copay estimate clearly."],
        },
    ]

    vector_topic_memory_block._invoke_batch_topic_naming_llm = MagicMock(
        return_value="""[
            {"topic_key": "score-1::1", "label": "Address Confirmation Edits"},
            {"topic_key": "score-1::2", "label": "Copay Estimate Clarifications"}
        ]"""
    )

    labels = vector_topic_memory_block._generate_topic_labels_batch(
        topic_inputs=topic_inputs,
        model_name="gpt-4o",
        api_key="test-key",
    )

    assert vector_topic_memory_block._invoke_batch_topic_naming_llm.call_count == 1
    assert labels == {
        "score-1::1": "Address Confirmation Edits",
        "score-1::2": "Copay Estimate Clarifications",
    }


def test_given_batch_invoke_when_timeout_specified_then_chat_openai_receives_timeout(
    vector_topic_memory_block,
):
    """Given batch invoke timeout, when calling ChatOpenAI, then timeout is applied."""
    with patch("langchain_openai.ChatOpenAI") as mock_chat_openai:
        mock_chat_openai.return_value.invoke.return_value = SimpleNamespace(content="[]")
        vector_topic_memory_block._invoke_batch_topic_naming_llm(
            system_prompt="sys",
            user_prompt="usr",
            model_name="gpt-4o",
            api_key="k",
            timeout_seconds=17,
        )

    assert mock_chat_openai.call_count == 1
    assert mock_chat_openai.call_args.kwargs["timeout"] == 17


def test_given_single_label_invoke_when_timeout_specified_then_chat_openai_receives_timeout(
    vector_topic_memory_block,
):
    """Given per-topic timeout, when calling ChatOpenAI, then timeout is applied."""
    with patch("langchain_openai.ChatOpenAI") as mock_chat_openai:
        vector_topic_memory_block._generate_topic_label(
            keywords=["one", "two"],
            exemplars=["example"],
            model_name="gpt-4o-mini",
            api_key="k",
            timeout_seconds=11,
        )

    assert mock_chat_openai.call_count == 1
    assert mock_chat_openai.call_args.kwargs["timeout"] == 11


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
