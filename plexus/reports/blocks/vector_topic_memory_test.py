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
    vector_topic_memory_block.config = {}  # No opensearch -> shell mode
    output_data, log_string = await vector_topic_memory_block.generate()

    assert output_data is not None
    assert isinstance(output_data, dict)
    assert output_data.get("type") == "VectorTopicMemory"
    assert output_data.get("status") in ("shell", "error", "ok")
    assert log_string is not None
    assert isinstance(log_string, str)


@pytest.mark.asyncio
async def test_vector_topic_memory_shell_when_no_opensearch(vector_topic_memory_block):
    """Block returns shell status when OpenSearch not configured."""
    vector_topic_memory_block.config = {"data": {"dataset": "ds-1"}}
    with patch(
        "plexus.reports.blocks.vector_topic_memory.DatasetResolver"
    ) as mock_resolver:
        mock_resolver.return_value.resolve_and_cache_dataset = AsyncMock(
            return_value=(None, None)
        )
        output_data, _ = await vector_topic_memory_block.generate()
    assert output_data["status"] == "shell"


@pytest.mark.asyncio
async def test_vector_topic_memory_error_when_no_data_config(vector_topic_memory_block):
    """Block returns error when data config missing."""
    vector_topic_memory_block.config = {"opensearch": {"endpoint": "x", "region": "us-west-2"}}
    output_data, _ = await vector_topic_memory_block.generate()
    assert output_data["status"] == "error"
    assert "Missing data config" in output_data.get("summary", "")


@pytest.mark.asyncio
async def test_vector_topic_memory_is_base_report_block():
    """VectorTopicMemory subclasses BaseReportBlock."""
    from plexus.reports.blocks.base import BaseReportBlock

    assert issubclass(VectorTopicMemory, BaseReportBlock)
