"""
Log Primitive - Logging operations.

Provides:
- Log.debug(message, context={}) - Debug logging
- Log.info(message, context={}) - Info logging
- Log.warn(message, context={}) - Warning logging
- Log.error(message, context={}) - Error logging
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class LogPrimitive:
    """
    Provides logging operations for procedures.

    All methods log using Python's standard logging module
    with appropriate log levels.
    """

    def __init__(self, procedure_id: str):
        """
        Initialize Log primitive.

        Args:
            procedure_id: ID of the running procedure (for context)
        """
        self.procedure_id = procedure_id
        self.logger = logging.getLogger(f"procedure.{procedure_id}")

    def _format_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Format log message with context."""
        if context:
            import json
            # Convert Lua tables to Python dicts
            context_dict = self._lua_to_python(context)
            context_str = json.dumps(context_dict, indent=2)
            return f"{message}\nContext: {context_str}"
        return message

    def _lua_to_python(self, obj: Any) -> Any:
        """Convert Lua objects to Python equivalents recursively."""
        # Check if it's a Lua table
        if hasattr(obj, 'items'):  # Lua table with dict-like interface
            return {self._lua_to_python(k): self._lua_to_python(v) for k, v in obj.items()}
        elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):  # Lua array
            try:
                return [self._lua_to_python(v) for v in obj]
            except:
                # If iteration fails, return as-is
                return obj
        else:
            return obj

    def debug(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log debug message.

        Args:
            message: Debug message
            context: Optional context dict

        Example (Lua):
            Log.debug("Processing item", {index = i, item = item})
        """
        formatted = self._format_message(message, context)
        self.logger.debug(formatted)

    def info(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log info message.

        Args:
            message: Info message
            context: Optional context dict

        Example (Lua):
            Log.info("Phase complete", {duration = elapsed, items = count})
        """
        formatted = self._format_message(message, context)
        self.logger.info(formatted)

    def warn(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log warning message.

        Args:
            message: Warning message
            context: Optional context dict

        Example (Lua):
            Log.warn("Retry limit reached", {attempts = attempts})
        """
        formatted = self._format_message(message, context)
        self.logger.warning(formatted)

    def error(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log error message.

        Args:
            message: Error message
            context: Optional context dict

        Example (Lua):
            Log.error("Operation failed", {error = last_error})
        """
        formatted = self._format_message(message, context)
        self.logger.error(formatted)

    def __repr__(self) -> str:
        return f"LogPrimitive(procedure_id={self.procedure_id})"
