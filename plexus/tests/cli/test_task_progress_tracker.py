import pytest
import time
from datetime import datetime, timezone
from plexus.cli.task_progress_tracker import TaskProgressTracker, Stage, StageConfig

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

def test_estimated_time_remaining():
    default_stages = {
        "Default": StageConfig(order=1, total_items=100, status_message="Processing")
    }
    tracker = TaskProgressTracker(total_items=100, stage_configs=default_stages, prevent_new_task=True)
    time.sleep(1)  # Process for 1 second
    tracker.update(current_items=50)  # Update halfway through
    # If 50 items took 1 second, remaining 50 should take ~1 second
    eta = tracker.estimated_time_remaining
    assert isinstance(eta, float)
    assert 0.8 <= eta <= 1.2  # Allow small margin of error

def test_stage_management():
    stage_configs = {
        "Setup": StageConfig(
            order=1,
            total_items=1,
            status_message="Setting up"
        ),
        "Processing": StageConfig(
            order=2,
            total_items=100,
            status_message="Processing items"
        ),
        "Cleanup": StageConfig(
            order=3,
            total_items=1,
            status_message="Cleaning up"
        )
    }
    
    tracker = TaskProgressTracker(total_items=100, stage_configs=stage_configs)
    
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

def test_context_manager():
    default_stages = {
        "Default": StageConfig(order=1, total_items=100, status_message="Processing")
    }
    with TaskProgressTracker(total_items=100, stage_configs=default_stages, prevent_new_task=True) as tracker:
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
    
    # Test invalid updates
    with pytest.raises(ValueError):
        tracker.update(current_items=150)  # Exceeds total
    
    with pytest.raises(ValueError):
        tracker.update(current_items=-10)  # Negative value
    
    # Test completing without going through all stages
    stage_configs = {
        "Stage1": StageConfig(order=1, total_items=50),
        "Stage2": StageConfig(order=2, total_items=50)
    }
    tracker = TaskProgressTracker(total_items=100, stage_configs=stage_configs)
    with pytest.raises(RuntimeError):
        tracker.complete()  # Can't complete before going through all stages

def test_status_message_generation():
    default_stages = {
        "Default": StageConfig(
            order=1,
            total_items=100,
            status_message=None  # Explicitly set to None to allow dynamic messages
        )
    }
    tracker = TaskProgressTracker(total_items=100, stage_configs=default_stages, prevent_new_task=True)
    
    # Test different progress levels
    tracker.update(current_items=5)
    assert "5%" in tracker.status or "5.0%" in tracker.status
    
    tracker.update(current_items=50)
    assert "50%" in tracker.status or "50.0%" in tracker.status
    
    tracker.update(current_items=100)
    assert "100%" in tracker.status or "Complete" in tracker.status

def test_estimated_completion_time():
    default_stages = {
        "Default": StageConfig(order=1, total_items=100, status_message="Processing")
    }
    tracker = TaskProgressTracker(total_items=100, stage_configs=default_stages, prevent_new_task=True)
    time.sleep(1)  # Process for 1 second
    tracker.update(current_items=50)  # Update halfway through
    
    completion_time = tracker.estimated_completion_time
    assert isinstance(completion_time, datetime)
    assert completion_time.tzinfo == timezone.utc
    
    # Should be roughly 1 second from now
    now = datetime.now(timezone.utc)
    diff = (completion_time - now).total_seconds()
    assert 0.8 <= diff <= 1.2  # Allow small margin of error

def test_items_per_second():
    default_stages = {
        "Default": StageConfig(order=1, total_items=100, status_message="Processing")
    }
    tracker = TaskProgressTracker(total_items=100, stage_configs=default_stages)
    time.sleep(1)  # Process for 1 second
    tracker.update(current_items=50)  # 50 items in 1 second
    
    items_per_sec = tracker.items_per_second
    assert isinstance(items_per_sec, float)
    assert 45 <= items_per_sec <= 55  # Allow for some timing variance 