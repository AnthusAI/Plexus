"""
Tests for Control Primitives - Flow control and termination.

Tests all Control primitive methods:
- Stop.requested()
- Stop.reason()
- Stop.success()
- Iterations.current()
- Iterations.exceeded(max)
- Tool.called(name)
- Tool.last_result(name)
- Tool.last_call(name)
"""

import pytest
from plexus.cli.procedure.lua_dsl.primitives.control import (
    StopPrimitive,
    IterationsPrimitive
)
from plexus.cli.procedure.lua_dsl.primitives.tool import (
    ToolPrimitive,
    ToolCall
)


# ===== Stop Primitive Tests =====

@pytest.fixture
def stop():
    """Create a fresh Stop primitive for each test."""
    return StopPrimitive()


class TestStopRequested:
    """Tests for Stop.requested()"""

    def test_requested_returns_false_initially(self, stop):
        """Should return False when not stopped."""
        assert stop.requested() is False

    def test_requested_returns_true_after_request(self, stop):
        """Should return True after stop is requested."""
        stop.request("Test reason")
        assert stop.requested() is True

    def test_requested_persists_across_calls(self, stop):
        """Should remain True on repeated calls."""
        stop.request("Test reason")
        assert stop.requested() is True
        assert stop.requested() is True
        assert stop.requested() is True


class TestStopReason:
    """Tests for Stop.reason()"""

    def test_reason_returns_none_initially(self, stop):
        """Should return None when not stopped."""
        assert stop.reason() is None

    def test_reason_returns_provided_reason(self, stop):
        """Should return the reason provided."""
        stop.request("Out of time")
        assert stop.reason() == "Out of time"

    def test_reason_with_different_reasons(self, stop):
        """Should handle various reason strings."""
        reasons = [
            "Max iterations exceeded",
            "User requested",
            "Error encountered",
            ""  # Empty string
        ]

        for reason in reasons:
            stop.reset()
            stop.request(reason)
            assert stop.reason() == reason


class TestStopSuccess:
    """Tests for Stop.success()"""

    def test_success_returns_true_initially(self, stop):
        """Should return True by default."""
        assert stop.success() is True

    def test_success_returns_true_for_successful_stop(self, stop):
        """Should return True for successful completion."""
        stop.request("Completed successfully", success=True)
        assert stop.success() is True

    def test_success_returns_false_for_error_stop(self, stop):
        """Should return False for error-based stop."""
        stop.request("Error occurred", success=False)
        assert stop.success() is False

    def test_success_without_stop_request(self, stop):
        """Should return True even when not stopped."""
        assert stop.requested() is False
        assert stop.success() is True


class TestStopIntegration:
    """Integration tests for Stop primitive."""

    def test_typical_successful_stop(self, stop):
        """Test typical successful stop pattern."""
        # Stop with success
        stop.request("Task completed", success=True)

        # Check all attributes
        assert stop.requested() is True
        assert stop.success() is True
        assert stop.reason() == "Task completed"

    def test_typical_error_stop(self, stop):
        """Test typical error stop pattern."""
        # Stop with error
        stop.request("Critical error", success=False)

        # Check all attributes
        assert stop.requested() is True
        assert stop.success() is False
        assert stop.reason() == "Critical error"

    def test_reset_clears_all_state(self, stop):
        """Test that reset clears all stop state."""
        stop.request("Test reason", success=False)

        stop.reset()

        assert stop.requested() is False
        assert stop.reason() is None
        assert stop.success() is True


class TestStopRepr:
    """Tests for Stop.__repr__()"""

    def test_repr_not_requested(self, stop):
        """Should show not requested."""
        assert repr(stop) == "StopPrimitive(requested=False, success=True)"

    def test_repr_requested_success(self, stop):
        """Should show requested with success."""
        stop.request("Done", success=True)
        assert repr(stop) == "StopPrimitive(requested=True, success=True)"

    def test_repr_requested_failure(self, stop):
        """Should show requested with failure."""
        stop.request("Error", success=False)
        assert repr(stop) == "StopPrimitive(requested=True, success=False)"


# ===== Iterations Primitive Tests =====

@pytest.fixture
def iterations():
    """Create a fresh Iterations primitive for each test."""
    return IterationsPrimitive()


class TestIterationsCurrent:
    """Tests for Iterations.current()"""

    def test_current_returns_zero_initially(self, iterations):
        """Should return 0 initially."""
        assert iterations.current() == 0

    def test_current_returns_incremented_value(self, iterations):
        """Should return current iteration after increments."""
        iterations.increment()
        assert iterations.current() == 1

        iterations.increment()
        assert iterations.current() == 2

        iterations.increment()
        assert iterations.current() == 3

    def test_current_after_many_increments(self, iterations):
        """Should track many iterations."""
        for i in range(100):
            iterations.increment()

        assert iterations.current() == 100


class TestIterationsExceeded:
    """Tests for Iterations.exceeded()"""

    def test_exceeded_returns_false_when_under_limit(self, iterations):
        """Should return False when under limit."""
        assert iterations.exceeded(10) is False
        iterations.increment()
        assert iterations.exceeded(10) is False

    def test_exceeded_returns_true_when_at_limit(self, iterations):
        """Should return True when at limit."""
        for _ in range(10):
            iterations.increment()

        assert iterations.exceeded(10) is True

    def test_exceeded_returns_true_when_over_limit(self, iterations):
        """Should return True when over limit."""
        for _ in range(15):
            iterations.increment()

        assert iterations.exceeded(10) is True

    def test_exceeded_with_zero_limit(self, iterations):
        """Should return True immediately with zero limit."""
        assert iterations.exceeded(0) is True
        iterations.increment()
        assert iterations.exceeded(0) is True

    def test_exceeded_with_negative_limit(self, iterations):
        """Should return True with negative limit."""
        assert iterations.exceeded(-1) is True

    def test_exceeded_boundary_cases(self, iterations):
        """Should handle boundary cases correctly."""
        # At iteration 0
        assert iterations.exceeded(1) is False

        # At iteration 1 (reached limit of 1)
        iterations.increment()
        assert iterations.exceeded(1) is True

        # At iteration 2 (exceeded limit of 1)
        iterations.increment()
        assert iterations.exceeded(1) is True


class TestIterationsIntegration:
    """Integration tests for Iterations primitive."""

    def test_typical_iteration_control_flow(self, iterations):
        """Test typical iteration control pattern."""
        max_iterations = 5

        for i in range(10):  # Try 10 iterations
            if iterations.exceeded(max_iterations):
                break

            # Do work
            iterations.increment()

        # Should have stopped at max
        assert iterations.current() == max_iterations

    def test_reset_clears_counter(self, iterations):
        """Test that reset clears iteration count."""
        for _ in range(50):
            iterations.increment()

        assert iterations.current() == 50

        iterations.reset()
        assert iterations.current() == 0


class TestIterationsRepr:
    """Tests for Iterations.__repr__()"""

    def test_repr_at_zero(self, iterations):
        """Should show current iteration."""
        assert repr(iterations) == "IterationsPrimitive(current=0)"

    def test_repr_after_increments(self, iterations):
        """Should update with current count."""
        iterations.increment()
        iterations.increment()
        iterations.increment()
        assert repr(iterations) == "IterationsPrimitive(current=3)"


# ===== Tool Primitive Tests =====

@pytest.fixture
def tool():
    """Create a fresh Tool primitive for each test."""
    return ToolPrimitive()


class TestToolCalled:
    """Tests for Tool.called()"""

    def test_called_returns_false_initially(self, tool):
        """Should return False for never-called tool."""
        assert tool.called("search") is False
        assert tool.called("done") is False

    def test_called_returns_true_after_recording(self, tool):
        """Should return True after tool is recorded."""
        tool.record_call("search", {"query": "test"}, ["result1", "result2"])
        assert tool.called("search") is True

    def test_called_returns_false_for_other_tools(self, tool):
        """Should only return True for recorded tools."""
        tool.record_call("search", {}, "result")
        assert tool.called("search") is True
        assert tool.called("done") is False
        assert tool.called("other") is False

    def test_called_with_multiple_tools(self, tool):
        """Should track multiple different tools."""
        tool.record_call("search", {}, "result1")
        tool.record_call("done", {}, None)
        tool.record_call("process", {}, "result2")

        assert tool.called("search") is True
        assert tool.called("done") is True
        assert tool.called("process") is True
        assert tool.called("unknown") is False


class TestToolLastResult:
    """Tests for Tool.last_result()"""

    def test_last_result_returns_none_when_never_called(self, tool):
        """Should return None for never-called tool."""
        assert tool.last_result("search") is None

    def test_last_result_returns_recorded_result(self, tool):
        """Should return the result that was recorded."""
        tool.record_call("search", {}, ["result1", "result2"])
        assert tool.last_result("search") == ["result1", "result2"]

    def test_last_result_with_various_types(self, tool):
        """Should handle various result types."""
        tool.record_call("tool1", {}, "string result")
        tool.record_call("tool2", {}, 42)
        tool.record_call("tool3", {}, {"key": "value"})
        tool.record_call("tool4", {}, None)
        tool.record_call("tool5", {}, [1, 2, 3])

        assert tool.last_result("tool1") == "string result"
        assert tool.last_result("tool2") == 42
        assert tool.last_result("tool3") == {"key": "value"}
        assert tool.last_result("tool4") is None
        assert tool.last_result("tool5") == [1, 2, 3]

    def test_last_result_updates_on_multiple_calls(self, tool):
        """Should return only the last result."""
        tool.record_call("search", {}, "first result")
        assert tool.last_result("search") == "first result"

        tool.record_call("search", {}, "second result")
        assert tool.last_result("search") == "second result"

        tool.record_call("search", {}, "third result")
        assert tool.last_result("search") == "third result"


class TestToolLastCall:
    """Tests for Tool.last_call()"""

    def test_last_call_returns_none_when_never_called(self, tool):
        """Should return None for never-called tool."""
        assert tool.last_call("search") is None

    def test_last_call_returns_full_info(self, tool):
        """Should return dict with name, args, and result."""
        tool.record_call("search", {"query": "test"}, ["result1"])

        call = tool.last_call("search")
        assert call is not None
        assert call['name'] == "search"
        assert call['args'] == {"query": "test"}
        assert call['result'] == ["result1"]

    def test_last_call_with_complex_args(self, tool):
        """Should handle complex argument structures."""
        complex_args = {
            "query": "test",
            "filters": ["filter1", "filter2"],
            "options": {"limit": 10, "offset": 0}
        }

        tool.record_call("search", complex_args, "result")

        call = tool.last_call("search")
        assert call['args'] == complex_args

    def test_last_call_updates_on_multiple_calls(self, tool):
        """Should return only the last call info."""
        tool.record_call("search", {"query": "first"}, "result1")
        tool.record_call("search", {"query": "second"}, "result2")

        call = tool.last_call("search")
        assert call['args']['query'] == "second"
        assert call['result'] == "result2"


class TestToolIntegration:
    """Integration tests for Tool primitive."""

    def test_typical_tool_usage_pattern(self, tool):
        """Test typical tool tracking workflow."""
        # Record some tool calls
        tool.record_call("search", {"query": "python"}, ["doc1", "doc2"])
        tool.record_call("done", {}, None)

        # Check what was called
        assert tool.called("search") is True
        assert tool.called("done") is True

        # Get results
        search_result = tool.last_result("search")
        assert len(search_result) == 2

        # Get full call info
        search_call = tool.last_call("search")
        assert search_call['args']['query'] == "python"

    def test_multiple_calls_to_same_tool(self, tool):
        """Test tracking multiple calls to same tool."""
        # Call search multiple times
        tool.record_call("search", {"query": "first"}, "result1")
        tool.record_call("search", {"query": "second"}, "result2")
        tool.record_call("search", {"query": "third"}, "result3")

        # Should track only last
        assert tool.called("search") is True
        assert tool.last_result("search") == "result3"

        # But get_call_count should show all
        assert tool.get_call_count("search") == 3

    def test_get_all_calls(self, tool):
        """Test retrieving all tool calls."""
        tool.record_call("tool1", {}, "result1")
        tool.record_call("tool2", {}, "result2")
        tool.record_call("tool1", {}, "result3")

        all_calls = tool.get_all_calls()
        assert len(all_calls) == 3
        assert all_calls[0].name == "tool1"
        assert all_calls[1].name == "tool2"
        assert all_calls[2].name == "tool1"

    def test_get_call_count_per_tool(self, tool):
        """Test counting calls per tool."""
        tool.record_call("search", {}, "r1")
        tool.record_call("process", {}, "r2")
        tool.record_call("search", {}, "r3")
        tool.record_call("search", {}, "r4")

        assert tool.get_call_count("search") == 3
        assert tool.get_call_count("process") == 1
        assert tool.get_call_count("unknown") == 0
        assert tool.get_call_count() == 4  # Total

    def test_reset_clears_all_tracking(self, tool):
        """Test that reset clears all tool tracking."""
        tool.record_call("tool1", {}, "result1")
        tool.record_call("tool2", {}, "result2")

        tool.reset()

        assert tool.called("tool1") is False
        assert tool.called("tool2") is False
        assert tool.last_result("tool1") is None
        assert tool.get_call_count() == 0


class TestToolCallClass:
    """Tests for ToolCall helper class."""

    def test_tool_call_creation(self):
        """Should create ToolCall with all fields."""
        call = ToolCall("search", {"query": "test"}, "result")
        assert call.name == "search"
        assert call.args == {"query": "test"}
        assert call.result == "result"

    def test_tool_call_to_dict(self):
        """Should convert to dictionary."""
        call = ToolCall("search", {"query": "test"}, ["r1", "r2"])
        d = call.to_dict()

        assert d == {
            'name': "search",
            'args': {"query": "test"},
            'result': ["r1", "r2"]
        }

    def test_tool_call_repr(self):
        """Should have useful string representation."""
        call = ToolCall("search", {"query": "test"}, "result")
        assert repr(call) == "ToolCall(search, args={'query': 'test'})"


class TestToolRepr:
    """Tests for Tool.__repr__()"""

    def test_repr_no_calls(self, tool):
        """Should show 0 calls initially."""
        assert repr(tool) == "ToolPrimitive(0 calls)"

    def test_repr_with_calls(self, tool):
        """Should show call count."""
        tool.record_call("tool1", {}, "result")
        tool.record_call("tool2", {}, "result")
        tool.record_call("tool1", {}, "result")

        assert repr(tool) == "ToolPrimitive(3 calls)"


# ===== Edge Cases and Error Conditions =====

class TestControlPrimitivesEdgeCases:
    """Edge cases across all control primitives."""

    def test_stop_with_empty_reason(self):
        """Should handle empty reason string."""
        stop = StopPrimitive()
        stop.request("", success=True)
        assert stop.requested() is True
        assert stop.reason() == ""

    def test_stop_with_very_long_reason(self):
        """Should handle very long reason strings."""
        stop = StopPrimitive()
        long_reason = "x" * 10000
        stop.request(long_reason, success=False)
        assert stop.reason() == long_reason

    def test_iterations_with_very_high_counts(self):
        """Should handle high iteration counts."""
        iterations = IterationsPrimitive()
        for _ in range(10000):
            iterations.increment()

        assert iterations.current() == 10000
        assert iterations.exceeded(5000) is True

    def test_tool_with_empty_tool_name(self):
        """Should handle empty tool name."""
        tool = ToolPrimitive()
        tool.record_call("", {}, "result")
        assert tool.called("") is True
        assert tool.last_result("") == "result"

    def test_tool_with_special_character_names(self):
        """Should handle tool names with special characters."""
        tool = ToolPrimitive()
        names = ["tool-1", "tool_2", "tool.3", "tool:4", "tool/5"]

        for name in names:
            tool.record_call(name, {}, f"result_{name}")

        for name in names:
            assert tool.called(name) is True
            assert tool.last_result(name) == f"result_{name}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
