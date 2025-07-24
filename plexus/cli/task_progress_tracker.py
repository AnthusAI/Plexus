from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any
import time
import logging
import os
import json
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.task import Task
import threading
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Minimum time between API updates in seconds
MIN_API_UPDATE_INTERVAL = 2.0  # 2000ms

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

    # Override default dataclass __eq__ to prevent infinite recursion
    def __eq__(self, other):
        if not isinstance(other, Stage):
            return False
        return self.name == other.name and self.order == other.order

    def start(self):
        """Start this stage."""
        self.start_time = time.time()
        self.status = 'RUNNING'
        if self.total_items is not None:
            self.processed_items = 0  # Only initialize processed_items if total_items is set
        else:
            self.processed_items = None  # Explicitly set processed_items to None when total_items is None
        logging.debug(f"Starting stage {self.name} with total_items={self.total_items}")

    def complete(self):
        """Complete this stage."""
        self.end_time = time.time()
        self.status = 'COMPLETED'
        logging.debug(f"Completed stage {self.name} with processed_items={self.processed_items}")

    def update_processed_count(self, current_count: int):
        """Update the processed items count with the current total count.
        
        Args:
            current_count: The current total count of processed items
        """
        if current_count < 0:
            logging.warning(f"Stage {self.name}: Received negative count {current_count}, clamping to 0")
            current_count = 0
            
        if self.total_items is None:
            # Don't update processed_items if total_items is None
            logging.debug(f"Stage {self.name}: Not updating processed count because total_items is None")
            return
            
        if current_count > self.total_items:
            logging.warning(f"Stage {self.name}: Count {current_count} exceeds total items {self.total_items}")
            current_count = self.total_items
            
        # Always use the current count - don't compare with previous
        self.processed_items = current_count
        logging.info(f"Updated stage {self.name} processed count to {current_count}")

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
        stage_configs: Dict[str, StageConfig],
        task_object: Optional[Task] = None,
        task_id: Optional[str] = None,
        total_items: int = 0,
        target: Optional[str] = None,
        command: Optional[str] = None,
        description: Optional[str] = None,
        dispatch_status: Optional[str] = None,
        prevent_new_task: bool = True,
        metadata: Optional[Dict] = None,
        account_id: Optional[str] = None,
        client: Optional[PlexusDashboardClient] = None
    ):
        """Initialize progress tracker.

        Args:
            stage_configs: Dict mapping stage names to their configs.
            task_object: Optional pre-fetched Task object to track.
            task_id: Optional API task ID (used if task_object is None).
            total_items: Total items (can be updated later).
            target: Target string for new task records
            command: Command string for new task records
            description: Description string for task status display
            dispatch_status: Dispatch status for new task records
            prevent_new_task: If True, don't create new task records
            metadata: Optional metadata to store with the task
            account_id: Optional account ID to associate with the task
            client: Optional existing PlexusDashboardClient instance.
        """
        # Initialize core attributes
        self.total_items = total_items
        self.current_items = 0
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.status = "Not started"
        self.is_complete = False
        self.is_failed = False
        self.api_task: Optional[Task] = None
        self._api_update_lock = threading.Lock()
        self._last_stage_configs_str = None
        self._last_api_update_time = 0
        self._stage_ids = {}  # Map of stage name to API stage ID
        self._client = client

        # Stage management
        self.stage_configs = stage_configs
        self._stages: Dict[str, Stage] = {}
        self._current_stage_name: Optional[str] = None

        # --- Task Association --- #
        task_created_internally = False # Flag to track if we created the task
        if task_object:
            self.api_task = task_object
            logging.debug(f"Tracker initialized with provided Task object: {self.api_task.id}")
        elif task_id and prevent_new_task: # Only fetch by ID if object not given and we ARE preventing new task creation
            try:
                # Use provided client if available, otherwise create one
                if not self._client:
                    api_url = os.environ.get('PLEXUS_API_URL')
                    api_key = os.environ.get('PLEXUS_API_KEY')
                    if api_url and api_key:
                        self._client = PlexusDashboardClient(api_url=api_url, api_key=api_key)
                    else:
                        # Don't raise, but log clearly - we might operate without API
                        logging.error("API URL/Key not configured for internal client creation during task fetch.")
                        self._client = None # Ensure client is None if config missing
                
                if self._client: # Only attempt fetch if client is available
                    logging.debug(f"Attempting to fetch Task by ID: {task_id}")
                    # Ensure Task class is accessible
                    from plexus.dashboard.api.models.task import Task
                    self.api_task = Task.get_by_id(task_id, self._client)
                    if not self.api_task:
                        logging.error(f"Task.get_by_id returned None for task_id: {task_id}")
                    else:
                        logging.debug(f"Successfully fetched Task object: {self.api_task.id}")
                else:
                    logging.warning(f"Cannot fetch Task {task_id}, API client not available.")

            except Exception as e:
                logging.error(f"Could not get Task {task_id} during tracker init: {str(e)}", exc_info=True)
        elif not prevent_new_task:
             # Use the Task.create method (which should be patched in the test)
             try:
                 client = self._get_client() # Get or create client
                 # Prepare basic task details for creation
                 # Use provided account_id or fallback to a sensible default/env var if needed
                 default_account = os.environ.get("PLEXUS_DEFAULT_ACCOUNT_ID", "unknown_account")
                 task_details = {
                     'accountId': account_id or default_account,
                     'type': 'UNKNOWN', # TODO: Consider making type mandatory or deriving it
                     'target': target or 'unknown_target',
                     'command': command or 'unknown_command',
                     'status': 'PENDING', # Initial status before tracker starts it
                     # Add other necessary fields based on Task model definition
                 }
                 if description: task_details['description'] = description
                 if metadata: task_details['metadata'] = json.dumps(metadata) # Ensure metadata is JSON string
                 if dispatch_status: task_details['dispatchStatus'] = dispatch_status

                 logging.debug(f"Attempting to create new Task via Task.create with details: {task_details}")
                 # Task.create is expected to be patched in the test scenario
                 from plexus.dashboard.api.models.task import Task
                 self.api_task = Task.create(client=client, **task_details)
                 if self.api_task:
                     task_created_internally = True
                     logging.debug(f"Successfully created/mocked Task: {self.api_task.id}")
                 else:
                     # This case might happen if the mock returns None or creation fails
                     logging.error("Task.create returned None during tracker init.")

             except ValueError as ve: # Catch specific error from _get_client
                 logging.error(f"Cannot create task, API client configuration missing: {ve}")
                 self.api_task = None # Ensure api_task is None if client fails
             except Exception as e:
                 logging.error(f"Error creating Task during tracker init: {e}", exc_info=True)
                 self.api_task = None # Ensure api_task is None on other errors
        # else: task_id provided and prevent_new_task is True - self.api_task remains None if fetch failed

        # --- Initialize Stages (after task association attempt) --- #
        if stage_configs:
            for name, config in stage_configs.items():
                stage_total_items = config.total_items
                self._stages[name] = Stage(
                    name=name,
                    order=config.order,
                    total_items=stage_total_items,
                    processed_items=None,  # Always initialize processed_items to None
                    status_message=config.status_message
                )
            first_stage = min(self._stages.values(), key=lambda s: s.order)
            self._current_stage_name = first_stage.name
            # Start the first stage *only if* we have an associated task
            if self.api_task:
                 first_stage.start() # This should now run if task was created/fetched
                 logging.debug(f"Started first stage: {first_stage.name}")
                 # Set initial task status to RUNNING if we just created it and it's PENDING
                 if task_created_internally and self.api_task.status == 'PENDING':
                     try:
                         # Use a simple update call, assuming the mock/real Task handles it
                         self.api_task.update(status='RUNNING', startedAt=datetime.now(timezone.utc).isoformat())
                         logging.debug(f"Set newly created task {self.api_task.id} status to RUNNING")
                     except Exception as e:
                         # Log error but don't crash initialization
                         logging.error(f"Failed to update status for newly created task {self.api_task.id}: {e}", exc_info=True)
            else:
                 # This path should be less common now, but log remains useful
                 logging.warning("Tracker has no associated Task object; cannot start stages.")

        # --- Create/Sync API Stages (if task exists) --- #
        if self.api_task:
            # Sync stages asynchronously to avoid blocking init
            threading.Thread(target=self._sync_api_stages, daemon=True).start()
            # self._sync_api_stages() # Synchronous version for debugging
            
            # Set initial task status if we created it
            if task_created_internally:
                self.update(current_items=0, status='RUNNING') # Signal the task has started

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            self.complete()

    def update(self, current_items: int, status: Optional[str] = None):
        """Update progress with current count and optional status message.

        Args:
            current_items: Current number of items processed.
            status: Optional status message.
        """
        if current_items < 0:
            logging.warning(f"Received negative count {current_items}, clamping to 0")
            current_items = 0

        if current_items > self.total_items and self.total_items > 0:
            logging.warning(f"Count {current_items} exceeds total items {self.total_items}")
            current_items = self.total_items

        # Always update the tracker's overall count
        self.current_items = current_items
        logging.info(f"Updating progress with count: {current_items}/{self.total_items}")

        # Only update the current stage if it has total_items set (i.e., it's showing a progress bar)
        if self.current_stage and self.current_stage.total_items is not None:
            self.current_stage.update_processed_count(current_items)
            logging.info(f"Set stage {self.current_stage.name} processed count to {current_items}")

        if status:
            self.status = status

        # Update API task if we have one
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
            # Auto-start any unstarted stages
            unstarted_stages = [
                s for s in self._stages.values()
                if not s.start_time
            ]
            for stage in unstarted_stages:
                logging.warning(f"Auto-starting unstarted stage '{stage.name}' during completion")
                stage.start()
                # If this stage has a total_items, set processed_items to match
                if stage.total_items is not None:
                    stage.processed_items = stage.total_items

            # Complete current stage if it exists
            if self.current_stage:
                self.current_stage.complete()
                # Ensure processed items matches total items for the stage
                if self.current_stage.total_items is not None:
                    self.current_stage.processed_items = self.current_stage.total_items

            # Mark all stages as completed
            for stage in self._stages.values():
                if not stage.end_time:
                    stage.end_time = time.time()
                stage.status = 'COMPLETED'
                # Ensure all stages with total_items have matching processed_items
                if stage.total_items is not None:
                    stage.processed_items = stage.total_items

        # Don't override the current_items count
        self.end_time = time.time()
        self.is_complete = True
        self.status = "Complete"

        # Update API task if we have one
        if self.api_task:
            # First update all stages to completed state
            stages = self.api_task.get_stages()
            for stage in stages:
                stage.update(
                    status='COMPLETED',
                    completedAt=datetime.now(timezone.utc).isoformat(),
                    statusMessage=self.current_stage.status_message if self.current_stage else "Demo command completed"
                )
            # Then mark the task as complete
            self.api_task.complete_processing()
            
    def complete_with_message(self, message: str):
        """Complete tracking with a custom completion message.
        
        Args:
            message: A custom message to display as completion status
        """
        if self.current_stage:
            self.current_stage.status_message = message
        self.status = message
        self.complete()

    def fail(self, error_message: str):
        """Mark the task as failed and stop progress tracking."""
        # Acquire the lock to ensure atomic failure state update
        with self._api_update_lock:
            self.is_failed = True
            self.end_time = time.time()
            self.status = f"Failed: {error_message}"
            
            if self.current_stage:
                self.current_stage.status = 'FAILED'
                self.current_stage.status_message = f"Error: {error_message}"
                self.current_stage.end_time = time.time()  # Set end time for failed stage
            
            # Update API task if we have one - do this synchronously for failures
            if self.api_task:
                try:
                    # First update the stage status synchronously
                    if self.current_stage:
                        stage_configs = {
                            self.current_stage.name: {
                                "order": self.current_stage.order,
                                "statusMessage": f"Error: {error_message}",  # Use error message directly
                                "status": 'FAILED',
                                "name": self.current_stage.name,
                                "startedAt": datetime.fromtimestamp(self.current_stage.start_time, timezone.utc).isoformat() if self.current_stage.start_time else None,
                                "completedAt": datetime.fromtimestamp(self.current_stage.end_time, timezone.utc).isoformat(),
                            }
                        }
                        # Add items if this is a processing stage
                        if self.current_stage.name.lower() not in ['setup', 'finalizing']:
                            if self.current_stage.total_items is not None:
                                stage_configs[self.current_stage.name]["totalItems"] = self.current_stage.total_items
                            if self.current_stage.processed_items is not None:
                                stage_configs[self.current_stage.name]["processedItems"] = self.current_stage.processed_items

                        # Update the stage synchronously
                        stages = self.api_task.get_stages()
                        current_api_stage = next((s for s in stages if s.name == self.current_stage.name), None)
                        if current_api_stage:
                            current_api_stage.update(**stage_configs[self.current_stage.name])

                    # Fail the task with the error message - this should be atomic
                    self.api_task.fail_processing(error_message)  # This will set both status and message
                except Exception as e:
                    logging.error(f"Failed to update API task failure status: {str(e)}")

    def fail_current_stage(self, error_message: str, error_details: Optional[Dict] = None, current_items: Optional[int] = None):
        """Mark the current stage as failed but don't fail the entire task.
        
        This method only fails the current stage, allowing execution to potentially continue
        with other stages. To fail the entire task, use the fail() method instead.
        
        Args:
            error_message: The error message to display
            error_details: Optional dictionary of additional error details
            current_items: The number of items processed when the failure occurred
        """
        # Mark the current stage as failed
        if self.current_stage:
            self.current_stage.status = 'FAILED'
            self.current_stage.status_message = f"Error: {error_message}"
            self.current_stage.end_time = time.time()
            
            # Update processed items if provided
            if current_items is not None:
                self.current_stage.processed_items = current_items
            
            # Update the API task stage if we have one
            if self.api_task:
                try:
                    # Delegate to the API task's fail_current_stage method
                    self.api_task.fail_current_stage(
                        error_message=error_message,
                        error_details=error_details,
                        current_items=current_items
                    )
                except Exception as e:
                    logging.error(f"Failed to update API task stage failure status: {str(e)}")
            
            logging.info(f"Failed stage '{self.current_stage.name}' with error: {error_message}")
        else:
            # If no current stage, just log the error
            logging.error(f"Failed to fail current stage: no current stage exists. Error: {error_message}")

    def fail_processing(self, error_message: str, error_details: Optional[Dict] = None, current_items: Optional[int] = None):
        """Mark the task as failed with detailed error information.
        
        This is a comprehensive failure handling method that:
        1. Fails the current stage with the error message
        2. Fails the entire task with the same error
        3. Updates the API task if available
        
        Args:
            error_message: The error message to display
            error_details: Optional dictionary of additional error details
            current_items: The number of items processed when the failure occurred
        """
        # First fail the current stage with the error message
        self.fail_current_stage(error_message, error_details, current_items)
        
        # Then fail the entire task
        if self.api_task:
            try:
                # Delegate to the API task's fail_processing method
                self.api_task.fail_processing(
                    error_message=error_message,
                    error_details=error_details,
                    current_items=current_items
                )
            except Exception as e:
                logging.error(f"Failed to update API task failure status: {str(e)}")
        
        # Mark the task as failed locally
        self.is_failed = True
        self.end_time = time.time()
        self.status = f"Failed: {error_message}"
        
        logging.error(f"Task failed with error: {error_message}")

    def _update_api_task_progress(self):
        """Update API task record with current progress asynchronously."""
        if not self.api_task:
            logging.debug("No API task available, skipping progress update")
            return

        # Never update if the task is in a terminal state or has failed locally
        if self.api_task.status in ['FAILED', 'COMPLETED'] or self.is_failed:
            logging.debug(f"Skipping update for {self.api_task.status} task")
            return

        # Check if this is a critical update (completion, failure, or all items processed)
        is_critical_update = (
            self.is_complete or 
            self.is_failed or
            (self.current_items == self.total_items) or
            (self.current_stage and self.current_stage.status in ['COMPLETED', 'FAILED'])
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
            # Double check we haven't failed while waiting for the lock
            if self.api_task.status == 'FAILED' or self.is_failed:
                logging.debug("Task failed while waiting for lock, skipping update")
                return

            stage_configs = {}

            # Get current API stages to check their status
            api_stages = {s.name: s for s in self.api_task.get_stages()}

            for name, stage in self._stages.items():
                # Never update a stage that's already failed
                if stage.status == 'FAILED':
                    logging.debug(f"Skipping update for failed stage '{name}'")
                    continue

                if not self.is_complete:
                    # Skip updating stages that are in terminal states in the API
                    if name in api_stages and api_stages[name].status in ['FAILED', 'COMPLETED']:
                        logging.debug(f"Skipping update for {api_stages[name].status} stage '{name}'")
                        continue

                start_time = (
                    datetime.fromtimestamp(stage.start_time, timezone.utc).isoformat()
                    if stage.start_time else None
                )
                end_time = (
                    datetime.fromtimestamp(stage.end_time, timezone.utc).isoformat()
                    if stage.end_time else None
                )

                # For completed task, ensure all stages show as completed
                if self.is_complete:
                    if not end_time:
                        end_time = datetime.now(timezone.utc).isoformat()
                    if not start_time:
                        start_time = self.api_task.startedAt

                config = {
                    # Required fields that must always be present
                    "taskId": self.api_task.id,  # Add this required field
                    "order": stage.order,
                    "name": name,
                    "status": stage.status,
                    
                    # Optional fields
                    "statusMessage": stage.status_message if stage.status == 'FAILED' else (stage.status_message or self.status),
                    "startedAt": start_time,
                    "completedAt": end_time,
                }

                # For processing stages, use the current count we have
                if name.lower() not in ['setup', 'finalizing']:
                    if stage.total_items is not None:
                        config["totalItems"] = stage.total_items
                        config["processedItems"] = stage.processed_items
                    # Only set estimated completion time for the current stage if it's not in a terminal state
                    if name == self.current_stage.name and stage.status not in ['FAILED', 'COMPLETED'] and not self.is_complete:
                        estimated_completion = self.estimated_completion_time
                        if estimated_completion:
                            config["estimatedCompletionAt"] = estimated_completion.isoformat()
                else:
                    config["totalItems"] = None
                    config["processedItems"] = None

                stage_configs[name] = config

            # Compute a JSON string of stage_configs to detect duplicate updates
            config_str = json.dumps(stage_configs, sort_keys=True)
            if self._last_stage_configs_str == config_str and not is_critical_update:
                logging.info(json.dumps({
                    "type": "skip_update",
                    "reason": "configs_unchanged",
                    "is_critical": is_critical_update
                }))
                return
            else:
                self._last_stage_configs_str = config_str
                if is_critical_update:
                    logging.info(json.dumps({
                        "type": "critical_update",
                        "message": "Processing critical update with new stage configs"
                    }))

            # Update the last update time before starting the update
            self._last_api_update_time = current_time

            # For critical updates, do the update synchronously to ensure it completes
            if is_critical_update:
                logging.info(json.dumps({
                    "type": "sync_update",
                    "message": "Performing critical update synchronously"
                }))
                self._async_update_api_task_progress(stage_configs, self.estimated_completion_time.isoformat() if self.estimated_completion_time else None)
            else:
                # Offload non-critical updates to a background thread
                threading.Thread(target=self._async_update_api_task_progress, args=(stage_configs, self.estimated_completion_time.isoformat() if self.estimated_completion_time else None), daemon=True).start()
        finally:
            if self._api_update_lock.locked():
                self._api_update_lock.release()

    def _async_update_api_task_progress(self, stage_configs, estimated_completion):
        """Helper method to perform the API task progress update."""
        try:
            # Only update existing stages, never create new ones
            stages = self.api_task.get_stages()

            # Construct a single batched mutation for all stage updates
            mutation = """
            mutation BatchUpdateStages(
                $taskInput: UpdateTaskInput!
            """ 
            
            # Add variables for each stage
            for stage in stages:
                if stage.name in stage_configs:
                    sanitized_name = self._sanitize_graphql_name(stage.name)
                    mutation += f"""
                    ${sanitized_name}Input: UpdateTaskStageInput!"""
            
            mutation += """) {
                # Update task estimated completion if provided
                updateTask(input: $taskInput) {
                    id
                    accountId
                    type
                    status
                    target
                    command
                    estimatedCompletionAt
                    description
                    dispatchStatus
                    metadata
                    createdAt
                    startedAt
                    completedAt
                    errorMessage
                    errorDetails
                    currentStageId
                }
            """
            
            # Add update operations for each stage
            for stage in stages:
                if stage.name in stage_configs:
                    sanitized_name = self._sanitize_graphql_name(stage.name)
                    mutation += f"""
                    update{sanitized_name}Stage: updateTaskStage(input: ${sanitized_name}Input) {{
                        id
                        taskId
                        name
                        order
                        status
                        statusMessage
                        processedItems
                        totalItems
                        startedAt
                        completedAt
                        estimatedCompletionAt
                    }}
                    """
            
            mutation += "}"
            
            # Construct variables for the mutation
            variables = {
                "taskInput": {
                    "id": self.api_task.id,
                    "accountId": self.api_task.accountId,
                    "type": self.api_task.type,
                    "status": self.api_task.status,
                    "target": self.api_task.target,
                    "command": self.api_task.command,
                    "estimatedCompletionAt": estimated_completion
                }
            }
            
            # Add variables for each stage update
            for stage in stages:
                if stage.name in stage_configs:
                    config = stage_configs[stage.name].copy()
                    # Add estimated completion time to current stage
                    if stage.name == self._current_stage_name and estimated_completion:
                        config['estimatedCompletionAt'] = estimated_completion
                    
                    # Add required fields
                    config['id'] = stage.id
                    config['taskId'] = stage.taskId  # Ensure taskId is included
                    config['order'] = stage.order    # Ensure order is included
                    config['name'] = stage.name      # Ensure name is included
                    if 'status' not in config:       # Ensure status is included
                        config['status'] = stage.status
                    
                    sanitized_name = self._sanitize_graphql_name(stage.name)
                    variables[f"{sanitized_name}Input"] = config
            
            # Log the mutation and variables
            logging.debug(json.dumps({
                "type": "batch_mutation",
                "mutation": mutation,
                "variables": variables
            }, indent=2))
            
            # Execute the batched mutation
            result = self.api_task._client.execute(mutation, variables)
            
        except Exception as e:
            logging.error(json.dumps({
                "type": "task_update_error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }))

    def _sanitize_graphql_name(self, name: str) -> str:
        """Sanitize a string to be a valid GraphQL name (remove spaces, etc.)."""
        # Basic sanitization: remove spaces and non-alphanumeric chars
        # Consider a more robust regex if needed
        import re
        sanitized = re.sub(r'\W+', '', name)
        # Ensure it starts with a letter or underscore if it's not empty
        if sanitized and not sanitized[0].isalpha() and sanitized[0] != '_':
            sanitized = '_' + sanitized
        return sanitized or 'sanitizedStageName' # Fallback if empty

    def _generate_status_message(self) -> str:
        """Generate a status message based on current progress."""
        if self.total_items <= 0:
            return "Processing items"
            
        percentage = int(100 * self.current_items / self.total_items)
        
        if self.current_stage and self.current_stage.status_message:
            # If stage has a status message, use that with percentage
            return f"{self.current_stage.status_message} ({percentage}%)"
            
        # Default status based on percentage
        if percentage <= 0:
            return "Starting processing... (0%)"
        elif percentage < 100:
            return f"Processing items ({percentage}%)"
        else:
            return "Processing complete (100%)"

    @property
    def task(self) -> Optional['Task']:
        """Return the API task instance if one exists."""
        return self.api_task

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

    def set_total_items(self, total_items: int):
        """Set the total items count - this is our single source of truth for the total count."""
        
        # Validate input
        if total_items < 0:
            raise ValueError("Total items cannot be negative")
            
        # Set the total at tracker level
        self.total_items = total_items
        
        # Update all non-finalizing stages with the new total
        if self._stages:
            for stage in self._stages.values():
                if stage.name.lower() != 'finalizing':
                    old_total = stage.total_items
                    stage.total_items = total_items
                    
                    # If this is the current stage, ensure its processed items are valid
                    if stage == self.current_stage:
                        if stage.processed_items is None or stage.processed_items > total_items:
                            stage.processed_items = 0
        
        # Force an API update to ensure the new total is propagated
        if self.api_task:
            self._update_api_task_progress()
        
        # Return the new total to allow verification
        return self.total_items 

    def _get_client(self) -> PlexusDashboardClient:
        """Returns the associated client or creates one if necessary."""
        if self._client:
            return self._client
        
        api_url = os.environ.get('PLEXUS_API_URL')
        api_key = os.environ.get('PLEXUS_API_KEY')
        if api_url and api_key:
            self._client = PlexusDashboardClient(api_url=api_url, api_key=api_key)
            return self._client
        else:
            raise ValueError("Cannot perform API operation: API URL/Key not configured and no client provided.")

    def _sync_api_stages(self):
        """Creates or finds API TaskStage records corresponding to local stage configs."""
        if not self.api_task:
            return

        client = self._get_client() # Get the client instance
        try:
            # Pass client correctly if get_stages supports it, otherwise omit
            # Assuming get_stages uses self._client if available or creates default
            existing_api_stages = {s.name: s for s in self.api_task.get_stages(client=client)}
            logging.debug(f"Found existing API stages: {list(existing_api_stages.keys())}")
        except TypeError:
             # Fallback if get_stages doesn't accept client kwarg
             logging.warning("Task.get_stages does not accept 'client', using default client resolution.")
             existing_api_stages = {s.name: s for s in self.api_task.get_stages()}
        except Exception as e:
            logging.error(f"Failed to get existing stages for task {self.api_task.id}: {e}", exc_info=True)
            existing_api_stages = {}

        # Collect stages that need to be created
        stages_to_create = []
        
        for name, stage_config in self._stages.items():
            if name in existing_api_stages:
                self._stage_ids[name] = existing_api_stages[name].id
                logging.debug(f"Stage '{name}' already exists in API with ID: {self._stage_ids[name]}")
            else:
                # Prepare stage configuration for batch creation
                create_fields = {
                    'name': name,
                    'order': stage_config.order,
                    'status': self._stages[name].status,
                }
                if stage_config.status_message:
                    create_fields['statusMessage'] = stage_config.status_message
                if stage_config.total_items is not None:
                    create_fields['totalItems'] = stage_config.total_items
                if self._stages[name].start_time:
                    create_fields['startedAt'] = datetime.fromtimestamp(self._stages[name].start_time, timezone.utc).isoformat()
                    if stage_config.total_items is not None:
                        estimated_completion = datetime.now(timezone.utc) + timedelta(seconds=20)
                        create_fields['estimatedCompletionAt'] = estimated_completion.isoformat()
                
                stages_to_create.append(create_fields)
                logging.debug(f"Queued stage '{name}' for batch creation")
        
        # Create all missing stages in a single batch operation
        if stages_to_create:
            try:
                logging.info(f"Creating {len(stages_to_create)} stages in batch for task {self.api_task.id}")
                created_stages = self.api_task.create_stages_batch(stages_to_create)
                
                # Map created stages to our internal stage IDs
                for stage in created_stages:
                    self._stage_ids[stage.name] = stage.id
                    logging.debug(f"Successfully created API stage '{stage.name}' with ID: {stage.id}")
                
                logging.info(f"Successfully created {len(created_stages)} stages in batch")
                
            except Exception as e:
                logging.error(f"Error creating stages in batch: {e}", exc_info=True)
                # Fallback to individual creation if batch fails
                logging.info("Falling back to individual stage creation...")
                for stage_config in stages_to_create:
                    try:
                        new_stage = self.api_task.create_stage(**stage_config)
                        if new_stage:
                            self._stage_ids[stage_config['name']] = new_stage.id
                            logging.debug(f"Successfully created API stage '{stage_config['name']}' with ID: {new_stage.id}")
                        else:
                            logging.error(f"API call create_stage for '{stage_config['name']}' returned None.")
                    except Exception as stage_error:
                        logging.error(f"Error creating individual stage '{stage_config['name']}': {stage_error}", exc_info=True)
    
    @classmethod
    def create_for_operation_type(
        cls,
        operation_type: str,
        total_items: int = 1,
        target: Optional[str] = None,
        command: Optional[str] = None,
        description: Optional[str] = None,
        task_id: Optional[str] = None,
        account_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        client: Optional[PlexusDashboardClient] = None,
        **kwargs
    ) -> 'TaskProgressTracker':
        """Create a TaskProgressTracker configured for a specific operation type.
        
        Args:
            operation_type: Type of operation ('evaluation', 'prediction', etc.)
            total_items: Total number of items to process
            target: Target string for the task
            command: Command string for the task
            description: Description for the task
            task_id: Optional existing task ID
            account_id: Account ID for the task
            metadata: Optional metadata for the task
            client: Optional API client
            **kwargs: Additional arguments passed to TaskProgressTracker
        
        Returns:
            TaskProgressTracker: Configured tracker for the operation type
        """
        from plexus.cli.stage_configurations import get_stage_configs_for_operation_type
        
        # Get appropriate stage configuration
        stage_configs = get_stage_configs_for_operation_type(operation_type, total_items)
        
        # Set default values based on operation type
        if not target:
            target = f"{operation_type.lower()}/task"
        if not command:
            command = f"{operation_type.lower()} command"
        if not description:
            description = f"{operation_type.title()} task"
        if not metadata:
            metadata = {}
        
        # Add operation type to metadata
        metadata.update({
            "operation_type": operation_type,
            "task_type": operation_type.title()
        })
        
        return cls(
            stage_configs=stage_configs,
            total_items=total_items,
            target=target,
            command=command,
            description=description,
            task_id=task_id,
            account_id=account_id,
            metadata=metadata,
            client=client,
            **kwargs
        )
    
    @classmethod
    def create_for_evaluation(
        cls,
        scorecard_name: str,
        total_items: int,
        task_id: Optional[str] = None,
        account_id: Optional[str] = None,
        client: Optional[PlexusDashboardClient] = None,
        **kwargs
    ) -> 'TaskProgressTracker':
        """Create a TaskProgressTracker configured for evaluation operations.
        
        Args:
            scorecard_name: Name of the scorecard being evaluated
            total_items: Total number of items to evaluate
            task_id: Optional existing task ID
            account_id: Account ID for the task
            client: Optional API client
            **kwargs: Additional arguments passed to TaskProgressTracker
        
        Returns:
            TaskProgressTracker: Configured tracker for evaluation
        """
        return cls.create_for_operation_type(
            operation_type="evaluation",
            total_items=total_items,
            target=f"evaluation/accuracy/{scorecard_name}",
            command=f"evaluate accuracy --scorecard-name {scorecard_name}",
            description=f"Accuracy evaluation for {scorecard_name}",
            task_id=task_id,
            account_id=account_id,
            metadata={
                "scorecard": scorecard_name,
                "evaluation_type": "accuracy"
            },
            client=client,
            **kwargs
        )
    
    @classmethod
    def create_for_prediction(
        cls,
        scorecard_identifier: str,
        score_names: list,
        total_items: int = 1,
        task_id: Optional[str] = None,
        account_id: Optional[str] = None,
        client: Optional[PlexusDashboardClient] = None,
        **kwargs
    ) -> 'TaskProgressTracker':
        """Create a TaskProgressTracker configured for prediction operations.
        
        Args:
            scorecard_identifier: Identifier of the scorecard
            score_names: List of score names being predicted
            total_items: Total number of predictions to run
            task_id: Optional existing task ID
            account_id: Account ID for the task
            client: Optional API client
            **kwargs: Additional arguments passed to TaskProgressTracker
        
        Returns:
            TaskProgressTracker: Configured tracker for prediction
        """
        return cls.create_for_operation_type(
            operation_type="prediction",
            total_items=total_items,
            target=f"prediction/{scorecard_identifier}",
            command=f"predict --scorecard {scorecard_identifier}",
            description=f"Prediction for {scorecard_identifier}",
            task_id=task_id,
            account_id=account_id,
            metadata={
                "scorecard": scorecard_identifier,
                "scores": score_names,
                "prediction_count": total_items
            },
            client=client,
            **kwargs
        )
    
    def get_stage_by_name(self, stage_name: str) -> Optional[Stage]:
        """Get a stage by its name.
        
        Args:
            stage_name: Name of the stage to retrieve
            
        Returns:
            Stage: The stage object if found, None otherwise
        """
        return self._stages.get(stage_name)
    
    def get_all_stages(self) -> Dict[str, Stage]:
        """Get all stages in this tracker.
        
        Returns:
            Dict[str, Stage]: Dictionary mapping stage names to Stage objects
        """
        return self._stages.copy()
    
    def set_stage_message(self, stage_name: str, message: str) -> None:
        """Set the status message for a specific stage.
        
        Args:
            stage_name: Name of the stage
            message: Status message to set
        """
        stage = self._stages.get(stage_name)
        if stage:
            stage.status_message = message
            # Update API if this is the current stage
            if stage_name == self._current_stage_name:
                self._update_api_task_progress()
        else:
            logging.warning(f"Stage '{stage_name}' not found") 