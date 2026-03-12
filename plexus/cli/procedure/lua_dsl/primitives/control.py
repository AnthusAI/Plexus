"""
Control Primitives - Flow control and termination.

Provides:
- Iterations.current() - Get current iteration number
- Iterations.exceeded(max) - Check if exceeded max iterations
- Stop.requested() - Check if stop was requested
- Stop.reason() - Get stop reason
- Stop.success() - Check if stop was successful
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class IterationsPrimitive:
    """
    Tracks iteration count for procedure execution.

    Provides safety limits and iteration-based control flow.
    """

    def __init__(self):
        """Initialize iteration counter."""
        self._current_iteration = 0
        logger.debug("IterationsPrimitive initialized")

    def current(self) -> int:
        """
        Get the current iteration number.

        Returns:
            Current iteration count (0-indexed)

        Example (Lua):
            local iter = Iterations.current()
            Log.info("Iteration: " .. iter)
        """
        return self._current_iteration

    def exceeded(self, max_iterations: int) -> bool:
        """
        Check if current iteration has exceeded the maximum.

        Args:
            max_iterations: Maximum allowed iterations

        Returns:
            True if current iteration >= max_iterations

        Example (Lua):
            if Iterations.exceeded(100) then
                return {success = false, reason = "Max iterations exceeded"}
            end
        """
        exceeded = self._current_iteration >= max_iterations
        if exceeded:
            logger.warning(
                f"Iterations exceeded: {self._current_iteration} >= {max_iterations}"
            )
        return exceeded

    def increment(self) -> int:
        """
        Increment the iteration counter.

        Returns:
            New iteration count

        Note: This is called internally by the runtime, not from Lua
        """
        self._current_iteration += 1
        logger.debug(f"Iteration incremented to {self._current_iteration}")
        return self._current_iteration

    def reset(self) -> None:
        """Reset iteration counter (mainly for testing)."""
        self._current_iteration = 0
        logger.debug("Iterations reset to 0")

    def __repr__(self) -> str:
        return f"IterationsPrimitive(current={self._current_iteration})"


class StopPrimitive:
    """
    Manages procedure termination state.

    Tracks when a stop was requested and the reason/success status.
    """

    def __init__(self):
        """Initialize stop state."""
        self._requested = False
        self._reason: Optional[str] = None
        self._success = True
        logger.debug("StopPrimitive initialized")

    def requested(self) -> bool:
        """
        Check if a stop was requested.

        Returns:
            True if stop was requested

        Example (Lua):
            if Stop.requested() then
                return {success = true, message = "Procedure stopped"}
            end
        """
        return self._requested

    def reason(self) -> Optional[str]:
        """
        Get the reason for stopping.

        Returns:
            Stop reason string or None if not stopped

        Example (Lua):
            if Stop.requested() then
                Log.info("Stopped because: " .. Stop.reason())
            end
        """
        return self._reason

    def success(self) -> bool:
        """
        Check if the stop was due to successful completion.

        Returns:
            True if stopped successfully, False if stopped due to error

        Example (Lua):
            if Stop.requested() and Stop.success() then
                return {success = true}
            else
                return {success = false}
            end
        """
        return self._success

    def request(self, reason: str, success: bool = True) -> None:
        """
        Request a stop (called by tools or runtime).

        Args:
            reason: Reason for stopping
            success: Whether this is a successful completion

        Note: This is called internally, not from Lua
        """
        self._requested = True
        self._reason = reason
        self._success = success

        log_level = logging.INFO if success else logging.WARNING
        logger.log(
            log_level,
            f"Stop requested: {reason} (success={success})"
        )

    def reset(self) -> None:
        """Reset stop state (mainly for testing)."""
        self._requested = False
        self._reason = None
        self._success = True
        logger.debug("Stop state reset")

    def __repr__(self) -> str:
        return f"StopPrimitive(requested={self._requested}, success={self._success})"
