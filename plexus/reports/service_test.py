import pytest
from unittest.mock import patch, MagicMock, ANY, AsyncMock
import logging
import json

from plexus.reports.service import generate_report, _load_report_configuration, ReportBlockExtractor
from plexus.reports.blocks.base import BaseReportBlock
from plexus.reports.blocks.score_info import ScoreInfo # Import for mocking later
# Import models needed for spec in MagicMock
from plexus.dashboard.api.models.report import Report
from plexus.dashboard.api.models.report_block import ReportBlock

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

# Use standard MagicMock for methods called via asyncio.to_thread,
# as the methods themselves are synchronous.
@patch('plexus.reports.service.Report.create') 
@patch('plexus.reports.service.ReportBlock.create') 
# We will mock the instance update method specifically later.
@patch('plexus.reports.service._load_report_configuration', new_callable=AsyncMock) # Keep AsyncMock for the truly async loader
@patch('plexus.reports.service._parse_report_configuration') # This one is called directly, sync mock is fine
@pytest.mark.asyncio
async def test_generate_report_success(
    mock_parse_config,
    mock_load_config, 
    mock_block_create,  # Now a MagicMock again
    mock_report_create, # Now a MagicMock again
    mock_report_config  # The fixture
):
    """Tests successful report generation with Markdown and blocks (async)."""
    # --- Mock ReportConfiguration Loading ---
    mock_config_object = MagicMock()
    mock_config_object.configuration = mock_report_config['configuration']
    mock_config_object.name = mock_report_config['name']
    mock_config_object.accountId = 'test-account-id'
    mock_load_config.return_value = mock_config_object

    # --- Mock Report Creation ---
    # Define the mock Report object that Report.create should return
    mock_created_report_obj = MagicMock(spec=Report) # Keep the base obj as MagicMock
    mock_created_report_obj.id = "report-test-config-1-run1" # Predictable ID
    # Mock the update method ON THE INSTANCE as a standard MagicMock
    mock_created_report_obj.update = MagicMock(return_value=None) # Set return value if needed
    mock_report_create.return_value = mock_created_report_obj # create returns the mock obj

    # --- Mock Configuration Parsing ---
    reconstructed_markdown = mock_report_config['configuration']
    mock_block_defs = [
        {"class_name": "ScoreInfoBlock", "config": {"scoreId": "score-test-123", "include_variant": False}, "name": "block_0", "position": 0},
        {"class_name": "ScoreInfoBlock", "config": {"scoreId": "score-test-456"}, "name": "block_1", "position": 1}
    ]
    mock_parse_config.return_value = (reconstructed_markdown, mock_block_defs)

    # --- Mock ReportBlock Creation ---
    # mock_block_create is now a MagicMock from the decorator
    # Ensure the returned mock has an ID attribute
    mock_block_create.return_value = MagicMock(spec=ReportBlock, id="mock-block-id-123") 

    # --- Mock _instantiate_and_run_block ---
    # This is called directly within the async function, so MagicMock is fine
    with patch('plexus.reports.service._instantiate_and_run_block') as mock_run_block:
        mock_run_block.side_effect = [
            (json.dumps({"id": "score-test-123", "name": "Mock Score 1"}), None),
            (json.dumps({"id": "score-test-456", "name": "Mock Score 2"}), None),
        ]

        # === Call the async service function ===
        report_id_result = await generate_report("test-config-1")

    # === Assertions ===
    # 1. Config Loading
    mock_load_config.assert_awaited_once_with(ANY, "test-config-1")

    # 2. Initial Report Creation
    # Check that Report.create was called (via to_thread, so sync assert)
    mock_report_create.assert_called_once() 
    create_call_kwargs = mock_report_create.call_args.kwargs
    assert create_call_kwargs['reportConfigurationId'] == "test-config-1"
    assert create_call_kwargs['accountId'] == 'test-account-id'
    assert create_call_kwargs['name'].startswith(mock_report_config['name'])
    assert create_call_kwargs['parameters'] == {}
    assert create_call_kwargs['status'] == 'RUNNING'

    # 3. Parsing
    mock_parse_config.assert_called_once_with(mock_config_object.configuration)

    # 4. Block Instantiation/Run
    assert mock_run_block.call_count == 2
    call1_args = mock_run_block.call_args_list[0].args
    call1_kwargs = mock_run_block.call_args_list[0].kwargs
    assert call1_args[0] == mock_block_defs[0]
    assert call1_kwargs.get('report_params') == {}
    # ... (check second call similarly) ...

    # 5. ReportBlock Creation
    # Check that ReportBlock.create was called (via to_thread, so sync assert)
    assert mock_block_create.call_count == len(mock_block_defs) 
    # Check args for the first block create call
    block_create_call_kwargs = mock_block_create.call_args_list[0].kwargs
    assert block_create_call_kwargs['reportId'] == mock_created_report_obj.id
    assert block_create_call_kwargs['position'] == mock_block_defs[0]['position']
    assert block_create_call_kwargs['name'] == mock_block_defs[0]['name']
    assert block_create_call_kwargs['output'] == json.dumps({"id": "score-test-123", "name": "Mock Score 1"})
    assert block_create_call_kwargs['log'] is None
    # ... (check second call similarly) ...

    # 6. Final Report Update
    # Check that the update method *on the created object* was called (via to_thread, so sync assert)
    mock_created_report_obj.update.assert_called_once()
    update_call_args, update_call_kwargs = mock_created_report_obj.update.call_args
    assert update_call_kwargs['status'] == 'COMPLETED'
    assert update_call_kwargs['output'] == reconstructed_markdown
    assert 'completedAt' in update_call_kwargs
    assert 'errorMessage' not in update_call_kwargs # Should not be present on success

    # 7. Return value
    # Check the structure and content of the returned report data (report_id string)
    assert isinstance(report_id_result, str)
    # Check it returns the predictable ID from our mock
    assert report_id_result == mock_created_report_obj.id

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