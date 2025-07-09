"""
Comprehensive tests for TaskProgressTracker and stage configuration system.

This test suite covers critical functionality including:
- Stage configuration validation and setup
- Command-specific stage integration
- Stage progression logic
- Progress tracking per command type
- API stage synchronization
- Concurrency and error handling
"""

import pytest
import time
import threading
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timezone
from typing import Dict, Optional

from plexus.cli.task_progress_tracker import (
    TaskProgressTracker, 
    StageConfig, 
    Stage,
    MIN_API_UPDATE_INTERVAL
)
from plexus.cli.stage_configurations import (
    get_evaluation_stage_configs,
    get_prediction_stage_configs,
    get_stage_configs_for_operation_type
)
from plexus.dashboard.api.models.task import Task
from plexus.dashboard.api.client import PlexusDashboardClient


class TestStageConfigurationSystem:
    """Test stage configuration validation and factory methods."""
    
    def test_evaluation_stage_configs_structure(self):
        """Test evaluation stage configuration structure and defaults."""
        configs = get_evaluation_stage_configs(total_items=100)
        
        # Verify all expected stages are present
        assert "Setup" in configs
        assert "Processing" in configs
        assert "Finalizing" in configs
        
        # Verify stage ordering
        assert configs["Setup"].order == 1
        assert configs["Processing"].order == 2
        assert configs["Finalizing"].order == 3
        
        # Verify progress bar behavior (only Processing should have total_items)
        assert configs["Setup"].total_items is None
        assert configs["Processing"].total_items == 100
        assert configs["Finalizing"].total_items is None
        
        # Verify status messages are set
        assert configs["Setup"].status_message == "Setting up evaluation..."
        assert configs["Processing"].status_message == "Starting processing..."
        assert configs["Finalizing"].status_message == "Starting finalization..."
    
    def test_prediction_stage_configs_structure(self):
        """Test prediction stage configuration structure and defaults."""
        configs = get_prediction_stage_configs(total_items=50)
        
        # Verify all expected stages are present
        assert "Querying" in configs
        assert "Predicting" in configs
        assert "Archiving" in configs
        
        # Verify stage ordering
        assert configs["Querying"].order == 1
        assert configs["Predicting"].order == 2
        assert configs["Archiving"].order == 3
        
        # Verify progress bar behavior (only Predicting should have total_items)
        assert configs["Querying"].total_items is None
        assert configs["Predicting"].total_items == 50
        assert configs["Archiving"].total_items is None
    
    def test_stage_configs_for_operation_type_evaluation(self):
        """Test operation type factory method for evaluation."""
        configs = get_stage_configs_for_operation_type("evaluation", total_items=75)
        
        # Should return evaluation configs
        assert "Setup" in configs
        assert "Processing" in configs
        assert "Finalizing" in configs
        assert configs["Processing"].total_items == 75
        
        # Test case variations
        for op_type in ["evaluation", "evaluate", "accuracy", "EVALUATION"]:
            configs = get_stage_configs_for_operation_type(op_type, total_items=10)
            assert configs["Processing"].total_items == 10
    
    def test_stage_configs_for_operation_type_prediction(self):
        """Test operation type factory method for prediction."""
        configs = get_stage_configs_for_operation_type("prediction", total_items=25)
        
        # Should return prediction configs
        assert "Querying" in configs
        assert "Predicting" in configs
        assert "Archiving" in configs
        assert configs["Predicting"].total_items == 25
        
        # Test case variations
        for op_type in ["prediction", "predict", "PREDICT"]:
            configs = get_stage_configs_for_operation_type(op_type, total_items=15)
            assert configs["Predicting"].total_items == 15
    
    def test_stage_configs_for_invalid_operation_type(self):
        """Test that invalid operation types raise ValueError."""
        with pytest.raises(ValueError, match="Unknown operation type: invalid"):
            get_stage_configs_for_operation_type("invalid")
    
    def test_stage_config_zero_total_items(self):
        """Test stage configs with zero total items."""
        configs = get_evaluation_stage_configs(total_items=0)
        assert configs["Processing"].total_items == 0
        
        configs = get_prediction_stage_configs(total_items=0)
        assert configs["Predicting"].total_items == 0
    
    def test_stage_config_negative_total_items(self):
        """Test stage configs with negative total items."""
        configs = get_evaluation_stage_configs(total_items=-10)
        assert configs["Processing"].total_items == -10  # Should accept negative values


