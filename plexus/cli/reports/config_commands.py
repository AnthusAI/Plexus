"""
Commands for managing Plexus Report Configurations.
"""

import click
import logging
import json
import traceback
from typing import Optional
import uuid

from rich.panel import Panel
from rich.syntax import Syntax
from rich.markup import escape
from gql.transport.exceptions import TransportQueryError
from rich.console import Group
from rich.text import Text

# Import necessary utilities and models
from plexus.cli.console import console
from plexus.cli.client_utils import create_client
from plexus.dashboard.api.models.report_configuration import ReportConfiguration
from plexus.dashboard.api.models.account import Account

# Import shared utility functions
from .utils import (
    resolve_account_id_for_command,
    resolve_report_config
)

logger = logging.getLogger(__name__)

@click.group()
def config():
    """Manage report configurations."""
    pass

@config.command(name="list")
@click.option('--account', 'account_identifier', help='Optional account key or ID to filter by.', default=None)
@click.option('--limit', type=int, default=50, help='Maximum number of configurations to list.')
def list_configs(account_identifier: Optional[str], limit: int):
    """List available Report Configurations for an account."""
    client = create_client()
    # Resolve account ID using the shared utility
    account_id = resolve_account_id_for_command(client, account_identifier)

    console.print(f"[cyan]Listing Report Configurations for Account ID: {account_id}[/cyan]")

    try:
        # Call the centralized model method to list configurations
        result_data = ReportConfiguration.list_by_account_id(
            account_id=account_id,
            client=client,
            limit=limit
        )
        # result_data is likely a dict like {'items': [...], 'nextToken': ...}
        config_objects = []
        if isinstance(result_data, dict):
            config_objects = result_data.get('items', [])
        elif isinstance(result_data, list):
             config_objects = result_data # Fallback
        else:
            console.print(f"[red]Unexpected data type returned by list_by_account_id: {type(result_data)}[/red]")
            return

        if not config_objects:
            console.print(f"[yellow]No report configurations found in the 'items' list for account {account_id}.[/yellow]")
            return

        # --- Display results using Panels --- #
        console.print(f"[bold]Found {len(config_objects)} Report Configuration(s) for Account: {account_id}[/bold]")
        for config_instance in config_objects:
            # Ensure we have a valid object (optional check, can be removed if confident)
            if not isinstance(config_instance, ReportConfiguration):
                logger.warning(f"Skipping unexpected item type in list results: {type(config_instance)}")
                continue

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

    except AttributeError as ae:
        # Catch attribute errors specifically, often happens if API returns unexpected data
        console.print(f"[bold red]Error processing report configuration data: {ae}[/bold red]")
        logger.error(f"Attribute error processing configurations: {ae}\n{traceback.format_exc()}")
    except Exception as e:
        console.print(f"[bold red]Error listing report configurations: {e}[/bold red]")
        logger.error(f"Failed to list report configurations: {e}\n{traceback.format_exc()}")

