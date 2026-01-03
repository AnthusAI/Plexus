"""
Tests for Retry Primitive - Error handling with exponential backoff.

Tests all Retry primitive methods:
- Retry.with_backoff(fn, options) - Retry function with exponential backoff
"""

import pytest
import time
from unittest.mock import Mock, patch
from plexus.cli.procedure.lua_dsl.primitives.retry import RetryPrimitive


@pytest.fixture
def retry():
    """Create a fresh Retry primitive for each test."""
    return RetryPrimitive()


class TestRetrySuccess:
    """Tests for successful retry scenarios."""

    def test_success_on_first_attempt(self, retry):
        """Should return result on first successful attempt."""
        mock_fn = Mock(return_value="success")

        result = retry.with_backoff(mock_fn)

        assert result == "success"
        assert mock_fn.call_count == 1

    def test_success_on_second_attempt(self, retry):
        """Should retry once and succeed."""
        mock_fn = Mock(side_effect=[Exception("fail"), "success"])

        with patch('time.sleep'):  # Mock sleep to speed up test
            result = retry.with_backoff(mock_fn, {"max_attempts": 3})

        assert result == "success"
        assert mock_fn.call_count == 2

    def test_success_on_final_attempt(self, retry):
        """Should succeed on the last allowed attempt."""
        mock_fn = Mock(side_effect=[
            Exception("fail 1"),
            Exception("fail 2"),
            "success"
        ])

        with patch('time.sleep'):
            result = retry.with_backoff(mock_fn, {"max_attempts": 3})

        assert result == "success"
        assert mock_fn.call_count == 3

    def test_returns_function_result(self, retry):
        """Should return whatever the function returns."""
        mock_fn = Mock(return_value={"data": [1, 2, 3], "count": 3})

        result = retry.with_backoff(mock_fn)

        assert result == {"data": [1, 2, 3], "count": 3}


class TestRetryFailure:
    """Tests for retry failure scenarios."""

    def test_all_attempts_fail(self, retry):
        """Should raise exception after all attempts fail."""
        mock_fn = Mock(side_effect=Exception("always fails"))

        with patch('time.sleep'):
            with pytest.raises(Exception, match="Retry failed after 3 attempts"):
                retry.with_backoff(mock_fn, {"max_attempts": 3})

        assert mock_fn.call_count == 3

    def test_preserves_original_error(self, retry):
        """Should include original error in final exception."""
        mock_fn = Mock(side_effect=ValueError("original error"))

        with patch('time.sleep'):
            with pytest.raises(Exception, match="original error"):
                retry.with_backoff(mock_fn, {"max_attempts": 2})

    def test_exhausts_max_attempts(self, retry):
        """Should respect max_attempts setting."""
        mock_fn = Mock(side_effect=Exception("fail"))

        with patch('time.sleep'):
            with pytest.raises(Exception):
                retry.with_backoff(mock_fn, {"max_attempts": 5})

        assert mock_fn.call_count == 5

    def test_single_attempt_fails(self, retry):
        """Should fail immediately with max_attempts=1."""
        mock_fn = Mock(side_effect=Exception("fail"))

        with pytest.raises(Exception, match="Retry failed after 1 attempts"):
            retry.with_backoff(mock_fn, {"max_attempts": 1})

        assert mock_fn.call_count == 1


