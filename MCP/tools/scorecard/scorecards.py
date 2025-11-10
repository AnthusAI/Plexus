#!/usr/bin/env python3
"""
Scorecard management tools for Plexus MCP server
"""
import os
import json
from io import StringIO
from typing import Union, List, Dict, Optional, Any
from fastmcp import FastMCP
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.setup import logger, create_dashboard_client, resolve_scorecard_identifier, resolve_account_identifier
from shared.utils import get_default_account_id

def register_scorecard_tools(mcp: FastMCP):
    """Register scorecard tools with the MCP server"""
    
    @mcp.tool()
    async def plexus_scorecards_list(
        identifier: Optional[str] = None, 
        limit: Optional[str] = None
    ) -> Union[str, List[Dict]]:
        """
        Lists scorecards from the Plexus Dashboard.
        
        Parameters:
        - identifier: Filter by scorecard name, key, ID, or external ID (optional)
        - limit: Maximum number of scorecards to return (optional)
        
        Returns:
        - A list of scorecards matching the filter criteria
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Convert parameters to proper types (MCP passes strings)
            limit_int = None
            if limit is not None:
                try:
                    limit_int = int(limit)
                    if limit_int < 1:
                        return f"Error: Invalid limit parameter: {limit}. Must be a positive number."
                except (ValueError, TypeError):
                    return f"Error: Invalid limit parameter: {limit}. Must be a number."
            
            # Try to import required modules directly
            try:
                from plexus.dashboard.api.client import PlexusDashboardClient
            except ImportError as e:
                return f"Error: Could not import required modules: {e}. Core modules may not be available."
            
            client = None
            
            # Check if we have the necessary credentials
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                logger.warning("Missing API credentials. Ensure .env file is loaded.")
                return "Error: Missing API credentials. Use --env-file to specify your .env file path."
            
            # Create the client directly
            try:
                # Create another stdout redirect just for client creation
                client_stdout = StringIO()
                saved_stdout = sys.stdout
                sys.stdout = client_stdout
                
                try:
                    client = PlexusDashboardClient(api_url=api_url, api_key=api_key)
                finally:
                    client_output = client_stdout.getvalue()
                    if client_output:
                        logger.warning(f"Captured unexpected stdout during client creation in list_plexus_scorecards: {client_output}")
                    sys.stdout = saved_stdout
            except Exception as client_err:
                logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
                return f"Error creating dashboard client: {str(client_err)}"
                
            if not client:
                return "Error: Could not create dashboard client."

            # Handle limit=None as fetching a large number (proxy for all)
            fetch_limit = limit_int if limit_int is not None else 1000 # Use 1000 if no limit specified

            filter_parts = []
            
            # Always use default account
            default_account_id = get_default_account_id()
            if default_account_id:
                filter_parts.append(f'accountId: {{ eq: "{default_account_id}" }}')
                logger.info("Using default account for scorecard listing")
            else:
                logger.warning("No default account ID available for filtering scorecards")
            
            # Handle specific scorecard filtering if identifier is provided
            if identifier:
                # First try to directly resolve the identifier to a scorecard ID
                try:
                    id_stdout = StringIO()
                    saved_stdout = sys.stdout
                    sys.stdout = id_stdout
                    
                    try:
                        scorecard_id = resolve_scorecard_identifier(client, identifier)
                        if scorecard_id:
                            # If we found a specific ID, just return that scorecard
                            query = f"""
                            query GetScorecard {{ 
                                getScorecard(id: "{scorecard_id}") {{
                                    id name key description externalId createdAt updatedAt 
                                }} 
                            }}
                            """
                            logger.info(f"Found exact scorecard match with ID: {scorecard_id}")
                            response = client.execute(query)
                            
                            if 'errors' in response:
                                error_details = json.dumps(response['errors'], indent=2)
                                logger.error(f"Dashboard query returned errors: {error_details}")
                                return f"Error from Dashboard query: {error_details}"
                            
                            scorecard_data = response.get('getScorecard')
                            if scorecard_data:
                                return [scorecard_data]
                            else:
                                logger.warning(f"Resolved scorecard ID {scorecard_id} but couldn't fetch details")
                    finally:
                        id_output = id_stdout.getvalue()
                        if id_output:
                            logger.warning(f"Captured unexpected stdout during scorecard ID resolution: {id_output}")
                        sys.stdout = saved_stdout
                except Exception as id_err:
                    logger.error(f"Error resolving scorecard ID for '{identifier}': {id_err}", exc_info=True)
                
                # If direct resolution failed, try flexible search terms
                # First check if it could be a name (contains spaces, proper case)
                if ' ' in identifier or not identifier.islower():
                    filter_parts.append(f'name: {{ contains: "{identifier}" }}')
                else:
                    # Otherwise use it as a general search term that could match name or key
                    filter_parts.append(f'or: [{{name: {{ contains: "{identifier}" }}}}, {{key: {{ contains: "{identifier}" }}}}]')

            filter_str = ", ".join(filter_parts)

            query = f"""
            query ListScorecards {{ listScorecards(filter: {{ {filter_str} }}, limit: {fetch_limit}) {{
                items {{ id name key description externalId createdAt updatedAt }} }} }}
            """
            logger.info(f"Executing Dashboard query (limit={fetch_limit})")
            
            # Execute query - this might raise exceptions or return error structures
            # Redirect again for the query execution
            query_stdout = StringIO()
            saved_stdout = sys.stdout
            sys.stdout = query_stdout
            
            try:
                response = client.execute(query)
                
                # Check for GraphQL errors within the response structure
                if 'errors' in response:
                    error_details = json.dumps(response['errors'], indent=2)
                    logger.error(f"Dashboard query returned errors: {error_details}")
                    return f"Error from Dashboard query: {error_details}"
        
                scorecards_data = response.get('listScorecards', {}).get('items', [])
        
                if not scorecards_data:
                    return "No scorecards found matching the criteria in the Plexus Dashboard."
        
                # Return raw data
                return scorecards_data
            finally:
                query_output = query_stdout.getvalue()
                if query_output:
                    logger.warning(f"Captured unexpected stdout during query execution: {query_output}")
                sys.stdout = saved_stdout
        except Exception as e:
            # Catch ANY exception during the process (client creation, query execution, etc.)
            logger.error(f"Error listing dashboard scorecards: {str(e)}", exc_info=True)
            return f"Error listing dashboard scorecards: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during list_plexus_scorecards: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_scorecard_info(scorecard_identifier: str) -> Union[str, Dict[str, Any]]:
        """
        Gets detailed information about a specific scorecard, including its sections and scores.
        
        Parameters:
        - scorecard_identifier: The identifier for the scorecard (can be ID, name, key, or external ID)
        
        Returns:
        - Detailed information about the scorecard
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Import plexus CLI inside function to keep startup fast
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
                from plexus.cli.scorecard.scorecards import resolve_scorecard_identifier
                from plexus.dashboard.api.client import PlexusDashboardClient
            except ImportError as e:
                logger.error(f"ImportError: {str(e)}", exc_info=True)
                return f"Error: Failed to import Plexus modules: {str(e)}"

            # Check if we have the necessary credentials
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                logger.warning("Missing API credentials. Ensure .env file is loaded.")
                return "Error: Missing API credentials. Use --env-file to specify your .env file path."
            
            # Get the scorecard details - use functions directly instead of through a CLI object
            client = create_dashboard_client()
            if not client:
                return "Error: Could not create dashboard client."

            # Resolve the scorecard identifier
            scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
            if not scorecard_id:
                return f"Error: Scorecard '{scorecard_identifier}' not found in Dashboard."

            # Fetch the scorecard with sections and scores
            query = f"""
            query GetScorecard {{
                getScorecard(id: "{scorecard_id}") {{
                    id
                    name
                    key
                    description
                    guidelines
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
            logger.info(f"Executing Dashboard query for scorecard ID: {scorecard_id}")
            response = client.execute(query)

            if 'errors' in response:
                error_details = json.dumps(response['errors'], indent=2)
                logger.error(f"Dashboard query for scorecard info returned errors: {error_details}")
                return f"Error from Dashboard query for scorecard info: {error_details}"

            scorecard_data = response.get('getScorecard')
            if not scorecard_data:
                return f"Error: Scorecard with ID '{scorecard_id}' (resolved from '{scorecard_identifier}') not found after query."

            # Restructure the output to prioritize key info and nest less frequently needed details
            formatted_output = {
                "name": scorecard_data.get("name"),
                "key": scorecard_data.get("key"),
                "externalId": scorecard_data.get("externalId"),
                "description": scorecard_data.get("description"),
                "guidelines": scorecard_data.get("guidelines"),
                "additionalDetails": {
                    "id": scorecard_data.get("id"),
                    "createdAt": scorecard_data.get("createdAt"),
                    "updatedAt": scorecard_data.get("updatedAt"),
                },
                "sections": scorecard_data.get("sections") # Keep full sections/scores structure
            }
            return formatted_output

        except Exception as e:
            logger.error(f"Error getting scorecard info for '{scorecard_identifier}': {str(e)}", exc_info=True)
            return f"Error getting scorecard info: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during get_plexus_scorecard_info: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_scorecard_create(
        name: str,
        account_identifier: str,
        key: Optional[str] = None,
        external_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Creates a new scorecard in the specified account.
        
        Parameters:
        - name: Display name for the scorecard (required)
        - account_identifier: Identifier for the account (ID, name, key, or external ID) (required)
        - key: Unique key for the scorecard. If not provided, generates from name
        - external_id: External ID for the scorecard. If not provided, generates a unique ID
        - description: Optional description for the scorecard
        
        Returns:
        - Information about the created scorecard including its ID and dashboard URL
        """
        import re
        import uuid
        
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Validate required parameters
            if not name or not name.strip():
                return "Error: name is required and cannot be empty"
            
            if not account_identifier or not account_identifier.strip():
                return "Error: account_identifier is required and cannot be empty"
            
            # Auto-generate key from name if not provided
            if not key:
                # Convert name to snake_case key
                key = re.sub(r'[^a-zA-Z0-9]+', '_', name.strip().lower()).strip('_')
                if not key:
                    key = "scorecard_" + str(uuid.uuid4()).replace('-', '')[:8]
            
            # Auto-generate external_id if not provided
            if not external_id:
                external_id = f"scorecard_{str(uuid.uuid4()).replace('-', '')[:8]}"
            
            # Try to import required modules
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
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
            client = create_dashboard_client()
            if not client:
                return "Error: Could not create Dashboard client."
            
            # Resolve the account ID - if account_identifier is provided, use it; otherwise use default
            if account_identifier.lower() == 'default':
                account_id = resolve_account_id_for_command(client, None)  # Use default account
            else:
                # For now, we'll use the CLI scorecard function for other account identifiers
                try:
                    from plexus.cli.scorecard.scorecards import resolve_account_identifier
                    account_id = resolve_account_identifier(client, account_identifier)
                except ImportError:
                    return f"Error: Could not import account resolution function for identifier: {account_identifier}"
            
            if not account_id:
                return f"Error: Could not resolve account identifier: {account_identifier}"
            
            # Build and execute the GraphQL mutation
            mutation = f"""
            mutation CreateScorecard {{
                createScorecard(input: {{
                    name: "{name}"
                    key: "{key}"
                    externalId: "{external_id}"
                    accountId: "{account_id}"
                    description: "{description or ''}"
                }}) {{
                    id
                    name
                    key
                    externalId
                    description
                    accountId
                    createdAt
                    updatedAt
                }}
            }}
            """
            
            logger.info(f"Executing createScorecard mutation for name: {name}")
            result = client.execute(mutation)
            
            if not result or 'createScorecard' not in result:
                return f"Error: Failed to create scorecard '{name}'. No response from server."
            
            created_scorecard = result['createScorecard']
            if not created_scorecard:
                return f"Error: Failed to create scorecard '{name}'. Mutation returned null."
            
            scorecard_id = created_scorecard.get('id')
            if not scorecard_id:
                return f"Error: Failed to create scorecard '{name}'. No ID returned."

            # Create a default section for the scorecard
            section_mutation = f"""
            mutation CreateSection {{
                createScorecardSection(input: {{
                    scorecardId: "{scorecard_id}"
                    name: "Default"
                    order: 0
                }}) {{
                    id
                    name
                    order
                }}
            }}
            """

            logger.info(f"Creating default section for scorecard: {scorecard_id}")
            section_result = client.execute(section_mutation)

            section_created = False
            section_id = None
            if section_result and 'createScorecardSection' in section_result:
                section_data = section_result['createScorecardSection']
                if section_data:
                    section_id = section_data.get('id')
                    section_created = True
                    logger.info(f"Created default section with ID: {section_id}")
                else:
                    logger.warning(f"Section creation returned null for scorecard {scorecard_id}")
            else:
                logger.warning(f"No section creation response for scorecard {scorecard_id}")

            # Generate dashboard URL
            dashboard_url = f"https://plexus.anth.us/lab/scorecards/{scorecard_id}"

            # Return structured success response
            return {
                "success": True,
                "scorecardId": scorecard_id,
                "scorecardName": created_scorecard.get('name', name),
                "scorecardKey": created_scorecard.get('key', key),
                "externalId": created_scorecard.get('externalId', external_id),
                "description": created_scorecard.get('description', description or ''),
                "accountId": created_scorecard.get('accountId', account_id),
                "createdAt": created_scorecard.get('createdAt'),
                "dashboardUrl": dashboard_url,
                "defaultSectionCreated": section_created,
                "defaultSectionId": section_id
            }
            
        except Exception as e:
            logger.error(f"Error creating scorecard: {str(e)}", exc_info=True)
            return f"Error creating scorecard: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during plexus_scorecard_create: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_scorecard_update(
        scorecard_id: str,
        name: Optional[str] = None,
        key: Optional[str] = None,
        external_id: Optional[str] = None,
        description: Optional[str] = None,
        guidelines: Optional[str] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Updates metadata properties of an existing scorecard.
        
        Parameters:
        - scorecard_id: The ID of the scorecard to update (required)
        - name: New display name for the scorecard
        - key: New unique key for the scorecard
        - external_id: New external ID for the scorecard
        - description: New description for the scorecard
        - guidelines: New guidelines content for the scorecard (Markdown format)
        
        Returns:
        - Information about the updated scorecard and what fields were changed
        """
        import re
        
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Validate required parameters
            if not scorecard_id or not scorecard_id.strip():
                return "Error: scorecard_id is required and cannot be empty"
            
            # Validate that at least one update field is provided
            update_fields = {
                'name': name,
                'key': key,
                'externalId': external_id,
                'description': description,
                'guidelines': guidelines
            }
            provided_updates = {k: v for k, v in update_fields.items() if v is not None}
            
            if not provided_updates:
                return "Error: At least one field to update must be provided"
            
            # Validate field values
            if name is not None and not name.strip():
                return "Error: name cannot be empty when provided"
            
            if key is not None and not key.strip():
                return "Error: key cannot be empty when provided"
            
            # Try to import required modules
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
                from plexus.cli.shared.memoized_resolvers import memoized_resolve_scorecard_identifier
            except ImportError as e:
                return f"Error: Could not import required modules: {e}. Core modules may not be available."
            
            # Check if we have the necessary credentials
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                logger.warning("Missing API credentials. Ensure .env file is loaded.")
                return "Error: Missing API credentials. Use --env-file to specify your .env file path."
            
            # Create the client
            client = create_dashboard_client()
            if not client:
                return "Error: Could not create Dashboard client."
            
            # Resolve the scorecard ID (supports ID, name, key, external ID)
            resolved_scorecard_id = memoized_resolve_scorecard_identifier(client, scorecard_id)
            if not resolved_scorecard_id:
                return f"Error: Could not resolve scorecard identifier: {scorecard_id}"
            
            # Build the update fields for GraphQL
            update_input = {"id": resolved_scorecard_id}
            changed_fields = []
            
            if name is not None:
                update_input["name"] = name
                changed_fields.append("name")
            
            if key is not None:
                update_input["key"] = key
                changed_fields.append("key")
                
            if external_id is not None:
                update_input["externalId"] = external_id
                changed_fields.append("externalId")
                
            if description is not None:
                update_input["description"] = description
                changed_fields.append("description")
                
            if guidelines is not None:
                update_input["guidelines"] = guidelines
                changed_fields.append("guidelines")
            
            # Build and execute the GraphQL mutation
            # Create the input fields string for the mutation
            input_fields = []
            for field, value in update_input.items():
                if field != "id":  # ID is handled separately
                    input_fields.append(f'{field}: "{value}"')
            
            input_fields_str = ", ".join(input_fields)
            
            mutation = f"""
            mutation UpdateScorecard {{
                updateScorecard(input: {{
                    id: "{resolved_scorecard_id}"
                    {input_fields_str}
                }}) {{
                    id
                    name
                    key
                    externalId
                    description
                    guidelines
                    updatedAt
                }}
            }}
            """
            
            logger.info(f"Executing updateScorecard mutation for ID: {resolved_scorecard_id}")
            result = client.execute(mutation)
            
            if not result or 'updateScorecard' not in result:
                return f"Error: Failed to update scorecard with ID '{resolved_scorecard_id}'. No response from server."
            
            updated_scorecard = result['updateScorecard']
            if not updated_scorecard:
                return f"Error: Failed to update scorecard with ID '{resolved_scorecard_id}'. Mutation returned null."
            
            # Generate dashboard URL
            dashboard_url = f"https://plexus.anth.us/lab/scorecards/{resolved_scorecard_id}"
            
            # Build the response with changed fields
            updated_fields = {}
            for field in changed_fields:
                if field == 'externalId':
                    updated_fields[field] = updated_scorecard.get('externalId')
                else:
                    updated_fields[field] = updated_scorecard.get(field)
            
            # Return structured success response
            return {
                "success": True,
                "scorecardId": resolved_scorecard_id,
                "scorecardName": updated_scorecard.get('name'),
                "updatedFields": updated_fields,
                "updatedAt": updated_scorecard.get('updatedAt'),
                "dashboardUrl": dashboard_url
            }
            
        except Exception as e:
            logger.error(f"Error updating scorecard: {str(e)}", exc_info=True)
            return f"Error updating scorecard: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during plexus_scorecard_update: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout