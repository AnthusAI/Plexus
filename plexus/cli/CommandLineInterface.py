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
from typing import Optional, Tuple, List, Dict, Any
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
@click.option('--fast', is_flag=True, help='Skip fetching sections and scores for faster results')
@click.option('--debug', is_flag=True, help='Show debug information')
def list(account: str, name: Optional[str], key: Optional[str], columns: int, show_scores: bool, fast: bool, debug: bool):
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
        from tqdm import tqdm
        
        # If fast mode is enabled or scores are hidden, use a simpler query
        if fast or not show_scores:
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
            if debug:
                console.print(f"[dim]DEBUG: Executing query in fast mode[/dim]")
            
            result = client.execute(query, variables)
            scorecards = result.get('listScorecards', {}).get('items', [])
            
            if fast and show_scores:
                console.print("[yellow]Fast mode enabled: Skipping section and score fetching[/yellow]")
        else:
            # Use a comprehensive query that fetches scorecards, sections, and scores in one go
            query = """
            query ListScorecardsWithSectionsAndScores($filter: ModelScorecardFilterInput) {
                listScorecards(filter: $filter) {
                    items {
                        id
                        name
                        key
                        externalId
                        description
                        accountId
                        sections {
                            items {
                                id
                                name
                                order
                                scores {
                                    items {
                                        id
                                        name
                                        key
                                        order
                                        type
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """
            
            variables = {"filter": filter_dict}
            if debug:
                console.print(f"[dim]DEBUG: Executing comprehensive query to fetch scorecards, sections, and scores in one go[/dim]")
            
            console.print("[bold]Fetching scorecards with sections and scores...[/bold]")
            result = client.execute(query, variables)
            scorecards = result.get('listScorecards', {}).get('items', [])
        
        if not scorecards:
            console.print(f"[yellow]No scorecards found for account '{account_name}' matching the criteria.[/yellow]")
            return
        
        # Sort scorecards by name for consistent display
        sorted_scorecards = sorted([Scorecard.from_dict(sc, client) for sc in scorecards], 
                                  key=lambda x: x.name.lower())
        
        console.print(f"\n[bold]Found {len(sorted_scorecards)} scorecards for account '{account_name}':[/bold]\n")
        
        # Process scorecards in batches for columns display
        batch_size = min(columns, len(sorted_scorecards))
        
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
                sections_data = []
                score_count = 0
                
                if not fast and show_scores and hasattr(scorecard, 'sections') and scorecard.sections:
                    # Process sections and scores from the comprehensive query result
                    for section in sorted(scorecard.sections.get('items', []), key=lambda s: s.get('order', 0)):
                        scores = section.get('scores', {}).get('items', [])
                        sections_data.append({
                            'section': section,
                            'scores': scores
                        })
                        score_count += len(scores)
                
                # Add score count
                if not fast:
                    table.add_row("Score Count", f"[bold green]{score_count}[/bold green]")
                else:
                    table.add_row("Score Count", "[dim](not fetched in fast mode)[/dim]")
                
                # Add scores tree if requested
                if show_scores and sections_data:
                    # Create a tree with a "Scores" header
                    scores_tree = Tree(" [bold]Scores[/bold]")
                    has_scores = False
                    
                    for section_data in sorted(sections_data, key=lambda s: s['section'].get('order', 0)):
                        section = section_data['section']
                        scores = section_data['scores']
                        
                        # Always show the section, even if it has no scores
                        section_branch = scores_tree.add(f"[bold]{section.get('name', 'Unnamed Section')}[/bold] ({len(scores)})")
                        
                        if scores:
                            has_scores = True
                            for score in sorted(scores, key=lambda s: s.get('order', 0)):
                                score_text = f"[sky_blue]{score.get('name', 'Unnamed Score')}[/sky_blue]"
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
        if debug:
            import traceback
            console.print(traceback.format_exc())

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

