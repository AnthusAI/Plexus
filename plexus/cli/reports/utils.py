"""
Utility functions for report CLI commands.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple, List
import json
import logging
import os
import click

from rich.table import Table
from rich.panel import Panel
from rich.pretty import pretty_repr
from rich.syntax import Syntax
from rich.markup import escape
from rich.markdown import Markdown
from rich.console import Group, Console
from rich.text import Text

from plexus.cli.console import console # Assuming this is the shared console instance
from plexus.dashboard.api.client import PlexusDashboardClient, _BaseAPIClient
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.report_configuration import ReportConfiguration
from plexus.dashboard.api.models.report import Report
from plexus.dashboard.api.models.report_block import ReportBlock
from plexus.dashboard.api.models.task import Task

logger = logging.getLogger(__name__)

# --- Helper function to resolve Account ID ---
def resolve_account_id_for_command(client: PlexusDashboardClient, account_identifier: Optional[str]) -> str:
    """Resolves the account ID based on provided identifier or default context."""
    account_id = None
    account_display_name = "default account"

    if account_identifier:
        account_display_name = f"identifier '{account_identifier}'"
        try:
            # Try resolving by key first, then ID
            console.print(f"[dim]Resolving account by identifier: {account_identifier}...[/dim]", highlight=False)
            account_obj = Account.get_by_key_or_id(account_identifier, client)
            if account_obj:
                account_id = account_obj.id
                console.print(f"[dim]Resolved account ID: {account_id}[/dim]", highlight=False)
            else:
                console.print(f"[red]Error: Could not resolve account identifier '{account_identifier}' as key or ID.[/red]")
                raise click.Abort() # Assuming click is available or handle differently
        except Exception as e:
            console.print(f"[red]Error resolving account identifier '{account_identifier}': {e}[/red]")
            raise click.Abort() # Assuming click is available or handle differently
    else:
        # No identifier provided, use client's internal resolution
        account_display_name = "default account (from environment)"
        console.print(f"[dim]Resolving default account from environment...[/dim]", highlight=False)
        try:
            account_id = client._resolve_account_id()
            if account_id:
                console.print(f"[dim]Resolved default account ID: {account_id}[/dim]", highlight=False)
            else:
                console.print(f"[red]Error: Could not resolve default account ID. Is PLEXUS_ACCOUNT_KEY set and valid?[/red]")
                raise click.Abort() # Assuming click is available or handle differently
        except Exception as e:
             console.print(f"[red]Error resolving default account: {e}. Is PLEXUS_ACCOUNT_KEY set and valid?[/red]")
             raise click.Abort() # Assuming click is available or handle differently

    # Final check before returning
    if not account_id:
        # This should ideally be caught by Aborts above, but as a safeguard:
        console.print(f"[red]Error: Failed to determine Account ID for {account_display_name}.[/red]")
        raise click.Abort() # Assuming click is available or handle differently

    return account_id

# Define a helper for consistent key-value rendering
def format_kv(key: str, value: str, max_key_len: int) -> Text:
    """Formats a key-value pair with consistent padding."""
    padded_key = key.ljust(max_key_len)
    return Text.assemble(f"{padded_key}: ", (str(value) if value is not None else "N/A", "bold"))

# --- Helper function for ID/Name resolution ---
def resolve_report_config(identifier: str, account_id: str, client: PlexusDashboardClient) -> Optional[ReportConfiguration]:
    """
    Helper to find a ReportConfiguration by ID or name within an account.
    Tries ID first if it looks like a UUID, otherwise tries name first.
    """
    # No special case for testing - let the mocks handle it directly
    
    is_uuid = False
    config: Optional[ReportConfiguration] = None
    try:
        uuid.UUID(identifier)
        is_uuid = True
    except ValueError:
        pass # Not a valid UUID format

    if is_uuid:
        # Try ID first
        try:
            logger.debug(f"Attempting to resolve config by ID: {identifier}")
            config = ReportConfiguration.get_by_id(identifier, client=client)
            # Verify account matches if found by ID (important!)
            if config and config.accountId == account_id:
                console.print(f"[dim]Resolved config by ID: {identifier}[/dim]")
                return config
            elif config:
                # Found but wrong account
                logger.warning(f"Config {identifier} found by ID, but belongs to account {config.accountId}, not {account_id}.")
                config = None # Reset config as it's not the correct one
            else:
                 logger.debug(f"Config not found by ID: {identifier}")
        except Exception as e:
            logger.error(f"Error resolving config by ID '{identifier}': {e}")
            console.print(f"[dim]Error resolving config by ID \'{identifier}\': {e}. Trying by name...[/dim]")
            # Fall through to name lookup

        # If ID lookup failed or returned wrong account, try name
        if not config:
            try:
                logger.debug(f"Attempting to resolve config '{identifier}' by name after ID attempt")
                config = ReportConfiguration.get_by_name(identifier, account_id, client=client)
                if config:
                    console.print(f"[dim]Resolved config by name after ID lookup: '{identifier}' to ID {config.id}[/dim]")
                    return config
                else:
                    logger.debug(f"Config '{identifier}' not found by name after ID attempt.")
            except Exception as e:
                logger.error(f"Error resolving config by name '{identifier}' after ID attempt: {e}")
                console.print(f"[dim]Error resolving config by name \'{identifier}\': {e}[/dim]")

    else: # Not a UUID format
        # Try Name first
        try:
            logger.debug(f"Attempting to resolve config by name: '{identifier}'")
            config = ReportConfiguration.get_by_name(identifier, account_id, client=client)
            if config:
                console.print(f"[dim]Resolved config by name: '{identifier}' to ID {config.id}[/dim]")
                return config
            else:
                logger.debug(f"Config not found by name: '{identifier}'")
        except Exception as e:
            logger.error(f"Error resolving config by name '{identifier}': {e}")
            console.print(f"[dim]Error resolving config by name \'{identifier}\': {e}. Trying by ID...[/dim]")
            # Fall through to ID lookup

        # If name lookup failed, try ID (in case name happened to look like a UUID key or something else)
        if not config:
            try:
                logger.debug(f"Attempting to resolve config '{identifier}' by ID after name attempt")
                config = ReportConfiguration.get_by_id(identifier, client=client)
                if config and config.accountId == account_id:
                    console.print(f"[dim]Resolved config by ID after name lookup: {identifier}[/dim]")
                    return config
                elif config:
                    logger.warning(f"Config {identifier} found by ID after name attempt, but belongs to account {config.accountId}, not {account_id}.")
                    config = None
                else:
                    logger.debug(f"Config '{identifier}' not found by ID after name attempt.")
            except Exception as e:
                 logger.error(f"Error resolving config by ID '{identifier}' after name attempt: {e}")
                 console.print(f"[dim]Error resolving config by ID \'{identifier}\': {e}[/dim]")

    # If we reach here, neither method worked
    logger.warning(f"Failed to resolve ReportConfiguration '{identifier}' for account {account_id} by ID or name.")
    return None

# --- Helper function to create the basic report info table ---
def build_report_info_table(report_instance: Report, config_name: str, task_status: str) -> Table:
    """Creates a Rich Table containing the standard report identification information."""
    created_at_str = report_instance.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC") if hasattr(report_instance, 'createdAt') and report_instance.createdAt else 'N/A'
    task_id = getattr(report_instance, 'taskId', 'N/A')
    config_id = getattr(report_instance, 'reportConfigurationId', 'N/A')

    content_table = Table(box=None, show_header=False, padding=0, pad_edge=False)
    content_table.add_column(style="bold", width=15) # Column for labels (fixed width)
    content_table.add_column() # Column for values

    content_table.add_row("[bold cyan]Report ID:", report_instance.id)
    content_table.add_row("[bold magenta]Config Name:", f"{config_name} ([i]ID: {config_id}[/i])")
    content_table.add_row("[bold yellow]Task ID:", task_id)
    content_table.add_row("[bold blue]Task Status:", task_status)
    content_table.add_row("[bold green]Created At:", created_at_str)

    return content_table

# --- Helper to resolve a Report ---
# TODO: Define/Fix this helper if needed, or integrate logic directly into commands.
# The original ReportCommands.py used it in 'show_report' but the definition was missing.
# If we keep 'show_report', it needs this logic.
def resolve_report(identifier: str, account_id: str, client: PlexusDashboardClient) -> Optional[Report]:
    """
    Helper to find a Report by ID or name within an account.
    Tries ID first if it looks like a UUID, otherwise tries name first.
    (Note: This function needs to be implemented based on available model methods,
     e.g., Report.get_by_id and potentially Report.list_by_account_and_name)
    """
    is_uuid = False
    try:
        uuid.UUID(identifier)
        is_uuid = True
    except ValueError:
        pass # Not a valid UUID format

    report_instance = None

    if is_uuid:
        # Try ID first
        try:
            report_instance = Report.get_by_id(identifier, client=client)
            if report_instance and report_instance.accountId != account_id:
                console.print(f"[yellow]Report found by ID, but belongs to a different account ({report_instance.accountId}).[/yellow]")
                return None # Don't return report from wrong account
            if report_instance:
                 console.print(f"[dim]Resolved report by ID: {identifier}[/dim]")
                 return report_instance
        except Exception as e:
            console.print(f"[dim]Failed to get report by ID \'{identifier}\': {e}. Trying by name...[/dim]")
            # Fall through
    else:
        # Try Name first
        try:
            # Assuming list_by_account_and_name exists for Report model
            reports_result = Report.list_by_account_and_name(
                account_id=account_id,
                name=identifier,
                client=client
            )
            items = reports_result if isinstance(reports_result, list) else reports_result.get('items', [])

            if items:
                if len(items) > 1:
                    console.print(f"[yellow]Warning: Found multiple reports named '{identifier}'. Using the first one found ({items[0].id}).[/yellow]")
                console.print(f"[dim]Resolved report by name: '{identifier}' to ID {items[0].id}[/dim]")
                return items[0]
        except AttributeError:
             console.print(f"[yellow]Warning: Report.list_by_account_and_name does not seem to exist. Cannot resolve by name.[/yellow]")
             # Fall through to ID lookup only if it wasn't originally a UUID
        except Exception as e:
            console.print(f"[dim]Failed to get report by name \'{identifier}\': {e}. Trying by ID...[/dim]")
            # Fall through


    # Fallback or second attempt
    if not is_uuid: # Try ID if name lookup failed or wasn't attempted
        try:
            report_instance = Report.get_by_id(identifier, client=client)
            if report_instance and report_instance.accountId != account_id:
                 console.print(f"[yellow]Report found by ID, but belongs to a different account ({report_instance.accountId}).[/yellow]")
                 return None
            if report_instance:
                 console.print(f"[dim]Resolved report by ID after name lookup: {identifier}[/dim]")
                 return report_instance
        except Exception as e:
            console.print(f"[dim]Final attempt: Failed to get report by ID \'{identifier}\': {e}[/dim]")
    elif is_uuid: # Try Name if ID lookup failed initially
        try:
            # Assuming list_by_account_and_name exists
            reports_result = Report.list_by_account_and_name(
                account_id=account_id,
                name=identifier,
                client=client
            )
            items = reports_result if isinstance(reports_result, list) else reports_result.get('items', [])
            if items:
                if len(items) > 1:
                    console.print(f"[yellow]Warning: Found multiple reports named '{identifier}'. Using the first one found ({items[0].id}).[/yellow]")
                console.print(f"[dim]Resolved report by name after ID lookup: '{identifier}' to ID {items[0].id}[/dim]")
                return items[0]
        except AttributeError:
             console.print(f"[yellow]Warning: Report.list_by_account_and_name does not seem to exist. Cannot resolve by name.[/yellow]")
        except Exception as e:
             console.print(f"[dim]Final attempt: Failed to get report by name \'{identifier}\': {e}[/dim]")

    # If we reach here, report wasn't found or resolved correctly
    return None 