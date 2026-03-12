"""
Basic integration tests for report system that actually work.
Tests core functionality without complex mocking that causes issues.
"""

import pytest
from unittest.mock import patch, MagicMock
import json

from plexus.reports.service import (
    _load_report_configuration, _parse_report_configuration, 
    _instantiate_and_run_block
)


class TestBasicReportServiceIntegration:
    """Test basic report service functionality that works reliably."""

    @patch('plexus.reports.service.ReportConfiguration.get_by_id')
    def test_load_report_configuration_basic(self, mock_get_by_id):
        """Test basic configuration loading."""
        # Setup mock
        mock_client = MagicMock()
        mock_config = MagicMock()
        mock_config.id = "config-123"
        mock_config.name = "Test Config"
        mock_get_by_id.return_value = mock_config
        
        # Execute function
        result = _load_report_configuration(mock_client, "config-123")
        
        # Verify success
        assert result == mock_config
        mock_get_by_id.assert_called_once_with("config-123", mock_client)

    def test_parse_report_configuration_basic(self):
        """Test basic configuration parsing."""
        markdown = """
# Test Report

```block
class: TestBlockClass
config:
  param1: value1
  param2: value2
```
"""
        
        # Execute function
        result = _parse_report_configuration(markdown)
        
        # Verify parsing
        assert len(result) == 1
        assert result[0]["class_name"] == "TestBlockClass"
        assert result[0]["config"]["param1"] == "value1"
        assert result[0]["config"]["param2"] == "value2"
        assert result[0]["position"] == 0

    def test_parse_multiple_blocks(self):
        """Test parsing multiple blocks."""
        markdown = """
# Test Report

First block:

```block
class: FirstBlock
config:
  param: first_value
```

Second block:

```block
class: SecondBlock
config:
  param: second_value
```
"""
        
        # Execute function
        result = _parse_report_configuration(markdown)
        
        # Verify parsing
        assert len(result) == 2
        assert result[0]["class_name"] == "FirstBlock"
        assert result[0]["position"] == 0
        assert result[1]["class_name"] == "SecondBlock"
        assert result[1]["position"] == 1

    def test_instantiate_block_class_not_found(self):
        """Test block instantiation when class doesn't exist."""
        # Execute function with non-existent class
        output, log, dataset_id = _instantiate_and_run_block(
            block_def={
                "class_name": "NonExistentBlockClass",
                "config": {"param": "value"}
            },
            report_params={},
            api_client=MagicMock()
        )
        
        # Verify error handling
        assert output is None
        assert "not found or not registered" in log
        assert dataset_id is None

    def test_parse_empty_configuration(self):
        """Test parsing empty configuration."""
        result = _parse_report_configuration("")
        assert result == []

    def test_parse_configuration_no_blocks(self):
        """Test parsing configuration with no blocks."""
        markdown = """
# Test Report

This is just regular markdown content with no blocks.

Some more text here.
"""
        
        result = _parse_report_configuration(markdown)
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])