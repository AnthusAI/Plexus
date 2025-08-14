#!/usr/bin/env python3
"""
Score management tools for Plexus MCP server
"""
import os
import sys
import json
import yaml
from io import StringIO
from typing import Union, List, Dict, Optional, Any
from fastmcp import FastMCP
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.setup import logger
from shared.utils import (
    get_default_account_id, get_plexus_url, find_score_instance
)

def register_score_tools(mcp: FastMCP):
    """Register score management tools with the MCP server"""
    
    @mcp.tool()
    async def plexus_score_info(
        score_identifier: str,
        scorecard_identifier: Optional[str] = None,
        version_id: Optional[str] = None,
        include_versions: bool = False
    ) -> Union[str, Dict[str, Any]]:
        """
        Get detailed information about a specific score, including its location, configuration, and optionally all versions.
        Supports intelligent search across scorecards when scorecard_identifier is omitted.
        
        Parameters:
        - score_identifier: Identifier for the score (ID, name, key, or external ID)
        - scorecard_identifier: Optional identifier for the parent scorecard to narrow search. If omitted, searches across all scorecards.
        - version_id: Optional specific version ID to show configuration for. If omitted, uses champion version.
        - include_versions: If True, include detailed version information and all versions list
        
        Returns:
        - Information about the found score including its location, configuration, and optionally version details
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Try to import required modules directly
            try:
                from plexus.dashboard.api.client import PlexusDashboardClient
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
                from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
            except ImportError as e:
                return f"Error: Could not import required modules: {e}. Core modules may not be available."
            
            # Check if we have the necessary credentials
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                logger.warning("Missing API credentials. Ensure .env file is loaded.")
                return "Error: Missing API credentials. Use --env-file to specify your .env file path."
            
            # Create the client
            try:
                client_stdout = StringIO()
                saved_stdout = sys.stdout
                sys.stdout = client_stdout
                
                try:
                    client = create_dashboard_client()
                finally:
                    client_output = client_stdout.getvalue()
                    if client_output:
                        logger.warning(f"Captured unexpected stdout during client creation in find_plexus_score: {client_output}")
                    sys.stdout = saved_stdout
            except Exception as client_err:
                logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
                return f"Error creating dashboard client: {str(client_err)}"
                
            if not client:
                return "Error: Could not create dashboard client."

            # Build search strategy
            found_scores = []
            
            if scorecard_identifier:
                # Search within a specific scorecard
                scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
                if not scorecard_id:
                    return f"Error: Scorecard '{scorecard_identifier}' not found."
                
                # Get scorecard with scores
                scorecard_query = f"""
                query GetScorecardWithScores {{
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
                                        description
                                        type
                                        championVersionId
                                        isDisabled
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
                """
                
                result = client.execute(scorecard_query)
                scorecard_data = result.get('getScorecard')
                
                if scorecard_data:
                    for section in scorecard_data.get('sections', {}).get('items', []):
                        for score in section.get('scores', {}).get('items', []):
                            # Check if this score matches the identifier
                            if (score.get('id') == score_identifier or 
                                score.get('name', '').lower() == score_identifier.lower() or 
                                score.get('key') == score_identifier or 
                                score.get('externalId') == score_identifier or
                                score_identifier.lower() in score.get('name', '').lower()):
                                
                                found_scores.append({
                                    'score': score,
                                    'section': section,
                                    'scorecard': scorecard_data
                                })
            else:
                # Search across all scorecards for the score
                default_account_id = get_default_account_id()
                if not default_account_id:
                    return "Error: No default account available for searching scorecards."
                
                # Get all scorecards for the account
                scorecards_query = f"""
                query ListScorecardsForSearch {{
                    listScorecards(filter: {{ accountId: {{ eq: "{default_account_id}" }} }}, limit: 100) {{
                        items {{
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
                                            description
                                            type
                                            championVersionId
                                            isDisabled
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
                """
                
                result = client.execute(scorecards_query)
                scorecards = result.get('listScorecards', {}).get('items', [])
                
                # Search through all scorecards
                for scorecard in scorecards:
                    for section in scorecard.get('sections', {}).get('items', []):
                        for score in section.get('scores', {}).get('items', []):
                            # Check if this score matches the identifier  
                            if (score.get('id') == score_identifier or 
                                score.get('name', '').lower() == score_identifier.lower() or 
                                score.get('key') == score_identifier or 
                                score.get('externalId') == score_identifier or
                                score_identifier.lower() in score.get('name', '').lower()):
                                
                                found_scores.append({
                                    'score': score,
                                    'section': section,
                                    'scorecard': scorecard
                                })

            if not found_scores:
                search_scope = f" within scorecard '{scorecard_identifier}'" if scorecard_identifier else " across all scorecards"
                return f"No scores found matching '{score_identifier}'{search_scope}."
            
            if len(found_scores) == 1:
                # Single match - return detailed information
                match = found_scores[0]
                score = match['score']
                section = match['section']
                scorecard = match['scorecard']
                score_id = score['id']
                scorecard_id = scorecard['id']
                
                # Base response object
                response = {
                    "found": True,
                    "scoreId": score_id,
                    "scoreName": score['name'],
                    "scoreKey": score.get('key'),
                    "externalId": score.get('externalId'),
                    "description": score.get('description'),
                    "type": score.get('type'),
                    "championVersionId": score.get('championVersionId'),
                    "isDisabled": score.get('isDisabled', False),
                    "location": {
                        "scorecardId": scorecard_id,
                        "scorecardName": scorecard['name'],
                        "sectionId": section['id'],
                        "sectionName": section['name']
                    },
                    "dashboardUrl": get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score_id}")
                }
                
                if include_versions or version_id:
                    # Get detailed version information like get_plexus_score_details
                    try:
                        score_versions_query = f"""
                        query GetScoreVersions {{
                            getScore(id: "{score_id}") {{
                                id
                                name
                                key
                                externalId
                                championVersionId
                                versions(sortDirection: DESC, limit: 50) {{
                                    items {{
                                        id
                                        configuration
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
                        
                        versions_response = client.execute(score_versions_query)
                        if 'errors' in versions_response:
                            logger.error(f"Error fetching versions: {versions_response['errors']}")
                            response["versionsError"] = f"Error fetching versions: {versions_response['errors']}"
                        else:
                            score_data_with_versions = versions_response.get('getScore')
                            if score_data_with_versions:
                                all_versions = score_data_with_versions.get('versions', {}).get('items', [])
                                
                                # Find target version
                                target_version_data = None
                                if version_id:
                                    for v in all_versions:
                                        if v.get('id') == version_id:
                                            target_version_data = v
                                            break
                                    if not target_version_data:
                                        response["versionError"] = f"Specified version ID '{version_id}' not found"
                                else:
                                    # Use champion version
                                    effective_champion_id = score_data_with_versions.get('championVersionId') or score.get('championVersionId')
                                    if effective_champion_id:
                                        for v in all_versions:
                                            if v.get('id') == effective_champion_id:
                                                target_version_data = v
                                                break
                                    if not target_version_data and all_versions:
                                        target_version_data = all_versions[0]  # Most recent
                                
                                if target_version_data:
                                    response["targetedVersionDetails"] = target_version_data
                                    response["configuration"] = target_version_data.get('configuration')
                                    
                                if include_versions:
                                    response["allVersions"] = all_versions
                                    
                    except Exception as e:
                        logger.error(f"Error fetching version details: {str(e)}", exc_info=True)
                        response["versionsError"] = f"Error fetching version details: {str(e)}"
                else:
                    # Get configuration preview if champion version exists (original behavior)
                    config_preview = "No configuration available"
                    champion_version_id = score.get('championVersionId')
                    if champion_version_id:
                        try:
                            version_query = f"""
                            query GetScoreVersion {{
                                getScoreVersion(id: "{champion_version_id}") {{
                                    configuration
                                }}
                            }}
                            """
                            version_result = client.execute(version_query)
                            version_data = version_result.get('getScoreVersion')
                            if version_data and version_data.get('configuration'):
                                config = version_data['configuration']
                                # Show first few lines as preview
                                config_lines = config.split('\n')[:5]
                                config_preview = '\n'.join(config_lines)
                                if len(config.split('\n')) > 5:
                                    config_preview += '\n... (truncated)'
                        except Exception as e:
                            config_preview = f"Error loading configuration: {str(e)}"
                    
                    response["configurationPreview"] = config_preview
                
                return response
            else:
                # Multiple matches - return summary list
                matches = []
                for match in found_scores:
                    score = match['score']
                    scorecard = match['scorecard']
                    section = match['section']
                    matches.append({
                        "scoreId": score['id'],
                        "scoreName": score['name'],
                        "scorecardName": scorecard['name'],
                        "sectionName": section['name'],
                        "isDisabled": score.get('isDisabled', False),
                        "dashboardUrl": get_plexus_url(f"lab/scorecards/{scorecard['id']}/scores/{score['id']}")
                    })
                
                return {
                    "found": True,
                    "multiple": True,
                    "count": len(found_scores),
                    "matches": matches,
                    "message": f"Found {len(found_scores)} scores matching '{score_identifier}'. Use more specific identifiers to narrow down the search."
                }
            
        except Exception as e:
            logger.error(f"Error finding score '{score_identifier}': {str(e)}", exc_info=True)
            return f"Error finding score: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during find_plexus_score: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_score_delete(
        score_id: str,
        confirm: Optional[bool] = False
    ) -> Union[str, Dict[str, Any]]:
        """
        Deletes a specific score by its ID.
        
        Parameters:
        - score_id: The ID of the score to delete
        - confirm: Whether to skip confirmation (default: False for safety)
        
        Returns:
        - Confirmation of deletion or error message
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Core availability is enforced at server startup
            
            # Ensure project root is in Python path for ScoreService import
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
                logger.info(f"Added project root to Python path: {project_root}")
            
            try:
                # Use the shared score service
                from plexus.cli.score.scores import ScoreService
                logger.info("Successfully imported ScoreService")
                
                score_service = ScoreService()
                result = score_service.delete_score(score_id, confirm)
                
                return result
                
            except ImportError as import_err:
                logger.error(f"Failed to import ScoreService: {import_err}")
                # Add more detailed debugging
                logger.error(f"Current working directory: {os.getcwd()}")
                logger.error(f"Python path first 3 entries: {sys.path[:3]}")
                score_init_path = os.path.join(project_root, "plexus", "cli", "score", "__init__.py")
                score_service_path = os.path.join(project_root, "plexus", "cli", "score", "score_service.py")
                logger.error(f"Score __init__.py exists: {os.path.exists(score_init_path)}")
                logger.error(f"Score service exists: {os.path.exists(score_service_path)}")
                return f"Error: Failed to import ScoreService. {import_err}"
                
            except Exception as service_err:
                logger.error(f"Error using ScoreService: {service_err}")
                return f"Error using ScoreService: {service_err}"
            
        except Exception as e:
            logger.error(f"Unexpected error in delete_plexus_score: {str(e)}", exc_info=True)
            return f"Unexpected error: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during delete_plexus_score: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout