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
import os # Added for file operations
from pathlib import Path # Added for path handling

from plexus.cli.console import console
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.cli.client_utils import create_client
from plexus.dashboard.api.models.report_configuration import ReportConfiguration
from plexus.dashboard.api.models.report import Report
from plexus.dashboard.api.models.task import Task
from plexus.tasks.reports import generate_report_task
from rich.table import Table # Import Table for display
from rich.panel import Panel
from rich.pretty import pretty_repr
from rich.syntax import Syntax # Added for JSON highlighting
from dataclasses import asdict
import uuid # Added for UUID validation
from gql.transport.exceptions import TransportQueryError # Added import
from gql import gql # Added import for gql function
from rich.markup import escape # Added escape import

# Import the refactored service function and tracker
from plexus.reports.service import _generate_report_core
from plexus.cli.task_progress_tracker import TaskProgressTracker, StageConfig # Restore full import

from plexus.cli.utils import parse_kv_pairs # Assume this exists

# Import Account model for resolving ID
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.report_block import ReportBlock # Added for fetching blocks

logger = logging.getLogger(__name__)

@click.group()
def report():
    """Commands for managing and running reports."""
    # Diagnostic print
    # print("--- Report command group loaded ---", file=sys.stderr) # Removed diagnostic print
    pass

# Define the 'config' subgroup
@click.group()
def config():
    """Manage report configurations."""
    pass

# Add the 'config' subgroup to the 'report' group
report.add_command(config)

# Define the 'block' subgroup
@click.group()
def block():
    """Manage report blocks within a specific report."""
    pass

# Add the 'block' subgroup to the 'report' group
report.add_command(block)

@config.command(name="list") # Changed from @report.command to @config.command
@click.option('--account', 'account_identifier', help='Optional account key or ID to filter by.', default=None)
@click.option('--limit', type=int, default=50, help='Maximum number of configurations to list.')
def list_configs(account_identifier: Optional[str], limit: int): # Renamed function
    """List available Report Configurations for an account."""
    client = create_client()
    account_id = None
    account_display_name = "default account"

    if account_identifier:
        account_display_name = f"identifier '{account_identifier}'"
        # User provided an identifier - try resolving by key first, then ID
        try:
            console.print(f"[dim]Attempting to resolve account by key: {account_identifier}...[/dim]")
            account_obj = Account.get_by_key(key=account_identifier, client=client)
            if account_obj:
                account_id = account_obj.id
                console.print(f"[dim]Resolved account ID by key: {account_id}[/dim]")
            else:
                console.print(f"[dim]Account key '{account_identifier}' not found. Trying as ID...[/dim]")
                try:
                    # Fallback: Try treating it as an ID
                    account_obj_by_id = Account.get_by_id(account_identifier, client)
                    if account_obj_by_id:
                        account_id = account_obj_by_id.id
                        console.print(f"[dim]Resolved account ID directly: {account_id}[/dim]")
                    else:
                         # Should be caught by get_by_id exception, but handle just in case
                         console.print(f"[red]Error: Could not resolve account identifier '{account_identifier}' as ID.[/red]")
                         raise click.Abort()
                except Exception as id_e:
                    console.print(f"[red]Error: Could not resolve account identifier '{account_identifier}' as key or ID: {id_e}[/red]")
                    raise click.Abort()
        except Exception as key_e:
            # Error during get_by_key, maybe transient or invalid key format?
            # Still attempt fallback to ID lookup
            console.print(f"[yellow]Warning: Error during key lookup for '{account_identifier}' ({key_e}). Trying as ID...[/yellow]")
            try:
                 account_obj_by_id = Account.get_by_id(account_identifier, client)
                 if account_obj_by_id:
                     account_id = account_obj_by_id.id
                     console.print(f"[dim]Resolved account ID directly after key lookup error: {account_id}[/dim]")
                 else:
                     console.print(f"[red]Error: Could not resolve '{account_identifier}' as ID after key lookup error.[/red]")
                     raise click.Abort()
            except Exception as final_id_e:
                console.print(f"[red]Error: Failed to resolve '{account_identifier}' as key or ID. Key Error: {key_e}, ID Error: {final_id_e}[/red]")
                raise click.Abort()
    else:
        # No identifier provided, use client's internal resolution (uses context/env var)
        account_display_name = "default account (from environment)"
        console.print(f"[dim]Attempting to resolve default account from environment...[/dim]")
        try:
            account_id = client._resolve_account_id() # Correct method call for default
            if account_id:
                 console.print(f"[dim]Resolved default account ID: {account_id}[/dim]")
            else:
                # This case might not be reachable if _resolve_account_id raises error on failure
                console.print(f"[red]Error: client._resolve_account_id() returned None. Is PLEXUS_ACCOUNT_KEY set and valid?[/red]")
                raise click.Abort()
        except Exception as e:
             console.print(f"[red]Error resolving default account: {e}. Is PLEXUS_ACCOUNT_KEY set and valid?[/red]")
             raise click.Abort()

    # Final check
    if not account_id:
        console.print(f"[red]Error: Could not determine Account ID for {account_display_name}.[/red]")
        raise click.Abort()

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

        # --- Display results using Panels instead of Table ---
        console.print(f"[bold]Found {len(items)} Report Configuration(s) for Account: {account_id}[/bold]")
        for config_instance in items:
            # Format datetimes
            created_at_str = config_instance.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC") if config_instance.createdAt else 'N/A'
            updated_at_str = config_instance.updatedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if config_instance.updatedAt else 'N/A'

            # Build panel content string (Name first)
            panel_content = (
                f"[bold magenta]Name:[/bold magenta]        {config_instance.name}\n"
                f"[bold cyan]ID:[/bold cyan]          {config_instance.id}\n"
                f"[bold green]Description:[/bold green] {config_instance.description or '-'}\n"
                f"[bold blue]Created At:[/bold blue]  {created_at_str}\n"
                f"[bold blue]Updated At:[/bold blue]  {updated_at_str}"
            )

            # Create and print the panel with updated title
            console.print(
                Panel(
                    panel_content,
                    title="[bold]Report Configuration[/bold]", # Updated title to be static
                    border_style="blue",
                    expand=True # Don't expand panel width unnecessarily
                )
            )
        # --- End Panel Display ---

    except Exception as e:
        console.print(f"[bold red]Error listing report configurations: {e}[/bold red]")
        logger.error(f"Failed to list report configurations: {e}\n{traceback.format_exc()}")

