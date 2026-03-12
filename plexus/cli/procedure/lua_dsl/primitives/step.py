"""
Step primitive for checkpointed operations.

Provides Step.run() for checkpointing arbitrary operations that aren't agent turns.
"""

from typing import Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)


class StepPrimitive:
    """
    Step primitive for checkpointing operations.

    Example usage:
        local metrics = Step.run("evaluate_champion", function()
            return Tools.plexus_run_evaluation({
                score_id = params.score_id,
                version = "champion"
            })
        end)

    On first execution: runs the function and caches result
    On replay: returns cached result without re-executing
    """

    def __init__(self, execution_context):
        """
        Initialize Step primitive.

        Args:
            execution_context: ExecutionContext instance for checkpoint operations
        """
        self.execution_context = execution_context

    def run(self, name: str, fn: Callable[[], Any]) -> Any:
        """
        Execute function with checkpointing.

        Args:
            name: Unique checkpoint name
            fn: Function to execute (must be deterministic)

        Returns:
            Result of fn() on first execution, cached result on replay
        """
        logger.debug(f"Step.run('{name}')")

        try:
            result = self.execution_context.step_run(name, fn)
            logger.debug(f"Step.run('{name}') completed successfully")
            return result
        except Exception as e:
            logger.error(f"Step.run('{name}') failed: {e}")
            raise


class CheckpointPrimitive:
    """
    Checkpoint management primitive.

    Provides checkpoint inspection and clearing operations for testing.
    """

    def __init__(self, execution_context):
        """
        Initialize Checkpoint primitive.

        Args:
            execution_context: ExecutionContext instance
        """
        self.execution_context = execution_context

    def clear_all(self) -> None:
        """
        Clear all checkpoints. Restarts procedure from beginning.

        Example:
            Checkpoint.clear_all()
        """
        logger.info("Clearing all checkpoints")
        self.execution_context.checkpoint_clear_all()

    def clear_after(self, name: str) -> None:
        """
        Clear checkpoint and all subsequent ones.

        Args:
            name: Checkpoint name to clear from

        Example:
            Checkpoint.clear_after("evaluate_candidate_1")
        """
        logger.info(f"Clearing checkpoints after '{name}'")
        self.execution_context.checkpoint_clear_after(name)

    def exists(self, name: str) -> bool:
        """
        Check if checkpoint exists.

        Args:
            name: Checkpoint name

        Returns:
            True if checkpoint exists

        Example:
            if Checkpoint.exists("load_champion") then
                -- Already loaded
            end
        """
        return self.execution_context.checkpoint_exists(name)

    def get(self, name: str) -> Optional[Any]:
        """
        Get cached checkpoint value.

        Args:
            name: Checkpoint name

        Returns:
            Cached value or None if not found

        Example:
            local cached = Checkpoint.get("evaluate_champion")
            if cached then
                use_cached_value(cached)
            end
        """
        return self.execution_context.checkpoint_get(name)