@scorecards.command()
@click.argument('score')
@click.option('--account', help='Account identifier (name, key, or ID) to scope the search')
@click.option('--scorecard', help='Scorecard identifier (name, key, or ID) to scope the search')
@click.option('--show-versions', is_flag=True, help='Show version history')
@click.option('--show-config', is_flag=True, help='Show score configuration')
@click.option('--debug', is_flag=True, help='Show debug information')
def score(score: str, account: Optional[str], scorecard: Optional[str],
          show_versions: bool, show_config: bool, debug: bool):
    """Display information about a single score.
    
    SCORE: Score identifier (ID, key, name, or external ID)
    
    Examples:
        plexus scorecards score "Term Explanation"
        plexus scorecards score term-explanation
        plexus scorecards score "Term Explanation" --account call-criteria
        plexus scorecards score "Term Explanation" --scorecard "Term Life AI 1.0"
    """
    client = create_client()
    
    try:
        # Step 1: Resolve account if provided
        account_id = None
        if account:
            account_obj, error = resolve_account(client, account, debug)
            if error:
                console.print(f"[bold red]Error:[/bold red] {error}")
                return
            
            account_id = account_obj.id
            if debug:
                console.print(f"[dim]DEBUG: Resolved account '{account}' to ID '{account_id}'[/dim]")
        
        # Step 2: Resolve scorecard if provided
        scorecard_id = None
        if scorecard:
            scorecard_obj, error = resolve_scorecard(client, scorecard, account_id, debug)
            if error:
                console.print(f"[bold red]Error:[/bold red] {error}")
                return
            
            scorecard_id = scorecard_obj.id
            if debug:
                console.print(f"[dim]DEBUG: Resolved scorecard '{scorecard}' to ID '{scorecard_id}'[/dim]")
            
        # Step 3: Get sections if scorecard is provided
        section_ids = None
        if scorecard_id:
            sections_query = """
            query GetSections($scorecardId: String!) {
                listScorecardSections(filter: {scorecardId: {eq: $scorecardId}}) {
                    items {
                        id
                    }
                }
            }
            """
            
            result = client.execute(sections_query, {"scorecardId": scorecard_id})
            sections = result.get('listScorecardSections', {}).get('items', [])
            
            if not sections:
                console.print(f"[bold red]Error:[/bold red] No sections found for scorecard")
                return
            
            section_ids = [section['id'] for section in sections]
            if debug:
                console.print(f"[dim]DEBUG: Found {len(section_ids)} sections for scorecard[/dim]")
        
        # Step 4: Resolve score
        score_data, error = resolve_score(client, score, section_ids, debug)
        if error:
            console.print(f"[bold red]Error:[/bold red] {error}")
            return
        
        # Display the score information
        from rich.panel import Panel
        from rich.tree import Tree
        from rich.table import Table
        from rich.text import Text
        
        # Create a tree for hierarchical display
        score_tree = Tree(f"[bold]{score_data['name']}[/bold]")
        
        # Add basic information
        score_tree.add(f"ID: {score_data['id']}")
        if score_data.get('key'):
            score_tree.add(f"Key: {score_data['key']}")
        if score_data.get('externalId'):
            score_tree.add(f"External ID: {score_data['externalId']}")
        if score_data.get('description'):
            score_tree.add(f"Description: {score_data['description']}")
        score_tree.add(f"Type: {score_data['type']}")
        score_tree.add(f"Order: {score_data.get('order', 'N/A')}")
        
        # Add section and scorecard information
        if score_data.get('section'):
            section = score_data['section']
            section_branch = score_tree.add("Section")
            section_branch.add(f"ID: {section['id']}")
            section_branch.add(f"Name: {section['name']}")
            section_branch.add(f"Order: {section['order']}")
            
            if section.get('scorecard'):
                scorecard = section['scorecard']
                scorecard_branch = score_tree.add("Scorecard")
                scorecard_branch.add(f"ID: {scorecard['id']}")
                scorecard_branch.add(f"Name: {scorecard['name']}")
                scorecard_branch.add(f"Key: {scorecard['key']}")
                
                if scorecard.get('account'):
                    account = scorecard['account']
                    account_branch = scorecard_branch.add("Account")
                    account_branch.add(f"ID: {account['id']}")
                    account_branch.add(f"Name: {account['name']}")
                    account_branch.add(f"Key: {account['key']}")
        
        # Add champion version information
        if score_data.get('championVersionId'):
            score_tree.add(f"Champion Version: {score_data['championVersionId']}")
        
        # Add version history if requested
        if show_versions and score_data.get('versions', {}).get('items'):
            versions = score_data['versions']['items']
            versions_branch = score_tree.add(f"Version History ({len(versions)} versions)")
            
            # Sort versions by creation date (newest first)
            sorted_versions = sorted(versions, key=lambda v: v.get('createdAt', ''), reverse=True)
            
            for version in sorted_versions:
                version_date = version.get('createdAt', 'Unknown date')
                if version_date != 'Unknown date':
                    # Format the date for better readability
                    from datetime import datetime
                    try:
                        dt = datetime.fromisoformat(version_date.replace('Z', '+00:00'))
                        version_date = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                    except Exception:
                        pass
                
                # Highlight champion version
                is_champion = score_data.get('championVersionId') == version.get('id')
                champion_marker = " [bold green](CHAMPION)[/bold green]" if is_champion else ""
                featured_marker = " [yellow](FEATURED)[/yellow]" if version.get('isFeatured') else ""
                
                version_branch = versions_branch.add(f"Version {version['id']}{champion_marker}{featured_marker}")
                version_branch.add(f"Created: {version_date}")
                
                if version.get('note'):
                    version_branch.add(f"Note: {version['note']}")
                
                # Show configuration if requested
                if show_config and version.get('configuration'):
                    config_branch = version_branch.add("Configuration")
                    try:
                        # Try to parse as YAML for better display
                        import yaml
                        config = yaml.safe_load(version['configuration'])
                        config_str = yaml.dump(config, default_flow_style=False)
                        for line in config_str.split('\n'):
                            if line.strip():
                                config_branch.add(line)
                    except Exception:
                        # Fall back to raw display
                        config_lines = version['configuration'].split('\n')
                        for line in config_lines[:20]:  # Limit to first 20 lines
                            config_branch.add(line)
                        if len(config_lines) > 20:
                            config_branch.add("... (truncated)")
        
        # Display the tree
        console.print(score_tree)
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if debug:
            import traceback
            console.print(traceback.format_exc())

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

