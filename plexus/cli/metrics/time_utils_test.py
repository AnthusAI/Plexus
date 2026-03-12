"""
Tests for time parsing utilities.

These tests verify:
1. parse_flexible_time() with various formats
2. get_time_range_from_args() with different combinations
3. Edge cases and error handling
"""

import pytest
from datetime import datetime, timezone, timedelta
from .time_utils import (
    parse_flexible_time,
    get_time_range_from_args,
    format_time_range,
    get_calendar_hour_range
)


def test_parse_flexible_time_relative():
    """Test parsing relative time strings"""
    now = datetime.now(timezone.utc)
    
    # "2 hours ago"
    result = parse_flexible_time("2 hours ago")
    expected = now - timedelta(hours=2)
    assert abs((result - expected).total_seconds()) < 60  # Within 1 minute
    
    # "yesterday"
    result = parse_flexible_time("yesterday")
    expected = now - timedelta(days=1)
    assert abs((result - expected).total_seconds()) < 86400  # Within 1 day


def test_parse_flexible_time_absolute():
    """Test parsing absolute date strings"""
    # ISO format
    result = parse_flexible_time("2024-11-19")
    assert result.year == 2024
    assert result.month == 11
    assert result.day == 19
    
    # With time
    result = parse_flexible_time("2024-11-19 14:00")
    assert result.year == 2024
    assert result.month == 11
    assert result.day == 19
    assert result.hour == 14
    assert result.minute == 0


def test_parse_flexible_time_natural():
    """Test parsing natural language time strings"""
    # "November 19 2024"
    result = parse_flexible_time("November 19 2024")
    assert result.year == 2024
    assert result.month == 11
    assert result.day == 19
    
    # "Nov 19 2pm"
    result = parse_flexible_time("Nov 19 2024 2pm")
    assert result.year == 2024
    assert result.month == 11
    assert result.day == 19
    assert result.hour == 14


def test_parse_flexible_time_timezone():
    """Test that parsed times have UTC timezone"""
    result = parse_flexible_time("2024-11-19 14:00")
    assert result.tzinfo is not None
    assert result.tzinfo == timezone.utc


def test_parse_flexible_time_empty_string():
    """Test that empty string raises ValueError"""
    with pytest.raises(ValueError, match="Time string cannot be empty"):
        parse_flexible_time("")


def test_parse_flexible_time_invalid():
    """Test that invalid string raises ValueError"""
    with pytest.raises(ValueError, match="Could not parse"):
        parse_flexible_time("not a valid time string xyz123")


def test_get_time_range_from_args_hours():
    """Test time range with hours parameter"""
    now = datetime.now(timezone.utc)
    
    start, end = get_time_range_from_args(hours=2)
    
    # End should be close to now
    assert abs((end - now).total_seconds()) < 60
    
    # Start should be 2 hours before end
    assert abs((end - start).total_seconds() - 7200) < 60


def test_get_time_range_from_args_start_and_end():
    """Test time range with start and end parameters"""
    start, end = get_time_range_from_args(
        start="2024-11-19 10:00",
        end="2024-11-19 12:00"
    )
    
    assert start.year == 2024
    assert start.month == 11
    assert start.day == 19
    assert start.hour == 10
    
    assert end.year == 2024
    assert end.month == 11
    assert end.day == 19
    assert end.hour == 12


def test_get_time_range_from_args_only_start():
    """Test time range with only start parameter"""
    now = datetime.now(timezone.utc)
    
    start, end = get_time_range_from_args(start="2024-11-19 10:00")
    
    assert start.year == 2024
    assert start.month == 11
    assert start.day == 19
    assert start.hour == 10
    
    # End should be close to now
    assert abs((end - now).total_seconds()) < 60


def test_get_time_range_from_args_default():
    """Test default time range (current and previous calendar hour)"""
    now = datetime.now(timezone.utc)
    current_hour_start = now.replace(minute=0, second=0, microsecond=0)
    previous_hour_start = current_hour_start - timedelta(hours=1)
    next_hour_start = current_hour_start + timedelta(hours=1)
    
    start, end = get_time_range_from_args()
    
    assert start == previous_hour_start
    assert end == next_hour_start


def test_get_time_range_from_args_end_before_start():
    """Test that end before start raises ValueError"""
    with pytest.raises(ValueError, match="End time .* must be after start time"):
        get_time_range_from_args(
            start="2024-11-19 12:00",
            end="2024-11-19 10:00"
        )


def test_get_time_range_from_args_negative_hours():
    """Test that negative hours raises ValueError"""
    with pytest.raises(ValueError, match="Hours must be a positive number"):
        get_time_range_from_args(hours=-1)


def test_get_time_range_from_args_zero_hours():
    """Test that zero hours raises ValueError"""
    with pytest.raises(ValueError, match="Hours must be a positive number"):
        get_time_range_from_args(hours=0)


def test_format_time_range_same_day():
    """Test formatting time range on same day"""
    start = datetime(2024, 11, 19, 13, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 11, 19, 15, 0, 0, tzinfo=timezone.utc)
    
    result = format_time_range(start, end)
    
    assert "2024-11-19 13:00" in result
    assert "15:00" in result
    assert "2.0 hours" in result


def test_format_time_range_different_days():
    """Test formatting time range across different days"""
    start = datetime(2024, 11, 19, 23, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 11, 20, 1, 0, 0, tzinfo=timezone.utc)
    
    result = format_time_range(start, end)
    
    assert "2024-11-19 23:00" in result
    assert "2024-11-20 01:00" in result
    assert "2.0 hours" in result


def test_get_calendar_hour_range_default():
    """Test getting calendar hour range with default (now)"""
    now = datetime.now(timezone.utc)
    current_hour_start = now.replace(minute=0, second=0, microsecond=0)
    previous_hour_start = current_hour_start - timedelta(hours=1)
    next_hour_start = current_hour_start + timedelta(hours=1)
    
    start, end = get_calendar_hour_range()
    
    assert start == previous_hour_start
    assert end == next_hour_start


def test_get_calendar_hour_range_with_reference():
    """Test getting calendar hour range with specific reference time"""
    ref = datetime(2024, 11, 19, 14, 30, 0, tzinfo=timezone.utc)
    
    start, end = get_calendar_hour_range(ref)
    
    # Should return 13:00 to 15:00
    assert start == datetime(2024, 11, 19, 13, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2024, 11, 19, 15, 0, 0, tzinfo=timezone.utc)


def test_get_calendar_hour_range_at_hour_boundary():
    """Test calendar hour range exactly at hour boundary"""
    ref = datetime(2024, 11, 19, 14, 0, 0, tzinfo=timezone.utc)
    
    start, end = get_calendar_hour_range(ref)
    
    # Should return 13:00 to 15:00
    assert start == datetime(2024, 11, 19, 13, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2024, 11, 19, 15, 0, 0, tzinfo=timezone.utc)