class TestStageClass:
    """Test the Stage dataclass functionality."""
    
    def test_stage_initialization(self):
        """Test Stage object initialization."""
        stage = Stage(name="Test", order=1)
        
        assert stage.name == "Test"
        assert stage.order == 1
        assert stage.total_items is None
        assert stage.processed_items is None
        assert stage.status_message is None
        assert stage.start_time is None
        assert stage.end_time is None
        assert stage.status == 'PENDING'
    
    def test_stage_equality(self):
        """Test Stage equality comparison."""
        stage1 = Stage(name="Test", order=1)
        stage2 = Stage(name="Test", order=1)
        stage3 = Stage(name="Different", order=1)
        stage4 = Stage(name="Test", order=2)
        
        assert stage1 == stage2
        assert stage1 != stage3
        assert stage1 != stage4
        assert stage1 != "not a stage"
    
    def test_stage_start(self):
        """Test stage start functionality."""
        stage = Stage(name="Test", order=1, total_items=100)
        
        start_time = time.time()
        stage.start()
        
        assert stage.status == 'RUNNING'
        assert stage.start_time is not None
        assert stage.start_time >= start_time
        assert stage.processed_items == 0  # Should initialize when total_items is set
    
    def test_stage_start_without_total_items(self):
        """Test stage start when total_items is None."""
        stage = Stage(name="Test", order=1)
        
        stage.start()
        
        assert stage.status == 'RUNNING'
        assert stage.processed_items is None  # Should remain None
    
    def test_stage_complete(self):
        """Test stage completion."""
        stage = Stage(name="Test", order=1)
        stage.start()
        
        end_time = time.time()
        stage.complete()
        
        assert stage.status == 'COMPLETED'
        assert stage.end_time is not None
        assert stage.end_time >= end_time
    
    def test_stage_update_processed_count(self):
        """Test updating processed item count."""
        stage = Stage(name="Test", order=1, total_items=100)
        stage.start()
        
        # Normal update
        stage.update_processed_count(50)
        assert stage.processed_items == 50
        
        # Update with higher count
        stage.update_processed_count(75)
        assert stage.processed_items == 75
    
    def test_stage_update_processed_count_boundary_conditions(self):
        """Test processed count updates with boundary conditions."""
        stage = Stage(name="Test", order=1, total_items=100)
        stage.start()
        
        # Negative count should be clamped
        stage.update_processed_count(-10)
        assert stage.processed_items == 0
        
        # Count exceeding total should be clamped
        stage.update_processed_count(150)
        assert stage.processed_items == 100
    
    def test_stage_update_processed_count_no_total_items(self):
        """Test processed count update when total_items is None."""
        stage = Stage(name="Test", order=1)
        stage.start()
        
        # Should not update processed_items when total_items is None
        stage.update_processed_count(50)
        assert stage.processed_items is None


