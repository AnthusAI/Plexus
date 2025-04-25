import pytest
from unittest.mock import patch, MagicMock, ANY
import logging

from plexus.reports.service import generate_report, _load_report_configuration, ReportBlockExtractor
from plexus.reports.blocks.base import BaseReportBlock
from plexus.reports.blocks.score_info import ScoreInfoBlock # Import for mocking later

# Disable logging noise during tests
logging.disable(logging.CRITICAL)

@pytest.fixture
def mock_report_config():
    """Provides a mock report configuration dictionary."""
    return {
        "id": "test-config-1",
        "name": "Test Score Report",
        "configuration": """
# Test Report Header

This is the first markdown section.

```block
pythonClass: ScoreInfoBlock
config:
  scoreId: "score-test-123"
  include_variant: false
```

This is markdown between blocks.

```block
pythonClass: ScoreInfoBlock
config:
  scoreId: "score-test-456"
```

Final markdown footer.
"""
    }

@patch('plexus.reports.service._load_report_configuration')
@patch('plexus.reports.blocks.score_info.ScoreInfoBlock.generate') # Patch the actual block's generate
def test_generate_report_success(mock_score_info_generate, mock_load_config, mock_report_config):
    """Tests successful report generation with Markdown and blocks."""
    # Configure mocks
    mock_load_config.return_value = mock_report_config
    
    # Make generate return different results for each call if needed, or a fixed one
    mock_score_info_generate.side_effect = [
        {"type": "ScoreInfo", "data": {"id": "score-test-123", "name": "Mock Score 1"}},
        {"type": "ScoreInfo", "data": {"id": "score-test-456", "name": "Mock Score 2"}},
    ]

    # Call the service function
    report_data = generate_report("test-config-1")

    # Assertions
    mock_load_config.assert_called_once_with("test-config-1")
    assert mock_score_info_generate.call_count == 2

    # Check the first call to the mocked generate
    assert mock_score_info_generate.call_args_list[0].kwargs['config'] == {"scoreId": "score-test-123", "include_variant": False}
    assert mock_score_info_generate.call_args_list[0].kwargs['params'] is None

    # Check the second call to the mocked generate
    assert mock_score_info_generate.call_args_list[1].kwargs['config'] == {"scoreId": "score-test-456"}
    assert mock_score_info_generate.call_args_list[1].kwargs['params'] is None

    # Check the structure and content of the returned report data
    assert len(report_data) == 5 # 3 markdown sections + 2 block results

    assert report_data[0]["type"] == "markdown"
    assert "# Test Report Header" in report_data[0]["content"]
    assert "first markdown section" in report_data[0]["content"]

    assert report_data[1]["type"] == "block_result"
    assert report_data[1]["block_type"] == "ScoreInfo" # Should match the mock return
    assert report_data[1]["data"]["data"]["id"] == "score-test-123"

    assert report_data[2]["type"] == "markdown"
    assert "markdown between blocks" in report_data[2]["content"]

    assert report_data[3]["type"] == "block_result"
    assert report_data[3]["block_type"] == "ScoreInfo" # Should match the mock return
    assert report_data[3]["data"]["data"]["id"] == "score-test-456"

    assert report_data[4]["type"] == "markdown"
    assert "Final markdown footer" in report_data[4]["content"]

@patch('plexus.reports.service._load_report_configuration')
def test_generate_report_config_not_found(mock_load_config):
    """Tests behavior when the report configuration ID is not found."""
    # Configure mock to simulate config not found
    mock_load_config.return_value = None

    # Call the service function with a non-existent ID
    report_data = generate_report("non-existent-config-id")

    # Assertions
    mock_load_config.assert_called_once_with("non-existent-config-id")
    assert report_data == [] # Expect an empty list based on current service logic

# TODO: Add tests for config not found, invalid markdown/yaml, block class not found, block generate error etc.

@pytest.mark.skip(reason="Not implemented yet")
def test_generate_report_empty_config_content():
    """Tests behavior when the config exists but has no/empty markdown."""
    pass

@pytest.mark.skip(reason="Not implemented yet")
def test_generate_report_invalid_yaml():
    """Tests behavior when a block contains invalid YAML."""
    pass

@pytest.mark.skip(reason="Not implemented yet")
def test_generate_report_block_class_not_found():
    """Tests behavior when pythonClass refers to a non-existent block."""
    pass

@pytest.mark.skip(reason="Not implemented yet")
def test_generate_report_block_generate_error():
    """Tests behavior when a block's generate() method raises an exception."""
    pass 