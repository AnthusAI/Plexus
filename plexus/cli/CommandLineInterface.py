import click
import os
import time
from dotenv import load_dotenv
from celery import Celery
from plexus.CustomLogging import logging
from kombu.utils.url import safequote
import sys
import rich
from rich.table import Table
from rich.console import Console
import importlib
import builtins
import json
import random
import numpy as np
import threading
import yaml
import logging
import boto3
from botocore.config import Config
from datetime import datetime, timezone, timedelta
from collections import OrderedDict
from typing import Optional
from sklearn.metrics import (
    confusion_matrix,
    accuracy_score
)

from .DataCommands import data
from .EvaluationCommands import evaluate, evaluations
from .TrainingCommands import train
from .ReportingCommands import report
from .PredictionCommands import predict
from .TuningCommands import tuning
from .AnalyzeCommands import analyze
from .console import console
from .BatchCommands import batch
from .CommandDispatch import command
from .TaskCommands import tasks

# Import dashboard-specific modules
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.evaluation import Evaluation
from plexus.dashboard.api.models.scorecard import Scorecard
from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.score_result import ScoreResult
from plexus.dashboard.api.models.task import Task
from plexus.dashboard.api.models.task_stage import TaskStage
from plexus.dashboard.commands.simulate import (
    generate_class_distribution,
    simulate_prediction,
    select_metrics_and_explanation,
    calculate_metrics,
    select_num_classes,
    SCORE_GOALS,
    CLASS_SETS
)

# Import centralized logging configuration
from plexus.CustomLogging import setup_logging

# Use centralized logging configuration
setup_logging()
logger = logging.getLogger(__name__)

# Constants from dashboard CLI
SCORE_TYPES = ['binary', 'multiclass']
DATA_BALANCES = ['balanced', 'unbalanced']

def generate_key(name: str) -> str:
    """Generate a URL-safe key from a name."""
    return name.lower().replace(' ', '-')

def create_client() -> PlexusDashboardClient:
    """Create a client and log its configuration"""
    client = PlexusDashboardClient()
    logger.debug(f"Using API URL: {client.api_url}")
    return client

class OrderCommands(click.Group):
    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands)

@click.group(cls=OrderCommands)
def cli():
    """
    Plexus CLI for managing scorecards, scores, and evaluations.
    """
    pass

# Add original commands
cli.add_command(data)
cli.add_command(evaluate)
cli.add_command(train)
cli.add_command(report)
cli.add_command(predict)
cli.add_command(tuning)
cli.add_command(analyze)
cli.add_command(batch)
cli.add_command(command)

# Dashboard CLI Commands
cli.add_command(evaluations)
cli.add_command(tasks)

@cli.group()
def scores():
    """Manage score results"""
    pass

@scores.command()
@click.option('--value', type=float, required=True, help='Score value')
@click.option('--item-id', required=True, help='ID of the item being scored')
@click.option('--account-id', required=True, help='ID of the account')
@click.option('--scoring-job-id', required=True, help='ID of the scoring job')
@click.option('--scorecard-id', required=True, help='ID of the scorecard')
@click.option('--confidence', type=float, help='Confidence score (optional)')
@click.option('--metadata', type=str, help='JSON metadata (optional)')
def create_score(value, item_id, account_id, scoring_job_id, scorecard_id, confidence, metadata):
    """Create a new dashboard score result"""
    # ... [rest of the create_score function implementation] ...

@cli.group()
def scorecards():
    """Manage scorecards"""
    pass

