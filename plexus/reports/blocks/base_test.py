import pytest
import asyncio
from unittest.mock import MagicMock, patch
from typing import Dict, Any, Optional, Tuple

from plexus.reports.blocks.base import BaseReportBlock


class TestReportBlock(BaseReportBlock):
    """Test implementation of BaseReportBlock for testing purposes."""
    
    def __init__(self, config: Dict[str, Any], params: Optional[Dict[str, Any]], api_client):
        super().__init__(config, params, api_client)
        self.generate_called = False
        self.generate_result = ({"test": "data"}, "test log")
        self.should_raise = False
        
    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Test implementation of generate method."""
        self.generate_called = True
        if self.should_raise:
            raise ValueError("Test error")
        return self.generate_result


@pytest.fixture
def mock_api_client():
    """Creates a mock API client."""
    client = MagicMock()
    client.account_id = "test-account-id"
    return client


@pytest.fixture
def test_config():
    """Test configuration dictionary."""
    return {
        "test_param": "test_value",
        "numeric_param": 42,
        "boolean_param": True
    }


@pytest.fixture
def test_params():
    """Test parameters dictionary."""
    return {
        "report_id": "test-report-123",
        "user_id": "test-user-456"
    }


class TestBaseReportBlock:
    """Tests for the BaseReportBlock class."""
    
    def test_init_with_all_params(self, mock_api_client, test_config, test_params):
        """Test initialization with all parameters."""
        block = TestReportBlock(test_config, test_params, mock_api_client)
        
        assert block.config == test_config
        assert block.params == test_params
        assert block.api_client == mock_api_client
        assert block.report_block_id is None
        assert block._orm is not None
        assert block.log_messages == block._orm.log_messages
        
    def test_init_with_none_params(self, mock_api_client, test_config):
        """Test initialization with None params."""
        block = TestReportBlock(test_config, None, mock_api_client)
        
        assert block.config == test_config
        assert block.params == {}
        assert block.api_client == mock_api_client
        
    def test_init_with_empty_params(self, mock_api_client, test_config):
        """Test initialization with empty params."""
        block = TestReportBlock(test_config, {}, mock_api_client)
        
        assert block.config == test_config
        assert block.params == {}
        assert block.api_client == mock_api_client
        
    def test_log_method(self, mock_api_client, test_config):
        """Test the _log method."""
        block = TestReportBlock(test_config, {}, mock_api_client)
        
        # Test basic logging
        block._log("Test message")
        assert len(block.log_messages) == 1
        assert "Test message" in block.log_messages[0]
        assert "[INFO]" in block.log_messages[0]
        
        # Test different log levels
        block._log("Warning message", "WARNING")
        assert len(block.log_messages) == 2
        assert "Warning message" in block.log_messages[1]
        assert "[WARNING]" in block.log_messages[1]
        
        block._log("Error message", "ERROR")
        assert len(block.log_messages) == 3
        assert "Error message" in block.log_messages[2]
        assert "[ERROR]" in block.log_messages[2]
        
    def test_log_console_only(self, mock_api_client, test_config):
        """Test logging with console_only flag."""
        block = TestReportBlock(test_config, {}, mock_api_client)
        
        # Console-only logs should not be stored in log_messages
        block._log("Console only message", console_only=True)
        assert len(block.log_messages) == 0
        
        # Regular logs should be stored
        block._log("Regular message")
        assert len(block.log_messages) == 1
        
    def test_log_with_report_block_id(self, mock_api_client, test_config):
        """Test logging when report_block_id is set."""
        block = TestReportBlock(test_config, {}, mock_api_client)
        block.report_block_id = "test-block-123"
        
        block._log("Test message with ID")
        assert len(block.log_messages) == 1
        assert "Test message with ID" in block.log_messages[0]
        
    def test_get_log_string(self, mock_api_client, test_config):
        """Test the _get_log_string method."""
        block = TestReportBlock(test_config, {}, mock_api_client)
        
        # Empty log string initially
        assert block._get_log_string() == ""
        
        # Add some log messages
        block._log("First message")
        block._log("Second message")
        
        log_string = block._get_log_string()
        assert "First message" in log_string
        assert "Second message" in log_string
        assert log_string.count("\n") == 1  # Two messages separated by newline
        
    @patch('plexus.reports.s3_utils.add_file_to_report_block')
    def test_attach_detail_file(self, mock_add_file, mock_api_client, test_config):
        """Test the attach_detail_file method."""
        mock_add_file.return_value = "s3://bucket/path/to/file.txt"
        
        block = TestReportBlock(test_config, {}, mock_api_client)
        report_block_id = "test-block-123"
        file_name = "test_file.txt"
        content = b"test content"
        content_type = "text/plain"
        
        result = block.attach_detail_file(report_block_id, file_name, content, content_type)
        
        assert result == "s3://bucket/path/to/file.txt"
        mock_add_file.assert_called_once_with(
            report_block_id=report_block_id,
            file_name=file_name,
            content=content,
            content_type=content_type,
            client=mock_api_client
        )
        
    @pytest.mark.asyncio
    async def test_generate_abstract_method(self, mock_api_client, test_config):
        """Test that the generate method is properly implemented in subclass."""
        block = TestReportBlock(test_config, {}, mock_api_client)
        
        result = await block.generate()
        
        assert block.generate_called is True
        assert result == ({"test": "data"}, "test log")
        
    @pytest.mark.asyncio
    async def test_generate_with_error(self, mock_api_client, test_config):
        """Test generate method when it raises an error."""
        block = TestReportBlock(test_config, {}, mock_api_client)
        block.should_raise = True
        
        with pytest.raises(ValueError, match="Test error"):
            await block.generate()
            
    def test_default_class_attributes(self, mock_api_client, test_config):
        """Test default class attributes."""
        block = TestReportBlock(test_config, {}, mock_api_client)
        
        assert block.DEFAULT_NAME is None
        assert block.DEFAULT_DESCRIPTION is None
        
    def test_orm_integration(self, mock_api_client, test_config):
        """Test integration with ReportBlockORM."""
        block = TestReportBlock(test_config, {}, mock_api_client)
        
        # Test that ORM is properly initialized
        assert block._orm is not None
        assert block._orm.api_client == mock_api_client
        assert block._orm.config == test_config
        
        # Test that log_messages is shared
        assert block.log_messages is block._orm.log_messages
        
        # Test logging through ORM
        block._log("ORM test message")
        assert len(block._orm.log_messages) == 1
        assert "ORM test message" in block._orm.log_messages[0] 