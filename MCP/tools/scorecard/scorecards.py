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

from shared.setup import logger, create_dashboard_client, resolve_scorecard_identifier
from shared.utils import get_default_account_id

def register_scorecard_tools(mcp: FastMCP):
    """Register scorecard tools with the MCP server"""
    
    @mcp.tool()
    async def plexus_scorecards_list(
        identifier: Optional[str] = None, 
        limit: Optional[int] = None
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
            fetch_limit = limit if limit is not None else 1000 # Use 1000 if no limit specified

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
                from plexus.cli.client_utils import create_client as create_dashboard_client
                from plexus.cli.ScorecardCommands import resolve_scorecard_identifier
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
    async def run_plexus_evaluation(
        scorecard_name: str = "",
        score_name: str = "",
        n_samples: int = 10,
        ctx = None # Context is not used in this simplified background version
    ) -> str:
        """
        Dispatches a Plexus scorecard evaluation to run in the background.
        The server does not track the status of this background process.
        
        Parameters:
        - scorecard_name: The name of the scorecard to evaluate (e.g., 'CMG - EDU v1.0')
        - score_name: The name of the specific score to evaluate (e.g., 'Pain Points')
        - n_samples: Number of samples to evaluate
        
        Returns:
        - A string confirming the evaluation has been dispatched.
        """
        import sys
        import asyncio
        import subprocess
        # Validate inputs
        if not scorecard_name:
            return "Error: scorecard_name must be provided"

        async def _run_evaluation_in_background():
            """Helper to run the CLI command in the background and log basic info."""
            try:
                import importlib.util
                
                python_executable = sys.executable
                plexus_spec = importlib.util.find_spec("plexus")
                if not plexus_spec:
                    logger.error("Plexus module not found in Python path for background evaluation.")
                    return
                    
                plexus_dir = os.path.dirname(plexus_spec.origin)
                cli_dir = os.path.join(plexus_dir, "cli")
                cli_script = os.path.join(cli_dir, "CommandLineInterface.py")
                
                if not os.path.isfile(cli_script):
                    logger.error(f"CommandLineInterface.py not found at {cli_script} for background evaluation.")
                    return
                    
                eval_cmd_str = f"evaluate accuracy --scorecard-name '{scorecard_name}'"
                if score_name:
                    eval_cmd_str += f" --score-name '{score_name}'"
                eval_cmd_str += f" --number-of-samples {n_samples}"
                
                cmd_list = [python_executable, cli_script, "command", "dispatch", eval_cmd_str]
                cmd_log_str = ' '.join(cmd_list)
                logger.info(f"Dispatching background evaluation command: {cmd_log_str}")
                
                env = os.environ.copy()
                if "AWS_DEFAULT_REGION" not in env:
                    env["AWS_DEFAULT_REGION"] = "us-west-2"
                    logger.info("Setting AWS_DEFAULT_REGION=us-west-2 for background evaluation command")
                
                # Launch the process in the background
                # We are not capturing stdout/stderr here for simplicity, assuming the CLI script handles its own logging.
                # The Popen object is not awaited, so it runs in the background.
                process = await asyncio.create_subprocess_exec(
                    *cmd_list,
                    env=env,
                    stdout=subprocess.DEVNULL, # Prevent output from interfering if not handled by CLI
                    stderr=subprocess.DEVNULL  # Prevent output from interfering if not handled by CLI
                )
                
                logger.info(f"Background evaluation process started (PID: {process.pid}) for scorecard: {scorecard_name}")
                # We don't wait for completion: await process.wait()

            except Exception as e:
                logger.error(f"Error launching background evaluation for {scorecard_name}: {str(e)}", exc_info=True)

        # Create an asyncio task to run the helper function in the background
        asyncio.create_task(_run_evaluation_in_background())
        
        return (f"Plexus evaluation for scorecard '{scorecard_name}' has been dispatched to run in the background. "
                f"Monitor logs or Plexus Dashboard for status and results.")