"""
Display utilities for rendering API model objects in rich output formats.

This module provides standardized methods for converting API model objects
to rich Display objects (Panels, Tables, etc.) for consistent CLI output.
"""

import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group
from rich import box

logger = logging.getLogger(__name__)

def format_datetime(dt: Optional[datetime]) -> str:
    """Format a datetime object for display, handling None values."""
    if not dt:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def truncate_text(text: Optional[str], max_length: int = 40) -> str:
    """Truncate text to specified length, adding ellipsis if needed."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def dict_to_table(data: Dict[str, Any], style_key: str = "cyan") -> Table:
    """Convert a dictionary to a rich Table for display."""
    table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    table.add_column("Field", style=style_key)
    table.add_column("Value")
    
    for key, value in data.items():
        # Handle various value types
        if isinstance(value, datetime):
            display_value = format_datetime(value)
        elif isinstance(value, str):
            display_value = truncate_text(value)
        elif value is None:
            display_value = "N/A"
        elif isinstance(value, bool):
            display_value = "Yes" if value else "No"
        else:
            display_value = str(value)
            
        table.add_row(key, display_value)
        
    return table

def model_to_panel(
    model: Any, 
    title: Optional[str] = None, 
    fields: Optional[List[str]] = None,
    border_style: str = "green",
    nested_panels: Optional[List[Panel]] = None
) -> Panel:
    """
    Convert an API model object to a rich Panel for display.
    
    Args:
        model: The model object to display
        title: Optional title for the panel
        fields: List of fields to include (defaults to all public fields)
        border_style: Style to use for the panel border
        nested_panels: Optional list of panels to display beneath the model data
        
    Returns:
        A rich Panel object displaying the model data
    """
    if not model:
        return Panel("No data available", title=title or "Empty Record", border_style="red")
    
    # Generate panel title if not provided
    if not title:
        model_type = type(model).__name__
        model_id = getattr(model, 'id', None)
        title = f"{model_type}" + (f" ({model_id})" if model_id else "")
    
    # Get fields to display
    if not fields:
        # Exclude private fields and relationship fields by default
        fields = [
            attr for attr in dir(model) 
            if not attr.startswith('_') and 
            not callable(getattr(model, attr)) and
            not isinstance(getattr(model, attr), (list, dict))
        ]
    
    # Build data dictionary
    data = {}
    for field in fields:
        if hasattr(model, field):
            data[field] = getattr(model, field)
    
    # Create table from data
    table = dict_to_table(data)
    
    # Create renderable group for all content
    group_items = [table]
    
    # Add nested panels with header if provided
    if nested_panels and len(nested_panels) > 0:
        group_items.append(Text("\nChange Details:", style="bold"))
        group_items.extend(nested_panels)
    else:
        group_items.append(Text("\nNo change details available", style="italic"))
    
    # Create a group from the items
    content_group = Group(*group_items)
    
    # Create and return the panel
    return Panel(
        content_group,
        title=title,
        border_style=border_style
    ) 