def resolve_account(client, identifier: str, debug: bool = False) -> Tuple[Optional[Any], Optional[str]]:
    """
    Resolve an account identifier (name, key, or ID) to an account object.
    Returns a tuple of (account_obj, error_message).
    If successful, account_obj will be populated and error_message will be None.
    If unsuccessful, account_obj will be None and error_message will contain the error.
    """
    # First try as key (most common)
    if debug:
        console.print(f"[dim]DEBUG: Trying to find account with key '{identifier}'[/dim]")
    account_obj = client.Account.get_by_key(identifier)
    
    # If not found, try as ID
    if not account_obj:
        if debug:
            console.print(f"[dim]DEBUG: Not found by key, trying as ID[/dim]")
        try:
            account_obj = client.Account.get_by_id(identifier)
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
            result = client.execute(query, {"name": identifier})
            accounts = result.get('listAccounts', {}).get('items', [])
            if accounts:
                # Use the first matching account
                from plexus.dashboard.api.models.account import Account
                account_obj = Account.from_dict(accounts[0], client)
        except Exception as e:
            if debug:
                console.print(f"[red]DEBUG ERROR: Error searching by name: {str(e)}[/red]")
            account_obj = None
    
    # If account not found by any method, return error
    if not account_obj:
        return None, f"Account '{identifier}' not found by key, ID, or name."
    
    return account_obj, None

