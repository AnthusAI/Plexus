"""
Time parsing utilities for flexible date/time input handling.

This module provides flexible time parsing using the dateparser library,
allowing users to input times in various formats:
- Relative: "2 hours ago", "yesterday", "last week"
- Absolute: "2024-11-19", "2024-11-19 14:00"
- Natural: "1 AM February 3", "Nov 19 2pm"
"""

import dateparser
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple


def parse_flexible_time(time_str: str) -> datetime:
    """
    Parse a flexible time string into a datetime object.
    
    Supports a wide variety of formats:
    - Relative times: "2 hours ago", "yesterday", "last week"
    - Absolute dates: "2024-11-19", "November 19 2024"
    - Times with dates: "2024-11-19 14:00", "1 AM February 3"
    - Natural language: "tomorrow at 3pm", "next Monday"
    
    Args:
        time_str: The time string to parse
        
    Returns:
        datetime: Parsed datetime in UTC timezone
        
    Raises:
        ValueError: If the time string cannot be parsed
        
    Examples:
        >>> parse_flexible_time("2 hours ago")
        datetime.datetime(2024, 11, 19, 12, 0, 0, tzinfo=timezone.utc)
        
        >>> parse_flexible_time("2024-11-19 14:00")
        datetime.datetime(2024, 11, 19, 14, 0, 0, tzinfo=timezone.utc)
        
        >>> parse_flexible_time("yesterday")
        datetime.datetime(2024, 11, 18, 0, 0, 0, tzinfo=timezone.utc)
    """
    if not time_str:
        raise ValueError("Time string cannot be empty")
    
    # Use dateparser with settings for consistent UTC handling
    parsed = dateparser.parse(
        time_str,
        settings={
            'TIMEZONE': 'UTC',
            'RETURN_AS_TIMEZONE_AWARE': True,
            'PREFER_DATES_FROM': 'past'  # Assume past dates by default
        }
    )
    
    if parsed is None:
        raise ValueError(f"Could not parse time string: '{time_str}'")
    
    # Ensure UTC timezone
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    
    return parsed


def get_time_range_from_args(
    hours: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None
) -> Tuple[datetime, datetime]:
    """
    Get a time range from command-line arguments.
    
    Priority order:
    1. If hours is provided: return (now - hours, now)
    2. If start and end are provided: parse both and return
    3. If only start is provided: return (start, now)
    4. Default: return current and previous calendar hour
    
    Args:
        hours: Number of hours to go back from now
        start: Start time string (flexible format)
        end: End time string (flexible format)
        
    Returns:
        Tuple of (start_time, end_time) as datetime objects in UTC
        
    Raises:
        ValueError: If time strings cannot be parsed or if end < start
        
    Examples:
        >>> get_time_range_from_args(hours=2)
        (datetime(2024, 11, 19, 12, 0, 0), datetime(2024, 11, 19, 14, 0, 0))
        
        >>> get_time_range_from_args(start="yesterday", end="now")
        (datetime(2024, 11, 18, 0, 0, 0), datetime(2024, 11, 19, 14, 0, 0))
        
        >>> get_time_range_from_args()  # Default: current and previous hour
        (datetime(2024, 11, 19, 13, 0, 0), datetime(2024, 11, 19, 15, 0, 0))
    """
    now = datetime.now(timezone.utc)
    
    # Priority 1: hours argument
    if hours is not None:
        if hours <= 0:
            raise ValueError("Hours must be a positive number")
        start_time = now - timedelta(hours=hours)
        return (start_time, now)
    
    # Priority 2: both start and end provided
    if start and end:
        start_time = parse_flexible_time(start)
        end_time = parse_flexible_time(end)
        
        if end_time < start_time:
            raise ValueError(f"End time ({end_time}) must be after start time ({start_time})")
        
        return (start_time, end_time)
    
    # Priority 3: only start provided
    if start:
        start_time = parse_flexible_time(start)
        return (start_time, now)
    
    # Default: current and previous calendar hour
    # If it's 14:30, return (13:00, 15:00) covering hours 13 and 14
    current_hour_start = now.replace(minute=0, second=0, microsecond=0)
    previous_hour_start = current_hour_start - timedelta(hours=1)
    next_hour_start = current_hour_start + timedelta(hours=1)
    
    return (previous_hour_start, next_hour_start)


def format_time_range(start: datetime, end: datetime) -> str:
    """
    Format a time range for display.
    
    Args:
        start: Start datetime
        end: End datetime
        
    Returns:
        Formatted string representation of the time range
        
    Examples:
        >>> start = datetime(2024, 11, 19, 13, 0, 0, tzinfo=timezone.utc)
        >>> end = datetime(2024, 11, 19, 15, 0, 0, tzinfo=timezone.utc)
        >>> format_time_range(start, end)
        '2024-11-19 13:00 to 15:00 UTC (2.0 hours)'
    """
    # Calculate duration
    duration = end - start
    hours = duration.total_seconds() / 3600
    
    # Format dates
    start_str = start.strftime('%Y-%m-%d %H:%M')
    
    # If same day, only show time for end
    if start.date() == end.date():
        end_str = end.strftime('%H:%M')
    else:
        end_str = end.strftime('%Y-%m-%d %H:%M')
    
    return f"{start_str} to {end_str} UTC ({hours:.1f} hours)"


def get_calendar_hour_range(reference_time: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Get the current and previous calendar hour range.
    
    This is the default time range used by the Lambda function.
    If it's 14:30, returns (13:00, 15:00) covering hours 13 and 14.
    
    Args:
        reference_time: Optional reference time (defaults to now)
        
    Returns:
        Tuple of (start_time, end_time) covering two calendar hours
        
    Examples:
        >>> ref = datetime(2024, 11, 19, 14, 30, 0, tzinfo=timezone.utc)
        >>> get_calendar_hour_range(ref)
        (datetime(2024, 11, 19, 13, 0, 0), datetime(2024, 11, 19, 15, 0, 0))
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    
    current_hour_start = reference_time.replace(minute=0, second=0, microsecond=0)
    previous_hour_start = current_hour_start - timedelta(hours=1)
    next_hour_start = current_hour_start + timedelta(hours=1)
    
    return (previous_hour_start, next_hour_start)
