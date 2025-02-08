from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Any
import time
import logging
import os
import json
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.task import Task
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Minimum time between API updates in seconds
MIN_API_UPDATE_INTERVAL = 0.5  # 500ms

@dataclass
class StageConfig:
    """Configuration for a task stage.
    
    Args:
        order: The order of this stage in the task sequence
        total_items: Optional number of items to process in this stage.
            Only set this if you want the stage to show a progress bar in the UI.
            Typically only set for main processing stages, not for setup or finalizing stages.
        status_message: Optional status message to display for this stage
    """
    order: int
    total_items: Optional[int] = None
    status_message: Optional[str] = None

@dataclass
class Stage:
    """Internal representation of a task stage.
    
    This class tracks the state of a single stage in a task's execution.
    Progress bars in the UI are only shown for stages that have total_items set.
    Typically, only the main processing stages should have total_items set,
    while setup and finalizing stages should not show progress bars.
    """
    name: str
    order: int
    total_items: Optional[int] = None
    processed_items: Optional[int] = None
    status_message: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    status: str = 'PENDING'

    def start(self):
        """Start this stage."""
        self.start_time = time.time()
        self.status = 'RUNNING'
        self.processed_items = 0  # Reset processed items when starting stage
        logging.debug(f"Starting stage {self.name} with total_items={self.total_items}")

    def complete(self):
        """Complete this stage."""
        self.end_time = time.time()
        self.status = 'COMPLETED'
        # Only set processed_items to total_items if they're set
        # This preserves the behavior where some stages don't show progress
        if self.total_items is not None:
            self.processed_items = self.total_items
            logging.debug(f"Completed stage {self.name} with processed_items={self.processed_items}")
        else:
            logging.debug(f"Completed stage {self.name} without progress bar")

