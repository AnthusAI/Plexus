"""
Score Service - Shared service for score management operations.

This service provides reusable functionality for:
- Finding scores by various criteria
- Searching scores by name patterns  
- Deleting scores with safety checks
- Retrieving score details and configurations
"""

import logging
import os
from typing import Optional, Dict, Any, List, Union, Tuple
from io import StringIO
import sys

logger = logging.getLogger(__name__)


class ScoreService:
    """Shared service for score management operations."""
    
    def __init__(self, client=None):
        """
        Initialize the ScoreService.
        
        Args:
            client: Optional PlexusDashboardClient instance. If not provided, will create one.
        """
        self.client = client
        if not self.client:
            self.client = self._create_client()
    
    def _create_client(self):
        """Create a PlexusDashboardClient instance."""
        try:
            from plexus.cli.shared.client_utils import create_client as create_dashboard_client
            return create_dashboard_client()
        except ImportError as e:
            logger.error(f"Failed to import Plexus client modules: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to create Plexus client: {e}")
            return None
    
    def validate_credentials(self) -> Tuple[bool, str]:
        """
        Validate that required API credentials are available.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        api_url = os.environ.get('PLEXUS_API_URL', '')
        api_key = os.environ.get('PLEXUS_API_KEY', '')
        
        if not api_url:
            return False, "PLEXUS_API_URL environment variable not set"
        
        if not api_key:
            return False, "PLEXUS_API_KEY environment variable not set"
        
        if not self.client:
            return False, "Could not create Plexus client"
        
        return True, ""
    
    def resolve_scorecard_identifier(self, identifier: str) -> Optional[str]:
        """
        Resolve a scorecard identifier to its ID.
        
        Args:
            identifier: Scorecard identifier (ID, name, key, or external ID)
            
        Returns:
            Scorecard ID string or None if not found
        """
        try:
            from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier
            return resolve_scorecard_identifier(self.client, identifier)
        except ImportError as e:
            logger.error(f"Failed to import scorecard resolution functions: {e}")
            return self._resolve_scorecard_fallback(identifier)
    
    def _resolve_scorecard_fallback(self, identifier: str) -> Optional[str]:
        """Fallback method to resolve scorecard using direct GraphQL."""
        try:
            # Try direct ID lookup first
            query = f"""
            query GetScorecard {{
                getScorecard(id: "{identifier}") {{
                    id
                }}
            }}
            """
            result = self.client.execute(query)
            if result.get('getScorecard'):
                return identifier
        except:
            pass
        
        try:
            # Try lookup by key, name, or external ID
            query = f"""
            query ListScorecards {{
                listScorecards(filter: {{
                    or: [
                        {{ key: {{ eq: "{identifier}" }} }},
                        {{ name: {{ eq: "{identifier}" }} }},
                        {{ externalId: {{ eq: "{identifier}" }} }}
                    ]
                }}, limit: 1) {{
                    items {{
                        id
                    }}
                }}
            }}
            """
            result = self.client.execute(query)
            items = result.get('listScorecards', {}).get('items', [])
            return items[0]['id'] if items else None
        except Exception as e:
            logger.error(f"Failed to resolve scorecard {identifier}: {e}")
            return None
    
    def find_scores_by_pattern(self, pattern: str, scorecard_identifier: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find scores that match a name pattern (case-insensitive substring match).
        
        Args:
            pattern: Pattern to search for in score names
            scorecard_identifier: Optional scorecard identifier to limit search scope
            
        Returns:
            List of matching scores with their details
        """
        found_scores = []
        
        if scorecard_identifier:
            scorecard_id = self.resolve_scorecard_identifier(scorecard_identifier)
            if not scorecard_id:
                logger.error(f"Scorecard not found: {scorecard_identifier}")
                return []
            
            # Get scorecard details with sections and scores
            query = f"""
            query GetScorecardForSearch {{
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
                                    externalId
                                    type
                                    order
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            """
            
            success, result = self._execute_with_error_handling(query)
            if not success:
                logger.error(f"Failed to get scorecard data: {result}")
                return []
            
            scorecard = result.get('getScorecard')
            if not scorecard:
                logger.error(f"Could not retrieve scorecard data for ID: {scorecard_id}")
                return []
            
            # Search through scores in this scorecard
            sections = scorecard.get('sections', {}).get('items', [])
            for section in sections:
                section_name = section.get('name', 'Unknown Section')
                scores = section.get('scores', {}).get('items', [])
                
                for score in scores:
                    score_name = score.get('name', '')
                    if pattern.lower() in score_name.lower():
                        found_scores.append({
                            'id': score.get('id'),
                            'name': score_name,
                            'key': score.get('key'),
                            'externalId': score.get('externalId'),
                            'type': score.get('type'),
                            'order': score.get('order'),
                            'section': {
                                'id': section.get('id'),
                                'name': section_name
                            },
                            'scorecard': {
                                'id': scorecard.get('id'),
                                'name': scorecard.get('name'),
                                'key': scorecard.get('key')
                            }
                        })
        else:
            # Search across all scorecards would be implemented here if needed
            logger.warning("Searching across all scorecards not implemented for performance reasons")
        
        return found_scores
    
    def delete_score(self, score_id: str, confirm: bool = False) -> str:
        """
        Delete a specific score by its ID.
        
        Args:
            score_id: The ID of the score to delete
            confirm: Whether to skip confirmation (default: False for safety)
            
        Returns:
            Success/error message
        """
        # Safety check
        if not confirm:
            return f"Error: Deletion requires confirmation. Set confirm=True to proceed with deleting score ID: {score_id}"
        
        # Validate credentials
        is_valid, error_msg = self.validate_credentials()
        if not is_valid:
            return f"Error: {error_msg}"
        
        # Build and execute the delete mutation
        mutation = f"""
        mutation DeleteScore {{
            deleteScore(input: {{ id: "{score_id}" }}) {{
                id
            }}
        }}
        """
        
        logger.info(f"Executing deleteScore mutation for ID: {score_id}")
        success, result = self._execute_with_error_handling(mutation)
        
        if not success:
            return f"Error from deleteScore mutation: {result}"

        deleted_score = result.get('deleteScore')
        if not deleted_score:
            return f"Error: Failed to delete score with ID '{score_id}'. No response from server."
            
        return f"Successfully deleted score with ID: {score_id}"
    
    def get_score_details(self, score_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific score.
        
        Args:
            score_id: The ID of the score
            
        Returns:
            Score details dictionary or None if not found
        """
        query = f"""
        query GetScore {{
            getScore(id: "{score_id}") {{
                id
                name
                key
                externalId
                description
                type
                order
                championVersionId
                sectionId
                scorecardId
            }}
        }}
        """
        
        success, result = self._execute_with_error_handling(query)
        if not success:
            logger.error(f"Failed to get score details: {result}")
            return None
        
        return result.get('getScore')
    
    def _execute_with_error_handling(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any]:
        """
        Execute a GraphQL query with proper error handling.
        
        Args:
            query: GraphQL query string
            variables: Optional query variables
            
        Returns:
            Tuple of (success, result_or_error_message)
        """
        try:
            result = self.client.execute(query, variables)
            
            if result.get('errors'):
                import json
                error_details = json.dumps(result['errors'], indent=2)
                logger.error(f"GraphQL query returned errors: {error_details}")
                return False, f"GraphQL errors: {error_details}"
            
            return True, result
        except Exception as e:
            logger.error(f"Exception during GraphQL execution: {e}")
            return False, f"Execution error: {str(e)}" 