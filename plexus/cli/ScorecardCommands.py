import click
import os
import json
import yaml
from rich.table import Table
from rich.panel import Panel
from plexus.cli.console import console
from plexus.dashboard.api.client import PlexusDashboardClient
from typing import Optional
import rich

# Define the main command groups that will be exported
@click.group()
def scorecards():
    """Manage multiple scorecards"""
    pass

@click.group()
def scorecard():
    """Manage scorecards (alias for 'scorecards')"""
    pass

@click.group()
def scores():
    """Commands for managing scores."""
    pass

@click.group()
def score():
    """Manage individual scores (alias for 'scores')"""
    pass

# Helper functions for resolving identifiers

def create_client() -> PlexusDashboardClient:
    """Create a client and log its configuration"""
    client = PlexusDashboardClient()
    return client

def resolve_scorecard_identifier(client, identifier):
    """Resolve a scorecard identifier to its ID."""
    # First try direct ID lookup
    try:
        query = f"""
        query GetScorecard {{
            getScorecard(id: "{identifier}") {{
                id
            }}
        }}
        """
        result = client.execute(query)
        if result.get('getScorecard'):
            return identifier
    except:
        pass
    
    # Try by name, key, or externalId
    query = f"""
    query FindScorecard {{
        listScorecards(filter: {{ 
            or: [
                {{ name: {{ eq: "{identifier}" }} }},
                {{ key: {{ eq: "{identifier}" }} }},
                {{ externalId: {{ eq: "{identifier}" }} }}
            ]
        }}) {{
            items {{
                id
            }}
        }}
    }}
    """
    
    try:
        result = client.execute(query)
        scorecards = result.get('listScorecards', {}).get('items', [])
        if scorecards:
            return scorecards[0].get('id')
    except:
        pass
    
    return None