@config.command(name="create")
@click.option('--name', required=True, help='Name for the new Report Configuration.')
@click.option('--description', default="", help='Optional description.')
@click.option('--account', 'account_identifier', default=None, help='Account key or ID to associate with. Defaults to PLEXUS_ACCOUNT_KEY.')
@click.option('--file', 'config_file_path', type=click.Path(exists=True, dir_okay=False, readable=True), required=True, help='Path to the Markdown file containing the report configuration content.')
def create_config(name: str, description: str, account_identifier: Optional[str], config_file_path: str):
    """Create a new Report Configuration from a Markdown file."""
    client = create_client()
    # Resolve account ID using the shared utility
    account_id = resolve_account_id_for_command(client, account_identifier)

    console.print(f"[cyan]Creating Report Configuration \'{name}\' for Account ID: {account_id}...[/cyan]")

    try:
        # Read the configuration content from the file
        with open(config_file_path, 'r', encoding='utf-8') as f:
            configuration_content = f.read()
            # Log the actual content
            logger.info(f"Raw file content (first 100 chars): {configuration_content[:100]}")
            backslash_n = r'\n'
            newline = '\n'
            logger.info(f"Raw file content contains backslash-n: {backslash_n in configuration_content}")
            logger.info(f"Raw file content contains actual newlines: {newline in configuration_content}")

        # Validate if the content is not empty (basic check)
        if not configuration_content.strip():
             console.print(f"[red]Error: Configuration file \'{config_file_path}\' is empty.[/red]")
             raise click.Abort()

        # --- Check for Duplicates --- # (Using resolve_report_config helper)
        console.print(f"[dim]Checking for existing configurations named \'{name}\' in account {account_id}...[/dim]")
        existing_config = None
        try:
            # Use resolve_report_config to find by name (it handles ambiguity)
            existing_config = resolve_report_config(name, account_id, client)
        except Exception as e:
            logger.warning(f"Failed to check for existing configuration named \'{name}\': {e}")

        if existing_config:
            console.print(f"[yellow]Found existing configuration with the same name:[/yellow]")
            console.print(f"  ID: {existing_config.id}")
            console.print(f"  Name: {existing_config.name}")

            # Compare content
            if hasattr(existing_config, 'configuration') and existing_config.configuration == configuration_content:
                console.print(f"[bold yellow]Warning: An existing configuration with the name '{name}' and identical content already exists.[/bold yellow]")
                if not click.confirm("Do you want to proceed and create a duplicate configuration?", default=False):
                    console.print("[cyan]Operation cancelled by user.[/cyan]")
                    raise click.Abort()
            else:
                console.print(f"[bold yellow]Warning: An existing configuration with the name '{name}' but different content already exists.[/bold yellow]")
                if not click.confirm("Do you want to proceed and create a new configuration with this name?", default=False):
                    console.print("[cyan]Operation cancelled by user.[/cyan]")
                    raise click.Abort()
        else:
             console.print(f"[dim]No existing configuration found. Proceeding...[/dim]")
        # --- End Duplicate Check ---

        # Create the ReportConfiguration instance using the API client or model method
        new_config = ReportConfiguration.create(
            client=client,
            accountId=account_id,
            name=name,
            description=description,
            configuration=configuration_content
        )

        if new_config:
            # Log the content after creation
            logger.info(f"Config content after creation (first 100 chars): {new_config.configuration[:100]}")
            logger.info(f"Config content contains backslash-n: {backslash_n in new_config.configuration}")
            logger.info(f"Config content contains actual newlines: {newline in new_config.configuration}")
            escaped_id = escape(str(new_config.id))
            escaped_name = escape(str(new_config.name))
            escaped_account_id = escape(str(new_config.accountId))

            console.print(f"[bold]Successfully created Report Configuration:[/bold]")
            console.print(f"  ID: {escaped_id}")
            console.print(f"  Name: {escaped_name}")
            console.print(f"  Account ID: {escaped_account_id}")
        else:
            console.print(f"[red]Error: Failed to create report configuration \'{name}\'. API returned no object.[/red]")

    except FileNotFoundError:
         console.print(f"[red]Error: Configuration file not found at path: {config_file_path}[/red]")
    except IOError as e:
         console.print(f"[red]Error reading configuration file \'{config_file_path}\': {e}[/red]")
    except click.Abort:
        raise
    except Exception as e:
        escaped_error = escape(str(e))
        console.print(f"[bold red]Error creating report configuration: {escaped_error}[/bold red]")
        logger.error(f"Failed to create report configuration \'{name}\': {e}\n{traceback.format_exc()}")

