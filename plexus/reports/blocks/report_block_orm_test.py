import pytest
import logging
from unittest.mock import MagicMock, patch
from typing import Dict, Any, Optional

from plexus.reports.blocks.report_block_orm import ReportBlockORM


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


class TestReportBlockORM:
    """Tests for the ReportBlockORM class."""
    
    def test_init_with_all_params(self, mock_api_client, test_config):
        """Test initialization with all parameters."""
        report_block_id = "test-block-123"
        orm = ReportBlockORM(mock_api_client, report_block_id, test_config)
        
        assert orm.api_client == mock_api_client
        assert orm.report_block_id == report_block_id
        assert orm.config == test_config
        assert orm.log_messages == []
        assert orm.attached_files == []
        assert orm.logger is not None
        
    def test_init_with_minimal_params(self, mock_api_client):
        """Test initialization with minimal parameters."""
        orm = ReportBlockORM(mock_api_client)
        
        assert orm.api_client == mock_api_client
        assert orm.report_block_id is None
        assert orm.config == {}
        assert orm.log_messages == []
        assert orm.attached_files == []
        
    def test_init_with_none_config(self, mock_api_client):
        """Test initialization with None config."""
        orm = ReportBlockORM(mock_api_client, None, None)
        
        assert orm.config == {}
        
    def test_log_method_basic(self, mock_api_client, test_config):
        """Test basic logging functionality."""
        orm = ReportBlockORM(mock_api_client, "test-block-123", test_config)
        
        orm.log("Test message")
        
        assert len(orm.log_messages) == 1
        assert "Test message" in orm.log_messages[0]
        assert "[INFO]" in orm.log_messages[0]
        
    def test_log_method_different_levels(self, mock_api_client, test_config):
        """Test logging with different levels."""
        orm = ReportBlockORM(mock_api_client, "test-block-123", test_config)
        
        orm.log("Info message", "INFO")
        orm.log("Warning message", "WARNING")
        orm.log("Error message", "ERROR")
        
        assert len(orm.log_messages) == 3
        assert "[INFO]" in orm.log_messages[0]
        assert "[WARNING]" in orm.log_messages[1]
        assert "[ERROR]" in orm.log_messages[2]
        
    def test_log_method_console_only(self, mock_api_client, test_config):
        """Test logging with console_only flag."""
        orm = ReportBlockORM(mock_api_client, "test-block-123", test_config)
        
        # Console-only logs should not be stored
        orm.log("Console only message", console_only=True)
        assert len(orm.log_messages) == 0
        
        # Regular logs should be stored
        orm.log("Regular message")
        assert len(orm.log_messages) == 1
        
    def test_log_method_debug_level(self, mock_api_client, test_config):
        """Test that DEBUG logs are not stored in attached log."""
        orm = ReportBlockORM(mock_api_client, "test-block-123", test_config)
        
        orm.log("Debug message", "DEBUG")
        assert len(orm.log_messages) == 0  # DEBUG logs not stored
        
        orm.log("Info message", "INFO")
        assert len(orm.log_messages) == 1  # INFO logs are stored
        
    def test_log_convenience_methods(self, mock_api_client, test_config):
        """Test convenience logging methods."""
        orm = ReportBlockORM(mock_api_client, "test-block-123", test_config)
        
        orm.log_debug("Debug message")
        orm.log_info("Info message")
        orm.log_warning("Warning message")
        orm.log_error("Error message")
        
        # Only non-DEBUG messages should be stored
        assert len(orm.log_messages) == 3
        assert "[INFO]" in orm.log_messages[0]
        assert "[WARNING]" in orm.log_messages[1]
        assert "[ERROR]" in orm.log_messages[2]
        
    def test_log_with_block_context(self, mock_api_client, test_config):
        """Test logging includes block context when report_block_id is set."""
        report_block_id = "test-block-123"
        orm = ReportBlockORM(mock_api_client, report_block_id, test_config)
        
        with patch.object(orm.logger, 'info') as mock_logger:
            orm.log("Test message")
            mock_logger.assert_called_once()
            call_args = mock_logger.call_args[0][0]
            assert f"[ReportBlock {report_block_id}]" in call_args
            assert "Test message" in call_args
            
    def test_log_without_block_context(self, mock_api_client, test_config):
        """Test logging without report_block_id."""
        orm = ReportBlockORM(mock_api_client, None, test_config)
        
        with patch.object(orm.logger, 'info') as mock_logger:
            orm.log("Test message")
            mock_logger.assert_called_once()
            call_args = mock_logger.call_args[0][0]
            assert "[ReportBlock]" in call_args
            assert "Test message" in call_args
            
    @patch('plexus.reports.s3_utils.add_file_to_report_block')
    def test_attach_file_success(self, mock_add_file, mock_api_client, test_config):
        """Test successful file attachment."""
        mock_add_file.return_value = "s3://bucket/path/to/file.txt"
        
        report_block_id = "test-block-123"
        orm = ReportBlockORM(mock_api_client, report_block_id, test_config)
        
        file_name = "test_file.txt"
        content = b"test content"
        content_type = "text/plain"
        
        result = orm.attach_file(file_name, content, content_type)
        
        assert result == "s3://bucket/path/to/file.txt"
        assert "s3://bucket/path/to/file.txt" in orm.attached_files
        assert len(orm.log_messages) == 1  # Should log the attachment
        assert "Attached file 'test_file.txt'" in orm.log_messages[0]
        
        mock_add_file.assert_called_once_with(
            report_block_id=report_block_id,
            file_name=file_name,
            content=content,
            content_type=content_type,
            client=mock_api_client
        )
        
    def test_attach_file_no_report_block_id(self, mock_api_client, test_config):
        """Test file attachment fails when no report_block_id is set."""
        orm = ReportBlockORM(mock_api_client, None, test_config)
        
        with pytest.raises(ValueError, match="Cannot attach files: report_block_id not set"):
            orm.attach_file("test.txt", b"content")
            
    def test_get_log_string_empty(self, mock_api_client, test_config):
        """Test get_log_string with no messages."""
        orm = ReportBlockORM(mock_api_client, "test-block-123", test_config)
        
        assert orm.get_log_string() == ""
        
    def test_get_log_string_with_messages(self, mock_api_client, test_config):
        """Test get_log_string with multiple messages."""
        orm = ReportBlockORM(mock_api_client, "test-block-123", test_config)
        
        orm.log("First message")
        orm.log("Second message")
        
        log_string = orm.get_log_string()
        assert "First message" in log_string
        assert "Second message" in log_string
        assert log_string.count("\n") == 1  # Two messages separated by newline
        
    def test_get_attached_files_empty(self, mock_api_client, test_config):
        """Test get_attached_files with no files."""
        orm = ReportBlockORM(mock_api_client, "test-block-123", test_config)
        
        files = orm.get_attached_files()
        assert files == []
        assert files is not orm.attached_files  # Should return a copy
        
    @patch('plexus.reports.s3_utils.add_file_to_report_block')
    def test_get_attached_files_with_files(self, mock_add_file, mock_api_client, test_config):
        """Test get_attached_files with attached files."""
        mock_add_file.return_value = "s3://bucket/path/to/file.txt"
        
        orm = ReportBlockORM(mock_api_client, "test-block-123", test_config)
        orm.attach_file("test.txt", b"content")
        
        files = orm.get_attached_files()
        assert files == ["s3://bucket/path/to/file.txt"]
        assert files is not orm.attached_files  # Should return a copy
        
    def test_set_report_block_id(self, mock_api_client, test_config):
        """Test setting report block ID."""
        orm = ReportBlockORM(mock_api_client, None, test_config)
        assert orm.report_block_id is None
        
        new_id = "new-block-456"
        orm.set_report_block_id(new_id)
        
        assert orm.report_block_id == new_id
        
    def test_logger_configuration(self, mock_api_client, test_config):
        """Test that logger is properly configured."""
        orm = ReportBlockORM(mock_api_client, "test-block-123", test_config)
        
        assert orm.logger.name == "plexus.reports.blocks.report_block_orm"
        assert isinstance(orm.logger, logging.Logger)
        
    def test_log_message_timestamps(self, mock_api_client, test_config):
        """Test that log messages include timestamps."""
        orm = ReportBlockORM(mock_api_client, "test-block-123", test_config)
        
        orm.log("Test message")
        
        assert len(orm.log_messages) == 1
        log_message = orm.log_messages[0]
        
        # Should contain ISO timestamp format
        assert "T" in log_message  # ISO format contains 'T'
        assert ("+00:00" in log_message or "Z" in log_message)  # UTC timezone indicator
        assert "[INFO]" in log_message
        assert "Test message" in log_message
        
    def test_multiple_file_attachments(self, mock_api_client, test_config):
        """Test multiple file attachments."""
        with patch('plexus.reports.s3_utils.add_file_to_report_block') as mock_add_file:
            mock_add_file.side_effect = [
                "s3://bucket/file1.txt",
                "s3://bucket/file2.txt"
            ]
            
            orm = ReportBlockORM(mock_api_client, "test-block-123", test_config)
            
            result1 = orm.attach_file("file1.txt", b"content1")
            result2 = orm.attach_file("file2.txt", b"content2")
            
            assert result1 == "s3://bucket/file1.txt"
            assert result2 == "s3://bucket/file2.txt"
            assert len(orm.attached_files) == 2
            assert "s3://bucket/file1.txt" in orm.attached_files
            assert "s3://bucket/file2.txt" in orm.attached_files
            
    def test_log_level_case_insensitive(self, mock_api_client, test_config):
        """Test that log levels are handled case-insensitively."""
        orm = ReportBlockORM(mock_api_client, "test-block-123", test_config)
        
        with patch.object(orm.logger, 'warning') as mock_logger:
            orm.log("Test message", "warning")  # lowercase
            mock_logger.assert_called_once()
            
        with patch.object(orm.logger, 'error') as mock_logger:
            orm.log("Test message", "ERROR")  # uppercase
            mock_logger.assert_called_once() 