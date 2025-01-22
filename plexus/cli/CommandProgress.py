import time
from typing import Optional
from dataclasses import dataclass
from contextlib import contextmanager

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
    """Progress tracking that's safe to use in both direct and Celery execution."""
    _current_progress: Optional[ProgressState] = None
    _update_callback = None
    
    @classmethod
    def set_update_callback(cls, callback):
        """Set the callback function that will be called when progress is updated."""
        cls._update_callback = callback
        if callback and cls._current_progress:
            # If we have existing progress when a callback is set, notify it
            callback(cls._current_progress)
    
    @classmethod
    def update(cls, current: int, total: int, status: str):
        """Update the progress state and notify the callback if set.
        Safe to call even when no callback is set."""
        if cls._current_progress is None:
            cls._current_progress = ProgressState(
                current=current,
                total=total,
                status=status,
                start_time=time.time()
            )
        else:
            cls._current_progress.current = current
            cls._current_progress.total = total
            cls._current_progress.status = status
        
        if cls._update_callback:
            cls._update_callback(cls._current_progress)
    
    @classmethod
    @contextmanager
    def track(cls, total: int, status: str):
        """Context manager for tracking progress of an operation.
        Safe to use even when no callback is set."""
        try:
            cls.update(0, total, status)
            yield cls
        finally:
            cls._current_progress = None
    
    @classmethod
    def get_current_state(cls) -> Optional[ProgressState]:
        """Get the current progress state if any."""
        return cls._current_progress 