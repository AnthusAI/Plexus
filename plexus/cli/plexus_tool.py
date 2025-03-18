"""
Implementation of the Plexus tool for Claude to interact with scores and scorecards.

This module implements the Plexus tool protocol for Claude to:
1. List available scorecards
2. List scores within a scorecard
3. Pull score versions as YAML
4. Push score version updates from YAML
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml
from rich.console import Console
import click
from ruamel.yaml import YAML

from plexus.cli.identifier_resolution import resolve_scorecard_identifier, resolve_score_identifier
from plexus.cli.console import console
from plexus.cli.CommandLineInterface import create_client
from plexus.cli.shared import get_score_yaml_path
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.cli.memoized_resolvers import (
    memoized_resolve_scorecard_identifier,
    memoized_resolve_score_identifier,
    clear_resolver_caches
)

console = Console()

class PlexusTool:
    """Tool for Claude to interact with Plexus scores and scorecards."""
    
    def __init__(self):
        """Initialize the Plexus tool with an API client."""
        self.client = create_client()
    
    def list_scorecards(self) -> List[Dict[str, Any]]:
        """List all available scorecards.
        
        Returns:
            List of scorecard dictionaries containing:
                - id: Scorecard ID
                - name: Scorecard name
                - key: Scorecard key
                - externalId: External ID
        """
        try:
            query = """
            query ListScorecards {
                listScorecards(limit: 100) {
                    items {
                        id
                        name
                        key
                        externalId
                    }
                }
            }
            """
            result = self.client.execute(query)
            return result.get('listScorecards', {}).get('items', [])
        except Exception as e:
            console.print(f"[red]Error listing scorecards: {e}[/red]")
            return []
    
    def list_scores_by_scorecard(self, scorecard: str) -> List[Dict]:
        """List all scores within a specific scorecard.
        
        Args:
            scorecard: Scorecard identifier (ID, name, key, or external ID)
            
        Returns:
            List of score dictionaries containing:
                - id: Score ID
                - name: Score name
                - key: Score key
                - type: Score type
                - order: Score order
                - externalId: External ID
                - section: Section name and order
        """
        try:
            # Resolve the scorecard ID
            scorecard_id = resolve_scorecard_identifier(self.client, scorecard)
            if not scorecard_id:
                console.print(f"[red]Scorecard not found: {scorecard}[/red]")
                return []
            
            # Get all sections and their scores
            query = f"""
            query GetScorecard {{
                getScorecard(id: "{scorecard_id}") {{
                    id
                    name
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
            result = self.client.execute(query)
            scorecard_data = result.get('getScorecard')
            if not scorecard_data:
                console.print(f"[red]Scorecard not found: {scorecard}[/red]")
                return []
            
            # Flatten scores from all sections
            all_scores = []
            for section in scorecard_data.get('sections', {}).get('items', []):
                for score in section.get('scores', {}).get('items', []):
                    score['section'] = {
                        'name': section['name'],
                        'order': section['order']
                    }
                    all_scores.append(score)
            
            # Sort scores by section order, then score order
            sorted_scores = sorted(
                all_scores,
                key=lambda s: (
                    s['section']['order'] if s.get('section') else 999,
                    s.get('order', 999)
                )
            )
            
            return sorted_scores
            
        except Exception as e:
            console.print(f"[red]Error listing scores: {str(e)}[/red]")
            return []
    
    def pull_score(self, scorecard: str, score: str) -> Optional[str]:
        """Pull a score's current champion version as YAML."""
        try:
            # Resolve identifiers
            scorecard_id = memoized_resolve_scorecard_identifier(self.client, scorecard)
            if not scorecard_id:
                console.print(f"[red]Scorecard not found: {scorecard}[/red]")
                return None
            
            score_id = memoized_resolve_score_identifier(self.client, scorecard_id, score)
            if not score_id:
                console.print(f"[red]Score not found: {score}[/red]")
                return None
            
            # Get scorecard details for display
            query = f"""
            query GetScorecardDetails {{
                getScorecard(id: "{scorecard_id}") {{
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
                                    key
                                    championVersionId
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            """
            
            result = self.client.execute(query)
            scorecard_data = result.get('getScorecard', {})
            scorecard_name = scorecard_data.get('name', 'Unknown')
            scorecard_key = scorecard_data.get('key', 'Unknown')
            
            # Find the score in the scorecard
            found_score = None
            for section in scorecard_data.get('sections', {}).get('items', []):
                for score_item in section.get('scores', {}).get('items', []):
                    if (score_item['id'] == score or 
                        score_item['key'] == score or 
                        score_item['name'] == score):
                        found_score = score_item
                        break
                if found_score:
                    break
            
            if not found_score:
                console.print(f"[red]Could not find score: {score}[/red]")
                return None
            
            score_name = found_score['name']
            score_key = found_score['key']
            champion_version_id = found_score.get('championVersionId')
            
            if not champion_version_id:
                console.print(f"[red]No champion version found for score: {score_name}[/red]")
                return None
            
            # Get the score version content
            version_query = f"""
            query GetScoreVersion {{
                getScoreVersion(id: "{champion_version_id}") {{
                    id
                    configuration
                    createdAt
                    updatedAt
                    note
                }}
            }}
            """
            
            version_result = self.client.execute(version_query)
            version_data = version_result.get('getScoreVersion')
            
            if not version_data or not version_data.get('configuration'):
                console.print(f"[red]No configuration found for version: {champion_version_id}[/red]")
                return None
            
            # Get the YAML file path using the utility function
            yaml_path = get_score_yaml_path(scorecard_name, score_name)
            
            # Parse the content as YAML using ruamel.yaml
            try:
                content = version_data.get('configuration')
                
                # Initialize ruamel.yaml
                yaml = YAML()
                yaml.preserve_quotes = True
                yaml.width = 4096  # Prevent line wrapping
                
                # Configure YAML formatting
                yaml.indent(mapping=2, sequence=4, offset=2)
                yaml.map_indent = 2
                yaml.sequence_indent = 4
                yaml.sequence_dash_offset = 2
                
                # Configure literal block style for system_message and user_message
                def literal_presenter(dumper, data):
                    if isinstance(data, str) and "\n" in data:
                        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
                    return dumper.represent_scalar('tag:yaml.org,2002:str', data)
                
                yaml.representer.add_representer(str, literal_presenter)
                
                # Parse the YAML content
                yaml_data = yaml.load(content)
                
                # Write to file
                with open(yaml_path, 'w') as f:
                    yaml.dump(yaml_data, f)
                
                return f"Pulled score configuration to: {yaml_path}"
                
            except Exception as e:
                console.print(f"[red]Error parsing YAML content: {str(e)}[/red]")
                import traceback
                console.print(f"[red]{traceback.format_exc()}[/red]")
                return None
            
        except Exception as e:
            console.print(f"[red]Error during pull operation: {str(e)}[/red]")
            import traceback
            console.print(f"[red]{traceback.format_exc()}[/red]")
            return None
    
    def push_score(self, scorecard: str, score: str, yaml_path: str) -> Optional[str]:
        """Push a score version from YAML."""
        try:
            # Resolve identifiers
            scorecard_id = memoized_resolve_scorecard_identifier(self.client, scorecard)
            if not scorecard_id:
                console.print(f"[red]Scorecard not found: {scorecard}[/red]")
                return None
            
            score_id = memoized_resolve_score_identifier(self.client, scorecard_id, score)
            if not score_id:
                console.print(f"[red]Score not found: {score}[/red]")
                return None
            
            # Get the score name and champion version ID
            query = f"""
            query GetScore {{
                getScore(id: "{score_id}") {{
                    name
                    championVersionId
                }}
            }}
            """
            result = self.client.execute(query)
            score_data = result.get('getScore')
            if not score_data:
                return f"Error retrieving score: {score}"
            score_name = score_data['name']
            champion_version_id = score_data.get('championVersionId')
            
            # Check if the YAML file exists
            yaml_path = Path(yaml_path)
            if not yaml_path.exists():
                return f"YAML file not found at: {yaml_path}"
            
            try:
                # Read the YAML file
                with open(yaml_path, 'r') as f:
                    yaml_content = f.read()
                
                # Create a new version
                mutation = f"""
                mutation CreateScoreVersion($input: CreateScoreVersionInput!) {{
                    createScoreVersion(input: $input) {{
                        id
                        configuration
                        createdAt
                        updatedAt
                        note
                    }}
                }}
                """
                
                version_input = {
                    'scoreId': score_id,
                    'configuration': yaml_content,
                    'note': ''
                }
                
                result = self.client.execute(mutation, {'input': version_input})
                new_version = result.get('createScoreVersion')
                
                if not new_version:
                    return "Failed to create new version"
                
                # Update the score's champion version
                update_mutation = f"""
                mutation UpdateScore($input: UpdateScoreInput!) {{
                    updateScore(input: $input) {{
                        id
                        championVersionId
                    }}
                }}
                """
                
                update_input = {
                    'id': score_id,
                    'championVersionId': new_version['id']
                }
                
                update_result = self.client.execute(update_mutation, {'input': update_input})
                if not update_result.get('updateScore'):
                    return "Failed to update champion version"
                
                return f"Successfully updated score {score_name} with new version {new_version['id']}"
                
            except Exception as e:
                return f"Error pushing score: {str(e)}"
        except Exception as e:
            return f"Error pushing score: {str(e)}" 