import pytest
from unittest.mock import patch, MagicMock, ANY, AsyncMock
import logging
import json

from plexus.reports.service import generate_report, _load_report_configuration, ReportBlockExtractor
from plexus.reports.blocks.base import BaseReportBlock
from plexus.reports.blocks.score_info import ScoreInfo # Import for mocking later

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

@patch('plexus.reports.service._load_report_configuration', new_callable=AsyncMock)
@patch('plexus.reports.service._parse_report_configuration')
@pytest.mark.asyncio
async def test_generate_report_success(mock_parse_config, mock_load_config, mock_report_config):
    """Tests successful report generation with Markdown and blocks (async)."""
    # Configure mocks
    # mock_load_config corresponds to the _load_report_configuration patch
    # Create a mock ReportConfiguration object to return
    mock_config_object = MagicMock()
    # Use the actual fixture data passed as mock_report_config
    mock_config_object.configuration = mock_report_config['configuration']
    mock_config_object.name = mock_report_config['name']
    mock_config_object.accountId = 'test-account-id' # Add accountId expected by generate_report
    mock_load_config.return_value = mock_config_object # Set return value for the correct mock

    # mock_parse_config corresponds to the _parse_report_configuration patch
    # Configure the mock parser to return the reconstructed markdown and block definitions
    # The first item should be the reconstructed original markdown string
    reconstructed_markdown = mock_report_config['configuration'] # For simplicity, assume parser returns original
    mock_block_defs = [
        { # Mock definition for the first block
            "class_name": "ScoreInfoBlock", # Corrected class name casing potentially
            "config": {"scoreId": "score-test-123", "include_variant": False},
            "name": "block_0", # Assuming default name from parser
            "position": 0
        },
        { # Mock definition for the second block
            "class_name": "ScoreInfoBlock",
            "config": {"scoreId": "score-test-456"},
            "name": "block_1",
            "position": 1
        }
    ]
    mock_parse_config.return_value = (reconstructed_markdown, mock_block_defs)

    # Patch _instantiate_and_run_block within the test using a context manager
    with patch('plexus.reports.service._instantiate_and_run_block') as mock_run_block:
        # Configure _instantiate_and_run_block mock
        mock_run_block.side_effect = [
            # Return value for first block call (output JSON string, log string)
            (json.dumps({"id": "score-test-123", "name": "Mock Score 1"}), None),
            # Return value for second block call
            (json.dumps({"id": "score-test-456", "name": "Mock Score 2"}), None),
        ]

        # Call the async service function using await
        report_data = await generate_report("test-config-1")
    
        # Assertions
        mock_load_config.assert_awaited_once_with(ANY, "test-config-1")
        mock_parse_config.assert_called_once_with(mock_report_config["configuration"])
        # Check that _instantiate_and_run_block was called twice
        assert mock_run_block.call_count == 2 

        # Check the first call to the mocked _instantiate_and_run_block
        call1_args = mock_run_block.call_args_list[0].args
        call1_kwargs = mock_run_block.call_args_list[0].kwargs
        # The first positional argument should be the first block definition
        assert call1_args[0] == mock_block_defs[0]
        # The keyword argument 'report_params' should be the params dictionary (empty in this test)
        assert call1_kwargs.get('report_params') == {}

        # Check the second call to the mocked _instantiate_and_run_block
        call2_args = mock_run_block.call_args_list[1].args
        call2_kwargs = mock_run_block.call_args_list[1].kwargs
        assert call2_args[0] == mock_block_defs[1]
        assert call2_kwargs.get('report_params') == {}

        # Check the structure and content of the returned report data (report_id string)
        assert isinstance(report_data, str) # Check it returns a string (report_id)
        assert report_data.startswith("report-test-config-1") # Check mock report ID format

@patch('plexus.reports.service._load_report_configuration', new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_generate_report_config_not_found(mock_load_config):
    """Tests behavior when the report configuration ID is not found (async)."""
    # Configure mock to simulate config not found
    mock_load_config.return_value = None

    # Call the async service function with a non-existent ID and await it
    with pytest.raises(ValueError, match="ReportConfiguration not found"):
        await generate_report("non-existent-config-id")

    # Assertions
    mock_load_config.assert_awaited_once_with(ANY, "non-existent-config-id")

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