@config.command(name="show")
@click.argument('id_or_name', type=str)
@click.option('--account', 'account_identifier', help='Optional account key or ID for context (needed for name lookup).', default=None)
def show_config(id_or_name: str, account_identifier: Optional[str]):
    """Display details of a specific Report Configuration."""
    client = create_client()
    # Resolve account ID using the shared utility
    acc_id_for_lookup = resolve_account_id_for_command(client, account_identifier)

    console.print(f"Showing Report Configuration '{id_or_name}' for account: [cyan]{acc_id_for_lookup}[/cyan]")

    try:
        # Use the helper function to resolve by ID or Name
        config_instance = resolve_report_config(id_or_name, acc_id_for_lookup, client)

        if not config_instance:
            console.print(f"[yellow]Report Configuration '{id_or_name}' not found for account {acc_id_for_lookup}.[/yellow]")
            return

        # --- Display using Panel with Nested Content --- #
        created_at_str = config_instance.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC") if config_instance.createdAt else 'N/A'
        updated_at_str = config_instance.updatedAt.strftime("%Y-%m-%d %H:%M:%S UTC") if config_instance.updatedAt else 'N/A'

        # Create metadata text
        metadata_text = Text.assemble(
            ("Name:", "bold magenta"), f"        {escape(config_instance.name)}\n",
            ("ID:", "bold cyan"), f"          {config_instance.id}\n",
            ("Description:", "bold green"), f" {escape(config_instance.description or '-')}\n",
            ("Created At:", "bold blue"), f"  {created_at_str}\n",
            ("Updated At:", "bold blue"), f"  {updated_at_str}"
        )

        # Create content panel (or placeholder)
        if config_instance.configuration:
            content_syntax = Syntax(config_instance.configuration, "markdown", theme="default", line_numbers=True)
            content_panel = Panel(
                content_syntax,
                title="[yellow]Configuration Content[/yellow]",
                border_style="yellow",
                expand=True # Expand content panel horizontally
            )
        else:
            content_panel = Text("[dim]Configuration content is empty.[/dim]")

        # Group metadata and content panel
        group = Group(
            metadata_text,
            "", # Add a blank line for spacing
            content_panel
        )

        # Print the main panel containing the group
        console.print(
            Panel(
                group,
                title=f"[bold]Report Configuration Details[/bold]",
                border_style="blue",
                expand=True # Allow main panel to expand
            )
        )
        # --- End Panel Display ---

    except Exception as e:
        console.print(f"[bold red]Error retrieving report configuration '{id_or_name}': {e}[/bold red]")
        logger.error(f"Failed to show report configuration: {e}\n{traceback.format_exc()}")

