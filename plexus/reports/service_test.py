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
# Mock the instance update method on the Report object that will be returned by create
# Note: We mock it here, but the actual mocking happens on the *returned instance* below.
# This patch decorator might not be strictly necessary if we only mock the instance, 
# but it's good practice to declare the intent.
# We also need to mock the client used *within* the instance update method.
@patch('plexus.reports.service.PlexusDashboardClient') 
@patch('plexus.reports.service._load_report_configuration', new_callable=AsyncMock) # Keep AsyncMock for the truly async loader
@patch('plexus.reports.service._parse_report_configuration') # This one is called directly, sync mock is fine
@patch('plexus.reports.service._instantiate_and_run_block', new_callable=AsyncMock) # <-- Use AsyncMock here
@pytest.mark.asyncio
async def test_generate_report_success(
    mock_run_block,      # <-- Mock is now AsyncMock
    mock_parse_config,
    mock_load_config,
    mock_api_client,    # Mock for the client used in update
    mock_block_create,  # Now a MagicMock again
    mock_report_create, # Now a MagicMock again
    mock_report_config  # The fixture
):
    """Tests successful report generation with Markdown and blocks (async)."""
    # --- Mock API Client ---
    # The Report instance's update method needs a client.
    mock_client_instance = MagicMock()
    mock_api_client.return_value = mock_client_instance

    # --- Mock ReportConfiguration Loading ---
    mock_config_object = MagicMock()
    mock_config_object.configuration = mock_report_config['configuration']
    mock_config_object.name = mock_report_config['name']
    mock_config_object.accountId = 'test-account-id'
    mock_load_config.return_value = mock_config_object

    # --- Mock Report Creation ---
    # Define the mock Report object that Report.create should return.
    # It needs a client instance associated with it for the update method to work.
    mock_created_report_obj = MagicMock(spec=Report, _client=mock_client_instance)
    mock_created_report_obj.id = "report-test-config-1-run1" # Predictable ID
    # Mock the update method ON THE INSTANCE as a standard MagicMock
    # This is the crucial part: mock the method on the *instance*.
    mock_created_report_obj.update = MagicMock(return_value=None) # Set return value if needed
    mock_report_create.return_value = mock_created_report_obj # create returns the mock obj

    # --- Mock Configuration Parsing ---
    reconstructed_markdown = mock_report_config['configuration']
    # Use actual class name used in service
    mock_block_defs = [
        {"class_name": "ScoreInfo", "config": {"scoreId": "score-test-123", "include_variant": False}, "name": "block_0", "position": 0},
        {"class_name": "ScoreInfo", "config": {"scoreId": "score-test-456"}, "name": "block_1", "position": 1}
    ]
    mock_parse_config.return_value = (reconstructed_markdown, mock_block_defs)

    # --- Mock ReportBlock Creation ---
    # mock_block_create is now a MagicMock from the decorator
    # Ensure the returned mock has an ID attribute
    mock_block_create.return_value = MagicMock(spec=ReportBlock, id="mock-block-id-123")

    # --- Configure the AsyncMock for _instantiate_and_run_block ---
    # Set the side_effect directly on the AsyncMock passed to the test
    mock_run_block.side_effect = [
        (json.dumps({"id": "score-test-123", "name": "Mock Score 1"}), "Log for block 1"), # Return tuple directly
        (json.dumps({"id": "score-test-456", "name": "Mock Score 2"}), "Log for block 2"), # Return tuple directly
    ]

    # === Call the async service function ===
    report_id_result = await generate_report(
        report_config_id="test-config-1",
        account_id="test-account-id",
        task_id="mock-task-id-123"
    )

    # === Assertions ===
    # 1. Config Loading
    mock_load_config.assert_awaited_once_with(mock_client_instance, "test-config-1")

    # 2. Initial Report Creation
    # Check that Report.create was called (via to_thread, so sync assert)
    mock_report_create.assert_called_once()
    create_call_kwargs = mock_report_create.call_args.kwargs
    assert create_call_kwargs['reportConfigurationId'] == "test-config-1"
    assert create_call_kwargs['accountId'] == 'test-account-id'
    assert create_call_kwargs['name'].startswith(mock_report_config['name'])
    assert create_call_kwargs['parameters'] == {}
    # Assert that status is NOT set during creation (it belongs to Task)
    assert 'status' not in create_call_kwargs

    # 3. Parsing
    mock_parse_config.assert_called_once_with(mock_config_object.configuration)

    # 4. Block Instantiation/Run (Now check the AsyncMock)
    assert mock_run_block.await_count == 2

    # Check the arguments passed to the first call
    call1 = mock_run_block.await_args_list[0]
    # Expecting keyword arguments based on function signature and typical async calls
    assert not call1.args # Positional args should be empty
    assert call1.kwargs['block_def'] == mock_block_defs[0]
    assert call1.kwargs['report_params'] == {"scoreId": "score-test-123", "include_variant": False} # Combined params check
    assert call1.kwargs['api_client'] == mock_client_instance

    # Check the arguments passed to the second call
    call2 = mock_run_block.await_args_list[1]
    assert not call2.args # Positional args should be empty
    assert call2.kwargs['block_def'] == mock_block_defs[1]
    assert call2.kwargs['report_params'] == {"scoreId": "score-test-456"} # Combined params check
    assert call2.kwargs['api_client'] == mock_client_instance

    # 5. ReportBlock Creation
    # Check that ReportBlock.create was called (via to_thread, so sync assert)
    assert mock_block_create.call_count == len(mock_block_defs)
    block_create_call_1_kwargs = mock_block_create.call_args_list[0].kwargs
    assert block_create_call_1_kwargs['reportId'] == mock_created_report_obj.id
    assert block_create_call_1_kwargs['position'] == mock_block_defs[0]['position'] + 1
    assert block_create_call_1_kwargs['name'] == mock_block_defs[0]['name']
    assert block_create_call_1_kwargs['output'] == json.dumps({"id": "score-test-123", "name": "Mock Score 1"})
    assert block_create_call_1_kwargs['log'] == "Log for block 1"
    block_create_call_2_kwargs = mock_block_create.call_args_list[1].kwargs
    assert block_create_call_2_kwargs['reportId'] == mock_created_report_obj.id
    assert block_create_call_2_kwargs['position'] == mock_block_defs[1]['position'] + 1
    assert block_create_call_2_kwargs['name'] == mock_block_defs[1]['name']
    assert block_create_call_2_kwargs['output'] == json.dumps({"id": "score-test-456", "name": "Mock Score 2"})
    assert block_create_call_2_kwargs['log'] == "Log for block 2"

    # 6. Final Report Update (Instance method)
    # Check that the update method *on the created object* was called (via to_thread, so sync assert)
    mock_created_report_obj.update.assert_called_once()
    update_call_args, update_call_kwargs = mock_created_report_obj.update.call_args
    # Check that ONLY allowed fields (like output) are updated
    assert update_call_kwargs['output'] == reconstructed_markdown
    # Assert that forbidden fields are NOT updated
    forbidden_fields = ['status', 'completedAt', 'errorMessage', 'errorDetails', 'taskId']
    for field in forbidden_fields:
        assert field not in update_call_kwargs
    assert 'errorMessage' not in update_call_kwargs # Should not be present on success

    # 7. Return value
    # Check the structure and content of the returned report data (report_id string)
    assert isinstance(report_id_result, str)
    # Check it returns the predictable ID from our mock
    assert report_id_result == mock_created_report_obj.id

