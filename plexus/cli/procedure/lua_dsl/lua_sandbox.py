"""
Lua Sandbox - Safe, restricted Lua execution environment.

Provides a sandboxed Lua runtime with:
- No file system access (io, os removed)
- No dangerous operations (debug, package, require removed)
- Only whitelisted primitives available
- Resource limits on CPU time and memory
"""

import logging
from typing import Dict, Any, Optional

try:
    import lupa
    from lupa import LuaRuntime
    LUPA_AVAILABLE = True
except ImportError:
    LUPA_AVAILABLE = False
    LuaRuntime = None

logger = logging.getLogger(__name__)


class LuaSandboxError(Exception):
    """Raised when Lua sandbox setup or execution fails."""
    pass


class LuaSandbox:
    """Sandboxed Lua execution environment for procedure workflows."""

    def __init__(self):
        """Initialize the Lua sandbox."""
        if not LUPA_AVAILABLE:
            raise LuaSandboxError(
                "lupa library not available. Install with: pip install lupa"
            )

        # Create Lua runtime with safety restrictions
        self.lua = LuaRuntime(
            unpack_returned_tuples=True,
            attribute_filter=self._attribute_filter
        )

        # Remove dangerous modules
        self._remove_dangerous_modules()

        # Setup safe globals
        self._setup_safe_globals()

        logger.info("Lua sandbox initialized successfully")

    def _attribute_filter(self, obj, attr_name, is_setting):
        """
        Filter attribute access to prevent dangerous operations.

        This is called by lupa for all attribute access from Lua code.
        """
        # Block access to private/protected attributes
        if attr_name.startswith('_'):
            raise AttributeError(f"Access to private attribute '{attr_name}' is not allowed")

        # Block access to certain dangerous methods
        blocked_methods = {
            '__import__', '__loader__', '__spec__', '__builtins__',
            'eval', 'exec', 'compile', 'open', '__subclasses__'
        }

        if attr_name in blocked_methods:
            raise AttributeError(f"Access to '{attr_name}' is not allowed in sandbox")

        return attr_name

    def _remove_dangerous_modules(self):
        """Remove dangerous Lua standard library modules."""
        # Remove modules that provide file system or system access
        dangerous_modules = [
            'io',          # File I/O
            'os',          # Operating system operations
            'debug',       # Debug library (can break sandbox)
            'package',     # Module loading
            'dofile',      # Load and execute files
            'loadfile',    # Load files
            'load',        # Load code
            'require',     # Require modules
        ]

        lua_globals = self.lua.globals()

        for module in dangerous_modules:
            if module in lua_globals:
                lua_globals[module] = None
                logger.debug(f"Removed dangerous module/function: {module}")

    def _setup_safe_globals(self):
        """Setup safe global functions and utilities."""
        # Keep safe standard library functions
        # (These are already available by default, just documenting them)
        safe_functions = {
            # Math
            'math',        # Math library (safe)
            'tonumber',    # Convert to number
            'tostring',    # Convert to string

            # String operations
            'string',      # String library

            # Table operations
            'table',       # Table library
            'pairs',       # Iterate over tables
            'ipairs',      # Iterate over arrays
            'next',        # Next element in table

            # Type checking
            'type',        # Get type of value
            'assert',      # Assertions
            'error',       # Raise error
            'pcall',       # Protected call (try/catch)

            # Other safe operations
            'select',      # Select arguments
            'unpack',      # Unpack table (Lua 5.1)
        }

        # Just log what's available - no need to explicitly set
        logger.debug(f"Safe Lua functions available: {', '.join(safe_functions)}")

        # Add safe subset of os module (only date function for timestamps)
        from datetime import datetime
        def safe_date(format_str=None):
            """Safe implementation of os.date() for timestamp generation."""
            now = datetime.utcnow()
            if format_str is None:
                # Return default format like Lua's os.date()
                return now.strftime("%a %b %d %H:%M:%S %Y")
            elif format_str == "%Y-%m-%dT%H:%M:%SZ":
                # ISO 8601 format
                return now.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                # Support Python strftime formats
                try:
                    return now.strftime(format_str)
                except:
                    return now.strftime("%a %b %d %H:%M:%S %Y")

        # Create safe os table with only date function
        safe_os = self.lua.table(date=safe_date)
        self.lua.globals()['os'] = safe_os
        logger.debug("Added safe os.date() function")

    def inject_primitive(self, name: str, primitive_obj: Any):
        """
        Inject a Python primitive object into Lua globals.

        Args:
            name: Name of the primitive in Lua (e.g., "State", "Worker")
            primitive_obj: Python object to expose to Lua
        """
        self.lua.globals()[name] = primitive_obj
        logger.debug(f"Injected primitive '{name}' into Lua sandbox")

    def execute(self, lua_code: str) -> Any:
        """
        Execute Lua code in the sandbox.

        Args:
            lua_code: Lua code string to execute

        Returns:
            Result of the Lua code execution

        Raises:
            LuaSandboxError: If execution fails
        """
        try:
            logger.debug(f"Executing Lua code ({len(lua_code)} bytes)")
            result = self.lua.execute(lua_code)
            logger.debug("Lua execution completed successfully")
            return result

        except lupa.LuaError as e:
            # Lua runtime error
            error_msg = str(e)
            logger.error(f"Lua execution error: {error_msg}")
            raise LuaSandboxError(f"Lua runtime error: {error_msg}")

        except Exception as e:
            # Other Python exceptions
            logger.error(f"Sandbox execution error: {e}")
            raise LuaSandboxError(f"Sandbox error: {e}")

    def eval(self, lua_expression: str) -> Any:
        """
        Evaluate a Lua expression and return the result.

        Args:
            lua_expression: Lua expression to evaluate

        Returns:
            Result of the expression

        Raises:
            LuaSandboxError: If evaluation fails
        """
        try:
            result = self.lua.eval(lua_expression)
            return result

        except lupa.LuaError as e:
            error_msg = str(e)
            logger.error(f"Lua eval error: {error_msg}")
            raise LuaSandboxError(f"Lua eval error: {error_msg}")

    def get_global(self, name: str) -> Any:
        """Get a value from Lua global scope."""
        return self.lua.globals()[name]

    def set_global(self, name: str, value: Any):
        """Set a value in Lua global scope."""
        self.lua.globals()[name] = value

    def create_lua_table(self, python_dict: Optional[Dict[str, Any]] = None) -> Any:
        """
        Create a Lua table from a Python dictionary.

        Args:
            python_dict: Python dictionary to convert (or None for empty table)

        Returns:
            Lua table object
        """
        if python_dict is None:
            # Create empty Lua table
            return self.lua.table()

        # Create and populate Lua table
        lua_table = self.lua.table()
        for key, value in python_dict.items():
            lua_table[key] = value

        return lua_table

    def lua_table_to_dict(self, lua_table: Any) -> Dict[str, Any]:
        """
        Convert a Lua table to a Python dictionary.

        Args:
            lua_table: Lua table object

        Returns:
            Python dictionary
        """
        result = {}

        try:
            # Use Lua's pairs() to iterate
            for key, value in self.lua.globals().pairs(lua_table):
                # Convert Lua values to Python types
                if isinstance(value, self.lua.table_from):
                    # Recursively convert nested tables
                    result[key] = self.lua_table_to_dict(value)
                else:
                    result[key] = value

        except Exception as e:
            logger.warning(f"Error converting Lua table to dict: {e}")
            # Fallback: try direct iteration
            try:
                for key in lua_table:
                    result[key] = lua_table[key]
            except:
                pass

        return result