def resolve_scorecard(client, identifier: str, account_id: Optional[str] = None, debug: bool = False) -> Tuple[Optional[Any], Optional[str]]:
    """
    Resolve a scorecard identifier (name, key, or ID) to a scorecard object.
    Optionally scope the search to a specific account.
    Returns a tuple of (scorecard_obj, error_message).
    """
    # First try as ID (direct lookup)
    if debug:
        console.print(f"[dim]DEBUG: Trying to find scorecard with ID '{identifier}'[/dim]")
    try:
        from plexus.dashboard.api.models.scorecard import Scorecard
        scorecard_obj = client.Scorecard.get_by_id(identifier)
        if scorecard_obj:
            # If account_id is provided, verify the scorecard belongs to this account
            if account_id and scorecard_obj.accountId != account_id:
                if debug:
                    console.print(f"[dim]DEBUG: Scorecard found but belongs to a different account[/dim]")
                scorecard_obj = None
            else:
                return scorecard_obj, None
    except Exception:
        scorecard_obj = None
    
    # Build filter for GraphQL query
    filter_dict = {}
    
    # Try as key
    if debug:
        console.print(f"[dim]DEBUG: Not found by ID, trying as key[/dim]")
    
    # If we have an account_id, add it to the filter
    if account_id:
        filter_dict["accountId"] = {"eq": account_id}
    
    # Try by key
    key_filter = {**filter_dict, "key": {"eq": identifier}}
    query = """
    query GetScorecardByKey($filter: ModelScorecardFilterInput) {
        listScorecards(filter: $filter, limit: 1) {
            items {
                id
                name
                key
                accountId
                externalId
            }
        }
    }
    """
    
    result = client.execute(query, {"filter": key_filter})
    scorecards = result.get('listScorecards', {}).get('items', [])
    
    if scorecards:
        from plexus.dashboard.api.models.scorecard import Scorecard
        # Handle missing externalId field
        if 'externalId' not in scorecards[0]:
            scorecards[0]['externalId'] = None
        return Scorecard.from_dict(scorecards[0], client), None
    
    # Try by name
    if debug:
        console.print(f"[dim]DEBUG: Not found by key, trying as name[/dim]")
    
    name_filter = {**filter_dict, "name": {"eq": identifier}}
    result = client.execute(query, {"filter": name_filter})
    scorecards = result.get('listScorecards', {}).get('items', [])
    
    if scorecards:
        from plexus.dashboard.api.models.scorecard import Scorecard
        # Handle missing externalId field
        if 'externalId' not in scorecards[0]:
            scorecards[0]['externalId'] = None
        return Scorecard.from_dict(scorecards[0], client), None
    
    # If still not found, try a contains search on name as a last resort
    if debug:
        console.print(f"[dim]DEBUG: Not found by exact name, trying name contains[/dim]")
    
    name_contains_filter = {**filter_dict, "name": {"contains": identifier}}
    result = client.execute(query, {"filter": name_contains_filter})
    scorecards = result.get('listScorecards', {}).get('items', [])
    
    if scorecards:
        from plexus.dashboard.api.models.scorecard import Scorecard
        # Handle missing externalId field
        if 'externalId' not in scorecards[0]:
            scorecards[0]['externalId'] = None
        return Scorecard.from_dict(scorecards[0], client), None
    
    # Not found by any method
    account_scope = f" in account '{account_id}'" if account_id else ""
    return None, f"Scorecard '{identifier}' not found by ID, key, or name{account_scope}."

