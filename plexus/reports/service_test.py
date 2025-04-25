import pytest
from unittest.mock import patch, MagicMock, ANY
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

@patch('plexus.reports.service._load_report_configuration')
@patch('plexus.reports.service._parse_report_configuration')
@patch('plexus.reports.blocks.score_info.ScoreInfo.generate') # Patch the actual block's generate
def test_generate_report_success(mock_score_info_generate, mock_parse_config, mock_load_config, mock_report_config):
    """Tests successful report generation with Markdown and blocks."""
    # Configure mocks
    mock_load_config.return_value = mock_report_config

    # Configure the mock parser to return a dummy template and two block definitions
    mock_template_string = "Report Template Content. Blocks: {{ blocks }}"
    mock_block_defs = [
        { # Mock definition for the first block
            "name": "Block 1",
            "class": "ScoreInfo", # Match the class we are mocking generate for
            "config": {"score": "score-test-123", "include_variant": False}
        },
        { # Mock definition for the second block
            "name": "Block 2",
            "class": "ScoreInfo",
            "config": {"score": "score-test-456"}
        }
    ]
    mock_parse_config.return_value = (mock_template_string, mock_block_defs)
    
    # Configure the mock block generator
    # It should return JSON strings now, as expected by generate_report
    # The json.dumps is needed because generate_report expects JSON *strings* from _instantiate_and_run_block
    # Let's also patch _instantiate_and_run_block to return these strings
    # mock_score_info_generate.side_effect = [
    #     json.dumps({"type": "ScoreInfo", "data": {"id": "score-test-123", "name": "Mock Score 1"}}),
    #     json.dumps({"type": "ScoreInfo", "data": {"id": "score-test-456", "name": "Mock Score 2"}}),
    # ]
    # Instead of patching ScoreInfo.generate directly, patch _instantiate_and_run_block
    with patch('plexus.reports.service._instantiate_and_run_block') as mock_run_block:
        # Configure _instantiate_and_run_block mock
        mock_run_block.side_effect = [
            # Return value for first block call (output JSON string, log string)
            (json.dumps({"id": "score-test-123", "name": "Mock Score 1"}), None),
            # Return value for second block call
            (json.dumps({"id": "score-test-456", "name": "Mock Score 2"}), None),
        ]

        # Call the service function
        report_data = generate_report("test-config-1")
    
        # Assertions
        mock_load_config.assert_called_once_with("test-config-1")
        mock_parse_config.assert_called_once_with(mock_report_config["configuration"])
        # Check that _instantiate_and_run_block was called twice
        assert mock_run_block.call_count == 2 

        # Check the first call to the mocked _instantiate_and_run_block
        # The first argument passed should be the first block definition
        assert mock_run_block.call_args_list[0].args[0] == mock_block_defs[0]
        # The second argument should be the params dictionary
        assert mock_run_block.call_args_list[0].args[1] == {} 

        # Check the second call to the mocked _instantiate_and_run_block
        assert mock_run_block.call_args_list[1].args[0] == mock_block_defs[1]
        assert mock_run_block.call_args_list[1].args[1] == {} 

        # Check the structure and content of the returned report data (report_id string)
        assert isinstance(report_data, str) # Check it returns a string (report_id)
        assert report_data.startswith("report-test-config-1") # Check mock report ID format

@patch('plexus.reports.service._load_report_configuration')
def test_generate_report_config_not_found(mock_load_config):
    """Tests behavior when the report configuration ID is not found."""
    # Configure mock to simulate config not found
    mock_load_config.return_value = None

    # Call the service function with a non-existent ID
    with pytest.raises(ValueError, match="ReportConfiguration not found"):
        generate_report("non-existent-config-id")

    # Assertions
    mock_load_config.assert_called_once_with("non-existent-config-id")

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