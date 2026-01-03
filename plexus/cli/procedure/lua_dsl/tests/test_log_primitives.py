"""
Tests for Log Primitive - Logging operations.

Tests all Log primitive methods:
- Log.debug(message, context)
- Log.info(message, context)
- Log.warn(message, context)
- Log.error(message, context)
"""

import pytest
import logging
from unittest.mock import Mock, patch
from plexus.cli.procedure.lua_dsl.primitives.log import LogPrimitive


@pytest.fixture
def log_primitive():
    """Create a fresh Log primitive for each test."""
    return LogPrimitive(procedure_id="test_procedure_123")


@pytest.fixture
def mock_logger(log_primitive):
    """Create a mock logger for the primitive."""
    mock = Mock()
    log_primitive.logger = mock
    return mock


class TestLogDebug:
    """Tests for Log.debug()"""

    def test_debug_simple_message(self, log_primitive, mock_logger):
        """Should log debug message."""
        log_primitive.debug("Debug message")
        mock_logger.debug.assert_called_once_with("Debug message")

    def test_debug_message_with_context(self, log_primitive, mock_logger):
        """Should log debug message with context dict."""
        log_primitive.debug("Processing item", {"index": 1, "name": "test"})

        call_args = mock_logger.debug.call_args[0][0]
        assert "Processing item" in call_args
        assert "Context:" in call_args
        assert "index" in call_args
        assert "name" in call_args

    def test_debug_with_empty_context(self, log_primitive, mock_logger):
        """Should handle empty context dict."""
        log_primitive.debug("Message", {})

        call_args = mock_logger.debug.call_args[0][0]
        assert "Message" in call_args
        # Empty dict doesn't add Context: prefix in implementation
        assert call_args == "Message"

    def test_debug_with_none_context(self, log_primitive, mock_logger):
        """Should handle None context."""
        log_primitive.debug("Message", None)
        mock_logger.debug.assert_called_once_with("Message")

    def test_debug_with_nested_context(self, log_primitive, mock_logger):
        """Should handle nested dict context."""
        context = {
            "user": {"name": "Alice", "id": 123},
            "settings": {"theme": "dark"}
        }
        log_primitive.debug("User action", context)

        call_args = mock_logger.debug.call_args[0][0]
        assert "User action" in call_args
        assert "Alice" in call_args

    def test_debug_with_list_context(self, log_primitive, mock_logger):
        """Should handle list values in context."""
        log_primitive.debug("Items processed", {"items": [1, 2, 3]})

        call_args = mock_logger.debug.call_args[0][0]
        assert "Items processed" in call_args
        assert "items" in call_args

    def test_debug_multiple_calls(self, log_primitive, mock_logger):
        """Should handle multiple debug calls."""
        log_primitive.debug("Message 1")
        log_primitive.debug("Message 2")
        log_primitive.debug("Message 3")

        assert mock_logger.debug.call_count == 3


class TestLogInfo:
    """Tests for Log.info()"""

    def test_info_simple_message(self, log_primitive, mock_logger):
        """Should log info message."""
        log_primitive.info("Info message")
        mock_logger.info.assert_called_once_with("Info message")

    def test_info_message_with_context(self, log_primitive, mock_logger):
        """Should log info message with context dict."""
        log_primitive.info("Phase complete", {"duration": 5.2, "items": 42})

        call_args = mock_logger.info.call_args[0][0]
        assert "Phase complete" in call_args
        assert "Context:" in call_args
        assert "duration" in call_args
        assert "items" in call_args

    def test_info_with_boolean_context(self, log_primitive, mock_logger):
        """Should handle boolean values in context."""
        log_primitive.info("Status", {"success": True, "failed": False})

        call_args = mock_logger.info.call_args[0][0]
        assert "Status" in call_args
        assert "success" in call_args

    def test_info_with_numeric_context(self, log_primitive, mock_logger):
        """Should handle numeric values in context."""
        log_primitive.info("Metrics", {"count": 100, "average": 45.67, "total": 4567})

        call_args = mock_logger.info.call_args[0][0]
        assert "Metrics" in call_args
        assert "count" in call_args
        assert "100" in call_args

    def test_info_with_none_value_in_context(self, log_primitive, mock_logger):
        """Should handle None values in context."""
        log_primitive.info("Result", {"data": None, "error": None})

        call_args = mock_logger.info.call_args[0][0]
        assert "Result" in call_args
        assert "null" in call_args  # JSON representation of None


class TestLogWarn:
    """Tests for Log.warn()"""

    def test_warn_simple_message(self, log_primitive, mock_logger):
        """Should log warning message."""
        log_primitive.warn("Warning message")
        mock_logger.warning.assert_called_once_with("Warning message")

    def test_warn_message_with_context(self, log_primitive, mock_logger):
        """Should log warning message with context dict."""
        log_primitive.warn("Retry limit reached", {"attempts": 3, "max_attempts": 3})

        call_args = mock_logger.warning.call_args[0][0]
        assert "Retry limit reached" in call_args
        assert "Context:" in call_args
        assert "attempts" in call_args

    def test_warn_with_error_context(self, log_primitive, mock_logger):
        """Should handle error information in context."""
        log_primitive.warn("Operation slow", {"duration": 30.5, "threshold": 10})

        call_args = mock_logger.warning.call_args[0][0]
        assert "Operation slow" in call_args
        assert "duration" in call_args

    def test_warn_with_string_context(self, log_primitive, mock_logger):
        """Should handle string values in context."""
        log_primitive.warn("Invalid input", {"field": "email", "value": "invalid"})

        call_args = mock_logger.warning.call_args[0][0]
        assert "Invalid input" in call_args
        assert "email" in call_args


