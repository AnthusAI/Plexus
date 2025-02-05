from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional
import time
import logging
import os
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.task import Task

@dataclass
class StageConfig:
    order: int
    total_items: Optional[int] = None
    status_message: Optional[str] = None

@dataclass
class Stage:
    name: str
    order: int
    total_items: Optional[int] = None
    processed_items: Optional[int] = None
    status_message: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def start(self):
        self.start_time = time.time()

    def complete(self):
        self.end_time = time.time()
        if self.total_items is not None:
            self.processed_items = self.total_items

class TaskProgressTracker:
    def __init__(
        self,
        total_items: int,
        stage_configs: Dict[str, StageConfig],
        task_id: Optional[str] = None,
        target: Optional[str] = None,
        command: Optional[str] = None,
        dispatch_status: Optional[str] = None,
        prevent_new_task: bool = True
    ):
        """
        Initialize progress tracker with optional API task record management.
        
        Args:
            total_items: Total number of items to process
            stage_configs: Optional dict mapping stage names to their configs
            task_id: Optional API task ID to retrieve existing task record
            target: Target string for new task records
            command: Command string for new task records
            dispatch_status: Dispatch status for new task records
            prevent_new_task: If True, don't create new task records for salary commands
        """
        self.total_items = total_items
        self.current_items = 0
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.status = "Not started"
        self.is_complete = False
        self.api_task = None

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
                    except Exception as e:
                        logging.error(f"Could not get Task {task_id}: {str(e)}")
                elif command and target:  # Only create new task if we have command and target
                    try:
                        self.api_task = Task.create(
                            client=client,
                            accountId="demo_account",
                            type=command,
                            target=target,
                            command=command,
                            dispatchStatus=dispatch_status or "PENDING"
                        )
                    except Exception as e:
                        logging.error(f"Failed to create task record: {str(e)}")
        
        # Initialize stages if provided
        if stage_configs:
            for name, config in stage_configs.items():
                self._stages[name] = Stage(
                    name=name,
                    order=config.order,
                    total_items=config.total_items,
                    status_message=config.status_message
                )
            # Set current stage to the first one by order
            first_stage = min(self._stages.values(), key=lambda s: s.order)
            self._current_stage_name = first_stage.name
            first_stage.start()

            # Update API task with initial stages if we have one
            if self.api_task:
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
            self.current_stage.processed_items = current_items

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

        # Update API task if we have one
        if self.api_task:
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
        """Update API task record with current progress."""
        if not self.api_task:
            return

        # Convert stages to API format
        stage_configs = {}
        for name, stage in self._stages.items():
            stage_configs[name] = {
                "order": stage.order,
                "totalItems": stage.total_items or 0,
                "processedItems": stage.processed_items or 0,
                "statusMessage": stage.status_message or self.status
            }

        # Update API task progress
        self.api_task.update_progress(
            self.current_items,
            self.total_items,
            stage_configs,
            estimated_completion_at=self.estimated_completion_time
        )

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
        if self.is_complete:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @property
    def items_per_second(self) -> Optional[float]:
        if self.current_items == 0:
            return None
        return self.current_items / self.elapsed_time

    @property
    def estimated_time_remaining(self) -> Optional[float]:
        if not self.items_per_second:
            return None
        remaining_items = self.total_items - self.current_items
        return remaining_items / self.items_per_second

    @property
    def estimated_completion_time(self) -> Optional[datetime]:
        remaining = self.estimated_time_remaining
        if remaining is None:
            return None
        return datetime.fromtimestamp(time.time() + remaining, tz=timezone.utc) 