@scorecards.command()
@click.argument('account')
@click.option('--name', help='Filter by scorecard name')
@click.option('--key', help='Filter by scorecard key')
@click.option('--columns', type=int, default=1, help='Number of columns to display')
@click.option('--show-scores/--hide-scores', default=True, help='Show sub-scores for each scorecard')
@click.option('--debug', is_flag=True, help='Show debug information')
def list(account: str, name: Optional[str], key: Optional[str], columns: int, show_scores: bool, debug: bool):
    """List dashboard scorecards with optional filtering.
    
    ACCOUNT: Account name, key, or ID to scope the query
    """
    client = create_client()
    console.print("[bold]Fetching scorecards...[/bold]")
    
    try:
        # Try to identify the account by name, key, or ID
        account_id = None
        account_name = None
        account_key = None
        
        # First try as key (most common)
        if debug:
            console.print(f"[dim]DEBUG: Trying to find account with key '{account}'[/dim]")
        account_obj = client.Account.get_by_key(account)
        
        # If not found, try as ID
        if not account_obj:
            if debug:
                console.print(f"[dim]DEBUG: Not found by key, trying as ID[/dim]")
            try:
                account_obj = client.Account.get_by_id(account)
            except Exception:
                account_obj = None
        
        # If still not found, try by name (using GraphQL query)
        if not account_obj:
            if debug:
                console.print(f"[dim]DEBUG: Not found by ID, trying as name[/dim]")
            try:
                query = """
                query GetAccountByName($name: String!) {
                    listAccounts(filter: { name: { eq: $name } }) {
                        items {
                            id
                            name
                            key
                        }
                    }
                }
                """
                result = client.execute(query, {"name": account})
                accounts = result.get('listAccounts', {}).get('items', [])
                if accounts:
                    # Use the first matching account
                    from plexus.dashboard.api.models.account import Account
                    account_obj = Account.from_dict(accounts[0], client)
            except Exception as e:
                if debug:
                    console.print(f"[red]DEBUG ERROR: Error searching by name: {str(e)}[/red]")
                account_obj = None
        
        # If account not found by any method, exit
        if not account_obj:
            console.print(f"[bold red]Error:[/bold red] Account '{account}' not found by key, ID, or name.")
            return
        
        # Set account details
        account_id = account_obj.id
        account_name = account_obj.name
        account_key = account_obj.key
        
        console.print(f"Using account: [bold]{account_name}[/bold] (Key: {account_key}, ID: {account_id})")
        
        # Build filter for GraphQL query
        filter_dict = {"accountId": {"eq": account_id}}
        if name:
            filter_dict["name"] = {"contains": name}
        if key:
            filter_dict["key"] = {"contains": key}
        
        # Construct and execute GraphQL query
        from plexus.dashboard.api.models.scorecard import Scorecard
        from plexus.dashboard.api.models.account import Account
        from rich.panel import Panel
        from rich.table import Table
        from rich.columns import Columns
        from rich.text import Text
        from rich.console import Group
        from rich.tree import Tree
        
        query = """
        query ListScorecards($filter: ModelScorecardFilterInput) {
            listScorecards(filter: $filter) {
                items {
                    %s
                }
            }
        }
        """ % Scorecard.fields()
        
        variables = {"filter": filter_dict}
        result = client.execute(query, variables)
        scorecards = result.get('listScorecards', {}).get('items', [])
        
        if not scorecards:
            console.print(f"[yellow]No scorecards found for account '{account_name}' matching the criteria.[/yellow]")
            return
        
        # Sort scorecards by name for consistent display
        sorted_scorecards = sorted([Scorecard.from_dict(sc, client) for sc in scorecards], 
                                  key=lambda x: x.name.lower())
        
        console.print(f"\n[bold]Found {len(sorted_scorecards)} scorecards for account '{account_name}':[/bold]\n")
        
        # Fetch sections and scores for all scorecards if show_scores is enabled
        scorecard_sections = {}
        if show_scores:
            for sc in sorted_scorecards:
                try:
                    if debug:
                        console.print(f"[dim]DEBUG: Fetching sections for scorecard {sc.id} ({sc.name})[/dim]")
                    
                    # Use GraphQL to fetch sections and scores
                    sections_query = """
                    query GetScorecardSections($scorecardId: String!) {
                        listScorecardSections(filter: { scorecardId: { eq: $scorecardId } }) {
                            items {
                                id
                                name
                                order
                            }
                        }
                    }
                    """
                    sections_result = client.execute(sections_query, {"scorecardId": sc.id})
                    sections = sections_result.get('listScorecardSections', {}).get('items', [])
                    
                    if debug:
                        console.print(f"[dim]DEBUG: Found {len(sections)} sections for scorecard {sc.name}[/dim]")
                    
                    scorecard_sections[sc.id] = []
                    
                    # For each section, fetch its scores
                    for section in sections:
                        if debug:
                            console.print(f"[dim]DEBUG: Fetching scores for section {section['id']} ({section['name']})[/dim]")
                        
                        scores_query = """
                        query GetSectionScores($sectionId: String!) {
                            listScores(filter: { sectionId: { eq: $sectionId } }) {
                                items {
                                    id
                                    name
                                    key
                                    order
                                    type
                                }
                            }
                        }
                        """
                        scores_result = client.execute(scores_query, {"sectionId": section['id']})
                        scores = scores_result.get('listScores', {}).get('items', [])
                        
                        if debug:
                            console.print(f"[dim]DEBUG: Found {len(scores)} scores for section {section['name']}[/dim]")
                        
                        scorecard_sections[sc.id].append({
                            'section': section,
                            'scores': scores
                        })
                except Exception as e:
                    error_msg = f"Error fetching sections for scorecard {sc.id}: {str(e)}"
                    logger.error(error_msg)
                    if debug:
                        console.print(f"[red]DEBUG ERROR: {error_msg}[/red]")
                    scorecard_sections[sc.id] = []
        
        # Process scorecards in batches for columns display
        batch_size = min(columns, len(sorted_scorecards))  # Use the smaller of columns or total scorecards
        
        for i in range(0, len(sorted_scorecards), batch_size):
            batch = sorted_scorecards[i:i+batch_size]
            panels = []
            
            for scorecard in batch:
                # Create a table for the scorecard details
                table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
                table.add_column("Field", style="cyan bold")
                table.add_column("Value")
                
                # Add rows for each field in the specified order
                table.add_row("Name", f"[bold]{scorecard.name}[/bold]")
                table.add_row("Key", f"[sky_blue]{scorecard.key or '-'}[/sky_blue]")
                table.add_row("External ID", f"[magenta]{scorecard.externalId or '-'}[/magenta]")
                table.add_row("Account", f"{account_key} ([dim]{account_id}[/dim])")
                
                # Add description (potentially multi-line)
                description = scorecard.description or "-"
                table.add_row("Description", description)
                
                # Get sections and scores for this scorecard
                sections_data = scorecard_sections.get(scorecard.id, [])
                
                # Calculate total score count
                score_count = sum(len(section_data['scores']) for section_data in sections_data)
                
                # Add score count
                table.add_row("Score Count", f"[bold green]{score_count}[/bold green]")
                
                # Add scores tree if requested
                if show_scores and sections_data:
                    # Create a tree with a "Scores" header
                    scores_tree = Tree(" [bold]Scores[/bold]")
                    has_scores = False
                    
                    for section_data in sorted(sections_data, key=lambda s: s['section']['order']):
                        section = section_data['section']
                        scores = section_data['scores']
                        
                        # Always show the section, even if it has no scores
                        section_branch = scores_tree.add(f"[bold]{section['name']}[/bold] ({len(scores)})")
                        
                        if scores:
                            has_scores = True
                            for score in sorted(scores, key=lambda s: s['order']):
                                score_text = f"[sky_blue]{score['name']}[/sky_blue]"
                                if score.get('key'):
                                    score_text += f" ([dim]{score['key']}[/dim])"
                                section_branch.add(score_text)
                        else:
                            section_branch.add("[italic dim]No scores defined[/italic dim]")
                    
                    # Add the scores tree to the table, spanning both columns
                    if has_scores:
                        # Add a separator row
                        table.add_row("", "")
                
                # Create a header with the scorecard ID
                header = Text.from_markup(f"ID: {scorecard.id}")
                header.stylize("dim")
                
                # Create the content for the panel
                content = table
                
                # If we have scores, add them after the table to span the full width
                if show_scores and sections_data and has_scores:
                    # Remove the extra padding to fix alignment
                    content = Group(table, scores_tree)
                
                # Create a panel with the content
                panel = Panel(
                    content,
                    title=header,
                    subtitle=f"Scorecard {i+batch.index(scorecard)+1}/{len(sorted_scorecards)}",
                    border_style="blue",
                    expand=True,
                    padding=(1, 2)
                )
                panels.append(panel)
            
            # Display the panels in columns
            console.print(Columns(panels, equal=True, expand=True))
            
            # Add spacing between batches
            if i + batch_size < len(sorted_scorecards):
                console.print()
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        logger.error(f"Error listing scorecards: {str(e)}", exc_info=True)