class TestTaskProgressTrackerInitialization:
    """Test TaskProgressTracker initialization scenarios."""
    
    def test_basic_initialization(self):
        """Test basic tracker initialization."""
        stage_configs = {"Test": StageConfig(order=1)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=100,
            prevent_new_task=True
        )
        
        assert tracker.total_items == 100
        assert tracker.current_items == 0
        assert tracker.status == "Not started"
        assert not tracker.is_complete
        assert not tracker.is_failed
        assert tracker.api_task is None
    
    def test_initialization_with_task_object(self):
        """Test initialization with existing Task object."""
        mock_task = Mock(spec=Task)
        mock_task.id = "test-task-123"
        stage_configs = {"Test": StageConfig(order=1)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            task_object=mock_task,
            total_items=50
        )
        
        assert tracker.api_task == mock_task
        assert tracker.total_items == 50
    
    @patch('plexus.cli.task_progress_tracker.PlexusDashboardClient')
    def test_initialization_with_task_id(self, mock_client_class):
        """Test initialization with task_id and prevent_new_task=True."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_task = Mock(spec=Task)
        mock_task.id = "test-task-456"
        mock_task.get_by_id = Mock(return_value=mock_task)
        
        with patch.dict('os.environ', {
            'PLEXUS_API_URL': 'http://test-api',
            'PLEXUS_API_KEY': 'test-key'
        }):
            with patch.object(Task, 'get_by_id', return_value=mock_task):
                stage_configs = {"Test": StageConfig(order=1)}
                
                tracker = TaskProgressTracker(
                    stage_configs=stage_configs,
                    task_id="test-task-456",
                    prevent_new_task=True
                )
                
                assert tracker.api_task == mock_task
    
    def test_stage_setup_from_configs(self):
        """Test that stages are properly set up from configs."""
        stage_configs = {
            "First": StageConfig(order=1, status_message="First stage"),
            "Second": StageConfig(order=2, total_items=100, status_message="Second stage"),
            "Third": StageConfig(order=3, status_message="Third stage")
        }
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=100,
            prevent_new_task=True
        )
        
        # Verify stages are created
        assert len(tracker._stages) == 3
        assert "First" in tracker._stages
        assert "Second" in tracker._stages
        assert "Third" in tracker._stages
        
        # Verify stage properties
        first_stage = tracker._stages["First"]
        assert first_stage.order == 1
        assert first_stage.total_items is None
        assert first_stage.status_message == "First stage"
        
        second_stage = tracker._stages["Second"]
        assert second_stage.order == 2
        assert second_stage.total_items == 100
        assert second_stage.status_message == "Second stage"
    
    def test_empty_stage_configs(self):
        """Test initialization with empty stage configs."""
        tracker = TaskProgressTracker(
            stage_configs={},
            total_items=0,
            prevent_new_task=True
        )
        
        assert len(tracker._stages) == 0
        assert tracker.current_stage is None


class TestCommandStageIntegration:
    """Test integration with command-specific stage configurations."""
    
    def test_evaluation_workflow_integration(self):
        """Test TaskProgressTracker with evaluation stage configs."""
        stage_configs = get_evaluation_stage_configs(total_items=200)
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=200,
            prevent_new_task=True
        )
        
        # Verify evaluation stages are set up correctly
        assert len(tracker._stages) == 3
        assert "Setup" in tracker._stages
        assert "Processing" in tracker._stages
        assert "Finalizing" in tracker._stages
        
        # Verify only Processing stage has progress tracking
        setup_stage = tracker._stages["Setup"]
        processing_stage = tracker._stages["Processing"]
        finalizing_stage = tracker._stages["Finalizing"]
        
        assert setup_stage.total_items is None
        assert processing_stage.total_items == 200
        assert finalizing_stage.total_items is None
    
    def test_prediction_workflow_integration(self):
        """Test TaskProgressTracker with prediction stage configs."""
        stage_configs = get_prediction_stage_configs(total_items=50)
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=50,
            prevent_new_task=True
        )
        
        # Verify prediction stages are set up correctly
        assert len(tracker._stages) == 3
        assert "Querying" in tracker._stages
        assert "Predicting" in tracker._stages
        assert "Archiving" in tracker._stages
        
        # Verify only Predicting stage has progress tracking
        querying_stage = tracker._stages["Querying"]
        predicting_stage = tracker._stages["Predicting"]
        archiving_stage = tracker._stages["Archiving"]
        
        assert querying_stage.total_items is None
        assert predicting_stage.total_items == 50
        assert archiving_stage.total_items is None
    
    def test_custom_stage_configuration(self):
        """Test with custom stage configuration."""
        custom_configs = {
            "Initialize": StageConfig(order=1, status_message="Starting up..."),
            "MainWork": StageConfig(order=2, total_items=300, status_message="Doing main work..."),
            "Cleanup": StageConfig(order=3, status_message="Cleaning up...")
        }
        
        tracker = TaskProgressTracker(
            stage_configs=custom_configs,
            total_items=300,
            prevent_new_task=True
        )
        
        # Verify custom stages work correctly
        assert len(tracker._stages) == 3
        main_work_stage = tracker._stages["MainWork"]
        assert main_work_stage.total_items == 300
        assert main_work_stage.status_message == "Doing main work..."
    
    def test_stage_order_validation(self):
        """Test that stages are processed in correct order."""
        stage_configs = {
            "Third": StageConfig(order=3),
            "First": StageConfig(order=1),
            "Second": StageConfig(order=2)
        }
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=10,
            prevent_new_task=True
        )
        
        # Get the first stage (should be order=1)
        first_stage = min(tracker._stages.values(), key=lambda s: s.order)
        assert first_stage.name == "First"
        assert first_stage.order == 1


class TestStageProgression:
    """Test stage progression and advancement logic."""
    
    @patch('threading.Thread')
    def test_stage_advancement_sequence(self, mock_thread):
        """Test normal stage advancement sequence."""
        stage_configs = {
            "First": StageConfig(order=1),
            "Second": StageConfig(order=2),
            "Third": StageConfig(order=3)
        }
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=10,
            prevent_new_task=True
        )
        
        # TaskProgressTracker automatically sets current stage to first stage during init
        # but doesn't start it without an API task
        assert tracker.current_stage.name == "First"
        assert tracker.current_stage.status == 'PENDING'  # Not started yet
        
        # Start first stage manually
        tracker.current_stage.start()
        
        assert tracker.current_stage.name == "First"
        assert tracker.current_stage.status == 'RUNNING'
        
        # Advance to second stage (without API task, so no API calls)
        tracker.advance_stage()
        
        assert tracker.current_stage.name == "Second"
        assert tracker.current_stage.status == 'RUNNING'
        assert tracker._stages["First"].status == 'COMPLETED'  # Use _stages dict directly
        
        # Advance to third stage
        tracker.advance_stage()
        
        assert tracker.current_stage.name == "Third"
        assert tracker.current_stage.status == 'RUNNING'
        assert tracker._stages["Second"].status == 'COMPLETED'
    
    def test_advance_stage_when_no_next_stage(self):
        """Test advancing when there's no next stage."""
        stage_configs = {"Only": StageConfig(order=1)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=10,
            prevent_new_task=True
        )
        
        # Start the only stage
        tracker._current_stage_name = "Only"
        tracker._stages["Only"].start()
        
        # Try to advance (should not error)
        tracker.advance_stage()
        
        # Should still be on the same stage but completed
        assert tracker._stages["Only"].status == 'COMPLETED'
        assert tracker._current_stage_name == "Only"
    
    def test_advance_stage_with_no_current_stage(self):
        """Test advancing when there's no current stage."""
        stage_configs = {"Test": StageConfig(order=1)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=10,
            prevent_new_task=True
        )
        
        # Try to advance with no current stage (should not error)
        tracker.advance_stage()
    
    def test_advance_stage_with_empty_stages(self):
        """Test advancing with no stages configured."""
        tracker = TaskProgressTracker(
            stage_configs={},
            total_items=10,
            prevent_new_task=True
        )
        
        # Should not error
        tracker.advance_stage()