class TestRetryBackoff:
    """Tests for exponential backoff behavior."""

    def test_default_backoff_delays(self, retry):
        """Should use default backoff delays."""
        mock_fn = Mock(side_effect=[Exception("1"), Exception("2"), "success"])

        with patch('time.sleep') as mock_sleep:
            retry.with_backoff(mock_fn)

        # Check sleep was called with increasing delays
        assert mock_sleep.call_count == 2
        # Default: 1, 2 (factor of 2)
        assert mock_sleep.call_args_list[0][0][0] == 1.0
        assert mock_sleep.call_args_list[1][0][0] == 2.0

    def test_custom_initial_delay(self, retry):
        """Should use custom initial delay."""
        mock_fn = Mock(side_effect=[Exception("1"), "success"])

        with patch('time.sleep') as mock_sleep:
            retry.with_backoff(mock_fn, {"initial_delay": 5.0})

        mock_sleep.assert_called_once_with(5.0)

    def test_custom_backoff_factor(self, retry):
        """Should use custom backoff factor."""
        mock_fn = Mock(side_effect=[Exception("1"), Exception("2"), "success"])

        with patch('time.sleep') as mock_sleep:
            retry.with_backoff(mock_fn, {
                "initial_delay": 1.0,
                "backoff_factor": 3.0
            })

        # Should increase by factor of 3
        assert mock_sleep.call_args_list[0][0][0] == 1.0
        assert mock_sleep.call_args_list[1][0][0] == 3.0

    def test_max_delay_cap(self, retry):
        """Should cap delay at max_delay."""
        mock_fn = Mock(side_effect=[
            Exception("1"),
            Exception("2"),
            Exception("3"),
            Exception("4"),
            "success"
        ])

        with patch('time.sleep') as mock_sleep:
            retry.with_backoff(mock_fn, {
                "max_attempts": 5,
                "initial_delay": 10.0,
                "max_delay": 15.0,
                "backoff_factor": 2.0
            })

        # Delays: 10, 15 (capped from 20), 15 (capped from 30), 15 (capped from 45)
        assert mock_sleep.call_args_list[0][0][0] == 10.0
        assert mock_sleep.call_args_list[1][0][0] == 15.0  # 20 capped to 15
        assert mock_sleep.call_args_list[2][0][0] == 15.0  # 30 capped to 15
        assert mock_sleep.call_args_list[3][0][0] == 15.0  # 45 capped to 15

    def test_exponential_growth(self, retry):
        """Should grow delays exponentially."""
        mock_fn = Mock(side_effect=[
            Exception("1"),
            Exception("2"),
            Exception("3"),
            Exception("4"),
            "success"
        ])

        with patch('time.sleep') as mock_sleep:
            retry.with_backoff(mock_fn, {
                "initial_delay": 1.0,
                "backoff_factor": 2.0,
                "max_attempts": 5
            })

        # Delays: 1, 2, 4, 8
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0, 8.0]

    def test_no_sleep_on_success(self, retry):
        """Should not sleep if first attempt succeeds."""
        mock_fn = Mock(return_value="success")

        with patch('time.sleep') as mock_sleep:
            retry.with_backoff(mock_fn)

        mock_sleep.assert_not_called()

    def test_no_sleep_after_final_failure(self, retry):
        """Should not sleep after final failed attempt."""
        mock_fn = Mock(side_effect=Exception("fail"))

        with patch('time.sleep') as mock_sleep:
            with pytest.raises(Exception):
                retry.with_backoff(mock_fn, {"max_attempts": 3})

        # Should sleep only 2 times (after attempt 1 and 2, not after 3)
        assert mock_sleep.call_count == 2


class TestRetryOptions:
    """Tests for retry options handling."""

    def test_default_options(self, retry):
        """Should use default options when none provided."""
        mock_fn = Mock(side_effect=[Exception("1"), Exception("2"), "success"])

        with patch('time.sleep') as mock_sleep:
            retry.with_backoff(mock_fn)

        # Default max_attempts is 3
        assert mock_fn.call_count == 3

    def test_none_options(self, retry):
        """Should handle None options."""
        mock_fn = Mock(return_value="success")

        result = retry.with_backoff(mock_fn, None)

        assert result == "success"

    def test_empty_options(self, retry):
        """Should handle empty options dict."""
        mock_fn = Mock(return_value="success")

        result = retry.with_backoff(mock_fn, {})

        assert result == "success"

    def test_partial_options(self, retry):
        """Should use defaults for missing options."""
        mock_fn = Mock(side_effect=[Exception("1"), "success"])

        with patch('time.sleep') as mock_sleep:
            retry.with_backoff(mock_fn, {"max_attempts": 5})

        # Should still use default initial_delay
        mock_sleep.assert_called_once_with(1.0)

    def test_custom_max_attempts(self, retry):
        """Should respect custom max_attempts."""
        mock_fn = Mock(side_effect=Exception("fail"))

        with patch('time.sleep'):
            with pytest.raises(Exception):
                retry.with_backoff(mock_fn, {"max_attempts": 10})

        assert mock_fn.call_count == 10