@report.command()
@click.option('--config', 'config_identifier', required=True, help='ID or name of the ReportConfiguration to use.')
@click.argument('params', nargs=-1)
def run(config_identifier: str, params: Tuple[str]):
    """
    Generate a new report instance from a ReportConfiguration synchronously.

    PARAMS should be key=value pairs to override or supplement configuration parameters.
    Example: plexus report run --config my_analysis start_date=2023-01-01 end_date=2023-12-31
    """
    client = create_client() # Instantiate client
    tracker = None # Initialize tracker variable
    task_id = None # Initialize task_id variable

    try:
        # --- Step 1: Parse Parameters & Resolve Account ---
        run_parameters = parse_kv_pairs(params)
        console.print(f"Attempting to run report from configuration: [cyan]'{config_identifier}'[/cyan] with parameters: {run_parameters}")

        # Resolve account ID first (needed for config lookup by name)
        try:
            account_id = client._resolve_account_id()
            if not account_id:
                 raise RuntimeError("Could not resolve default account ID. Is PLEXUS_ACCOUNT_KEY set?")
            console.print(f"[dim]Using Account ID: {account_id}[/dim]")
        except Exception as e:
            console.print(f"[red]Error resolving account: {e}[/red]")
            raise click.Abort()

        # --- Step 2: Resolve Report Configuration ---
        console.print(f"Resolving Report Configuration: [cyan]'{config_identifier}'[/cyan]...")
        report_config = _resolve_report_config(config_identifier, account_id, client)
        if not report_config:
            console.print(f"[red]Error: Report Configuration '{config_identifier}' not found for account {account_id}.[/red]")
            raise click.Abort()
        resolved_config_id = report_config.id
        console.print(f"Resolved to Configuration ID: [cyan]{resolved_config_id}[/cyan] (Name: {report_config.name})")

        # --- Step 3: Create Task Record ---
        console.print(f"Creating Task record for synchronous run...")
        task_metadata = {
            "report_configuration_id": resolved_config_id,
            "report_parameters": run_parameters,
            "account_id": account_id, # Include account ID in metadata
            "trigger": "cli_sync" # Indicate synchronous trigger
        }
        metadata_json = json.dumps(task_metadata)
        task_description = f"Synchronously generate report from config '{report_config.name}' ({resolved_config_id})"

        new_task = Task.create(
            client=client,
            accountId=account_id, # Explicitly set account ID
            type="report_generation",
            target=resolved_config_id,
            command="plexus report run (sync)",
            description=task_description,
            metadata=metadata_json,
            dispatchStatus="SYNC", # Indicate synchronous execution
            status="PENDING" # Initial status, will be updated by tracker
        )
        task_id = new_task.id # Store task_id for potential error reporting
        console.print(f"Created Task: [cyan]{task_id}[/cyan]")

        # --- Step 4: Initialize Task Progress Tracker ---
        console.print(f"Initializing progress tracker for Task [cyan]{task_id}[/cyan]...")
        # Define stages consistent with the service
        stage_configs = {
            "Loading Configuration": StageConfig(order=1, status_message="Loading report configuration details."),
            "Initializing Report Record": StageConfig(order=2, status_message="Creating initial database entry for the report."),
            "Parsing Configuration": StageConfig(order=3, status_message="Analyzing report structure and block definitions."),
            "Processing Report Blocks": StageConfig(order=4, status_message="Executing individual report block components.", total_items=0), # total_items set dynamically in core
            "Finalizing Report": StageConfig(order=5, status_message="Saving results and completing generation."),
        }
        # Use the correct initialization based on the class definition, passing the task object
        tracker = TaskProgressTracker(
            # task_id=task_id,              # Provide the existing task ID (alternative)
            task_object=new_task,         # Pass the created Task object directly
            stage_configs=stage_configs,  # Provide the stage definitions
            total_items=0,                # Provide a default total_items (can be updated by set_total_items later)
            prevent_new_task=True,        # Explicitly prevent creating another task
            client=client                 # Pass the existing client instance
        )
        console.print("Tracker initialized.")

        # --- Step 5: Execute Report Generation Synchronously ---
        console.print(f"Executing report generation synchronously for Task [cyan]{task_id}[/cyan]...")
        log_prefix = f"[ReportGenCLI task_id={task_id}]" # Custom log prefix for CLI context

        report_id = _generate_report_core(
            report_config_id=resolved_config_id,
            account_id=account_id,
            run_parameters=run_parameters,
            client=client,
            tracker=tracker, # Pass the initialized tracker
            log_prefix_override=log_prefix # Pass custom log prefix
        )

        # --- Step 6: Mark Task as Completed ---
        console.print(f"[green]Report generation successful![/green]")
        console.print(f"  Report ID: [magenta]{report_id}[/magenta]")
        console.print(f"  Task ID:   [cyan]{task_id}[/cyan]")
        tracker.complete()
        console.print(f"Task [cyan]{task_id}[/cyan] marked as COMPLETED.")

    except ValueError as e:
        # Specifically catch errors from parse_kv_pairs
        console.print(f"[bold red]Error parsing parameters:[/bold red] {e}")
        # No task created yet, just abort.
        raise click.Abort()
    except click.Abort:
         # Handle Abort exceptions raised previously (e.g., config not found)
         console.print("[yellow]Aborting report run.[/yellow]")
         # Attempt to mark task FAILED if it was created before aborting
         if tracker:
             try:
                 tracker.fail("Report run aborted by user or prerequisite failure.")
                 console.print(f"[yellow]Task {task_id} marked as FAILED due to abort.[/yellow]")
             except Exception as tracker_err:
                 console.print(f"[red]Error marking task {task_id} as FAILED after abort: {tracker_err}[/red]")
         elif task_id: # Task created but tracker failed? Less likely
              try:
                 task = Task.get_by_id(task_id, client)
                 if task:
                     task.update(status="FAILED", errorMessage="Report run aborted before tracker initialization.", completedAt=datetime.now(timezone.utc).isoformat())
                     console.print(f"[yellow]Task {task_id} marked as FAILED via direct update due to abort.[/yellow]")
              except Exception as update_err:
                 console.print(f"[red]Error marking task {task_id} as FAILED via direct update after abort: {update_err}[/red]")
         # Let click handle the exit
    except Exception as e:
        # Catch potential errors during Task creation or _generate_report_core execution
        error_msg = f"An error occurred during synchronous report generation"
        detailed_error = traceback.format_exc()
        console.print(f"[bold red]{error_msg}:[/bold red]")
        console.print(f"{type(e).__name__}: {e}")
        logger.error(f"CLI synchronous report run failed for Task {task_id or 'N/A'}: {e}\n{detailed_error}")

        if tracker:
            # If tracker exists, use it to mark the task as failed
            try:
                tracker.fail(f"{error_msg}: {e}\nDetails:\n{detailed_error}")
                console.print(f"[red]Task {task_id} marked as FAILED via tracker.[/red]")
            except Exception as tracker_fail_err:
                console.print(f"[red]Error marking task {task_id} as FAILED via tracker after primary error: {tracker_fail_err}[/red]")
                # Fallback? Direct update might be risky if tracker failed badly.
        elif task_id:
            # If task was created but tracker failed or error occurred before tracker init
             try:
                 task = Task.get_by_id(task_id, client)
                 if task:
                     task.update(status="FAILED", errorMessage=f"{error_msg}: {e}", errorDetails=detailed_error, completedAt=datetime.now(timezone.utc).isoformat())
                     console.print(f"[red]Task {task_id} marked as FAILED via direct update.[/red]")
             except Exception as final_update_err:
                 console.print(f"[red]CRITICAL: Failed to mark task {task_id} as FAILED via any method after error: {final_update_err}[/red]")
        else:
            console.print("[red]No Task ID available to mark as failed.[/red]")

        # Exit with non-zero status
        sys.exit(1)

