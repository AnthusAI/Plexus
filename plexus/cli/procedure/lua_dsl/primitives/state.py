"""
State Primitive - Mutable state management for procedures.

Provides:
- State.get(key, default) - Get state value
- State.set(key, value) - Set state value
- State.increment(key, amount) - Increment numeric value
- State.append(key, value) - Append to list
- State.all() - Get all state as table
"""

import logging
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)


class StatePrimitive:
    """
    Manages mutable state for procedure execution.

    State is preserved across agent turns and can be used to track
    progress, accumulate results, and coordinate between agents.
    """

    def __init__(self):
        """Initialize state storage."""
        self._state: Dict[str, Any] = {}
        logger.debug("StatePrimitive initialized")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from state.

        Args:
            key: State key to retrieve
            default: Default value if key not found

        Returns:
            Stored value or default

        Example (Lua):
            local count = State.get("hypothesis_count", 0)
        """
        value = self._state.get(key, default)
        logger.debug(f"State.get('{key}') = {value}")
        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set a value in state.

        Args:
            key: State key to set
            value: Value to store

        Example (Lua):
            State.set("current_phase", "exploration")
        """
        self._state[key] = value
        logger.debug(f"State.set('{key}', {value})")

    def increment(self, key: str, amount: float = 1) -> float:
        """
        Increment a numeric value in state.

        Args:
            key: State key to increment
            amount: Amount to increment by (default 1)

        Returns:
            New value after increment

        Example (Lua):
            State.increment("hypotheses_filed")
            State.increment("score", 10)
        """
        current = self._state.get(key, 0)

        # Ensure numeric
        if not isinstance(current, (int, float)):
            logger.warning(f"State.increment: '{key}' is not numeric, resetting to 0")
            current = 0

        new_value = current + amount
        self._state[key] = new_value

        logger.debug(f"State.increment('{key}', {amount}) = {new_value}")
        return new_value

    def append(self, key: str, value: Any) -> None:
        """
        Append a value to a list in state.

        Args:
            key: State key (will be created as list if doesn't exist)
            value: Value to append

        Example (Lua):
            State.append("nodes_created", node_id)
        """
        if key not in self._state:
            self._state[key] = []
        elif not isinstance(self._state[key], list):
            logger.warning(f"State.append: '{key}' is not a list, converting")
            self._state[key] = [self._state[key]]

        self._state[key].append(value)
        logger.debug(f"State.append('{key}', {value}) -> list length: {len(self._state[key])}")

    def all(self) -> Dict[str, Any]:
        """
        Get all state as a dictionary.

        Returns:
            Complete state dictionary

        Example (Lua):
            local state = State.all()
            for k, v in pairs(state) do
                print(k, v)
            end
        """
        logger.debug(f"State.all() returning {len(self._state)} keys")
        return self._state.copy()

    def clear(self) -> None:
        """Clear all state (mainly for testing)."""
        self._state.clear()
        logger.debug("State.clear() - all state cleared")

    def __repr__(self) -> str:
        return f"StatePrimitive({len(self._state)} keys)"