class TaskProgressTracker:
    """Tracks progress of a multi-stage task with optional API integration.
    
    This class manages the progress of a task through multiple stages, with proper
    UI integration for progress bars and status updates. Key concepts:
    
    1. Stage Progress Bars:
       - Only stages with total_items set will show progress bars in the UI
       - Typically, only main processing stages should show progress
       - Setup and finalizing stages usually should not have total_items set
    
    2. Stage Types:
       - Setup stages: Quick preparation steps, usually no progress bar needed
       - Processing stages: Main work stages that show progress bars
       - Finalizing stages: Cleanup/completion steps, usually no progress bar needed
    
    Example usage:
        # Configure stages - only Processing shows progress
        stages = {
            "Setup": StageConfig(order=1, status_message="Setting up..."),
            "Processing": StageConfig(order=2, total_items=100),
            "Finalizing": StageConfig(order=3, status_message="Finishing...")
        }
        
        # Create tracker
        tracker = TaskProgressTracker(total_items=100, stage_configs=stages)
        
        # Update progress (only affects stages with total_items set)
        tracker.update(current_items=50)
    """
    def __init__(
        self,
        total_items: int,
        stage_configs: Dict[str, StageConfig],
        task_id: Optional[str] = None,
        target: Optional[str] = None,
        command: Optional[str] = None,
        description: Optional[str] = None,
        dispatch_status: Optional[str] = None,
        prevent_new_task: bool = True,
        metadata: Optional[Dict] = None,
        account_id: Optional[str] = None
    ):
        """Initialize progress tracker with optional API task record management.
        
        Args:
            total_items: Total number of items to process
            stage_configs: Optional dict mapping stage names to their configs
            task_id: Optional API task ID to retrieve existing task record
            target: Target string for new task records
            command: Command string for new task records
            description: Description string for task status display
            dispatch_status: Dispatch status for new task records
            prevent_new_task: If True, don't create new task records
            metadata: Optional metadata to store with the task
            account_id: Optional account ID to associate with the task
        """
        self.total_items = total_items
        self.current_items = 0
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.status = "Not started"
        self.is_complete = False
        self.api_task = None
        self._api_update_lock = threading.Lock()
        self._last_stage_configs_str = None
        self._last_api_update_time = 0
        self._stage_ids = {}  # Map of stage name to API stage ID

        # Stage management
        self.stage_configs = stage_configs
        self._stages: Dict[str, Stage] = {}
        self._current_stage_name: Optional[str] = None

        # Only try to get/create task if we're allowed
        if not prevent_new_task:
            api_url = os.environ.get('PLEXUS_API_URL')
            api_key = os.environ.get('PLEXUS_API_KEY')
            
            if api_url and api_key:
                client = PlexusDashboardClient(api_url=api_url, api_key=api_key)
                
                if task_id:
                    try:
                        self.api_task = Task.get_by_id(task_id, client)
                        if description:  # Update description if provided
                            self.api_task.update(description=description)
                        if metadata:  # Update metadata if provided
                            self.api_task.update(metadata=json.dumps(metadata))
                    except Exception as e:
                        logging.error(f"Could not get Task {task_id}: {str(e)}")
                elif command and target:  # Only create new task if we have command and target
                    create_args = {
                        "client": client,
                        "type": metadata.get("type", command) if metadata else command,
                        "target": target,
                        "command": command,
                        "description": description,
                        "metadata": json.dumps(metadata) if metadata else None,
                        "dispatchStatus": dispatch_status or "PENDING",
                        "startedAt": datetime.now(timezone.utc).isoformat()
                    }
                    # Add account_id if provided
                    if account_id:
                        create_args["accountId"] = account_id
                    
                    self.api_task = Task.create(**create_args)
        
        # Initialize stages if provided
        if stage_configs:
            for name, config in stage_configs.items():
                # Don't set total_items for finalizing stage
                stage_total_items = None if name.lower() == 'finalizing' else config.total_items
                logging.debug(f"Initializing stage {name} with total_items={stage_total_items}")
                self._stages[name] = Stage(
                    name=name,
                    order=config.order,
                    total_items=stage_total_items,
                    status_message=config.status_message
                )
            # Set current stage to the first one by order
            first_stage = min(self._stages.values(), key=lambda s: s.order)
            self._current_stage_name = first_stage.name
            first_stage.start()

            # Create API stages once during initialization
            if self.api_task:
                # Get existing stages first
                existing_stages = {s.name: s.id for s in self.api_task.get_stages()}
                
                # Create any missing stages and store their IDs
                for name, stage in self._stages.items():
                    if name in existing_stages:
                        self._stage_ids[name] = existing_stages[name]
                    else:
                        new_stage = self.api_task.create_stage(
                            name=name,
                            order=stage.order
                        )
                        self._stage_ids[name] = new_stage.id
                        logging.debug(f"Created stage {name} with ID: {new_stage.id}")

                self._update_api_task_progress()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            self.complete()

    def update(self, current_items: int, status: Optional[str] = None):
        """Update progress and optionally the API task record."""
        if current_items < 0:
            raise ValueError("Current items cannot be negative")
        if current_items > self.total_items:
            raise ValueError("Current items cannot exceed total items")

        self.current_items = current_items
        
        # Update current stage if we have stages
        if self.current_stage:
            if self.current_stage.name.lower() != 'finalizing':
                self.current_stage.processed_items = current_items
                logging.debug(f"Updated stage {self.current_stage.name} progress: {current_items}/{self.current_stage.total_items}")
            else:
                logging.debug(f"Skipping progress update for finalizing stage")

        # Update status message
        if status:
            self.status = status
        else:
            self.status = self._generate_status_message()

        # Update API task if we have one
        if self.api_task:
            self._update_api_task_progress()

    def advance_stage(self):
        """Advance to next stage and update API task if we have one."""
        if not self._stages:
            return

        # Complete current stage
        current = self.current_stage
        if current:
            current.complete()
            logging.debug(f"Completed stage {current.name}")

        # Find next stage
        next_stages = [
            s for s in self._stages.values()
            if s.order > current.order
        ]
        if not next_stages:
            return

        next_stage = min(next_stages, key=lambda s: s.order)
        self._current_stage_name = next_stage.name
        next_stage.start()
        logging.debug(f"Advanced to stage {next_stage.name}")

        # Update API task if we have one
        if self.api_task:
            # Update current stage in API
            stages = self.api_task.get_stages()
            next_api_stage = next(
                (s for s in stages if s.name == next_stage.name),
                None
            )
            if next_api_stage:
                self.api_task.advance_stage(next_api_stage)
            self._update_api_task_progress()

    def complete(self):
        """Complete tracking and update API task if we have one."""
        if self._stages:
            # Complete current stage if it exists
            if self.current_stage:
                self.current_stage.complete()

            # Verify all stages are complete
            incomplete = [
                s.name for s in self._stages.values()
                if not s.end_time
            ]
            if incomplete:
                raise RuntimeError(
                    f"Cannot complete task: stages not finished: {incomplete}"
                )

        self.current_items = self.total_items
        self.end_time = time.time()
        self.is_complete = True
        self.status = "Complete"

        # Update API task if we have one
        if self.api_task:
            self._update_api_task_progress()
            self.api_task.complete_processing()

    def _update_api_task_progress(self):
        """Update API task record with current progress asynchronously."""
        if not self.api_task:
            logging.debug("No API task available, skipping progress update")
            return

        # Check if this is a critical update (completion or all items processed)
        is_critical_update = (
            self.is_complete or 
            (self.current_items == self.total_items) or
            (self.current_stage and self.current_stage.status == 'COMPLETED')
        )

        # Check if enough time has passed since the last update
        current_time = time.time()
        time_since_last_update = current_time - self._last_api_update_time
        if time_since_last_update < MIN_API_UPDATE_INTERVAL and not is_critical_update:
            logging.debug(f"Skipping non-critical API update - only {time_since_last_update:.3f}s since last update")
            return

        # Ensure only one API update is in progress at a time
        if not self._api_update_lock.acquire(blocking=False):
            if is_critical_update:
                logging.info("Critical update waiting for lock...")
                self._api_update_lock.acquire(blocking=True)  # Wait for lock if critical
            else:
                logging.debug("API update already in progress, skipping this update.")
                return

        try:
            stage_configs = {}
            logging.debug("\nPreparing API task update:")
            logging.debug(f"Current stage: {self._current_stage_name}")
            logging.debug(f"Overall progress: {self.current_items}/{self.total_items}")
            logging.debug(f"Is critical update: {is_critical_update}")

            for name, stage in self._stages.items():
                start_time = (
                    datetime.fromtimestamp(stage.start_time, timezone.utc).isoformat()
                    if stage.start_time else None
                )
                end_time = (
                    datetime.fromtimestamp(stage.end_time, timezone.utc).isoformat()
                    if stage.end_time else None
                )
                config = {
                    "order": stage.order,
                    "statusMessage": stage.status_message or self.status,
                    "status": stage.status,
                    "name": name,
                    "startedAt": start_time,
                    "completedAt": end_time,
                    "estimatedCompletionAt": None
                }
                if name.lower() not in ['setup', 'finalizing']:
                    if stage.total_items is not None:
                        config["totalItems"] = stage.total_items
                    if stage.processed_items is not None:
                        config["processedItems"] = stage.processed_items
                else:
                    config["totalItems"] = None
                    config["processedItems"] = None

                stage_configs[name] = config

                logging.debug(f"\nStage '{name}' API data:")
                logging.debug(f"  - Order: {stage.order}")
                logging.debug(f"  - Status: {stage.status}")
                if name.lower() not in ['setup', 'finalizing']:
                    logging.debug(f"  - Total Items: {stage.total_items}")
                    logging.debug(f"  - Processed Items: {stage.processed_items}")
                else:
                    logging.debug(f"  - Total Items: None (not tracked for {name})")
                    logging.debug(f"  - Processed Items: None (not tracked for {name})")
                logging.debug(f"  - Status Message: {stage.status_message or self.status}")
                logging.debug(f"  - Start Time: {start_time}")
                logging.debug(f"  - End Time: {end_time}")

            estimated_completion = self.estimated_completion_time
            logging.debug(f"\nEstimated completion time: {estimated_completion}")

            # Compute a JSON string of stage_configs to detect duplicate updates
            config_str = json.dumps(stage_configs, sort_keys=True)
            if self._last_stage_configs_str == config_str and not is_critical_update:
                logging.debug("Stage configs unchanged, skipping non-critical duplicate API update.")
                return
            else:
                self._last_stage_configs_str = config_str
                if is_critical_update:
                    logging.debug("Processing critical update with new stage configs")

            # Update the last update time before starting the update
            self._last_api_update_time = current_time

            # For critical updates, do the update synchronously to ensure it completes
            if is_critical_update:
                logging.debug("Performing critical update synchronously")
                self._async_update_api_task(stage_configs, estimated_completion)
            else:
                # Offload non-critical updates to a background thread
                threading.Thread(target=self._async_update_api_task, args=(stage_configs, estimated_completion), daemon=True).start()
        finally:
            if self._api_update_lock.locked():
                self._api_update_lock.release()

    def _async_update_api_task(self, stage_configs, estimated_completion):
        """Helper method to perform the API task progress update."""
        try:
            # Only update existing stages, never create new ones
            stages = self.api_task.get_stages()
            for stage in stages:
                if stage.name in stage_configs:
                    config = stage_configs[stage.name]
                    stage.update(**config)

            # Only update the estimated completion time on the task
            if estimated_completion:
                self.api_task.update(
                    estimatedCompletionAt=estimated_completion
                )

            logging.debug("API task update completed successfully")
        except Exception as e:
            logging.error("Failed to update API task progress", exc_info=True)

    def _generate_status_message(self) -> str:
        if self.is_complete:
            return "Complete"

        # Use stage status message if available
        if self.current_stage and self.current_stage.status_message:
            return self.current_stage.status_message

        progress = self.progress
        if progress == 0:
            return "Starting..."
        elif progress <= 5:
            return "Starting..."
        elif progress <= 35:
            return "Processing items..."
        elif progress <= 65:
            return "Cruising..."
        elif progress <= 80:
            return "On autopilot..."
        elif progress <= 90:
            return "Finishing soon..."
        elif progress < 100:
            return "Almost done..."
        else:
            return "Complete"

    @property
    def progress(self) -> int:
        if self.total_items == 0:
            return 100 if self.is_complete else 0
        return int((self.current_items / self.total_items) * 100)

    @property
    def current_stage(self) -> Optional[Stage]:
        if not self._current_stage_name:
            return None
        return self._stages[self._current_stage_name]

    @property
    def elapsed_time(self) -> float:
        """Return elapsed time since task started, regardless of current stage."""
        return time.time() - self.start_time

    @property
    def items_per_second(self) -> Optional[float]:
        if (not self.current_stage or 
            not self.current_stage.start_time or 
            not self.current_stage.processed_items):
            return None
            
        # Use stage-specific item count and timing
        stage_elapsed = time.time() - self.current_stage.start_time
        if stage_elapsed <= 0:
            return None
            
        # Calculate rate based on stage-specific processed items
        return self.current_stage.processed_items / stage_elapsed

    @property
    def estimated_time_remaining(self) -> Optional[float]:
        if not self.items_per_second or not self.items_per_second > 0:
            return None
            
        # Calculate remaining items in current stage
        if not self.current_stage or not self.current_stage.total_items:
            return None
            
        # Only show ETA after 10% progress to ensure we have enough data
        stage_progress = (self.current_stage.processed_items or 0) / self.current_stage.total_items * 100
        if stage_progress < 10:
            return None
            
        remaining_items = self.current_stage.total_items - (self.current_stage.processed_items or 0)
        return remaining_items / self.items_per_second

    @property
    def estimated_completion_time(self) -> Optional[datetime]:
        remaining = self.estimated_time_remaining
        if remaining is None or not self.current_stage or not self.current_stage.start_time:
            return None
        # Calculate completion time based on stage start time plus elapsed and remaining time
        stage_elapsed = time.time() - self.current_stage.start_time
        completion_time = self.current_stage.start_time + stage_elapsed + remaining
        return datetime.fromtimestamp(completion_time, tz=timezone.utc) 