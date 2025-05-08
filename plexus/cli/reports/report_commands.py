"""
Commands for generating and inspecting Plexus Reports.
"""

import click
import logging
import json
import traceback
from datetime import datetime, timezone
from typing import Optional, Tuple
import sys

# Import necessary utilities and models
from plexus.cli.console import console
from plexus.cli.client_utils import create_client
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.report_configuration import ReportConfiguration
from plexus.dashboard.api.models.report import Report
from plexus.dashboard.api.models.task import Task
from plexus.dashboard.api.models.report_block import ReportBlock
from plexus.tasks.reports import generate_report_task
from plexus.reports.service import _generate_report_core
from plexus.cli.task_progress_tracker import TaskProgressTracker, StageConfig
from plexus.cli.utils import parse_kv_pairs

from rich.panel import Panel
from rich.table import Table
from rich.pretty import pretty_repr
from rich.syntax import Syntax
from rich.markup import escape
from rich.markdown import Markdown
from rich.console import Group
from gql.transport.exceptions import TransportQueryError

# Import shared utility functions
from .utils import (
    resolve_account_id_for_command,
    format_kv,
    resolve_report_config,
    build_report_info_table,
    resolve_report
)

logger = logging.getLogger(__name__)

# Note: The @click.group() definition remains in the main ReportCommands.py
# These commands will be added to that group.

@click.command(name="run") # Changed from report.command to click.command
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
        # Use the utility function
        account_id = resolve_account_id_for_command(client, None) # Pass None to use default
        console.print(f"[dim]Using Account ID: {account_id}[/dim]")

        # --- Step 2: Resolve Report Configuration --- # (Use utility)
        console.print(f"Resolving Report Configuration: [cyan]'{config_identifier}'[/cyan]...")
        report_config = resolve_report_config(config_identifier, account_id, client)
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
        stage_configs = {
            "Loading Configuration": StageConfig(order=1, status_message="Loading report configuration details."),
            "Initializing Report Record": StageConfig(order=2, status_message="Creating initial database entry for the report."),
            "Parsing Configuration": StageConfig(order=3, status_message="Analyzing report structure and block definitions."),
            "Processing Report Blocks": StageConfig(order=4, status_message="Executing individual report block components.", total_items=0),
            "Finalizing Report": StageConfig(order=5, status_message="Saving results and completing generation."),
        }
        tracker = TaskProgressTracker(
            task_object=new_task,
            stage_configs=stage_configs,
            total_items=0,
            prevent_new_task=True,
            client=client
        )
        console.print("Tracker initialized.")

        # --- Step 5: Execute Report Generation Synchronously ---
        console.print(f"Executing report generation synchronously for Task [cyan]{task_id}[/cyan]...")
        log_prefix = f"[ReportGenCLI task_id={task_id}]"

        report_id, first_block_error = _generate_report_core(
            report_config_id=resolved_config_id,
            account_id=account_id,
            run_parameters=run_parameters,
            client=client,
            tracker=tracker,
            log_prefix_override=log_prefix
        )

        # --- Step 6: Mark Task Status based on Core Logic Result ---
        if first_block_error is None:
            console.print(f"[green]Report generation completed successfully![/green]")
            console.print(f"  Report ID: [magenta]{report_id}[/magenta]")
            console.print(f"  Task ID:   [cyan]{task_id}[/cyan]")
            tracker.complete()
            console.print(f"Task [cyan]{task_id}[/cyan] marked as COMPLETED.")
        else:
            # Blocks failed, but core process didn't crash critically
            console.print(f"[yellow]Report generation finished with errors.[/yellow]")
            console.print(f"  [bold red]Error:[/bold red] {first_block_error}") # Show specific error
            console.print(f"  Report ID: [magenta]{report_id}[/magenta] (may be incomplete)")
            console.print(f"  Task ID:   [cyan]{task_id}[/cyan]")
            # Mark task as failed using the specific error message
            tracker.fail(first_block_error)
            console.print(f"[yellow]Task [cyan]{task_id}[/cyan] marked as FAILED due to block errors.[/yellow]")

    except ValueError as e:
        console.print(f"[bold red]Error parsing parameters:[/bold red] {e}")
        raise click.Abort()
    except click.Abort:
         console.print("[yellow]Aborting report run.[/yellow]")
         if tracker:
             try:
                 tracker.fail("Report run aborted by user or prerequisite failure.")
                 console.print(f"[yellow]Task {task_id} marked as FAILED due to abort.[/yellow]")
             except Exception as tracker_err:
                 console.print(f"[red]Error marking task {task_id} as FAILED after abort: {tracker_err}[/red]")
         elif task_id:
              try:
                 task = Task.get_by_id(task_id, client)
                 if task:
                     task.update(status="FAILED", errorMessage="Report run aborted before tracker initialization.", completedAt=datetime.now(timezone.utc).isoformat())
                     console.print(f"[yellow]Task {task_id} marked as FAILED via direct update due to abort.[/yellow]")
              except Exception as update_err:
                 console.print(f"[red]Error marking task {task_id} as FAILED via direct update after abort: {update_err}[/red]")
    except Exception as e:
        error_msg = f"An error occurred during synchronous report generation"
        detailed_error = traceback.format_exc()
        console.print(f"[bold red]{error_msg}:[/bold red]")
        console.print(f"{type(e).__name__}: {e}")
        logger.error(f"CLI synchronous report run failed for Task {task_id or 'N/A'}: {e}\n{detailed_error}")

        if tracker:
            try:
                tracker.fail(f"{error_msg}: {e}\nDetails:\n{detailed_error}")
                console.print(f"[red]Task {task_id} marked as FAILED via tracker.[/red]")
            except Exception as tracker_fail_err:
                console.print(f"[red]Error marking task {task_id} as FAILED via tracker after primary error: {tracker_fail_err}[/red]")
        elif task_id:
             try:
                 task = Task.get_by_id(task_id, client)
                 if task:
                     task.update(status="FAILED", errorMessage=f"{error_msg}: {e}", errorDetails=detailed_error, completedAt=datetime.now(timezone.utc).isoformat())
                     console.print(f"[red]Task {task_id} marked as FAILED via direct update.[/red]")
             except Exception as final_update_err:
                 console.print(f"[red]CRITICAL: Failed to mark task {task_id} as FAILED via any method after error: {final_update_err}[/red]")
        else:
            console.print("[red]No Task ID available to mark as failed.[/red]")
        sys.exit(1)

