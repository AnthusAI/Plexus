"""
CLI commands for metrics aggregation.

Commands:
- show: Display aggregated metrics for a time range
- verify: Compare computed counts vs stored values (read-only)
- update: Recompute and update aggregated metrics
"""

import click
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import load_dotenv

from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.aggregated_metrics import AggregatedMetrics
from plexus.cli.shared.client_utils import create_client
from .time_utils import get_time_range_from_args, format_time_range
from .aggregation import (
    query_records_for_counting,
    count_records_efficiently,
    BUCKET_SIZES
)

# Load environment variables
load_dotenv()

# Console for rich output
console = Console()

# Record types to process
# Ordered from lowest to highest volume - high-volume types processed last
# Note: chatMessages excluded - no accountId field, belongs to sessions
RECORD_TYPES = [
    'tasks',           # Low volume
    'evaluations',     # Low volume
    'procedures',      # Low volume
    'chatSessions',    # Low volume
    'graphNodes',      # Low volume
    'feedbackItems',   # Medium volume
    'items',           # HIGH volume - 3 metrics computed
    'predictionItems',        # Filtered items
    'evaluationItems',        # Filtered items
    'scoreResults',    # HIGH volume - 3 metrics computed
    'predictionScoreResults',  # Filtered scoreResults
    'evaluationScoreResults',  # Filtered scoreResults
]

# Mapping of record types to their filter settings
RECORD_TYPE_FILTERS = {
    'predictionItems': {'filter_field': 'createdByType', 'filter_value': 'prediction'},
    'evaluationItems': {'filter_field': 'createdByType', 'filter_value': 'evaluation'},
    'predictionScoreResults': {'filter_field': 'type', 'filter_value': 'prediction'},
    'evaluationScoreResults': {'filter_field': 'type', 'filter_value': 'evaluation'},
}


def get_account_id_from_env(client: PlexusDashboardClient) -> str:
    """
    Get account ID from PLEXUS_ACCOUNT_KEY environment variable.
    
    Args:
        client: The API client
        
    Returns:
        Account ID
        
    Raises:
        ValueError: If PLEXUS_ACCOUNT_KEY is not set or account not found
    """
    account_key = os.environ.get('PLEXUS_ACCOUNT_KEY')
    if not account_key:
        raise ValueError("PLEXUS_ACCOUNT_KEY environment variable not set")
    
    account = Account.get_by_key(account_key, client)
    if not account:
        raise ValueError(f"Account with key '{account_key}' not found")
    
    return account.id


@click.group()
def metrics_group():
    """Metrics aggregation commands."""
    pass


@metrics_group.command('show')
@click.option('--hours', type=int, help='Show metrics for last N hours')
@click.option('--start', help='Start time (flexible format)')
@click.option('--end', help='End time (flexible format)')
@click.option('--record-type', help='Filter by record type (items, scoreResults, tasks, evaluations)')
def show_metrics(hours: Optional[int], start: Optional[str], end: Optional[str], record_type: Optional[str]):
    """Display aggregated metrics for a time range."""
    try:
        # Create client and get account
        client = create_client()
        account_id = get_account_id_from_env(client)
        
        # Parse time range
        start_time, end_time = get_time_range_from_args(hours, start, end)
        
        # Display header
        console.print(Panel(
            f"[bold cyan]Aggregated Metrics[/bold cyan]\n"
            f"Time Range: {format_time_range(start_time, end_time)}\n"
            f"Account: {os.environ.get('PLEXUS_ACCOUNT_KEY')}",
            expand=False
        ))
        
        # Determine which record types to query
        types_to_query = [record_type] if record_type else RECORD_TYPES
        
        # Query and display metrics for each record type
        for rec_type in types_to_query:
            metrics = AggregatedMetrics.list_by_time_range(
                client,
                account_id,
                start_time,
                end_time,
                rec_type
            )
            
            if not metrics:
                console.print(f"\n[yellow]No metrics found for {rec_type}[/yellow]")
                continue
            
            # Create table
            table = Table(title=f"{rec_type} Metrics")
            table.add_column("Time Range Start", style="cyan")
            table.add_column("Bucket", justify="right", style="magenta")
            table.add_column("Count", justify="right", style="green")
            table.add_column("Complete", justify="center")
            
            # Sort by time and bucket size
            metrics.sort(key=lambda m: (m.timeRangeStart, m.numberOfMinutes))
            
            # Add rows
            for metric in metrics:
                table.add_row(
                    metric.timeRangeStart.strftime('%Y-%m-%d %H:%M'),
                    f"{metric.numberOfMinutes}min",
                    str(metric.count),
                    "✓" if metric.complete else "⏳"
                )
            
            console.print(table)
            
            # Show summary statistics
            total_records = sum(m.count for m in metrics if m.numberOfMinutes == 1)
            console.print(f"[bold]Total records (1-min buckets): {total_records}[/bold]\n")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@metrics_group.command('verify')
@click.option('--hours', type=int, help='Verify last N hours')
@click.option('--start', help='Start time (flexible format)')
@click.option('--end', help='End time (flexible format)')
@click.option('--record-type', default='all', help='Specific record type or "all"')
def verify_metrics(hours: Optional[int], start: Optional[str], end: Optional[str], record_type: str):
    """Verify counts by comparing computed vs stored values (read-only)."""
    try:
        # Create client and get account
        client = create_client()
        account_id = get_account_id_from_env(client)
        
        # Parse time range
        start_time, end_time = get_time_range_from_args(hours, start, end)
        
        # Display header
        console.print(Panel(
            f"[bold cyan]Verify Metrics[/bold cyan]\n"
            f"Time Range: {format_time_range(start_time, end_time)}\n"
            f"Account: {os.environ.get('PLEXUS_ACCOUNT_KEY')}\n"
            f"[yellow]Read-only mode - no changes will be made[/yellow]",
            expand=False
        ))
        
        # Determine which record types to verify
        types_to_verify = [record_type] if record_type != 'all' else RECORD_TYPES
        
        all_match = True
        
        for rec_type in types_to_verify:
            console.print(f"\n[bold]Verifying {rec_type}...[/bold]")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                # Query raw records
                task = progress.add_task(f"Querying {rec_type}...", total=None)
                records = query_records_for_counting(
                    client,
                    account_id,
                    rec_type,
                    start_time,
                    end_time,
                    verbose=False
                )
                progress.update(task, completed=True)
                
                # Count into buckets
                task = progress.add_task("Counting into buckets...", total=None)
                # Get filter settings if this is a filtered record type
                filter_settings = RECORD_TYPE_FILTERS.get(rec_type, {})
                computed_counts = count_records_efficiently(
                    records,
                    account_id,
                    rec_type,
                    verbose=False,
                    **filter_settings
                )
                progress.update(task, completed=True)
                
                # Query existing metrics
                task = progress.add_task("Querying stored metrics...", total=None)
                stored_metrics = AggregatedMetrics.list_by_time_range(
                    client,
                    account_id,
                    start_time,
                    end_time,
                    rec_type
                )
                progress.update(task, completed=True)
            
            # Create lookup for stored metrics
            stored_lookup = {}
            for metric in stored_metrics:
                key = (
                    metric.timeRangeStart.isoformat(),
                    metric.numberOfMinutes
                )
                stored_lookup[key] = metric.count
            
            # Compare computed vs stored
            differences = []
            for computed in computed_counts:
                key = (
                    computed['time_range_start'].isoformat(),
                    computed['number_of_minutes']
                )
                computed_count = computed['count']
                stored_count = stored_lookup.get(key, 0)
                
                if computed_count != stored_count:
                    differences.append({
                        'time': computed['time_range_start'].strftime('%Y-%m-%d %H:%M'),
                        'bucket': f"{computed['number_of_minutes']}min",
                        'computed': computed_count,
                        'stored': stored_count,
                        'diff': computed_count - stored_count
                    })
            
            # Display results
            if differences:
                all_match = False
                table = Table(title=f"[red]Differences found for {rec_type}[/red]")
                table.add_column("Time", style="cyan")
                table.add_column("Bucket", style="magenta")
                table.add_column("Computed", justify="right", style="green")
                table.add_column("Stored", justify="right", style="yellow")
                table.add_column("Diff", justify="right", style="red")
                
                for diff in differences:
                    table.add_row(
                        diff['time'],
                        diff['bucket'],
                        str(diff['computed']),
                        str(diff['stored']),
                        f"{diff['diff']:+d}"
                    )
                
                console.print(table)
            else:
                console.print(f"[green]✓ All counts match for {rec_type}[/green]")
        
        # Exit with appropriate code
        if all_match:
            console.print(f"\n[bold green]✓ All metrics verified successfully[/bold green]")
            raise SystemExit(0)
        else:
            console.print(f"\n[bold red]✗ Differences found - run 'plexus metrics update' to fix[/bold red]")
            raise SystemExit(1)
    
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@metrics_group.command('update')
@click.option('--hours', type=int, help='Update last N hours')
@click.option('--start', help='Start time (flexible format)')
@click.option('--end', help='End time (flexible format)')
@click.option('--record-type', default='all', help='Specific record type or "all"')
@click.option('--force', is_flag=True, help='Update even if counts match')
def update_metrics(hours: Optional[int], start: Optional[str], end: Optional[str], record_type: str, force: bool):
    """Recompute and update aggregated metrics."""
    try:
        # Create client and get account
        client = create_client()
        account_id = get_account_id_from_env(client)
        
        # Parse time range
        start_time, end_time = get_time_range_from_args(hours, start, end)
        
        # Display header
        console.print(Panel(
            f"[bold cyan]Update Metrics[/bold cyan]\n"
            f"Time Range: {format_time_range(start_time, end_time)}\n"
            f"Account: {os.environ.get('PLEXUS_ACCOUNT_KEY')}\n"
            f"[red]{'Force update mode' if force else 'Will update only changed counts'}[/red]",
            expand=False
        ))
        
        # Determine which record types to update
        types_to_update = [record_type] if record_type != 'all' else RECORD_TYPES
        
        total_updates = 0
        total_skipped = 0
        
        for rec_type in types_to_update:
            console.print(f"\n[bold]Updating {rec_type}...[/bold]")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                # Query raw records
                task = progress.add_task(f"Querying {rec_type}...", total=None)
                records = query_records_for_counting(
                    client,
                    account_id,
                    rec_type,
                    start_time,
                    end_time,
                    verbose=False
                )
                progress.update(task, completed=True)
                
                # Count into buckets
                task = progress.add_task("Counting into buckets...", total=None)
                # Get filter settings if this is a filtered record type
                filter_settings = RECORD_TYPE_FILTERS.get(rec_type, {})
                computed_counts = count_records_efficiently(
                    records,
                    account_id,
                    rec_type,
                    verbose=True,  # Show counting details
                    **filter_settings
                )
                progress.update(task, completed=True)
                
                # Query existing metrics if not forcing
                stored_lookup = {}
                if not force:
                    task = progress.add_task("Querying stored metrics...", total=None)
                    stored_metrics = AggregatedMetrics.list_by_time_range(
                        client,
                        account_id,
                        start_time,
                        end_time,
                        rec_type
                    )
                    progress.update(task, completed=True)
                    
                    for metric in stored_metrics:
                        key = (
                            metric.timeRangeStart.isoformat(),
                            metric.numberOfMinutes
                        )
                        stored_lookup[key] = metric.count
                
                # Update metrics
                task = progress.add_task("Updating metrics...", total=len(computed_counts))
                updates = 0
                skipped = 0
                
                for computed in computed_counts:
                    key = (
                        computed['time_range_start'].isoformat(),
                        computed['number_of_minutes']
                    )
                    computed_count = computed['count']
                    stored_count = stored_lookup.get(key, None)
                    
                    # Skip if counts match and not forcing
                    if not force and stored_count == computed_count:
                        skipped += 1
                        progress.update(task, advance=1)
                        continue
                    
                    # Update via ORM
                    AggregatedMetrics.create_or_update(
                        client,
                        account_id=account_id,
                        record_type=rec_type,
                        time_range_start=computed['time_range_start'],
                        time_range_end=computed['time_range_end'],
                        number_of_minutes=computed['number_of_minutes'],
                        count=computed_count,
                        complete=computed['complete']
                    )
                    updates += 1
                    progress.update(task, advance=1)
                
                progress.update(task, completed=True)
            
            console.print(f"[green]✓ Updated {updates} buckets, skipped {skipped} (unchanged)[/green]")
            total_updates += updates
            total_skipped += skipped
        
        # Final summary
        console.print(f"\n[bold green]✓ Complete: {total_updates} buckets updated, {total_skipped} skipped[/bold green]")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
