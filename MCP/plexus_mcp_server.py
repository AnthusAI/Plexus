#!/usr/bin/env python3
import os
import sys
import json
import asyncio
import logging
import argparse
from typing import Dict, Any, List, Union, Optional
from io import StringIO

# Temporarily capture stdout during module imports
original_stdout = sys.stdout
temp_stdout = StringIO()
sys.stdout = temp_stdout

# Safety measure: Monkey patch builtins.print to always use stderr
# This prevents any imported libraries from accidentally writing to stdout
original_print = print
def safe_print(*args, **kwargs):
    # If file is explicitly set, honor it; otherwise, force stderr
    if 'file' not in kwargs:
        kwargs['file'] = sys.stderr
    return original_print(*args, **kwargs)
print = safe_print

# Create a custom ArgumentParser that writes to stderr
class StderrArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that writes all output to stderr instead of stdout."""
    def _print_message(self, message, file=None):
        if message:
            if file is None:
                file = sys.stderr
            file.write(message)
    
    def exit(self, status=0, message=None):
        if message:
            self._print_message(message, sys.stderr)
        sys.exit(status)

# Configure root logger EARLY and definitively to stderr
# This should happen before any other module (like Plexus) tries to configure logging
log_level_main = logging.DEBUG if os.environ.get("MCP_DEBUG") else logging.INFO
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler) # Remove any pre-existing handlers
stderr_handler_main = logging.StreamHandler(sys.stderr)
stderr_handler_main.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.root.addHandler(stderr_handler_main)
logging.root.setLevel(log_level_main)

# Get the logger for this module AFTER root configuration
logger = logging.getLogger("plexus_mcp_server_lib")

try:
    # Use mcp.server library components
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent

    # --- Plexus Core Imports & Setup ---
    # Add Plexus project root to Python path if necessary
    plexus_root = os.path.dirname(os.path.abspath(__file__))
    if plexus_root not in sys.path:
        sys.path.append(plexus_root)
    # Also add parent if running from within Plexus directory structure
    parent_dir = os.path.dirname(plexus_root)
    if parent_dir not in sys.path:
         sys.path.append(parent_dir)

    # Initialize flags/dummies first
    PLEXUS_CORE_AVAILABLE = False
    def create_dashboard_client(): return None
    def resolve_account_identifier(client, identifier): return None
    def resolve_scorecard_identifier(client, identifier): return None

    try:
        # Attempt to import Plexus modules for core functionality
        # Plexus logging setup might conflict, rely on our root logger setup above
        # from plexus.CustomLogging import setup_logging, set_log_group 
        # setup_logging() # Avoid calling this if it might hijack stdout
        from plexus.dashboard.api.client import PlexusDashboardClient
        # Assign imported functions to pre-defined names
        from plexus.cli.ScorecardCommands import create_client as _create_dashboard_client, resolve_account_identifier as _resolve_account_identifier
        from plexus.cli.identifier_resolution import resolve_scorecard_identifier as _resolve_scorecard_identifier
        create_dashboard_client = _create_dashboard_client
        resolve_account_identifier = _resolve_account_identifier
        resolve_scorecard_identifier = _resolve_scorecard_identifier
        PLEXUS_CORE_AVAILABLE = True
        logger.info("Plexus core modules imported successfully.")
        # Try setting log group if function exists, but don't rely on setup_logging
        # try:
        #     from plexus.CustomLogging import set_log_group
        #     set_log_group('plexus/mcp_server')
        # except Exception as log_group_err:
        #     logger.warning(f"Could not set log group: {log_group_err}")
    except ImportError as e:
        logger.warning(f"Could not import core Plexus modules: {e}. Dashboard features will be unavailable.")
        # Dummies are already defined, PLEXUS_CORE_AVAILABLE is already False
    except Exception as import_err:
        # Catch other potential errors during import/setup
        logger.error(f"Error during Plexus core module import/setup: {import_err}", exc_info=True)
        PLEXUS_CORE_AVAILABLE = False
        
    # Check for and log any accidental stdout output from imports
    stdout_captured = temp_stdout.getvalue()
    if stdout_captured:
        logger.warning(f"Captured unexpected stdout output during imports: {stdout_captured}")
    
    # Restore stdout for proper JSON-RPC communication
    sys.stdout = original_stdout
except Exception as e:
    # Ensure stdout is restored in case of exception
    sys.stdout = original_stdout
    logger.error(f"Error during initialization: {e}", exc_info=True)
    raise

# --- Tool Implementation Functions (Plexus) ---

def list_dashboard_scorecards(account=None, name=None, key=None, limit: Optional[int] = None) -> Union[str, List[Dict]]:
    """ Fetches scorecards from dashboard, capturing errors cleanly. """
    if not PLEXUS_CORE_AVAILABLE:
        return "Error: Plexus Dashboard components not available (Plexus core modules failed to import)."
    
    client = None # Initialize client to None
    try:
        # Check if we have the necessary credentials
        api_url = os.environ.get('PLEXUS_API_URL', '')
        api_key = os.environ.get('PLEXUS_API_KEY', '')
        
        if not api_url or not api_key:
            logger.warning("Missing API credentials. Ensure .env file is loaded.")
            return "Error: Missing API credentials. Use --env-file to specify your .env file path."
        
        # Create the client directly
        from plexus.dashboard.api.client import PlexusDashboardClient
        client = PlexusDashboardClient(api_url=api_url, api_key=api_key)
            
        if not client:
            return "Error: Could not create dashboard client."

        # Handle limit=None as fetching a large number (proxy for all)
        fetch_limit = limit if limit is not None else 1000 # Use 1000 if no limit specified

        filter_parts = []
        if account:
            # Wrap resolver call in try/except if it might also print tracebacks
            try:
                account_id = resolve_account_identifier(client, account)
                if not account_id:
                    return f"Error: Account '{account}' not found in Dashboard."
                filter_parts.append(f'accountId: {{ eq: "{account_id}" }}')
            except Exception as acc_res_err:
                 logger.error(f"Error resolving account '{account}': {acc_res_err}", exc_info=True)
                 return f"Error resolving account '{account}'."
        if name:
            filter_parts.append(f'name: {{ contains: "{name}" }}')
        if key:
            filter_parts.append(f'key: {{ contains: "{key}" }}')
        filter_str = ", ".join(filter_parts)

        query = f"""
        query ListScorecards {{ listScorecards(filter: {{ {filter_str} }}, limit: {fetch_limit}) {{
            items {{ id name key description externalId createdAt updatedAt }} }} }}
        """
        logger.info(f"Executing Dashboard query (limit={fetch_limit})")
        # Execute query - this might raise exceptions or return error structures
        response = client.execute(query)
        
        # Check for GraphQL errors within the response structure
        if 'errors' in response:
             error_details = json.dumps(response['errors'], indent=2)
             logger.error(f"Dashboard query returned errors: {error_details}")
             return f"Error from Dashboard query: {error_details}" # Return clean error

        scorecards_data = response.get('listScorecards', {}).get('items', [])

        if not scorecards_data:
            return "No scorecards found matching the criteria in the Plexus Dashboard."

        # Return raw data for executeTool
        return scorecards_data

    except Exception as e:
        # Catch ANY exception during the process (client creation, query execution, etc.)
        # Log it cleanly using our logger (which goes to stderr)
        logger.error(f"Error listing dashboard scorecards: {str(e)}", exc_info=True)
        # Return a simple error string, preventing tracebacks on stdout
        return f"Error listing dashboard scorecards: An internal error occurred. Check server logs for details."

def get_scorecard_info_impl(scorecard_identifier: str) -> Union[str, Dict[str, Any]]:
    """ Fetches detailed information for a specific scorecard from the dashboard. """
    if not PLEXUS_CORE_AVAILABLE:
        return "Error: Plexus Dashboard components not available (Plexus core modules failed to import)."

    client = None
    try:
        api_url = os.environ.get('PLEXUS_API_URL', '')
        api_key = os.environ.get('PLEXUS_API_KEY', '')

        if not api_url or not api_key:
            logger.warning("Missing API credentials for get_scorecard_info. Ensure .env file is loaded.")
            return "Error: Missing API credentials. Use --env-file to specify your .env file path."

        from plexus.dashboard.api.client import PlexusDashboardClient
        client = PlexusDashboardClient(api_url=api_url, api_key=api_key)

        if not client:
            return "Error: Could not create dashboard client for get_scorecard_info."

        # Resolve the scorecard identifier
        actual_scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
        if not actual_scorecard_id:
            return f"Error: Scorecard '{scorecard_identifier}' not found in Dashboard."

        # Fetch the scorecard with sections and scores
        query = f"""
        query GetScorecard {{
            getScorecard(id: "{actual_scorecard_id}") {{
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
        logger.info(f"Executing Dashboard query for scorecard ID: {actual_scorecard_id}")
        response = client.execute(query)

        if 'errors' in response:
            error_details = json.dumps(response['errors'], indent=2)
            logger.error(f"Dashboard query for scorecard info returned errors: {error_details}")
            return f"Error from Dashboard query for scorecard info: {error_details}"

        scorecard_data = response.get('getScorecard')
        if not scorecard_data:
            return f"Error: Scorecard with ID '{actual_scorecard_id}' (resolved from '{scorecard_identifier}') not found after query."

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
        return f"Error getting scorecard info: An internal error occurred. Check server logs for details."

def get_score_details_impl(scorecard_identifier: str, score_identifier: str, version_id: Optional[str] = None) -> Union[str, Dict[str, Any]]:
    """ Fetches detailed information for a specific score, including its versions and configuration. """
    if not PLEXUS_CORE_AVAILABLE:
        return "Error: Plexus Dashboard components not available (Plexus core modules failed to import)."

    client = None
    try:
        api_url = os.environ.get('PLEXUS_API_URL', '')
        api_key = os.environ.get('PLEXUS_API_KEY', '')

        if not api_url or not api_key:
            logger.warning("Missing API credentials for get_score_details. Ensure .env file is loaded.")
            return "Error: Missing API credentials for get_score_details."

        from plexus.dashboard.api.client import PlexusDashboardClient
        client = PlexusDashboardClient(api_url=api_url, api_key=api_key)

        if not client:
            return "Error: Could not create dashboard client for get_score_details."

        # 1. Resolve scorecard_identifier to scorecard_id
        actual_scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
        if not actual_scorecard_id:
            return f"Error: Scorecard '{scorecard_identifier}' not found."

        # 2. Fetch scorecard to find the score_id and its details (including championVersionId)
        scorecard_query = f"""
        query GetScorecardForScoreResolution {{
            getScorecard(id: "{actual_scorecard_id}") {{
                id
                name
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
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        logger.debug(f"Fetching scorecard '{actual_scorecard_id}' to resolve score '{score_identifier}'")
        scorecard_response = client.execute(scorecard_query)
        if 'errors' in scorecard_response:
            return f"Error fetching scorecard details for score resolution: {json.dumps(scorecard_response['errors'])}"
        
        scorecard_data = scorecard_response.get('getScorecard')
        if not scorecard_data:
            return f"Error: Scorecard '{actual_scorecard_id}' data not found after query."

        found_score_details = None
        for section in scorecard_data.get('sections', {}).get('items', []):
            for s_item in section.get('scores', {}).get('items', []):
                if (s_item.get('id') == score_identifier or 
                    s_item.get('key') == score_identifier or 
                    s_item.get("name") == score_identifier or 
                    s_item.get("externalId") == score_identifier):
                    found_score_details = s_item
                    break
            if found_score_details:
                break
        
        if not found_score_details:
            return f"Error: Score '{score_identifier}' not found within scorecard '{scorecard_identifier} (ID: {actual_scorecard_id})'."

        actual_score_id = found_score_details.get('id')
        champion_version_id_from_score = found_score_details.get('championVersionId')

        # 3. Fetch all versions for the identified score
        score_versions_query = f"""
        query GetScoreVersions {{
            getScore(id: "{actual_score_id}") {{
                id
                name
                key
                externalId
                championVersionId # Confirm champion ID at score level
                versions(sortDirection: DESC, limit: 50) {{ # Get a decent number of recent versions
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
        logger.info(f"Fetching versions for score ID: {actual_score_id}")
        versions_response = client.execute(score_versions_query)

        if 'errors' in versions_response:
            error_details = json.dumps(versions_response['errors'], indent=2)
            logger.error(f"Dashboard query for score versions returned errors: {error_details}")
            return f"Error from Dashboard query for score versions: {error_details}"

        score_data_with_versions = versions_response.get('getScore')
        if not score_data_with_versions:
            return f"Error: Score data with versions for ID '{actual_score_id}' not found."

        all_versions = score_data_with_versions.get('versions', {}).get('items', [])
        if not all_versions:
            return f"No versions found for score '{score_identifier}' (ID: {actual_score_id})."

        target_version_data = None
        if version_id:
            # User specified a version_id
            for v in all_versions:
                if v.get('id') == version_id:
                    target_version_data = v
                    break
            if not target_version_data:
                return f"Error: Specified version ID '{version_id}' not found for score '{actual_score_id}'."
        else:
            # No specific version_id, try champion, then most recent
            effective_champion_id = score_data_with_versions.get('championVersionId') or champion_version_id_from_score
            if effective_champion_id:
                for v in all_versions:
                    if v.get('id') == effective_champion_id:
                        target_version_data = v
                        break
            if not target_version_data and all_versions: # Fallback to most recent if champion not found or not set
                target_version_data = all_versions[0] # Assumes versions are sorted DESC by createdAt
        
        if not target_version_data:
            return f"Could not determine target version for score '{actual_score_id}'."

        # Return the full score details along with all its versions, and specifically the target version's config
        # The main structure is the score itself, with a list of all its versions,
        # and a special field for the configuration of the version we targeted.
        output = {
            "scoreId": score_data_with_versions.get("id"),
            "scoreName": score_data_with_versions.get("name"),
            "scoreKey": score_data_with_versions.get("key"),
            "scoreExternalId": score_data_with_versions.get("externalId"),
            "currentChampionVersionId": score_data_with_versions.get("championVersionId"),
            "targetedVersionDetails": target_version_data, # This includes the configuration string
            "allVersions": all_versions # List of all version metadata (config included in each)
        }
        return output

    except Exception as e:
        logger.error(f"Error getting score details for scorecard '{scorecard_identifier}', score '{score_identifier}': {str(e)}", exc_info=True)
        return f"Error getting score details: An internal error occurred. Check server logs for details."

# --- Report Tool Implementations ---

def list_plexus_reports_impl(account_identifier: Optional[str] = None, report_configuration_id: Optional[str] = None, limit: Optional[int] = 10) -> Union[str, List[Dict]]:
    """ Lists reports, optionally filtered by account or report configuration. """
    if not PLEXUS_CORE_AVAILABLE:
        return "Error: Plexus Dashboard components not available."
    client = create_dashboard_client()
    if not client: return "Error: Could not create dashboard client."

    filter_conditions = []
    if account_identifier:
        actual_account_id = resolve_account_identifier(client, account_identifier)
        if not actual_account_id:
            return f"Error: Account '{account_identifier}' not found."
        filter_conditions.append(f'accountId: {{eq: "{actual_account_id}"}}')
    if report_configuration_id:
        filter_conditions.append(f'reportConfigurationId: {{eq: "{report_configuration_id}"}}')
    
    filter_string = ", ".join(filter_conditions)
    limit_val = limit if limit is not None else 10

    # Note: The listReports GQL schema might not directly support a sortField parameter.
    # We rely on sortDirection applying to a relevant field like createdAt or a GSI.
    # For reports, GSIs on (accountId, updatedAt) and (reportConfigurationId, createdAt) exist.
    # If report_configuration_id is given, sorting by createdAt is effective.
    # If only accountId is given, sorting by updatedAt is effective.
    # If neither, default AppSync sorting applies (often by ID, or primary index sort key if defined).
    # For consistency with 'latest', we use DESC.
    query = f"""
    query ListReports {{
        listReports(filter: {{ {filter_string} }}, limit: {limit_val}, sortDirection: DESC) {{
            items {{
                id
                name
                createdAt
                updatedAt
                reportConfigurationId
                accountId
                taskId
            }}
        }}
    }}
    """
    
    try:
        logger.info(f"Executing listReports query: {query}")
        response = client.execute(query_string=query) # client.execute should handle GQL string directly
        
        if response.get('errors'):
             error_details = json.dumps(response['errors'], indent=2)
             logger.error(f"listReports query returned errors: {error_details}")
             return f"Error from listReports query: {error_details}"
        
        reports_data = response.get('listReports', {}).get('items', [])
        if not reports_data and not filter_string: # Only show general message if no filters applied
            return "No reports found."
        elif not reports_data:
            return "No reports found matching the criteria."
        return reports_data
    except Exception as e:
        logger.error(f"Error listing reports: {str(e)}", exc_info=True)
        return "Error listing reports: An internal error occurred."

def get_plexus_report_details_impl(report_id: str) -> Union[str, Dict[str, Any]]:
    """ Fetches detailed information for a specific report, including its blocks. """
    if not PLEXUS_CORE_AVAILABLE: return "Error: Plexus Dashboard components not available."
    client = create_dashboard_client()
    if not client: return "Error: Could not create dashboard client."

    query = f"""
    query GetReport {{
        getReport(id: "{report_id}") {{
            id
            name
            createdAt
            updatedAt
            parameters
            output # Original markdown template
            accountId
            reportConfigurationId
            taskId
            reportBlocks {{
                items {{
                    id
                    reportId
                    name
                    position
                    type
                    output # JSON output from block
                    log
                    createdAt
                    updatedAt
                }}
            }}
        }}
    }}
    """
    try:
        logger.info(f"Executing getReport query for ID: {report_id}")
        response = client.execute(query_string=query)

        if response.get('errors'):
            error_details = json.dumps(response['errors'], indent=2)
            logger.error(f"getReport query returned errors: {error_details}")
            return f"Error from getReport query: {error_details}"

        report_data = response.get('getReport')
        if not report_data:
            return f"Error: Report with ID '{report_id}' not found."
        return report_data
    except Exception as e:
        logger.error(f"Error getting report details for ID '{report_id}': {str(e)}", exc_info=True)
        return f"Error getting report details: An internal error occurred."

def get_latest_plexus_report_impl(account_identifier: Optional[str] = None, report_configuration_id: Optional[str] = None) -> Union[str, Dict[str, Any]]:
    """ Fetches details for the most recent report, optionally filtered. """
    # First, list reports to find the latest one's ID
    # list_plexus_reports_impl already sorts DESC by default relevant field implicitly or via GSI behavior
    latest_report_list_response = list_plexus_reports_impl(account_identifier=account_identifier, report_configuration_id=report_configuration_id, limit=1)

    if isinstance(latest_report_list_response, str) and latest_report_list_response.startswith("Error:"):
        # Pass through error from list_plexus_reports_impl
        return latest_report_list_response 
    if not latest_report_list_response or not isinstance(latest_report_list_response, list) or not latest_report_list_response[0]:
        # Handle cases where list_plexus_reports_impl returns "No reports found..." string or empty list
        if isinstance(latest_report_list_response, str): 
            return latest_report_list_response # Return the message like "No reports found..."
        return "No reports found to determine the latest one, or list_plexus_reports_impl returned an unexpected type."
    
    latest_report_id = latest_report_list_response[0].get('id')
    if not latest_report_id:
        return "Error: Could not extract ID from the latest report found by list_plexus_reports_impl."
    
    logger.info(f"Latest report ID found: {latest_report_id}. Fetching details...")
    return get_plexus_report_details_impl(report_id=latest_report_id)

def run_plexus_evaluation(scorecard_name=None, score_name=None, n_samples=10) -> str:
    """Run a Plexus evaluation using the direct CLI script approach."""
    logger.info(f"Running Plexus evaluation: scorecard_name={scorecard_name}, score_name={score_name}, n_samples={n_samples}")
    
    try:
        import subprocess
        import os
        import importlib.util
        
        # Validate parameters
        if not scorecard_name:
            return "Error: scorecard_name must be provided."
            
        # Get Python executable path
        python_executable = sys.executable
        
        # Find the Plexus CLI CommandLineInterface.py script
        plexus_spec = importlib.util.find_spec("plexus")
        if not plexus_spec:
            return "Error: Plexus module not found in Python path."
            
        plexus_dir = os.path.dirname(plexus_spec.origin)
        cli_dir = os.path.join(plexus_dir, "cli")
        cli_script = os.path.join(cli_dir, "CommandLineInterface.py")
        
        if not os.path.isfile(cli_script):
            return f"Error: CommandLineInterface.py not found at {cli_script}"
        
        # First, construct the evaluation command as a single string
        # Make sure values with spaces are properly quoted
        eval_cmd = "evaluate accuracy"
        eval_cmd += f" --scorecard-name \"{scorecard_name.replace('\"', '\\\"')}\""
        
        if score_name:
            eval_cmd += f" --score-name \"{score_name.replace('\"', '\\\"')}\""
            
        eval_cmd += f" --number-of-samples {n_samples}"
        
        # Then build the full command list, passing the evaluation command as a single argument
        cmd_list = [
            python_executable,
            cli_script,
            "command", "dispatch",
            eval_cmd  # The entire evaluation command as a single argument
        ]
        
        # Log the command for debugging
        cmd_str = ' '.join(cmd_list)  # Simple space-joined string
        cmd_repr = ' '.join(repr(arg) for arg in cmd_list)  # With proper quoting
        logger.info(f"Executing command: {cmd_str}")
        logger.info(f"Command with proper quoting: {cmd_repr}")
        logger.info(f"Evaluation command portion: {eval_cmd}")
        
        # Set environment variables including AWS region
        env = os.environ.copy()
        if "AWS_DEFAULT_REGION" not in env:
            env["AWS_DEFAULT_REGION"] = "us-west-2"
            logger.info("Setting AWS_DEFAULT_REGION=us-west-2")
            
        # Execute the command
        process = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,  # Important: set to False for proper argument handling
            env=env,
            text=True,
            cwd=os.getcwd()  # Use current working directory
        )
        
        # Wait for the command to complete with a timeout
        try:
            stdout, stderr = process.communicate(timeout=60)
            return_code = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return "Error: Command execution timed out after 60 seconds."
            
        # Check return code and format response
        if return_code == 0:
            result = "Plexus evaluation dispatch successful!\n\n"
            result += f"Command: {cmd_str}\n"
            result += f"Scorecard: {scorecard_name}\n"
            if score_name:
                result += f"Score: {score_name}\n"
            result += f"Samples: {n_samples}\n\n"
            
            if stdout.strip():
                result += "Output:\n" + stdout
                
            if "Finished processing items" in stdout:
                result += "\nEvaluation has been successfully dispatched."
                
            return result
        else:
            error_msg = f"Command failed with return code {return_code}\n\n"
            if stderr.strip():
                error_msg += "Error output:\n" + stderr
            if stdout.strip():
                error_msg += "\nStandard output:\n" + stdout
            return f"Error: {error_msg}"
            
    except Exception as e:
        logger.error(f"Error running Plexus evaluation: {str(e)}", exc_info=True)
        return f"Error running Plexus evaluation: {str(e)}"

def debug_python_env(module_to_check: str = "plexus.cli") -> str:
    """Returns debugging information about the Python environment."""
    try:
        import sys
        import importlib.util
        import os
        import subprocess
        
        # Get system paths
        paths = sys.path
        
        # Format the result
        result = "Python Environment Debug Information:\n\n"
        
        # Python executable
        result += f"Python executable: {sys.executable}\n"
        result += f"Python version: {sys.version}\n\n"
        
        # Current working directory
        result += f"Current working directory: {os.getcwd()}\n\n"
        
        # Check for the module
        module_spec = importlib.util.find_spec(module_to_check)
        result += f"Module '{module_to_check}' found: {module_spec is not None}\n"
        if module_spec:
            result += f"Module location: {module_spec.origin}\n\n"
        else:
            result += "\n"
        
        # Check for plexus package
        plexus_spec = importlib.util.find_spec("plexus")
        result += f"Module 'plexus' found: {plexus_spec is not None}\n"
        if plexus_spec:
            result += f"Plexus package location: {plexus_spec.origin}\n\n"
        else:
            result += "\n"
            
        # List Python files in the plexus/cli directory if it exists
        if plexus_spec:
            plexus_dir = os.path.dirname(plexus_spec.origin)
            cli_dir = os.path.join(plexus_dir, "cli")
            if os.path.isdir(cli_dir):
                result += "Files in plexus/cli directory:\n"
                for file in sorted(os.listdir(cli_dir)):
                    if file.endswith(".py") or os.path.isdir(os.path.join(cli_dir, file)):
                        result += f"- {file}\n"
                result += "\n"
        
        # Test if the plexus command exists
        try:
            which_process = subprocess.run(
                ["which", "plexus"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if which_process.returncode == 0:
                result += f"Plexus command found at: {which_process.stdout.strip()}\n\n"
            else:
                result += "Plexus command not found in PATH\n\n"
        except Exception as cmd_err:
            result += f"Error checking for plexus command: {str(cmd_err)}\n\n"
            
        # List sys.path (first 10 entries)
        result += "sys.path (search paths for Python modules):\n"
        for i, path in enumerate(paths[:10]):
            result += f"{i+1}. {path}\n"
        
        if len(paths) > 10:
            result += f"... and {len(paths) - 10} more paths\n\n"
            
        # List environment variables related to Python or Plexus
        result += "Relevant environment variables:\n"
        env_vars = ["PYTHONPATH", "PYTHONHOME", "PATH", "PLEXUS_API_URL", "PLEXUS_API_KEY", "AWS_DEFAULT_REGION"]
        for var in env_vars:
            if var in os.environ:
                value = os.environ[var]
                # Mask sensitive values
                if var in ["PLEXUS_API_KEY"]:
                    value = value[:5] + "..." if value else "Not set"
                result += f"{var}: {value}\n"
            else:
                result += f"{var}: Not set\n"
                
        return result
    except Exception as e:
        return f"Error getting Python environment info: {str(e)}"

def test_plexus_commands() -> str:
    """Tests different methods of executing Plexus commands."""
    import subprocess
    import os
    
    result = "Testing different Plexus command execution methods:\n\n"
    commands = [
        # Test 1: plexus direct command
        {
            "desc": "Direct plexus command",
            "cmd": "plexus --help", 
            "shell": True
        },
        # Test 2: Python module entry point
        {
            "desc": "Python module entry point", 
            "cmd": f"{sys.executable} -m plexus.cli --help", 
            "shell": True
        },
        # Test 3: Find any command scripts
        {
            "desc": "Execute plexus.cli directly with Python",
            "cmd": f"{sys.executable} -c \"import plexus.cli; print('Modules in plexus.cli:', dir(plexus.cli))\"",
            "shell": True
        },
        # Test 4: Try CommandLineInterface directly
        {
            "desc": "Import and run CommandLineInterface",
            "cmd": f"{sys.executable} -c \"from plexus.cli.CommandLineInterface import cli; print('CLI command found:', cli != None)\"",
            "shell": True
        },
        # Test 5: Try finding the actual command script
        {
            "desc": "Find plexus script/binary in PATH",
            "cmd": "which plexus",
            "shell": True
        }
    ]
    
    for i, test in enumerate(commands, 1):
        result += f"Test {i}: {test['desc']}\n"
        result += f"Command: {test['cmd']}\n"
        
        try:
            process = subprocess.run(
                test["cmd"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=test["shell"],
                env=os.environ.copy(),
                text=True,
                timeout=10
            )
            result += f"Return code: {process.returncode}\n"
            
            if process.stdout.strip():
                stdout = process.stdout.strip()
                # Truncate if too long
                if len(stdout) > 500:
                    stdout = stdout[:500] + "... [truncated]"
                result += f"Output:\n{stdout}\n"
                
            if process.stderr.strip():
                stderr = process.stderr.strip()
                # Truncate if too long
                if len(stderr) > 500:
                    stderr = stderr[:500] + "... [truncated]"
                result += f"Error output:\n{stderr}\n"
                
        except subprocess.TimeoutExpired:
            result += "Command timed out after 10 seconds.\n"
        except Exception as e:
            result += f"Error running command: {str(e)}\n"
            
        result += "\n" + "-" * 40 + "\n\n"
    
    return result

# Create the Server instance
# Use a more specific name now that Plexus code is included
server = Server("Plexus MCP Server", "0.3.0")

# --- Tool Definitions (Dictionaries) ---

LIST_PLEXUS_SCORECARDS_TOOL_DEF = {
    "name": "list_plexus_scorecards",
    "description": "Lists scorecards from the Plexus Dashboard. Can filter by account, name, or key.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account": {"type": "string", "description": "Filter by account name or key (for Dashboard lookup)."},
            "name": {"type": "string", "description": "Filter scorecards whose name contains this string."},
            "key": {"type": "string", "description": "Filter scorecards whose key contains this string."},
            "limit": {"type": ["integer", "null"], "description": "Maximum number of scorecards to return. If omitted or null, attempts to return all."}
        },
        "required": []
    },
    "annotations": {
        "readOnlyHint": True
    }
}

GET_PLEXUS_SCORECARD_INFO_TOOL_DEF = {
    "name": "get_plexus_scorecard_info",
    "description": "Gets detailed information about a specific scorecard, including its sections and scores.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "scorecard_identifier": {
                "type": "string",
                "description": "The identifier for the scorecard (can be ID, name, key, or external ID)."
            }
        },
        "required": ["scorecard_identifier"]
    },
    "annotations": {
        "readOnlyHint": True
    }
}

GET_PLEXUS_SCORE_DETAILS_TOOL_DEF = {
    "name": "get_plexus_score_details",
    "description": "Gets detailed information for a specific score, including its configuration and version history.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "scorecard_identifier": {
                "type": "string",
                "description": "Identifier for the parent scorecard (ID, name, key, or external ID)."
            },
            "score_identifier": {
                "type": "string",
                "description": "Identifier for the score (ID, name, key, or external ID)."
            },
            "version_id": {
                "type": ["string", "null"],
                "description": "Optional specific version ID of the score to fetch configuration for. If omitted, defaults to champion or latest."
            }
        },
        "required": ["scorecard_identifier", "score_identifier"]
    },
    "annotations": {
        "readOnlyHint": True
    }
}

LIST_PLEXUS_REPORTS_TOOL_DEF = {
    "name": "list_plexus_reports",
    "description": "Lists reports from the Plexus Dashboard. Can be filtered by account or report configuration ID. Results are sorted by most recent first.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_identifier": {"type": ["string", "null"], "description": "Optional: Account name, key, or ID."},
            "report_configuration_id": {"type": ["string", "null"], "description": "Optional: ID of the report configuration."},
            "limit": {"type": ["integer", "null"], "description": "Optional: Maximum number of reports to return (default 10)."}
        },
        "required": []
    },
    "annotations": {"readOnlyHint": True}
}

GET_PLEXUS_REPORT_DETAILS_TOOL_DEF = {
    "name": "get_plexus_report_details",
    "description": "Gets detailed information for a specific report, including its output and any generated blocks.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "report_id": {"type": "string", "description": "The unique ID of the report."}
        },
        "required": ["report_id"]
    },
    "annotations": {"readOnlyHint": True}
}

