#!/usr/bin/env python3
"""
Score management tools for Plexus MCP Server
"""
import os
import sys
import json
import logging
from typing import Dict, Any, List, Union, Optional
from io import StringIO
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_score_tools(mcp: FastMCP):
    """Register score tools with the MCP server"""
    
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
                from plexus.cli.report.utils import resolve_account_id_for_command
                
                client_for_account = create_dashboard_client()
                default_account_id = resolve_account_id_for_command(client_for_account, None)
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
                    "dashboardUrl": _get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score_id}")
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
                        "dashboardUrl": _get_plexus_url(f"lab/scorecards/{scorecard['id']}/scores/{score['id']}")
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

    async def _find_score_instance(scorecard_identifier: str, score_identifier: str, client) -> Dict[str, Any]:
        """
        Helper function to find a Score instance from scorecard and score identifiers.
        
        Returns a dict containing:
        - success: bool
        - score: Score instance (if successful)
        - scorecard_name: str (if successful)
        - scorecard_id: str (if successful)
        - error: str (if failed)
        """
        try:
            from plexus.dashboard.api.models.score import Score
            from plexus.dashboard.api.models.scorecard import Scorecard
            from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
            
            # Resolve scorecard identifier
            scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
            if not scorecard_id:
                return {
                    "success": False,
                    "error": f"Scorecard '{scorecard_identifier}' not found."
                }

            # Get scorecard name
            scorecard = Scorecard.get_by_id(scorecard_id, client)
            if not scorecard:
                return {
                    "success": False,
                    "error": f"Could not retrieve scorecard data for ID '{scorecard_id}'."
                }

            # Find the score within the scorecard
            scorecard_query = f"""
            query GetScorecardForScore {{
                getScorecard(id: "{scorecard_id}") {{
                    sections {{
                        items {{
                            id
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
            
            result = client.execute(scorecard_query)
            scorecard_data = result.get('getScorecard')
            if not scorecard_data:
                return {
                    "success": False,
                    "error": f"Could not retrieve scorecard sections for '{scorecard_identifier}'."
                }

            # Find the specific score
            found_score_data = None
            found_section_id = None
            for section in scorecard_data.get('sections', {}).get('items', []):
                for score_data in section.get('scores', {}).get('items', []):
                    if (score_data.get('id') == score_identifier or 
                        score_data.get('name') == score_identifier or 
                        score_data.get('key') == score_identifier or 
                        score_data.get('externalId') == score_identifier):
                        found_score_data = score_data
                        found_section_id = section['id']
                        break
                if found_score_data:
                    break

            if not found_score_data:
                return {
                    "success": False,
                    "error": f"Score '{score_identifier}' not found within scorecard '{scorecard_identifier}'."
                }

            # Create Score instance
            score = Score(
                id=found_score_data['id'],
                name=found_score_data['name'],
                key=found_score_data['key'],
                externalId=found_score_data['externalId'],
                type=found_score_data['type'],
                order=found_score_data['order'],
                sectionId=found_section_id,
                client=client
            )

            return {
                "success": True,
                "score": score,
                "scorecard_name": scorecard.name,
                "scorecard_id": scorecard_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error finding score: {str(e)}"
            }

    @mcp.tool()
    async def plexus_score_configuration(
        scorecard_identifier: str,
        score_identifier: str,
        version_id: Optional[str] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Gets the YAML configuration for a specific score version, with syntax highlighting and formatting.
        
        Parameters:
        - scorecard_identifier: Identifier for the parent scorecard (ID, name, key, or external ID)
        - score_identifier: Identifier for the score (ID, name, key, or external ID)
        - version_id: Optional specific version ID of the score. If omitted, uses champion version.
        
        Returns:
        - The YAML configuration content along with metadata about the version
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Try to import required modules directly
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
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
                        logger.warning(f"Captured unexpected stdout during client creation in get_plexus_score_configuration: {client_output}")
                    sys.stdout = saved_stdout
            except Exception as client_err:
                logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
                return f"Error creating dashboard client: {str(client_err)}"
                
            if not client:
                return "Error: Could not create dashboard client."

            # Find the score instance
            find_result = await _find_score_instance(scorecard_identifier, score_identifier, client)
            if not find_result["success"]:
                return find_result["error"]
            
            score = find_result["score"]
            scorecard_name = find_result["scorecard_name"]
            scorecard_id = find_result["scorecard_id"]

            # Get configuration using the Score model method
            if version_id:
                # If specific version requested, get that version directly
                version_query = f"""
                query GetScoreVersion {{
                    getScoreVersion(id: "{version_id}") {{
                        id
                        configuration
                        createdAt
                        updatedAt
                        note
                        isFeatured
                        parentVersionId
                    }}
                }}
                """
                
                version_result = client.execute(version_query)
                version_data = version_result.get('getScoreVersion')
                
                if not version_data:
                    return f"Error: Version '{version_id}' not found."

                configuration = version_data.get('configuration')
                if not configuration:
                    return f"Error: No configuration found for version '{version_id}'."
                    
                # Check if this is the champion version
                champion_query = f"""
                query GetScoreChampion {{
                    getScore(id: "{score.id}") {{
                        championVersionId
                    }}
                }}
                """
                champion_result = client.execute(champion_query)
                champion_version_id = champion_result.get('getScore', {}).get('championVersionId')
                is_champion = version_id == champion_version_id

                return {
                    "scoreId": score.id,
                    "scoreName": score.name,
                    "scorecardName": scorecard_name,
                    "versionId": version_data['id'],
                    "isChampionVersion": is_champion,
                    "configuration": configuration,
                    "versionMetadata": {
                        "createdAt": version_data.get('createdAt'),
                        "updatedAt": version_data.get('updatedAt'),
                        "note": version_data.get('note'),
                        "isFeatured": version_data.get('isFeatured'),
                        "parentVersionId": version_data.get('parentVersionId')
                    },
                    "dashboardUrl": _get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score.id}")
                }
            else:
                # Use Score.get_configuration() for champion version
                config_dict = score.get_configuration()
                if not config_dict:
                    return f"Error: No champion version configuration found for score '{score.name}'."
                
                # Convert dict back to YAML string for consistency with API
                import yaml
                configuration = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
                
                # Get champion version metadata
                champion_query = f"""
                query GetScoreWithChampionVersion {{
                    getScore(id: "{score.id}") {{
                        championVersionId
                    }}
                }}
                """
                champion_result = client.execute(champion_query)
                champion_version_id = champion_result.get('getScore', {}).get('championVersionId')
                
                if champion_version_id:
                    version_query = f"""
                    query GetScoreVersion {{
                        getScoreVersion(id: "{champion_version_id}") {{
                            id
                            createdAt
                            updatedAt
                            note
                            isFeatured
                            parentVersionId
                        }}
                    }}
                    """
                    
                    version_result = client.execute(version_query)
                    version_data = version_result.get('getScoreVersion', {})
                else:
                    version_data = {}

                return {
                    "scoreId": score.id,
                    "scoreName": score.name,
                    "scorecardName": scorecard_name,
                    "versionId": champion_version_id,
                    "isChampionVersion": True,
                    "configuration": configuration,
                    "versionMetadata": {
                        "createdAt": version_data.get('createdAt'),
                        "updatedAt": version_data.get('updatedAt'),
                        "note": version_data.get('note'),
                        "isFeatured": version_data.get('isFeatured'),
                        "parentVersionId": version_data.get('parentVersionId')
                    },
                    "dashboardUrl": _get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score.id}")
                }
            
        except Exception as e:
            logger.error(f"Error getting score configuration: {str(e)}", exc_info=True)
            return f"Error getting score configuration: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during get_plexus_score_configuration: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_score_pull(
        scorecard_identifier: str,
        score_identifier: str
    ) -> Union[str, Dict[str, Any]]:
        """
        Pulls a score's champion version YAML configuration to a local file.
        Uses the reusable Score.pull_configuration() method for implementation.
        
        Parameters:
        - scorecard_identifier: Identifier for the parent scorecard (ID, name, key, or external ID)
        - score_identifier: Identifier for the score (ID, name, key, or external ID)
        
        Returns:
        - Information about the pulled configuration, including local file path
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Try to import required modules directly
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
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
                        logger.warning(f"Captured unexpected stdout during client creation in pull_plexus_score_configuration: {client_output}")
                    sys.stdout = saved_stdout
            except Exception as client_err:
                logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
                return f"Error creating dashboard client: {str(client_err)}"
                
            if not client:
                return "Error: Could not create dashboard client."

            # Find the score instance
            find_result = await _find_score_instance(scorecard_identifier, score_identifier, client)
            if not find_result["success"]:
                return find_result["error"]
            
            score = find_result["score"]
            scorecard_name = find_result["scorecard_name"]
            scorecard_id = find_result["scorecard_id"]

            # Use the Score model's pull_configuration method
            pull_result = score.pull_configuration(scorecard_name=scorecard_name)
            
            if not pull_result["success"]:
                return f"Error: {pull_result.get('message', 'Failed to pull configuration')}"
            
            return {
                "success": True,
                "scoreId": score.id,
                "scoreName": score.name,
                "scorecardName": scorecard_name,
                "filePath": pull_result["file_path"],
                "versionId": pull_result["version_id"],
                "message": pull_result["message"],
                "dashboardUrl": _get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score.id}")
            }
            
        except Exception as e:
            logger.error(f"Error pulling score configuration: {str(e)}", exc_info=True)
            return f"Error pulling score configuration: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during pull_plexus_score_configuration: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_score_push(
        scorecard_identifier: str,
        score_identifier: str,
        version_note: Optional[str] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Pushes a score's local YAML configuration file to create a new version.
        Uses the reusable Score.push_configuration() method for implementation.
        
        Parameters:
        - scorecard_identifier: Identifier for the parent scorecard (ID, name, key, or external ID)
        - score_identifier: Identifier for the score (ID, name, key, or external ID)
        - version_note: Optional note describing the changes made in this version
        
        Returns:
        - Information about the pushed configuration and new version
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Try to import required modules directly
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
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
                        logger.warning(f"Captured unexpected stdout during client creation in push_plexus_score_configuration: {client_output}")
                    sys.stdout = saved_stdout
            except Exception as client_err:
                logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
                return f"Error creating dashboard client: {str(client_err)}"
                
            if not client:
                return "Error: Could not create dashboard client."

            # Find the score instance
            find_result = await _find_score_instance(scorecard_identifier, score_identifier, client)
            if not find_result["success"]:
                return find_result["error"]
            
            score = find_result["score"]
            scorecard_name = find_result["scorecard_name"]
            scorecard_id = find_result["scorecard_id"]

            # Use the Score model's push_configuration method
            push_result = score.push_configuration(
                scorecard_name=scorecard_name,
                note=version_note or "Updated via MCP pull/push workflow"
            )
            
            if not push_result["success"]:
                return f"Error: {push_result.get('message', 'Failed to push configuration')}"
            
            # Get additional metadata for comprehensive response
            new_version_id = push_result["version_id"]
            
            # Get current champion version ID for comparison
            champion_query = f"""
            query GetScore {{
                getScore(id: "{score.id}") {{
                    championVersionId
                }}
            }}
            """
            champion_result = client.execute(champion_query)
            current_champion_id = champion_result.get('getScore', {}).get('championVersionId')
            
            # Get version creation timestamp if a new version was created
            if not push_result.get("skipped", False):
                version_query = f"""
                query GetScoreVersion {{
                    getScoreVersion(id: "{new_version_id}") {{
                        createdAt
                        configuration
                    }}
                }}
                """
                version_result = client.execute(version_query)
                version_data = version_result.get('getScoreVersion', {})
                created_at = version_data.get('createdAt')
                config_length = len(version_data.get('configuration', ''))
            else:
                created_at = None
                config_length = 0

            return {
                "success": True,
                "scoreId": score.id,
                "scoreName": score.name,
                "scorecardName": scorecard_name,
                "newVersionId": new_version_id,
                "previousChampionVersionId": current_champion_id if current_champion_id != new_version_id else None,
                "versionNote": version_note or "Updated via MCP pull/push workflow",
                "configurationLength": config_length,
                "createdAt": created_at,
                # Enforce never promoting champion from MCP push
                "championUpdated": False,
                "skipped": push_result.get("skipped", False),
                "message": push_result["message"],
                "dashboardUrl": _get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score.id}")
            }
            
        except Exception as e:
            logger.error(f"Error pushing score configuration: {str(e)}", exc_info=True)
            return f"Error pushing score configuration: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during push_plexus_score_configuration: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_score_update(
        scorecard_identifier: str,
        score_identifier: str,
        yaml_configuration: str,
        version_note: Optional[str] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Updates a score's configuration by creating a new version with the provided YAML content.
        Uses the reusable Score.push_configuration() method for implementation.
        
        Parameters:
        - scorecard_identifier: Identifier for the parent scorecard (ID, name, key, or external ID)
        - score_identifier: Identifier for the score (ID, name, key, or external ID)
        - yaml_configuration: The new YAML configuration content for the score
        - version_note: Optional note describing the changes made in this version
        
        Returns:
        - Information about the created version and updated score, including dashboard URL
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Try to import required modules directly
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
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
                        logger.warning(f"Captured unexpected stdout during client creation in update_plexus_score_configuration: {client_output}")
                    sys.stdout = saved_stdout
            except Exception as client_err:
                logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
                return f"Error creating dashboard client: {str(client_err)}"
                
            if not client:
                return "Error: Could not create dashboard client."

            # Validate YAML configuration
            try:
                import yaml
                yaml.safe_load(yaml_configuration)
            except yaml.YAMLError as e:
                return f"Error: Invalid YAML configuration: {str(e)}"

            # Find the score instance
            find_result = await _find_score_instance(scorecard_identifier, score_identifier, client)
            if not find_result["success"]:
                return find_result["error"]
            
            score = find_result["score"]
            scorecard_name = find_result["scorecard_name"]
            scorecard_id = find_result["scorecard_id"]

            # Use the foundational create_version_from_yaml method directly
            result = score.create_version_from_yaml(
                yaml_configuration,
                note=version_note or "Updated via MCP server"
            )
            
            if not result["success"]:
                return f"Error: {result.get('message', 'Failed to create version')}"
            
            # Get version creation timestamp if a new version was created
            new_version_id = result["version_id"]
            if not result.get("skipped", False):
                version_query = f"""
                query GetScoreVersion {{
                    getScoreVersion(id: "{new_version_id}") {{
                        createdAt
                    }}
                }}
                """
                version_result = client.execute(version_query)
                created_at = version_result.get('getScoreVersion', {}).get('createdAt')
            else:
                created_at = None

            return {
                "success": True,
                "scoreId": score.id,
                "scoreName": score.name,
                "scorecardName": scorecard_name,
                "newVersionId": new_version_id,
                "previousChampionVersionId": None,  # The Score method handles version tracking internally
                "versionNote": version_note or "Updated via MCP server",
                "configurationLength": len(yaml_configuration),
                "createdAt": created_at,
                # Enforce never promoting champion from MCP update
                "championUpdated": False,
                "skipped": result.get("skipped", False),
                "dashboardUrl": _get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score.id}")
            }
            
        except Exception as e:
            logger.error(f"Error updating score configuration: {str(e)}", exc_info=True)
            return f"Error updating score configuration: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during update_plexus_score_configuration: {captured_output}")
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
        import sys
        import os
        
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Check if Plexus core modules are available
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
            except ImportError:
                return "Error: Plexus Dashboard components are not available. Core modules failed to import."
            
            # Ensure project root is in Python path for ScoreService import
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
                logger.info(f"Added project root to Python path: {project_root}")
            
            try:
                # Use the shared score service
                from plexus.cli.score import ScoreService
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


def _get_plexus_url(path: str) -> str:
    """
    Safely concatenates the PLEXUS_APP_URL with the provided path.
    Handles cases where base URL may or may not have trailing slashes
    and path may or may not have leading slashes.
    
    Parameters:
    - path: The URL path to append to the base URL
    
    Returns:
    - Full URL string
    """
    from urllib.parse import urljoin
    
    base_url = os.environ.get('PLEXUS_APP_URL', 'https://plexus.anth.us')
    # Ensure base URL ends with a slash for urljoin to work correctly
    if not base_url.endswith('/'):
        base_url += '/'
    # Strip leading slash from path if present to avoid double slashes
    path = path.lstrip('/')
    return urljoin(base_url, path)