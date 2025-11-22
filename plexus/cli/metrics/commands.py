"""
CLI commands for metrics aggregation.

Commands:
- show: Display aggregated metrics for a time range
- verify: Compare computed counts vs stored values (read-only)
- update: Recompute and update aggregated metrics
"""

import click
import os
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID
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
@click.option('--concurrency', type=int, default=10, help='Number of parallel workers (default: 10, max recommended: 50)')
def update_metrics(hours: Optional[int], start: Optional[str], end: Optional[str], record_type: str, force: bool, concurrency: int):
    """
    Recompute and update aggregated metrics with parallel processing.
    
    Buckets are written immediately as they're computed, using multiple parallel workers
    for maximum throughput. Increase --concurrency for faster updates of large time ranges.
    """
    try:
        # Create client and get account
        client = create_client()
        account_id = get_account_id_from_env(client)
        
        # Parse time range
        start_time, end_time = get_time_range_from_args(hours, start, end)
        
        # Display header
        console.print(Panel(
            f"[bold cyan]Update Metrics (Parallel)[/bold cyan]\n"
            f"Time Range: {format_time_range(start_time, end_time)}\n"
            f"Account: {os.environ.get('PLEXUS_ACCOUNT_KEY')}\n"
            f"Concurrency: {concurrency} workers\n"
            f"[red]{'Force update mode' if force else 'Will update only changed counts'}[/red]",
            expand=False
        ))
        
        # Determine which record types to update
        types_to_update = [record_type] if record_type != 'all' else RECORD_TYPES
        
        total_updates = 0
        total_skipped = 0
        
        # Process each record type
        for rec_type in types_to_update:
            console.print(f"\n[bold]Updating {rec_type}...[/bold]")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console
            ) as progress:
                # Query raw records
                query_task = progress.add_task(f"Querying {rec_type}...", total=None)
                console.print(f"[dim]Querying {rec_type} records from {format_time_range(start_time, end_time)}...[/dim]")
                records = query_records_for_counting(
                    client,
                    account_id,
                    rec_type,
                    start_time,
                    end_time,
                    verbose=True  # Show pagination progress
                )
                console.print(f"[dim]Retrieved {len(records)} {rec_type} records[/dim]")
                progress.update(query_task, completed=True)
                
                # Count into buckets
                count_task = progress.add_task("Counting into buckets...", total=None)
                console.print(f"[dim]Counting {len(records)} records into time buckets...[/dim]")
                # Get filter settings if this is a filtered record type
                filter_settings = RECORD_TYPE_FILTERS.get(rec_type, {})
                computed_counts = count_records_efficiently(
                    records,
                    account_id,
                    rec_type,
                    verbose=True,  # Show counting details
                    **filter_settings
                )
                console.print(f"[dim]Generated {len(computed_counts)} bucket counts[/dim]")
                progress.update(count_task, completed=True)
                
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
                
                # Filter buckets that need updating
                buckets_to_update = []
                for computed in computed_counts:
                    key = (
                        computed['time_range_start'].isoformat(),
                        computed['number_of_minutes']
                    )
                    computed_count = computed['count']
                    stored_count = stored_lookup.get(key, None)
                    
                    # Skip if counts match and not forcing
                    if not force and stored_count == computed_count:
                        total_skipped += 1
                        continue
                    
                    buckets_to_update.append(computed)
                
                # Sort buckets by time (most recent first) so dashboard shows recent data immediately
                buckets_to_update.sort(
                    key=lambda b: (b['time_range_start'], b['number_of_minutes']),
                    reverse=True
                )
                
                if not buckets_to_update:
                    console.print(f"[yellow]No updates needed for {rec_type}[/yellow]")
                    continue
                
                # Show time range being updated
                oldest_bucket = min(buckets_to_update, key=lambda b: b['time_range_start'])
                newest_bucket = max(buckets_to_update, key=lambda b: b['time_range_start'])
                console.print(f"[dim]Updating {len(buckets_to_update)} buckets from {newest_bucket['time_range_start'].strftime('%Y-%m-%d %H:%M')} back to {oldest_bucket['time_range_start'].strftime('%Y-%m-%d %H:%M')} (most recent first)[/dim]")
                
                # Update metrics in parallel
                task = progress.add_task(
                    f"Updating {len(buckets_to_update)} buckets...", 
                    total=len(buckets_to_update)
                )
                
                # Thread-local storage for clients (one per thread)
                thread_local = threading.local()
                
                def get_thread_client():
                    """Get or create a client for the current thread."""
                    if not hasattr(thread_local, 'client'):
                        thread_local.client = create_client()
                    return thread_local.client
                
                def update_bucket(bucket_data: Dict[str, Any]) -> bool:
                    """Update a single bucket. Returns True on success."""
                    try:
                        # Use thread-local client to avoid creating new clients constantly
                        thread_client = get_thread_client()
                        AggregatedMetrics.create_or_update(
                            thread_client,
                            account_id=account_id,
                            record_type=rec_type,
                            time_range_start=bucket_data['time_range_start'],
                            time_range_end=bucket_data['time_range_end'],
                            number_of_minutes=bucket_data['number_of_minutes'],
                            count=bucket_data['count'],
                            complete=bucket_data['complete']
                        )
                        return True
                    except Exception as e:
                        console.print(f"[red]Error updating bucket: {e}[/red]")
                        return False
                
                # Process buckets in parallel
                updates = 0
                errors = 0
                last_report = 0
                report_interval = max(10, len(buckets_to_update) // 20)  # Report every 5% or 10 buckets
                
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    # Submit all tasks
                    future_to_bucket = {
                        executor.submit(update_bucket, bucket): bucket 
                        for bucket in buckets_to_update
                    }
                    
                    # Process as they complete
                    for completed_count, future in enumerate(as_completed(future_to_bucket), 1):
                        if future.result():
                            updates += 1
                        else:
                            errors += 1
                        progress.update(task, advance=1)
                        
                        # Periodic progress report
                        if completed_count - last_report >= report_interval:
                            pct = (completed_count / len(buckets_to_update)) * 100
                            console.print(f"[dim]  Progress: {completed_count}/{len(buckets_to_update)} ({pct:.0f}%) - {updates} updated, {errors} errors[/dim]")
                            last_report = completed_count
                
                progress.update(task, completed=True)
            
            console.print(f"[green]✓ Updated {updates} buckets for {rec_type}[/green]")
            total_updates += updates
        
        # Final summary
        console.print(f"\n[bold green]✓ Complete: {total_updates} buckets updated, {total_skipped} skipped[/bold green]")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()


@metrics_group.command('delete-all')
@click.option('--dry-run', is_flag=True, help='Show what would be deleted without actually deleting')
@click.confirmation_option(prompt='Are you sure you want to delete ALL aggregated metrics? This cannot be undone!')
def delete_all_metrics(dry_run: bool):
    """
    Delete all AggregatedMetrics records for the account.
    
    Use this before schema migration to clean up old records.
    After deletion, run 'plexus metrics update' to repopulate.
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        raise click.Abort()
    
    try:
        # Get account ID
        account_id = get_account_id_from_env(client)
        
        console.print(f"\n[yellow]{'DRY RUN: ' if dry_run else ''}Deleting all AggregatedMetrics for account {account_id}...[/yellow]\n")
        
        deleted = 0
        errors = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task("Querying records...", total=None)
            
            # Query all records using the GSI
            query = """
            query ListAllMetrics($accountId: String!, $nextToken: String) {
                listAggregatedMetricsByAccountIdAndTimeRangeStartAndRecordType(
                    accountId: $accountId,
                    limit: 1000,
                    nextToken: $nextToken
                ) {
                    items {
                        accountId
                        compositeKey
                        recordType
                        timeRangeStart
                        numberOfMinutes
                    }
                    nextToken
                }
            }
            """
            
            next_token = None
            batch_count = 0
            
            while True:
                # Query batch
                variables = {'accountId': account_id}
                if next_token:
                    variables['nextToken'] = next_token
                
                result = client.execute(query, variables)
                items = result.get('listAggregatedMetricsByAccountIdAndTimeRangeStartAndRecordType', {}).get('items', [])
                
                if not items:
                    break
                
                batch_count += 1
                
                # Update progress with total for this batch
                progress.update(task, description=f"Deleting batch {batch_count}", total=len(items), completed=0)
                
                # Delete each record
                for idx, item in enumerate(items):
                    if not dry_run:
                        try:
                            delete_mutation = """
                            mutation DeleteAggregatedMetrics($input: DeleteAggregatedMetricsInput!) {
                                deleteAggregatedMetrics(input: $input) {
                                    accountId
                                    compositeKey
                                }
                            }
                            """
                            
                            delete_input = {
                                'accountId': item['accountId'],
                                'compositeKey': item['compositeKey']
                            }
                            
                            client.execute(delete_mutation, {'input': delete_input})
                            deleted += 1
                        except Exception as e:
                            errors += 1
                            console.print(f"[red]Error deleting {item['recordType']} {item['timeRangeStart']}: {e}[/red]")
                    else:
                        deleted += 1
                    
                    # Update progress
                    progress.update(task, completed=idx + 1)
                
                # Check for more pages
                next_token = result.get('listAggregatedMetricsByAccountIdAndTimeRangeStartAndRecordType', {}).get('nextToken')
                if not next_token:
                    break
            
            progress.update(task, description="Complete", completed=True)
        
        # Summary
        if dry_run:
            console.print(f"\n[yellow]DRY RUN: Would delete {deleted} records[/yellow]")
        else:
            if errors > 0:
                console.print(f"\n[yellow]⚠ Deleted {deleted} records with {errors} errors[/yellow]")
            else:
                console.print(f"\n[green]✓ Successfully deleted {deleted} records[/green]")
        
        if not dry_run and deleted > 0:
            console.print(f"\n[dim]To repopulate metrics, run:[/dim]")
            console.print(f"[dim]  plexus metrics update --hours 168[/dim]")
    
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()