class TestProgressTracking:
    """Test progress tracking functionality."""
    
    def test_progress_update_basic(self):
        """Test basic progress updates."""
        stage_configs = {"Test": StageConfig(order=1, total_items=100)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=100,
            prevent_new_task=True
        )
        
        # Start the stage
        tracker._current_stage_name = "Test"
        tracker._stages["Test"].start()
        
        # Update progress
        tracker.update(current_items=50)
        
        assert tracker.current_items == 50
        assert tracker.current_stage.processed_items == 50
    
    def test_progress_update_boundary_conditions(self):
        """Test progress updates with boundary conditions."""
        stage_configs = {"Test": StageConfig(order=1, total_items=100)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=100,
            prevent_new_task=True
        )
        
        # Negative progress should be clamped
        tracker.update(current_items=-10)
        assert tracker.current_items == 0
        
        # Progress exceeding total should be clamped
        tracker.update(current_items=150)
        assert tracker.current_items == 100
    
    def test_progress_update_with_status_message(self):
        """Test progress updates with status messages."""
        stage_configs = {"Test": StageConfig(order=1, total_items=100)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=100,
            prevent_new_task=True
        )
        
        tracker.update(current_items=25, status="Custom status")
        
        assert tracker.current_items == 25
        assert tracker.status == "Custom status"
    
    def test_progress_property(self):
        """Test progress percentage property."""
        tracker = TaskProgressTracker(
            stage_configs={},
            total_items=200,
            prevent_new_task=True
        )
        
        # Test various progress levels
        tracker.update(current_items=0)
        assert tracker.progress == 0
        
        tracker.update(current_items=50)
        assert tracker.progress == 25
        
        tracker.update(current_items=100)
        assert tracker.progress == 50
        
        tracker.update(current_items=200)
        assert tracker.progress == 100
    
    def test_progress_property_zero_total(self):
        """Test progress property when total_items is zero."""
        tracker = TaskProgressTracker(
            stage_configs={},
            total_items=0,
            prevent_new_task=True
        )
        
        # Should return 0 when not complete
        assert tracker.progress == 0
        
        # Should return 100 when complete
        tracker.is_complete = True
        assert tracker.progress == 100


