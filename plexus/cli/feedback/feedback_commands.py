"""
Commands for managing Plexus feedback data.
"""

import click
import logging
import traceback
from typing import Optional, Dict, Any, Tuple
from rich.prompt import Confirm

from plexus.cli.console import console
from plexus.cli.client_utils import create_client
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.dashboard.api.models.feedback_change_detail import FeedbackChangeDetail
from plexus.cli.reports.utils import resolve_account_id_for_command

logger = logging.getLogger(__name__)

@click.command(name="purge")
@click.option('--account', 'account_identifier', help='Optional account key or ID to filter by.', default=None)
@click.option('--yes', is_flag=True, help='Skip confirmation prompt.')
def purge_all_feedback(account_identifier: Optional[str], yes: bool):
    """
    Purge ALL feedback data (FeedbackItem and FeedbackChangeDetail records).
    
    This command permanently deletes all feedback data for the specified account.
    USE WITH CAUTION as this operation cannot be undone.
    """
    client = create_client()
    account_id = resolve_account_id_for_command(client, account_identifier)
    
    console.print(f"[bold yellow]CAUTION:[/bold yellow] About to purge [bold red]ALL[/bold red] feedback data for account: [cyan]{account_id}[/cyan]")
    
    try:
        # Count the records first to inform the user
        console.print("[dim]Counting feedback records...[/dim]")
        
        # Count FeedbackChangeDetail records
        change_detail_records = FeedbackChangeDetail.count_by_account_id(account_id, client)
        
        # Count FeedbackItem records
        item_records = FeedbackItem.count_by_account_id(account_id, client)
        
        console.print(f"Found:")
        console.print(f"  - [cyan]{item_records}[/cyan] FeedbackItem records")
        console.print(f"  - [cyan]{change_detail_records}[/cyan] FeedbackChangeDetail records")
        
        # Skip confirmation if there are no records to delete
        total_records = item_records + change_detail_records
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
        
        # Perform the deletion in the correct order (child records first)
        console.print("[dim]Purging FeedbackChangeDetail records first...[/dim]")
        change_details_deleted = FeedbackChangeDetail.delete_all_by_account_id(account_id, client)
        
        console.print("[dim]Purging FeedbackItem records...[/dim]")
        items_deleted = FeedbackItem.delete_all_by_account_id(account_id, client)
        
        # Report success
        console.print(f"[green]Successfully purged all feedback data:[/green]")
        console.print(f"  - [cyan]{items_deleted}[/cyan] FeedbackItem records deleted")
        console.print(f"  - [cyan]{change_details_deleted}[/cyan] FeedbackChangeDetail records deleted")
        
    except Exception as e:
        console.print(f"[bold red]Error purging feedback data: {e}[/bold red]")
        logger.error(f"Failed to purge feedback data: {e}\n{traceback.format_exc()}") 