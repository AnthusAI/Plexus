import click
import os
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

def _process_single_scorecard_push(client, scorecard_identifier: str, account: str, skip_duplicate_check: bool, skip_external_id_check: bool, file_path: Optional[str] = None, yaml_data: Optional[dict] = None, note: Optional[str] = None, create_if_missing: bool = False) -> bool:
    """
    Process a single scorecard push operation.
    Returns True if successful, False if failed.
    """
    try:
        # The logic here will be the same as the original push command
        # but wrapped in a try-catch and returning a boolean
        # This is a simplified version that just calls the original push logic
        
        # If yaml_data is already provided, use it directly
        if yaml_data is not None:
            # We have the YAML data, now process it
            yaml_config = yaml_data
        else:
            # Load YAML from file or find matching file
            if file_path:
                if not os.path.exists(file_path):
                    console.print(f"[red]File not found: {file_path}[/red]")
                    return False
                
                try:
                    yaml_handler = get_yaml_handler()
                    with open(file_path, 'r') as f:
                        yaml_config = yaml_handler.load(f)
                    console.print(f"[green]Loaded configuration from {file_path}[/green]")
                except Exception as e:
                    console.print(f"[red]Error loading YAML from {file_path}: {e}[/red]")
                    return False
            else:
                # Search for matching YAML file in scorecards/ directory
                if not os.path.exists('scorecards'):
                    console.print("[red]scorecards/ directory not found[/red]")
                    return False
                
                yaml_files = [f for f in os.listdir('scorecards') if f.endswith('.yaml')]
                if not yaml_files:
                    console.print("[red]No YAML files found in scorecards/ directory[/red]")
                    return False
                
                # Try to find a matching YAML file
                matching_file = None
                yaml_config = None
                
                for yaml_file in yaml_files:
                    try:
                        file_path = os.path.join('scorecards', yaml_file)
                        with open(file_path, 'r') as f:
                            yaml_handler = get_yaml_handler()
                            data = yaml_handler.load(f)
                            
                            # Check if this file matches our scorecard identifier
                            filename_without_ext = os.path.splitext(yaml_file)[0].lower()
                            if (filename_without_ext == scorecard_identifier.lower() or
                                data.get('key') == scorecard_identifier or
                                data.get('name') == scorecard_identifier):
                                matching_file = file_path
                                yaml_config = data
                                break
                    except Exception:
                        continue
                
                if not matching_file:
                    console.print(f"[red]Could not find matching YAML file for scorecard: {scorecard_identifier}[/red]")
                    return False
                
                console.print(f"[green]Found and loaded configuration from {matching_file}[/green]")
        
        # Now we have yaml_config, proceed with the push logic
        # Try to resolve the scorecard identifier to an ID
        scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
        
        # If scorecard doesn't exist and create_if_missing is True, create it
        if not scorecard_id and create_if_missing:
            # First, resolve the account identifier to an ID
            account_id = resolve_account_identifier(client, account)
            if not account_id:
                console.print(f"[red]Could not find account: {account}[/red]")
                return False
            
            # Extract required fields from YAML
            scorecard_name = yaml_config.get('name')
            scorecard_key = yaml_config.get('key')
            scorecard_external_id = str(yaml_config.get('id', ''))
            scorecard_description = yaml_config.get('description', '')
            
            if not scorecard_name or not scorecard_key:
                console.print("[red]YAML file must contain 'name' and 'key' fields to create a new scorecard[/red]")
                return False
            
            # Create the scorecard
            try:
                create_mutation = f"""
                mutation CreateScorecard {{
                    createScorecard(input: {{
                        name: "{scorecard_name}"
                        key: "{scorecard_key}"
                        externalId: "{scorecard_external_id}"
                        accountId: "{account_id}"
                        description: "{scorecard_description}"
                    }}) {{
                        id
                        name
                        key
                        externalId
                    }}
                }}
                """
                result = client.execute(create_mutation)
                new_scorecard = result.get('createScorecard', {})
                scorecard_id = new_scorecard.get('id')
                
                if not scorecard_id:
                    console.print("[red]Failed to create new scorecard[/red]")
                    return False
                
                console.print(f"[green]Created new scorecard: {scorecard_name} (ID: {scorecard_id}, Key: {scorecard_key})[/green]")
            except Exception as e:
                console.print(f"[red]Error creating scorecard: {e}[/red]")
                return False
        elif not scorecard_id:
            console.print(f"[red]Could not find scorecard: {scorecard_identifier}[/red]")
            console.print("[yellow]Use --create-if-missing flag to create a new scorecard if it doesn't exist[/yellow]")
            return False
        
        # Get scorecard details for display
        query = f"""
        query GetScorecard {{
            getScorecard(id: "{scorecard_id}") {{
                id
                name
                key
                externalId
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
        """
        
        result = client.execute(query)
        scorecard_data = result.get('getScorecard', {})
        scorecard_name = scorecard_data.get('name', 'Unknown')
        scorecard_key = scorecard_data.get('key', 'Unknown')
        scorecard_external_id = scorecard_data.get('externalId', 'None')
        
        console.print(f"[green]Found scorecard: {scorecard_name} (ID: {scorecard_id}, Key: {scorecard_key}, External ID: {scorecard_external_id})[/green]")
        
        # Update scorecard metadata if necessary
        if yaml_config.get('name') != scorecard_name or yaml_config.get('key') != scorecard_key or yaml_config.get('externalId') != scorecard_external_id:
            update_mutation = f"""
            mutation UpdateScorecard {{
                updateScorecard(input: {{
                    id: "{scorecard_id}"
                    name: "{yaml_config.get('name', scorecard_name)}"
                    key: "{yaml_config.get('key', scorecard_key)}"
                    externalId: "{yaml_config.get('externalId', scorecard_external_id)}"
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
        
        # Process scores if they exist in the YAML
        if 'scores' in yaml_config and yaml_config['scores']:
            console.print(f"[green]Found {len(yaml_config['scores'])} scores in YAML configuration[/green]")
            
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
                                    isDisabled
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
            # Also create a map of externalId to score across all sections
            external_id_map = {}
            
            for section in sections:
                section_name = section.get('name')
                if section_name not in score_map:
                    score_map[section_name] = {}
                
                scores = section.get('scores', {}).get('items', [])
                for score in scores:
                    score_name = score.get('name')
                    score_external_id = score.get('externalId')
                    score_map[section_name][score_name] = score
                    
                    # Map external ID to score (if external ID exists)
                    if score_external_id and score_external_id.strip():
                        external_id_map[score_external_id] = score
            
            # Process each score in the YAML
            scores_processed = 0
            scores_updated = 0
            scores_created = 0
            
            for score_data in yaml_config['scores']:
                score_name = score_data.get('name')
                section_name = score_data.get('section', 'Default')
                
                if not score_name:
                    console.print("[yellow]Skipping score with missing name[/yellow]")
                    continue
                
                # Remove section from score_data as it's not part of the score configuration
                score_config_data = score_data.copy()
                if 'section' in score_config_data:
                    del score_config_data['section']
                
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
                
                # Check if score exists - prioritize externalId match over name match
                yaml_external_id = str(score_data.get('id', ''))
                existing_score = None
                score_id = None
                
                # First, check if a score with this externalId already exists anywhere
                if yaml_external_id and yaml_external_id.strip() and yaml_external_id in external_id_map:
                    existing_score = external_id_map[yaml_external_id]
                    score_id = existing_score.get('id')
                    console.print(f"[yellow]Found existing score by externalId '{yaml_external_id}': {existing_score.get('name')}[/yellow]")
                # If no externalId match, check by name in the specified section
                elif section_name in score_map and score_name in score_map[section_name]:
                    existing_score = score_map[section_name][score_name]
                    score_id = existing_score.get('id')
                    console.print(f"[dim]Found existing score by name in section '{section_name}': {score_name}[/dim]")
                
                if existing_score:
                    # Update existing score
                    
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
                            yaml_handler = get_yaml_handler()
                            parent_config_stream = io.StringIO(parent_config)
                            parent_config_obj = yaml_handler.load(parent_config_stream)
                        except:
                            # If parsing fails, try JSON as fallback
                            try:
                                parent_config_obj = json.loads(parent_config)
                            except:
                                parent_config_obj = {}
                        
                        # Create a copy of score_data without parent field for comparison
                        score_data_for_comparison = score_config_data.copy()
                        if 'parent' in score_data_for_comparison:
                            del score_data_for_comparison['parent']
                        
                        # Remove parent from parent_config_obj if it exists
                        if isinstance(parent_config_obj, dict) and 'parent' in parent_config_obj:
                            del parent_config_obj['parent']
                        
                        # Compare the configurations
                        yaml_handler = get_yaml_handler()
                        
                        yaml_str1 = io.StringIO()
                        yaml_handler.dump(score_data_for_comparison, yaml_str1)
                        yaml_str1 = yaml_str1.getvalue()
                        
                        yaml_str2 = io.StringIO()
                        yaml_handler.dump(parent_config_obj, yaml_str2)
                        yaml_str2 = yaml_str2.getvalue()
                        
                        if yaml_str1 == yaml_str2:
                            create_new_version = False
                            console.print(f"[dim]No changes detected for score: {score_name}[/dim]")
                        else:
                            console.print(f"[yellow]Changes detected for score: {score_name}[/yellow]")
                    
                    # Check if external ID needs to be updated regardless of configuration changes
                    yaml_id = str(score_data.get('id', ''))
                    current_external_id = existing_score.get('externalId', '')
                    
                    if yaml_id and yaml_id != current_external_id:
                        console.print(f"[yellow]External ID mismatch for score: {score_name} - updating to {yaml_id}[/yellow]")
                        
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
                        client.execute(update_external_id_mutation)
                    
                    # Check if the score name needs to be updated (handle renames)
                    current_score_name = existing_score.get('name', '')
                    if score_name != current_score_name:
                        console.print(f"[yellow]Score name change detected: '{current_score_name}' -> '{score_name}'[/yellow]")
                        
                        # Update the score name
                        update_name_mutation = f"""
                        mutation UpdateScoreName {{
                            updateScore(input: {{
                                id: "{score_id}"
                                name: "{score_name}"
                            }}) {{
                                id
                                name
                            }}
                        }}
                        """
                        client.execute(update_name_mutation)
                    
                    # Check if the disabled status needs to be updated
                    yaml_disabled = score_data.get('disabled', False)
                    current_disabled = existing_score.get('isDisabled', False)
                    
                    if yaml_disabled != current_disabled:
                        console.print(f"[yellow]Disabled status change detected for score: {score_name} - updating to {yaml_disabled}[/yellow]")
                        
                        # Update the disabled status
                        disabled_str = "true" if yaml_disabled else "false"
                        update_disabled_mutation = f"""
                        mutation UpdateScoreDisabled {{
                            updateScore(input: {{
                                id: "{score_id}"
                                isDisabled: {disabled_str}
                            }}) {{
                                id
                                name
                                isDisabled
                            }}
                        }}
                        """
                        client.execute(update_disabled_mutation)
                    
                    if create_new_version:
                        # Add parent ID to score_data for the new version
                        if parent_version_id:
                            score_config_data['parent'] = parent_version_id
                        
                        # Convert score_data to YAML string for configuration
                        yaml_handler = get_yaml_handler()
                        yaml_str = io.StringIO()
                        yaml_handler.dump(score_config_data, yaml_str)
                        yaml_config_str = yaml_str.getvalue()
                        
                        # Get version note
                        version_note = note or ""
                        
                        # Define timestamp for version creation
                        now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                        
                        # Define parent version field if parent_version_id exists
                        parent_version_field = f'parentVersionId: "{parent_version_id}",' if parent_version_id else ""
                        
                        # Include note in mutation if provided
                        note_field = f'note: {json.dumps(version_note)},' if version_note else ""
                        
                        create_version_mutation = f"""
                        mutation CreateScoreVersion {{
                            createScoreVersion(input: {{
                                scoreId: "{score_id}"
                                configuration: {json.dumps(yaml_config_str)}
                                # Never auto-promote when creating versions from scorecard push
                                isFeatured: false
                                createdAt: "{now}"
                                updatedAt: "{now}"
                                {parent_version_field}
                                {note_field}
                            }}) {{
                                id
                                scoreId
                                configuration
                                isFeatured
                                createdAt
                                updatedAt
                                parentVersionId
                                note
                            }}
                        }}
                        """
                        
                        version_result = client.execute(create_version_mutation)
                        new_version_id = version_result.get('createScoreVersion', {}).get('id')
                        
                        # Update Score to point to new champion version
                        external_id = str(score_data.get('id', ''))
                        
                        # Ensure key is not an empty string to avoid DynamoDB errors
                        score_key = score_data.get('key', '')
                        if not score_key or score_key.strip() == '':
                            score_key = generate_key(score_name)
                        
                        # Ensure aiProvider and aiModel are not empty strings
                        ai_provider = score_data.get('model_provider', '')
                        if not ai_provider or ai_provider.strip() == '':
                            ai_provider = "unknown"
                            
                        ai_model = score_data.get('model_name', '')
                        if not ai_model or ai_model.strip() == '':
                            ai_model = "unknown"
                        
                        # Handle disabled field
                        is_disabled = score_data.get('disabled', False)
                        is_disabled_str = "true" if is_disabled else "false"
                        
                        update_score_mutation = f"""
                        mutation UpdateScore {{
                            updateScore(input: {{
                                id: "{score_id}"
                                championVersionId: "{new_version_id}"
                                name: "{score_name}"
                                key: "{score_key}"
                                externalId: "{external_id}"
                                aiProvider: "{ai_provider}"
                                aiModel: "{ai_model}"
                                isDisabled: {is_disabled_str}
                            }}) {{
                                id
                                name
                                championVersionId
                                externalId
                                isDisabled
                            }}
                        }}
                        """
                        client.execute(update_score_mutation)
                        console.print(f"[green]Created new version for score: {score_name}[/green]")
                        scores_updated += 1
                    
                    scores_processed += 1
                    
                else:
                    # Create new score
                    score_key = score_data.get('key', '')
                    if not score_key or not score_key.strip():
                        score_key = generate_key(score_name)
                    
                    external_id = str(score_data.get('id', ''))
                    
                    # Ensure aiProvider and aiModel are not empty strings
                    ai_provider = score_data.get('model_provider', '')
                    if not ai_provider or ai_provider.strip() == '':
                        ai_provider = "unknown"
                        
                    ai_model = score_data.get('model_name', '')
                    if not ai_model or ai_model.strip() == '':
                        ai_model = "unknown"
                    
                    # Handle disabled field
                    is_disabled = score_data.get('disabled', False)
                    is_disabled_str = "true" if is_disabled else "false"
                    
                    create_score_mutation = f"""
                    mutation CreateScore {{
                        createScore(input: {{
                            name: "{score_name}"
                            key: "{score_key}"
                            externalId: "{external_id}"
                            order: 0
                            type: "STANDARD"
                            aiProvider: "{ai_provider}"
                            aiModel: "{ai_model}"
                            sectionId: "{section_id}"
                            scorecardId: "{scorecard_id}"
                            isDisabled: {is_disabled_str}
                        }}) {{
                            id
                            name
                            externalId
                            isDisabled
                        }}
                    }}
                    """
                    score_result = client.execute(create_score_mutation)
                    new_score_id = score_result.get('createScore', {}).get('id')
                    
                    # Create initial ScoreVersion for the new score
                    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                    
                    # Convert score_data to YAML string for configuration
                    yaml_handler = get_yaml_handler()
                    yaml_str = io.StringIO()
                    yaml_handler.dump(score_config_data, yaml_str)
                    yaml_config_str = yaml_str.getvalue()
                    
                    # Get version note
                    version_note = note or ""
                    
                    # Include note in mutation if provided
                    note_field = f'note: {json.dumps(version_note)},' if version_note else ""
                    
                    create_version_mutation = f"""
                    mutation CreateScoreVersion {{
                        createScoreVersion(input: {{
                            scoreId: "{new_score_id}"
                            configuration: {json.dumps(yaml_config_str)}
                            # Never auto-promote when creating initial score version
                            isFeatured: false
                            createdAt: "{now}"
                            updatedAt: "{now}"
                            {note_field}
                        }}) {{
                            id
                            scoreId
                            configuration
                            isFeatured
                            createdAt
                            updatedAt
                            note
                        }}
                    }}
                    """
                    
                    version_result = client.execute(create_version_mutation)
                    new_version_id = version_result.get('createScoreVersion', {}).get('id')
                    
                    # Update Score to point to new champion version
                    update_score_mutation = f"""
                    mutation UpdateScore {{
                        updateScore(input: {{
                            id: "{new_score_id}"
                            championVersionId: "{new_version_id}"
                            name: "{score_name}"
                            key: "{score_key}"
                            externalId: "{external_id}"
                            aiProvider: "{ai_provider}"
                            aiModel: "{ai_model}"
                            isDisabled: {is_disabled_str}
                        }}) {{
                            id
                            name
                            championVersionId
                            externalId
                            isDisabled
                        }}
                    }}
                    """
                    client.execute(update_score_mutation)
                    console.print(f"[green]Created new score with initial version: {score_name}[/green]")
                    scores_created += 1
                    scores_processed += 1
            
            if scores_processed > 0:
                console.print(f"[green]Processed {scores_processed} scores ({scores_created} created, {scores_updated} updated)[/green]")
        else:
            console.print("[dim]No scores found in YAML configuration[/dim]")
        
        # Check for duplicates if requested
        if not skip_duplicate_check:
            detect_and_clean_duplicates(client, scorecard_id)
        
        # Check for missing external IDs if requested
        if not skip_external_id_check:
            ensure_valid_external_ids(client, scorecard_id)
        
        return True
        
    except Exception as e:
        console.print(f"[red]Error processing scorecard {scorecard_identifier}: {e}[/red]")
        return False

@scorecards.command()
@click.option('--scorecard', help='Scorecard to push (accepts ID, name, key, or external ID)')
@click.option('--all', is_flag=True, help='Push all scorecards found in the scorecards directory')
@click.option('--account', default=lambda: os.getenv('PLEXUS_ACCOUNT_KEY'), help='Account to push scorecard to (accepts ID, name, or key)')
@click.option('--skip-duplicate-check', is_flag=True, help='Skip checking for and removing duplicate scores')
@click.option('--skip-external-id-check', is_flag=True, help='Skip checking for and fixing missing external IDs')
@click.option('--file', help='Path to specific YAML file to push (if not provided, will search in scorecards/ directory)')
@click.option('--note', help='Note to include when creating a new score version')
@click.option('--create-if-missing', is_flag=True, help='Create the scorecard if it does not exist')
def push(scorecard: Optional[str], all: bool, account: str, skip_duplicate_check: bool, skip_external_id_check: bool, file: Optional[str] = None, note: Optional[str] = None, create_if_missing: bool = False):
    """Push a scorecard to the dashboard."""
    client = create_client()
    
    # Validate input - either --all or --scorecard must be provided
    if all and scorecard:
        console.print("[red]Cannot specify both --all and --scorecard options[/red]")
        return
    
    if not all and not scorecard:
        console.print("[red]Must specify either --all or --scorecard option[/red]")
        return
    
    # If --all flag is used, push all scorecards in the directory
    if all:
        if not os.path.exists('scorecards'):
            console.print("[red]scorecards/ directory not found[/red]")
            return
        
        yaml_files = [f for f in os.listdir('scorecards') if f.endswith('.yaml')]
        if not yaml_files:
            console.print("[red]No YAML files found in scorecards/ directory[/red]")
            return
        
        console.print(f"[green]Found {len(yaml_files)} YAML files to push[/green]")
        
        # Process each YAML file
        for yaml_file in yaml_files:
            yaml_file_path = os.path.join('scorecards', yaml_file)
            scorecard_name_from_file = os.path.splitext(yaml_file)[0]
            
            console.print(f"\n[bold]Processing {yaml_file}...[/bold]")
            
            try:
                # Load YAML data
                yaml_handler = get_yaml_handler()
                with open(yaml_file_path, 'r') as f:
                    yaml_data = yaml_handler.load(f)
                
                # Use the scorecard key or name from the YAML, or fallback to filename
                scorecard_identifier = yaml_data.get('key') or yaml_data.get('name') or scorecard_name_from_file
                
                # Process this individual scorecard using the same logic as the single scorecard push
                # Set the scorecard variable to the identifier for this file
                scorecard = scorecard_identifier
                file = yaml_file_path
                
                # Execute the single scorecard push logic
                success = _process_single_scorecard_push(
                    client, scorecard, account, skip_duplicate_check, 
                    skip_external_id_check, file, yaml_data, note, create_if_missing
                )
                
                if success:
                    console.print(f"[green]✓ Successfully pushed {yaml_file}[/green]")
                else:
                    console.print(f"[red]✗ Failed to push {yaml_file}[/red]")
                
            except Exception as e:
                console.print(f"[red]Error processing {yaml_file}: {e}[/red]")
                continue
        
        console.print("\n[green]Finished pushing all scorecards[/green]")
        return
    
    # Handle single scorecard push
    success = _process_single_scorecard_push(
        client, scorecard, account, skip_duplicate_check, 
        skip_external_id_check, file, None, note, create_if_missing
    )
    
    if success:
        console.print("\n[green]Push operation completed successfully[/green]")
    else:
        console.print("\n[red]Push operation failed[/red]") 

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