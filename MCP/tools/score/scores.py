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
                                        guidelines
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
                                    response["code"] = target_version_data.get('configuration')
                                    response["guidelines"] = target_version_data.get('guidelines')
                                    
                                if include_versions:
                                    response["allVersions"] = all_versions
                                    
                    except Exception as e:
                        logger.error(f"Error fetching version details: {str(e)}", exc_info=True)
                        response["versionsError"] = f"Error fetching version details: {str(e)}"
                else:
                    # Get full configuration if champion version exists (no truncation)
                    configuration = None
                    champion_version_id = score.get('championVersionId')
                    if champion_version_id:
                        try:
                            version_query = f"""
                            query GetScoreVersion {{
                                getScoreVersion(id: "{champion_version_id}") {{
                                    configuration
                                    guidelines
                                }}
                            }}
                            """
                            version_result = client.execute(version_query)
                            version_data = version_result.get('getScoreVersion')
                            if version_data and version_data.get('configuration'):
                                configuration = version_data['configuration']
                                # Also include guidelines if available
                                if version_data.get('guidelines'):
                                    response["guidelines"] = version_data['guidelines']
                        except Exception as e:
                            configuration = f"Error loading configuration: {str(e)}"
                    
                    response["code"] = configuration
                
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
                        guidelines
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
                    "guidelines": version_data.get('guidelines'),
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
                            configuration
                            guidelines
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
                    "guidelines": version_data.get('guidelines'),
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
        Pulls a score's champion version code and guidelines to local files.
        Uses the reusable Score.pull_code_and_guidelines() method for implementation.
        
        Parameters:
        - scorecard_identifier: Identifier for the parent scorecard (ID, name, key, or external ID)
        - score_identifier: Identifier for the score (ID, name, key, or external ID)
        
        Returns:
        - Information about the pulled code and guidelines, including local file paths
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

            # Use the Score model's pull_code_and_guidelines method
            pull_result = score.pull_code_and_guidelines(scorecard_name=scorecard_name)
            
            if not pull_result["success"]:
                return f"Error: {pull_result.get('message', 'Failed to pull code and guidelines')}"
            
            return {
                "success": True,
                "scoreId": score.id,
                "scoreName": score.name,
                "scorecardName": scorecard_name,
                "codeFilePath": pull_result["code_file_path"],
                "guidelinesFilePath": pull_result["guidelines_file_path"],
                "versionId": pull_result["version_id"],
                "message": pull_result["message"],
                "dashboardUrl": _get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score.id}")
            }
            
        except Exception as e:
            logger.error(f"Error pulling score code and guidelines: {str(e)}", exc_info=True)
            return f"Error pulling score code and guidelines: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during plexus_score_pull: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_score_push(
        scorecard_identifier: str,
        score_identifier: str,
        version_note: Optional[str] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Pushes a score's local code and guidelines files to create a new version.
        Automatically detects which files have changed and pushes accordingly.
        Uses the reusable Score.push_code_and_guidelines() method for implementation.
        
        Parameters:
        - scorecard_identifier: Identifier for the parent scorecard (ID, name, key, or external ID)
        - score_identifier: Identifier for the score (ID, name, key, or external ID)
        - version_note: Optional note describing the changes made in this version
        
        Returns:
        - Information about the pushed code/guidelines and new version
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

            # Use the Score model's push_code_and_guidelines method
            push_result = score.push_code_and_guidelines(
                scorecard_name=scorecard_name,
                note=version_note or "Updated via MCP pull/push workflow"
            )
            
            if not push_result["success"]:
                return f"Error: {push_result.get('message', 'Failed to push code and guidelines')}"
            
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
                "codeLength": config_length,
                "createdAt": created_at,
                # Enforce never promoting champion from MCP push
                "championUpdated": False,
                "skipped": push_result.get("skipped", False),
                "changesDetected": push_result.get("changes_detected", {}),
                "message": push_result["message"],
                "dashboardUrl": _get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score.id}")
            }
            
        except Exception as e:
            logger.error(f"Error pushing score code and guidelines: {str(e)}", exc_info=True)
            return f"Error pushing score code and guidelines: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during plexus_score_push: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_score_update(
        scorecard_identifier: str,
        score_identifier: str,
        # Score metadata fields (updates Score record)
        name: Optional[str] = None,
        key: Optional[str] = None,
        external_id: Optional[str] = None,
        description: Optional[str] = None,
        is_disabled: Optional[bool] = None,
        ai_provider: Optional[str] = None,
        ai_model: Optional[str] = None,
        order: Optional[int] = None,
        # ScoreVersion fields (creates new version if changed)
        code: Optional[str] = None,
        guidelines: Optional[str] = None,
        version_note: Optional[str] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Intelligently updates a score's metadata and/or creates a new version with updated code/guidelines.
        
        This tool can update:
        1. Score metadata (name, key, external_id, description, etc.) - updates the Score record directly
        2. Score version content (code YAML, guidelines) - creates a new ScoreVersion if content changed
        
        Parameters:
        - scorecard_identifier: Identifier for the parent scorecard (ID, name, key, or external ID)
        - score_identifier: Identifier for the score (ID, name, key, or external ID)
        
        Score Metadata Updates (updates Score record):
        - name: New display name for the score
        - key: New unique key for the score  
        - external_id: New external ID for the score
        - description: New description for the score
        - is_disabled: Whether the score should be disabled
        - ai_provider: New AI provider
        - ai_model: New AI model
        - order: New display order
        
        ScoreVersion Updates (creates new version if content changed):
        - code: The new YAML code content for the score
        - guidelines: The new guidelines content for the score
        - version_note: Optional note describing the changes made in this version
        
        Returns:
        - Information about what was updated (metadata and/or version), including dashboard URL
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
            
            # Validate that at least one field is provided for update
            metadata_fields = {
                'name': name,
                'key': key,
                'external_id': external_id,
                'description': description,
                'is_disabled': is_disabled,
                'ai_provider': ai_provider,
                'ai_model': ai_model,
                'order': order
            }
            version_fields = {
                'code': code,
                'guidelines': guidelines
            }
            
            has_metadata_updates = any(v is not None for v in metadata_fields.values())
            has_version_updates = any(v is not None for v in version_fields.values())
            
            if not has_metadata_updates and not has_version_updates:
                return "Error: At least one field must be provided for update (metadata or version content)"
            
            # Validate YAML code if provided
            if code:
                try:
                    import yaml
                    yaml.safe_load(code)
                except yaml.YAMLError as e:
                    return f"Error: Invalid YAML code: {str(e)}"
            
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
                        logger.warning(f"Captured unexpected stdout during client creation in plexus_score_update: {client_output}")
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

            # Track what was updated
            updates_performed = {
                "metadata_updated": False,
                "version_created": False,
                "metadata_changes": {},
                "version_info": {}
            }

            # 1. Handle Score metadata updates first
            if has_metadata_updates:
                # Build update input for Score metadata
                update_input = {'id': score.id}
                
                # Only include fields that are actually being updated
                if name is not None:
                    update_input['name'] = name
                    updates_performed["metadata_changes"]["name"] = name
                if key is not None:
                    update_input['key'] = key
                    updates_performed["metadata_changes"]["key"] = key
                if external_id is not None:
                    update_input['externalId'] = external_id
                    updates_performed["metadata_changes"]["external_id"] = external_id
                if description is not None:
                    update_input['description'] = description
                    updates_performed["metadata_changes"]["description"] = description
                if is_disabled is not None:
                    update_input['isDisabled'] = is_disabled
                    updates_performed["metadata_changes"]["is_disabled"] = is_disabled
                if ai_provider is not None:
                    update_input['aiProvider'] = ai_provider
                    updates_performed["metadata_changes"]["ai_provider"] = ai_provider
                if ai_model is not None:
                    update_input['aiModel'] = ai_model
                    updates_performed["metadata_changes"]["ai_model"] = ai_model
                if order is not None:
                    update_input['order'] = order
                    updates_performed["metadata_changes"]["order"] = order

                # Execute Score metadata update
                update_mutation = """
                mutation UpdateScore($input: UpdateScoreInput!) {
                    updateScore(input: $input) {
                        id
                        name
                        key
                        externalId
                        description
                        isDisabled
                        aiProvider
                        aiModel
                        order
                    }
                }
                """
                
                try:
                    update_result = client.execute(update_mutation, {'input': update_input})
                    if update_result and 'updateScore' in update_result:
                        updates_performed["metadata_updated"] = True
                        logger.info(f"Successfully updated Score metadata for {score.name}")
                    else:
                        return f"Error: Failed to update Score metadata: {update_result}"
                except Exception as e:
                    return f"Error updating Score metadata: {str(e)}"

            # 2. Handle ScoreVersion updates (configuration/guidelines)
            if has_version_updates:
                # If only guidelines provided, get current code to preserve it
                if guidelines is not None and code is None:
                    # Get current champion version code to preserve it
                    champion_query = f"""
                    query GetScore {{
                        getScore(id: "{score.id}") {{
                            championVersionId
                        }}
                    }}
                    """
                    champion_result = client.execute(champion_query)
                    current_champion_id = champion_result.get('getScore', {}).get('championVersionId')
                    
                    if current_champion_id:
                        config_query = f"""
                        query GetScoreVersion {{
                            getScoreVersion(id: "{current_champion_id}") {{
                                configuration
                            }}
                        }}
                        """
                        config_result = client.execute(config_query)
                        code = config_result.get('getScoreVersion', {}).get('configuration', '')
                
                # Create new version with updated content
                if code:  # Only proceed if we have code
                    result = score.create_version_from_code(
                        code,
                        note=version_note or "Updated via MCP server",
                        guidelines=guidelines
                    )
                    
                    if result["success"]:
                        updates_performed["version_created"] = not result.get("skipped", False)
                        updates_performed["version_info"] = {
                            "version_id": result["version_id"],
                            "skipped": result.get("skipped", False),
                            "message": result["message"]
                        }
                        
                        if not result.get("skipped", False):
                            logger.info(f"Successfully created new version for Score {score.name}")
                    else:
                        return f"Error creating new version: {result.get('message', 'Unknown error')}"

            # Build comprehensive response
            response = {
                "success": True,
                "scoreId": score.id,
                "scoreName": score.name,
                "scorecardName": scorecard_name,
                "updates": updates_performed,
                "dashboardUrl": _get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score.id}")
            }
            
            # Add version-specific info if version was updated
            if updates_performed["version_created"]:
                response["newVersionId"] = updates_performed["version_info"]["version_id"]
                response["versionNote"] = version_note or "Updated via MCP server"
                
                # Get creation timestamp
                new_version_id = updates_performed["version_info"]["version_id"]
                version_query = f"""
                query GetScoreVersion {{
                    getScoreVersion(id: "{new_version_id}") {{
                        createdAt
                    }}
                }}
                """
                version_result = client.execute(version_query)
                response["createdAt"] = version_result.get('getScoreVersion', {}).get('createdAt')

            return response
            
        except Exception as e:
            logger.error(f"Error updating score: {str(e)}", exc_info=True)
            return f"Error updating score: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during plexus_score_update: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout


    @mcp.tool()
    async def plexus_score_create(
        name: str,
        scorecard_identifier: str,
        section_identifier: Optional[str] = None,
        score_type: str = "SimpleLLMScore",
        external_id: Optional[str] = None,
        key: Optional[str] = None,
        description: Optional[str] = None,
        ai_provider: Optional[str] = None,
        ai_model: Optional[str] = None,
        order: Optional[int] = None,
        is_disabled: bool = False
    ) -> Union[str, Dict[str, Any]]:
        """
        Creates a new score in the specified scorecard and section.
        
        Parameters:
        - name: Display name for the score (required)
        - scorecard_identifier: Identifier for the parent scorecard (ID, name, key, or external ID) (required)
        - section_identifier: Identifier for the section (name or ID). If not provided, uses the first available section
        - score_type: Type of score (default: "SimpleLLMScore"). Options: "SimpleLLMScore", "LangGraphScore", "ClassifierScore", "STANDARD"
        - external_id: External ID for the score. If not provided, generates a unique ID
        - key: Unique key for the score. If not provided, generates from name
        - description: Optional description for the score
        - ai_provider: AI provider (default: "unknown")
        - ai_model: AI model (default: "unknown")
        - order: Display order in section. If not provided, uses next available order
        - is_disabled: Whether the score is disabled (default: False)
        
        Returns:
        - Information about the created score including its ID and dashboard URL
        """
        import uuid
        import re
        
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Validate required parameters
            if not name or not name.strip():
                return "Error: name is required and cannot be empty"
            
            if not scorecard_identifier or not scorecard_identifier.strip():
                return "Error: scorecard_identifier is required and cannot be empty"
            
            # Validate score_type
            valid_types = ["SimpleLLMScore", "LangGraphScore", "ClassifierScore", "STANDARD"]
            if score_type not in valid_types:
                return f"Error: score_type must be one of: {', '.join(valid_types)}"
            
            # Try to import required modules directly
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
                from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
                from plexus.cli.report.utils import resolve_account_id_for_command
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
                        logger.warning(f"Captured unexpected stdout during client creation in plexus_score_create: {client_output}")
                    sys.stdout = saved_stdout
            except Exception as client_err:
                logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
                return f"Error creating dashboard client: {str(client_err)}"
                
            if not client:
                return "Error: Could not create dashboard client."

            # Resolve scorecard ID
            scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
            if not scorecard_id:
                return f"Error: Scorecard '{scorecard_identifier}' not found."
            
            # Get default account ID
            account_id = resolve_account_id_for_command(client, None)
            if not account_id:
                return "Error: No default account available for score creation."
            
            # Get scorecard details including sections
            scorecard_query = f"""
            query GetScorecardForScoreCreation {{
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
                return f"Error: Could not retrieve scorecard data for '{scorecard_identifier}'."
            
            sections = scorecard_data.get('sections', {}).get('items', [])
            if not sections:
                return f"Error: No sections found in scorecard '{scorecard_identifier}'. Cannot create score without a section."
            
            # Find target section
            target_section = None
            if section_identifier:
                # Search for section by name or ID
                for section in sections:
                    if (section.get('id') == section_identifier or 
                        section.get('name', '').lower() == section_identifier.lower()):
                        target_section = section
                        break
                
                if not target_section:
                    return f"Error: Section '{section_identifier}' not found in scorecard '{scorecard_identifier}'."
            else:
                # Use first available section
                target_section = sections[0]
            
            # Generate defaults if not provided
            if not key:
                # Generate key from name: lowercase, replace spaces with underscores, remove special chars
                key = name.lower().replace(' ', '_')
                key = re.sub(r'[^a-z0-9_]', '', key)
                if not key:
                    key = f"score_{uuid.uuid4().hex[:8]}"
            
            if not external_id:
                external_id = f"score_{uuid.uuid4().hex[:8]}"
            
            if ai_provider is None:
                ai_provider = "unknown"
            
            if ai_model is None:
                ai_model = "unknown"
            
            # Calculate order if not provided
            if order is None:
                existing_scores = target_section.get('scores', {}).get('items', [])
                order = len(existing_scores)
            
            # Prepare mutation variables
            is_disabled_str = "true" if is_disabled else "false"
            
            # Create score mutation
            create_score_mutation = f"""
            mutation CreateScore {{
                createScore(input: {{
                    name: "{name}"
                    key: "{key}"
                    externalId: "{external_id}"
                    order: {order}
                    type: "{score_type}"
                    aiProvider: "{ai_provider}"
                    aiModel: "{ai_model}"
                    sectionId: "{target_section['id']}"
                    scorecardId: "{scorecard_id}"
                    isDisabled: {is_disabled_str}
                    {f'description: "{description}"' if description else ''}
                }}) {{
                    id
                    name
                    key
                    externalId
                    type
                    order
                    sectionId
                    scorecardId
                    isDisabled
                    description
                    createdAt
                }}
            }}
            """
            
            create_result = client.execute(create_score_mutation)
            created_score = create_result.get('createScore')
            
            if not created_score:
                error_msg = "Failed to create score"
                if 'errors' in create_result:
                    error_details = '; '.join([error.get('message', str(error)) for error in create_result['errors']])
                    error_msg += f": {error_details}"
                return f"Error: {error_msg}"
            
            return {
                "success": True,
                "scoreId": created_score['id'],
                "scoreName": created_score['name'],
                "scoreKey": created_score['key'],
                "externalId": created_score['externalId'],
                "scoreType": created_score['type'],
                "order": created_score['order'],
                "isDisabled": created_score.get('isDisabled', False),
                "description": created_score.get('description'),
                "location": {
                    "scorecardId": scorecard_id,
                    "scorecardName": scorecard_data['name'],
                    "sectionId": target_section['id'],
                    "sectionName": target_section['name']
                },
                "createdAt": created_score.get('createdAt'),
                "dashboardUrl": _get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{created_score['id']}")
            }
            
        except Exception as e:
            logger.error(f"Error creating score: {str(e)}", exc_info=True)
            return f"Error creating score: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during plexus_score_create: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout



    @mcp.tool()
    async def plexus_score_metadata_update(
        score_id: str,
        name: Optional[str] = None,
        key: Optional[str] = None,
        external_id: Optional[str] = None,
        description: Optional[str] = None,
        is_disabled: Optional[bool] = None,
        ai_provider: Optional[str] = None,
        ai_model: Optional[str] = None,
        order: Optional[int] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Updates a score's metadata fields.
        
        Parameters:
        - score_id: The ID of the score to update
        - name: New display name for the score
        - key: New unique key for the score
        - external_id: New external ID for the score
        - description: New description for the score
        - is_disabled: Whether the score should be disabled
        - ai_provider: New AI provider
        - ai_model: New AI model
        - order: New display order
        
        Returns:
        - Information about the updated score
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Validate that at least one field is provided for update
            update_fields = {
                'name': name,
                'key': key,
                'external_id': external_id,
                'description': description,
                'is_disabled': is_disabled,
                'ai_provider': ai_provider,
                'ai_model': ai_model,
                'order': order
            }
            
            provided_updates = {k: v for k, v in update_fields.items() if v is not None}
            if not provided_updates:
                return "Error: At least one field to update must be provided"
            
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
                        logger.warning(f"Captured unexpected stdout during client creation in plexus_score_metadata_update: {client_output}")
                    sys.stdout = saved_stdout
            except Exception as client_err:
                logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
                return f"Error creating dashboard client: {str(client_err)}"
                
            if not client:
                return "Error: Could not create dashboard client."

            # Build update input
            update_input = {'id': score_id}
            updated_fields = {}
            
            # Only include fields that are actually being updated
            if name is not None:
                update_input['name'] = name
                updated_fields['name'] = name
            if key is not None:
                update_input['key'] = key
                updated_fields['key'] = key
            if external_id is not None:
                update_input['externalId'] = external_id
                updated_fields['externalId'] = external_id
            if description is not None:
                update_input['description'] = description
                updated_fields['description'] = description
            if is_disabled is not None:
                update_input['isDisabled'] = is_disabled
                updated_fields['isDisabled'] = is_disabled
            if ai_provider is not None:
                update_input['aiProvider'] = ai_provider
                updated_fields['aiProvider'] = ai_provider
            if ai_model is not None:
                update_input['aiModel'] = ai_model
                updated_fields['aiModel'] = ai_model
            if order is not None:
                update_input['order'] = order
                updated_fields['order'] = order

            # Execute Score metadata update
            update_mutation = """
            mutation UpdateScore($input: UpdateScoreInput!) {
                updateScore(input: $input) {
                    id
                    name
                    key
                    externalId
                    description
                    isDisabled
                    aiProvider
                    aiModel
                    order
                    updatedAt
                }
            }
            """
            
            try:
                update_result = client.execute(update_mutation, {'input': update_input})
                if update_result and 'updateScore' in update_result:
                    updated_score = update_result['updateScore']
                    return {
                        "success": True,
                        "scoreId": updated_score['id'],
                        "updatedFields": updated_fields,
                        "updatedAt": updated_score.get('updatedAt')
                    }
                else:
                    return f"Error: Failed to update Score metadata: {update_result}"
            except Exception as e:
                return f"Error updating score: {str(e)}"
            
        except Exception as e:
            logger.error(f"Error updating score metadata: {str(e)}", exc_info=True)
            return f"Error updating score metadata: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during plexus_score_metadata_update: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_score_delete(
        score_id: str,
        confirm: bool = False
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
            # Handle boolean parameter conversion (MCP may send strings)
            if isinstance(confirm, str):
                confirm = confirm.lower() in ['true', '1', 'yes']
            elif not isinstance(confirm, bool):
                return f"Error: confirm must be a boolean value, got {type(confirm)}"
            
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
                from plexus.cli.score.score_service import ScoreService
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