@click.command(name="list") # Changed from report.command to click.command
@click.option('--config', 'config_identifier', default=None, help='Filter reports by a specific configuration ID or name.')
@click.option('--account', 'account_identifier', help='Optional account key or ID to filter by.', default=None)
@click.option('--limit', type=int, default=10, help='Maximum number of reports to list.')
def list_reports(config_identifier: Optional[str], account_identifier: Optional[str], limit: int):
    """List generated Reports, optionally filtering by configuration."""
    client = create_client()
    resolved_config_id = None

    # --- Account Resolution --- # (Use utility)
    account_id = resolve_account_id_for_command(client, account_identifier)

    # --- Resolve Config Identifier if provided --- # (Use utility)
    if config_identifier:
        console.print(f"[cyan]Resolving configuration filter: '{config_identifier}'...[/cyan]")
        config_instance = resolve_report_config(config_identifier, account_id, client)
        if not config_instance:
            console.print(f"[yellow]Could not resolve Report Configuration '{config_identifier}' to filter by.[/yellow]")
            return
        resolved_config_id = config_instance.id
        console.print(f"[cyan]Filtering reports for Configuration ID: {resolved_config_id}[/cyan]")

    console.print(f"[cyan]Listing Reports for Account ID: {account_id}[/cyan]" + (f" (Config ID: {resolved_config_id})" if resolved_config_id else ""))

    try:
        # Fetch initial batch
        report_result_data = Report.list_by_account_id(
            account_id=account_id,
            client=client,
            limit=200
        )
        reports = report_result_data

        # Client-side filtering
        if resolved_config_id:
             filtered_reports = [r for r in reports if hasattr(r, 'reportConfigurationId') and r.reportConfigurationId == resolved_config_id]
             reports = filtered_reports

        # Sort client-side by createdAt descending
        reports.sort(key=lambda r: getattr(r, 'createdAt', datetime.min.replace(tzinfo=timezone.utc)), reverse=True)

        # Apply limit *after* sorting/filtering
        final_reports_to_display = reports[:limit]

        if not final_reports_to_display:
            filter_msg = f" for configuration '{config_identifier}'" if config_identifier else ""
            console.print(f"[yellow]No reports found for account {account_id}{filter_msg}.[/yellow]")
            return

        # --- Fetch associated data ONLY for the reports being displayed ---
        config_names = {}
        task_statuses = {}
        report_config_ids = list(set(r.reportConfigurationId for r in final_reports_to_display if hasattr(r, 'reportConfigurationId') and r.reportConfigurationId))
        report_task_ids = list(set(r.taskId for r in final_reports_to_display if hasattr(r, 'taskId') and r.taskId))

        # Fetch Config Names
        if report_config_ids:
            console.print(f"[dim]Fetching configuration names for {len(report_config_ids)} relevant configs...[/dim]")
            for config_id in report_config_ids:
                try:
                    config_instance = ReportConfiguration.get_by_id(config_id, client)
                    if config_instance and hasattr(config_instance, 'name'):
                        config_names[config_id] = config_instance.name
                    else:
                        config_names[config_id] = "[dim]Not Found[/dim]"
                except Exception as config_e:
                    logger.warning(f"Failed to fetch config {config_id}: {config_e}")
                    config_names[config_id] = "[red]Error[/red]"

        # Fetch Task Statuses
        if report_task_ids:
            console.print(f"[dim]Fetching task statuses for {len(report_task_ids)} relevant tasks...[/dim]")
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
        # ---

        # Display results using Panels with internal Tables for alignment
        console.print(f"[bold]Displaying the {len(final_reports_to_display)} most recent reports:[/bold]")
        for report_instance in final_reports_to_display:
            config_id = getattr(report_instance, 'reportConfigurationId', 'N/A')
            config_name = config_names.get(config_id, "[dim]N/A[/dim]") if config_id != 'N/A' else "[dim]-[/dim]"
            task_status = task_statuses.get(report_instance.taskId, "[dim]N/A[/dim]") if hasattr(report_instance, 'taskId') and report_instance.taskId else "[dim]-[/dim]"

            # Use the helper function to build the info table (from utils)
            content_table = build_report_info_table(report_instance, config_name, task_status)

            console.print(Panel(content_table, title=f"Report: {getattr(report_instance, 'name', '[i]No Name[/i]')}", expand=True, border_style="dim"))

    except Exception as e:
        console.print(f"[bold red]Error listing reports: {e}[/bold red]")
        logger.error(f"Failed to list reports: {e}\n{traceback.format_exc()}")