class TestRetryCallback:
    """Tests for on_error callback."""

    def test_callback_called_on_error(self, retry):
        """Should call on_error callback when error occurs."""
        mock_fn = Mock(side_effect=[Exception("fail"), "success"])
        mock_callback = Mock()

        with patch('time.sleep'):
            retry.with_backoff(mock_fn, {"on_error": mock_callback})

        assert mock_callback.call_count == 1

    def test_callback_receives_error_info(self, retry):
        """Should pass error info to callback."""
        mock_fn = Mock(side_effect=[Exception("test error"), "success"])
        mock_callback = Mock()

        with patch('time.sleep'):
            retry.with_backoff(mock_fn, {"on_error": mock_callback})

        # Check callback was called with error info
        call_args = mock_callback.call_args[0][0]
        assert "attempt" in call_args
        assert "max_attempts" in call_args
        assert "error" in call_args
        assert "delay" in call_args
        assert "test error" in call_args["error"]

    def test_callback_called_multiple_times(self, retry):
        """Should call callback for each error."""
        mock_fn = Mock(side_effect=[
            Exception("fail 1"),
            Exception("fail 2"),
            "success"
        ])
        mock_callback = Mock()

        with patch('time.sleep'):
            retry.with_backoff(mock_fn, {
                "max_attempts": 3,
                "on_error": mock_callback
            })

        assert mock_callback.call_count == 2

    def test_callback_receives_attempt_number(self, retry):
        """Should receive correct attempt number."""
        mock_fn = Mock(side_effect=[
            Exception("fail 1"),
            Exception("fail 2"),
            "success"
        ])
        mock_callback = Mock()

        with patch('time.sleep'):
            retry.with_backoff(mock_fn, {"on_error": mock_callback})

        # Check attempt numbers
        first_call = mock_callback.call_args_list[0][0][0]
        second_call = mock_callback.call_args_list[1][0][0]

        assert first_call["attempt"] == 1
        assert second_call["attempt"] == 2

    def test_callback_error_ignored(self, retry):
        """Should continue retry if callback fails."""
        mock_fn = Mock(side_effect=[Exception("fail"), "success"])
        mock_callback = Mock(side_effect=Exception("callback error"))

        with patch('time.sleep'):
            result = retry.with_backoff(mock_fn, {"on_error": mock_callback})

        # Should still succeed despite callback error
        assert result == "success"

    def test_no_callback_on_success(self, retry):
        """Should not call callback if first attempt succeeds."""
        mock_fn = Mock(return_value="success")
        mock_callback = Mock()

        retry.with_backoff(mock_fn, {"on_error": mock_callback})

        mock_callback.assert_not_called()


class TestRetryIntegration:
    """Integration tests combining multiple scenarios."""

    def test_api_call_pattern(self, retry):
        """Test typical API retry pattern."""
        call_count = 0

        def api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Connection timeout")
            return {"status": "success", "data": [1, 2, 3]}

        with patch('time.sleep'):
            result = retry.with_backoff(api_call, {
                "max_attempts": 5,
                "initial_delay": 1.0,
                "backoff_factor": 2.0
            })

        assert result["status"] == "success"
        assert call_count == 3

    def test_database_retry_pattern(self, retry):
        """Test database connection retry pattern."""
        errors = []

        def on_error_handler(info):
            errors.append(info["error"])

        mock_db = Mock(side_effect=[
            Exception("Connection refused"),
            Exception("Timeout"),
            "connected"
        ])

        with patch('time.sleep'):
            result = retry.with_backoff(mock_db, {
                "max_attempts": 5,
                "initial_delay": 2.0,
                "on_error": on_error_handler
            })

        assert result == "connected"
        assert len(errors) == 2
        assert "Connection refused" in errors[0]

    def test_gradual_backoff_sequence(self, retry):
        """Test complete backoff sequence."""
        mock_fn = Mock(side_effect=[
            Exception("1"),
            Exception("2"),
            Exception("3"),
            Exception("4"),
            "success"
        ])

        with patch('time.sleep') as mock_sleep:
            retry.with_backoff(mock_fn, {
                "max_attempts": 5,
                "initial_delay": 0.5,
                "backoff_factor": 2.0
            })

        # Verify exponential backoff: 0.5, 1.0, 2.0, 4.0
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert delays == [0.5, 1.0, 2.0, 4.0]

    def test_max_delay_limiting(self, retry):
        """Test that max_delay properly limits growth."""
        mock_fn = Mock(side_effect=[
            Exception("1"),
            Exception("2"),
            Exception("3"),
            Exception("4"),
            Exception("5")
        ])

        with patch('time.sleep') as mock_sleep:
            with pytest.raises(Exception):
                retry.with_backoff(mock_fn, {
                    "max_attempts": 5,
                    "initial_delay": 5.0,
                    "backoff_factor": 3.0,
                    "max_delay": 20.0
                })

        delays = [call[0][0] for call in mock_sleep.call_args_list]
        # 5, 15, 20 (capped), 20 (capped)
        assert delays == [5.0, 15.0, 20.0, 20.0]