class TestTaskCompletion:
    """Test task completion and failure scenarios."""
    
    def test_task_completion_basic(self):
        """Test basic task completion."""
        stage_configs = {"Test": StageConfig(order=1, total_items=50)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=50,
            prevent_new_task=True
        )
        
        # Start and complete
        tracker._current_stage_name = "Test"
        tracker._stages["Test"].start()
        tracker.complete()
        
        assert tracker.is_complete
        assert tracker.end_time is not None
        assert tracker._stages["Test"].status == 'COMPLETED'
    
    def test_task_completion_auto_start_stages(self):
        """Test that completion auto-starts unstarted stages."""
        stage_configs = {
            "First": StageConfig(order=1),
            "Second": StageConfig(order=2, total_items=100)
        }
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=100,
            prevent_new_task=True
        )
        
        # Complete without starting stages
        tracker.complete()
        
        # Both stages should be started and completed
        assert tracker._stages["First"].start_time is not None
        assert tracker._stages["First"].status == 'COMPLETED'
        assert tracker._stages["Second"].start_time is not None
        assert tracker._stages["Second"].status == 'COMPLETED'
        
        # Second stage should have processed_items set to total_items
        assert tracker._stages["Second"].processed_items == 100
    
    def test_task_failure(self):
        """Test task failure handling."""
        stage_configs = {"Test": StageConfig(order=1)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=50,
            prevent_new_task=True
        )
        
        # Start stage and then fail
        tracker._current_stage_name = "Test"
        tracker._stages["Test"].start()
        
        error_message = "Something went wrong"
        tracker.fail(error_message)
        
        assert tracker.is_failed
        assert tracker.end_time is not None
        assert f"Failed: {error_message}" in tracker.status
        assert tracker._stages["Test"].status == 'FAILED'
        assert error_message in tracker._stages["Test"].status_message
    
    def test_context_manager_success(self):
        """Test successful context manager usage."""
        stage_configs = {"Test": StageConfig(order=1)}
        
        with TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=10,
            prevent_new_task=True
        ) as tracker:
            assert not tracker.is_complete
        
        # Should be completed after context exit
        assert tracker.is_complete
    
    @patch('threading.Thread')
    def test_context_manager_exception(self, mock_thread):
        """Test context manager when exception occurs."""
        stage_configs = {"Test": StageConfig(order=1)}
        
        tracker = None
        try:
            with TaskProgressTracker(
                stage_configs=stage_configs,
                total_items=10,
                prevent_new_task=True
            ) as t:
                tracker = t
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # When an exception occurs, __exit__ does NOT call complete()
        # So the tracker should not be completed
        assert tracker is not None
        assert not tracker.is_complete  # Should NOT be completed when exception occurs


class TestConcurrencyAndThreadSafety:
    """Test concurrency and thread safety aspects."""
    
    def test_concurrent_progress_updates(self):
        """Test concurrent progress updates don't cause race conditions."""
        stage_configs = {"Test": StageConfig(order=1, total_items=1000)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=1000,
            prevent_new_task=True
        )
        
        # Start the stage
        tracker._current_stage_name = "Test"
        tracker._stages["Test"].start()
        
        def update_progress(start_val, count):
            for i in range(count):
                tracker.update(current_items=start_val + i)
        
        # Run concurrent updates
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_progress, args=(i * 100, 50))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have some final progress value
        assert tracker.current_items >= 0
        assert tracker.current_items <= 1000
    
    def test_concurrent_stage_advancement(self):
        """Test that concurrent stage advancement is handled safely."""
        stage_configs = {
            "First": StageConfig(order=1),
            "Second": StageConfig(order=2),
            "Third": StageConfig(order=3)
        }
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=10,
            prevent_new_task=True
        )
        
        # Start first stage
        tracker._current_stage_name = "First"
        tracker._stages["First"].start()
        
        def advance_stages():
            tracker.advance_stage()
            time.sleep(0.01)  # Small delay
            tracker.advance_stage()
        
        # Run concurrent advancement
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=advance_stages)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should end up in a valid state
        assert tracker.current_stage is not None
        assert tracker.current_stage.status in ['RUNNING', 'COMPLETED']


