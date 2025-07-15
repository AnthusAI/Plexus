"""
Lua runtime integration utilities for LogicalNode and LogicalClassifier.
Provides Python-Lua data conversion and execution capabilities.
"""

from typing import Any, Dict, Optional, Union, List
import json
from plexus.CustomLogging import logging

try:
    import lupa
    LUPA_AVAILABLE = True
except ImportError:
    LUPA_AVAILABLE = False
    logging.warning("lupa library not available. Lua support will be disabled.")


class LuaRuntime:
    """Runtime for executing Lua code with Python-Lua data conversion."""
    
    def __init__(self):
        if not LUPA_AVAILABLE:
            raise ImportError("lupa library is required for Lua support. Install with: pip install lupa")
        
        self.lua = lupa.LuaRuntime(unpack_returned_tuples=True)
        self._setup_lua_environment()
    
    def _setup_lua_environment(self):
        """Set up the Lua environment with utility functions and logging."""
        # Add JSON utilities
        self.lua.execute("""
            json = {}
            function json.encode(obj)
                return python.json_encode(obj)
            end
            
            function json.decode(str)
                return python.json_decode(str)
            end
        """)
        
        # Add logging functions
        self.lua.execute("""
            log = {}
            function log.info(message)
                python.log_info(message)
            end
            
            function log.debug(message)
                python.log_debug(message)
            end
            
            function log.warning(message)
                python.log_warning(message)
            end
            
            function log.error(message)
                python.log_error(message)
            end
            
            -- Alias for print
            function print(...)
                local args = {...}
                local message = ""
                for i, v in ipairs(args) do
                    message = message .. tostring(v)
                    if i < #args then
                        message = message .. " "
                    end
                end
                python.log_info(message)
            end
        """)
        
        # Set up Python bridge
        self.lua.globals().python = self.lua.table_from({
            'json_encode': self._json_encode,
            'json_decode': self._json_decode,
            'log_info': lambda msg: logging.info(f"[Lua] {msg}"),
            'log_debug': lambda msg: logging.debug(f"[Lua] {msg}"),
            'log_warning': lambda msg: logging.warning(f"[Lua] {msg}"),
            'log_error': lambda msg: logging.error(f"[Lua] {msg}"),
        })
    
    def _json_encode(self, obj: Any) -> str:
        """Convert Python object to JSON string for Lua."""
        return json.dumps(obj, default=str)
    
    def _json_decode(self, json_str: str) -> Any:
        """Convert JSON string to Python object from Lua."""
        return json.loads(json_str)
    
    def python_to_lua(self, obj: Any) -> Any:
        """Convert Python objects to Lua-compatible format."""
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, dict):
            lua_table = self.lua.table()
            for key, value in obj.items():
                lua_table[key] = self.python_to_lua(value)
            return lua_table
        elif isinstance(obj, (list, tuple)):
            lua_table = self.lua.table()
            for i, value in enumerate(obj, 1):  # Lua arrays are 1-indexed
                lua_table[i] = self.python_to_lua(value)
            return lua_table
        else:
            # For complex objects, convert to JSON string
            return self._json_encode(obj)
    
    def lua_to_python(self, obj: Any) -> Any:
        """Convert Lua objects to Python-compatible format."""
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif lupa.lua_type(obj) == 'table':
            # Check if it's an array-like table (consecutive integer keys starting from 1)
            keys = list(obj.keys())
            if keys and all(isinstance(k, int) for k in keys):
                # Sort keys to handle them in order
                sorted_keys = sorted(keys)
                if sorted_keys == list(range(1, len(sorted_keys) + 1)):
                    # It's an array
                    return [self.lua_to_python(obj[k]) for k in sorted_keys]
            
            # It's a dictionary
            return {k: self.lua_to_python(v) for k, v in obj.items()}
        else:
            # Convert unknown types to string
            return str(obj)
    
    def execute_function(self, code: str, function_name: str, context: Dict[str, Any]) -> Any:
        """Execute a Lua function with given context."""
        try:
            # Convert context to Lua format
            lua_context = self.python_to_lua(context)
            
            # Execute the code
            self.lua.execute(code)
            
            # Get the function
            lua_function = self.lua.globals()[function_name]
            if not lua_function:
                raise ValueError(f"Lua code must define a '{function_name}' function")
            
            # Call the function with context
            result = lua_function(lua_context)
            
            # Convert result back to Python
            return self.lua_to_python(result)
            
        except Exception as e:
            logging.error(f"Error executing Lua function: {str(e)}")
            raise
    
    def execute_score_function(self, code: str, parameters: Any, score_input: Any) -> Any:
        """Execute a Lua score function with parameters and input."""
        try:
            # Convert parameters and input to Lua format
            lua_parameters = self.python_to_lua(parameters.model_dump() if hasattr(parameters, 'model_dump') else parameters)
            lua_input = self.python_to_lua({
                'text': score_input.text,
                'metadata': score_input.metadata,
                'results': score_input.results
            } if hasattr(score_input, 'text') else score_input)
            
            # Execute the code
            self.lua.execute(code)
            
            # Get the score function
            lua_function = self.lua.globals()['score']
            if not lua_function:
                raise ValueError("Lua code must define a 'score' function")
            
            # Call the function with parameters and input
            result = lua_function(lua_parameters, lua_input)
            
            # Convert result back to Python
            python_result = self.lua_to_python(result)
            
            # Convert to Score.Result if it's a dictionary with the right structure
            if isinstance(python_result, dict) and 'value' in python_result:
                # Import here to avoid circular imports
                from plexus.scores.Score import Score
                return Score.Result(
                    parameters=parameters,
                    value=python_result['value'],
                    explanation=python_result.get('explanation', ''),
                    confidence=python_result.get('confidence'),
                    metadata=python_result.get('metadata', {})
                )
            
            return python_result
            
        except Exception as e:
            logging.error(f"Error executing Lua score function: {str(e)}")
            raise


class LuaCompatibleError(Exception):
    """Exception for Lua compatibility issues."""
    pass


# Global instance for reuse
_lua_runtime = None

def get_lua_runtime() -> LuaRuntime:
    """Get shared Lua runtime instance."""
    global _lua_runtime
    if _lua_runtime is None:
        _lua_runtime = LuaRuntime()
    return _lua_runtime


def is_lua_available() -> bool:
    """Check if Lua runtime is available."""
    return LUPA_AVAILABLE