class TestRetryEdgeCases:
    """Edge case and error condition tests."""

    def test_zero_max_attempts_handled(self, retry):
        """Should handle edge case of zero max attempts."""
        mock_fn = Mock(side_effect=Exception("fail"))

        with pytest.raises(Exception):
            retry.with_backoff(mock_fn, {"max_attempts": 0})

        # Should not call function with 0 attempts
        assert mock_fn.call_count == 0

    def test_very_small_delay(self, retry):
        """Should handle very small delays."""
        mock_fn = Mock(side_effect=[Exception("fail"), "success"])

        with patch('time.sleep') as mock_sleep:
            retry.with_backoff(mock_fn, {"initial_delay": 0.001})

        mock_sleep.assert_called_once_with(0.001)

    def test_very_large_delay(self, retry):
        """Should handle very large delays."""
        mock_fn = Mock(side_effect=[Exception("fail"), "success"])

        with patch('time.sleep') as mock_sleep:
            retry.with_backoff(mock_fn, {
                "initial_delay": 1000.0,
                "max_delay": 10000.0
            })

        mock_sleep.assert_called_once_with(1000.0)

    def test_backoff_factor_one(self, retry):
        """Should handle backoff factor of 1 (no growth)."""
        mock_fn = Mock(side_effect=[Exception("1"), Exception("2"), "success"])

        with patch('time.sleep') as mock_sleep:
            retry.with_backoff(mock_fn, {
                "initial_delay": 2.0,
                "backoff_factor": 1.0
            })

        # All delays should be 2.0
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert delays == [2.0, 2.0]

    def test_different_exception_types(self, retry):
        """Should retry on different exception types."""
        mock_fn = Mock(side_effect=[
            ValueError("value error"),
            TypeError("type error"),
            RuntimeError("runtime error"),
            "success"
        ])

        with patch('time.sleep'):
            result = retry.with_backoff(mock_fn, {"max_attempts": 5})

        assert result == "success"
        assert mock_fn.call_count == 4

    def test_function_returns_none(self, retry):
        """Should handle function returning None."""
        mock_fn = Mock(return_value=None)

        result = retry.with_backoff(mock_fn)

        assert result is None

    def test_function_returns_false(self, retry):
        """Should handle function returning False."""
        mock_fn = Mock(return_value=False)

        result = retry.with_backoff(mock_fn)

        assert result is False


class TestRetryConvertLuaToPython:
    """Tests for _convert_lua_to_python() helper."""

    def test_convert_none(self, retry):
        """Should handle None input."""
        result = retry._convert_lua_to_python(None)
        assert result is None

    def test_convert_dict(self, retry):
        """Should convert dict-like structures."""
        lua_table = {"key": "value", "num": 123}
        result = retry._convert_lua_to_python(lua_table)

        assert result == {"key": "value", "num": 123}

    def test_convert_nested_dict(self, retry):
        """Should recursively convert nested dicts."""
        lua_table = {
            "outer": {
                "inner": {
                    "value": 42
                }
            }
        }
        result = retry._convert_lua_to_python(lua_table)

        assert result["outer"]["inner"]["value"] == 42

    def test_convert_primitives(self, retry):
        """Should return primitives unchanged."""
        assert retry._convert_lua_to_python("string") == "string"
        assert retry._convert_lua_to_python(123) == 123
        assert retry._convert_lua_to_python(45.67) == 45.67
        assert retry._convert_lua_to_python(True) is True


class TestRetryRepr:
    """Tests for __repr__()"""

    def test_repr_format(self, retry):
        """Should show RetryPrimitive in repr."""
        assert repr(retry) == "RetryPrimitive()"

    def test_repr_consistent(self, retry):
        """Should return consistent repr."""
        repr1 = repr(retry)
        repr2 = repr(retry)
        assert repr1 == repr2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
