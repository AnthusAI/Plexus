"""Tests for VectorTopicMemory ReportBlock."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

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
