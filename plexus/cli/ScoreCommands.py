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
import datetime

# Define the main command groups that will be exported
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
    
    # Try lookup by key
    try:
        query = f"""
        query ListScorecards {{
            listScorecards(filter: {{ key: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listScorecards', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    # Try lookup by name
    try:
        query = f"""
        query ListScorecards {{
            listScorecards(filter: {{ name: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listScorecards', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    # Try lookup by externalId
    try:
        query = f"""
        query ListScorecards {{
            listScorecards(filter: {{ externalId: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listScorecards', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    return None

def resolve_score_identifier(client, identifier: str) -> Optional[str]:
    """Resolve a score identifier to its ID."""
    # First try direct ID lookup
    try:
        query = f"""
        query GetScore {{
            getScore(id: "{identifier}") {{
                id
            }}
        }}
        """
        result = client.execute(query)
        if result.get('getScore'):
            return identifier
    except:
        pass
    
    # Try lookup by key
    try:
        query = f"""
        query ListScores {{
            listScores(filter: {{ key: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listScores', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    # Try lookup by name
    try:
        query = f"""
        query ListScores {{
            listScores(filter: {{ name: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listScores', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    # Try lookup by externalId
    try:
        query = f"""
        query ListScores {{
            listScores(filter: {{ externalId: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listScores', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    return None

def generate_key(name: str) -> str:
    """Generate a key from a name by converting to lowercase and replacing spaces with hyphens."""
    return name.lower().replace(' ', '-')

@scores.command()
@click.option('--scorecard', required=True, help='Scorecard containing the score (accepts ID, name, key, or external ID)')
@click.option('--score', required=True, help='Score to get info about (accepts ID, name, key, or external ID)')
def info(scorecard: str, score: str):
    """Get detailed information about a specific score within a scorecard."""
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
            externalId
            createdAt
            updatedAt
            sections {{
                items {{
                    id
                    name
                    scores {{
                        items {{
                            id
                            name
                            key
                            description
                            type
                            order
                            externalId
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
            click.echo(f"Scorecard not found: {scorecard}")
            return
        
        # Find the score in the scorecard
        found_score = None
        section_name = None
        
        for section in scorecard_data.get('sections', {}).get('items', []):
            for score_item in section.get('scores', {}).get('items', []):
                if (score_item['id'] == score or 
                    score_item['key'] == score or 
                    score_item['name'] == score or 
                    score_item.get('externalId') == score):
                    found_score = score_item
                    section_name = section['name']
                    break
            if found_score:
                break
        
        if not found_score:
            click.echo(f"Score not found: {score}")
            return
        
        # Display the score information
        panel = Panel.fit(
            f"[bold]Score ID:[/bold] {found_score['id']}\n"
            f"[bold]Name:[/bold] {found_score['name']}\n"
            f"[bold]Key:[/bold] {found_score['key']}\n"
            f"[bold]Type:[/bold] {found_score['type']}\n"
            f"[bold]Order:[/bold] {found_score['order']}\n"
            f"[bold]External ID:[/bold] {found_score.get('externalId', 'None')}\n"
            f"[bold]Section:[/bold] {section_name}\n"
            f"[bold]Description:[/bold] {found_score.get('description', 'None')}\n",
            title=f"Score: {found_score['name']}",
            border_style="blue"
        )
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]Error retrieving score information: {e}[/red]")

# Add the same command to the score group as an alias
score.add_command(info)

@scores.command()
@click.option('--scorecard', required=True, help='Scorecard to list scores for (accepts ID, name, key, or external ID)')
@click.option('--limit', default=50, help='Maximum number of scores to return')
def list(scorecard: str, limit: int):
    """List scores in a scorecard with rich formatting."""
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
            externalId
            createdAt
            updatedAt
            sections {{
                items {{
                    id
                    name
                    scores {{
                        items {{
                            id
                            name
                            key
                            description
                            type
                            order
                            externalId
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
        
        # Format the scorecard panel with sections and detailed scores included
        from plexus.cli.ScorecardCommands import format_scorecard_panel
        panel = format_scorecard_panel(scorecard_data, include_sections=True, detailed_scores=True)
        
        # Override the panel title to indicate this is a scores listing
        panel.title = f"[bold magenta]Scores for {scorecard_data.get('name', 'Scorecard')}[/bold magenta]"
        
        console.print(panel)
        
    except Exception as e:
        click.echo(f"Error listing scores: {e}")

# Add an alias for the list command to the score group
score.add_command(list)

@score.command()
@click.option('--id', required=True, help='Score ID to list versions for')
def versions(id: str):
    """List all versions for a specific score."""
    client = create_client()
    
    # First, get the score details to check if it exists and get the champion version ID
    query = f"""
    query GetScore {{
        getScore(id: "{id}") {{
            id
            name
            key
            externalId
            championVersionId
            section {{
                id
                name
            }}
            versions {{
                items {{
                    id
                    createdAt
                    updatedAt
                    isFeatured
                    parentVersionId
                    note
                }}
            }}
        }}
    }}
    """
    
    try:
        result = client.execute(query)
        score_data = result.get('getScore')
        
        if not score_data:
            console.print(f"[red]Score not found with ID: {id}[/red]")
            return
        
        score_name = score_data.get('name')
        champion_version_id = score_data.get('championVersionId')
        section_name = score_data.get('section', {}).get('name', 'Unknown Section')
        
        console.print(f"[bold]Versions for score: {score_name} (ID: {id})[/bold]")
        console.print(f"[dim]Section: {section_name}[/dim]")
        console.print(f"[yellow]Current champion version ID: {champion_version_id}[/yellow]")
        
        # Get all versions
        versions = score_data.get('versions', {}).get('items', [])
        
        if not versions:
            console.print("[yellow]No versions found for this score.[/yellow]")
            return
        
        # Sort versions by creation date (newest first)
        versions.sort(key=lambda v: v.get('createdAt', ''), reverse=True)
        
        # Create a table to display the versions
        table = Table(title=f"Score Versions ({len(versions)} total)")
        table.add_column("ID", style="cyan")
        table.add_column("Created", style="green")
        table.add_column("Updated", style="green")
        table.add_column("Parent ID", style="blue")
        table.add_column("Champion", style="magenta")
        table.add_column("Note", style="yellow")
        
        for version in versions:
            version_id = version.get('id')
            created_at = version.get('createdAt')
            updated_at = version.get('updatedAt')
            parent_id = version.get('parentVersionId', 'None')
            is_champion = "✓" if version_id == champion_version_id else ""
            note = version.get('note', '')
            
            # Truncate note if it's too long
            if note and len(note) > 40:
                note = note[:37] + "..."
            
            table.add_row(
                version_id,
                created_at,
                updated_at,
                parent_id,
                is_champion,
                note
            )
        
        console.print(table)
        
        # Check if champion version exists in the versions list
        if champion_version_id:
            champion_exists = any(v.get('id') == champion_version_id for v in versions)
            if not champion_exists:
                console.print(f"[red]WARNING: Champion version ID {champion_version_id} does not exist in the versions list![/red]")
        
    except Exception as e:
        console.print(f"[red]Error listing score versions: {e}[/red]")

score.add_command(versions)