@config.command(name="create")
@click.option('--name', required=True, help='Name for the new Report Configuration.')
@click.option('--description', default="", help='Optional description.')
@click.option('--account', 'account_identifier', default=None, help='Account key or ID to associate with. Defaults to PLEXUS_ACCOUNT_KEY.')
@click.option('--file', 'config_file_path', type=click.Path(exists=True, dir_okay=False, readable=True), required=True, help='Path to the Markdown file containing the report configuration content.')
def create_config(name: str, description: str, account_identifier: Optional[str], config_file_path: str):
    """Create a new Report Configuration from a Markdown file."""
    client = create_client()
    account_id = None

    # --- Account Resolution Logic (copied from list_configs for brevity) ---
    # Resolve account ID (use the same robust logic as in list_configs)
    if account_identifier:
        try:
            account_obj = Account.get_by_key(key=account_identifier, client=client)
            if account_obj:
                account_id = account_obj.id
            else: # Try ID
                account_obj_by_id = Account.get_by_id(account_identifier, client)
                if account_obj_by_id: account_id = account_obj_by_id.id
                # If still no account_id after trying both key and ID
                elif not account_id:
                     console.print(f"[red]Error: Could not resolve account identifier '{account_identifier}' as key or ID.[/red]")
                     raise click.Abort()
        except Exception as e:
             console.print(f"[red]Error resolving account identifier '{account_identifier}': {e}[/red]")
             raise click.Abort() # Use Abort
    else:
        try:
            account_id = client._resolve_account_id()
        except Exception as e:
            console.print(f"[red]Error resolving default account: {e}. Is PLEXUS_ACCOUNT_KEY set?[/red]")
            raise click.Abort() # Use Abort

    if not account_id:
        console.print("[red]Error: Could not determine Account ID.[/red]")
        raise click.Abort() # Use Abort
    # --- End Account Resolution ---

    console.print(f"[cyan]Creating Report Configuration \'{name}\' for Account ID: {account_id}...[/cyan]")

    try:
        # Read the configuration content from the file
        with open(config_file_path, 'r', encoding='utf-8') as f:
            configuration_content = f.read()

        # Validate if the content is not empty (basic check)
        if not configuration_content.strip():
             console.print(f"[red]Error: Configuration file \'{config_file_path}\' is empty.[/red]")
             raise click.Abort()

        # --- Check for Duplicates ---
        console.print(f"[dim]Checking for existing configurations named \'{name}\' in account {account_id}...[/dim]")
        existing_config = None
        try:
            # Use get_by_name which should return one or None if name is unique per account
            # If names aren't unique, this needs adjustment to list_by_name or similar
            existing_config = ReportConfiguration.get_by_name(name=name, account_id=account_id, client=client)
        except Exception as e:
            # Log the error but proceed, assuming no duplicate if lookup fails
            logger.warning(f"Failed to check for existing configuration named \'{name}\': {e}")
            # Optionally, inform the user about the failed check?
            # console.print(f"[yellow]Warning: Could not check for existing configurations due to an error: {e}[/yellow]")

        if existing_config:
            console.print(f"[yellow]Found existing configuration with the same name:[/yellow]")
            console.print(f"  ID: {existing_config.id}")
            console.print(f"  Name: {existing_config.name}")
            
            # Compare content (assuming existing_config.configuration holds the content)
            if hasattr(existing_config, 'configuration') and existing_config.configuration == configuration_content:
                console.print(f"[bold yellow]Warning: An existing configuration with the name '{name}' and identical content already exists.[/bold yellow]")
                if not click.confirm("Do you want to proceed and create a duplicate configuration?", default=False):
                    console.print("[cyan]Operation cancelled by user.[/cyan]")
                    raise click.Abort() # Use Abort for user cancellation
            else:
                console.print(f"[bold yellow]Warning: An existing configuration with the name '{name}' but different content already exists.[/bold yellow]")
                if not click.confirm("Do you want to proceed and create a new configuration with this name?", default=False):
                    console.print("[cyan]Operation cancelled by user.[/cyan]")
                    raise click.Abort() # Use Abort for user cancellation
        else:
             console.print(f"[dim]No existing configuration found with the name '{name}'. Proceeding...[/dim]")
        # --- End Duplicate Check ---


        # --- Example Block Parsing (Placeholder/Illustrative) ---
        # You might want basic validation or parsing here depending on requirements
        # For now, we store the raw Markdown content.
        # If JSON storage is preferred, you'd parse/validate here.
        # Example: try parsing blocks, though we don't use --block-class/-param anymore
        # parsed_blocks = parse_markdown_blocks(configuration_content) # Fictional function
        # if not parsed_blocks:
        #    console.print("[yellow]Warning: No report blocks found in the configuration file.[/yellow]")
        # --- End Example Parsing ---

        # Create the ReportConfiguration instance using the API client or model method
        # Assume ReportConfiguration.create() exists and takes these parameters
        new_config = ReportConfiguration.create(
            client=client,
            accountId=account_id,  # Corrected keyword argument case
            name=name,
            description=description,
            configuration=configuration_content # Use file content here
        )

        if new_config:
            # Escape potentially problematic values before printing with Rich
            escaped_id = escape(str(new_config.id))
            escaped_name = escape(str(new_config.name))
            escaped_account_id = escape(str(new_config.accountId))
            
            # Simplified markup
            console.print(f"[bold]Successfully created Report Configuration:[/bold]")
            console.print(f"  ID: {escaped_id}")
            console.print(f"  Name: {escaped_name}")
            console.print(f"  Account ID: {escaped_account_id}")
        else:
            # Handle case where creation method returns None or raises an expected error
            console.print(f"[red]Error: Failed to create report configuration \'{name}\'. API returned no object.[/red]")

    except FileNotFoundError:
         console.print(f"[red]Error: Configuration file not found at path: {config_file_path}[/red]")
    except IOError as e:
         console.print(f"[red]Error reading configuration file \'{config_file_path}\': {e}[/red]")
    except click.Abort: # Explicitly handle/re-raise Abort
        raise # Re-raise the abort to let Click handle it
    except Exception as e:
        # Escape the error message to prevent Rich parsing issues
        escaped_error = escape(str(e))
        console.print(f"[bold red]Error creating report configuration: {escaped_error}[/bold red]")
        logger.error(f"Failed to create report configuration \'{name}\': {e}\\n{traceback.format_exc()}")