@scorecards.command()
@click.option('--account-key', default='call-criteria', help='Account key identifier')
@click.option('--directory', default='scorecards', help='Directory containing YAML scorecard files')
def sync(account_key: str, directory: str):
    """Sync YAML scorecards to the dashboard API"""
    # ... [rest of the sync function implementation] ...

@scorecards.command()
@click.option('--account-key', required=True, help='Account key')
@click.option('--scorecard-key', help='Filter by scorecard key')
@click.option('--score-key', help='Filter by score key')
@click.option('--directory', default='scorecards', help='Directory to save YAML files')
def pull(account_key: str, scorecard_key: Optional[str], score_key: Optional[str], directory: str):
    """Download latest champion version of scores to local YAML files.
    
    Examples:
        plexus scorecards pull --account-key my-account
        plexus scorecards pull --account-key my-account --scorecard-key my-scorecard
        plexus scorecards pull --account-key my-account --score-key my-score
        plexus scorecards pull --account-key my-account --directory path/to/save
    """
    logger.info("This command will be implemented to download champion versions of scores")
    logger.info(f"Parameters: account_key={account_key}, scorecard_key={scorecard_key}, score_key={score_key}, directory={directory}")
    click.echo("The 'pull' command is not yet implemented. Coming soon!")

@scorecards.command()
@click.option('--account-key', required=True, help='Account key')
@click.option('--directory', default='scorecards', help='Directory containing YAML scorecard files')
@click.option('--comment', help='Comment for the new version')
def push(account_key: str, directory: str, comment: Optional[str]):
    """Upload local YAML changes as new versions.
    
    Examples:
        plexus scorecards push --account-key my-account
        plexus scorecards push --account-key my-account --directory path/to/scorecards
        plexus scorecards push --account-key my-account --comment "Updated configuration"
    """
    logger.info("This command will be implemented to upload local changes as new versions")
    logger.info(f"Parameters: account_key={account_key}, directory={directory}, comment={comment}")
    click.echo("The 'push' command is not yet implemented. Coming soon!")

