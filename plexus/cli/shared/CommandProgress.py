import time
from contextvars import ContextVar
from typing import Optional
from dataclasses import dataclass
from contextlib import contextmanager
from celery import current_task


@dataclass
class ProgressState:
    current: int
    total: int
    status: str
    start_time: float

    @property
    def elapsed_time(self) -> str:
        elapsed = time.time() - self.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes}m {seconds}s"

    @property
    def estimated_remaining(self) -> Optional[str]:
        if self.current == 0:
            return None

        elapsed = time.time() - self.start_time
        items_per_second = self.current / elapsed
        remaining_items = self.total - self.current

        if items_per_second <= 0:
            return None

        remaining_seconds = remaining_items / items_per_second
        minutes = int(remaining_seconds // 60)
        seconds = int(remaining_seconds % 60)
        return f"{minutes}m {seconds}s"


class CommandProgress:
    """Progress tracking scoped to one command execution context.

    A worker can process more than one command at a time.  Progress state and
    callbacks therefore live in ``ContextVar`` bindings instead of process-wide
    class attributes, so one command can never publish updates through another
    command's lifecycle callback.
    """

    _current_progress: ContextVar[Optional[ProgressState]] = ContextVar(
        "command_progress_state", default=None
    )
    _update_callback: ContextVar[object | None] = ContextVar(
        "command_progress_callback", default=None
    )

    @classmethod
    def set_update_callback(cls, callback):
        """Set the callback function that will be called when progress is updated."""
        cls._update_callback.set(callback)
        current_progress = cls._current_progress.get()
        if callback and current_progress:
            # If we have existing progress when a callback is set, notify it
            callback(current_progress)

    @classmethod
    def update(cls, current: int, total: int, status: str = None):
        """Update the progress state and notify the callback if set.
        Safe to call even when no callback is set."""
        current_progress = cls._current_progress.get()
        if current_progress is None:
            current_progress = ProgressState(
                current=current, total=total, status=status, start_time=time.time()
            )
            cls._current_progress.set(current_progress)
        else:
            current_progress.current = current
            current_progress.total = total
            current_progress.status = status

        callback = cls._update_callback.get()
        if callback:
            callback(current_progress)

        # Get current Celery task if we're in a Celery worker
        celery_task = current_task
        if not celery_task:
            return

        # Update Celery task state
        celery_task.update_state(
            state="PROGRESS",
            meta={"current": current, "total": total, "status": status},
        )

    @classmethod
    @contextmanager
    def track(cls, total: int, status: str):
        """Context manager for tracking progress of an operation.
        Safe to use even when no callback is set."""
        progress_token = cls._current_progress.set(None)
        try:
            cls.update(0, total, status)
            yield cls
        finally:
            cls._current_progress.reset(progress_token)

    @classmethod
    def get_current_state(cls) -> Optional[ProgressState]:
        """Get the current progress state if any."""
        return cls._current_progress.get()