# --- Helper function for ID/Name resolution (Copied from show_config) ---
def _resolve_report_config(identifier: str, account_id: str, client: PlexusDashboardClient) -> Optional[ReportConfiguration]:
    """Attempts to resolve a ReportConfiguration by ID first, then by name within the account."""
    config = None
    is_uuid = False
    try:
        uuid.UUID(identifier)
        is_uuid = True
    except ValueError:
        pass # Not a UUID

    if is_uuid:
        console.print(f"[dim]Attempting to resolve Report Configuration by ID: {identifier}...[/dim]")
        try:
            config = ReportConfiguration.get_by_id(identifier, client)
            if config:
                 console.print(f"[dim]Resolved by ID.[/dim]")
                 return config # Found by ID
            else:
                 console.print(f"[dim]ID \'{identifier}\' not found. Trying as name...[/dim]")
        except Exception as id_e:
            console.print(f"[yellow]Warning: Error during ID lookup for \'{identifier}\' ({id_e}). Trying as name...[/yellow]")
            # Fall through to name lookup even if ID lookup fails unexpectedly

    # Try resolving by name (either because it wasn't a UUID or ID lookup failed)
    if not config: # Only try name if ID lookup didn't succeed
        console.print(f"[dim]Attempting to resolve Report Configuration by name: \'{identifier}\' in account {account_id}...[/dim]")
        try:
            config = ReportConfiguration.get_by_name(name=identifier, account_id=account_id, client=client)
            if config:
                console.print(f"[dim]Resolved by name.[/dim]")
                return config # Found by name
            else:
                console.print(f"[dim]Name \'{identifier}\' not found in account {account_id}.[/dim]")
                return None # Not found by name either
        except Exception as name_e:
            console.print(f"[red]Error during name lookup for \'{identifier}\': {name_e}[/red]")
            return None # Error during name lookup

    # This part should technically not be reached if logic above is sound
    return config # Return whatever was found, or None

@config.command(name="show")
@click.argument('id_or_name', type=str)
@click.option('--account', 'account_identifier', help='Optional account key or ID for context (needed for name lookup).', default=None)
def show_config(id_or_name: str, account_identifier: Optional[str]):
    """Display details of a specific Report Configuration."""
    client = create_client()
    resolved_account_id = account_identifier # Placeholder, need actual resolution logic if name lookup needed

    # If account_identifier is provided, resolve it. Otherwise, use default client context.
    acc_id_for_lookup = None
    account_display_name = "default account (from environment)"
    if account_identifier:
        account_display_name = f"identifier '{account_identifier}'"
        # Resolve the provided identifier
        try:
            acc_obj = Account.get_by_key_or_id(account_identifier, client)
            if acc_obj:
                acc_id_for_lookup = acc_obj.id
            else:
                console.print(f"[red]Error: Could not resolve account identifier '{account_identifier}'.[/red]")
                raise click.Abort()
        except Exception as e:
            console.print(f"[red]Error resolving account '{account_identifier}': {e}[/red]")
            raise click.Abort()
    else:
        # Use default account ID from client
        try:
            acc_id_for_lookup = client._resolve_account_id()
            if not acc_id_for_lookup:
                raise RuntimeError("Could not resolve default account ID.")
        except Exception as e:
             console.print(f"[red]Error resolving default account: {e}. Is PLEXUS_ACCOUNT_KEY set?[/red]")
             raise click.Abort()

    console.print(f"Showing Report Configuration '{id_or_name}' for account: [cyan]{acc_id_for_lookup}[/cyan] ({account_display_name})")

    try:
        # Use the helper function to resolve by ID or Name
        config_instance = _resolve_report_config(id_or_name, acc_id_for_lookup, client)

        if not config_instance:
            console.print(f"[yellow]Report Configuration '{id_or_name}' not found for account {acc_id_for_lookup}.[/yellow]")
            return

        # --- Display using Panel ---
        created_at_str = config_instance.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC") if config_instance.createdAt else 'N/A'
        updated_at_str = config_instance.updatedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if config_instance.updatedAt else 'N/A'

        panel_content = (
            f"[bold magenta]Name:[/bold magenta]        {escape(config_instance.name)}\\n"
            f"[bold cyan]ID:[/bold cyan]          {config_instance.id}\\n"
            f"[bold green]Description:[/bold green] {escape(config_instance.description or '-')}\\n"
            f"[bold blue]Created At:[/bold blue]  {created_at_str}\\n"
            f"[bold blue]Updated At:[/bold blue]  {updated_at_str}\\n\\n"
            f"[bold yellow]Configuration Content:[/bold yellow]"
        )

        console.print(
            Panel(
                panel_content,
                title=f"[bold]Report Configuration Details[/bold]",
                border_style="blue",
                expand=True
            )
        )

        # Display configuration content with Markdown syntax highlighting
        if config_instance.configuration:
             syntax = Syntax(config_instance.configuration, "markdown", theme="default", line_numbers=True)
             console.print(syntax)
        else:
            console.print("[dim]Configuration content is empty.[/dim]")
        # --- End Panel Display ---


    except Exception as e:
        console.print(f"[bold red]Error retrieving report configuration '{id_or_name}': {e}[/bold red]")
        logger.error(f"Failed to show report configuration: {e}\\n{traceback.format_exc()}")