@scorecards.command()
@click.option('--account-key', required=True, help='Account key')
@click.option('--scorecard-key', help='Filter by scorecard key')
@click.option('--score-key', help='Filter by score key')
@click.option('--score-id', help='Filter by score ID')
def history(account_key: str, scorecard_key: Optional[str], score_key: Optional[str], score_id: Optional[str]):
    """View version history for scores.
    
    Examples:
        plexus scorecards history --account-key my-account
        plexus scorecards history --account-key my-account --scorecard-key my-scorecard
        plexus scorecards history --account-key my-account --score-key my-score
        plexus scorecards history --account-key my-account --score-id 123456
    """
    logger.info("This command will be implemented to view version history")
    logger.info(f"Parameters: account_key={account_key}, scorecard_key={scorecard_key}, score_key={score_key}, score_id={score_id}")
    click.echo("The 'history' command is not yet implemented. Coming soon!")

@scorecards.command()
@click.option('--account-key', required=True, help='Account key')
@click.option('--score-id', required=True, help='Score ID')
@click.option('--version-id', required=True, help='Version ID to promote')
def promote(account_key: str, score_id: str, version_id: str):
    """Promote a specific version to champion.
    
    Examples:
        plexus scorecards promote --account-key my-account --score-id 123456 --version-id 789012
    """
    logger.info("This command will be implemented to promote versions to champion")
    logger.info(f"Parameters: account_key={account_key}, score_id={score_id}, version_id={version_id}")
    click.echo("The 'promote' command is not yet implemented. Coming soon!")

@scorecards.command()
@click.option('--account-key', required=True, help='Account key')
@click.option('--fix', is_flag=True, help='Fix duplicates by removing newer copies')
def find_duplicates(account_key: str, fix: bool):
    """Find and optionally fix duplicate scores based on name+order+section combination"""
    # ... [rest of the find_duplicates function implementation] ...

@scorecards.command()
@click.option('--scorecard-id', help='Scorecard ID')
@click.option('--scorecard-key', help='Scorecard key')
@click.option('--scorecard-name', help='Scorecard name')
def list_scores(scorecard_id: Optional[str], scorecard_key: Optional[str], scorecard_name: Optional[str]):
    """List all scores for a specific dashboard scorecard"""
    # ... [rest of the list_scores function implementation] ...

def load_plexus_extensions():
    """Load Plexus extensions from the plexus_extensions directory"""
    logger.debug("Loading Plexus extensions...")
    extensions_path = os.path.join(os.getcwd(), 'plexus_extensions')
    
    if os.path.isdir(extensions_path):
        sys.path.insert(0, extensions_path)
        sys.path.insert(0, os.path.join(os.getcwd(), '.'))

        for root, _, files in os.walk(extensions_path):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    logger.debug(f"Loading extension: {file}")
                    module_name = file[:-3]
                    imported_module = importlib.import_module(module_name)
                    logger.debug(f"Loaded extension module: {module_name}")
                    
                    for attr_name in dir(imported_module):
                        attr = getattr(imported_module, attr_name)
                        if isinstance(attr, type):
                            setattr(builtins, attr_name, attr)
                            logger.debug(f"Registered class {attr_name} globally in builtins")
    else:
        logger.debug("No extensions folder found.")

# Call this function during CLI initialization
load_plexus_extensions()

@click.group()
def tasks():
    """Manage task records in the dashboard"""
    pass

