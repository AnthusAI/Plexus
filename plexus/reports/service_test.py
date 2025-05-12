import pytest
from unittest.mock import patch, MagicMock, ANY
import logging
import json

from plexus.reports.service import generate_report, _load_report_configuration, ReportBlockExtractor
from plexus.reports.blocks.base import BaseReportBlock
from plexus.reports.blocks.score_info import ScoreInfo # Import for mocking later
# Import models needed for spec in MagicMock
from plexus.dashboard.api.models.report import Report
from plexus.dashboard.api.models.report_block import ReportBlock
from plexus.dashboard.api.models.task import Task # Added for mocking
from plexus.cli.task_progress_tracker import TaskProgressTracker # Added for mocking

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

@patch('plexus.reports.service.Report.create')
@patch('plexus.reports.service.ReportBlock.create')
@patch('plexus.reports.service.PlexusDashboardClient')
@patch('plexus.reports.service._load_report_configuration')
@patch('plexus.reports.service._parse_report_configuration')
@patch('plexus.reports.service._instantiate_and_run_block')
@patch('plexus.reports.service.TaskProgressTracker')
@patch('plexus.reports.service.Task')
def test_generate_report_success(
    MockTask,
    MockTaskProgressTracker,
    mock_run_block,
    mock_parse_config,
    mock_load_config,
    mock_api_client,
    mock_block_create,
    mock_report_create,
    mock_report_config
):
    """Tests successful report generation with Markdown and blocks."""
    # === Mocks Setup ===
    # --- Mock API Client ---
    mock_client_instance = MagicMock()
    mock_api_client.return_value = mock_client_instance

    # --- Mock Task Loading ---
    mock_task_instance = MagicMock(spec=Task)
    mock_task_instance.id = "task-123"
    mock_task_instance.metadata = json.dumps({
        "report_configuration_id": "test-config-1",
        "account_id": "test-account-id",
        "report_parameters": {"param1": "value1"}
    })
    # Mock the class method Task.get_by_id
    MockTask.get_by_id.return_value = mock_task_instance

    # --- Mock ReportConfiguration Loading ---
    mock_config_object = MagicMock()
    mock_config_object.configuration = mock_report_config['configuration']
    mock_config_object.name = mock_report_config['name']
    mock_config_object.accountId = 'test-account-id'
    mock_load_config.return_value = mock_config_object

    # --- Mock Report Creation ---
    mock_created_report_obj = MagicMock(spec=Report, _client=mock_client_instance)
    mock_created_report_obj.id = "report-test-config-1-run1"
    mock_created_report_obj.update = MagicMock(return_value=None) # Set return value if needed
    mock_report_create.return_value = mock_created_report_obj # create returns the mock obj

    # --- Mock Configuration Parsing ---
    reconstructed_markdown = mock_report_config['configuration']
    # Use actual class name used in service
    mock_block_defs = [
        {"class_name": "ScoreInfo", "config": {"scoreId": "score-test-123", "include_variant": False}, "block_name": "block_0", "position": 1},
        {"class_name": "ScoreInfo", "config": {"scoreId": "score-test-456"}, "block_name": "block_1", "position": 2}
    ]
    mock_parse_config.return_value = mock_block_defs

    # --- Mock ReportBlock Creation ---
    mock_block_create.return_value = MagicMock(spec=ReportBlock, id="mock-block-id-123")

    # --- Configure the mock for _instantiate_and_run_block ---
    mock_run_block.side_effect = [
        ({"id": "score-test-123", "name": "Mock Score 1"}, "Log for block 1"), # Return tuple with raw dict
        ({"id": "score-test-456", "name": "Mock Score 2"}, "Log for block 2"), # Return tuple with raw dict
    ]

    # --- Mock TaskProgressTracker --- 
    mock_tracker_instance = MagicMock() # Remove spec to allow any method call
    # Mock the context manager methods
    mock_tracker_instance.__enter__.return_value = mock_tracker_instance
    mock_tracker_instance.__exit__.return_value = None # Simulate clean exit
    mock_tracker_instance.task_id = "task-123" # <<< ADDED: Configure mock task_id
    # Create a mock task object with id property
    mock_task = MagicMock()
    mock_task.id = "task-123"
    mock_tracker_instance.task = mock_task
    MockTaskProgressTracker.return_value = mock_tracker_instance

    # === Call the service function ===
    generate_report(task_id="task-123") # Call with only task_id

    # === Assertions ===
    # 1. Task Loading
    MockTask.get_by_id.assert_called_once_with("task-123", mock_client_instance)

    # 2. Config Loading
    mock_load_config.assert_called_once_with(mock_client_instance, "test-config-1")

    # 3. TaskProgressTracker Instantiation
    MockTaskProgressTracker.assert_called_once_with(
        task_id="task-123",
        stage_configs=ANY, # Check stages if specific structure is important
        total_items=0,
        prevent_new_task=True
    )
    # Verify context manager usage is no longer applicable
    # mock_tracker_instance.__enter__.assert_called_once()
    # mock_tracker_instance.__exit__.assert_called_once()

    # Verify stage setting calls are no longer applicable within generate_report
    # mock_tracker_instance.set_stage.assert_any_call("Setup")
    # mock_tracker_instance.set_stage.assert_any_call("Generate Blocks", total_items=len(mock_block_defs))
    # mock_tracker_instance.set_stage.assert_any_call("Finalize")

    # 4. Initial Report Creation
    mock_report_create.assert_called_once()
    create_call_kwargs = mock_report_create.call_args.kwargs
    assert create_call_kwargs['reportConfigurationId'] == "test-config-1"
    assert create_call_kwargs['accountId'] == 'test-account-id'
    assert create_call_kwargs['name'].startswith(mock_report_config['name'])
    assert create_call_kwargs['parameters'] == json.dumps({"param1": "value1"})
    assert create_call_kwargs['taskId'] == "task-123" # Check taskId is passed
    # Assert that status is NOT set during creation (it belongs to Task)
    assert 'status' not in create_call_kwargs

    # 5. Parsing
    mock_parse_config.assert_called_once_with(mock_config_object.configuration)

    # 6. Block Instantiation/Run
    assert mock_run_block.call_count == 2
    # Check first call args
    call1_args, call1_kwargs = mock_run_block.call_args_list[0]
    assert call1_kwargs['block_def'] == mock_block_defs[0]
    assert call1_kwargs['report_params'] == {"param1": "value1"} # Check report params
    assert call1_kwargs['api_client'] == mock_client_instance
    # Check second call args
    call2_args, call2_kwargs = mock_run_block.call_args_list[1]
    assert call2_kwargs['block_def'] == mock_block_defs[1]
    assert call2_kwargs['report_params'] == {"param1": "value1"}
    assert call2_kwargs['api_client'] == mock_client_instance

    # 7. ReportBlock Creation
    assert mock_block_create.call_count == len(mock_block_defs)
    block_create_call_1_kwargs = mock_block_create.call_args_list[0].kwargs
    assert block_create_call_1_kwargs['reportId'] == mock_created_report_obj.id
    assert block_create_call_1_kwargs['position'] == 1 # Now 1-based
    assert block_create_call_1_kwargs['name'] == mock_block_defs[0]['block_name']
    assert json.loads(block_create_call_1_kwargs['output']) == {"id": "score-test-123", "name": "Mock Score 1"}
    assert block_create_call_1_kwargs['log'] == "Log for block 1"
    block_create_call_2_kwargs = mock_block_create.call_args_list[1].kwargs
    assert block_create_call_2_kwargs['reportId'] == mock_created_report_obj.id
    assert block_create_call_2_kwargs['position'] == 2 # Now 1-based
    assert block_create_call_2_kwargs['name'] == mock_block_defs[1]['block_name']
    assert json.loads(block_create_call_2_kwargs['output']) == {"id": "score-test-456", "name": "Mock Score 2"}
    assert block_create_call_2_kwargs['log'] == "Log for block 2"

    # 8. Tracker Progress Update calls are no longer applicable within generate_report
    # mock_tracker_instance.update.assert_any_call(current_items=1)
    # mock_tracker_instance.update.assert_any_call(current_items=2)

    # 9. Final Report Update (Saving Markdown) - this is no longer done in the implementation
    # mock_created_report_obj.update.assert_called_once()
    # _ , update_call_kwargs = mock_created_report_obj.update.call_args
    # Check that ONLY output field is updated
    # assert update_call_kwargs['output'] == reconstructed_markdown
    # Verify only 'output' key exists in the update call kwargs
    # assert list(update_call_kwargs.keys()) == ['output']

    # 10. No return value from generate_report

