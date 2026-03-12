"""
Json Primitive - JSON serialization/deserialization.

Provides:
- Json.encode(data) - Serialize Lua table/value to JSON string
- Json.decode(json_str) - Parse JSON string to Lua table
"""

import logging
import json
from typing import Any, Dict

logger = logging.getLogger(__name__)


class JsonPrimitive:
    """
    Handles JSON encoding and decoding for procedures.

    Enables workflows to:
    - Serialize Lua tables to JSON strings
    - Parse JSON strings into Lua tables
    - Handle data interchange with external systems
    """

    def __init__(self, lua_sandbox=None):
        """
        Initialize Json primitive.

        Args:
            lua_sandbox: LuaSandbox for creating Lua tables (optional)
        """
        self.lua_sandbox = lua_sandbox
        logger.debug("JsonPrimitive initialized")

    def encode(self, data: Any) -> str:
        """
        Encode Lua data structure to JSON string.

        Args:
            data: Lua table or primitive value to encode

        Returns:
            JSON string representation

        Raises:
            ValueError: If data cannot be serialized to JSON

        Example (Lua):
            local user = {
                name = "Alice",
                age = 30,
                active = true
            }
            local json_str = Json.encode(user)
            Log.info("Encoded JSON", {json = json_str})
            -- json_str = '{"name": "Alice", "age": 30, "active": true}'
        """
        try:
            # Convert Lua tables to Python dicts recursively if needed
            python_data = self._lua_to_python(data)

            json_str = json.dumps(python_data, ensure_ascii=False, indent=None)
            logger.debug(f"Encoded data to JSON ({len(json_str)} bytes)")
            return json_str

        except (TypeError, ValueError) as e:
            error_msg = f"Failed to encode to JSON: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def decode(self, json_str: str):
        """
        Decode JSON string to Lua table.

        Args:
            json_str: JSON string to parse

        Returns:
            Lua table with parsed data

        Raises:
            ValueError: If JSON is malformed

        Example (Lua):
            local json_str = '{"name": "Bob", "scores": [85, 92, 78]}'
            local data = Json.decode(json_str)
            Log.info("Decoded data", {
                name = data.name,
                first_score = data.scores[1]
            })
        """
        try:
            # Parse JSON to Python dict
            python_data = json.loads(json_str)
            logger.debug(f"Decoded JSON string ({len(json_str)} bytes)")

            # Convert to Lua table if lua_sandbox available
            if self.lua_sandbox:
                return self._python_to_lua(python_data)
            else:
                # Fallback: return Python dict (will work but not ideal)
                return python_data

        except json.JSONDecodeError as e:
            error_msg = f"Failed to decode JSON: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def _lua_to_python(self, value: Any) -> Any:
        """
        Recursively convert Lua tables to Python dicts/lists.

        Args:
            value: Lua value to convert

        Returns:
            Python equivalent (dict, list, or primitive)
        """
        # Import lupa for table checking
        try:
            from lupa import lua_type

            # Check if it's a Lua table
            if lua_type(value) == 'table':
                # Try to determine if it's an array or dict
                # Lua arrays have consecutive integer keys starting at 1
                result = {}
                is_array = True
                keys = []

                for k, v in value.items():
                    keys.append(k)
                    result[k] = self._lua_to_python(v)
                    if not isinstance(k, int) or k < 1:
                        is_array = False

                # Check if keys are consecutive integers starting at 1
                if is_array and keys:
                    keys_sorted = sorted(keys)
                    if keys_sorted != list(range(1, len(keys) + 1)):
                        is_array = False

                # Convert to list if it's an array
                if is_array and keys:
                    return [result[i] for i in range(1, len(keys) + 1)]
                else:
                    return result
            else:
                # Primitive value
                return value

        except ImportError:
            # If lupa not available, just return as-is
            return value

    def _python_to_lua(self, value: Any):
        """
        Recursively convert Python dicts/lists to Lua tables.

        Args:
            value: Python value to convert

        Returns:
            Lua table or primitive value
        """
        if not self.lua_sandbox:
            return value

        if isinstance(value, dict):
            # Convert dict to Lua table
            lua_table = self.lua_sandbox.lua.table()
            for k, v in value.items():
                lua_table[k] = self._python_to_lua(v)
            return lua_table

        elif isinstance(value, (list, tuple)):
            # Convert list to Lua array (1-indexed)
            lua_table = self.lua_sandbox.lua.table()
            for i, item in enumerate(value, start=1):
                lua_table[i] = self._python_to_lua(item)
            return lua_table

        else:
            # Primitive value (str, int, float, bool, None)
            return value

    def __repr__(self) -> str:
        return "JsonPrimitive()"