@patch('plexus.reports.service.PlexusDashboardClient')
@patch('plexus.reports.service._load_report_configuration', new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_generate_report_config_not_found(
    mock_load_config,
    mock_api_client
):
    """Tests behavior when the report configuration ID is not found (async)."""
    # Configure mock API client instance (needed by the function)
    mock_client_instance = MagicMock()
    mock_api_client.return_value = mock_client_instance

    # Configure mock load_config to simulate config not found
    mock_load_config.return_value = None

    # Define report_id and task_id for the scenario where update_status might be called
    test_report_id = "existing-report-id-123"
    test_task_id = "mock-task-id-456"

    # Call the async service function with a non-existent ID and await it
    with pytest.raises(ValueError, match="ReportConfiguration not found"):
        await generate_report(
            report_config_id="non-existent-config-id",
            account_id="test-account-id",
            report_id=test_report_id,
            task_id=test_task_id
        )

    # Assertions
    mock_load_config.assert_awaited_once_with(mock_client_instance, "non-existent-config-id")

    # Verify NO update method was called on Report, as the service should just raise ValueError
    # (Status update should happen on the Task by the calling Celery task)

@patch('plexus.reports.service.PlexusDashboardClient')
@patch('plexus.reports.service._load_report_configuration', new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_generate_report_config_not_found_no_report_id(
    mock_load_config,
    mock_api_client
):
    """Tests config not found when no pre-existing report_id is given."""
    mock_client_instance = MagicMock()
    mock_api_client.return_value = mock_client_instance
    mock_load_config.return_value = None

    with pytest.raises(ValueError, match="ReportConfiguration not found"):
        await generate_report(
            report_config_id="non-existent-config-id",
            account_id="test-account-id",
            report_id=None,
            task_id="mock-task-id-789"
        )

    mock_load_config.assert_awaited_once_with(mock_client_instance, "non-existent-config-id")
    # Ensure no update method was called
    # (mock_update_status is removed, so no assertion needed here)

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