"""
Retry Primitive - Error handling with exponential backoff.

Provides:
- Retry.with_backoff(fn, options) - Retry function with exponential backoff
"""

import logging
import time
from typing import Callable, Any, Optional, Dict

logger = logging.getLogger(__name__)


class RetryPrimitive:
    """
    Handles retry logic with exponential backoff for procedures.

    Enables workflows to:
    - Retry failed operations automatically
    - Use exponential backoff between attempts
    - Handle transient errors gracefully
    - Configure max attempts and delays
    """

    def __init__(self):
        """Initialize Retry primitive."""
        logger.debug("RetryPrimitive initialized")

    def with_backoff(self, fn: Callable, options: Optional[Dict[str, Any]] = None) -> Any:
        """
        Retry a function with exponential backoff.

        Args:
            fn: Function to retry (Lua function)
            options: Dict with:
                - max_attempts: Maximum retry attempts (default: 3)
                - initial_delay: Initial delay in seconds (default: 1)
                - max_delay: Maximum delay in seconds (default: 60)
                - backoff_factor: Multiplier for delay (default: 2)
                - on_error: Optional callback when error occurs

        Returns:
            Result from successful function call

        Raises:
            Exception: If all retry attempts fail

        Example (Lua):
            local result = Retry.with_backoff(function()
                -- Try to fetch data from API
                local data = fetch_api_data()
                if not data then
                    error("API returned no data")
                end
                return data
            end, {
                max_attempts = 5,
                initial_delay = 2,
                backoff_factor = 2
            })
        """
        # Convert Lua tables to Python dicts if needed
        opts = self._convert_lua_to_python(options) or {}

        max_attempts = opts.get('max_attempts', 3)
        initial_delay = opts.get('initial_delay', 1.0)
        max_delay = opts.get('max_delay', 60.0)
        backoff_factor = opts.get('backoff_factor', 2.0)
        on_error = opts.get('on_error')

        attempt = 0
        delay = initial_delay
        last_error = None

        logger.info(f"Starting retry with_backoff (max_attempts={max_attempts})")

        while attempt < max_attempts:
            attempt += 1

            try:
                logger.debug(f"Retry attempt {attempt}/{max_attempts}")
                result = fn()
                logger.info(f"Success on attempt {attempt}/{max_attempts}")
                return result

            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt}/{max_attempts} failed: {e}")

                # Call error callback if provided
                if on_error and callable(on_error):
                    try:
                        on_error({
                            'attempt': attempt,
                            'max_attempts': max_attempts,
                            'error': str(e),
                            'delay': delay
                        })
                    except Exception as callback_error:
                        logger.error(f"Error callback failed: {callback_error}")

                # Check if we should retry
                if attempt >= max_attempts:
                    logger.error(f"All {max_attempts} attempts failed")
                    raise Exception(f"Retry failed after {max_attempts} attempts: {last_error}")

                # Wait with exponential backoff
                logger.info(f"Waiting {delay:.2f}s before retry...")
                time.sleep(delay)

                # Increase delay for next attempt (exponential backoff)
                delay = min(delay * backoff_factor, max_delay)

        # Should not reach here, but handle it
        raise Exception(f"Retry logic error: {last_error}")

    def _convert_lua_to_python(self, value: Any) -> Any:
        """
        Recursively convert Lua tables to Python dicts.

        Args:
            value: Lua value to convert

        Returns:
            Python equivalent (dict or primitive)
        """
        if value is None:
            return None

        # Import lupa for table checking
        try:
            from lupa import lua_type

            # Check if it's a Lua table
            if lua_type(value) == 'table':
                result = {}
                for k, v in value.items():
                    # Convert key and value recursively
                    py_key = self._convert_lua_to_python(k) if lua_type(k) == 'table' else k
                    py_value = self._convert_lua_to_python(v)
                    result[py_key] = py_value
                return result
            else:
                # Primitive value or function
                return value

        except ImportError:
            # If lupa not available, just return as-is
            return value

    def __repr__(self) -> str:
        return "RetryPrimitive()"