@tasks.command()
@click.option('--account-id', help='Filter by account ID')
@click.option('--status', help='Filter by status (PENDING, RUNNING, COMPLETED, FAILED)')
@click.option('--type', help='Filter by task type')
def list(account_id: Optional[str], status: Optional[str], type: Optional[str]):
    """List tasks with optional filtering"""
    client = create_client()
    
    # Build filter conditions
    filter_conditions = []
    if account_id:
        filter_conditions.append(f'accountId: {{ eq: "{account_id}" }}')
    if status:
        filter_conditions.append(f'status: {{ eq: "{status}" }}')
    if type:
        filter_conditions.append(f'type: {{ eq: "{type}" }}')
    
    filter_str = ", ".join(filter_conditions)
    if filter_str:
        filter_str = f"filter: {{ {filter_str} }}"
    
    query = f"""
    query ListTasks({filter_str}) {{
        listTasks({filter_str}) {{
            items {{
                {Task.fields()}
            }}
        }}
    }}
    """
    
    result = client.execute(query)
    tasks = result.get('listTasks', {}).get('items', [])
    
    # Create a rich table for display
    table = rich.table.Table(show_header=True, header_style="bold magenta")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Target")
    table.add_column("Command")
    table.add_column("Created")
    table.add_column("Updated")
    
    for task_data in tasks:
        task = Task.from_dict(task_data, client)
        table.add_row(
            task.id,
            task.type,
            task.status,
            task.target,
            task.command,
            task.createdAt.strftime("%Y-%m-%d %H:%M:%S") if task.createdAt else "",
            task.updatedAt.strftime("%Y-%m-%d %H:%M:%S") if task.updatedAt else ""
        )
    
    console.print(table)

@tasks.command()
@click.option('--task-id', help='Delete a specific task by ID')
@click.option('--account-id', help='Delete all tasks for an account')
@click.option('--status', help='Delete tasks with specific status')
@click.option('--type', help='Delete tasks of specific type')
@click.option('--force', is_flag=True, help='Skip confirmation prompt')
def delete(task_id: Optional[str], account_id: Optional[str], status: Optional[str], type: Optional[str], force: bool):
    """Delete tasks and their stages"""
    client = create_client()
    
    # Build filter conditions for listing tasks to delete
    filter_conditions = []
    if task_id:
        filter_conditions.append(f'id: {{ eq: "{task_id}" }}')
    if account_id:
        filter_conditions.append(f'accountId: {{ eq: "{account_id}" }}')
    if status:
        filter_conditions.append(f'status: {{ eq: "{status}" }}')
    if type:
        filter_conditions.append(f'type: {{ eq: "{type}" }}')
    
    filter_str = ", ".join(filter_conditions)
    if filter_str:
        filter_str = f"filter: {{ {filter_str} }}"
    
    # First list tasks that will be deleted
    query = f"""
    query ListTasks({filter_str}) {{
        listTasks({filter_str}) {{
            items {{
                {Task.fields()}
            }}
        }}
    }}
    """
    
    result = client.execute(query)
    tasks = result.get('listTasks', {}).get('items', [])
    
    if not tasks:
        console.print("[yellow]No tasks found matching the criteria[/yellow]")
        return
    
    # Show tasks that will be deleted
    table = rich.table.Table(show_header=True, header_style="bold red")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Target")
    table.add_column("Command")
    
    for task_data in tasks:
        task = Task.from_dict(task_data, client)
        table.add_row(
            task.id,
            task.type,
            task.status,
            task.target,
            task.command
        )
    
    console.print("\n[bold red]The following tasks will be deleted:[/bold red]")
    console.print(table)
    
    # Get confirmation unless --force is used
    if not force:
        confirm = click.confirm("\nAre you sure you want to delete these tasks?", default=False)
        if not confirm:
            console.print("[yellow]Operation cancelled[/yellow]")
            return
    
    # Delete tasks and their stages
    deleted_count = 0
    for task_data in tasks:
        task = Task.from_dict(task_data, client)
        
        # First delete all stages
        stages = task.get_stages()
        for stage in stages:
            mutation = """
            mutation DeleteTaskStage($input: DeleteTaskStageInput!) {
                deleteTaskStage(input: { id: $input }) {
                    id
                }
            }
            """
            client.execute(mutation, {'input': stage.id})
        
        # Then delete the task
        mutation = """
        mutation DeleteTask($input: DeleteTaskInput!) {
            deleteTask(input: { id: $input }) {
                id
            }
        }
        """
        client.execute(mutation, {'input': task.id})
        deleted_count += 1
    
    console.print(f"\n[green]Successfully deleted {deleted_count} tasks and their stages[/green]")

def main():
    """Entry point for the Plexus CLI."""
    cli(standalone_mode=False)