@click.command(name="show") # Changed from report.command to click.command
@click.argument('id_or_name', type=str)
@click.option('--account', 'account_identifier', help='Optional account key or ID for context (needed for name lookup).', default=None)
def show_report(id_or_name: str, account_identifier: Optional[str]):
    """Display details of a specific Report."""
    client = create_client()
    # Use utility function
    account_id = resolve_account_id_for_command(client, account_identifier)

    console.print(f"Fetching Report details for: [cyan]'{id_or_name}'[/cyan] in Account [cyan]{account_id}[/cyan]")

    try:
        # Use utility function
        report_instance = resolve_report(id_or_name, account_id, client)
        if not report_instance:
            console.print(f"[red]Error: Report '{id_or_name}' not found for account {account_id}.[/red]")
            raise click.Abort()

        console.print(f"Found Report: {report_instance.name} (ID: {report_instance.id})")
        console.print("Fetching associated Task, Configuration, and Blocks...")

        # --- Fetch Associated Data ---
        task_instance = None
        task_stages = [] # Keep for potential future use, but not directly displayed now
        task_error = None
        if report_instance.taskId:
            try:
                task_instance = Task.get_by_id(report_instance.taskId, client=client)
                if not task_instance:
                     console.print(f"[yellow]Warning: Could not fetch Task with ID {report_instance.taskId}.[/yellow]")
                     task_error = f"Task ID {report_instance.taskId} not found."
                # Stage fetching logic remains, but errors are handled differently in display
                elif hasattr(task_instance, 'get_stages'):
                    try:
                        task_stages_data = task_instance.get_stages()
                        if task_stages_data:
                            task_stages = sorted(
                                [stage for stage in task_stages_data if stage],
                                key=lambda s: getattr(s, 'createdAt', datetime.min.replace(tzinfo=timezone.utc))
                            )
                        else:
                            console.print(f"[dim]Task {task_instance.id} has no associated stages.[/dim]")
                    except Exception as stage_e:
                        task_error = f"Error fetching stages for task {task_instance.id}: {stage_e}"
                        console.print(f"[red]{task_error}[/red]")
                        logger.error(f"{task_error}\n{traceback.format_exc()}")
                else:
                    task_error = f"Task object (ID: {task_instance.id}) does not have get_stages() method."
                    console.print(f"[yellow]Warning: {task_error}[/yellow]")
            except Exception as e:
                task_error = f"Error fetching task details: {e}"
                console.print(f"[red]{task_error}[/red]")
                logger.error(f"Error fetching task {report_instance.taskId}: {e}\n{traceback.format_exc()}")
        else:
            console.print("[yellow]Warning: Report is not associated with a Task (taskId is null).[/yellow]")

        config_instance = None
        config_error = None
        if report_instance.reportConfigurationId:
            try:
                config_instance = ReportConfiguration.get_by_id(report_instance.reportConfigurationId, client)
            except Exception as e:
                config_error = f"Error fetching configuration details: {e}"
                console.print(f"[red]{config_error}[/red]")
        else:
            console.print("[yellow]Warning: Report is not associated with a Configuration.[/yellow]")

        blocks = []
        blocks_error = None
        try:
            blocks_data = ReportBlock.list_by_report_id(report_instance.id, client)
            if blocks_data:
                 blocks = sorted([b for b in blocks_data if b and b.position is not None], key=lambda b: b.position)
            else:
                 console.print("[dim]No report blocks found for this report.[/dim]")
        except Exception as e:
            blocks_error = f"Error fetching report blocks: {e}"
            console.print(f"[red]{blocks_error}[/red]")
            logger.error(f"Error fetching blocks for report {report_instance.id}: {e}\n{traceback.format_exc()}")

        # --- Prepare Display Data ---
        config_display = f"{config_instance.name} (ID: {config_instance.id})" if config_instance else "N/A"
        if config_error:
            config_display = f"[red]Config Error[/red]"

        task_status_display = task_instance.status if task_instance else "N/A"
        if task_error and not task_instance:
             task_status_display = f"[red]Task Error[/red]"

        created_at_str = report_instance.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC") if report_instance.createdAt else 'N/A'
        updated_at_str = report_instance.updatedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if report_instance.updatedAt else 'N/A'
        params_str = json.dumps(report_instance.parameters, indent=4) if report_instance.parameters else "{}"

        # --- Build Panels ---
        # First create all content dictionaries
        report_info_content = {
            "Report Name": report_instance.name,
            "Report ID": report_instance.id,
            "Account ID": report_instance.accountId,
            "Configuration": config_display,
            "Task ID": report_instance.taskId or "N/A",
            "Task Status": task_status_display,
            "Created At": created_at_str,
            "Updated At": updated_at_str,
            "Run Parameters": params_str
        }

        task_content = {}
        if task_instance:
            # Calculate task-related strings
            task_created_str = task_instance.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC") if task_instance.createdAt else 'N/A'
            task_updated_str = task_instance.updatedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if task_instance.updatedAt else 'N/A'
            task_started_str = task_instance.startedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if task_instance.startedAt else 'N/A'
            task_completed_str = task_instance.completedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if task_instance.completedAt else 'N/A'
            metadata_str = json.dumps(task_instance.metadata, indent=4) if task_instance.metadata else "{}"

            # Determine current stage name
            current_stage_name = getattr(task_instance, 'currentStageName', None)
            if not current_stage_name:
                current_stage_name = f"({task_instance.status})"
            elif task_error and "stage" in task_error.lower():
                current_stage_name += " [Error Fetching Stages]"

            task_content = {
                "Task Status": task_instance.status or "N/A",
                "Current Stage": current_stage_name,
                "Description": task_instance.description or "N/A",
                "Created": task_created_str,
                "Updated": task_updated_str,
                "Started": task_started_str,
                "Completed": task_completed_str,
                "Error": task_instance.errorMessage or "None",
                "Metadata": metadata_str
            }

        # Now calculate max key length after all content is defined
        max_key_len = max(
            max(len(k) for k in report_info_content.keys()) if report_info_content else 0,
            max(len(k) for k in task_content.keys()) if task_content else 0,
            10  # Minimum width for block headers
        )

        # Report Info Panel
        report_info_panel_content = Group(*(
            format_kv(k, v, max_key_len) for k, v in report_info_content.items()
        ))
        report_info_panel = Panel(
            report_info_panel_content,
            title="[bold]Report Information[/bold]",
            border_style="blue",
            expand=True
        )

        # Task Details Panel
        task_details_panel = Panel("[dim]No Task associated or Task details could not be fetched.[/dim]", title="[bold]Associated Task Details[/bold]", border_style="yellow", expand=True)
        if task_instance:
            task_details_panel_content = Group(*(
                format_kv(k, v, max_key_len) for k, v in task_content.items()
            ))
            task_details_panel = Panel(
                task_details_panel_content,
                title="[bold]Associated Task Details[/bold]",
                border_style="green",
                expand=True
            )
        elif task_error:
            task_details_panel = Panel(f"[red]{task_error}[/red]", title="[bold]Associated Task Details[/bold]", border_style="red", expand=True)

        # Report Output Panel
        report_output_panel = Panel(
            report_instance.output or "[dim]No output generated.[/dim]",
            title="[bold]Raw Report Output[/bold]",
            border_style="magenta",
            expand=True
        )

        # Report Blocks Panel
        blocks_panel_content = None
        if blocks_error:
            blocks_panel_content = f"[red]{blocks_error}[/red]"
        elif blocks:
            # Create a list of block panels
            block_panels = []
            for block_instance in blocks:
                # Block header panel with name, position, and type
                header_content = Group(
                    format_kv("Name", block_instance.name or "[No Name]", max_key_len),
                    format_kv("Position", str(block_instance.position), max_key_len),
                    format_kv("Type", block_instance.type or "[No Type]", max_key_len)
                )
                header_panel = Panel(
                    header_content,
                    title=f"[bold]Block {block_instance.position}[/bold]",
                    border_style="blue",
                    expand=True
                )

                # Log panel (now first)
                log_content = block_instance.log or "[dim]No log messages[/dim]"
                log_panel = Panel(
                    log_content,
                    title="[bold]Log[/bold]",
                    border_style="yellow",
                    expand=True
                )

                # Output panel (now second)
                output_content = "[dim]No output[/dim]"
                if block_instance.output:
                    try:
                        output_content = pretty_repr(block_instance.output, max_width=80)
                    except Exception:
                        output_content = "[red]Error rendering output[/red]"
                output_panel = Panel(
                    output_content,
                    title="[bold]Output[/bold]",
                    border_style="green",
                    expand=True
                )

                # Combine all panels for this block
                block_panels.extend([header_panel, log_panel, output_panel])

            # Create the main blocks panel containing all block panels
            blocks_panel_content = Group(*block_panels)
        else:
            blocks_panel_content = "[dim]No report blocks found or loaded.[/dim]"

        report_blocks_panel = Panel(
            blocks_panel_content,
            title="[bold]Report Blocks[/bold]",
            border_style="yellow",
            expand=True
        )

        # --- Print Panels ---
        console.print(report_info_panel)
        console.print(task_details_panel)
        console.print(report_output_panel)
        console.print(report_blocks_panel)

    except TransportQueryError as e:
        console.print(f"[bold red]GraphQL Error fetching report details: {e}[/bold red]")
        if e.errors:
            for error in e.errors:
                console.print(f"  - {error.get('message', 'Unknown GraphQL error')}")
        logger.error(f"GraphQL Error in show_report for '{id_or_name}': {e}\n{traceback.format_exc()}")
    except click.Abort:
        raise # Re-raise Abort cleanly
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        logger.error(f"Unexpected error in show_report for '{id_or_name}': {e}\n{traceback.format_exc()}")

