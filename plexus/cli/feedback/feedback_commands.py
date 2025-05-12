"""
Commands for managing Plexus feedback data.
"""

import click
import logging
import traceback
from typing import Optional, Dict, Any, Tuple
from rich.prompt import Confirm
import time
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, TimeElapsedColumn, SpinnerColumn, Task

from plexus.cli.console import console
from plexus.cli.client_utils import create_client
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.cli.reports.utils import resolve_account_id_for_command

logger = logging.getLogger(__name__)

@click.command(name="purge")
@click.option('--account', 'account_identifier', help='Optional account key or ID to filter by.', default=None)
@click.option('--yes', is_flag=True, help='Skip confirmation prompt.')
def purge_all_feedback(account_identifier: Optional[str], yes: bool):
    """
    Purge ALL feedback data (FeedbackItem records).
    
    This command permanently deletes all feedback data for the specified account.
    USE WITH CAUTION as this operation cannot be undone.
    """
    client = create_client()
    account_id = resolve_account_id_for_command(client, account_identifier)
    
    console.print(f"[bold yellow]CAUTION:[/bold yellow] About to purge [bold red]ALL[/bold red] feedback data for account: [cyan]{account_id}[/cyan]")
    
    try:
        # Count the records first to inform the user
        console.print("[dim]Counting feedback records...[/dim]")
        
        # Count FeedbackItem records
        item_records = FeedbackItem.count_by_account_id(account_id, client)
        
        console.print(f"Found:")
        console.print(f"  - [cyan]{item_records}[/cyan] FeedbackItem records")
        
        # Skip confirmation if there are no records to delete
        total_records = item_records
        if total_records == 0:
            console.print("[yellow]No feedback records found to delete.[/yellow]")
            return
            
        # Get confirmation unless --yes flag was provided
        if not yes:
            # Use Click's built-in confirmation prompt instead of rich.prompt.Confirm
            # to avoid potential issues with the prompt
            should_continue = click.confirm(
                "This will permanently delete ALL feedback data. Are you absolutely sure?", 
                default=False
            )
            if not should_continue:
                console.print("[yellow]Purge operation cancelled.[/yellow]")
                return
        else:
            console.print("[yellow]Skipping confirmation due to --yes flag.[/yellow]")
        
        # Setup main progress display with tasks for overall progress
        # and detail-level progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=50),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[cyan]{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            expand=True
        ) as progress:
            # Add main purge task to track overall progress
            main_task = progress.add_task(
                "[bold magenta]Purging ALL feedback data", 
                total=1,  # One main step: delete items
                completed=0
            )
            
            if item_records > 0:
                item_task = progress.add_task(
                    "[cyan]Deleting FeedbackItem records", 
                    total=item_records,
                    visible=False  # Hide initially
                )
            
            # Delete items
            if item_records > 0:
                progress.update(main_task, description="[bold magenta]Purging FeedbackItem records")
                # Make the item task visible
                progress.update(item_task, visible=True)
                
                # Pass the progress instance and task ID to the delete method
                items_deleted = FeedbackItem.delete_all_by_account_id(
                    account_id, 
                    client,
                    progress=progress,
                    task_id=item_task
                )
                
                # Hide the item task and advance main progress
                progress.update(item_task, visible=False)
                progress.update(main_task, advance=1)
            else:
                items_deleted = 0
                progress.update(main_task, advance=1)
            
            # Final step to show completion
            progress.update(main_task, description="[bold green]Purge completed")
            time.sleep(0.5)
        
        # Report success
        console.print(f"[green]Successfully purged all feedback data:[/green]")
        console.print(f"  - [cyan]{items_deleted}[/cyan] FeedbackItem records deleted")
        
    except Exception as e:
        console.print(f"[bold red]Error purging feedback data: {e}[/bold red]")
        logger.error(f"Failed to purge feedback data: {e}\n{traceback.format_exc()}") 