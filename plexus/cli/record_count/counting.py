"""
CLI commands for counting records (items and score results).
"""

import click
import os
import json
import logging
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import load_dotenv

from plexus.metrics.calculator import create_calculator_from_env

# Load environment variables from .env file
load_dotenv('.env', override=True)

# Set up console for rich output
console = Console()

def resolve_account_id(account_id_param: Optional[str]) -> str:
    """
    Resolve account ID using the same pattern as other CLI commands.
    
    Args:
        account_id_param: Account ID provided via command line parameter
        
    Returns:
        Resolved account ID
        
    Raises:
        click.Abort: If account ID cannot be resolved
    """
    if account_id_param:
        return account_id_param
    
    try:
        from plexus.cli.shared.client_utils import create_client
        from plexus.cli.report.utils import resolve_account_id_for_command
        
        client = create_client()
        return resolve_account_id_for_command(client, None)
    except Exception as e:
        # Fallback to environment variable if the client approach fails
        account_id = os.environ.get('PLEXUS_ACCOUNT_KEY')
        if account_id:
            return account_id
        
        raise click.Abort(f"Could not resolve account ID. Provide --account-id or set PLEXUS_ACCOUNT_KEY environment variable. Error: {e}")


# Create the main count group
@click.group(name='count')
def count_group():
    """Count items and score results with various time-based filters."""
    pass


@click.command('items')
@click.option('--account-id', '-a', help='Account ID (uses PLEXUS_ACCOUNT_KEY env var if not specified)')
@click.option('--hours', '-h', type=int, default=24, help='Number of hours to look back (default: 24)')
@click.option('--bucket-width', default=15, help='The width of the cache buckets in minutes.')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--json-output', '-j', is_flag=True, help='Output results as JSON')
def count_items(account_id: Optional[str], hours: int, bucket_width: int, verbose: bool, json_output: bool):
    """Count items created in the specified timeframe."""
    
    # Set up logging - suppress for JSON output
    if json_output:
        logging.disable(logging.CRITICAL)
    elif verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
        
    logger = logging.getLogger(__name__)
    
    try:
        # Resolve account ID using the same pattern as other CLI commands
        resolved_account_id = resolve_account_id(account_id)
        
        if not json_output:
            console.print(Panel.fit(f"Counting items for account {resolved_account_id} over the last {hours} hours", title="Items Count"))
        
        # Create calculator and get metrics
        if json_output:
            # Skip progress display for JSON output
            calculator = create_calculator_from_env(cache_bucket_minutes=bucket_width)
            metrics = calculator.get_items_summary(resolved_account_id, hours)
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Calculating metrics...", total=None)
                
                calculator = create_calculator_from_env(cache_bucket_minutes=bucket_width)
                metrics = calculator.get_items_summary(resolved_account_id, hours)
                
                progress.remove_task(task)
        
        if json_output:
            # Output just the items-related data as JSON
            items_data = {
                'account_id': resolved_account_id,
                'hours_analyzed': hours,
                'items_current_hour': metrics['itemsPerHour'],
                'items_average_per_hour': metrics['itemsAveragePerHour'],
                'items_peak_hourly': metrics['itemsPeakHourly'],
                'items_total': metrics['itemsTotal24h'],
                'hourly_breakdown': [
                    {
                        'time': bucket['time'],
                        'count': bucket['items'],
                        'bucket_start': bucket['bucketStart'],
                        'bucket_end': bucket['bucketEnd']
                    }
                    for bucket in metrics['chartData']
                ]
            }
            console.print(json.dumps(items_data, indent=2))
        else:
            # Create summary table
            table = Table(title=f"Items Summary (Last {hours} Hours)")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Current Hour", str(metrics['itemsPerHour']))
            table.add_row("Average per Hour", str(metrics['itemsAveragePerHour']))
            table.add_row("Peak Hourly", str(metrics['itemsPeakHourly']))
            table.add_row(f"Total ({hours}h)", str(metrics['itemsTotal24h']))
            
            console.print(table)
            
            # Create hourly breakdown table
            breakdown_table = Table(title="Hourly Breakdown")
            breakdown_table.add_column("Time Period", style="cyan")
            breakdown_table.add_column("Items Count", style="green")
            
            for bucket in metrics['chartData'][:10]:  # Show first 10 hours
                breakdown_table.add_row(bucket['time'], str(bucket['items']))
                
            if len(metrics['chartData']) > 10:
                breakdown_table.add_row("...", "...")
                
            console.print(breakdown_table)
        
    except Exception as e:
        if json_output:
            error_data = {"error": str(e)}
            console.print(json.dumps(error_data, indent=2))
        else:
            console.print(f"[red]Error: {str(e)}[/red]")
            logger.error(f"Error counting items: {str(e)}")
        raise click.Abort()


