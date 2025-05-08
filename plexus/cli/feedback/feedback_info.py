"""
Command for displaying feedback data information.
"""

import click
import logging
from typing import Optional, List, Dict, Any
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from datetime import datetime

from plexus.cli.console import console
from plexus.cli.client_utils import create_client
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.cli.reports.utils import resolve_account_id_for_command

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

def get_feedback_stats(client, account_id: str) -> Dict[str, int]:
    """Get feedback data statistics."""
    # Count FeedbackItem records
    item_count = FeedbackItem.count_by_account_id(account_id, client)
    
    return {
        "items": item_count
    }

def get_recent_feedback_items(client, account_id: str, limit: int = 3) -> List[FeedbackItem]:
    """Get the most recent feedback items."""
    # Get the most recent feedback items
    items, _ = FeedbackItem.list(
        client=client,
        account_id=account_id,
        limit=limit,
        fields=FeedbackItem.GRAPHQL_BASE_FIELDS
    )
    
    # Sort by updatedAt descending (most recent first)
    return sorted(items, key=lambda item: item.updatedAt if item.updatedAt else datetime.min, reverse=True)

def display_feedback_item(item: FeedbackItem) -> None:
    """Display a FeedbackItem in rich format."""
    # Main item panel
    item_table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    item_table.add_column("Field", style="cyan")
    item_table.add_column("Value")
    
    # Add the basic fields
    item_table.add_row("ID", item.id)
    item_table.add_row("Cache Key", item.cacheKey or "N/A")
    item_table.add_row("Initial Answer", item.initialAnswerValue or "N/A")
    item_table.add_row("Final Answer", item.finalAnswerValue or "N/A")
    item_table.add_row("Initial Comment", truncate_text(item.initialCommentValue))
    item_table.add_row("Final Comment", truncate_text(item.finalCommentValue))
    item_table.add_row("Edit Comment", truncate_text(item.editCommentValue))
    item_table.add_row("Is Agreement", "Yes" if item.isAgreement else "No")
    item_table.add_row("Created At", format_datetime(item.createdAt))
    item_table.add_row("Updated At", format_datetime(item.updatedAt))
    
    # Create and print the panel containing the table
    main_panel = Panel(
        item_table,
        title=f"Feedback Item ({item.id})",
        border_style="green"
    )
    console.print(main_panel)

@click.command(name="info")
def feedback_info():
    """
    Display information about feedback data.
    
    Shows counts of feedback items and the most recent feedback items.
    """
    client = create_client()
    account_id = resolve_account_id_for_command(client, None)  # Use default account
    
    console.print(f"Feedback data for account: [cyan]{account_id}[/cyan]\n")
    
    try:
        # Get and display counts
        stats = get_feedback_stats(client, account_id)
        count_table = Table(title="Record Counts")
        count_table.add_column("Record Type", style="cyan")
        count_table.add_column("Count", justify="right")
        
        count_table.add_row("FeedbackItem", str(stats["items"]))
        
        console.print(count_table)
        console.print("")
        
        # If there are no items, just return
        if stats["items"] == 0:
            console.print("[yellow]No feedback items found.[/yellow]")
            return
            
        # Get and display recent items
        console.print("[bold]Recent Feedback Items:[/bold]\n")
        recent_items = get_recent_feedback_items(client, account_id)
        
        if not recent_items:
            console.print("[yellow]No recent feedback items found.[/yellow]")
            return
        
        for item in recent_items:
            display_feedback_item(item)
            console.print("")  # Add spacing between items
            
    except Exception as e:
        console.print(f"[bold red]Error retrieving feedback info: {e}[/bold red]")
        logger.error(f"Failed to retrieve feedback info: {e}") 