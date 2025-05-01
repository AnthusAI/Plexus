import pytest
import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from plexus.cli.task_progress_tracker import TaskProgressTracker, Stage, StageConfig

# Add a DummyAPITask class for mocking that includes is_local attribute
class DummyAPITask:
    def __init__(self, id="dummy-task-id"):
        self.id = id
        self.status = "PENDING"
        self.accountId = "test-account"
        self.type = "TEST"
        self.target = "test/target"
        self.command = "test command"
        self.total_items = None
        self._stages = {}
        self.is_local = True  # This attribute is checked in the implementation
        self.startedAt = datetime.now(timezone.utc)

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
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self

    def complete_processing(self):
        self.status = "COMPLETED"
        for stage in self._stages.values():
            if stage.status != "FAILED":
                stage.status = "COMPLETED"

class DummyAPIStage:
    def __init__(self, name, order):
        self.id = f"dummy-stage-{name}"
        self.name = name
        self.order = order
        self.status = "PENDING"
        self.status_message = None
        self.total_items = None
        self.processed_items = None
        self.start_time = None
        self.end_time = None

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self

@pytest.fixture
def mock_task_create():
    """Fixture to mock Task.create method for tests"""
    with patch("plexus.dashboard.api.models.task.Task.create") as mock_create:
        dummy_task = DummyAPITask()
        mock_create.return_value = dummy_task
        # Patch threading.Thread to run synchronously
        with patch('threading.Thread', MagicMock()) as mock_thread:
            # Make the thread start run the target function immediately
            def run_target():
                if 'target' in mock_thread.call_args.kwargs:
                    target = mock_thread.call_args.kwargs['target']
                    args = mock_thread.call_args.kwargs.get('args', ())
                    kwargs = mock_thread.call_args.kwargs.get('kwargs', {})
                    target(*args, **kwargs)
            mock_thread.return_value.start = run_target
            yield dummy_task

def test_basic_progress_tracking():
    default_stages = {
        "Default": StageConfig(order=1, total_items=100, status_message="Processing")
    }
    tracker = TaskProgressTracker(total_items=100, stage_configs=default_stages, prevent_new_task=True)
    assert tracker.total_items == 100
    assert tracker.current_items == 0
    assert tracker.progress == 0
    assert tracker.status == "Not started"

def test_update_progress():
    default_stages = {
        "Default": StageConfig(order=1, total_items=100, status_message="Processing")
    }
    tracker = TaskProgressTracker(total_items=100, stage_configs=default_stages, prevent_new_task=True)
    tracker.update(current_items=50, status="Processing")
    assert tracker.current_items == 50
    assert tracker.progress == 50
    assert tracker.status == "Processing"

def test_elapsed_time():
    default_stages = {
        "Default": StageConfig(order=1, total_items=100, status_message="Processing")
    }
    tracker = TaskProgressTracker(total_items=100, stage_configs=default_stages)
    time.sleep(1)  # Sleep to ensure elapsed time
    elapsed = tracker.elapsed_time
    assert elapsed >= 1.0
    assert isinstance(elapsed, float)

def test_estimated_time_remaining(mock_task_create):
    default_stages = {
        "Default": StageConfig(order=1, total_items=100, status_message="Processing")
    }
    tracker = TaskProgressTracker(
        total_items=100, 
        stage_configs=default_stages, 
        prevent_new_task=False,
        command="test",
        target="test"
    )
    
    # Start the tracker
    tracker._stages["Default"].start()
    time.sleep(1)  # Process for 1 second
    tracker.update(current_items=50)  # Update halfway through
    
    # If 50 items took 1 second, remaining 50 should take ~1 second
    # But allow for more variation in timing
    eta = tracker.estimated_time_remaining
    assert isinstance(eta, float)
    # Wider tolerance for timing variations in CI environments
    assert 0.5 <= eta <= 2.0  # More lenient assertion

def test_stage_management(mock_task_create):
    stage_configs = {
        "Setup": StageConfig(
            order=1,
            status_message="Setting up"
        ),
        "Processing": StageConfig(
            order=2,
            total_items=100,
            status_message="Processing items"
        ),
        "Cleanup": StageConfig(
            order=3,
            status_message="Cleaning up"
        )
    }
    
    tracker = TaskProgressTracker(
        total_items=100, 
        stage_configs=stage_configs,
        prevent_new_task=False,
        command="test",
        target="test"
    )
    
    # Manually start the first stage since we're using a mock task
    tracker._stages["Setup"].start()
    
    # Check initial stage
    assert tracker.current_stage.name == "Setup"
    assert tracker.current_stage.order == 1
    
    # Move to next stage
    tracker.advance_stage()
    assert tracker.current_stage.name == "Processing"
    assert tracker.current_stage.order == 2
    
    # Update progress in current stage
    tracker.update(current_items=50)
    assert tracker.current_stage.processed_items == 50
    
    # Complete all stages
    tracker.advance_stage()
    assert tracker.current_stage.name == "Cleanup"
    tracker.complete()
    assert tracker.is_complete

