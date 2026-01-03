"""
Tool Primitive - Tool call tracking and result access.

Provides:
- Tool.called(name) - Check if tool was called
- Tool.last_result(name) - Get last result from named tool
- Tool.last_call(name) - Get full call info
"""

import logging
from typing import Any, Optional, Dict, List

logger = logging.getLogger(__name__)


class ToolCall:
    """Represents a single tool call with arguments and result."""

    def __init__(self, name: str, args: Dict[str, Any], result: Any):
        self.name = name
        self.args = args
        self.result = result
        self.timestamp = None  # Could add timestamp tracking

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Lua access."""
        return {
            'name': self.name,
            'args': self.args,
            'result': self.result
        }

    def __repr__(self) -> str:
        return f"ToolCall({self.name}, args={self.args})"


class ToolPrimitive:
    """
    Tracks tool calls and provides access to results.

    Maintains a history of tool calls and their results, allowing
    Lua code to check what tools were used and access their outputs.
    """

    def __init__(self):
        """Initialize tool tracking."""
        self._tool_calls: List[ToolCall] = []
        self._last_calls: Dict[str, ToolCall] = {}  # name -> last call
        logger.debug("ToolPrimitive initialized")

    def called(self, tool_name: str) -> bool:
        """
        Check if a tool was called at least once.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if the tool was called

        Example (Lua):
            if Tool.called("done") then
                Log.info("Done tool was called")
            end
        """
        called = tool_name in self._last_calls
        logger.debug(f"Tool.called('{tool_name}') = {called}")
        return called

    def last_result(self, tool_name: str) -> Any:
        """
        Get the last result from a named tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Last result from the tool, or None if never called

        Example (Lua):
            local result = Tool.last_result("search")
            if result then
                Log.info("Search found: " .. result)
            end
        """
        if tool_name not in self._last_calls:
            logger.debug(f"Tool.last_result('{tool_name}') = None (never called)")
            return None

        result = self._last_calls[tool_name].result
        logger.debug(f"Tool.last_result('{tool_name}') = {result}")
        return result

    def last_call(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get full information about the last call to a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Dictionary with 'name', 'args', 'result' or None if never called

        Example (Lua):
            local call = Tool.last_call("search")
            if call then
                Log.info("Search was called with: " .. call.args.query)
                Log.info("Result: " .. call.result)
            end
        """
        if tool_name not in self._last_calls:
            logger.debug(f"Tool.last_call('{tool_name}') = None (never called)")
            return None

        call_dict = self._last_calls[tool_name].to_dict()
        logger.debug(f"Tool.last_call('{tool_name}') = {call_dict}")
        return call_dict

    def record_call(self, tool_name: str, args: Dict[str, Any], result: Any) -> None:
        """
        Record a tool call (called by runtime after tool execution).

        Args:
            tool_name: Name of the tool
            args: Arguments passed to the tool
            result: Result returned by the tool

        Note: This is called internally by the runtime, not from Lua
        """
        call = ToolCall(tool_name, args, result)
        self._tool_calls.append(call)
        self._last_calls[tool_name] = call

        logger.debug(
            f"Tool call recorded: {tool_name} -> "
            f"{len(self._tool_calls)} total calls"
        )

    def get_all_calls(self) -> List[ToolCall]:
        """
        Get all tool calls (for debugging/logging).

        Returns:
            List of all ToolCall objects
        """
        return self._tool_calls.copy()

    def get_call_count(self, tool_name: Optional[str] = None) -> int:
        """
        Get the number of times a tool was called.

        Args:
            tool_name: Name of tool (or None for total count)

        Returns:
            Number of calls
        """
        if tool_name is None:
            return len(self._tool_calls)

        return sum(1 for call in self._tool_calls if call.name == tool_name)

    def reset(self) -> None:
        """Reset tool tracking (mainly for testing)."""
        self._tool_calls.clear()
        self._last_calls.clear()
        logger.debug("Tool tracking reset")

    def __repr__(self) -> str:
        return f"ToolPrimitive({len(self._tool_calls)} calls)"
