"""
Command module for Plexus report generation commands.
"""

import click
import logging
import json
import traceback
from datetime import datetime, timezone
from typing import Optional, Tuple
import sys

from plexus.cli.console import console
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.cli.client_utils import create_client
from plexus.dashboard.api.models.report_configuration import ReportConfiguration
from plexus.dashboard.api.models.report import Report
from plexus.reports.service import generate_report
from rich.table import Table # Import Table for display
from rich.panel import Panel
from rich.pretty import pretty_repr
from dataclasses import asdict

from plexus.cli.utils import parse_kv_pairs # Assume this exists

logger = logging.getLogger(__name__)

@click.group()
def report():
    """Commands for managing and running reports."""
    # Diagnostic print
    # print("--- Report command group loaded ---", file=sys.stderr) # Removed diagnostic print
    pass

@report.command(name="list") # Add the list command
@click.option('--account', 'account_identifier', help='Optional account key or ID to filter by.', default=None)
@click.option('--limit', type=int, default=50, help='Maximum number of configurations to list.')
def list_configurations(account_identifier: Optional[str], limit: int):
    """List available Report Configurations for an account."""
    client = create_client()
    
    account_id = None
    if account_identifier:
        # Attempt to resolve provided identifier (could be key or ID)
        # We might need a shared resolver utility like in ScorecardCommands eventually
        try:
            account_id = client._resolve_account_id(account_key=account_identifier) # Assuming _resolve takes optional key
        except Exception as e:
            # Fallback: Try direct ID lookup if key lookup fails or method doesn't exist
            try:
                from plexus.dashboard.api.models.account import Account
                acc = Account.get_by_id(account_identifier, client)
                account_id = acc.id
            except Exception:
                 console.print(f"[red]Error: Could not resolve account identifier '{account_identifier}': {e}[/red]")
                 return
    else:
        # Resolve from context/env var if no specific account provided
        try:
            account_id = client._resolve_account_id()
        except Exception as e:
            console.print(f"[red]Error resolving default account: {e}. Is PLEXUS_ACCOUNT_KEY set?[/red]")
            return

    if not account_id:
        console.print("[red]Error: Could not determine Account ID.[/red]")
        return

    console.print(f"[cyan]Listing Report Configurations for Account ID: {account_id}[/cyan]")

    try:
        # Call the centralized model method to list configurations
        result_data = ReportConfiguration.list_by_account_id(
            account_id=account_id,
            client=client,
            limit=limit
        )
        items = result_data.get('items', []) # Extract items from the returned dict

        if not items:
            console.print(f"[yellow]No report configurations found for account {account_id}.[/yellow]")
            return

        # Display results in a table
        table = Table(title=f"Report Configurations (Account: {account_id})")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Description", style="green")
        table.add_column("Created At", style="blue")
        table.add_column("Updated At", style="blue")

        for config_instance in items: # Iterate over ReportConfiguration instances
            # Format datetimes if they exist, otherwise show N/A
            # Assumes from_dict correctly parses them into datetime objects
            # Adjust formatting as needed
            created_at_str = config_instance.createdAt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(config_instance, 'createdAt') and config_instance.createdAt else 'N/A' 
            updated_at_str = config_instance.updatedAt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(config_instance, 'updatedAt') and config_instance.updatedAt else 'N/A'
            
            table.add_row(
                config_instance.id, 
                config_instance.name, 
                config_instance.description or '-', 
                created_at_str, 
                updated_at_str
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error listing report configurations: {e}[/bold red]")
        logger.error(f"Failed to list report configurations: {e}\n{traceback.format_exc()}")

@report.command()
@click.option('--name', required=True, help='The name of the Report to retrieve.')
@click.option('--account', 'account_identifier', help='Optional account key or ID to filter by.', default=None)
def get(name: str, account_identifier: Optional[str]):
    """Get details for a specific Report by its name."""
    client = create_client()

    account_id = None
    # Reuse account resolution logic from 'list' command
    if account_identifier:
        try:
            account_id = client._resolve_account_id(account_key=account_identifier)
        except Exception as e:
            try:
                from plexus.dashboard.api.models.account import Account
                acc = Account.get_by_id(account_identifier, client)
                account_id = acc.id
            except Exception:
                 console.print(f"[red]Error: Could not resolve account identifier '{account_identifier}': {e}[/red]")
                 return
    else:
        try:
            account_id = client._resolve_account_id()
        except Exception as e:
            console.print(f"[red]Error resolving default account: {e}. Is PLEXUS_ACCOUNT_KEY set?[/red]")
            return

    if not account_id:
        console.print("[red]Error: Could not determine Account ID.[/red]")
        return

    console.print(f"[cyan]Fetching Report named '{name}' for Account ID: {account_id}[/cyan]")

    try:
        report_instance = Report.get_by_name(name=name, account_id=account_id, client=client)

        if not report_instance:
            console.print(f"[yellow]Report named '{name}' not found for account {account_id}.[/yellow]")
            return

        # Display the report details
        # Format dates nicely
        created_at_str = report_instance.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC") if report_instance.createdAt else 'N/A'
        updated_at_str = report_instance.updatedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if report_instance.updatedAt else 'N/A'
        started_at_str = report_instance.startedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if report_instance.startedAt else 'N/A'
        completed_at_str = report_instance.completedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if report_instance.completedAt else 'N/A'

        # Pretty print dicts/JSON fields
        params_str = pretty_repr(report_instance.parameters)
        # data_str = pretty_repr(report_instance.reportData) # OLD

        content = (
            f"[bold]ID:[/bold] {report_instance.id}\n"
            f"[bold]Name:[/bold] {report_instance.name}\n"
            f"[bold]Account ID:[/bold] {report_instance.accountId}\n"
            f"[bold]Configuration ID:[/bold] {report_instance.reportConfigurationId}\n"
            f"[bold]Status:[/bold] {report_instance.status}\n"
            f"[bold]Created At:[/bold] {created_at_str}\n"
            f"[bold]Updated At:[/bold] {updated_at_str}\n"
            f"[bold]Started At:[/bold] {started_at_str}\n"
            f"[bold]Completed At:[/bold] {completed_at_str}\n"
            f"[bold]Parameters:[/bold]\n{params_str}\n"
            f"[bold]Output:[/bold] (See full data with --show-data option - TBD)\n" # Changed from Report Data to Output
            # f"[bold]Output:[/bold]\n{report_instance.output}\n" # Option to show full data
            f"[bold]Error Message:[/bold] {report_instance.errorMessage or 'None'}\n"
            f"[bold]Error Details:[/bold] {report_instance.errorDetails or 'None'}"
        )

        console.print(Panel(content, title=f"Report Details: {report_instance.name}", border_style="blue"))

    except Exception as e:
        console.print(f"[bold red]Error retrieving report '{name}': {e}[/bold red]")
        logger.error(f"Failed to get report '{name}': {e}\n{traceback.format_exc()}")

@report.command()
@click.option('--config', 'config_identifier', required=True, help='ID or name of the ReportConfiguration to use.')
@click.argument('params', nargs=-1)
def run(config_identifier: str, params: Tuple[str]):
    """
    Generate a new report instance from a ReportConfiguration.

    PARAMS should be key=value pairs to override or supplement configuration parameters.
    Example: plexus report run --config my_analysis start_date=2023-01-01 end_date=2023-12-31
    """
    try:
        # Parse key-value parameters
        parameters = parse_kv_pairs(params)
        console.print(f"Attempting to generate report from configuration: [cyan]'{config_identifier}'[/cyan] with parameters: {parameters}")

        # Call the generation service
        # The service now handles client creation, DB interactions, status updates, etc.
        report_instance = generate_report(config_identifier=config_identifier, params=parameters)

        if report_instance:
            console.print(f"[green]Report generation process initiated successfully.[/green]")
            console.print(f"Report Name: [magenta]{report_instance.name}[/magenta]")
            console.print(f"Report ID:   [magenta]{report_instance.id}[/magenta]")
            console.print(f"Initial Status: [yellow]{report_instance.status}[/yellow]")
            console.print(f"Monitor status using 'plexus report get --name \"{report_instance.name}\"' or 'plexus tasks list'.")
        else:
            # This case might occur if generate_report decides not to proceed (e.g., config not found)
            # but doesn't raise an exception handled below.
            console.print(f"[yellow]Report generation did not proceed. Check logs or configuration '{config_identifier}'.[/yellow]")

    except ValueError as e:
        # Specifically catch errors from parse_kv_pairs
        console.print(f"[bold red]Error parsing parameters:[/bold red] {e}")
    except FileNotFoundError as e:
         # Catch errors if the configuration is not found by the service
        console.print(f"[bold red]Error:[/bold red] {e}")
    except Exception as e:
        # Catch potential errors from the generate_report service call
        console.print(f"[bold red]An error occurred during report generation initiation:[/bold red]")
        console.print(f"{type(e).__name__}: {e}")
        logger.error(f"CLI trigger failed for report generation: {e}\n{traceback.format_exc()}")
        console.print("Check service logs for more details.")
        # Potentially exit with non-zero status
        # sys.exit(1)

# Add other report-related commands as needed (e.g., create-config, delete-config, delete-report) 