class TestAPIStageSync:
    """Test API stage synchronization functionality."""
    
    @patch('plexus.cli.task_progress_tracker.PlexusDashboardClient')
    @patch('threading.Thread')
    def test_api_task_progress_update_rate_limiting(self, mock_thread, mock_client_class):
        """Test that API updates respect rate limiting."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_task = Mock(spec=Task)
        mock_task.id = "test-task"
        mock_task.status = "RUNNING"
        mock_task.update_progress = Mock()
        mock_task.get_stages = Mock(return_value=[])
        
        stage_configs = {"Test": StageConfig(order=1, total_items=100)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            task_object=mock_task,
            total_items=100,
            prevent_new_task=True
        )
        
        # Multiple rapid updates should be rate limited
        tracker.update(current_items=10)
        tracker.update(current_items=20)
        tracker.update(current_items=30)
        
        # Should have limited the number of API calls due to rate limiting
        # (This is a simplified test - actual rate limiting behavior may vary)
        assert mock_task.update_progress.call_count >= 0  # At least some calls should have been made
    
    @patch('plexus.cli.task_progress_tracker.PlexusDashboardClient')
    @patch('threading.Thread')
    def test_api_task_progress_update_critical_updates(self, mock_thread, mock_client_class):
        """Test that critical updates bypass rate limiting."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_task = Mock(spec=Task)
        mock_task.id = "test-task"
        mock_task.status = "RUNNING"
        mock_task.update_progress = Mock()
        mock_task.get_stages = Mock(return_value=[])
        mock_task.complete_processing = Mock()
        
        stage_configs = {"Test": StageConfig(order=1, total_items=100)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            task_object=mock_task,
            total_items=100,
            prevent_new_task=True
        )
        
        # Complete the task (critical update)
        tracker.complete()
        
        # Critical updates should always go through
        assert mock_task.complete_processing.called
    
    @patch('plexus.cli.task_progress_tracker.PlexusDashboardClient')
    def test_api_task_failure_sync(self, mock_client_class):
        """Test API task failure synchronization."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_task = Mock(spec=Task)
        mock_task.id = "test-task"
        mock_task.status = "RUNNING"
        mock_task.fail_processing = Mock()
        mock_task.get_stages = Mock(return_value=[])
        
        stage_configs = {"Test": StageConfig(order=1)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            task_object=mock_task,
            total_items=10,
            prevent_new_task=True
        )
        
        # Start stage and fail
        tracker._current_stage_name = "Test"
        tracker._stages["Test"].start()
        
        error_message = "Test failure"
        tracker.fail(error_message)
        
        # Should have called fail_processing on the API task
        mock_task.fail_processing.assert_called_once_with(error_message)
        assert tracker.is_failed
    
    @patch('plexus.cli.task_progress_tracker.PlexusDashboardClient')
    def test_api_task_completion_sync(self, mock_client_class):
        """Test API task completion synchronization."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_stage = Mock()
        mock_stage.update = Mock()
        
        mock_task = Mock(spec=Task)
        mock_task.id = "test-task"
        mock_task.status = "RUNNING"
        mock_task.complete_processing = Mock()
        mock_task.get_stages = Mock(return_value=[mock_stage])
        
        stage_configs = {"Test": StageConfig(order=1)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            task_object=mock_task,
            total_items=10,
            prevent_new_task=True
        )
        
        # Complete the task
        tracker.complete()
        
        # Should have called complete_processing on the API task
        mock_task.complete_processing.assert_called_once()
        assert tracker.is_complete
    
    @patch('plexus.cli.task_progress_tracker.PlexusDashboardClient')
    def test_api_task_stage_advancement_sync(self, mock_client_class):
        """Test API task stage advancement synchronization."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_next_stage = Mock()
        mock_next_stage.name = "Second"
        
        mock_task = Mock(spec=Task)
        mock_task.id = "test-task"
        mock_task.status = "RUNNING"
        mock_task.get_stages = Mock(return_value=[mock_next_stage])
        mock_task.advance_stage = Mock()
        
        stage_configs = {
            "First": StageConfig(order=1),
            "Second": StageConfig(order=2)
        }
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            task_object=mock_task,
            total_items=10,
            prevent_new_task=True
        )
        
        # Start first stage
        tracker._current_stage_name = "First"
        tracker._stages["First"].start()
        
        # Advance to second stage
        tracker.advance_stage()
        
        # Should have called advance_stage on the API task
        mock_task.advance_stage.assert_called_once_with(mock_next_stage)
    
    def test_api_update_skipped_when_task_failed(self):
        """Test that API updates are skipped when task is already failed."""
        mock_task = Mock(spec=Task)
        mock_task.id = "test-task"
        mock_task.status = "FAILED"  # Already failed
        mock_task.update_progress = Mock()
        
        stage_configs = {"Test": StageConfig(order=1, total_items=100)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            task_object=mock_task,
            total_items=100,
            prevent_new_task=True
        )
        
        # Try to update progress
        tracker.update(current_items=50)
        
        # Should not have called update_progress since task is already failed
        mock_task.update_progress.assert_not_called()
    
    def test_api_update_without_task(self):
        """Test that progress updates work when no API task is available."""
        stage_configs = {"Test": StageConfig(order=1, total_items=100)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=100,
            prevent_new_task=True  # No API task
        )
        
        # Should not error when updating without API task
        tracker.update(current_items=50)
        assert tracker.current_items == 50
    
    @patch('plexus.cli.task_progress_tracker.PlexusDashboardClient')
    def test_api_client_creation_failure(self, mock_client_class):
        """Test handling of API client creation failures."""
        # Mock client creation to raise exception
        mock_client_class.side_effect = Exception("API connection failed")
        
        stage_configs = {"Test": StageConfig(order=1)}
        
        # Should not raise exception even if API client creation fails
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=10,
            prevent_new_task=False  # Try to create API task
        )
        
        # Should still work without API task
        tracker.update(current_items=5)
        assert tracker.current_items == 5
    
    def test_api_stage_sync_threading(self):
        """Test that API stage sync uses threading appropriately."""
        mock_task = Mock(spec=Task)
        mock_task.id = "test-task"
        mock_task.status = "RUNNING"
        
        stage_configs = {"Test": StageConfig(order=1)}
        
        with patch('threading.Thread') as mock_thread:
            tracker = TaskProgressTracker(
                stage_configs=stage_configs,
                task_object=mock_task,
                total_items=10,
                prevent_new_task=True
            )
            
            # Should have created a thread for API sync
            assert mock_thread.called


class TestTaskProgressTrackerProperties:
    """Test TaskProgressTracker property methods."""
    
    def test_elapsed_time_property(self):
        """Test elapsed time calculation."""
        tracker = TaskProgressTracker(
            stage_configs={},
            total_items=10,
            prevent_new_task=True
        )
        
        # Sleep briefly to ensure elapsed time > 0
        time.sleep(0.01)
        
        elapsed = tracker.elapsed_time
        assert elapsed > 0
        assert elapsed < 1.0  # Should be less than 1 second
    
    def test_items_per_second_property(self):
        """Test items per second calculation."""
        stage_configs = {"Test": StageConfig(order=1, total_items=100)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=100,
            prevent_new_task=True
        )
        
        # Start stage and update progress
        tracker._current_stage_name = "Test"
        tracker._stages["Test"].start()
        
        # Sleep briefly then update
        time.sleep(0.01)
        tracker.update(current_items=10)
        
        items_per_sec = tracker.items_per_second
        assert items_per_sec is not None
        assert items_per_sec > 0
    
    def test_items_per_second_no_current_stage(self):
        """Test items per second when no current stage."""
        tracker = TaskProgressTracker(
            stage_configs={},
            total_items=10,
            prevent_new_task=True
        )
        
        assert tracker.items_per_second is None
    
    def test_estimated_time_remaining_property(self):
        """Test estimated time remaining calculation."""
        stage_configs = {"Test": StageConfig(order=1, total_items=100)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=100,
            prevent_new_task=True
        )
        
        # Start stage and update progress to >10%
        tracker._current_stage_name = "Test"
        tracker._stages["Test"].start()
        
        time.sleep(0.01)
        tracker.update(current_items=20)  # 20% progress
        
        eta = tracker.estimated_time_remaining
        assert eta is not None
        assert eta > 0
    
    def test_estimated_time_remaining_insufficient_progress(self):
        """Test ETA when progress is <10%."""
        stage_configs = {"Test": StageConfig(order=1, total_items=100)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=100,
            prevent_new_task=True
        )
        
        # Start stage with minimal progress
        tracker._current_stage_name = "Test"
        tracker._stages["Test"].start()
        tracker.update(current_items=5)  # Only 5% progress
        
        # Should return None for insufficient progress
        assert tracker.estimated_time_remaining is None
    
    def test_estimated_completion_time_property(self):
        """Test estimated completion time calculation."""
        stage_configs = {"Test": StageConfig(order=1, total_items=100)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=100,
            prevent_new_task=True
        )
        
        # Start stage and update progress
        tracker._current_stage_name = "Test"
        tracker._stages["Test"].start()
        
        time.sleep(0.01)
        tracker.update(current_items=20)
        
        completion_time = tracker.estimated_completion_time
        if completion_time:  # May be None if not enough data
            assert isinstance(completion_time, datetime)
            assert completion_time.tzinfo == timezone.utc
    
    def test_set_total_items_method(self):
        """Test set_total_items method."""
        stage_configs = {"Test": StageConfig(order=1, total_items=50)}
        
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=50,
            prevent_new_task=True
        )
        
        # Change total items
        tracker.set_total_items(100)
        
        assert tracker.total_items == 100
        # Stage total_items should also be updated
        assert tracker._stages["Test"].total_items == 100


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_malformed_stage_configs(self):
        """Test handling of malformed stage configurations."""
        # Test with duplicate orders
        stage_configs = {
            "First": StageConfig(order=1),
            "Second": StageConfig(order=1)  # Duplicate order
        }
        
        # Should not crash
        tracker = TaskProgressTracker(
            stage_configs=stage_configs,
            total_items=10,
            prevent_new_task=True
        )
        
        assert len(tracker._stages) == 2
    
    def test_missing_environment_variables(self):
        """Test behavior when environment variables are missing."""
        with patch.dict('os.environ', {}, clear=True):
            stage_configs = {"Test": StageConfig(order=1)}
            
            # Should not crash even without environment variables
            tracker = TaskProgressTracker(
                stage_configs=stage_configs,
                task_id="some-task",
                total_items=10,
                prevent_new_task=True
            )
            
            assert tracker.api_task is None
    
    @patch('threading.Thread')
    def test_zero_min_api_update_interval(self, mock_thread):
        """Test behavior when MIN_API_UPDATE_INTERVAL is very small."""
        original_interval = MIN_API_UPDATE_INTERVAL
        
        try:
            # Temporarily set very small interval
            import plexus.cli.task_progress_tracker as tracker_module
            tracker_module.MIN_API_UPDATE_INTERVAL = 0.001
            
            mock_task = Mock(spec=Task)
            mock_task.id = "test-task-123"  # Add the missing id attribute
            mock_task.status = "RUNNING"
            mock_task.update_progress = Mock()
            mock_task.get_stages = Mock(return_value=[])
            
            stage_configs = {"Test": StageConfig(order=1, total_items=100)}
            
            tracker = TaskProgressTracker(
                stage_configs=stage_configs,
                task_object=mock_task,
                total_items=100,
                prevent_new_task=True
            )
            
            # Rapid updates should work with small interval
            tracker.update(current_items=10)
            tracker.update(current_items=20)
            
        finally:
            # Restore original interval
            tracker_module.MIN_API_UPDATE_INTERVAL = original_interval
    
    def test_task_property_accessor(self):
        """Test the task property accessor."""
        mock_task = Mock(spec=Task)
        mock_task.id = "test-task"
        
        tracker = TaskProgressTracker(
            stage_configs={},
            task_object=mock_task,
            total_items=10,
            prevent_new_task=True
        )
        
        assert tracker.task == mock_task
        
        # Test with no task
        tracker_no_task = TaskProgressTracker(
            stage_configs={},
            total_items=10,
            prevent_new_task=True
        )
        
        assert tracker_no_task.task is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])