class TestLogError:
    """Tests for Log.error()"""

    def test_error_simple_message(self, log_primitive, mock_logger):
        """Should log error message."""
        log_primitive.error("Error message")
        mock_logger.error.assert_called_once_with("Error message")

    def test_error_message_with_context(self, log_primitive, mock_logger):
        """Should log error message with context dict."""
        log_primitive.error("Operation failed", {"error": "Connection timeout", "code": 500})

        call_args = mock_logger.error.call_args[0][0]
        assert "Operation failed" in call_args
        assert "Context:" in call_args
        assert "error" in call_args
        assert "Connection timeout" in call_args

    def test_error_with_exception_context(self, log_primitive, mock_logger):
        """Should handle exception information in context."""
        log_primitive.error("Database error", {
            "exception": "SQLError",
            "message": "Connection lost",
            "query": "SELECT * FROM users"
        })

        call_args = mock_logger.error.call_args[0][0]
        assert "Database error" in call_args
        assert "SQLError" in call_args

    def test_error_with_complex_context(self, log_primitive, mock_logger):
        """Should handle complex nested context."""
        context = {
            "error": {
                "type": "ValidationError",
                "fields": ["email", "password"],
                "details": {"email": "Invalid format"}
            },
            "request_id": "req-123"
        }
        log_primitive.error("Validation failed", context)

        call_args = mock_logger.error.call_args[0][0]
        assert "Validation failed" in call_args
        assert "ValidationError" in call_args


class TestLogFormatMessage:
    """Tests for _format_message() helper"""

    def test_format_message_without_context(self, log_primitive):
        """Should return message unchanged without context."""
        result = log_primitive._format_message("Test message")
        assert result == "Test message"

    def test_format_message_with_context(self, log_primitive):
        """Should format message with JSON context."""
        context = {"key": "value", "number": 42}
        result = log_primitive._format_message("Test", context)

        assert "Test" in result
        assert "Context:" in result
        assert "key" in result
        assert "value" in result

    def test_format_message_with_empty_context(self, log_primitive):
        """Should handle empty context dict."""
        result = log_primitive._format_message("Test", {})

        assert "Test" in result
        # Empty dict is still truthy, so Context: is added
        # But in actual implementation, empty context doesn't add prefix
        assert result == "Test"


class TestLogLuaConversion:
    """Tests for _lua_to_python() helper"""

    def test_lua_to_python_with_dict(self, log_primitive):
        """Should convert dict-like objects."""
        # Simulate a dict with items() method
        lua_table = {"key": "value", "num": 123}
        result = log_primitive._lua_to_python(lua_table)

        assert result == {"key": "value", "num": 123}

    def test_lua_to_python_with_nested_dict(self, log_primitive):
        """Should recursively convert nested structures."""
        lua_table = {
            "user": {"name": "Alice", "age": 30},
            "settings": {"theme": "dark"}
        }
        result = log_primitive._lua_to_python(lua_table)

        assert result["user"]["name"] == "Alice"
        assert result["settings"]["theme"] == "dark"

    def test_lua_to_python_with_list(self, log_primitive):
        """Should convert list-like objects."""
        lua_array = [1, 2, 3, 4, 5]
        result = log_primitive._lua_to_python(lua_array)

        assert result == [1, 2, 3, 4, 5]

    def test_lua_to_python_with_primitives(self, log_primitive):
        """Should return primitives unchanged."""
        assert log_primitive._lua_to_python("string") == "string"
        assert log_primitive._lua_to_python(123) == 123
        assert log_primitive._lua_to_python(45.67) == 45.67
        assert log_primitive._lua_to_python(True) is True
        assert log_primitive._lua_to_python(None) is None


