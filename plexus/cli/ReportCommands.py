"""
Command module for Plexus report generation commands.
"""

import click
import logging
import json
import traceback
from datetime import datetime, timezone
from typing import Optional
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
@click.option('--config', 'config_id', required=True, help='ID of the ReportConfiguration to run.')
@click.option('--params', 'params_json', help='JSON string of parameters to override/supplement the configuration.', default=None)
@click.option('--name', help='Optional name for this specific report run.', default=None)
def run(config_id: str, params_json: Optional[str], name: Optional[str]):
    """Generate a report instance from a ReportConfiguration."""
    client = create_client()
    console.print(f"[cyan]Starting report generation for configuration ID: {config_id}[/cyan]")

    run_params = {}
    if params_json:
        try:
            run_params = json.loads(params_json)
            console.print(f"[cyan]Using provided parameters: {run_params}[/cyan]")
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing --params JSON: {e}[/red]")
            return

    report_instance = None
    try:
        # Resolve the account ID from context/env var *first*
        resolved_account_id = client._resolve_account_id()
        if not resolved_account_id:
            # This should ideally not happen if create_client sets context correctly
            console.print("[red]Error: Could not resolve default account ID. Is PLEXUS_ACCOUNT_KEY set?[/red]")
            return
        console.print(f"[cyan]Using resolved Account ID: {resolved_account_id}[/cyan]")

        # 1. Fetch the Report Configuration
        console.print(f"Fetching report configuration '{config_id}'...")
        report_config = ReportConfiguration.get_by_id(config_id, client)
        console.print(f"[green]Successfully fetched configuration: {report_config.name}[/green]")

        # Determine report name
        report_name = name or f"{report_config.name} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"

        # 2. Create Initial Report Record using the *resolved* account ID
        console.print(f"Creating initial report record '{report_name}'...")
        report_instance = Report.create(
            client=client,
            reportConfigurationId=report_config.id,
            accountId=resolved_account_id,      # USE the resolved account ID
            name=report_name,
            parameters=run_params, # Store the effective parameters for this run
            status='PENDING'
        )
        console.print(f"[green]Created report record with ID: {report_instance.id}, Status: PENDING[/green]")

        # 3. Mark as RUNNING and record start time
        start_time = datetime.now(timezone.utc)
        report_instance.update(status='RUNNING', startedAt=start_time)
        console.print(f"[cyan]Report status updated to RUNNING at {start_time}[/cyan]")

        # 4. Generate Report Data using the service
        console.print("Generating report data...")
        
        # Convert ReportConfiguration object to a dict to pass to service
        # Ensure all necessary fields used by generate_report are included
        config_data_dict = asdict(report_config)
        
        # generated_data = generate_report(report_config_data=config_data_dict, params=run_params) # OLD list
        # generated_markdown: str = generate_report(report_config_data=config_data_dict, params=run_params) # Erroring call
        generated_markdown: str = generate_report(report_configuration_id=config_id, params=run_params) # Pass ID
        
        # Check for errors within the generated data
        # # Check 1: Top-level errors (e.g., parsing, block instantiation)
        # top_level_errors = [item for item in generated_data if item.get("type") == "error"]
        # # Check 2: Errors returned *within* successful block results
        # nested_errors = []
        # for item in generated_data:
        #     if item.get("type") == "block_result" and isinstance(item.get("data"), dict) and "error" in item["data"]:
        #         # Extract the error message from the nested data dictionary
        #         nested_error_message = item["data"]["error"]
        #         # Associate it with the block type if possible
        #         block_type = item.get("block_type", "Unknown Block")
        #         nested_errors.append({
        #             "type": "error", # Standardize structure
        #             "message": f"Block '{block_type}': {nested_error_message}"
        #         })

        # all_internal_errors = top_level_errors + nested_errors
        # has_internal_errors = bool(all_internal_errors)

        # NEW Error Check: Look for error markers in the generated markdown string
        error_marker = "<!-- Error:"
        has_internal_errors = error_marker in generated_markdown

        if has_internal_errors:
            console.print("[bold yellow]Warning: Report generation completed, but some blocks encountered errors.[/bold yellow]")
            # Extract and print error messages from markers
            error_messages = []
            start_idx = 0
            while True:
                err_start = generated_markdown.find(error_marker, start_idx)
                if err_start == -1:
                    break
                err_end = generated_markdown.find("-->", err_start)
                if err_end == -1:
                     # Malformed marker, stop searching here
                     error_messages.append("[Malformed Error Marker Found]")
                     break 
                error_msg = generated_markdown[err_start + len(error_marker):err_end].strip()
                console.print(f"  - [red]Error:[/red] {error_msg}")
                error_messages.append(error_msg)
                start_idx = err_end + 3 # Move past the marker
            
            # 5. Update Report with FAILED status and partial data
            completion_time = datetime.now(timezone.utc)
            # Extract the first error message for the main errorMessage field
            # first_error_msg = all_internal_errors[0].get("message", "Block generation failed")
            first_error_msg = error_messages[0] if error_messages else "Block generation failed"
            
            report_instance.update(
                status='FAILED',
                # reportData=generated_data, # OLD: List
                # reportData=generated_markdown, # NEW: String - Temporarily disabled
                completedAt=completion_time,
                errorMessage=f"Block execution failed: {first_error_msg}",
                # Store structured errors in details
                # errorDetails=json.dumps([err.get("message") for err in all_internal_errors]) # OLD
                errorDetails=json.dumps(error_messages) # NEW: Store extracted messages
            )
            console.print(f"[bold yellow]Report {report_instance.id} completed with errors at {completion_time}. Status set to FAILED.[/bold yellow]")
            sys.exit(1) # Exit with non-zero code to indicate failure
            
        else:
            # Original success path
            console.print("[green]Report data generated successfully.[/green]")
            
            # 5. Update Report with Results
            completion_time = datetime.now(timezone.utc)
            report_instance.update(
                status='COMPLETED',
                # reportData=generated_data, # OLD: List
                output=generated_markdown, # NEW: String
                completedAt=completion_time
            )
            console.print(f"[bold green]Report {report_instance.id} completed successfully at {completion_time}![/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error during report generation process: {e}[/bold red]")
        detailed_error = traceback.format_exc()
        logger.error(f"Report Generation Failed: {e}\n{detailed_error}")
        console.print(f"[yellow]Error details:\n{detailed_error}[/yellow]")

        if report_instance:
            try:
                # Update status to FAILED
                completion_time = datetime.now(timezone.utc)
                # Simplify error details sent to GraphQL to avoid validation errors
                simple_error_message = str(e)
                # Truncate if necessary to fit potential DB limits
                # max_len = 1000 # Example max length, adjust if needed
                # truncated_error_details = (simple_error_message[:max_len] + '...') if len(simple_error_message) > max_len else simple_error_message
                # Use truncated traceback for details instead
                detailed_traceback = traceback.format_exc()
                max_len_traceback = 1000 # Keep this relatively small
                truncated_traceback = (detailed_traceback[:max_len_traceback] + '...') if len(detailed_traceback) > max_len_traceback else detailed_traceback

                report_instance.update(
                    status='FAILED',
                    errorMessage=simple_error_message, # Use the simple message
                    # errorDetails=truncated_error_details, # Use truncated message for details too # OLD
                    errorDetails=truncated_traceback, # NEW: Use truncated traceback
                    completedAt=completion_time
                )
                console.print(f"[red]Report {report_instance.id} status updated to FAILED.[/red]")
            except Exception as update_e:
                console.print(f"[bold red]CRITICAL: Failed to update report status to FAILED: {update_e}[/bold red]")
                logger.error(f"Failed to update report {report_instance.id} to FAILED status: {update_e}\n{traceback.format_exc()}")
        else:
            console.print("[red]Failed before report record could be created or updated.[/red]") 