def resolve_score(client, identifier: str, section_ids: Optional[List[str]] = None, debug: bool = False) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Resolve a score identifier (ID, key, name, or external ID) to a score object.
    Optionally scope the search to specific sections.
    Returns a tuple of (score_data, error_message).
    """
    # Define the full score fields for GraphQL queries
    score_fields = """
        id
        name
        key
        description
        order
        type
        externalId
        championVersionId
        sectionId
        section {
            id
            name
            order
            scorecardId
            scorecard {
                id
                name
                key
                accountId
                account {
                    id
                    name
                    key
                }
            }
        }
        versions {
            items {
                id
                configuration
                isFeatured
                createdAt
                updatedAt
                note
            }
        }
    """
    
    # First try as ID (direct lookup)
    if debug:
        console.print(f"[dim]DEBUG: Trying to find score with ID '{identifier}'[/dim]")
    
    try:
        score_query = f"""
        query GetScore($id: ID!) {{
            getScore(id: $id) {{
                {score_fields}
            }}
        }}
        """
        
        result = client.execute(score_query, {"id": identifier})
        score_data = result.get('getScore')
        
        if score_data:
            # If section_ids is provided, verify the score belongs to one of these sections
            if section_ids and score_data.get('sectionId') not in section_ids:
                if debug:
                    console.print(f"[dim]DEBUG: Score found but belongs to a different section[/dim]")
            else:
                return score_data, None
    except Exception as e:
        if debug:
            console.print(f"[dim]DEBUG: Error looking up by ID: {str(e)}[/dim]")
    
    # Build filter for GraphQL query
    filter_dict = {}
    
    # If we have section_ids, add them to the filter
    if section_ids:
        if len(section_ids) == 1:
            filter_dict["sectionId"] = {"eq": section_ids[0]}
        else:
            filter_dict["sectionId"] = {"in": section_ids}
    
    # Try by key
    if debug:
        console.print(f"[dim]DEBUG: Not found by ID, trying as key[/dim]")
    
    key_filter = {**filter_dict, "key": {"eq": identifier}}
    scores_query = f"""
    query ListScores($filter: ModelScoreFilterInput) {{
        listScores(filter: $filter, limit: 10) {{
            items {{
                {score_fields}
            }}
        }}
    }}
    """
    
    result = client.execute(scores_query, {"filter": key_filter})
    scores = result.get('listScores', {}).get('items', [])
    
    if scores:
        if len(scores) > 1 and debug:
            console.print(f"[dim]DEBUG: Found {len(scores)} scores with key '{identifier}'[/dim]")
        return scores[0], None
    
    # Try by external ID
    if debug:
        console.print(f"[dim]DEBUG: Not found by key, trying as external ID[/dim]")
    
    external_id_filter = {**filter_dict, "externalId": {"eq": identifier}}
    result = client.execute(scores_query, {"filter": external_id_filter})
    scores = result.get('listScores', {}).get('items', [])
    
    if scores:
        if len(scores) > 1 and debug:
            console.print(f"[dim]DEBUG: Found {len(scores)} scores with external ID '{identifier}'[/dim]")
        return scores[0], None
    
    # Try by name
    if debug:
        console.print(f"[dim]DEBUG: Not found by external ID, trying as name[/dim]")
    
    name_filter = {**filter_dict, "name": {"eq": identifier}}
    result = client.execute(scores_query, {"filter": name_filter})
    scores = result.get('listScores', {}).get('items', [])
    
    if scores:
        if len(scores) > 1 and debug:
            console.print(f"[dim]DEBUG: Found {len(scores)} scores with name '{identifier}'[/dim]")
        return scores[0], None
    
    # If still not found, try a contains search on name as a last resort
    if debug:
        console.print(f"[dim]DEBUG: Not found by exact name, trying name contains[/dim]")
    
    name_contains_filter = {**filter_dict, "name": {"contains": identifier}}
    result = client.execute(scores_query, {"filter": name_contains_filter})
    scores = result.get('listScores', {}).get('items', [])
    
    if scores:
        if len(scores) > 1:
            if debug:
                console.print(f"[dim]DEBUG: Found {len(scores)} scores with name containing '{identifier}'[/dim]")
            return scores[0], None
    
    # Not found by any method
    section_scope = f" in the specified sections" if section_ids else ""
    return None, f"Score '{identifier}' not found by ID, key, external ID, or name{section_scope}."

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