GET_LATEST_PLEXUS_REPORT_TOOL_DEF = {
    "name": "get_latest_plexus_report",
    "description": "Gets full details for the most recent report, optionally filtered by account or report configuration ID.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_identifier": {"type": ["string", "null"], "description": "Optional: Account name, key, or ID to filter by."},
            "report_configuration_id": {"type": ["string", "null"], "description": "Optional: ID of the report configuration to filter by."}
        },
        "required": []
    },
    "annotations": {"readOnlyHint": True}
}

RUN_PLEXUS_EVALUATION_TOOL_DEF = {
    "name": "run_plexus_evaluation",
    "description": "Run an accuracy evaluation on a Plexus scorecard with a specific score.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "scorecard_name": {"type": "string", "description": "The name of the scorecard to evaluate (e.g., 'CMG - EDU v1.0')."},
            "score_name": {"type": "string", "description": "The name of a specific score to evaluate within the scorecard."},
            "n_samples": {"type": "integer", "description": "Number of samples to evaluate.", "default": 10}
        },
        "required": ["scorecard_name"]
    }
}

# Add debug tool definition
DEBUG_PYTHON_ENV_TOOL_DEF = {
    "name": "debug_python_env",
    "description": "Debug the Python environment, including available modules and paths.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "module_to_check": {"type": "string", "description": "Module to check for availability.", "default": "plexus.cli"}
        },
        "required": []
    }
}