@patch('plexus.reports.service.PlexusDashboardClient')
@patch('plexus.reports.service.Task') # Mock Task model
def test_generate_report_task_not_found(
    MockTask, # Mock Task class
    mock_api_client
):
    """Tests behavior when the task ID is not found."""
    # Configure mock API client instance
    mock_client_instance = MagicMock()
    mock_api_client.return_value = mock_client_instance

    # Configure Task.get_by_id to return None
    MockTask.get_by_id.return_value = None

    # Call the service function - Expect it to handle None and exit gracefully (e.g., log)
    generate_report(task_id="non-existent-task-id")

    # Assertions
    MockTask.get_by_id.assert_called_once_with("non-existent-task-id", mock_client_instance)
    # Task update should not be called if the task object itself wasn't retrieved

@patch('plexus.reports.service.PlexusDashboardClient') # Decorator 1 -> Argument 4
@patch('plexus.reports.service.Task') # Decorator 2 -> Argument 3 
@patch('plexus.reports.service._load_report_configuration') # Decorator 3 -> Argument 2
@patch('plexus.reports.service.TaskProgressTracker') # Decorator 4 -> Argument 1
def test_generate_report_config_not_found(
    MockTaskProgressTracker, # Argument 1
    mock_load_config,        # Argument 2
    MockTask,                # Argument 3 
    mock_api_client          # Argument 4
):
    """Tests behavior when the report configuration ID is not found."""
    # --- Mocks Setup ---
    # Use the correctly named mock for the client
    mock_client_instance = MagicMock()
    mock_api_client.return_value = mock_client_instance

    # Mock Task loading (using MockTask which now correctly maps to the @patch)
    mock_task_instance = MagicMock(spec=Task)
    mock_task_instance.id = "task-456"
    mock_task_instance.metadata = json.dumps({
        "report_configuration_id": "non-existent-config-id",
        "account_id": "test-account-id",
        "report_parameters": {}
    })
    mock_task_instance.update = MagicMock()
    MockTask.get_by_id.return_value = mock_task_instance

    # Mock config loading to return None (using mock_load_config which now correctly maps)
    mock_load_config.return_value = None

    # Mock the TaskProgressTracker instance (using MockTaskProgressTracker which now correctly maps)
    mock_tracker_instance = MagicMock()
    MockTaskProgressTracker.return_value = mock_tracker_instance

    # --- Call and Assert ---
    generate_report(task_id="task-456")

    # Assertions
    # Assert Task.get_by_id was called (using MockTask)
    MockTask.get_by_id.assert_called_once_with("task-456", mock_client_instance)
    # Assert _load_report_configuration was called (using mock_load_config)
    mock_load_config.assert_called_once_with(mock_client_instance, "non-existent-config-id")

    # Verify the TaskProgressTracker's fail method was called
    mock_tracker_instance.fail.assert_called_once()
    fail_args, _ = mock_tracker_instance.fail.call_args
    assert isinstance(fail_args[0], str)
    assert "ReportConfiguration not found" in fail_args[0]

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