# -------------------
# config delete command
# -------------------
@config.command(name="delete")
@click.argument('id_or_name', type=str)
@click.option('--account', 'account_identifier', default=None, help='Account key or ID context (needed for name lookup). Defaults to PLEXUS_ACCOUNT_KEY.')
@click.option('--yes', is_flag=True, callback=lambda ctx, param, value: console.print("[yellow]Skipping confirmation prompt due to --yes flag.[/yellow]") if value else None, expose_value=True, help='Skip confirmation prompt.')
def delete_config(id_or_name: str, account_identifier: Optional[str], yes: bool):
    """Delete a Report Configuration by its ID or name."""
    client = create_client()
    account_id = None

    # Resolve account ID (reuse logic from list_configs/create_config)
    if account_identifier:
        try:
            account_obj = Account.get_by_key(key=account_identifier, client=client)
            if account_obj: account_id = account_obj.id
            else:
                account_obj_by_id = Account.get_by_id(account_identifier, client)
                if account_obj_by_id: account_id = account_obj_by_id.id
        except Exception as e:
            console.print(f"[red]Error resolving account identifier \'{account_identifier}\': {e}[/red]")
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

    console.print(f"[cyan]Attempting to delete Report Configuration \'{id_or_name}\' in Account ID: {account_id}...[/cyan]")

    # Resolve the configuration using the helper function
    config_to_delete = _resolve_report_config(id_or_name, account_id, client)

    if not config_to_delete:
        console.print(f"[red]Error: Report Configuration \'{id_or_name}\' not found.[/red]")
        return

    console.print(f"[yellow]Found Report Configuration:[/yellow]")
    console.print(f"  ID: {config_to_delete.id}")
    console.print(f"  Name: {config_to_delete.name}")

    # Confirmation prompt
    if not yes:
        if not click.confirm(f"Are you sure you want to delete Report Configuration '{config_to_delete.name}' (ID: {config_to_delete.id})?"):
            console.print("[cyan]Deletion aborted.[/cyan]")
            return

    # Proceed with deletion
    try:
        console.print(f"[dim]Sending delete request for ID: {config_to_delete.id}...[/dim]")

        # --- Define the GraphQL Mutation --- 
        mutation_string = """
            mutation DeleteReportConfiguration($input: DeleteReportConfigurationInput!) {
                deleteReportConfiguration(input: $input) {
                    id # Request the ID back to confirm deletion
                }
            }
        """

        # --- Define the Input Variables ---
        variables = {
            "input": {
                "id": config_to_delete.id
            }
        }

        # --- Execute the Mutation --- 
        # client.execute returns the result dict or raises TransportQueryError
        result = client.execute(mutation_string, variables=variables)
        
        # --- Check Result --- 
        # If execute didn't raise an error and we got here, deletion was likely successful.
        # We can optionally check the result structure.
        deleted_id = result.get('deleteReportConfiguration', {}).get('id')
        if deleted_id == config_to_delete.id:
             console.print(f"[bold green]Successfully deleted Report Configuration \'{config_to_delete.name}\' (ID: {config_to_delete.id}).[/bold green]")
        else:
             # This case might indicate a partial success or unexpected response format
             console.print(f"[yellow]Warning: Delete mutation executed but confirmation ID mismatch or missing in response. Response: {result}[/yellow]")
             # Consider treating this as success anyway if no error was raised
             console.print(f"[bold green](Assuming success) Deleted Report Configuration \'{config_to_delete.name}\' (ID: {config_to_delete.id}).[/bold green]")

    except TransportQueryError as e:
        # Handle GraphQL specific errors more gracefully
        error_message = "Unknown GraphQL error"
        if hasattr(e, 'errors') and e.errors:
             error_message = e.errors[0].get('message', str(e.errors[0]))
        console.print(f"[bold red]Error deleting report configuration (GraphQL Error): {error_message}[/bold red]")
        logger.error(f"Failed to delete report configuration ID \'{config_to_delete.id}\' via GraphQL: {e.errors if hasattr(e, 'errors') else e}")
    except Exception as e:
        # Catch other potential exceptions (network errors, etc.)
        console.print(f"[bold red]Error deleting report configuration: {e}[/bold red]")
        logger.error(f"Failed to delete report configuration ID \'{config_to_delete.id}\': {e}\\n{traceback.format_exc()}")