class TestLogIntegration:
    """Integration tests combining multiple operations."""

    def test_all_log_levels(self, log_primitive, mock_logger):
        """Should support all log levels."""
        log_primitive.debug("Debug msg")
        log_primitive.info("Info msg")
        log_primitive.warn("Warn msg")
        log_primitive.error("Error msg")

        assert mock_logger.debug.call_count == 1
        assert mock_logger.info.call_count == 1
        assert mock_logger.warning.call_count == 1
        assert mock_logger.error.call_count == 1

    def test_workflow_logging_pattern(self, log_primitive, mock_logger):
        """Test typical workflow logging pattern."""
        # Start phase
        log_primitive.info("Starting processing phase")

        # Processing with debug
        log_primitive.debug("Processing item", {"index": 1})
        log_primitive.debug("Processing item", {"index": 2})

        # Warning for unusual condition
        log_primitive.warn("Slow response", {"duration": 5.2})

        # Complete phase
        log_primitive.info("Phase complete", {"items": 2})

        assert mock_logger.debug.call_count == 2
        assert mock_logger.info.call_count == 2
        assert mock_logger.warning.call_count == 1

    def test_error_handling_pattern(self, log_primitive, mock_logger):
        """Test error logging pattern."""
        try:
            # Simulate error
            raise ValueError("Test error")
        except ValueError as e:
            log_primitive.error("Operation failed", {
                "error": str(e),
                "type": type(e).__name__
            })

        call_args = mock_logger.error.call_args[0][0]
        assert "Operation failed" in call_args
        assert "Test error" in call_args

    def test_progressive_detail_logging(self, log_primitive, mock_logger):
        """Test logging with increasing detail levels."""
        # High-level info
        log_primitive.info("Starting analysis")

        # Mid-level debug
        log_primitive.debug("Loading data", {"source": "database"})

        # Detailed debug
        log_primitive.debug("Query executed", {
            "query": "SELECT * FROM users",
            "rows": 100,
            "duration_ms": 45
        })

        # Result info
        log_primitive.info("Analysis complete", {"results": 100})

        assert mock_logger.info.call_count == 2
        assert mock_logger.debug.call_count == 2


class TestLogEdgeCases:
    """Edge case and error condition tests."""

    def test_very_long_message(self, log_primitive, mock_logger):
        """Should handle very long messages."""
        long_message = "x" * 10000
        log_primitive.info(long_message)

        call_args = mock_logger.info.call_args[0][0]
        assert len(call_args) >= 10000

    def test_unicode_message(self, log_primitive, mock_logger):
        """Should handle unicode characters."""
        log_primitive.info("用户登录成功")
        mock_logger.info.assert_called_once()

    def test_unicode_in_context(self, log_primitive, mock_logger):
        """Should handle unicode in context."""
        log_primitive.info("User action", {"name": "张三", "action": "登录"})

        call_args = mock_logger.info.call_args[0][0]
        # JSON may encode unicode as escape sequences
        assert "User action" in call_args
        assert "name" in call_args

    def test_special_characters_in_message(self, log_primitive, mock_logger):
        """Should handle special characters."""
        log_primitive.info("Test: <>&\"'\\n\\t")
        mock_logger.info.assert_called_once()

    def test_large_context_dict(self, log_primitive, mock_logger):
        """Should handle large context dicts."""
        large_context = {f"key_{i}": f"value_{i}" for i in range(100)}
        log_primitive.debug("Large context", large_context)

        call_args = mock_logger.debug.call_args[0][0]
        assert "Large context" in call_args
        assert "key_0" in call_args
        assert "key_99" in call_args

    def test_deeply_nested_context(self, log_primitive, mock_logger):
        """Should handle deeply nested context."""
        nested = {"level1": {"level2": {"level3": {"level4": "deep"}}}}
        log_primitive.info("Nested data", nested)

        call_args = mock_logger.info.call_args[0][0]
        assert "Nested data" in call_args
        assert "deep" in call_args

    def test_empty_string_message(self, log_primitive, mock_logger):
        """Should handle empty string message."""
        log_primitive.info("")
        mock_logger.info.assert_called_once_with("")

    def test_context_with_circular_reference_safe(self, log_primitive, mock_logger):
        """Should handle simple circular-like structures safely."""
        # Note: True circular refs would cause JSON encoding to fail
        # Test that regular nested structures work
        context = {"a": {"b": {"c": "value"}}}
        log_primitive.info("Nested", context)
        mock_logger.info.assert_called_once()


class TestLogProcedureId:
    """Tests for procedure_id tracking"""

    def test_logger_name_includes_procedure_id(self):
        """Should create logger with procedure ID in name."""
        log_prim = LogPrimitive(procedure_id="proc-123")
        assert log_prim.logger.name == "procedure.proc-123"

    def test_procedure_id_in_repr(self):
        """Should include procedure_id in repr."""
        log_prim = LogPrimitive(procedure_id="test-proc")
        assert "test-proc" in repr(log_prim)

    def test_different_procedure_ids(self):
        """Should create separate loggers for different procedure IDs."""
        log1 = LogPrimitive(procedure_id="proc-1")
        log2 = LogPrimitive(procedure_id="proc-2")

        assert log1.logger.name != log2.logger.name
        assert "proc-1" in log1.logger.name
        assert "proc-2" in log2.logger.name


class TestLogRepr:
    """Tests for __repr__()"""

    def test_repr_format(self, log_primitive):
        """Should show procedure_id in repr."""
        assert repr(log_primitive) == "LogPrimitive(procedure_id=test_procedure_123)"

    def test_repr_with_different_id(self):
        """Should reflect different procedure IDs."""
        log1 = LogPrimitive(procedure_id="abc")
        log2 = LogPrimitive(procedure_id="xyz")

        assert repr(log1) == "LogPrimitive(procedure_id=abc)"
        assert repr(log2) == "LogPrimitive(procedure_id=xyz)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