@click.command('scoreresults')
@click.option('--account-id', '-a', help='Account ID (uses PLEXUS_ACCOUNT_KEY env var if not specified)')
@click.option('--hours', '-h', type=int, default=24, help='Number of hours to look back (default: 24)')
@click.option('--bucket-width', default=15, help='The width of the cache buckets in minutes.')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--json-output', '-j', is_flag=True, help='Output results as JSON')
def count_scoreresults(account_id: Optional[str], hours: int, bucket_width: int, verbose: bool, json_output: bool):
    """Count score results created in the specified timeframe."""
    
    # Set up logging - suppress for JSON output
    if json_output:
        logging.disable(logging.CRITICAL)
    elif verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
        
    logger = logging.getLogger(__name__)
    
    try:
        # Resolve account ID using the same pattern as other CLI commands
        resolved_account_id = resolve_account_id(account_id)
        
        if not json_output:
            console.print(Panel.fit(f"Counting score results for account {resolved_account_id} over the last {hours} hours", title="Score Results Count"))
        
        # Create calculator and get metrics
        if json_output:
            # Skip progress display for JSON output
            calculator = create_calculator_from_env(cache_bucket_minutes=bucket_width)
            metrics = calculator.get_score_results_summary(resolved_account_id, hours)
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Calculating metrics...", total=None)
                
                calculator = create_calculator_from_env(cache_bucket_minutes=bucket_width)
                metrics = calculator.get_score_results_summary(resolved_account_id, hours)
                
                progress.remove_task(task)
        
        if json_output:
            # Output just the score results-related data as JSON
            score_results_data = {
                'account_id': resolved_account_id,
                'hours_analyzed': hours,
                'score_results_current_hour': metrics['scoreResultsPerHour'],
                'score_results_average_per_hour': metrics['scoreResultsAveragePerHour'],
                'score_results_peak_hourly': metrics['scoreResultsPeakHourly'],
                'score_results_total': metrics['scoreResultsTotal24h'],
                'hourly_breakdown': [
                    {
                        'time': bucket['time'],
                        'count': bucket['scoreResults'],
                        'bucket_start': bucket['bucketStart'],
                        'bucket_end': bucket['bucketEnd']
                    }
                    for bucket in metrics['chartData']
                ]
            }
            console.print(json.dumps(score_results_data, indent=2))
        else:
            # Create summary table
            table = Table(title=f"Score Results Summary (Last {hours} Hours)")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Current Hour", str(metrics['scoreResultsPerHour']))
            table.add_row("Average per Hour", str(metrics['scoreResultsAveragePerHour']))
            table.add_row("Peak Hourly", str(metrics['scoreResultsPeakHourly']))
            table.add_row(f"Total ({hours}h)", str(metrics['scoreResultsTotal24h']))
            
            console.print(table)
            
            # Create hourly breakdown table
            breakdown_table = Table(title="Hourly Breakdown")
            breakdown_table.add_column("Time Period", style="cyan")
            breakdown_table.add_column("Score Results Count", style="green")
            
            for bucket in metrics['chartData'][:10]:  # Show first 10 hours
                breakdown_table.add_row(bucket['time'], str(bucket['scoreResults']))
                
            if len(metrics['chartData']) > 10:
                breakdown_table.add_row("...", "...")
                
            console.print(breakdown_table)
        
    except Exception as e:
        if json_output:
            error_data = {"error": str(e)}
            console.print(json.dumps(error_data, indent=2))
        else:
            console.print(f"[red]Error: {str(e)}[/red]")
            logger.error(f"Error counting score results: {str(e)}")
        raise click.Abort()


# Add an alias for 'results'
@click.command('results')
@click.option('--account-id', '-a', help='Account ID (uses PLEXUS_ACCOUNT_KEY env var if not specified)')
@click.option('--hours', '-h', type=int, default=24, help='Number of hours to look back (default: 24)')
@click.option('--bucket-width', default=15, help='The width of the cache buckets in minutes.')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--json-output', '-j', is_flag=True, help='Output results as JSON')
def count_results(account_id: Optional[str], hours: int, bucket_width: int, verbose: bool, json_output: bool):
    """Count score results created in the specified timeframe (alias for scoreresults)."""
    # Just call the scoreresults function with the same parameters
    from click.testing import CliRunner
    from click import Context
    
    # Create a new context and invoke the scoreresults command
    ctx = Context(count_scoreresults)
    ctx.invoke(count_scoreresults, account_id=account_id, hours=hours, bucket_width=bucket_width, verbose=verbose, json_output=json_output)


# Add commands to the group
count_group.add_command(count_items)
count_group.add_command(count_scoreresults) 
count_group.add_command(count_results)

# Export the group so it can be imported by the main CLI
count = count_group 