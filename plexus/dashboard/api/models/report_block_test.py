"""
Tests for ReportBlock model — focusing on the get_by_id classmethod.
"""

import pytest
from unittest.mock import Mock
from plexus.dashboard.api.models.report_block import ReportBlock


@pytest.fixture
def mock_client():
    return Mock()


@pytest.fixture
def sample_block_data():
    return {
        "id": "block-abc-123",
        "reportId": "report-xyz-456",
        "name": "block_0",
        "position": 0,
        "type": "FeedbackAlignment",
        "output": '{"status": "ok"}',
        "attachedFiles": ["reportblocks/block-abc-123/output.json"],
        "log": None,
    }


class TestReportBlockGetById:

    def test_returns_report_block_on_success(self, mock_client, sample_block_data):
        mock_client.execute.return_value = {"getReportBlock": sample_block_data}

        block = ReportBlock.get_by_id("block-abc-123", mock_client)

        assert block is not None
        assert block.id == "block-abc-123"
        assert block.reportId == "report-xyz-456"
        assert block.type == "FeedbackAlignment"

    def test_passes_correct_query_and_variables(self, mock_client, sample_block_data):
        mock_client.execute.return_value = {"getReportBlock": sample_block_data}

        ReportBlock.get_by_id("block-abc-123", mock_client)

        call_args = mock_client.execute.call_args
        query = call_args[0][0]
        variables = call_args[0][1]

        assert "getReportBlock" in query
        assert variables == {"id": "block-abc-123"}

    def test_returns_none_when_not_found(self, mock_client):
        mock_client.execute.return_value = {"getReportBlock": None}

        block = ReportBlock.get_by_id("nonexistent-id", mock_client)

        assert block is None

    def test_returns_none_on_api_exception(self, mock_client):
        mock_client.execute.side_effect = Exception("Network error")

        block = ReportBlock.get_by_id("block-abc-123", mock_client)

        assert block is None

    def test_returns_none_when_data_key_missing(self, mock_client):
        mock_client.execute.return_value = {}

        block = ReportBlock.get_by_id("block-abc-123", mock_client)

        assert block is None

    def test_report_id_is_accessible(self, mock_client, sample_block_data):
        """reportId field must be populated so ActionItems block can find its parent report."""
        mock_client.execute.return_value = {"getReportBlock": sample_block_data}

        block = ReportBlock.get_by_id("block-abc-123", mock_client)

        assert block.reportId == "report-xyz-456"
