import click
import os
import sys
from pathlib import Path
import json
from ruamel.yaml import YAML
import io
from rich.table import Table
from rich.panel import Panel
from plexus.cli.shared.console import console
from plexus.dashboard.api.client import PlexusDashboardClient
from typing import Optional
import rich
import datetime
from plexus.cli.shared.file_editor import FileEditor
from plexus.cli.shared import sanitize_path_name
from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier
from functools import lru_cache

# Define the main command groups that will be exported
@click.group()
def scorecards():
    """Commands for managing scorecards."""
    pass

@click.group()
def scorecard():
    """Manage individual scorecards (alias for 'scorecards')"""
    pass

# Helper functions for resolving identifiers

def create_client() -> PlexusDashboardClient:
    """Create a client and log its configuration"""
    client = PlexusDashboardClient()
    return client

def generate_key(name: str) -> str:
    """Generate a key from a name by converting to lowercase and replacing spaces with hyphens."""
    return name.lower().replace(' ', '-')

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
    
    # Try lookup by key
    try:
        query = f"""
        query ListAccounts {{
            listAccounts(filter: {{ key: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listAccounts', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    # Try lookup by name
    try:
        query = f"""
        query ListAccounts {{
            listAccounts(filter: {{ name: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listAccounts', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    return None

# Configure ruamel.yaml for better multi-line string handling
def get_yaml_handler():
    """Returns a configured YAML handler that preserves multi-line strings."""
    yaml_handler = YAML()
    yaml_handler.preserve_quotes = True
    yaml_handler.width = 4096  # Prevent line wrapping
    yaml_handler.indent(mapping=2, sequence=4, offset=2)
    yaml_handler.allow_duplicate_keys = True  # Allow duplicate keys in YAML
    return yaml_handler

def detect_and_clean_duplicates(client, scorecard_id: str) -> int:
    """
    Detect and clean duplicate scores in a scorecard.
    Also checks for duplicate scorecards by key.
    
    Args:
        client: GraphQL client
        scorecard_id: Scorecard ID
        
    Returns:
        Number of duplicates removed
    """
    # First, check for duplicate scorecards by key
    console.print("[bold]Checking for duplicate scorecards by key...[/bold]")
    
    # Get the current scorecard to find its key
    scorecard_query = f"""
    query GetScorecard {{
        getScorecard(id: "{scorecard_id}") {{
            id
            name
            key
            accountId
        }}
    }}
    """
    
    try:
        scorecard_result = client.execute(scorecard_query)
        scorecard = scorecard_result.get('getScorecard', {})
        scorecard_key = scorecard.get('key')
        account_id = scorecard.get('accountId')
        
        if not scorecard_key:
            console.print("[yellow]Current scorecard has no key, skipping duplicate scorecard check[/yellow]")
        else:
            # Find all scorecards with the same key
            duplicate_query = f"""
            query FindDuplicateScorecards {{
                listScorecardByKey(key: "{scorecard_key}") {{
                    items {{
                        id
                        name
                        key
                        accountId
                        createdAt
                        updatedAt
                    }}
                }}
            }}
            """
            
            duplicate_result = client.execute(duplicate_query)
            duplicate_scorecards = duplicate_result.get('listScorecardByKey', {}).get('items', [])
            
            if len(duplicate_scorecards) > 1:
                console.print(f"[yellow]Found {len(duplicate_scorecards)} scorecards with key '{scorecard_key}':[/yellow]")
                
                # Create a table to display the duplicates
                table = Table(title=f"Duplicate Scorecards with Key: {scorecard_key}")
                table.add_column("#", style="dim")
                table.add_column("ID", style="magenta")
                table.add_column("Name", style="blue")
                table.add_column("Account ID", style="cyan")
                table.add_column("Created At", style="dim")
                table.add_column("Updated At", style="dim")
                table.add_column("Current", style="green")
                
                # Add index number for selection
                for i, dup in enumerate(duplicate_scorecards):
                    is_current = dup.get('id') == scorecard_id
                    table.add_row(
                        str(i + 1),
                        dup.get('id'),
                        dup.get('name'),
                        dup.get('accountId'),
                        dup.get('createdAt'),
                        dup.get('updatedAt'),
                        "✓" if is_current else ""
                    )
                
                console.print(table)
                console.print("[yellow]Warning: Multiple scorecards with the same key can cause confusion and issues.[/yellow]")
                
                # Prompt user to choose which scorecard to delete
                if click.confirm("Do you want to delete one of these duplicate scorecards?"):
                    # Get user choice
                    max_choice = len(duplicate_scorecards)
                    choice_str = click.prompt(
                        f"Enter the number of the scorecard to delete (1-{max_choice})",
                        type=str
                    )
                    
                    try:
                        choice = int(choice_str)
                        if choice < 1 or choice > max_choice:
                            console.print(f"[red]Invalid choice: {choice}. Must be between 1 and {max_choice}.[/red]")
                            return 0
                    except ValueError:
                        console.print(f"[red]Invalid input: {choice_str}. Please enter a number.[/red]")
                        return 0
                    
                    # Get the selected scorecard
                    selected_scorecard = duplicate_scorecards[choice - 1]
                    selected_id = selected_scorecard.get('id')
                    selected_name = selected_scorecard.get('name')
                    
                    # Confirm deletion
                    console.print(f"[bold red]You are about to delete scorecard: {selected_name} (ID: {selected_id})[/bold red]")
                    console.print("[red]This will permanently delete the scorecard and all its scores and versions.[/red]")
                    
                    if click.confirm("Are you sure you want to proceed?", default=False):
                        # Get all sections and scores for this scorecard
                        detailed_query = f"""
                        query GetScorecardDetails {{
                            getScorecard(id: "{selected_id}") {{
                                id
                                name
                                key
                                sections {{
                                    items {{
                                        id
                                        name
                                        scores {{
                                            items {{
                                                id
                                                name
                                                versions {{
                                                    items {{
                                                        id
                                                    }}
                                                }}
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                        }}
                        """
                        
                        try:
                            detailed_result = client.execute(detailed_query)
                            detailed_scorecard = detailed_result.get('getScorecard', {})
                            sections = detailed_scorecard.get('sections', {}).get('items', [])
                            
                            total_sections = len(sections)
                            total_scores = 0
                            total_versions = 0
                            
                            # First, delete all versions for each score
                            for section in sections:
                                section_id = section.get('id')
                                section_name = section.get('name')
                                scores = section.get('scores', {}).get('items', [])
                                
                                for score in scores:
                                    score_id = score.get('id')
                                    score_name = score.get('name')
                                    versions = score.get('versions', {}).get('items', [])
                                    
                                    total_scores += 1
                                    total_versions += len(versions)
                                    
                                    # Delete each version
                                    for version in versions:
                                        version_id = version.get('id')
                                        delete_version_mutation = f"""
                                        mutation DeleteScoreVersion {{
                                            deleteScoreVersion(input: {{ id: "{version_id}" }}) {{
                                                id
                                            }}
                                        }}
                                        """
                                        client.execute(delete_version_mutation)
                                    
                                    # Delete the score
                                    delete_score_mutation = f"""
                                    mutation DeleteScore {{
                                        deleteScore(input: {{ id: "{score_id}" }}) {{
                                            id
                                        }}
                                    }}
                                    """
                                    client.execute(delete_score_mutation)
                                
                                # Delete the section
                                delete_section_mutation = f"""
                                mutation DeleteScorecardSection {{
                                    deleteScorecardSection(input: {{ id: "{section_id}" }}) {{
                                        id
                                    }}
                                }}
                                """
                                client.execute(delete_section_mutation)
                            
                            # Finally delete the scorecard
                            delete_scorecard_mutation = f"""
                            mutation DeleteScorecard {{
                                deleteScorecard(input: {{ id: "{selected_id}" }}) {{
                                    id
                                }}
                            }}
                            """
                            client.execute(delete_scorecard_mutation)
                            
                            console.print(f"[green]Successfully deleted scorecard: {selected_name} (ID: {selected_id})[/green]")
                            console.print(f"[green]Deleted {total_sections} sections, {total_scores} scores, and {total_versions} versions.[/green]")
                            
                        except Exception as e:
                            console.print(f"[red]Error deleting scorecard: {e}[/red]")
                    else:
                        console.print("[yellow]Deletion cancelled[/yellow]")
                else:
                    console.print("[yellow]Consider renaming or deleting duplicate scorecards to avoid confusion.[/yellow]")
            else:
                console.print(f"[green]No duplicate scorecards found with key '{scorecard_key}'[/green]")
    
    except Exception as e:
        console.print(f"[red]Error checking for duplicate scorecards: {e}[/red]")
    
    # Continue with the original function to check for duplicate scores
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
    
    Args:
        client: GraphQL client
        scorecard_id: Scorecard ID
        
    Returns:
        Number of scores updated
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
                    # Sort scores by order (primary) and externalId (secondary)
                    def get_sort_key(score):
                        # Remove debug print
                        
                        # Get order as primary sort key
                        order = score.get('order')
                        
                        # Get externalId as secondary sort key
                        external_id = score.get('externalId', '0')
                        try:
                            ext_id_int = int(external_id)
                        except (ValueError, TypeError):
                            ext_id_int = float('inf')  # Place scores without valid numeric externalId at the end
                        
                        # Return tuple for sorting: (order or infinity, externalId)
                        # This ensures scores are sorted by order first, then by externalId
                        return (order if order is not None else float('inf'), ext_id_int)
                    
                    sorted_scores = sorted(section['scores'].get('items', []), key=get_sort_key)
                    
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
        
        # Use the shared formatting function with sections included
        panel = format_scorecard_panel(scorecard_data, include_sections=True)
        console.print(panel)
        
    except Exception as e:
        click.echo(f"Error getting scorecard info: {e}")

@scorecards.command()
@click.option('--scorecard', required=True, help='Scorecard to delete (accepts ID, name, key, or external ID)')
@click.option('--force', is_flag=True, help='Skip confirmation prompt')
def delete(scorecard: str, force: bool):
    """Delete a scorecard."""
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
            mutation DeleteScorecardSection {{
                deleteScorecardSection(input: {{ id: "{section_id}" }}) {{
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
@click.option('--account', default=lambda: os.getenv('PLEXUS_ACCOUNT_KEY'), help='Account to pull scorecards from (accepts ID, name, or key)')
@click.option('--output', default='scorecards', help='Directory to save YAML files')
def pull(scorecard: Optional[str], account: str, output: str):
    """Pull scorecards from the dashboard and save as YAML files."""
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
            # If a specific scorecard was provided, resolve it to an ID
            scorecard_id = resolve_scorecard_identifier(client, scorecard)
            if not scorecard_id:
                console.print(f"[red]No scorecard found matching: {scorecard}[/red]")
                return
            
            filter_conditions.append(f'id: {{ eq: "{scorecard_id}" }}')
        
        filter_string = ", ".join(filter_conditions)
        
        query = f"""
        query ListScorecards {{
            listScorecards(filter: {{ {filter_string} }}) {{
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
                                    isDisabled
                                    championVersionId
                                    championVersion {{
                                        id
                                        configuration
                                        createdAt
                                        updatedAt
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
                        'externalId': score.get('externalId', ''),
                        'disabled': score.get('isDisabled', False),  # Map isDisabled to disabled
                        'championVersionId': score.get('championVersion', {}).get('id', ''),
                        'versions': []
                    }
                    
                    # Add configuration if available
                    champion_version = score.get('championVersion')
                    if champion_version:
                        config_yaml = champion_version.get('configuration', '')
                        if config_yaml:
                            try:
                                # Parse the configuration YAML
                                yaml_handler = get_yaml_handler()
                                config_yaml_stream = io.StringIO(config_yaml)
                                config_data = yaml_handler.load(config_yaml_stream)
                                if isinstance(config_data, dict):
                                    # Merge the configuration with the score data
                                    # This preserves the full YAML structure
                                    # Add section back to the config data
                                    config_data['section'] = section.get('name')
                                    
                                    # Ensure disabled status is included in the config
                                    if 'disabled' not in config_data:
                                        config_data['disabled'] = score.get('isDisabled', False)
                                    
                                    # Replace score_data with the full config
                                    score_data = config_data
                                else:
                                    console.print(f"[yellow]Warning: Configuration for score {score.get('name')} is not a valid YAML dictionary[/yellow]")
                            except Exception as e:
                                console.print(f"[yellow]Warning: Could not parse configuration for score {score.get('name')}: {e}[/yellow]")
                    
                    section_data['scores'].append(score_data)
                
                yaml_data['sections'].append(section_data)
            
            # Write to file
            file_name = f"{scorecard_key}.yaml"
            file_path = os.path.join(output, file_name)
            
            # Restructure the YAML data to match the expected format
            # Move scores to the top level
            scores = []
            for section in yaml_data['sections']:
                for score in section['scores']:
                    scores.append(score)
            
            # Create the final YAML structure
            final_yaml = {
                'name': yaml_data['name'],
                'key': yaml_data['key'],
                'description': yaml_data.get('description', ''),
                'externalId': yaml_data.get('externalId', ''),
                'scores': scores
            }
            
            with open(file_path, 'w') as f:
                # Use ruamel.yaml for better handling of multi-line strings
                yaml_handler = get_yaml_handler()
                yaml_handler.dump(final_yaml, f)
            
            console.print(f"[green]Saved scorecard to {file_path}[/green]")
        
        console.print("\n[green]Pull operation completed[/green]")
    
    except Exception as e:
        console.print(f"[red]Error during pull operation: {e}[/red]")

@scorecards.command()
@click.option('--scorecard', required=True, help='Scorecard to fix (accepts ID, name, key, or external ID)')
@click.option('--skip-duplicate-check', is_flag=True, help='Skip checking for and removing duplicate scores')
@click.option('--skip-external-id-check', is_flag=True, help='Skip checking for and fixing missing external IDs')
def fix(scorecard: str, skip_duplicate_check: bool, skip_external_id_check: bool):
    """Fix common issues with a scorecard."""
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
@click.option('--account', help='Filter by account (accepts ID, name, or key)')
@click.option('--limit', type=int, default=100, help='Maximum number of scorecards to check')
def find_duplicates(account: Optional[str], limit: int):
    """Find and manage duplicate scorecards across the system."""
    client = create_client()
    
    # Build filter string for GraphQL query
    filter_parts = []
    if account:
        account_id = resolve_account_identifier(client, account)
        if not account_id:
            click.echo(f"Account not found: {account}")
            return
        filter_parts.append(f'accountId: {{ eq: "{account_id}" }}')
    
    filter_str = ", ".join(filter_parts)
    
    # First, get all scorecards
    query = f"""
    query ListScorecards {{
        listScorecards(filter: {{ {filter_str} }}, limit: {limit}) {{
            items {{
                id
                name
                key
                accountId
                createdAt
                updatedAt
            }}
        }}
    }}
    """
    
    try:
        response = client.execute(query)
        scorecards = response.get('listScorecards', {}).get('items', [])
        
        if not scorecards:
            console.print("[yellow]No scorecards found.[/yellow]")
            return
        
        console.print(f"[green]Found {len(scorecards)} scorecards to check for duplicates.[/green]")
        
        # Group scorecards by key
        scorecards_by_key = {}
        for scorecard in scorecards:
            key = scorecard.get('key')
            if not key:
                continue
                
            if key not in scorecards_by_key:
                scorecards_by_key[key] = []
            scorecards_by_key[key].append(scorecard)
        
        # Find keys with multiple scorecards
        duplicate_keys = [key for key, cards in scorecards_by_key.items() if len(cards) > 1]
        
        if not duplicate_keys:
            console.print("[green]No duplicate scorecards found.[/green]")
            return
        
        console.print(f"[yellow]Found {len(duplicate_keys)} keys with duplicate scorecards:[/yellow]")
        
        # Create a table to display the duplicate keys
        keys_table = Table(title="Keys with Duplicate Scorecards")
        keys_table.add_column("#", style="dim")
        keys_table.add_column("Key", style="blue")
        keys_table.add_column("Count", style="magenta")
        
        for i, key in enumerate(duplicate_keys):
            keys_table.add_row(
                str(i + 1),
                key,
                str(len(scorecards_by_key[key]))
            )
        
        console.print(keys_table)
        
        # Prompt user to select a key to examine
        if click.confirm("Do you want to examine a specific key?"):
            max_key_choice = len(duplicate_keys)
            key_choice_str = click.prompt(
                f"Enter the number of the key to examine (1-{max_key_choice})",
                type=str
            )
            
            try:
                key_choice = int(key_choice_str)
                if key_choice < 1 or key_choice > max_key_choice:
                    console.print(f"[red]Invalid choice: {key_choice}. Must be between 1 and {max_key_choice}.[/red]")
                    return
            except ValueError:
                console.print(f"[red]Invalid input: {key_choice_str}. Please enter a number.[/red]")
                return
            
            selected_key = duplicate_keys[key_choice - 1]
            duplicate_scorecards = scorecards_by_key[selected_key]
            
            console.print(f"\n[bold]Examining scorecards with key: {selected_key}[/bold]")
            
            # Create a table to display the duplicates
            table = Table(title=f"Duplicate Scorecards with Key: {selected_key}")
            table.add_column("#", style="dim")
            table.add_column("ID", style="magenta")
            table.add_column("Name", style="blue")
            table.add_column("Account ID", style="cyan")
            table.add_column("Created At", style="dim")
            table.add_column("Updated At", style="dim")
            
            # Add index number for selection
            for i, dup in enumerate(duplicate_scorecards):
                table.add_row(
                    str(i + 1),
                    dup.get('id'),
                    dup.get('name'),
                    dup.get('accountId'),
                    dup.get('createdAt'),
                    dup.get('updatedAt')
                )
            
            console.print(table)
            
            # Prompt user to choose which scorecard to delete
            if click.confirm("Do you want to delete one of these duplicate scorecards?"):
                # Get user choice
                max_choice = len(duplicate_scorecards)
                choice_str = click.prompt(
                    f"Enter the number of the scorecard to delete (1-{max_choice})",
                    type=str
                )
                
                try:
                    choice = int(choice_str)
                    if choice < 1 or choice > max_choice:
                        console.print(f"[red]Invalid choice: {choice}. Must be between 1 and {max_choice}.[/red]")
                        return
                except ValueError:
                    console.print(f"[red]Invalid input: {choice_str}. Please enter a number.[/red]")
                    return
                
                # Get the selected scorecard
                selected_scorecard = duplicate_scorecards[choice - 1]
                selected_id = selected_scorecard.get('id')
                selected_name = selected_scorecard.get('name')
                
                # Confirm deletion
                console.print(f"[bold red]You are about to delete scorecard: {selected_name} (ID: {selected_id})[/bold red]")
                console.print("[red]This will permanently delete the scorecard and all its scores and versions.[/red]")
                
                if click.confirm("Are you sure you want to proceed?", default=False):
                    # Get all sections and scores for this scorecard
                    detailed_query = f"""
                    query GetScorecardDetails {{
                        getScorecard(id: "{selected_id}") {{
                            id
                            name
                            key
                            sections {{
                                items {{
                                    id
                                    name
                                    scores {{
                                        items {{
                                            id
                                            name
                                            versions {{
                                                items {{
                                                    id
                                                }}
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                    """
                    
                    try:
                        detailed_result = client.execute(detailed_query)
                        detailed_scorecard = detailed_result.get('getScorecard', {})
                        sections = detailed_scorecard.get('sections', {}).get('items', [])
                        
                        total_sections = len(sections)
                        total_scores = 0
                        total_versions = 0
                        
                        # First, delete all versions for each score
                        for section in sections:
                            section_id = section.get('id')
                            section_name = section.get('name')
                            scores = section.get('scores', {}).get('items', [])
                            
                            for score in scores:
                                score_id = score.get('id')
                                score_name = score.get('name')
                                versions = score.get('versions', {}).get('items', [])
                                
                                total_scores += 1
                                total_versions += len(versions)
                                
                                # Delete each version
                                for version in versions:
                                    version_id = version.get('id')
                                    delete_version_mutation = f"""
                                    mutation DeleteScoreVersion {{
                                        deleteScoreVersion(input: {{ id: "{version_id}" }}) {{
                                            id
                                        }}
                                    }}
                                    """
                                    client.execute(delete_version_mutation)
                                
                                # Delete the score
                                delete_score_mutation = f"""
                                mutation DeleteScore {{
                                    deleteScore(input: {{ id: "{score_id}" }}) {{
                                        id
                                    }}
                                }}
                                """
                                client.execute(delete_score_mutation)
                            
                            # Delete the section
                            delete_section_mutation = f"""
                            mutation DeleteScorecardSection {{
                                deleteScorecardSection(input: {{ id: "{section_id}" }}) {{
                                    id
                                }}
                            }}
                            """
                            client.execute(delete_section_mutation)
                        
                        # Finally delete the scorecard
                        delete_scorecard_mutation = f"""
                        mutation DeleteScorecard {{
                            deleteScorecard(input: {{ id: "{selected_id}" }}) {{
                                id
                            }}
                        }}
                        """
                        client.execute(delete_scorecard_mutation)
                        
                        console.print(f"[green]Successfully deleted scorecard: {selected_name} (ID: {selected_id})[/green]")
                        console.print(f"[green]Deleted {total_sections} sections, {total_scores} scores, and {total_versions} versions.[/green]")
                        
                    except Exception as e:
                        console.print(f"[red]Error deleting scorecard: {e}[/red]")
                    else:
                        console.print("[yellow]Deletion cancelled[/yellow]")
    
    except Exception as e:
        console.print(f"[red]Error finding duplicate scorecards: {e}[/red]")


@scorecards.command(name="promotion-packets")
@click.option('--scorecard', '-s', required=True, help='Scorecard identifier (name, key, or ID)')
@click.option('--scores', required=True, help='Comma-separated score identifiers')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', show_default=True)
def promotion_packets(scorecard: str, scores: str, output: str):
    """Build promotion packets for multiple scores in one scorecard."""
    from plexus.cli.score.scores import _resolve_optimizer_score_context
    from plexus.cli.shared.optimizer_results import OptimizerResultsService

    client = create_client()
    if not client:
        raise click.ClickException("Could not create API client")

    packets = []
    errors = []
    for score_identifier in [item.strip() for item in scores.split(",") if item.strip()]:
        try:
            context = _resolve_optimizer_score_context(client, scorecard, score_identifier)
            packet = context["service"].build_promotion_packet_for_score(
                context["score_id"],
                score_name=context["score_name"],
                scorecard_name=context["scorecard_name"],
                champion_version_id=context["champion_version_id"],
            )
            packets.append(packet)
        except Exception as exc:
            errors.append({"score": score_identifier, "error": str(exc)})

    payload = {
        "scorecard": scorecard,
        "packets": packets,
        "errors": errors,
        "markdown": OptimizerResultsService.render_promotion_packets_markdown(packets),
    }

    if output == 'json':
        click.echo(json.dumps(payload, indent=2, default=str))
        return
    if output == 'yaml':
        yaml_dumper = YAML()
        yaml_dumper.dump(payload, sys.stdout)
        return

    table = Table(title=f"Promotion Packets for {scorecard}")
    table.add_column("Score", style="cyan")
    table.add_column("Version", style="magenta")
    table.add_column("Champion", style="yellow")
    table.add_column("Feedback AC1", style="green")
    table.add_column("Accuracy AC1", style="green")
    table.add_column("Feedback Eval", style="blue")
    for packet in packets:
        table.add_row(
            packet.get("score_name") or "—",
            packet.get("version_id") or "—",
            "yes" if packet.get("is_champion") else "no",
            f"{packet['best_feedback_alignment']:.4f}" if packet.get("best_feedback_alignment") is not None else "—",
            f"{packet['best_accuracy_alignment']:.4f}" if packet.get("best_accuracy_alignment") is not None else "—",
            packet.get("best_feedback_evaluation_url") or "—",
        )
    console.print(table)
    if errors:
        error_table = Table(title="Scores Without Packets")
        error_table.add_column("Score", style="cyan")
        error_table.add_column("Error", style="red")
        for error in errors:
            error_table.add_row(error["score"], error["error"])
        console.print(error_table)


scorecard.add_command(promotion_packets)