def test_context_manager(mock_task_create):
    default_stages = {
        "Default": StageConfig(order=1, total_items=100, status_message="Processing")
    }
    with TaskProgressTracker(
        total_items=100, 
        stage_configs=default_stages, 
        prevent_new_task=False,
        command="test",
        target="test"
    ) as tracker:
        # Manually start the first stage since we're using a mock task
        tracker._stages["Default"].start()
        
        assert tracker.total_items == 100
        tracker.update(current_items=50)
        assert tracker.current_items == 50
    
    # After context exit, tracker should be complete
    assert tracker.is_complete

def test_error_handling():
    default_stages = {
        "Default": StageConfig(order=1, total_items=100, status_message="Processing")
    }
    tracker = TaskProgressTracker(total_items=100, stage_configs=default_stages, prevent_new_task=True)
    
    # Manually start the stage for the test
    tracker._stages["Default"].start()
    
    # Test invalid updates
    # The tracker should not raise errors for values that exceed the total
    # It should clamp values instead for better user experience
    tracker.update(current_items=150)  # Should clamp to 100
    assert tracker.current_items == 100
    
    # Test negative values - these should be clamped to 0
    tracker.update(current_items=-10)
    assert tracker.current_items == 0
    
    # Test completing without going through all stages
    stage_configs = {
        "Stage1": StageConfig(order=1, total_items=50),
        "Stage2": StageConfig(order=2, total_items=50)
    }
    multi_stage_tracker = TaskProgressTracker(total_items=100, stage_configs=stage_configs)
    # Start the first stage
    multi_stage_tracker._stages["Stage1"].start()
    
    # This should not raise an error - the implementation should handle this case
    multi_stage_tracker.complete()
    assert multi_stage_tracker.is_complete

def test_status_message_generation():
    default_stages = {
        "Default": StageConfig(
            order=1,
            total_items=100,
            status_message=None  # Explicitly set to None to allow dynamic messages
        )
    }
    tracker = TaskProgressTracker(total_items=100, stage_configs=default_stages, prevent_new_task=True)
    
    # Start the stage for the test
    tracker._stages["Default"].start()
    tracker._current_stage_name = "Default"
    
    # Test different progress levels
    tracker.update(current_items=5)
    status = tracker._generate_status_message()
    assert "5%" in status or "5.0%" in status
    
    tracker.update(current_items=50)
    status = tracker._generate_status_message()
    assert "50%" in status or "50.0%" in status
    
    tracker.update(current_items=100)
    status = tracker._generate_status_message()
    assert "100%" in status or "Complete" in status

def test_estimated_completion_time(mock_task_create):
    default_stages = {
        "Default": StageConfig(order=1, total_items=100, status_message="Processing")
    }
    tracker = TaskProgressTracker(
        total_items=100, 
        stage_configs=default_stages, 
        prevent_new_task=False,
        command="test",
        target="test"
    )
    
    # Manually start the first stage
    tracker._stages["Default"].start()
    time.sleep(1)  # Process for 1 second
    tracker.update(current_items=50)  # Update halfway through
    
    completion_time = tracker.estimated_completion_time
    assert isinstance(completion_time, datetime)
    assert completion_time.tzinfo == timezone.utc
    
    # Should be roughly 1 second from now, but allow more tolerance
    now = datetime.now(timezone.utc)
    diff = (completion_time - now).total_seconds()
    # More flexible assertion for CI environment timing variations
    assert 0.5 <= diff <= 2.5

def test_items_per_second(mock_task_create):
    default_stages = {
        "Default": StageConfig(order=1, total_items=100, status_message="Processing")
    }
    tracker = TaskProgressTracker(
        total_items=100, 
        stage_configs=default_stages,
        prevent_new_task=False,
        command="test",
        target="test"
    )
    
    # Manually start the first stage
    tracker._stages["Default"].start()
    time.sleep(1)  # Process for 1 second
    tracker.update(current_items=50)  # 50 items in 1 second
    
    items_per_sec = tracker.items_per_second
    assert isinstance(items_per_sec, float)
    # More flexible assertion for CI environment timing variations
    assert 25 <= items_per_sec <= 75  # Wider range for timing variance 