@click.command(name="last") # Changed from report.command to click.command
@click.option('--account', 'account_identifier', help='Optional account key or ID to specify account. Defaults to PLEXUS_ACCOUNT_KEY.', default=None)
def show_last_report(account_identifier: Optional[str]):
    """Display details of the most recently created Report."""
    client = create_client()
    # Use utility function
    account_id = resolve_account_id_for_command(client, account_identifier)

    console.print(f"Fetching the last Report for Account ID: [cyan]{account_id}[/cyan]")

    try:
        console.print("[dim]Fetching recent reports to find the latest...[/dim]")
        result_data = Report.list_by_account_id(
            client=client,
            account_id=account_id,
            limit=50,
        )

        report_items = result_data

        if not report_items:
            console.print(f"[yellow]No reports found for account {account_id}.[/yellow]")
            return

        # Sort client-side
        report_items.sort(key=lambda r: getattr(r, 'createdAt', datetime.min.replace(tzinfo=timezone.utc)), reverse=True)

        report_instance = report_items[0]
        console.print(f"Found last report: {report_instance.name} (ID: {report_instance.id})")
        console.print("Fetching associated Task, Configuration, and Blocks...")

        # --- Fetch Associated Data (Duplicate logic - needs refactoring into helper) ---
        task_instance = None
        task_stages = []
        task_error = None
        if report_instance.taskId:
            try:
                task_instance = Task.get_by_id(report_instance.taskId, client=client)
                if not task_instance:
                    console.print(f"[yellow]Warning: Could not fetch Task with ID {report_instance.taskId}.[/yellow]")
                    task_error = f"Task ID {report_instance.taskId} not found."
                elif hasattr(task_instance, 'get_stages'):
                    try:
                        task_stages_data = task_instance.get_stages()
                        if task_stages_data:
                            task_stages = sorted(
                                [stage for stage in task_stages_data if stage],
                                key=lambda s: getattr(s, 'createdAt', datetime.min.replace(tzinfo=timezone.utc))
                            )
                        else:
                            console.print(f"[dim]Task {task_instance.id} has no associated stages.[/dim]")
                    except Exception as stage_e:
                        task_error = f"Error fetching stages for task {task_instance.id}: {stage_e}"
                        logger.error(f"{task_error}\n{traceback.format_exc()}") # Log only
                else:
                    task_error = f"Task object (ID: {task_instance.id}) does not have get_stages() method."
                    logger.warning(task_error) # Log only

            except Exception as e:
                task_error = f"Error fetching task details: {e}"
                logger.error(f"Error fetching task {report_instance.taskId} for last report: {e}\n{traceback.format_exc()}") # Log only
        else:
            console.print("[yellow]Warning: Last report is not associated with a Task.[/yellow]")

        config_instance = None
        config_error = None
        if report_instance.reportConfigurationId:
            try:
                config_instance = ReportConfiguration.get_by_id(report_instance.reportConfigurationId, client)
            except Exception as e:
                config_error = f"Error fetching configuration details: {e}"
                logger.error(config_error) # Log only
        else:
            console.print("[yellow]Warning: Last report is not associated with a Configuration.[/yellow]")

        blocks = []
        blocks_error = None
        try:
            blocks_data = ReportBlock.list_by_report_id(report_instance.id, client)
            if blocks_data:
                blocks = sorted([b for b in blocks_data if b and b.position is not None], key=lambda b: b.position)
            else:
                console.print("[dim]No report blocks found for the last report.[/dim]")
        except Exception as e:
            blocks_error = f"Error fetching report blocks: {e}"
            logger.error(f"Error fetching blocks for last report {report_instance.id}: {e}\n{traceback.format_exc()}") # Log only

        # --- Prepare Display Data ---
        config_display = f"{config_instance.name} (ID: {config_instance.id})" if config_instance else "N/A"
        if config_error:
            config_display = f"[red]Config Error[/red]"

        task_status_display = task_instance.status if task_instance else "N/A"
        if task_error and not task_instance:
            task_status_display = f"[red]Task Error[/red]"

        created_at_str = report_instance.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC") if report_instance.createdAt else 'N/A'
        updated_at_str = report_instance.updatedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if report_instance.updatedAt else 'N/A'
        params_str = json.dumps(report_instance.parameters, indent=4) if report_instance.parameters else "{}"

        # --- Build Panels ---
        # First create all content dictionaries
        report_info_content = {
            "Report Name": report_instance.name,
            "Report ID": report_instance.id,
            "Account ID": report_instance.accountId,
            "Configuration": config_display,
            "Task ID": report_instance.taskId or "N/A",
            "Task Status": task_status_display,
            "Created At": created_at_str,
            "Updated At": updated_at_str,
            "Run Parameters": params_str
        }

        task_content = {}
        if task_instance:
            # Calculate task-related strings
            task_created_str = task_instance.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC") if task_instance.createdAt else 'N/A'
            task_updated_str = task_instance.updatedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if task_instance.updatedAt else 'N/A'
            task_started_str = task_instance.startedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if task_instance.startedAt else 'N/A'
            task_completed_str = task_instance.completedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if task_instance.completedAt else 'N/A'
            metadata_str = json.dumps(task_instance.metadata, indent=4) if task_instance.metadata else "{}"

            # Determine current stage name
            current_stage_name = getattr(task_instance, 'currentStageName', None)
            if not current_stage_name:
                current_stage_name = f"({task_instance.status})"
            elif task_error and "stage" in task_error.lower():
                current_stage_name += " [Error Fetching Stages]"

            task_content = {
                "Task Status": task_instance.status or "N/A",
                "Current Stage": current_stage_name,
                "Description": task_instance.description or "N/A",
                "Created": task_created_str,
                "Updated": task_updated_str,
                "Started": task_started_str,
                "Completed": task_completed_str,
                "Error": task_instance.errorMessage or "None",
                "Metadata": metadata_str
            }

        # Now calculate max key length after all content is defined
        max_key_len = max(
            max(len(k) for k in report_info_content.keys()) if report_info_content else 0,
            max(len(k) for k in task_content.keys()) if task_content else 0,
            10  # Minimum width for block headers
        )

        # Report Info Panel
        report_info_panel_content = Group(*(
            format_kv(k, v, max_key_len) for k, v in report_info_content.items()
        ))
        report_info_panel = Panel(
            report_info_panel_content,
            title="[bold]Report Information (Last)[/bold]",
            border_style="blue",
            expand=True
        )

        # Task Details Panel
        task_details_panel = Panel("[dim]No Task associated or Task details could not be fetched.[/dim]", title="[bold]Associated Task Details[/bold]", border_style="yellow", expand=True)
        if task_instance:
            task_details_panel_content = Group(*(
                format_kv(k, v, max_key_len) for k, v in task_content.items()
            ))
            task_details_panel = Panel(
                task_details_panel_content,
                title="[bold]Associated Task Details[/bold]",
                border_style="green",
                expand=True
            )
        elif task_error:
            task_details_panel = Panel(f"[red]Error fetching task details[/red]", title="[bold]Associated Task Details[/bold]", border_style="red", expand=True)

        # Report Output Panel
        report_output_panel = Panel(
            report_instance.output or "[dim]No output generated.[/dim]",
            title="[bold]Raw Report Output[/bold]",
            border_style="magenta",
            expand=True
        )

        # Report Blocks Panel
        blocks_panel_content = None
        if blocks_error:
            blocks_panel_content = f"[red]{blocks_error}[/red]"
        elif blocks:
            # Create a list of block panels
            block_panels = []
            for block_instance in blocks:
                # Block header panel with name, position, and type
                header_content = Group(
                    format_kv("Name", block_instance.name or "[No Name]", max_key_len),
                    format_kv("Position", str(block_instance.position), max_key_len),
                    format_kv("Type", block_instance.type or "[No Type]", max_key_len)
                )
                header_panel = Panel(
                    header_content,
                    title=f"[bold]Block {block_instance.position}[/bold]",
                    border_style="blue",
                    expand=True
                )

                # Log panel (now first)
                log_content = block_instance.log or "[dim]No log messages[/dim]"
                log_panel = Panel(
                    log_content,
                    title="[bold]Log[/bold]",
                    border_style="yellow",
                    expand=True
                )

                # Output panel (now second)
                output_content = "[dim]No output[/dim]"
                if block_instance.output:
                    try:
                        output_content = pretty_repr(block_instance.output, max_width=80)
                    except Exception:
                        output_content = "[red]Error rendering output[/red]"
                output_panel = Panel(
                    output_content,
                    title="[bold]Output[/bold]",
                    border_style="green",
                    expand=True
                )

                # Combine all panels for this block
                block_panels.extend([header_panel, log_panel, output_panel])

            # Create the main blocks panel containing all block panels
            blocks_panel_content = Group(*block_panels)
        else:
            blocks_panel_content = "[dim]No report blocks found or loaded."

        report_blocks_panel = Panel(
            blocks_panel_content,
            title="[bold]Report Blocks[/bold]",
            border_style="yellow",
            expand=True
        )

        # --- Print Panels ---
        console.print(report_info_panel)
        console.print(task_details_panel)
        console.print(report_output_panel)
        console.print(report_blocks_panel)

    except TransportQueryError as e:
        console.print(f"[bold red]GraphQL Error fetching last report: {e}[/bold red]")
        if e.errors:
            for error in e.errors:
                console.print(f"  - {error.get('message', 'Unknown GraphQL error')}")
        logger.error(f"GraphQL Error in show_last_report: {e}\n{traceback.format_exc()}")
    except click.Abort:
        raise # Re-raise Abort cleanly
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        logger.error(f"Unexpected error in show_last_report: {e}\n{traceback.format_exc()}") 