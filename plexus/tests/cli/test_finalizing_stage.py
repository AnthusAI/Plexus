import time
import logging
import os
from plexus.cli.task_progress_tracker import TaskProgressTracker, StageConfig
from unittest.mock import patch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True  # Override any existing logging configuration
)

# Add dummy API classes to simulate API task behavior without real cloud calls

class DummyAPIStage:
    def __init__(self, name, order):
        self.name = name
        self.order = order
        self.id = f"dummy_stage_{name}"
        self.status = "PENDING"
        self.status_message = None
        self.total_items = None
        self.processed_items = None
        self.start_time = None
        self.end_time = None

    def update(self, **kwargs):
        # Update any properties that are passed in
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self

class DummyAPITask:
    def __init__(self, id):
        self.id = id
        self._stages = {}

    def get_stages(self):
        return list(self._stages.values())

    def create_stage(self, name, order, **kwargs):
        stage = DummyAPIStage(name, order)
        # Apply any additional properties passed in kwargs
        for key, value in kwargs.items():
            setattr(stage, key, value)
        self._stages[name] = stage
        return stage

    def advance_stage(self, next_api_stage):
        pass

    def update(self, **kwargs):
        pass

    def complete_processing(self):
        pass

# Modify the test function to patch Task.create
@patch("plexus.dashboard.api.models.task.Task.create", autospec=True)

def test_finalizing_stage_progress(mock_create):
    dummy_task = DummyAPITask("dummy_task_id")
    mock_create.return_value = dummy_task

    """Test that stages are properly created, updated and visible in the UI.
    
    This test demonstrates the proper way to configure task stages for UI visibility:
    - Only stages that should show progress bars should have total_items set
    - Setup and Finalizing stages should NOT have processedItems or totalItems set at all
    - The Processing stage is the main stage that shows progress
    """
    # Configure stages with UI-specific properties
    stage_configs = {
        "Setup": StageConfig(
            order=1,
            status_message="Setting up task..."
            # No total_items - setup stage should not show progress bar
        ),
        "Processing": StageConfig(
            order=2, 
            total_items=100,  # Only Processing stage shows progress
            status_message="Processing items..."
        ),
        "Finalizing": StageConfig(
            order=3,
            status_message="Finalizing results..."
            # No total_items - finalizing stage should not show progress bar
        )
    }

    # Create progress tracker
    tracker = TaskProgressTracker(
        total_items=100,  # This is for the overall task progress
        stage_configs=stage_configs,
        command="test",
        target="test",
        prevent_new_task=False
    )

    # Verify initial stage setup
    assert tracker.current_stage.name == "Setup"
    assert tracker.current_stage.total_items is None  # Setup stage has no progress bar
    assert tracker.current_stage.processed_items is None
    assert tracker.current_stage.status == "RUNNING"
    assert tracker.current_stage.status_message == "Setting up task..."

    # Process Setup stage (no progress updates needed)
    time.sleep(2)  # Wait for API update
    
    # Advance to Processing stage
    tracker.advance_stage()
    time.sleep(2)  # Wait for API update
    
    # Verify Processing stage started correctly with progress tracking
    assert tracker.current_stage.name == "Processing"
    assert tracker.current_stage.total_items == 100
    assert tracker.current_stage.status == "RUNNING"
    assert tracker.current_stage.status_message == "Processing items..."

    # Process items in smaller batches with longer delays
    for i in range(0, 101, 25):  # Use 25 as step size to reach 100 evenly
        tracker.update(current_items=i if i > 0 else 1)  # Start with 1 instead of 0
        time.sleep(2)  # Wait for API updates
        
        # Verify Processing stage progress
        assert tracker.current_stage.processed_items == (i if i > 0 else 1)
        assert tracker.current_stage.total_items == 100
        assert tracker.current_stage.status == "RUNNING"

    # Make sure we hit 100
    tracker.update(current_items=100)
    time.sleep(2)  # Wait for API updates

    # Verify final processing stage state
    assert tracker.current_stage.processed_items == 100
    assert tracker.current_stage.total_items == 100
    assert tracker.current_stage.status == "RUNNING"

    # Advance to Finalizing stage
    tracker.advance_stage()
    time.sleep(2)  # Wait for API update
    
    # Verify Finalizing stage started without progress tracking
    assert tracker.current_stage.name == "Finalizing"
    assert tracker.current_stage.total_items is None
    assert tracker.current_stage.processed_items is None
    assert tracker.current_stage.status == "RUNNING"
    assert tracker.current_stage.status_message == "Finalizing results..."

    # Complete the task
    tracker.complete()
    time.sleep(2)  # Wait for final API update
    
    # Verify final state
    assert tracker.is_complete
    assert tracker.current_items == tracker.total_items
    assert tracker.current_stage.status == "COMPLETED"

    # Verify final state of all stages
    for name, stage in tracker._stages.items():
        # Common assertions for all stages
        assert stage.status == "COMPLETED"
        assert stage.status_message is not None
        
        # Stage-specific assertions
        if name == "Processing":
            # Only Processing stage should have progress tracking
            assert stage.total_items == 100
            assert stage.processed_items == 100
        else:
            # Setup and Finalizing stages should not have progress tracking
            assert stage.total_items is None, f"{name} stage should not have total_items set"
            assert stage.processed_items is None, f"{name} stage should not have processed_items set"

if __name__ == "__main__":
    print("Running finalizing stage progress test...")
    test_finalizing_stage_progress()
    print("Test completed successfully!") 