@report.command(name="list")
@click.option('--config', 'config_identifier', default=None, help='Filter reports by a specific configuration ID or name.')
@click.option('--account', 'account_identifier', help='Optional account key or ID to filter by.', default=None)
@click.option('--limit', type=int, default=50, help='Maximum number of reports to list.')
def list_reports(config_identifier: Optional[str], account_identifier: Optional[str], limit: int):
    """List generated Reports, optionally filtering by configuration."""
    client = create_client()
    account_id = None
    resolved_config_id = None

    # --- Account Resolution ---
    if account_identifier:
        try:
            account_id = client._resolve_account_id(account_key=account_identifier)
        except Exception as e:
            try:
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
    
    # --- Resolve Config Identifier if provided ---
    if config_identifier:
        console.print(f"[cyan]Resolving configuration filter: '{config_identifier}'...[/cyan]")
        config_instance = _resolve_report_config(config_identifier, account_id, client)
        if not config_instance:
            console.print(f"[yellow]Could not resolve Report Configuration '{config_identifier}' to filter by.[/yellow]")
            return
        resolved_config_id = config_instance.id
        console.print(f"[cyan]Filtering reports for Configuration ID: {resolved_config_id}[/cyan]")
    
    console.print(f"[cyan]Listing Reports for Account ID: {account_id}[/cyan]" + (f" (Config ID: {resolved_config_id})" if resolved_config_id else ""))

    try:
        # TODO: Update Report.list_by_account_id or create new method 
        # to support filtering by reportConfigurationId if resolved_config_id is not None.
        # For now, assume it fetches all and we filter client-side (inefficient).
        report_result_data = Report.list_by_account_id(
            account_id=account_id,
            client=client,
            limit=limit * 2 # Fetch more initially if filtering client-side
        )
        # The list_by_account_id method now returns a list directly
        reports = report_result_data 

        # --- Client-side filtering (replace with API filter later) ---
        if resolved_config_id:
             filtered_reports = [r for r in reports if hasattr(r, 'reportConfigurationId') and r.reportConfigurationId == resolved_config_id]
             reports = filtered_reports[:limit] # Apply limit after filtering
        else:
             reports = reports[:limit] # Apply limit directly
        # ---

        if not reports:
            filter_msg = f" for configuration '{config_identifier}'" if config_identifier else ""
            console.print(f"[yellow]No reports found for account {account_id}{filter_msg}.[/yellow]")
            return

        # --- Fetch associated Task statuses (inefficiently) ---
        # TODO: Optimize this - batch fetch tasks or include in report list API call
        task_statuses = {}
        report_task_ids = [r.taskId for r in reports if hasattr(r, 'taskId') and r.taskId]
        if report_task_ids:
            try:
                # Assuming a Task.batch_get_by_ids exists or similar
                # tasks_data = Task.batch_get_by_ids(task_ids=report_task_ids, client=client)
                # tasks = tasks_data.get('items', [])
                # for task in tasks:
                #     task_statuses[task.id] = task.status
                # For now, fetch individually (very slow!)
                console.print(f"[dim]Fetching task statuses for {len(report_task_ids)} reports...[/dim]")
                for task_id in report_task_ids:
                    try:
                        task = Task.get_by_id(task_id, client)
                        if task and hasattr(task, 'status'):
                           task_statuses[task_id] = task.status
                        else:
                           task_statuses[task_id] = "[dim]Not Found[/dim]"
                    except Exception as task_e:
                        logger.warning(f"Failed to fetch task {task_id}: {task_e}")
                        task_statuses[task_id] = "[red]Error[/red]"
            except Exception as batch_e:
                 logger.error(f"Failed to fetch task statuses: {batch_e}")
                 # Indicate error for all tasks if batch fails
                 for task_id in report_task_ids: task_statuses[task_id] = "[red]Fetch Error[/red]"
        # ---

        # Display results in a table
        table = Table(title=f"Generated Reports (Account: {account_id})" + (f" - Config: {config_identifier}" if config_identifier else ""))
        table.add_column("Report ID", style="cyan", no_wrap=True)
        table.add_column("Report Name", style="magenta")
        table.add_column("Config ID", style="green", no_wrap=True)
        table.add_column("Task ID", style="yellow", no_wrap=True)
        table.add_column("Task Status", style="blue")
        table.add_column("Created At", style="blue")

        for report_instance in reports: # Iterate over Report instances
            created_at_str = report_instance.createdAt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(report_instance, 'createdAt') and report_instance.createdAt else 'N/A'
            task_id = getattr(report_instance, 'taskId', 'N/A')
            task_status = task_statuses.get(task_id, "[dim]N/A[/dim]") if task_id != 'N/A' else "[dim]-[/dim]"
            config_id = getattr(report_instance, 'reportConfigurationId', 'N/A')
            
            table.add_row(
                report_instance.id, 
                getattr(report_instance, 'name', '[i]No Name[/i]'), 
                config_id,
                task_id,
                task_status,
                created_at_str
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error listing reports: {e}[/bold red]")
        logger.error(f"Failed to list reports: {e}\\n{traceback.format_exc()}")

@report.command(name="show")
@click.argument('id_or_name', type=str)
@click.option('--account', 'account_identifier', help='Optional account key or ID for context (needed for name lookup).', default=None)
def show_report(id_or_name: str, account_identifier: Optional[str]):
    """Show details for a specific Report, including its associated Task and Blocks."""
    client = create_client()

    # --- Account Resolution (Standard) ---
    account_id = None
    if account_identifier:
        try:
            account_id = client._resolve_account_id(account_key=account_identifier)
        except Exception as e:
            try:
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

    # --- Report Resolution --- #
    report_instance = _resolve_report(id_or_name, account_id, client)

    if not report_instance:
        console.print(f"[red]Report '{id_or_name}' not found for account {account_id}.[/red]")
        return

    console.print(f"[cyan]Showing details for Report ID: {report_instance.id} (Name: '{report_instance.name}')[/cyan]")

    # --- Fetch Associated Task --- #
    task_instance = None
    task_status = "N/A"
    started_at_str = "N/A"
    completed_at_str = "N/A"
    error_message_str = "N/A"
    error_details_str = "N/A"
    task_metadata_str = "N/A"

    if hasattr(report_instance, 'taskId') and report_instance.taskId:
        try:
            task_instance = Task.get_by_id(report_instance.taskId, client)
            if task_instance:
                task_status = task_instance.status or "UNKNOWN"
                started_at_str = task_instance.startedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if task_instance.startedAt else 'N/A'
                completed_at_str = task_instance.completedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if task_instance.completedAt else 'N/A'
                error_message_str = task_instance.errorMessage or 'None'
                error_details_str = task_instance.errorDetails or 'None'
                # Safely parse and format task metadata
                try:
                    metadata_dict = json.loads(task_instance.metadata) if task_instance.metadata else {}
                    task_metadata_str = pretty_repr(metadata_dict)
                except json.JSONDecodeError:
                    task_metadata_str = task_instance.metadata # Show raw if not JSON
                except Exception as e:
                    task_metadata_str = f"Error parsing metadata: {e}"

            else:
                task_status = "TASK_NOT_FOUND"
        except Exception as e:
            task_status = f"FETCH_ERROR: {e}"
            console.print(f"[yellow]Warning: Could not fetch associated Task {report_instance.taskId}: {e}[/yellow]")
    else:
        task_status = "NO_TASK_ID"

    # --- Fetch Associated Blocks --- #
    blocks = []
    try:
        # list_by_report_id now returns a list directly
        block_data = ReportBlock.list_by_report_id(report_instance.id, client)
        blocks = block_data # Assign the list directly
        # Sort blocks by position
        blocks.sort(key=lambda b: getattr(b, 'position', float('inf'))) # Sort by position, put items without position last
    except Exception as e:
        # The warning should now reflect the actual error if list_by_report_id fails
        console.print(f"[yellow]Warning: Could not fetch report blocks: {e}[/yellow]")

    # --- Display Report Details --- #
    created_at_str = report_instance.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC") if hasattr(report_instance, 'createdAt') and report_instance.createdAt else 'N/A'
    updated_at_str = report_instance.updatedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if hasattr(report_instance, 'updatedAt') and report_instance.updatedAt else 'N/A'
    config_id_str = report_instance.reportConfigurationId if hasattr(report_instance, 'reportConfigurationId') else 'N/A'
    params_str = pretty_repr(report_instance.parameters) if hasattr(report_instance, 'parameters') else 'N/A'
    # Render output potentially as Markdown
    # output_content = Syntax(report_instance.output, "markdown", theme="default", line_numbers=True) if hasattr(report_instance, 'output') and report_instance.output else "(No output content)"
    # For now, just show the raw output string, Markdown rendering can be complex in terminal
    output_str = report_instance.output if hasattr(report_instance, 'output') else 'N/A'

    report_content = (
        f"[bold]Report ID:[/bold] {report_instance.id}\n"
        f"[bold]Name:[/bold] {report_instance.name}\n"
        f"[bold]Account ID:[/bold] {report_instance.accountId}\n"
        f"[bold]Configuration ID:[/bold] {config_id_str}\n"
        f"[bold]Parameters:[/bold]\n{params_str}\n"
        f"[bold]Created At:[/bold] {created_at_str}\n"
        f"[bold]Updated At:[/bold] {updated_at_str}\n\n"
        f"[bold magenta]--- Associated Task ---[/bold magenta]\n"
        f"[bold]Task ID:[/bold] {report_instance.taskId or 'N/A'}\n"
        f"[bold]Task Status:[/bold] {task_status}\n"
        f"[bold]Task Started At:[/bold] {started_at_str}\n"
        f"[bold]Task Completed At:[/bold] {completed_at_str}\n"
        f"[bold]Task Error Message:[/bold] {error_message_str}\n"
        f"[bold]Task Error Details:[/bold] {error_details_str}\n"
        f"[bold]Task Metadata:[/bold]\n{task_metadata_str}\n\n"
        f"[bold magenta]--- Report Output (Markdown) ---[/bold magenta]\n"
        f"{output_str}\n\n"
        f"[bold magenta]--- Report Blocks ({len(blocks)} found) ---[/bold magenta]\n"
        f"(Use 'plexus report block list {report_instance.id}' or 'plexus report block show ...' for details)"
    )

    console.print(Panel(report_content, title=f"Report Details: {report_instance.name}", border_style="blue", expand=False))

    # Optionally list block summaries here if desired
    if blocks:
        block_table = Table(title="Associated Report Blocks Summary")
        block_table.add_column("Position", style="dim")
        block_table.add_column("Name", style="cyan")
        block_table.add_column("Output Keys", style="green") # Show keys of the JSON output
        block_table.add_column("Log Exists?", style="yellow")

        for block in blocks:
            pos_str = str(block.position) if hasattr(block, 'position') else "N/A"
            name_str = block.name if hasattr(block, 'name') else "(No Name)"
            log_exists_str = "Yes" if hasattr(block, 'log') and block.log else "No"
            output_keys_str = "N/A"
            if hasattr(block, 'output') and block.output:
                try:
                    output_dict = json.loads(block.output) if isinstance(block.output, str) else block.output
                    if isinstance(output_dict, dict):
                         output_keys_str = ", ".join(output_dict.keys())
                    else:
                         output_keys_str = f"({type(output_dict).__name__})"
                except Exception:
                     output_keys_str = "(Error parsing)"
            
            block_table.add_row(pos_str, name_str, output_keys_str, log_exists_str)
        
        console.print(block_table)

# --- Helper: Resolve ID or Name for Report ---
def _resolve_report(identifier: str, account_id: str, client: PlexusDashboardClient) -> Optional[Report]:
    """
    Resolves a report identifier (ID or name) to a Report object.
    Tries ID first, then name lookup within the account.
    """
    # Check if identifier looks like a UUID (potential ID)
    is_potential_uuid = False
    try:
        uuid.UUID(identifier)
        is_potential_uuid = True
    except ValueError:
        pass # Not a valid UUID format

    found_report = None
    # Strategy: Try ID first if it looks like one, otherwise try name first
    if is_potential_uuid:
        # Try getting by ID first
        try:
            console.print(f"Attempting to fetch Report by ID: {identifier}", style="dim")
            found_report = Report.get_by_id(identifier, client)
            if found_report:
                # Verify account match if possible (assuming report has accountId)
                if hasattr(found_report, 'accountId') and found_report.accountId == account_id:
                    console.print(f"Found Report by ID.", style="dim green")
                    return found_report
                else:
                     console.print(f"Found Report by ID, but account mismatch ({found_report.accountId} != {account_id}). Continuing search...", style="dim yellow")
                     found_report = None # Reset if account doesn't match
        except Exception as e:
            console.print(f"Failed to fetch Report by ID: {e}", style="dim red")
            pass # Ignore error and proceed to name lookup

        # If ID lookup failed or account mismatch, try by name
        if not found_report:
            try:
                console.print(f"Attempting to fetch Report by Name: {identifier} (Account: {account_id})", style="dim")
                found_report = Report.get_by_name(name=identifier, account_id=account_id, client=client)
                if found_report:
                    console.print(f"Found Report by Name.", style="dim green")
                    return found_report
            except Exception as e:
                console.print(f"Failed to fetch Report by Name: {e}", style="dim red")
                pass
    else:
        # Try getting by name first
        try:
            console.print(f"Attempting to fetch Report by Name: {identifier} (Account: {account_id})", style="dim")
            found_report = Report.get_by_name(name=identifier, account_id=account_id, client=client)
            if found_report:
                 console.print(f"Found Report by Name.", style="dim green")
                 return found_report
        except Exception as e:
            console.print(f"Failed to fetch Report by Name: {e}", style="dim red")
            pass # Ignore error and proceed to ID lookup

        # If name lookup failed, try by ID (in case it wasn't UUID format but still an ID)
        if not found_report:
            try:
                console.print(f"Attempting to fetch Report by ID: {identifier}", style="dim")
                found_report = Report.get_by_id(identifier, client)
                if found_report:
                     # Verify account match if possible
                    if hasattr(found_report, 'accountId') and found_report.accountId == account_id:
                        console.print(f"Found Report by ID.", style="dim green")
                        return found_report
                    else:
                        console.print(f"Found Report by ID, but account mismatch ({found_report.accountId} != {account_id}). Continuing search...", style="dim yellow")
                        found_report = None # Reset if account doesn't match
            except Exception as e:
                console.print(f"Failed to fetch Report by ID: {e}", style="dim red")
                pass

    # If neither worked
    console.print(f"Could not resolve Report identifier '{identifier}' (Account: {account_id}).", style="yellow")
    return None

@report.command(name="last")
@click.option('--account', 'account_identifier', help='Optional account key or ID to specify the account context.', default=None)
@click.pass_context # Pass the context to call other commands
def show_last_report(ctx, account_identifier: Optional[str]):
    """Show details for the most recently created Report for the account."""
    client = create_client()

    # --- Account Resolution (Standard) ---
    account_id = None
    if account_identifier:
        try:
            account_id = client._resolve_account_id(account_key=account_identifier)
        except Exception as e:
            try:
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

    console.print(f"[cyan]Fetching the most recent Report for Account ID: {account_id}[/cyan]")

    try:
        # List reports, sorted by createdAt descending, limit 1
        # Assuming list_by_account_id supports sorting or returns sorted by default.
        # If not, we might need a dedicated method or client-side sorting.
        report_result_data = Report.list_by_account_id(
            account_id=account_id,
            client=client,
            limit=1 # Fetch only the most recent one
        )
        # list_by_account_id returns a list directly
        reports = report_result_data 

        if not reports:
            console.print(f"[yellow]No reports found for account {account_id}.[/yellow]")
            return

        last_report = reports[0]
        console.print(f"[green]Found last report:[/green] ID: {last_report.id}, Name: '{last_report.name}'")
        
        # Invoke the 'show' command logic with the found ID
        # Pass necessary options (like account_id for context, although show might re-resolve)
        ctx.invoke(show_report, id_or_name=last_report.id, account_identifier=account_id)

    except Exception as e:
        console.print(f"[bold red]Error fetching last report: {e}[/bold red]")
        logger.error(f"Failed to fetch last report for account {account_id}: {e}\n{traceback.format_exc()}")

@block.command(name="list")
@click.argument('report_id', type=str)
@click.option('--limit', type=int, default=100, help='Maximum number of blocks to list.')
def list_blocks(report_id: str, limit: int):
    """List Report Blocks associated with a specific Report ID."""
    client = create_client()

    # Validate Report ID format (basic check)
    try:
        uuid.UUID(report_id)
    except ValueError:
        console.print(f"[red]Error: Invalid Report ID format. Please provide a valid UUID.[/red]")
        return

    console.print(f"[cyan]Listing Report Blocks for Report ID: {report_id}[/cyan]")

    try:
        # Fetch the parent report first to ensure it exists (optional, but good practice)
        try:
            parent_report = Report.get_by_id(report_id, client)
            if not parent_report:
                 console.print(f"[yellow]Warning: Report with ID {report_id} not found.[/yellow]")
                 # Continue anyway, list_by_report_id might still work or return empty
        except Exception as report_e:
             console.print(f"[yellow]Warning: Could not verify parent Report {report_id}: {report_e}[/yellow]")

        # Fetch blocks associated with the report ID
        block_data = ReportBlock.list_by_report_id(report_id, client, limit=limit)
        blocks = block_data.get('items', [])
        
        if not blocks:
            console.print(f"[yellow]No report blocks found for Report ID {report_id}.[/yellow]")
            return

        # Sort blocks by position
        blocks.sort(key=lambda b: getattr(b, 'position', float('inf')))

        # Display results in a table
        table = Table(title=f"Report Blocks (Report ID: {report_id})")
        table.add_column("Position", style="dim")
        table.add_column("Name", style="cyan")
        table.add_column("Output Keys/Type", style="green") # Show keys or type of the JSON output
        table.add_column("Log Exists?", style="yellow")
        table.add_column("Created At", style="blue")

        for block_instance in blocks:
            pos_str = str(block_instance.position) if hasattr(block_instance, 'position') else "N/A"
            name_str = block_instance.name if hasattr(block_instance, 'name') and block_instance.name else "(No Name)"
            log_exists_str = "Yes" if hasattr(block_instance, 'log') and block_instance.log else "No"
            created_at_str = block_instance.createdAt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(block_instance, 'createdAt') and block_instance.createdAt else 'N/A'
            output_summary = "N/A"
            if hasattr(block_instance, 'output') and block_instance.output:
                try:
                    # Handle potential double-encoded JSON
                    output_val = block_instance.output
                    if isinstance(output_val, str):
                        try:
                            output_dict = json.loads(output_val)
                        except json.JSONDecodeError:
                            output_dict = output_val # Keep as string if not valid JSON
                    else:
                         output_dict = output_val # Assume already decoded

                    if isinstance(output_dict, dict):
                        output_summary = ", ".join(output_dict.keys())
                        if not output_summary: output_summary = "(Empty Dict)"
                    elif isinstance(output_dict, list):
                         output_summary = f"(List, len={len(output_dict)})"
                    elif isinstance(output_dict, str):
                         output_summary = f"(String, len={len(output_dict)})"
                    else:
                        output_summary = f"({type(output_dict).__name__})"
                except Exception as parse_e:
                    logger.warning(f"Error parsing block output summary: {parse_e}")
                    output_summary = "(Error parsing)"
            
            table.add_row(pos_str, name_str, output_summary, log_exists_str, created_at_str)
        
        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error listing report blocks for report {report_id}: {e}[/bold red]")
        logger.error(f"Failed to list report blocks for {report_id}: {e}\n{traceback.format_exc()}")

@block.command(name="show")
@click.argument('report_id', type=str)
@click.argument('block_identifier', type=str)
def show_block(report_id: str, block_identifier: str):
    """Show details for a specific Report Block within a Report.

    BLOCK_IDENTIFIER can be the block's position (integer) or its name (string).
    """
    client = create_client()

    # Validate Report ID format
    try:
        uuid.UUID(report_id)
    except ValueError:
        console.print(f"[red]Error: Invalid Report ID format. Please provide a valid UUID.[/red]")
        return

    console.print(f"[cyan]Fetching Report Block '{block_identifier}' for Report ID: {report_id}[/cyan]")

    try:
        # Fetch all blocks for the report first (less efficient, but needed for name/pos lookup)
        # TODO: Ideally, the API would support get_by_report_and_position or get_by_report_and_name
        block_data = ReportBlock.list_by_report_id(report_id, client, limit=500) # Assume reasonable limit
        all_blocks = block_data.get('items', [])

        if not all_blocks:
            console.print(f"[yellow]No blocks found for Report ID {report_id}. Cannot find block '{block_identifier}'.[/yellow]")
            return

        found_block = None
        # Try to identify by position (integer)
        try:
            target_position = int(block_identifier)
            for b in all_blocks:
                if hasattr(b, 'position') and b.position == target_position:
                    found_block = b
                    console.print(f"[dim]Identified block by position: {target_position}[/dim]")
                    break
        except ValueError:
            # If not an integer, assume it's a name
            pass

        # If not found by position, try by name
        if not found_block:
            console.print(f"[dim]Block identifier '{block_identifier}' not an integer position. Trying name lookup...[/dim]")
            matched_by_name = []
            for b in all_blocks:
                if hasattr(b, 'name') and b.name == block_identifier:
                    matched_by_name.append(b)
            
            if len(matched_by_name) == 1:
                found_block = matched_by_name[0]
                console.print(f"[dim]Identified block by name: '{block_identifier}'[/dim]")
            elif len(matched_by_name) > 1:
                 console.print(f"[yellow]Warning: Multiple blocks found with name '{block_identifier}'. Showing the first one found (by API order, then position).[/yellow]")
                 # Sort by position if multiple have same name
                 matched_by_name.sort(key=lambda b: getattr(b, 'position', float('inf')))
                 found_block = matched_by_name[0]
            else:
                 console.print(f"[yellow]Block identifier '{block_identifier}' did not match any block name.[/yellow]")

        if not found_block:
            console.print(f"[red]Error: Could not find a block matching identifier '{block_identifier}' for Report ID {report_id}.[/red]")
            return

        # --- Display Block Details --- #
        pos_str = str(found_block.position) if hasattr(found_block, 'position') else "N/A"
        name_str = found_block.name if hasattr(found_block, 'name') and found_block.name else "(No Name)"
        created_at_str = found_block.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC") if hasattr(found_block, 'createdAt') and found_block.createdAt else 'N/A'
        updated_at_str = found_block.updatedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if hasattr(found_block, 'updatedAt') and found_block.updatedAt else 'N/A'
        log_content = found_block.log if hasattr(found_block, 'log') and found_block.log else "[i](No log content)[/i]"

        # Prepare output JSON for display
        output_display = None
        raw_output = getattr(found_block, 'output', None)
        if raw_output:
            try:
                # Handle potential double-encoded JSON string
                if isinstance(raw_output, str):
                    try:
                        output_data = json.loads(raw_output)
                    except json.JSONDecodeError:
                         # If it's a string but not JSON, display as plain text
                         output_display = Syntax(raw_output, "text", theme="default", line_numbers=False, word_wrap=True)
                         output_data = None # Mark as non-JSON
                else:
                    output_data = raw_output # Assume already decoded dict/list/etc.
                
                # If we have successfully decoded/retrieved structured data (dict/list)
                if output_data is not None and output_display is None:
                    pretty_output_str = json.dumps(output_data, indent=2)
                    output_display = Syntax(pretty_output_str, "json", theme="default", line_numbers=True)

            except Exception as e:
                logger.error(f"Error formatting block output: {e}")
                output_display = Panel(f"[red]Error formatting output: {e}[/red]", border_style="red")
        else:
            output_display = "[i](No output content)[/i]"

        # Build Panel Content
        panel_title = f"Report Block Details (Report: {report_id}) - Name: '{name_str}' Pos: {pos_str}"
        
        from rich.console import Group # Lazy import for Group
        from rich.text import Text

        content_group = Group(
            Text.from_markup(f"[bold]Report ID:[/bold] {report_id}"),
            Text.from_markup(f"[bold]Position:[/bold] {pos_str}"),
            Text.from_markup(f"[bold]Name:[/bold] {name_str}"),
            Text.from_markup(f"[bold]Created At:[/bold] {created_at_str}"),
            Text.from_markup(f"[bold]Updated At:[/bold] {updated_at_str}"),
            Text(""), # Spacer
            Text.from_markup("[bold magenta]--- Output ---[/bold magenta]"),
            output_display or Text.from_markup("[i](No output content)[/i]"),
            Text(""), # Spacer
            Text.from_markup("[bold magenta]--- Log ---[/bold magenta]"),
            Panel(Text(log_content, overflow="fold"), border_style="dim") # Panel for log folding
        )
        
        console.print(Panel(content_group, title=panel_title, border_style="green", expand=False))

    except Exception as e:
        console.print(f"[bold red]Error showing report block '{block_identifier}' for report {report_id}: {e}[/bold red]")
        logger.error(f"Failed to show report block '{block_identifier}' for {report_id}: {e}\n{traceback.format_exc()}")