def resolve_account_identifier(client, identifier):
    """Resolve an account identifier to its ID."""
    # First try direct ID lookup
    try:
        query = f"""
        query GetAccount {{
            getAccount(id: "{identifier}") {{
                id
            }}
        }}
        """
        result = client.execute(query)
        if result.get('getAccount'):
            return identifier
    except:
        pass
    
    # Try by name
    try:
        query = f"""
        query FindAccountByName {{
            listAccounts(filter: {{ name: {{ eq: "{identifier}" }} }}) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        accounts = result.get('listAccounts', {}).get('items', [])
        if accounts:
            return accounts[0].get('id')
    except:
        pass
    
    # Try by key
    try:
        query = f"""
        query FindAccountByKey {{
            listAccounts(filter: {{ key: {{ eq: "{identifier}" }} }}) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        accounts = result.get('listAccounts', {}).get('items', [])
        if accounts:
            return accounts[0].get('id')
    except:
        pass
    
    return None

def resolve_score_identifier(client, identifier: str) -> Optional[str]:
    """
    Resolves a score identifier (ID, name, key, or externalId) to a score ID.
    
    Args:
        client: GraphQL client
        identifier: Score identifier (ID, name, key, or externalId)
        
    Returns:
        Score ID if found, None otherwise
    """
    # Try direct ID lookup first
    query = f"""
    query GetScoreById {{
        getScore(id: "{identifier}") {{
            id
        }}
    }}
    """
    
    try:
        result = client.execute(query)
        if result.get('getScore'):
            return identifier
    except:
        pass
    
    # Try other identifiers
    query = f"""
    query FindScore {{
        listScores(filter: {{ 
            or: [
                {{ name: {{ eq: "{identifier}" }} }},
                {{ key: {{ eq: "{identifier}" }} }},
                {{ externalId: {{ eq: "{identifier}" }} }}
            ]
        }}) {{
            items {{
                id
            }}
        }}
    }}
    """
    
    try:
        result = client.execute(query)
        scores = result.get('listScores', {}).get('items', [])
        if scores:
            return scores[0].get('id')
    except:
        pass
    
    return None

def generate_key(name: str) -> str:
    """Generate a URL-safe key from a name."""
    return name.lower().replace(' ', '-')

def format_scorecard_panel(scorecard, include_sections=False, detailed_scores=False):
    """
    Format a scorecard as a rich panel with consistent styling.
    
    Args:
        scorecard: The scorecard data to format
        include_sections: Whether to include sections and scores in the output
        detailed_scores: Whether to show detailed information for each score
        
    Returns:
        A rich Panel object with formatted scorecard content
    """
    # Find the longest label for alignment
    labels = ["Name:", "Key:", "External ID:", "Description:", "Created:", "Updated:", "Total Scores:"]
    max_label_length = max(len(label) for label in labels)
    
    # Prepare content with aligned columns and color-coded values
    content = []
    
    # Scorecard Information - ID is removed from content as it's already in the panel title
    content.append(f"{'Name:':<{max_label_length}} [blue]{scorecard.get('name', 'N/A')}[/blue]")
    content.append(f"{'Key:':<{max_label_length}} [blue]{scorecard.get('key', 'N/A')}[/blue]")
    content.append(f"{'External ID:':<{max_label_length}} [magenta]{scorecard.get('externalId', 'N/A')}[/magenta]")
    
    description = scorecard.get('description', '')
    if description:
        content.append(f"{'Description:':<{max_label_length}} [blue]{description}[/blue]")
    
    created_at = scorecard.get('createdAt', 'N/A')
    updated_at = scorecard.get('updatedAt', 'N/A')
    content.append(f"{'Created:':<{max_label_length}} [dim]{created_at}[/dim]")
    content.append(f"{'Updated:':<{max_label_length}} [dim]{updated_at}[/dim]")
    
    # Sections and Scores if requested
    if include_sections and 'sections' in scorecard and scorecard['sections']:
        sections = scorecard['sections'].get('items', [])
        total_scores = sum(len(section.get('scores', {}).get('items', [])) for section in sections)
        content.append("")
        content.append(f"{'Total Scores:':<{max_label_length}} [magenta]{total_scores}[/magenta]")
        
        if total_scores > 0:
            content.append("")
            content.append("[bold]Sections and Scores[/bold]")
            
            # Sort sections by order
            sorted_sections = sorted(sections, key=lambda s: s.get('order', 0))
            
            for i, section in enumerate(sorted_sections):
                section_prefix = "└── " if i == len(sorted_sections) - 1 else "├── "
                content.append(f"{section_prefix}[bold][blue]{section.get('name', 'Unnamed Section')}[/blue][/bold]")
                
                if 'scores' in section and section['scores']:
                    # Sort scores by order
                    sorted_scores = sorted(section['scores'].get('items', []), key=lambda s: s.get('order', 0))
                    
                    for j, score in enumerate(sorted_scores):
                        is_last_score = j == len(sorted_scores) - 1
                        is_last_section = i == len(sorted_sections) - 1
                        
                        if is_last_section:
                            score_prefix = "    └── " if is_last_score else "    ├── "
                        else:
                            score_prefix = "│   └── " if is_last_score else "│   ├── "
                        
                        score_name = score.get('name', 'Unnamed Score')
                        content.append(f"{score_prefix}[blue]{score_name}[/blue]")
                        
                        # Add detailed score information if requested
                        if detailed_scores:
                            score_id = score.get('id', 'N/A')
                            score_key = score.get('key', 'N/A')
                            indent_prefix = score_prefix.replace("└──", "    ").replace("├──", "│   ")
                            content.append(f"{indent_prefix}  ID: [magenta]{score_id}[/magenta]")
                            content.append(f"{indent_prefix}  Key: [blue]{score_key}[/blue]")
    
    # Create panel with the content
    panel = rich.panel.Panel(
        "\n".join(content),
        title=f"[bold magenta]{scorecard.get('id', 'Scorecard')}[/bold magenta]",
        expand=True,
        padding=(1, 2)
    )
    
    return panel 

# Scorecard commands

@scorecards.command()
@click.option('--account', help='Filter by account (accepts ID, name, or key)')
@click.option('--name', help='Filter by scorecard name')
@click.option('--key', help='Filter by scorecard key')
@click.option('--limit', type=int, default=10, help='Maximum number of scorecards to return')
def list(account: Optional[str], name: Optional[str], key: Optional[str], limit: int):
    """List scorecards with rich formatting."""
    client = create_client()
    
    # Build filter string for GraphQL query
    filter_parts = []
    if account:
        account_id = resolve_account_identifier(client, account)
        if not account_id:
            click.echo(f"Account not found: {account}")
            return
        filter_parts.append(f'accountId: {{ eq: "{account_id}" }}')
    
    if name:
        filter_parts.append(f'name: {{ contains: "{name}" }}')
    
    if key:
        filter_parts.append(f'key: {{ contains: "{key}" }}')
    
    filter_str = ", ".join(filter_parts)
    
    # Construct the GraphQL query with proper variable syntax
    query = f"""
    query ListScorecards {{
        listScorecards(filter: {{ {filter_str} }}, limit: {limit}) {{
            items {{
                id
                name
                key
                description
                externalId
                createdAt
                updatedAt
                sections {{
                    items {{
                        id
                        name
                        order
                        scores {{
                            items {{
                                id
                                name
                                key
                                description
                                type
                                order
                            }}
                        }}
                    }}
                }}
            }}
        }}
    }}
    """
    
    try:
        response = client.execute(query)
        scorecards = response.get('listScorecards', {}).get('items', [])
        
        if not scorecards:
            click.echo("No scorecards found.")
            return
        
        console = rich.console.Console()
        
        # Create a grid for the panels
        grid = Table.grid(expand=True)
        grid.add_column()
        
        for scorecard in scorecards:
            # Use the shared formatting function with sections included
            panel = format_scorecard_panel(scorecard, include_sections=True)
            grid.add_row(panel)
            # Add a blank row for spacing
            grid.add_row("")
        
        console.print(grid)
        
    except Exception as e:
        click.echo(f"Error listing scorecards: {e}")

@scorecards.command()
@click.option('--scorecard', required=True, help='Scorecard to get info about (accepts ID, name, key, or external ID)')
def info(scorecard: str):
    """Get detailed information about a specific scorecard."""
    client = create_client()
    
    # Resolve the scorecard ID
    scorecard_id = resolve_scorecard_identifier(client, scorecard)
    if not scorecard_id:
        click.echo(f"Scorecard not found: {scorecard}")
        return
    
    # Fetch the scorecard with sections and scores
    query = f"""
    query GetScorecard {{
        getScorecard(id: "{scorecard_id}") {{
            id
            name
            key
            description
            externalId
            createdAt
            updatedAt
            sections {{
                items {{
                    id
                    name
                    order
                    scores {{
                        items {{
                            id
                            name
                            key
                            description
                            type
                            order
                        }}
                    }}
                }}
            }}
        }}
    }}
    """
    
    try:
        response = client.execute(query)
        scorecard_data = response.get('getScorecard')
        
        if not scorecard_data:
            click.echo(f"Scorecard not found: {scorecard}")
            return
        
        console = rich.console.Console()
        
        # Use the shared formatting function with sections included
        panel = format_scorecard_panel(scorecard_data, include_sections=True)
        console.print(panel)
        
    except Exception as e:
        click.echo(f"Error getting scorecard info: {e}")

@scorecards.command()
@click.option('--scorecard', required=True, help='Scorecard to list scores for (accepts ID, name, key, or external ID)')
@click.option('--limit', default=50, help='Maximum number of scores to return')
def list_scores(scorecard: str, limit: int):
    """List all scores for a specific scorecard, organized by section."""
    client = create_client()
    
    # Resolve the scorecard ID
    scorecard_id = resolve_scorecard_identifier(client, scorecard)
    if not scorecard_id:
        click.echo(f"Scorecard not found: {scorecard}")
        return
    
    # Fetch the scorecard with sections and scores
    query = f"""
    query GetScorecard {{
        getScorecard(id: "{scorecard_id}") {{
            id
            name
            key
            description
            externalId
            createdAt
            updatedAt
            sections {{
                items {{
                    id
                    name
                    order
                    scores {{
                        items {{
                            id
                            name
                            key
                            description
                            type
                            order
                        }}
                    }}
                }}
            }}
        }}
    }}
    """
    
    try:
        response = client.execute(query)
        scorecard_data = response.get('getScorecard')
        
        if not scorecard_data:
            click.echo(f"Scorecard not found: {scorecard}")
            return
        
        console = rich.console.Console()
        
        # Use the shared formatting function with sections and detailed scores included
        panel = format_scorecard_panel(scorecard_data, include_sections=True, detailed_scores=True)
        
        # Override the panel title to indicate this is a scores listing
        panel.title = f"[bold magenta]Scores for {scorecard_data.get('name', 'Scorecard')}[/bold magenta]"
        
        console.print(panel)
        
    except Exception as e:
        click.echo(f"Error listing scores: {e}")

# Add the scorecard commands (aliases to scorecards commands)
@scorecard.command()
@click.option('--account', default=None, help='Filter by account (accepts ID, name, or key)')
@click.option('--name', default=None, help='Filter by scorecard name')
@click.option('--key', default=None, help='Filter by scorecard key')
@click.option('--limit', default=50, help='Maximum number of scorecards to return')
def list(account: Optional[str], name: Optional[str], key: Optional[str], limit: int):
    """List scorecards with optional filtering.
    
    Examples:
        plexus scorecard list
        plexus scorecard list --account "My Account"
        plexus scorecard list --name "QA Scorecard"
        plexus scorecard list --key qa-v1
    """
    # Call the scorecards.list implementation
    ctx = click.get_current_context()
    ctx.forward(scorecards.commands['list'])

@scorecard.command()
@click.option('--scorecard', required=True, help='Scorecard to get info about (accepts ID, name, key, or external ID)')
def info(scorecard: str):
    """Get detailed information about a specific scorecard.
    
    Retrieves and displays detailed information about a scorecard, including its
    sections and scores. The command accepts a flexible identifier for the scorecard,
    which can be an ID, name, key, or external ID.
    
    Examples:
        plexus scorecard info --scorecard 1234            # Get info by ID
        plexus scorecard info --scorecard "QA Scorecard"  # Get info by name
        plexus scorecard info --scorecard qa-v1           # Get info by key
        plexus scorecard info --scorecard ext-1234        # Get info by external ID
    """
    # Call the scorecards.info implementation
    ctx = click.get_current_context()
    ctx.forward(scorecards.commands['info'])

@scorecard.command(name="list_scores")
@click.option('--scorecard', required=True, help='Scorecard to list scores for (accepts ID, name, key, or external ID)')
@click.option('--limit', default=50, help='Maximum number of scores to return')
def list_scores(scorecard: str, limit: int):
    """List all scores for a specific scorecard.
    
    Retrieves and displays a list of all scores associated with a specific scorecard.
    The scores are organized by section and displayed in a tree view.
    
    The --scorecard option accepts a flexible identifier, which can be an ID, name, key,
    or external ID.
    
    Examples:
        plexus scorecard list-scores --scorecard "QA Cards"    # List scores by scorecard name
        plexus scorecard list-scores --scorecard sc-123         # List scores by scorecard key
        plexus scorecard list-scores --scorecard 12345 --limit 100  # List up to 100 scores
    """
    # Call the scorecards.list_scores implementation
    ctx = click.get_current_context()
    ctx.forward(scorecards.commands['list_scores'])

@scorecards.command()
@click.option('--scorecard', required=True, help='Scorecard to delete (accepts ID, name, key, or external ID)')
@click.option('--force', is_flag=True, help='Skip confirmation prompt')
def delete(scorecard: str, force: bool):
    """Delete a scorecard and all its sections and scores.
    
    Permanently removes a scorecard and all its associated sections and scores from the system.
    This operation cannot be undone. The command will show a confirmation prompt unless --force
    is specified.
    
    The --scorecard option accepts an ID, name, key, or external ID - the system will
    automatically determine which type of identifier was provided.
    
    Examples:
        plexus scorecards delete --scorecard "QA Scorecard"  # Delete by name
        plexus scorecards delete --scorecard qa-v1           # Delete by key
        plexus scorecards delete --scorecard 1234 --force    # Delete by ID without confirmation
    """
    client = create_client()
    
    # First, resolve the scorecard identifier to an ID
    scorecard_id = resolve_scorecard_identifier(client, scorecard)
    if not scorecard_id:
        console.print(f"[red]Could not find scorecard: {scorecard}[/red]")
        return
    
    # Get scorecard details for confirmation
    query = f"""
    query GetScorecardDetails {{
        getScorecard(id: "{scorecard_id}") {{
            id
            name
            key
            accountId
            sections {{
                items {{
                    id
                    scores {{
                        items {{
                            id
                        }}
                    }}
                }}
            }}
        }}
    }}
    """
    
    try:
        result = client.execute(query)
        scorecard_data = result.get('getScorecard')
        
        if not scorecard_data:
            console.print(f"[red]Scorecard not found: {scorecard}[/red]")
            return
        
        scorecard_name = scorecard_data.get('name')
        scorecard_key = scorecard_data.get('key')
        
        # Count sections and scores
        sections = scorecard_data.get('sections', {}).get('items', [])
        section_count = len(sections)
        score_count = sum(len(section.get('scores', {}).get('items', [])) for section in sections)
        
        # Confirm deletion
        if not force:
            console.print(f"[yellow]Warning: This will delete scorecard '{scorecard_data.get('name')}' with {section_count} sections and {score_count} scores.[/yellow]")
            if not click.confirm("Are you sure you want to proceed?"):
                console.print("[yellow]Deletion cancelled[/yellow]")
                return
        
        # Delete all scores first
        for section in sections:
            section_id = section.get('id')
            scores = section.get('scores', {}).get('items', [])
            
            for score in scores:
                score_id = score.get('id')
                delete_score_mutation = f"""
                mutation DeleteScore {{
                    deleteScore(input: {{ id: "{score_id}" }}) {{
                        id
                    }}
                }}
                """
                client.execute(delete_score_mutation)
        
        # Delete all sections
        for section in sections:
            section_id = section.get('id')
            delete_section_mutation = f"""
            mutation DeleteSection {{
                deleteSection(input: {{ id: "{section_id}" }}) {{
                    id
                }}
            }}
            """
            client.execute(delete_section_mutation)
        
        # Finally delete the scorecard
        delete_scorecard_mutation = f"""
        mutation DeleteScorecard {{
            deleteScorecard(input: {{ id: "{scorecard_id}" }}) {{
                id
            }}
        }}
        """
        client.execute(delete_scorecard_mutation)
        
        console.print(f"[green]Successfully deleted scorecard: {scorecard_name} ({scorecard_key})[/green]")
        console.print(f"[green]Deleted {section_count} sections and {score_count} scores.[/green]")
    
    except Exception as e:
        console.print(f"[red]Error deleting scorecard: {e}[/red]")

@scorecards.command()
@click.option('--scorecard', help='Specific scorecard to pull (accepts ID, name, key, or external ID)')
@click.option('--account', default='call-criteria', help='Account to pull scorecards from (accepts ID, name, or key)')
@click.option('--output', default='scorecards', help='Directory to save YAML files')
def pull(scorecard: Optional[str], account: str, output: str):
    """Pull scorecard configurations from the API to local YAML files.
    
    Downloads scorecard configurations from the API and saves them as YAML files in the
    specified output directory. If a specific scorecard is provided, only that scorecard
    will be pulled. Otherwise, all scorecards for the specified account will be pulled.
    
    Both the --scorecard and --account options accept flexible identifiers - the system will
    automatically determine which type of identifier was provided.
    
    Examples:
        plexus scorecards pull                           # Pull all scorecards for default account
        plexus scorecards pull --scorecard "QA Cards"    # Pull specific scorecard by name
        plexus scorecards pull --account acme            # Pull all scorecards for specified account
        plexus scorecards pull --output ./my-scorecards  # Save to custom directory
    """
    client = create_client()
    
    # First, get the account ID from the provided identifier
    account_id = resolve_account_identifier(client, account)
    if not account_id:
        console.print(f"[red]No account found matching: {account}[/red]")
        return
    
    # Get account name for display
    account_query = f"""
    query GetAccount {{
        getAccount(id: "{account_id}") {{
            name
        }}
    }}
    """
    
    try:
        account_result = client.execute(account_query)
        account_name = account_result.get('getAccount', {}).get('name', account)
        console.print(f"[green]Using account: {account_name} (ID: {account_id})[/green]")
        
        # Create output directory if it doesn't exist
        os.makedirs(output, exist_ok=True)
        
        # Build query to get scorecards
        filter_conditions = [f'accountId: {{ eq: "{account_id}" }}']
        
        if scorecard:
            # Try to resolve the scorecard identifier
            scorecard_id = resolve_scorecard_identifier(client, scorecard)
            if scorecard_id:
                filter_conditions = [f'id: {{ eq: "{scorecard_id}" }}']
            else:
                console.print(f"[red]Could not find scorecard: {scorecard}[/red]")
                return
        
        filter_str = ", ".join(filter_conditions)
        
        # Query for scorecards with sections and scores
        query = f"""
        query ListScorecards {{
            listScorecards(filter: {{ {filter_str} }}, limit: 100) {{
                items {{
                    id
                    name
                    key
                    description
                    externalId
                    sections {{
                        items {{
                            id
                            name
                            order
                            scores {{
                                items {{
                                    id
                                    name
                                    key
                                    description
                                    order
                                    type
                                    externalId
                                    championVersion {{
                                        id
                                        configuration
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        result = client.execute(query)
        scorecards = result.get('listScorecards', {}).get('items', [])
        
        if not scorecards:
            console.print("[yellow]No scorecards found matching the criteria[/yellow]")
            return
        
        console.print(f"[green]Found {len(scorecards)} scorecards[/green]")
        
        # Process each scorecard
        for scorecard_data in scorecards:
            scorecard_name = scorecard_data.get('name')
            scorecard_key = scorecard_data.get('key')
            
            console.print(f"\n[bold]Processing scorecard: {scorecard_name}[/bold]")
            
            # Create YAML structure
            yaml_data = {
                'name': scorecard_name,
                'key': scorecard_key,
                'description': scorecard_data.get('description', ''),
                'externalId': scorecard_data.get('externalId', ''),
                'sections': []
            }
            
            # Add sections and scores
            sections = scorecard_data.get('sections', {}).get('items', [])
            for section in sections:
                section_data = {
                    'name': section.get('name'),
                    'order': section.get('order'),
                    'scores': []
                }
                
                scores = section.get('scores', {}).get('items', [])
                for score in scores:
                    score_data = {
                        'name': score.get('name'),
                        'key': score.get('key', ''),
                        'description': score.get('description', ''),
                        'order': score.get('order'),
                        'type': score.get('type'),
                        'externalId': score.get('externalId', '')
                    }
                    
                    # Add configuration if available
                    champion_version = score.get('championVersion')
                    if champion_version:
                        score_data['configuration'] = champion_version.get('configuration', {})
                    
                    section_data['scores'].append(score_data)
                
                yaml_data['sections'].append(section_data)
            
            # Write to file
            file_name = f"{scorecard_key}.yaml"
            file_path = os.path.join(output, file_name)
            
            with open(file_path, 'w') as f:
                yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
            
            console.print(f"[green]Saved scorecard to {file_path}[/green]")
        
        console.print("\n[green]Pull operation completed[/green]")
    
    except Exception as e:
        console.print(f"[red]Error during pull operation: {e}[/red]")

@scorecards.command()
@click.option('--file', required=True, help='Path to YAML file containing scorecard configuration')
@click.option('--account', default='call-criteria', help='Account to push scorecard to (accepts ID, name, or key)')
@click.option('--update/--no-update', default=False, help='Update existing scorecard if it exists')
def push(file: str, account: str, update: bool):
    """Push scorecard configuration from a YAML file to the API.
    
    Uploads a scorecard configuration from a YAML file to the API. If the scorecard already
    exists and --update is specified, the existing scorecard will be updated. Otherwise,
    a new scorecard will be created.
    
    The YAML file should contain a complete scorecard configuration, including sections
    and scores. The file format should match the output of the 'pull' command.
    
    Examples:
        plexus scorecards push --file ./my-scorecard.yaml
        plexus scorecards push --file ./my-scorecard.yaml --update
        plexus scorecards push --file ./my-scorecard.yaml --account acme
    """
    client = create_client()
    
    # First, get the account ID from the provided identifier
    account_id = resolve_account_identifier(client, account)
    if not account_id:
        console.print(f"[red]No account found matching: {account}[/red]")
        return
    
    # Get account name for display
    account_query = f"""
    query GetAccount {{
        getAccount(id: "{account_id}") {{
            name
        }}
    }}
    """
    
    try:
        account_result = client.execute(account_query)
        account_name = account_result.get('getAccount', {}).get('name', account)
        console.print(f"[green]Using account: {account_name} (ID: {account_id})[/green]")
        
        # Read the YAML file
        if not os.path.exists(file):
            console.print(f"[red]File not found: {file}[/red]")
            return
        
        with open(file, 'r') as f:
            yaml_data = yaml.safe_load(f)
        
        if not yaml_data:
            console.print(f"[red]Invalid or empty YAML file: {file}[/red]")
            return
        
        # Extract scorecard data
        scorecard_name = yaml_data.get('name')
        scorecard_key = yaml_data.get('key')
        scorecard_description = yaml_data.get('description', '')
        scorecard_external_id = yaml_data.get('externalId', '')
        
        if not scorecard_name or not scorecard_key:
            console.print("[red]Scorecard name and key are required[/red]")
            return
        
        console.print(f"[bold]Processing scorecard: {scorecard_name} ({scorecard_key})[/bold]")
        
        # Check if scorecard exists
        existing_scorecard_id = None
        if update:
            query = f"""
            query FindScorecard {{
                listScorecards(filter: {{ 
                    and: [
                        {{ accountId: {{ eq: "{account_id}" }} }},
                        {{ key: {{ eq: "{scorecard_key}" }} }}
                    ]
                }}) {{
                    items {{
                        id
                    }}
                }}
            }}
            """
            
            result = client.execute(query)
            scorecards = result.get('listScorecards', {}).get('items', [])
            if scorecards:
                existing_scorecard_id = scorecards[0].get('id')
                console.print(f"[yellow]Found existing scorecard with key '{scorecard_key}' (ID: {existing_scorecard_id})[/yellow]")
        
        # Create or update scorecard
        if existing_scorecard_id and update:
            # Update existing scorecard
            mutation = f"""
            mutation UpdateScorecard {{
                updateScorecard(input: {{
                    id: "{existing_scorecard_id}",
                    name: "{scorecard_name}",
                    description: "{scorecard_description}",
                    externalId: "{scorecard_external_id}"
                }}) {{
                    id
                }}
            }}
            """
            
            result = client.execute(mutation)
            scorecard_id = result.get('updateScorecard', {}).get('id')
            console.print(f"[green]Updated scorecard: {scorecard_name} (ID: {scorecard_id})[/green]")
        else:
            # Create new scorecard
            mutation = f"""
            mutation CreateScorecard {{
                createScorecard(input: {{
                    accountId: "{account_id}",
                    name: "{scorecard_name}",
                    key: "{scorecard_key}",
                    description: "{scorecard_description}",
                    externalId: "{scorecard_external_id}"
                }}) {{
                    id
                }}
            }}
            """
            
            result = client.execute(mutation)
            scorecard_id = result.get('createScorecard', {}).get('id')
            console.print(f"[green]Created scorecard: {scorecard_name} (ID: {scorecard_id})[/green]")
        
        # Process sections and scores
        sections = yaml_data.get('sections', [])
        for section_index, section_data in enumerate(sections):
            section_name = section_data.get('name')
            section_order = section_data.get('order', section_index)
            
            # Create section
            mutation = f"""
            mutation CreateSection {{
                createSection(input: {{
                    scorecardId: "{scorecard_id}",
                    name: "{section_name}",
                    order: {section_order}
                }}) {{
                    id
                }}
            }}
            """
            
            result = client.execute(mutation)
            section_id = result.get('createSection', {}).get('id')
            console.print(f"[green]Created section: {section_name} (ID: {section_id})[/green]")
            
            # Process scores
            scores = section_data.get('scores', [])
            for score_index, score_data in enumerate(scores):
                score_name = score_data.get('name')
                score_key = score_data.get('key', generate_key(score_name))
                score_description = score_data.get('description', '')
                score_order = score_data.get('order', score_index)
                score_type = score_data.get('type', 'binary')
                score_external_id = score_data.get('externalId', '')
                
                # Create score
                mutation = f"""
                mutation CreateScore {{
                    createScore(input: {{
                        sectionId: "{section_id}",
                        name: "{score_name}",
                        key: "{score_key}",
                        description: "{score_description}",
                        order: {score_order},
                        type: {score_type},
                        externalId: "{score_external_id}"
                    }}) {{
                        id
                    }}
                }}
                """
                
                result = client.execute(mutation)
                score_id = result.get('createScore', {}).get('id')
                console.print(f"[green]Created score: {score_name} (ID: {score_id})[/green]")
                
                # Add configuration if available
                configuration = score_data.get('configuration')
                if configuration:
                    # Convert configuration to JSON string
                    config_json = json.dumps(configuration)
                    
                    mutation = f"""
                    mutation CreateScoreVersion {{
                        createScoreVersion(input: {{
                            scoreId: "{score_id}",
                            configuration: {json.dumps(config_json)},
                            isChampion: true
                        }}) {{
                            id
                        }}
                    }}
                    """
                    
                    result = client.execute(mutation)
                    version_id = result.get('createScoreVersion', {}).get('id')
                    console.print(f"[green]Created score version with configuration (ID: {version_id})[/green]")
        
        console.print("\n[green]Push operation completed successfully[/green]")
    
    except Exception as e:
        console.print(f"[red]Error during push operation: {e}[/red]")

@scorecard.command()
@click.option('--file', required=True, help='Path to YAML file containing scorecard configuration')
@click.option('--account', default='call-criteria', help='Account to push scorecard to (accepts ID, name, or key)')
@click.option('--update/--no-update', default=False, help='Update existing scorecard if it exists')
def push(file: str, account: str, update: bool):
    """Push scorecard configuration from a YAML file to the API.
    
    Examples:
        plexus scorecard push --file ./my-scorecard.yaml
        plexus scorecard push --file ./my-scorecard.yaml --update
        plexus scorecard push --file ./my-scorecard.yaml --account acme
    """
    # Call the scorecards.push implementation
    ctx = click.get_current_context()
    ctx.forward(scorecards.commands['push'])

@scorecard.command()
@click.option('--scorecard', required=True, help='Scorecard to delete (accepts ID, name, key, or external ID)')
@click.option('--force', is_flag=True, help='Skip confirmation prompt')
def delete(scorecard: str, force: bool):
    """Delete a scorecard and all its sections and scores.
    
    Examples:
        plexus scorecard delete --scorecard 1234
        plexus scorecard delete --scorecard "QA Scorecard" --force
        plexus scorecard delete --scorecard qa-v1
    """
    # Call the scorecards.delete implementation
    ctx = click.get_current_context()
    ctx.forward(scorecards.commands['delete'])

# Scores commands

@scores.command()
@click.option('--score', required=True, help='Score to get info about (accepts ID, name, key, or external ID)')
def info(score: str):
    """Get detailed information about a specific score.
    
    Retrieves and displays detailed information about a score, including its
    configuration if available. The command accepts a flexible identifier for the score,
    which can be an ID, name, key, or external ID.
    
    Examples:
        plexus scores info --score "Critical Error"    # Get info by name
        plexus scores info --score sc-123              # Get info by key
        plexus scores info --score 12345               # Get info by ID
    """
    client = create_client()
    
    # Resolve the score identifier
    score_id = resolve_score_identifier(client, score)
    if not score_id:
        console.print(f"[red]No score found matching: {score}[/red]")
        return
    
    # Query for score details
    query = f"""
    query GetScore {{
        getScore(id: "{score_id}") {{
            id
            name
            key
            description
            type
            order
            externalId
            section {{
                id
                name
                scorecard {{
                    id
                    name
                    key
                    account {{
                        id
                        name
                        key
                    }}
                }}
            }}
            championVersion {{
                id
                configuration
                createdAt
            }}
        }}
    }}
    """
    
    try:
        result = client.execute(query)
        score_data = result.get('getScore')
        
        if not score_data:
            console.print(f"[red]Could not retrieve score with ID: {score_id}[/red]")
            return
        
        # Display score information
        console.print(f"\n[bold cyan]Score Information[/bold cyan]")
        console.print(f"[bold]ID:[/bold] {score_data.get('id')}")
        console.print(f"[bold]Name:[/bold] {score_data.get('name')}")
        console.print(f"[bold]Key:[/bold] {score_data.get('key', 'N/A')}")
        console.print(f"[bold]Description:[/bold] {score_data.get('description', 'N/A')}")
        console.print(f"[bold]Type:[/bold] {score_data.get('type', 'N/A')}")
        console.print(f"[bold]Order:[/bold] {score_data.get('order', 'N/A')}")
        console.print(f"[bold]External ID:[/bold] {score_data.get('externalId', 'N/A')}")
        
        # Display section and scorecard information
        section = score_data.get('section', {})
        scorecard = section.get('scorecard', {})
        account = scorecard.get('account', {})
        
        console.print(f"\n[bold cyan]Hierarchy Information[/bold cyan]")
        console.print(f"[bold]Section:[/bold] {section.get('name', 'N/A')} (ID: {section.get('id', 'N/A')})")
        console.print(f"[bold]Scorecard:[/bold] {scorecard.get('name', 'N/A')} (Key: {scorecard.get('key', 'N/A')}, ID: {scorecard.get('id', 'N/A')})")
        console.print(f"[bold]Account:[/bold] {account.get('name', 'N/A')} (Key: {account.get('key', 'N/A')}, ID: {account.get('id', 'N/A')})")
        
        # Display champion version information
        champion_version = score_data.get('championVersion', {})
        if champion_version:
            console.print(f"\n[bold cyan]Champion Version Information[/bold cyan]")
            console.print(f"[bold]Version ID:[/bold] {champion_version.get('id', 'N/A')}")
            console.print(f"[bold]Created At:[/bold] {champion_version.get('createdAt', 'N/A')}")
            
            # Display configuration if available
            configuration = champion_version.get('configuration')
            if configuration:
                console.print(f"\n[bold cyan]Configuration[/bold cyan]")
                
                # Try to parse the configuration as JSON
                try:
                    if isinstance(configuration, str):
                        config_obj = json.loads(configuration)
                    else:
                        config_obj = configuration
                    
                    # Pretty print the configuration
                    console.print(json.dumps(config_obj, indent=2))
                except:
                    # If parsing fails, just print it as is
                    console.print(str(configuration))
        else:
            console.print("\n[yellow]No champion version found for this score[/yellow]")
        
    except Exception as e:
        console.print(f"[red]Error retrieving score information: {e}[/red]")

@scores.command()
@click.option('--scorecard', required=True, help='Scorecard to list scores for (accepts ID, name, key, or external ID)')
@click.option('--limit', default=50, help='Maximum number of scores to return')
def list(scorecard: str, limit: int):
    """List all scores for a specific scorecard.
    
    Retrieves and displays a list of all scores associated with a specific scorecard.
    The scores are organized by section and displayed in a tree view.
    
    The --scorecard option accepts a flexible identifier, which can be an ID, name, key,
    or external ID.
    
    Examples:
        plexus scores list --scorecard "QA Cards"    # List scores by scorecard name
        plexus scores list --scorecard sc-123         # List scores by scorecard key
        plexus scores list --scorecard 12345 --limit 100  # List up to 100 scores
    """
    # Forward to the scorecards list_scores implementation
    ctx = click.get_current_context()
    ctx.forward(scorecards.commands['list_scores'])

# Score commands (aliases to scores commands)
@score.command()
@click.option('--scorecard', required=True, help='Scorecard to list scores for (accepts ID, name, key, or external ID)')
@click.option('--limit', default=50, help='Maximum number of scores to return')
def list(scorecard: str, limit: int):
    """List all scores for a specific scorecard.
    
    Examples:
        plexus score list --scorecard 1234
        plexus score list --scorecard "QA Scorecard"
        plexus score list --scorecard qa-v1
    """
    # Call the scores.list implementation
    ctx = click.get_current_context()
    ctx.forward(scores.commands['list'])

@score.command()
@click.option('--score', required=True, help='Score to get info about (accepts ID, name, key, or external ID)')
def info(score: str):
    """Get detailed information about a specific score.
    
    Examples:
        plexus score info --score 5678
        plexus score info --score "Grammar Check"
        plexus score info --score grammar-check
    """
    # Call the scores.info implementation
    ctx = click.get_current_context()
    ctx.forward(scores.commands['info']) 