@config.command(name="delete")
@click.argument('id_or_name', type=str)
@click.option('--account', 'account_identifier', default=None, help='Account key or ID context (needed for name lookup). Defaults to PLEXUS_ACCOUNT_KEY.')
@click.option('--yes', is_flag=True, expose_value=True, help='Skip confirmation prompt.')
def delete_config(id_or_name: str, account_identifier: Optional[str], yes: bool):
    """Delete a specific Report Configuration by ID or Name."""
    client = create_client()
    # Resolve account ID using the shared utility
    account_id = resolve_account_id_for_command(client, account_identifier)

    console.print(f"Attempting to delete Report Configuration: [cyan]'{id_or_name}'[/cyan] in Account [cyan]{account_id}[/cyan]...")

    # --- Resolve the configuration(s) to be deleted --- # (Uses resolve_report_config)
    configs_to_delete = []
    try:
        # Try resolving as a single config first (ID or unique name)
        single_resolved = resolve_report_config(id_or_name, account_id, client)

        if single_resolved:
            configs_to_delete.append(single_resolved)
            console.print(f"[dim]Found matching config by ID/unique name.[/dim]")
        else:
            # If not resolved as single, check if it was a UUID that wasn't found
            is_uuid = False
            try:
                uuid.UUID(id_or_name)
                is_uuid = True
            except ValueError:
                pass
            if is_uuid:
                # If it was a UUID but not found, exit.
                console.print(f"[yellow]Report Configuration ID '{id_or_name}' not found in account {account_id}.[/yellow]")
                return
            else:
                # If not a UUID and not found by unique name, list by name to find multiples
                console.print(f"[dim]Identifier not found as unique ID/name. Checking for multiple matches by name '{id_or_name}'...[/dim]")
                # Note: Requires ReportConfiguration.list_by_account_and_name
                # Or adapt to use list_by_account_id and filter client-side if list_by_name doesn't exist
                try:
                    all_configs_data = ReportConfiguration.list_by_account_id(account_id=account_id, client=client, limit=1000)
                    all_configs_items = all_configs_data # Assign directly
                    for config_item in all_configs_items:
                        if hasattr(config_item, 'name') and config_item.name == id_or_name:
                            configs_to_delete.append(config_item)
                except Exception as list_e:
                     console.print(f"[red]Error listing configurations to check for name matches: {list_e}[/red]")
                     raise click.Abort() # Abort if listing fails

            if not configs_to_delete:
                 console.print(f"[yellow]Report Configuration name '{id_or_name}' not found in account {account_id}.[/yellow]")
                 return

    except Exception as e:
        console.print(f"[bold red]Error resolving report configuration '{id_or_name}': {e}[/bold red]")
        logger.error(f"Failed to resolve report configuration for deletion: {e}\n{traceback.format_exc()}")
        raise click.Abort()
    # --- End Resolution --- #

    if not configs_to_delete:
         console.print(f"[yellow]Report Configuration '{id_or_name}' not found in account {account_id}.[/yellow]")
         return

    console.print(f"[yellow]Found {len(configs_to_delete)} configuration(s) matching '{id_or_name}'.[/yellow]")

    success_count = 0
    fail_count = 0
    skip_count = 0

    # Define the GraphQL Mutation String Once
    delete_mutation_string = """
        mutation DeleteReportConfiguration($input: DeleteReportConfigurationInput!) {
            deleteReportConfiguration(input: $input) {
                id
            }
        }
    """

    for config_instance in configs_to_delete:
        console.print(f"Processing configuration: [bold]{config_instance.name}[/bold] (ID: {config_instance.id})")

        if not yes:
            if not click.confirm(f"  -> Delete this configuration?", default=False):
                console.print("  [yellow]Skipping deletion.[/yellow]")
                skip_count += 1
                continue
        elif success_count == 0 and fail_count == 0 and skip_count == 0:
             console.print("[yellow]Skipping confirmation prompt for all items due to --yes flag.[/yellow]")

        try:
            variables = {
                "input": {
                    "id": config_instance.id
                }
            }
            console.print(f"  [dim]Sending delete request for ID: {config_instance.id}...[/dim]")
            result = client.execute(delete_mutation_string, variables=variables)

            deleted_id = result.get('deleteReportConfiguration', {}).get('id')
            if deleted_id == config_instance.id:
                 console.print(f"  [green]Successfully deleted.[/green]")
                 success_count += 1
            else:
                 console.print(f"  [yellow]Deletion mutation succeeded but response confirmation missing/mismatched. Result: {result}[/yellow]")
                 logger.warning(f"Deletion confirmation mismatch for {config_instance.id}. Response: {result}")
                 success_count += 1
        except TransportQueryError as gql_err:
            error_message = "Unknown GraphQL error"
            if hasattr(gql_err, 'errors') and gql_err.errors:
                error_message = gql_err.errors[0].get('message', str(gql_err.errors[0]))
            console.print(f"  [bold red]Error deleting (GraphQL): {error_message}[/bold red]")
            logger.error(f"Failed GraphQL deletion for {config_instance.id}: {gql_err.errors if hasattr(gql_err, 'errors') else gql_err}")
            fail_count += 1
        except Exception as e:
            console.print(f"  [bold red]Error deleting: {e}[/bold red]")
            logger.error(f"Failed to delete report configuration {config_instance.id}: {e}\n{traceback.format_exc()}")
            fail_count += 1

    # Print summary
    console.print("--- Deletion Summary ---")
    console.print(f"Successfully deleted: {success_count}")
    console.print(f"Skipped: {skip_count}")
    console.print(f"Failed: {fail_count}") 