# Add test commands tool definition
TEST_PLEXUS_COMMANDS_TOOL_DEF = {
    "name": "test_plexus_commands",
    "description": "Test different methods of executing Plexus commands to find one that works.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": []
    }
}

# --- MCP Server Handlers using Decorators ---

@server.list_tools()
async def list_tools() -> List[Tool]:
    """Returns the list of available tools."""
    tools = [
        Tool(**LIST_PLEXUS_SCORECARDS_TOOL_DEF),
        Tool(**RUN_PLEXUS_EVALUATION_TOOL_DEF),
        Tool(**DEBUG_PYTHON_ENV_TOOL_DEF),
        Tool(**GET_PLEXUS_SCORECARD_INFO_TOOL_DEF),
        Tool(**GET_PLEXUS_SCORE_DETAILS_TOOL_DEF),
        Tool(**LIST_PLEXUS_REPORTS_TOOL_DEF),
        Tool(**GET_PLEXUS_REPORT_DETAILS_TOOL_DEF),
        Tool(**GET_LATEST_PLEXUS_REPORT_TOOL_DEF),
        Tool(**TEST_PLEXUS_COMMANDS_TOOL_DEF)
    ]
    logger.info(f"Listing {len(tools)} tools.")
    return tools

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handles tool execution requests."""
    logger.info(f"Executing tool: {name} with args: {arguments}")

    result = None
    error_message = None

    try:
        if name == "list_plexus_scorecards":
            # Always use dashboard without local fallback
            result = list_dashboard_scorecards(
                account=arguments.get("account"),
                name=arguments.get("name"),
                key=arguments.get("key"),
                limit=arguments.get("limit")
            )
        elif name == "get_plexus_scorecard_info":
            scorecard_identifier_arg = arguments.get("scorecard_identifier")
            if not scorecard_identifier_arg:
                raise ValueError("Missing required argument: scorecard_identifier")
            result = get_scorecard_info_impl(scorecard_identifier=scorecard_identifier_arg)
        elif name == "get_plexus_score_details":
            scorecard_id_arg = arguments.get("scorecard_identifier")
            score_id_arg = arguments.get("score_identifier")
            version_id_arg = arguments.get("version_id") # Optional
            if not scorecard_id_arg or not score_id_arg:
                raise ValueError("Missing required arguments: scorecard_identifier and/or score_identifier")
            result = get_score_details_impl(
                scorecard_identifier=scorecard_id_arg, 
                score_identifier=score_id_arg, 
                version_id=version_id_arg
            )
        elif name == "list_plexus_reports":
            result = list_plexus_reports_impl(
                account_identifier=arguments.get("account_identifier"),
                report_configuration_id=arguments.get("report_configuration_id"),
                limit=arguments.get("limit")
            )
        elif name == "get_plexus_report_details":
            report_id_arg = arguments.get("report_id")
            if not report_id_arg:
                raise ValueError("Missing required argument: report_id")
            result = get_plexus_report_details_impl(report_id=report_id_arg)
        elif name == "get_latest_plexus_report":
            result = get_latest_plexus_report_impl(
                account_identifier=arguments.get("account_identifier"),
                report_configuration_id=arguments.get("report_configuration_id")
            )

        elif name == "run_plexus_evaluation":
            result = run_plexus_evaluation(
                scorecard_name=arguments.get("scorecard_name"),
                score_name=arguments.get("score_name"),
                n_samples=arguments.get("n_samples", 10)
            )
            
        elif name == "debug_python_env":
            module_to_check = arguments.get("module_to_check", "plexus.cli")
            result = debug_python_env(module_to_check)
            
        elif name == "test_plexus_commands":
            result = test_plexus_commands()
        
        # Add other tool handlers here later
        # elif name == "get_plexus_scorecard_info": # This was a typo, get_plexus_scorecard_info is already handled
        #     ...

        else:
            raise ValueError(f"Unknown tool: {name}")

        # Check if the implementation function returned an error string
        if isinstance(result, str) and result.startswith("Error:"):
            error_message = result
            result = None # Clear result if it was an error message

    except Exception as e:
        logger.error(f"Error during tool execution for '{name}': {str(e)}", exc_info=True)
        error_message = f"Error executing tool '{name}': {str(e)}"

    # Format the response
    if error_message:
        # Tool execution failed, return error as text content
        # Alternatively, could raise an MCPError for structured errors, but TextContent is simpler
        return [TextContent(type="text", text=error_message)]
    elif isinstance(result, (list, dict)):
        # If result is list/dict (e.g., from dashboard), return as JSON string
        try:
            json_result = json.dumps(result, indent=2)
            return [TextContent(type="text", text=json_result)]
        except Exception as json_err:
             logger.error(f"Failed to serialize result for tool {name} to JSON: {json_err}")
             return [TextContent(type="text", text=f"Error: Failed to serialize result to JSON.")]
    elif isinstance(result, str):
         # If result is already a string (e.g., from local list or hello_world)
        return [TextContent(type="text", text=result)]
    else:
        # Handle unexpected result types
        logger.warning(f"Tool {name} returned unexpected type: {type(result)}")
        return [TextContent(type="text", text=f"Error: Tool {name} returned unexpected result type.")]


# --- Main Execution Block ---

async def main():
    """Sets up logging and runs the MCP server."""
    global args # Access command line arguments if needed
    
    # Make sure we're not accidentally writing to stdout
    sys.stdout.flush()

    # Configure logging properly before starting server
    log_level = logging.DEBUG if os.environ.get("MCP_DEBUG") else logging.INFO
    # Ensure Plexus logging setup doesn't interfere if it failed
    if PLEXUS_CORE_AVAILABLE and 'setup_logging' in globals():
        # Assuming plexus setup_logging handles handlers correctly
        pass 
    else:
        # Fallback if Plexus logging isn't available or setup failed
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        # Remove basicConfig handlers if they exist before adding ours
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.root.addHandler(stderr_handler)
        logging.root.setLevel(log_level)

    # Log startup information
    logger.info(f"MCP Server starting")
    logger.info(f"Server working directory: {os.getcwd()}")
    
    # Check for essential environment variables
    api_url = os.environ.get('PLEXUS_API_URL')
    api_key = os.environ.get('PLEXUS_API_KEY')
    
    if not api_url or not api_key:
        logger.warning("API credentials missing. Ensure .env file is loaded with --env-file.")
    else:
        logger.info("API credentials found in environment.")

    logger.info(f"Starting MCP server ({server.name} v{server.version}) using mcp.server library...")

    # Create initialization options (library handles protocol version etc.)
    options = server.create_initialization_options()

    # Load .env file AFTER logging is configured
    # Use the --env-dir argument if provided
    dotenv_path = None # Initialize
    try:
        from dotenv import load_dotenv
        if args.env_dir:
            # Use the provided directory path
            env_directory = args.env_dir
            dotenv_path = os.path.join(env_directory, '.env')
            logger.info(f"Attempting to load .env file from specified --env-dir: {dotenv_path}")
            # Check if the target directory exists before trying to load
            if not os.path.isdir(env_directory):
                logger.error(f"--env-dir directory does not exist: {env_directory}")
                dotenv_path = None # Prevent further attempts
            elif not os.path.isfile(dotenv_path):
                logger.error(f".env file not found at specified location: {dotenv_path}")
                dotenv_path = None # Prevent further attempts
            else:
                # File exists, try to load it
                loaded = load_dotenv(dotenv_path=dotenv_path, override=True)
                if loaded:
                    logger.info(f".env file loaded successfully from {dotenv_path}")
                    # Log environment variables (excluding any sensitive info)
                    logger.info(f"Environment contains PLEXUS_DASHBOARD_API_URL: {'Yes' if os.environ.get('PLEXUS_DASHBOARD_API_URL') else 'No'}")
                    logger.info(f"Environment contains PLEXUS_DASHBOARD_API_KEY: {'Yes' if os.environ.get('PLEXUS_DASHBOARD_API_KEY') else 'No'}")
                else:
                    logger.error(f"Failed to load .env file from {dotenv_path} (load_dotenv returned False)")
        else:
            logger.warning("--env-dir argument not provided. Skipping .env file loading. Credentials must be available via environment.")

    except ImportError:
        logger.error("python-dotenv not found, cannot load .env file. Please install with: pip install python-dotenv")
    except Exception as env_err:
        env_path_str = f" from {dotenv_path}" if dotenv_path else ""
        logger.error(f"Error loading .env file{env_path_str}: {env_err}", exc_info=True)

    # Run the server using stdio
    async with stdio_server() as (read_stream, write_stream):
        logger.info("MCP Server connected via stdio, waiting for initialize...")
        try:
            # Flush stderr to ensure all logs are visible before starting protocol
            sys.stderr.flush()
            await server.run(read_stream, write_stream, options, raise_exceptions=True)
            logger.info("MCP Server finished.")
        except Exception as e:
            logger.error(f"Error in server.run: {e}", exc_info=True)
            raise

if __name__ == "__main__":
    # Basic argument parsing primarily for compatibility with the wrapper script
    parser = StderrArgumentParser(description="Plexus MCP Server (Library)")
    parser.add_argument("--host", help="Host (ignored for stdio)")
    parser.add_argument("--port", type=int, help="Port (ignored for stdio)")
    parser.add_argument("--transport", default="stdio", choices=["stdio"], help="Transport (only stdio supported)")
    parser.add_argument("--env-dir", help="Absolute path to the directory containing the .env file for credentials.")
    args = parser.parse_args()

    globals()["args"] = args # Make args accessible if needed elsewhere

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    except Exception as e:
         logger.error(f"MCP Server crashed: {e}", exc_info=True)
         sys.exit(1) 