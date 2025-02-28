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
def scorecards():
    """Manage scorecards"""
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

def detect_and_clean_duplicates(client, scorecard_id: str) -> int:
    """
    Detect and clean up duplicate scores within a scorecard.
    
    Duplicates are identified by either:
    1. Identical score names within the same section
    2. Identical score names across different sections
    3. Identical externalIds within the scorecard
    
    Args:
        client: GraphQL client
        scorecard_id: ID of the scorecard to check
        
    Returns:
        Number of duplicates removed
    """
    console.print("[bold]Checking for duplicate scores...[/bold]")
    
    # Get all sections for this scorecard
    sections_query = f"""
    query GetScorecardSections {{
        getScorecard(id: "{scorecard_id}") {{
            sections {{
                items {{
                    id
                    name
                }}
            }}
        }}
    }}
    """
    
    try:
        sections_result = client.execute(sections_query)
        sections = sections_result.get('getScorecard', {}).get('sections', {}).get('items', [])
        
        console.print(f"[dim]Found {len(sections)} sections in scorecard[/dim]")
        
        total_duplicates_removed = 0
        
        # Process each section
        for section in sections:
            section_id = section.get('id')
            section_name = section.get('name')
            
            console.print(f"[dim]Checking section: {section_name} (ID: {section_id})[/dim]")
            
            # Get all scores for this section
            scores_query = f"""
            query GetSectionScores {{
                listScores(filter: {{ sectionId: {{ eq: "{section_id}" }} }}) {{
                    items {{
                        id
                        name
                        externalId
                        key
                        createdAt
                    }}
                }}
            }}
            """
            
            scores_result = client.execute(scores_query)
            scores = scores_result.get('listScores', {}).get('items', [])
            
            console.print(f"[dim]Found {len(scores)} scores in section {section_name}[/dim]")
            
            # Debug: Print all scores in this section
            for score in scores:
                console.print(f"[dim]Score: {score.get('name')} (ID: {score.get('id')}, externalId: {score.get('externalId')})[/dim]")
            
            # Group scores by normalized name (lowercase, trimmed)
            scores_by_name = {}
            for score in scores:
                name = score.get('name', '').strip().lower()
                if name not in scores_by_name:
                    scores_by_name[name] = []
                scores_by_name[name].append(score)
            
            # Find and remove duplicates by name
            for name, name_scores in scores_by_name.items():
                if len(name_scores) > 1:
                    # Sort by createdAt to keep oldest
                    sorted_scores = sorted(name_scores, key=lambda s: s.get('createdAt', ''))
                    keep_score = sorted_scores[0]
                    to_delete = sorted_scores[1:]
                    
                    console.print(f"[yellow]Found {len(to_delete)} duplicate scores with name '{name_scores[0].get('name')}' in section '{section_name}'[/yellow]")
                    console.print(f"[green]Keeping oldest: {keep_score.get('id')} (created: {keep_score.get('createdAt')})[/green]")
                    
                    # Display duplicates
                    console.print("\n[yellow]Duplicate scores:[/yellow]")
                    for i, duplicate in enumerate(to_delete):
                        console.print(f"{i+1}. ID: {duplicate.get('id')}, name: {duplicate.get('name')}, created: {duplicate.get('createdAt')}")
                    
                    # Prompt for deletion
                    if click.confirm(f"\nDo you want to delete these duplicate scores with name '{name_scores[0].get('name')}'?"):
                        # Delete duplicates
                        for duplicate in to_delete:
                            console.print(f"[yellow]Deleting duplicate: {duplicate.get('id')} (created: {duplicate.get('createdAt')})[/yellow]")
                            delete_mutation = f"""
                            mutation DeleteScore {{
                                deleteScore(input: {{ id: "{duplicate.get('id')}" }}) {{
                                    id
                                }}
                            }}
                            """
                            client.execute(delete_mutation)
                        total_duplicates_removed += 1
                    else:
                        console.print("[yellow]Duplicate deletion skipped[/yellow]")
        
        # Now check for duplicates by name across all sections
        console.print("\n[bold]Checking for duplicate scores across all sections...[/bold]")
        
        # Get all scores for the entire scorecard
        all_scores_query = f"""
        query GetAllScoresForScorecard {{
            getScorecard(id: "{scorecard_id}") {{
                sections {{
                    items {{
                        id
                        name
                        scores {{
                            items {{
                                id
                                name
                                externalId
                                createdAt
                                section {{
                                    id
                                    name
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        all_scores_result = client.execute(all_scores_query)
        all_scores = []
        section_map = {}
        
        # Flatten the scores from all sections and build section map
        sections = all_scores_result.get('getScorecard', {}).get('sections', {}).get('items', [])
        for section in sections:
            section_id = section.get('id')
            section_name = section.get('name')
            section_map[section_id] = section_name
            
            section_scores = section.get('scores', {}).get('items', [])
            all_scores.extend(section_scores)
        
        console.print(f"[dim]Checking for duplicate names across {len(all_scores)} total scores in all sections[/dim]")
        
        # Group by normalized name (lowercase, trimmed)
        scores_by_name_across_sections = {}
        for score in all_scores:
            name = score.get('name', '').strip().lower()
            if name and name != 'none':  # Skip empty or 'none' names
                if name not in scores_by_name_across_sections:
                    scores_by_name_across_sections[name] = []
                scores_by_name_across_sections[name].append(score)
        
        # Find and remove duplicates by name across sections
        for name, name_scores in scores_by_name_across_sections.items():
            if len(name_scores) > 1:
                # Sort by createdAt to keep oldest
                sorted_scores = sorted(name_scores, key=lambda s: s.get('createdAt', ''))
                keep_score = sorted_scores[0]
                to_delete = sorted_scores[1:]
                
                console.print(f"[yellow]Found {len(to_delete)} duplicate scores with name '{name_scores[0].get('name')}' across different sections[/yellow]")
                console.print(f"[green]Keeping oldest: {keep_score.get('id')} (created: {keep_score.get('createdAt')}) in section '{section_map.get(keep_score.get('section', {}).get('id'), 'Unknown')}'[/green]")
                
                # Display duplicates
                console.print("\n[yellow]Duplicate scores:[/yellow]")
                for i, duplicate in enumerate(to_delete):
                    section_id = duplicate.get('section', {}).get('id')
                    section_name = section_map.get(section_id, 'Unknown')
                    console.print(f"{i+1}. {duplicate.get('name')} (ID: {duplicate.get('id')}, section: {section_name}, created: {duplicate.get('createdAt')})")
                
                # Prompt for deletion
                if click.confirm(f"\nDo you want to delete these duplicate scores with name '{name_scores[0].get('name')}'?"):
                    # Delete duplicates
                    for duplicate in to_delete:
                        console.print(f"[yellow]Deleting duplicate: {duplicate.get('id')} (created: {duplicate.get('createdAt')})[/yellow]")
                        delete_mutation = f"""
                        mutation DeleteScore {{
                            deleteScore(input: {{ id: "{duplicate.get('id')}" }}) {{
                                id
                            }}
                        }}
                        """
                        client.execute(delete_mutation)
                    total_duplicates_removed += 1
                else:
                    console.print("[yellow]Duplicate deletion skipped[/yellow]")
        
        # Now check for duplicates by externalId across the entire scorecard
        console.print("\n[bold]Checking for duplicate external IDs...[/bold]")
        
        external_id_query = f"""
        query GetAllScoresForScorecard {{
            getScorecard(id: "{scorecard_id}") {{
                sections {{
                    items {{
                        scores {{
                            items {{
                                id
                                name
                                externalId
                                createdAt
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        external_id_result = client.execute(external_id_query)
        all_scores = []
        
        # Flatten the scores from all sections
        sections = external_id_result.get('getScorecard', {}).get('sections', {}).get('items', [])
        for section in sections:
            section_scores = section.get('scores', {}).get('items', [])
            all_scores.extend(section_scores)
        
        console.print(f"[dim]Checking for duplicate externalIds across {len(all_scores)} total scores[/dim]")
        
        # Group by externalId (if not None or empty)
        scores_by_external_id = {}
        for score in all_scores:
            external_id = score.get('externalId')
            if external_id and external_id.strip():
                if external_id not in scores_by_external_id:
                    scores_by_external_id[external_id] = []
                scores_by_external_id[external_id].append(score)
        
        # Find and remove duplicates by externalId
        for external_id, ext_id_scores in scores_by_external_id.items():
            if len(ext_id_scores) > 1:
                # Sort by createdAt to keep oldest
                sorted_scores = sorted(ext_id_scores, key=lambda s: s.get('createdAt', ''))
                keep_score = sorted_scores[0]
                to_delete = sorted_scores[1:]
                
                console.print(f"[yellow]Found {len(to_delete)} duplicate scores with externalId '{external_id}'[/yellow]")
                console.print(f"[green]Keeping oldest: {keep_score.get('id')} (created: {keep_score.get('createdAt')})[/green]")
                
                # Display duplicates
                console.print("\n[yellow]Duplicate scores:[/yellow]")
                for i, duplicate in enumerate(to_delete):
                    console.print(f"{i+1}. {duplicate.get('name')} (ID: {duplicate.get('id')}, created: {duplicate.get('createdAt')})")
                
                # Prompt for deletion
                if click.confirm(f"\nDo you want to delete these duplicate scores with externalId '{external_id}'?"):
                    # Delete duplicates
                    for duplicate in to_delete:
                        console.print(f"[yellow]Deleting duplicate: {duplicate.get('id')} (created: {duplicate.get('createdAt')})[/yellow]")
                        delete_mutation = f"""
                        mutation DeleteScore {{
                            deleteScore(input: {{ id: "{duplicate.get('id')}" }}) {{
                                id
                            }}
                        }}
                        """
                        client.execute(delete_mutation)
                    total_duplicates_removed += 1
                else:
                    console.print("[yellow]Duplicate deletion skipped[/yellow]")
        
        if total_duplicates_removed > 0:
            console.print(f"[green]Successfully removed {total_duplicates_removed} duplicate scores[/green]")
        else:
            console.print("[green]No duplicate scores found[/green]")
            
        return total_duplicates_removed
        
    except Exception as e:
        console.print(f"[red]Error checking for duplicates: {e}[/red]")
        return 0

def ensure_valid_external_ids(client, scorecard_id: str) -> int:
    """
    Ensure all scores in a scorecard have valid external IDs.
    
    If a score has a missing or empty external ID, this function will generate
    a new one based on the scorecard key and score key.
    
    Args:
        client: GraphQL client
        scorecard_id: ID of the scorecard to check
        
    Returns:
        Number of scores updated with new external IDs
    """
    console.print("[bold]Checking for missing or invalid external IDs...[/bold]")
    
    # Get scorecard details to access the key
    scorecard_query = f"""
    query GetScorecardDetails {{
        getScorecard(id: "{scorecard_id}") {{
            key
            sections {{
                items {{
                    id
                    name
                    scores {{
                        items {{
                            id
                            name
                            key
                            externalId
                        }}
                    }}
                }}
            }}
        }}
    }}
    """
    
    try:
        scorecard_result = client.execute(scorecard_query)
        scorecard = scorecard_result.get('getScorecard', {})
        scorecard_key = scorecard.get('key', '')
        
        if not scorecard_key:
            console.print("[red]Could not retrieve scorecard key[/red]")
            return 0
        
        sections = scorecard.get('sections', {}).get('items', [])
        total_updated = 0
        
        for section in sections:
            section_name = section.get('name', 'Unknown Section')
            scores = section.get('scores', {}).get('items', [])
            
            for score in scores:
                score_id = score.get('id')
                score_name = score.get('name', 'Unknown Score')
                score_key = score.get('key', '')
                external_id = score.get('externalId', '')
                
                # If external ID is missing or empty, generate a new one
                if not external_id or not external_id.strip():
                    # Generate a key if one doesn't exist
                    if not score_key or not score_key.strip():
                        score_key = generate_key(score_name)
                    
                    # Create a new external ID based on scorecard key and score key
                    external_id = f"{scorecard_key}_{score_key}"
                    
                    console.print(f"[yellow]Updating score '{score_name}' with new externalId: {external_id}[/yellow]")
                    
                    # Update the score with the new external ID
                    mutation = f"""
                    mutation UpdateScore {{
                        updateScore(input: {{
                            id: "{score_id}",
                            externalId: "{external_id}"
                        }}) {{
                            id
                            externalId
                        }}
                    }}
                    """
                    
                    client.execute(mutation)
                    total_updated += 1
        
        if total_updated > 0:
            console.print(f"[green]Updated {total_updated} scores with new external IDs[/green]")
        else:
            console.print("[green]All scores have valid external IDs[/green]")
            
        return total_updated
        
    except Exception as e:
        console.print(f"[red]Error checking external IDs: {e}[/red]")
        return 0

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
                        external_id = score.get('externalId', '')
                        
                        # Display external ID next to score name if available
                        if external_id:
                            content.append(f"{score_prefix}[blue]{score_name}[/blue] [dim]({external_id})[/dim]")
                        else:
                            content.append(f"{score_prefix}[blue]{score_name}[/blue]")
                        
                        # Add detailed score information if requested
                        if detailed_scores:
                            score_id = score.get('id', 'N/A')
                            score_key = score.get('key', 'N/A')
                            indent_prefix = score_prefix.replace("└──", "    ").replace("├──", "│   ")
                            content.append(f"{indent_prefix}  ID: [magenta]{score_id}[/magenta]")
                            content.append(f"{indent_prefix}  Key: [blue]{score_key}[/blue]")
                            if not external_id:
                                content.append(f"{indent_prefix}  External ID: [yellow]Missing[/yellow]")
    
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
@click.option('--scorecard', required=True, help='Scorecard to fix (accepts ID, name, key, or external ID)')
@click.option('--skip-duplicate-check', is_flag=True, help='Skip checking for and removing duplicate scores')
@click.option('--skip-external-id-check', is_flag=True, help='Skip checking for and fixing missing external IDs')
def fix(scorecard: str, skip_duplicate_check: bool, skip_external_id_check: bool):
    """Fix data integrity issues in an existing scorecard.
    
    This command finds a scorecard by the provided identifier, checks for duplicates,
    and allows the user to interactively remove them. It also checks for and fixes
    missing external IDs.
    
    Examples:
        plexus scorecards fix --scorecard "QA Scorecard"
        plexus scorecards fix --scorecard qa-v1 --skip-duplicate-check
        plexus scorecards fix --scorecard 1234 --skip-external-id-check
    """
    client = create_client()
    
    # First, resolve the scorecard identifier to an ID
    scorecard_id = resolve_scorecard_identifier(client, scorecard)
    if not scorecard_id:
        console.print(f"[red]Could not find scorecard: {scorecard}[/red]")
        return
    
    # Get scorecard details for display
    query = f"""
    query GetScorecardDetails {{
        getScorecard(id: "{scorecard_id}") {{
            id
            name
            key
        }}
    }}
    """
    
    try:
        result = client.execute(query)
        scorecard_data = result.get('getScorecard', {})
        scorecard_name = scorecard_data.get('name', 'Unknown')
        
        console.print(f"[green]Found scorecard: {scorecard_name} (ID: {scorecard_id})[/green]")
        
        # Step 1: Check for duplicate scores within the scorecard
        if not skip_duplicate_check:
            console.print("\n[bold]Checking for duplicate scores...[/bold]")
            
            # Get all sections for this scorecard
            sections_query = f"""
            query GetScorecardSections {{
                getScorecard(id: "{scorecard_id}") {{
                    sections {{
                        items {{
                            id
                            name
                        }}
                    }}
                }}
            }}
            """
            
            sections_result = client.execute(sections_query)
            sections = sections_result.get('getScorecard', {}).get('sections', {}).get('items', [])
            
            total_duplicates_removed = 0
            
            # Process each section
            for section in sections:
                section_id = section.get('id')
                section_name = section.get('name')
                
                # Get all scores for this section
                scores_query = f"""
                query GetSectionScores {{
                    listScores(filter: {{ sectionId: {{ eq: "{section_id}" }} }}) {{
                        items {{
                            id
                            name
                            externalId
                            key
                            createdAt
                        }}
                    }}
                }}
                """
                
                scores_result = client.execute(scores_query)
                scores = scores_result.get('listScores', {}).get('items', [])
                
                # Group scores by normalized name (lowercase, trimmed)
                scores_by_name = {}
                for score in scores:
                    name = score.get('name', '').strip().lower()
                    if name not in scores_by_name:
                        scores_by_name[name] = []
                    scores_by_name[name].append(score)
                
                # Find and remove duplicates by name
                for name, name_scores in scores_by_name.items():
                    if len(name_scores) > 1:
                        # Sort by createdAt to keep oldest
                        sorted_scores = sorted(name_scores, key=lambda s: s.get('createdAt', ''))
                        keep_score = sorted_scores[0]
                        to_delete = sorted_scores[1:]
                        
                        console.print(f"[yellow]Found {len(to_delete)} duplicate scores with name '{name_scores[0].get('name')}' in section '{section_name}'[/yellow]")
                        console.print(f"[green]Keeping oldest: {keep_score.get('id')} (created: {keep_score.get('createdAt')})[/green]")
                        
                        # Display duplicates
                        console.print("\n[yellow]Duplicate scores:[/yellow]")
                        for i, duplicate in enumerate(to_delete):
                            console.print(f"{i+1}. ID: {duplicate.get('id')}, name: {duplicate.get('name')}, created: {duplicate.get('createdAt')}")
                        
                        # Prompt for deletion
                        if click.confirm(f"\nDo you want to delete these duplicate scores with name '{name_scores[0].get('name')}'?"):
                            # Delete duplicates
                            for duplicate in to_delete:
                                console.print(f"[yellow]Deleting duplicate: {duplicate.get('id')} (created: {duplicate.get('createdAt')})[/yellow]")
                                delete_mutation = f"""
                                mutation DeleteScore {{
                                    deleteScore(input: {{ id: "{duplicate.get('id')}" }}) {{
                                        id
                                    }}
                                }}
                                """
                                client.execute(delete_mutation)
                            total_duplicates_removed += 1
                        else:
                            console.print("[yellow]Duplicate deletion skipped[/yellow]")
        
        # Step 2: Check for missing external IDs
        if not skip_external_id_check:
            ensure_valid_external_ids(client, scorecard_id)
        
        console.print("\n[green]Fix operation completed successfully[/green]")
        
    except Exception as e:
        console.print(f"[red]Error during fix operation: {e}[/red]")

@scorecards.command()
@click.option('--scorecard', required=True, help='Scorecard to push (accepts ID, name, key, or external ID)')
@click.option('--account', default='call-criteria', help='Account to push scorecard to (accepts ID, name, or key)')
@click.option('--skip-duplicate-check', is_flag=True, help='Skip checking for and removing duplicate scores')
@click.option('--skip-external-id-check', is_flag=True, help='Skip checking for and fixing missing external IDs')
@click.option('--file', help='Path to specific YAML file to push (if not provided, will search in scorecards/ directory)')
def push(scorecard: str, account: str, skip_duplicate_check: bool, skip_external_id_check: bool, file: Optional[str] = None):
    """Push scorecard configuration to the API.
    
    This command finds a scorecard by the provided identifier, loads its configuration from a YAML file,
    checks for duplicates, and allows the user to interactively remove them before proceeding.
    
    If no --file parameter is provided, the command will search for a matching YAML file in the scorecards/ directory
    based on the scorecard ID, key, or name.
    
    Examples:
        plexus scorecards push --scorecard "QA Scorecard"
        plexus scorecards push --scorecard qa-v1 --skip-duplicate-check
        plexus scorecards push --scorecard 1234 --account acme
        plexus scorecards push --scorecard "QA Scorecard" --file ./my-scorecards/qa.yaml
    """
    client = create_client()
    
    # First, resolve the scorecard identifier to an ID
    scorecard_id = resolve_scorecard_identifier(client, scorecard)
    if not scorecard_id:
        console.print(f"[red]Could not find scorecard: {scorecard}[/red]")
        return
    
    # Get scorecard details for display
    query = f"""
    query GetScorecardDetails {{
        getScorecard(id: "{scorecard_id}") {{
            id
            name
            key
            externalId
        }}
    }}
    """
    
    try:
        result = client.execute(query)
        scorecard_data = result.get('getScorecard', {})
        scorecard_name = scorecard_data.get('name', 'Unknown')
        scorecard_key = scorecard_data.get('key', 'Unknown')
        scorecard_external_id = scorecard_data.get('externalId', 'None')
        
        console.print(f"[green]Found scorecard: {scorecard_name} (ID: {scorecard_id}, Key: {scorecard_key}, External ID: {scorecard_external_id})[/green]")
        
        # Load YAML configuration
        yaml_data = None
        
        if file:
            # Load from specified file
            if not os.path.exists(file):
                console.print(f"[red]File not found: {file}[/red]")
                return
            
            try:
                with open(file, 'r') as f:
                    yaml_data = yaml.safe_load(f)
                console.print(f"[green]Loaded configuration from {file}[/green]")
            except Exception as e:
                console.print(f"[red]Error loading YAML from {file}: {e}[/red]")
                return
        else:
            # Search for matching YAML file in scorecards/ directory
            if not os.path.exists('scorecards'):
                console.print("[red]scorecards/ directory not found[/red]")
                return
            
            yaml_files = [f for f in os.listdir('scorecards') if f.endswith('.yaml')]
            if not yaml_files:
                console.print("[red]No YAML files found in scorecards/ directory[/red]")
                return
            
            # Try to find a matching file by ID, key, or name
            matching_file = None
            for yaml_file in yaml_files:
                try:
                    with open(os.path.join('scorecards', yaml_file), 'r') as f:
                        data = yaml.safe_load(f)
                        if data.get('id') == scorecard_id or data.get('key') == scorecard_key or data.get('name') == scorecard_name:
                            matching_file = os.path.join('scorecards', yaml_file)
                            yaml_data = data
                            break
                except Exception:
                    continue
            
            if not matching_file:
                console.print(f"[red]Could not find matching YAML file for scorecard: {scorecard_name}[/red]")
                return
            
            console.print(f"[green]Found and loaded configuration from {matching_file}[/green]")
        
        # Update scorecard metadata if necessary
        if yaml_data.get('name') != scorecard_name or yaml_data.get('key') != scorecard_key or yaml_data.get('externalId') != scorecard_external_id:
            update_mutation = f"""
            mutation UpdateScorecard {{
                updateScorecard(input: {{
                    id: "{scorecard_id}"
                    name: "{yaml_data.get('name', scorecard_name)}"
                    key: "{yaml_data.get('key', scorecard_key)}"
                    externalId: "{yaml_data.get('externalId', scorecard_external_id)}"
                }}) {{
                    id
                    name
                    key
                    externalId
                }}
            }}
            """
            client.execute(update_mutation)
            console.print("[green]Updated scorecard metadata[/green]")
        
        # Process scores
        if 'scores' in yaml_data:
            console.print(f"[green]Found {len(yaml_data['scores'])} scores in YAML configuration[/green]")
            
            # Get existing scores for this scorecard
            existing_scores_query = f"""
            query GetScorecardScores {{
                getScorecard(id: "{scorecard_id}") {{
                    sections {{
                        items {{
                            id
                            name
                            scores {{
                                items {{
                                    id
                                    name
                                    key
                                    externalId
                                    championVersionId
                                    versions {{
                                        items {{
                                            id
                                            configuration
                                            isFeatured
                                            createdAt
                                            updatedAt
                                            parentVersionId
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            """
            
            existing_scores_result = client.execute(existing_scores_query)
            sections = existing_scores_result.get('getScorecard', {}).get('sections', {}).get('items', [])
            
            # Create a map of section name to ID
            section_map = {section.get('name'): section.get('id') for section in sections}
            
            # Create a map of score name to ID within each section
            score_map = {}
            for section in sections:
                section_id = section.get('id')
                section_name = section.get('name')
                if section_name not in score_map:
                    score_map[section_name] = {}
                
                scores = section.get('scores', {}).get('items', [])
                for score in scores:
                    score_name = score.get('name')
                    score_map[section_name][score_name] = score
            
            # Process each score in the YAML
            for score_data in yaml_data['scores']:
                score_name = score_data.get('name')
                section_name = score_data.get('section', 'Default')
                
                # Create section if it doesn't exist
                if section_name not in section_map:
                    create_section_mutation = f"""
                    mutation CreateSection {{
                        createScorecardSection(input: {{
                            name: "{section_name}"
                            order: 0
                            scorecardId: "{scorecard_id}"
                        }}) {{
                            id
                            name
                        }}
                    }}
                    """
                    section_result = client.execute(create_section_mutation)
                    section_id = section_result.get('createScorecardSection', {}).get('id')
                    section_map[section_name] = section_id
                    score_map[section_name] = {}
                    console.print(f"[green]Created new section: {section_name}[/green]")
                else:
                    section_id = section_map[section_name]
                
                # Check if score exists
                if section_name in score_map and score_name in score_map[section_name]:
                    # Update existing score
                    existing_score = score_map[section_name][score_name]
                    score_id = existing_score.get('id')
                    
                    # Handle ScoreVersion management
                    # Convert score_data to JSON string for configuration
                    score_config = json.dumps(score_data)
                    
                    # Get existing versions for this score
                    existing_versions = existing_score.get('versions', {}).get('items', [])
                    existing_versions.sort(key=lambda v: v.get('createdAt', ''), reverse=True)
                    
                    # Find parent version
                    parent_version_id = None
                    parent_version = None
                    
                    # Check if parent ID is specified in YAML
                    if 'parent' in score_data:
                        parent_version_id = score_data.get('parent')
                        # Find the parent version in existing versions
                        for version in existing_versions:
                            if version.get('id') == parent_version_id:
                                parent_version = version
                                break
                    elif existing_versions:
                        # Use most recent version as parent
                        parent_version = existing_versions[0]
                        parent_version_id = parent_version.get('id')
                    
                    # Determine if we need to create a new version
                    create_new_version = True
                    
                    if parent_version:
                        # Compare configurations (excluding parent field)
                        parent_config = parent_version.get('configuration', '{}')
                        
                        try:
                            # Try to parse the parent configuration as YAML
                            parent_config_obj = yaml.safe_load(parent_config)
                        except:
                            # If parsing fails, try JSON as fallback
                            try:
                                parent_config_obj = json.loads(parent_config)
                            except:
                                parent_config_obj = {}
                        
                        # Create a copy of score_data without parent field for comparison
                        score_data_for_comparison = score_data.copy()
                        if 'parent' in score_data_for_comparison:
                            del score_data_for_comparison['parent']
                        
                        # Remove parent from parent_config_obj if it exists
                        if isinstance(parent_config_obj, dict) and 'parent' in parent_config_obj:
                            del parent_config_obj['parent']
                        
                        # Compare the configurations
                        if yaml.dump(score_data_for_comparison, sort_keys=True) == yaml.dump(parent_config_obj, sort_keys=True):
                            create_new_version = False
                            console.print(f"[green]No changes detected for score: {score_name}[/green]")
                    
                    # Check if external ID needs to be updated regardless of configuration changes
                    yaml_id = str(score_data.get('id', ''))
                    current_external_id = existing_score.get('externalId', '')
                    
                    if yaml_id and yaml_id != current_external_id:
                        console.print(f"[yellow]External ID mismatch for score: {score_name}[/yellow]")
                        console.print(f"[yellow]  Current: {current_external_id}[/yellow]")
                        console.print(f"[yellow]  YAML: {yaml_id}[/yellow]")
                        
                        # Update the external ID even if no other changes
                        update_external_id_mutation = f"""
                        mutation UpdateScoreExternalId {{
                            updateScore(input: {{
                                id: "{score_id}"
                                externalId: "{yaml_id}"
                            }}) {{
                                id
                                name
                                externalId
                            }}
                        }}
                        """
                        external_id_result = client.execute(update_external_id_mutation)
                        console.print(f"[green]Updated external ID for score: {score_name} to {yaml_id}[/green]")
                    
                    if create_new_version:
                        # Add parent ID to score_data for the new version
                        if parent_version_id:
                            score_data['parent'] = parent_version_id
                        
                        # Convert score_data to YAML string for configuration
                        yaml_config = yaml.dump(score_data)
                        
                        # Create new ScoreVersion
                        now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                        
                        # Handle parentVersionId - if null, don't include it in the mutation
                        parent_version_field = f'parentVersionId: "{parent_version_id}",' if parent_version_id else ""
                        
                        create_version_mutation = f"""
                        mutation CreateScoreVersion {{
                            createScoreVersion(input: {{
                                scoreId: "{score_id}"
                                configuration: {json.dumps(yaml_config)}
                                isFeatured: true
                                createdAt: "{now}"
                                updatedAt: "{now}"
                                {parent_version_field}
                            }}) {{
                                id
                                scoreId
                                configuration
                                isFeatured
                                createdAt
                                updatedAt
                                parentVersionId
                            }}
                        }}
                        """
                        
                        version_result = client.execute(create_version_mutation)
                        new_version_id = version_result.get('createScoreVersion', {}).get('id')
                        
                        # Update Score to point to new champion version
                        # Always use the 'id' field from the YAML as the external ID
                        external_id = str(score_data.get('id', ''))
                        
                        update_score_mutation = f"""
                        mutation UpdateScore {{
                            updateScore(input: {{
                                id: "{score_id}"
                                championVersionId: "{new_version_id}"
                                name: "{score_name}"
                                key: "{score_data.get('key', '')}"
                                externalId: "{external_id}"
                                aiProvider: "{score_data.get('model_provider', '')}"
                                aiModel: "{score_data.get('model_name', '')}"
                            }}) {{
                                id
                                name
                                championVersionId
                                externalId
                            }}
                        }}
                        """
                        client.execute(update_score_mutation)
                        console.print(f"[green]Created new version for score: {score_name}[/green]")
                else:
                    # Create new score
                    # Generate a key if one doesn't exist
                    score_key = score_data.get('key', '')
                    if not score_key or not score_key.strip():
                        score_key = generate_key(score_name)
                    
                    # Always use the 'id' field from the YAML as the external ID
                    external_id = str(score_data.get('id', ''))
                    
                    create_score_mutation = f"""
                    mutation CreateScore {{
                        createScore(input: {{
                            name: "{score_name}"
                            key: "{score_key}"
                            externalId: "{external_id}"
                            order: 0
                            type: "STANDARD"
                            aiProvider: "{score_data.get('model_provider', '')}"
                            aiModel: "{score_data.get('model_name', '')}"
                            sectionId: "{section_id}"
                        }}) {{
                            id
                            name
                            externalId
                        }}
                    }}
                    """
                    score_result = client.execute(create_score_mutation)
                    new_score_id = score_result.get('createScore', {}).get('id')
                    
                    # Create initial ScoreVersion for the new score
                    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                    
                    # Convert score_data to YAML string for configuration
                    yaml_config = yaml.dump(score_data)
                    
                    create_version_mutation = f"""
                    mutation CreateScoreVersion {{
                        createScoreVersion(input: {{
                            scoreId: "{new_score_id}"
                            configuration: {json.dumps(yaml_config)}
                            isFeatured: true
                            createdAt: "{now}"
                            updatedAt: "{now}"
                        }}) {{
                            id
                            scoreId
                            configuration
                            isFeatured
                            createdAt
                            updatedAt
                        }}
                    }}
                    """
                    
                    version_result = client.execute(create_version_mutation)
                    new_version_id = version_result.get('createScoreVersion', {}).get('id')
                    
                    # Update Score to point to new champion version
                    # Always use the 'id' field from the YAML as the external ID
                    external_id = str(score_data.get('id', ''))
                    
                    update_score_mutation = f"""
                    mutation UpdateScore {{
                        updateScore(input: {{
                            id: "{new_score_id}"
                            championVersionId: "{new_version_id}"
                            name: "{score_name}"
                            key: "{score_data.get('key', '')}"
                            externalId: "{external_id}"
                            aiProvider: "{score_data.get('model_provider', '')}"
                            aiModel: "{score_data.get('model_name', '')}"
                        }}) {{
                            id
                            name
                            championVersionId
                            externalId
                        }}
                    }}
                    """
                    client.execute(update_score_mutation)
                    console.print(f"[green]Created new score with initial version: {score_name}[/green]")
        
        # Check for duplicates if requested
        if not skip_duplicate_check:
            detect_and_clean_duplicates(client, scorecard_id)
        
        # Check for missing external IDs if requested
        if not skip_external_id_check:
            ensure_valid_external_ids(client, scorecard_id)
        
        console.print("\n[green]Push operation completed successfully[/green]")
        
    except Exception as e:
        console.print(f"[red]Error during push operation: {e}[/red]") 