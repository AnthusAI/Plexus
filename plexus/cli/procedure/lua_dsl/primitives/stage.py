"""
Stage Primitive - Workflow progress tracking.

Provides:
- Stage.current() - Get current stage name
- Stage.set(stage) - Set current stage
- Stage.advance() - Move to next stage
- Stage.is(stage) - Check if in specific stage
- Stage.history() - Get stage transition history
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class StagePrimitive:
    """
    Manages workflow stage tracking for procedures.

    Enables workflows to:
    - Track current workflow stage
    - Validate stage transitions
    - Query stage state
    - Maintain stage history
    """

    def __init__(self, declared_stages: Optional[List[str]] = None, lua_sandbox=None):
        """
        Initialize Stage primitive.

        Args:
            declared_stages: List of valid stage names from YAML config
            lua_sandbox: LuaSandbox for creating Lua tables (optional)
        """
        self.declared_stages = declared_stages or []
        self.lua_sandbox = lua_sandbox
        self._current_stage: Optional[str] = None
        self._history: List[Dict[str, Any]] = []
        logger.debug(f"StagePrimitive initialized with stages: {self.declared_stages}")

    def current(self) -> Optional[str]:
        """
        Get current stage name.

        Returns:
            Current stage name or None if not set

        Example (Lua):
            local stage = Stage.current()
            if stage == "processing" then
                Log.info("Currently processing")
            end
        """
        logger.debug(f"Stage.current() = {self._current_stage}")
        return self._current_stage

    def set(self, stage: str) -> None:
        """
        Set current stage.

        Args:
            stage: Stage name to set

        Raises:
            ValueError: If stage not in declared stages list

        Example (Lua):
            Stage.set("processing")
            Log.info("Moved to processing stage")
        """
        # Validate stage if we have a declared list
        if self.declared_stages and stage not in self.declared_stages:
            valid_stages = ", ".join(self.declared_stages)
            error_msg = f"Invalid stage '{stage}'. Valid stages: {valid_stages}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        old_stage = self._current_stage
        self._current_stage = stage

        # Record transition in history
        self._history.append({
            'from_stage': old_stage,
            'to_stage': stage,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

        logger.info(f"Stage transition: {old_stage} -> {stage}")

    def advance(self) -> Optional[str]:
        """
        Move to next stage in declared sequence.

        Returns:
            New current stage name, or None if at end

        Raises:
            ValueError: If current stage not set or not in declared stages

        Example (Lua):
            Stage.set("setup")
            -- ... do work ...
            Stage.advance()  -- Moves to next stage in sequence
            Log.info("Advanced to", {stage = Stage.current()})
        """
        if not self._current_stage:
            raise ValueError("Cannot advance: no current stage set. Call Stage.set() first.")

        if not self.declared_stages:
            raise ValueError("Cannot advance: no stages declared in procedure config")

        try:
            current_index = self.declared_stages.index(self._current_stage)
        except ValueError:
            raise ValueError(f"Current stage '{self._current_stage}' not in declared stages: {self.declared_stages}")

        # Check if there's a next stage
        if current_index >= len(self.declared_stages) - 1:
            logger.warning(f"Cannot advance: already at final stage '{self._current_stage}'")
            return None

        # Move to next stage
        next_stage = self.declared_stages[current_index + 1]
        self.set(next_stage)
        return next_stage

    def is_current(self, stage: str) -> bool:
        """
        Check if currently in specific stage.

        Args:
            stage: Stage name to check

        Returns:
            True if current stage matches, False otherwise

        Example (Lua):
            if Stage.is("processing") then  -- 'is' is mapped to is_current()
                Log.info("Currently processing")
            end
        """
        result = self._current_stage == stage
        logger.debug(f"Stage.is('{stage}') = {result} (current: {self._current_stage})")
        return result

    def history(self):
        """
        Get stage transition history.

        Returns:
            Lua table (if lua_sandbox available) or Python list of transition records

        Example (Lua):
            local history = Stage.history()
            for i, transition in ipairs(history) do
                Log.debug("Transition", {
                    from = transition.from_stage,
                    to = transition.to_stage,
                    timestamp = transition.timestamp
                })
            end
        """
        logger.debug(f"Retrieved {len(self._history)} stage transitions")

        # If lua_sandbox available, create proper Lua table
        if self.lua_sandbox:
            lua_table = self.lua_sandbox.lua.table()
            for i, transition in enumerate(self._history, start=1):
                lua_table[i] = transition.copy()  # Lua uses 1-based indexing
            return lua_table
        else:
            # Fallback: return list
            return [transition.copy() for transition in self._history]

    def count(self) -> int:
        """
        Get count of stage transitions.

        Returns:
            Number of transitions in history
        """
        return len(self._history)

    def clear_history(self) -> None:
        """
        Clear stage transition history (mainly for testing).

        Note: Does not affect current stage.
        """
        count = len(self._history)
        self._history.clear()
        logger.debug(f"Cleared {count} stage transitions from history")

    def __repr__(self) -> str:
        return f"StagePrimitive(current={self._current_stage}, stages={self.declared_stages})"
