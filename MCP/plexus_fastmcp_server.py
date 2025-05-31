#!/usr/bin/env python3
"""
Plexus MCP Server using FastMCP - A simplified implementation using the FastMCP framework
"""
import os
import sys
import json
import io  # Import io module first
import logging
import asyncio
import shlex
import subprocess
from typing import Dict, Any, List, Union, Optional, Tuple
from io import StringIO
import argparse
from pydantic import BaseModel, Field
from typing_extensions import Annotated
from fastmcp import FastMCP, Context
from urllib.parse import urljoin

# Save original stdout file descriptor
original_stdout_fd = None
try:
    # Only do this if we're not already redirected
    if sys.stdout.fileno() == 1:  # 1 is the standard fd for stdout
        original_stdout_fd = os.dup(1)  # Duplicate original stdout fd
        os.dup2(2, 1)  # Redirect stdout (fd 1) to stderr (fd 2)
        # Now all stdout fd writes go to stderr
except (AttributeError, io.UnsupportedOperation):
    # Handle non-standard stdout (like in tests or IDEs)
    pass

def restore_stdout():
    """Restore original stdout for controlled JSON-RPC output"""
    if original_stdout_fd is not None:
        try:
            os.dup2(original_stdout_fd, 1)  # Restore original stdout
        except Exception as e:
            print(f"Error restoring stdout: {e}", file=sys.stderr)

def redirect_stdout_to_stderr():
    """Redirect stdout to stderr at the file descriptor level"""
    if original_stdout_fd is not None:
        try:
            os.dup2(2, 1)  # Redirect stdout to stderr again
        except Exception as e:
            print(f"Error redirecting stdout: {e}", file=sys.stderr)

# === END STDOUT PROTECTION ===

import logging
import asyncio
import shlex
import subprocess
from typing import Dict, Any, List, Union, Optional
from io import StringIO
import argparse
from pydantic import BaseModel, Field
from typing_extensions import Annotated

# Configure logging to stderr only
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# Safety measure: Monkey patch builtins.print to always use stderr
original_print = print
def safe_print(*args, **kwargs):
    # If file is explicitly set, honor it; otherwise, force stderr
    if 'file' not in kwargs:
        kwargs['file'] = sys.stderr
    return original_print(*args, **kwargs)
print = safe_print

# Global account cache - stores the resolved account ID
DEFAULT_ACCOUNT_ID = None
DEFAULT_ACCOUNT_KEY = None
ACCOUNT_CACHE = {}  # Maps account keys/names to resolved IDs

# Temporarily redirect stdout during initialization to prevent any accidental writing to stdout
original_stdout = sys.stdout
temp_stdout = StringIO()
sys.stdout = temp_stdout

# Initialize Global flags and dummy functions first
PLEXUS_CORE_AVAILABLE = False
def create_dashboard_client(): return None
def resolve_account_identifier(client, identifier): return None
def resolve_scorecard_identifier(client, identifier): return None

try:
    # Redirect sys.stdout again to make absolutely sure nothing leaks during path setup
    path_stdout = StringIO()
    sys.stdout = path_stdout
    
    # Add Plexus project root to Python path if necessary
    plexus_root = os.path.dirname(os.path.abspath(__file__))
    if plexus_root not in sys.path:
        sys.path.append(plexus_root)
    # Also add parent if running from within Plexus directory structure
    parent_dir = os.path.dirname(plexus_root)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    
    # Check if anything was written during path setup
    path_output = path_stdout.getvalue()
    if path_output:
        logger.warning(f"Captured unexpected stdout during path setup: {path_output}")
    # Restore to our main capture buffer
    sys.stdout = temp_stdout
    
    # Import FastMCP
    from fastmcp import FastMCP
    
    # Try to import the Plexus core modules
    try:
        # Attempt to import Plexus modules for core functionality
        from plexus.dashboard.api.client import PlexusDashboardClient
        # Assign imported functions to pre-defined names
        from plexus.cli.client_utils import create_client as _create_dashboard_client
        from plexus.cli.ScorecardCommands import resolve_account_identifier as _resolve_account_identifier
        from plexus.cli.identifier_resolution import resolve_scorecard_identifier as _resolve_scorecard_identifier
        
        # Create a wrapper around create_dashboard_client to add better error logging
        def enhanced_create_dashboard_client():
            # Redirect stdout during client creation
            client_stdout = StringIO()
            old_stdout = sys.stdout
            sys.stdout = client_stdout
            
            try:
                api_url = os.environ.get('PLEXUS_API_URL', '')
                api_key = os.environ.get('PLEXUS_API_KEY', '')
                
                logger.debug(f"API URL exists: {bool(api_url)}, API KEY exists: {bool(api_key)}")
                
                if not api_url or not api_key:
                    logger.warning("Missing API credentials: API_URL or API_KEY not set in environment")
                    return None
                
                # Call the original function
                client = _create_dashboard_client()
                
                if client:
                    logger.debug(f"Dashboard client created successfully with type: {type(client)}")
                else:
                    logger.warning("Dashboard client creation returned None - check API credentials")
                
                return client
            except Exception as e:
                logger.error(f"Error creating dashboard client: {str(e)}", exc_info=True)
                return None
            finally:
                # Check if anything was written to stdout
                client_output = client_stdout.getvalue()
                if client_output:
                    logger.warning(f"Captured unexpected stdout during client creation: {client_output}")
                # Restore stdout to previous capture
                sys.stdout = old_stdout
        
        # Create wrappers for identifier resolution functions to capture stdout
        def wrapped_resolve_account_identifier(client, identifier):
            resolve_stdout = StringIO()
            old_stdout = sys.stdout
            sys.stdout = resolve_stdout
            try:
                result = _resolve_account_identifier(client, identifier)
                return result
            finally:
                # Check if anything was written to stdout
                resolve_output = resolve_stdout.getvalue()
                if resolve_output:
                    logger.warning(f"Captured unexpected stdout during account resolution: {resolve_output}")
                # Restore stdout to previous capture
                sys.stdout = old_stdout
                
        def wrapped_resolve_scorecard_identifier(client, identifier):
            resolve_stdout = StringIO()
            old_stdout = sys.stdout
            sys.stdout = resolve_stdout
            try:
                result = _resolve_scorecard_identifier(client, identifier)
                return result
            finally:
                # Check if anything was written to stdout
                resolve_output = resolve_stdout.getvalue()
                if resolve_output:
                    logger.warning(f"Captured unexpected stdout during scorecard resolution: {resolve_output}")
                # Restore stdout to previous capture
                sys.stdout = old_stdout
        
        # Replace the imported functions with our enhanced versions
        create_dashboard_client = enhanced_create_dashboard_client
        resolve_account_identifier = wrapped_resolve_account_identifier
        resolve_scorecard_identifier = wrapped_resolve_scorecard_identifier
        PLEXUS_CORE_AVAILABLE = True
        logger.info("Plexus core modules imported successfully.")
    except ImportError as e:
        logger.warning(f"Could not import core Plexus modules: {e}. Dashboard features will be unavailable.")
        # Dummies are already defined, PLEXUS_CORE_AVAILABLE is already False
    except Exception as import_err:
        # Catch other potential errors during import/setup
        logger.error(f"Error during Plexus core module import/setup: {import_err}", exc_info=True)
    
    # Check for and log any accidental stdout output from imports
    stdout_captured = temp_stdout.getvalue()
    if stdout_captured:
        logger.warning(f"Captured unexpected stdout output during imports: {stdout_captured}")
    
    # Restore stdout for proper JSON-RPC communication
    sys.stdout = original_stdout
except Exception as e:
    # Ensure stdout is restored in case of exception
    sys.stdout = original_stdout
    # Log error to stderr
    if 'logger' in locals():
        logger.error(f"Error during initialization: {e}", exc_info=True)
    else:
        print(f"Error during initialization: {e}", file=sys.stderr)
    raise

# Create FastMCP instance
mcp = FastMCP(
    name="Plexus MCP Server",
    instructions="""
    Access Plexus Dashboard functionality, run evaluations, and manage scorecards.
    
    ## Scorecard Management
    - list_plexus_scorecards: List available scorecards with optional filtering by name or key
    - get_plexus_scorecard_info: Get detailed information about a specific scorecard, including sections and scores
    - get_plexus_score_details: Get configuration and version details for a specific score within a scorecard
    
    ## Score Configuration Management (NEW)
    - find_plexus_score: Intelligent search to find a specific score within scorecards using flexible identifiers
    - get_plexus_score_configuration: Get the YAML configuration for a specific score version
    - update_plexus_score_configuration: Update a score's configuration by creating a new version (MUTATION)
    
    ## Evaluation Tools
    - run_plexus_evaluation: Dispatches a scorecard evaluation to run in the background. 
      The server will confirm dispatch but will not track progress or results. 
      Monitor evaluation status via Plexus Dashboard or system logs.
    
    ## Report Tools
    - list_plexus_reports: List available reports with optional filtering by report configuration
    - get_plexus_report_details: Get detailed information about a specific report
    - get_latest_plexus_report: Get the most recent report, optionally filtered by report configuration
    - list_plexus_report_configurations: List available report configurations
    
    ## Item Tools
    - get_latest_plexus_item: Get the most recent item for an account, with optional score results
    - get_plexus_item_details: Get detailed information about a specific item by its ID, with optional score results
    
    ## Task Tools
    - get_latest_plexus_task: Get the most recent task for an account, with optional filtering by task type
    - get_plexus_task_details: Get detailed information about a specific task by its ID, including task stages
    
    ## Documentation Tools
    - get_plexus_documentation: Access specific documentation files by name (e.g., 'score-yaml-format' for Score YAML configuration guide)
    
    ## Utility Tools
    - think: REQUIRED tool to use before other tools to structure reasoning and plan approach
    - get_score_yaml_documentation: Comprehensive documentation about score YAML configuration format (legacy - use get_plexus_documentation instead)
    """
)

# --- Tool Implementations ---

@mcp.tool()
async def think(thought: str) -> str:
    """
    Before taking any action or responding to the user after receiving tool results, use the think tool as a scratchpad to:
    - Plan your approach
    - Verify parameters
    - Diagnose issues
    - Find specific information
    - Plan a sequence of tool calls
    
    When to use this tool:
    - Before running evaluations to verify parameters
    - After encountering an error and need to diagnose the issue
    - When analyzing scorecard or report data to find specific information
    - When planning a sequence of tool calls to accomplish a user request
    - When determining what information is missing from a user request
    - When deciding between multiple possible approaches
    - When you plan on using multiple tools in a sequence
    - ESPECIALLY when working with score configurations - always check if you need documentation first
    
    Here are some examples of what to iterate over inside the think tool:

    <think_tool_example_1>
    The user asked to run an evaluation for 'EDU Scorecard'.
    - I need to check: does this scorecard exist?
    - Did they specify a score name? No.
    - Did they specify sample count? Yes, 10 samples.
    - Plan: First list scorecards to confirm name exists, then run evaluation.
    </think_tool_example_1>
    
    <think_tool_example_2>
    The user wants the latest report.
    - Did they specify a report configuration? No.
    - Plan: Use get_latest_plexus_report with minimal filtering.
    </think_tool_example_2>
    
    <think_tool_example_3>
    User asked about 'Pain Points' score configuration.
    - Need to: 1) Find which scorecard contains this score
                2) Get the scorecard ID
                3) Get score details using the scorecard ID and score name
    </think_tool_example_3>

    <think_tool_example_4>
    User asked to see the most recent "HCS" report.
    - Did they specify a report configuration? No.
    - Plan: Use list_plexus_report_configurations to find the HCS report configuration.
    - Then use get_latest_plexus_report with the report configuration ID.
    - Then use get_plexus_report_details to get the details of the report.
    And I should always show the URL of the report in my response.
    </think_tool_example_4>
    
    <think_tool_example_5>
    User asked to update the "Grammar Check" score on the "Quality Assurance" scorecard.
    - Need to: 1) Find the scorecard and score using find_plexus_score
                2) Get current configuration using get_plexus_score_configuration
                3) IMPORTANT: If user needs help with YAML format, use get_plexus_documentation(filename="score-yaml-format")
                4) Discuss changes with user or apply requested modifications
                5) Use update_plexus_score_configuration to create new version
    - Should provide dashboard URL for easy access to the updated score.
    - This is a mutation operation, so be careful and confirm changes.
    </think_tool_example_5>
    
    <think_tool_example_6>
    User asked about score configuration format or needs help creating a new score.
    - FIRST: Use get_plexus_documentation(filename="score-yaml-format") to get the complete guide
    - This documentation includes:
      * Core concepts (Score vs Scorecard)
      * Implementation types (LangGraphScore, etc.)
      * Dependencies between scores
      * LangGraph configuration details
      * Node types (Classifier, Extractor, BeforeAfterSlicer, etc.)
      * Message templates and metadata
      * Best practices and examples
    - Then proceed with scorecard/score operations based on the user's specific needs
    - Always reference the documentation when explaining YAML configuration
    </think_tool_example_6>
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Log the thought for debugging purposes
        logger.info(f"Think tool used: {thought[:100]}...")
        
        return "Thought processed"
    except Exception as e:
        logger.error(f"Error in think tool: {str(e)}", exc_info=True)
        return f"Error processing thought: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during think: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def list_plexus_scorecards(
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
        # Check if Plexus core modules are available
        if not PLEXUS_CORE_AVAILABLE:
            return "Error: Plexus Dashboard components are not available. Core modules failed to import."
        
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
                from plexus.dashboard.api.client import PlexusDashboardClient
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
async def run_plexus_evaluation(
    scorecard_name: str = "",
    score_name: str = "",
    n_samples: int = 10,
    ctx: Context = None # Context is not used in this simplified background version
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

@mcp.tool()
async def get_plexus_scorecard_info(scorecard_identifier: str) -> Union[str, Dict[str, Any]]:
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
            # Fix the import to use the correct modules
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
async def get_plexus_score_details(
    scorecard_identifier: str,
    score_identifier: str,
    version_id: Optional[str] = None
) -> Union[str, Dict[str, Any]]:
    """
    Gets detailed information for a specific score, including its versions and configuration.
    
    Parameters:
    - scorecard_identifier: Identifier for the parent scorecard (ID, name, key, or external ID)
    - score_identifier: Identifier for the score (ID, name, key, or external ID)
    - version_id: Optional specific version ID of the score to fetch configuration for. If omitted, defaults to champion or latest
    
    Returns:
    - Detailed information about the score and its configuration
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Import plexus CLI inside function to keep startup fast
        try:
            # Fix the import to use the correct modules
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
            logger.warning("Missing API credentials for get_score_details. Ensure .env file is loaded.")
            return "Error: Missing API credentials for get_score_details."

        # Create the client directly
        client = create_dashboard_client()
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
        return f"Error getting score details: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during get_plexus_score_details: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def list_plexus_reports(
    report_configuration_id: Optional[str] = None,
    limit: Optional[int] = 10
) -> Union[str, List[Dict]]:
    """
    Lists reports from the Plexus Dashboard. Can be filtered by report configuration ID.
    
    Parameters:
    - report_configuration_id: Optional ID of the report configuration
    - limit: Maximum number of reports to return (default 10)
    
    Returns:
    - A list of reports matching the filter criteria, sorted by createdAt in descending order (newest first)
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Import plexus CLI inside function to keep startup fast
        try:
            # Fix imports to use the correct modules
            from plexus.cli.client_utils import create_client as create_dashboard_client
            from plexus.dashboard.api.client import PlexusDashboardClient
        except ImportError as e:
            logger.error(f"ImportError: {str(e)}", exc_info=True)
            return f"Error: Failed to import Plexus modules: {str(e)}"
        
        # Check if we have the necessary credentials
        api_url = os.environ.get('PLEXUS_API_URL', '')
        api_key = os.environ.get('PLEXUS_API_KEY', '')
        
        if not api_url or not api_key:
            logger.warning("Missing API credentials. Ensure .env file is loaded.")
            return "Error: Missing API credentials. API_URL or API_KEY not set in environment."
        
        # Create dashboard client
        client = create_dashboard_client()
        if not client:
            return "Error: Could not create dashboard client."

        # Build filter conditions
        filter_conditions = []
        
        # Always use default account
        default_account_id = get_default_account_id()
        if default_account_id:
            filter_conditions.append(f'accountId: {{eq: "{default_account_id}"}}')
            logger.info("Using default account for report listing")
        else:
            logger.warning("No default account ID available for filtering reports")
        
        limit_val = limit if limit is not None else 10
        
        # If we have a report configuration ID, use the specific GSI for it
        if report_configuration_id:
            # Use GSI by reportConfigurationId and createdAt for more efficient queries
            query = f"""
            query ListReportsByConfig {{
                listReportByReportConfigurationIdAndCreatedAt(
                    reportConfigurationId: "{report_configuration_id}",
                    sortDirection: DESC,
                    limit: {limit_val}
                ) {{
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
            
            logger.info(f"Executing listReportByReportConfigurationIdAndCreatedAt query")
            response = client.execute(query)
            
            if response.get('errors'):
                error_details = json.dumps(response['errors'], indent=2)
                logger.error(f"listReportByReportConfigurationIdAndCreatedAt query returned errors: {error_details}")
                return f"Error from listReportByReportConfigurationIdAndCreatedAt query: {error_details}"
                
            reports_data = response.get('listReportByReportConfigurationIdAndCreatedAt', {}).get('items', [])
        else:
            # No specific report configuration - use GSI by accountId and updatedAt for sorting
            if default_account_id:
                query = f"""
                query ListReportsByAccountAndUpdatedAt {{
                    listReportByAccountIdAndUpdatedAt(
                        accountId: "{default_account_id}",
                        sortDirection: DESC,
                        limit: {limit_val}
                    ) {{
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
                
                logger.info(f"Executing listReportByAccountIdAndUpdatedAt query")
                response = client.execute(query)
                
                if response.get('errors'):
                    error_details = json.dumps(response['errors'], indent=2)
                    logger.error(f"listReportByAccountIdAndUpdatedAt query returned errors: {error_details}")
                    return f"Error from listReportByAccountIdAndUpdatedAt query: {error_details}"
                    
                reports_data = response.get('listReportByAccountIdAndUpdatedAt', {}).get('items', [])
            else:
                # Fallback to basic listReports without sorting if no account ID
                query = f"""
                query ListReports {{
                    listReports(
                        limit: {limit_val}
                    ) {{
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
                
                logger.info(f"Executing basic listReports query (no account filter)")
                response = client.execute(query)
                
                if response.get('errors'):
                    error_details = json.dumps(response['errors'], indent=2)
                    logger.error(f"listReports query returned errors: {error_details}")
                    return f"Error from listReports query: {error_details}"
                    
                reports_data = response.get('listReports', {}).get('items', [])
        
        if not reports_data:
            if report_configuration_id:
                return f"No reports found for report configuration ID: {report_configuration_id}"
            else:
                return "No reports found."
            
        return reports_data
    except Exception as e:
        logger.error(f"Error listing reports: {str(e)}", exc_info=True)
        return f"Error listing reports: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during list_plexus_reports: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def get_plexus_report_details(report_id: str) -> Union[str, Dict[str, Any]]:
    """
    Gets detailed information for a specific report, including its output and any generated blocks.
    
    Parameters:
    - report_id: The unique ID of the report
    
    Returns:
    - Detailed information about the report
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Import plexus CLI inside function to keep startup fast
        try:
            # Fix imports to use the correct modules
            from plexus.cli.client_utils import create_client as create_dashboard_client
            from plexus.dashboard.api.client import PlexusDashboardClient
        except ImportError as e:
            logger.error(f"ImportError: {str(e)}", exc_info=True)
            return f"Error: Failed to import Plexus modules: {str(e)}"
        
        # Check if we have the necessary credentials
        api_url = os.environ.get('PLEXUS_API_URL', '')
        api_key = os.environ.get('PLEXUS_API_KEY', '')
        
        if not api_url or not api_key:
            return "Error: Missing API credentials. API_URL or API_KEY not set in environment."
        
        # Create the client
        client = create_dashboard_client()
        if not client:
            return "Error: Could not create dashboard client."

        # Build and execute the query
        query = f"""
        query GetReport {{
            getReport(id: "{report_id}") {{
                id
                name
                createdAt
                updatedAt
                parameters
                output
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
                        output
                        log
                        createdAt
                        updatedAt
                    }}
                }}
            }}
        }}
        """
        logger.info(f"Executing getReport query for ID: {report_id}")
        response = client.execute(query)

        if response.get('errors'):
            error_details = json.dumps(response['errors'], indent=2)
            logger.error(f"getReport query returned errors: {error_details}")
            return f"Error from getReport query: {error_details}"

        report_data = response.get('getReport')
        if not report_data:
            return f"Error: Report with ID '{report_id}' not found."
            
        # Add URL to the report data
        report_data['url'] = get_report_url(report_id)
        
        return report_data
    except Exception as e:
        logger.error(f"Error getting report details for ID '{report_id}': {str(e)}", exc_info=True)
        return f"Error getting report details: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during get_plexus_report_details: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def get_latest_plexus_report(
    report_configuration_id: Optional[str] = None
) -> Union[str, Dict[str, Any]]:
    """
    Gets full details for the most recent report, optionally filtered by report configuration ID.
    
    Parameters:
    - report_configuration_id: Optional ID of the report configuration to filter by
    
    Returns:
    - Detailed information about the most recent report
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # First, list reports to find the latest one's ID
        reports = await list_plexus_reports(
            report_configuration_id=report_configuration_id,
            limit=1
        )
        
        # Handle error string response
        if isinstance(reports, str) and reports.startswith("Error:"):
            return reports
            
        # Handle empty response
        if not reports or (isinstance(reports, list) and len(reports) == 0):
            return "No reports found to determine the latest one."
            
        # Parse JSON if we got a JSON string
        if isinstance(reports, str):
            try:
                reports = json.loads(reports)
            except:
                return f"Error: Unexpected response format from list_plexus_reports: {reports}"
        
        # Get the latest report ID
        if not isinstance(reports, list) or len(reports) == 0 or not reports[0].get('id'):
            return "Error: Could not extract ID from the latest report."
        
        latest_report_id = reports[0]['id']
        logger.info(f"Found latest report ID: {latest_report_id}")
        
        # Get the full report details
        report_details = await get_plexus_report_details(report_id=latest_report_id)
        
        # If report_details is already a string (error message), return it directly
        if isinstance(report_details, str):
            return report_details
            
        # Add the URL if not already present
        if isinstance(report_details, dict) and 'url' not in report_details:
            report_details['url'] = get_report_url(latest_report_id)
            
        return report_details
        
    except Exception as e:
        logger.error(f"Error getting latest report: {str(e)}", exc_info=True)
        return f"Error getting latest report: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during get_latest_plexus_report: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def list_plexus_report_configurations() -> Union[str, List[Dict]]:
    """
    List all report configurations in reverse chronological order.
    
    Returns:
    - Array of report configuration objects with name, id, description, and updatedAt fields
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Import plexus CLI inside function to keep startup fast
        try:
            from plexus.cli.client_utils import create_client as create_dashboard_client
            from plexus.dashboard.api.client import PlexusDashboardClient
        except ImportError as e:
            logger.error(f"ImportError: {str(e)}", exc_info=True)
            return f"Error: Failed to import Plexus modules: {str(e)}"
        
        # Get the client
        client = create_dashboard_client()
        if not client:
            return "Error: Could not create dashboard client."
        
        # Get the default account ID
        actual_account_id = get_default_account_id()
        if not actual_account_id:
            return "Error: Could not determine default account ID. Please check that PLEXUS_ACCOUNT_KEY is set in environment."
            
        logger.info("Listing report configurations")
        
        # Build and execute the query
        query = f"""
        query MyQuery {{
          listReportConfigurationByAccountIdAndUpdatedAt(
            accountId: "{actual_account_id}"
            sortDirection: DESC
          ) {{
            items {{
              description
              name
              id
              updatedAt
            }}
            nextToken
          }}
        }}
        """
        
        response = client.execute(query)
        
        if 'errors' in response:
            error_details = json.dumps(response['errors'], indent=2)
            logger.error(f"Dashboard query for report configurations returned errors: {error_details}")
            return f"Error from Dashboard query for report configurations: {error_details}"
        
        # Extract data from response
        configs_data = response.get('listReportConfigurationByAccountIdAndUpdatedAt', {}).get('items', [])
        
        # If no configurations found, try a different approach
        if not configs_data:
            # Try with slightly different parameters as a fallback
            retry_query = f"""
            query RetryQuery {{
              listReportConfigurations(filter: {{ accountId: {{ eq: "{actual_account_id}" }} }}, limit: 20) {{
                items {{
                  id
                  name
                  description
                  updatedAt
                }}
              }}
            }}
            """
            retry_response = client.execute(retry_query)
            
            if 'listReportConfigurations' in retry_response:
                configs_data = retry_response['listReportConfigurations'].get('items', [])
                
        # Format each configuration
        if not configs_data:
            return "No report configurations found."
        
        formatted_configs = []
        for config in configs_data:
            formatted_configs.append({
                "id": config.get("id"),
                "name": config.get("name"),
                "description": config.get("description"),
                "updatedAt": config.get("updatedAt")
            })
        
        logger.info(f"Successfully retrieved {len(formatted_configs)} report configurations")
        return formatted_configs
    
    except Exception as e:
        logger.error(f"Error listing report configurations: {str(e)}", exc_info=True)
        return f"Error listing report configurations: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during list_plexus_report_configurations: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def get_latest_plexus_item(
    include_score_results: bool = False
) -> Union[str, Dict[str, Any]]:
    """
    Gets the most recent item for the default account, with optional score results.
    
    Parameters:
    - include_score_results: Whether to include score results for the item (optional, default: False)
    
    Returns:
    - Detailed information about the most recent item
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Import plexus modules inside function to keep startup fast
        try:
            from plexus.cli.client_utils import create_client as create_dashboard_client
            from plexus.dashboard.api.models.item import Item
            from plexus.dashboard.api.models.score_result import ScoreResult
            from plexus.cli.reports.utils import resolve_account_id_for_command
        except ImportError as e:
            logger.error(f"ImportError: {str(e)}", exc_info=True)
            return f"Error: Failed to import Plexus modules: {str(e)}"
        
        # Check if we have the necessary credentials
        api_url = os.environ.get('PLEXUS_API_URL', '')
        api_key = os.environ.get('PLEXUS_API_KEY', '')
        
        if not api_url or not api_key:
            return "Error: Missing API credentials. API_URL or API_KEY not set in environment."
        
        # Create the client
        client = create_dashboard_client()
        if not client:
            return "Error: Could not create dashboard client."

        # Get the default account ID
        account_id = resolve_account_id_for_command(client, None)
        if not account_id:
            return "Error: Could not determine default account ID. Please check that PLEXUS_ACCOUNT_KEY is set in environment."
            
        logger.info(f"Getting latest item for account: {account_id}")
        
        # Use the GSI for proper ordering to get the most recent item
        query = f"""
        query ListItemByAccountIdAndCreatedAt($accountId: String!) {{
            listItemByAccountIdAndCreatedAt(accountId: $accountId, sortDirection: DESC, limit: 1) {{
                items {{
                    {Item.fields()}
                }}
            }}
        }}
        """
        
        response = client.execute(query, {'accountId': account_id})
        
        if 'errors' in response:
            error_details = json.dumps(response['errors'], indent=2)
            logger.error(f"Dashboard query returned errors: {error_details}")
            return f"Error from Dashboard query: {error_details}"
        
        items = response.get('listItemByAccountIdAndCreatedAt', {}).get('items', [])
        
        if not items:
            return "No items found for this account."
            
        # Get the most recent item
        item_data = items[0]
        item = Item.from_dict(item_data, client)
        
        # Convert item to dictionary format
        item_dict = {
            'id': item.id,
            'accountId': item.accountId,
            'evaluationId': item.evaluationId,
            'scoreId': item.scoreId,
            'description': item.description,
            'externalId': item.externalId,
            'isEvaluation': item.isEvaluation,
            'metadata': item.metadata,
            'identifiers': item.identifiers,
            'attachedFiles': item.attachedFiles,
            'createdAt': item.createdAt.isoformat() if item.createdAt else None,
            'updatedAt': item.updatedAt.isoformat() if item.updatedAt else None,
            'url': get_item_url(item.id)
        }
        
        # Get score results if requested
        if include_score_results:
            score_results = await _get_score_results_for_item(item.id, client)
            item_dict['scoreResults'] = score_results
        
        logger.info(f"Successfully retrieved latest item: {item.id}")
        return item_dict
        
    except Exception as e:
        logger.error(f"Error getting latest item: {str(e)}", exc_info=True)
        return f"Error getting latest item: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during get_latest_plexus_item: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def get_plexus_item_details(
    item_id: str,
    include_score_results: bool = False
) -> Union[str, Dict[str, Any]]:
    """
    Gets detailed information about a specific item by its ID, with optional score results.
    
    Parameters:
    - item_id: The unique ID of the item
    - include_score_results: Whether to include score results for the item (optional, default: False)
    
    Returns:
    - Detailed information about the item
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Import plexus modules inside function to keep startup fast
        try:
            from plexus.cli.client_utils import create_client as create_dashboard_client
            from plexus.dashboard.api.models.item import Item
            from plexus.dashboard.api.models.score_result import ScoreResult
        except ImportError as e:
            logger.error(f"ImportError: {str(e)}", exc_info=True)
            return f"Error: Failed to import Plexus modules: {str(e)}"
        
        # Check if we have the necessary credentials
        api_url = os.environ.get('PLEXUS_API_URL', '')
        api_key = os.environ.get('PLEXUS_API_KEY', '')
        
        if not api_url or not api_key:
            return "Error: Missing API credentials. API_URL or API_KEY not set in environment."
        
        # Create the client
        client = create_dashboard_client()
        if not client:
            return "Error: Could not create dashboard client."

        logger.info(f"Getting item details for ID: {item_id}")
        
        try:
            item = Item.get_by_id(item_id, client)
            if not item:
                return f"Item not found: {item_id}"
            
            # Convert item to dictionary format
            item_dict = {
                'id': item.id,
                'accountId': item.accountId,
                'evaluationId': item.evaluationId,
                'scoreId': item.scoreId,
                'description': item.description,
                'externalId': item.externalId,
                'isEvaluation': item.isEvaluation,
                'metadata': item.metadata,
                'identifiers': item.identifiers,
                'attachedFiles': item.attachedFiles,
                'createdAt': item.createdAt.isoformat() if item.createdAt else None,
                'updatedAt': item.updatedAt.isoformat() if item.updatedAt else None,
                'url': get_item_url(item.id)
            }
            
            # Get score results if requested
            if include_score_results:
                score_results = await _get_score_results_for_item(item.id, client)
                item_dict['scoreResults'] = score_results
            
            logger.info(f"Successfully retrieved item details: {item_id}")
            return item_dict
            
        except Exception as e:
            logger.error(f"Error retrieving item {item_id}: {str(e)}", exc_info=True)
            return f"Error retrieving item {item_id}: {str(e)}"
        
    except Exception as e:
        logger.error(f"Error getting item details for ID '{item_id}': {str(e)}", exc_info=True)
        return f"Error getting item details: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during get_plexus_item_details: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def get_latest_plexus_task(
    task_type: Optional[str] = None
) -> Union[str, Dict[str, Any]]:
    """
    Gets the most recent task for an account, with optional filtering by task type.
    
    Parameters:
    - task_type: Optional filter by task type (e.g., 'Evaluation', 'Report', etc.)
    
    Returns:
    - Detailed information about the most recent task, including its stages
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Check if Plexus core modules are available
        if not PLEXUS_CORE_AVAILABLE:
            return "Error: Plexus Dashboard components are not available. Core modules failed to import."
        
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
                from plexus.dashboard.api.client import PlexusDashboardClient
                client = PlexusDashboardClient(api_url=api_url, api_key=api_key)
            finally:
                client_output = client_stdout.getvalue()
                if client_output:
                    logger.warning(f"Captured unexpected stdout during client creation in get_latest_plexus_task: {client_output}")
                sys.stdout = saved_stdout
        except Exception as client_err:
            logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
            return f"Error creating dashboard client: {str(client_err)}"
            
        if not client:
            return "Error: Could not create dashboard client."

        # Get default account ID
        default_account_id = get_default_account_id()
        if not default_account_id:
            return "Error: No default account ID available."

        # Query for the most recent task using the GSI
        query = """
        query ListTaskByAccountIdAndUpdatedAt($accountId: String!) {
            listTaskByAccountIdAndUpdatedAt(accountId: $accountId, sortDirection: DESC, limit: 50) {
                items {
                    id
                    accountId
                    type
                    status
                    target
                    command
                    description
                    metadata
                    createdAt
                    updatedAt
                    startedAt
                    completedAt
                    estimatedCompletionAt
                    errorMessage
                    errorDetails
                    stdout
                    stderr
                    currentStageId
                    workerNodeId
                    dispatchStatus
                    scorecardId
                    scoreId
                }
            }
        }
        """
        
        # Execute query
        query_stdout = StringIO()
        saved_stdout = sys.stdout
        sys.stdout = query_stdout
        
        try:
            result = client.execute(query, {'accountId': default_account_id})
            
            # Check for GraphQL errors
            if 'errors' in result:
                error_details = json.dumps(result['errors'], indent=2)
                logger.error(f"Dashboard query returned errors: {error_details}")
                return f"Error from Dashboard query: {error_details}"

            tasks_data = result.get('listTaskByAccountIdAndUpdatedAt', {}).get('items', [])

            if not tasks_data:
                return "No tasks found for this account."

            # Filter by task type if specified
            if task_type:
                tasks_data = [t for t in tasks_data if t.get('type', '').lower() == task_type.lower()]
                if not tasks_data:
                    return f"No tasks found of type '{task_type}' for this account."

            # Get the most recent task
            latest_task_data = tasks_data[0]
            
            # Get task stages
            stages_query = """
            query ListTaskStageByTaskId($taskId: String!) {
                listTaskStageByTaskId(taskId: $taskId) {
                    items {
                        id
                        taskId
                        name
                        order
                        status
                        statusMessage
                        startedAt
                        completedAt
                        estimatedCompletionAt
                        processedItems
                        totalItems
                    }
                }
            }
            """
            
            stages_result = client.execute(stages_query, {'taskId': latest_task_data['id']})
            stages_data = stages_result.get('listTaskStageByTaskId', {}).get('items', [])
            
            # Sort stages by order
            stages_data.sort(key=lambda s: s.get('order', 0))
            
            # Include stages in the task data
            latest_task_data['stages'] = stages_data
            
            # Add the task URL for convenience
            latest_task_data['url'] = get_task_url(latest_task_data["id"])
            
            return latest_task_data
            
        finally:
            query_output = query_stdout.getvalue()
            if query_output:
                logger.warning(f"Captured unexpected stdout during task query execution: {query_output}")
            sys.stdout = saved_stdout
            
    except Exception as e:
        logger.error(f"Error retrieving latest task: {str(e)}", exc_info=True)
        return f"Error retrieving latest task: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during get_latest_plexus_task: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def get_plexus_task_details(task_id: str) -> Union[str, Dict[str, Any]]:
    """
    Gets detailed information about a specific task by its ID, including task stages.
    
    Parameters:
    - task_id: The unique ID of the task
    
    Returns:
    - Detailed information about the task, including its stages
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Check if Plexus core modules are available
        if not PLEXUS_CORE_AVAILABLE:
            return "Error: Plexus Dashboard components are not available. Core modules failed to import."
        
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
                from plexus.dashboard.api.client import PlexusDashboardClient
                client = PlexusDashboardClient(api_url=api_url, api_key=api_key)
            finally:
                client_output = client_stdout.getvalue()
                if client_output:
                    logger.warning(f"Captured unexpected stdout during client creation in get_plexus_task_details: {client_output}")
                sys.stdout = saved_stdout
        except Exception as client_err:
            logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
            return f"Error creating dashboard client: {str(client_err)}"
            
        if not client:
            return "Error: Could not create dashboard client."

        # Query for the specific task
        task_query = """
        query GetTask($id: ID!) {
            getTask(id: $id) {
                id
                accountId
                type
                status
                target
                command
                description
                metadata
                createdAt
                updatedAt
                startedAt
                completedAt
                estimatedCompletionAt
                errorMessage
                errorDetails
                stdout
                stderr
                currentStageId
                workerNodeId
                dispatchStatus
                scorecardId
                scoreId
            }
        }
        """
        
        # Execute task query
        query_stdout = StringIO()
        saved_stdout = sys.stdout
        sys.stdout = query_stdout
        
        try:
            task_result = client.execute(task_query, {'id': task_id})
            
            # Check for GraphQL errors
            if 'errors' in task_result:
                error_details = json.dumps(task_result['errors'], indent=2)
                logger.error(f"Dashboard query returned errors: {error_details}")
                return f"Error from Dashboard query: {error_details}"

            task_data = task_result.get('getTask')
            if not task_data:
                return f"Task not found with ID: {task_id}"

            # Get task stages
            stages_query = """
            query ListTaskStageByTaskId($taskId: String!) {
                listTaskStageByTaskId(taskId: $taskId) {
                    items {
                        id
                        taskId
                        name
                        order
                        status
                        statusMessage
                        startedAt
                        completedAt
                        estimatedCompletionAt
                        processedItems
                        totalItems
                    }
                }
            }
            """
            
            stages_result = client.execute(stages_query, {'taskId': task_id})
            stages_data = stages_result.get('listTaskStageByTaskId', {}).get('items', [])
            
            # Sort stages by order
            stages_data.sort(key=lambda s: s.get('order', 0))
            
            # Include stages in the task data
            task_data['stages'] = stages_data
            
            # Add the task URL for convenience
            task_data['url'] = get_task_url(task_id)
            
            return task_data
            
        finally:
            query_output = query_stdout.getvalue()
            if query_output:
                logger.warning(f"Captured unexpected stdout during task query execution: {query_output}")
            sys.stdout = saved_stdout
            
    except Exception as e:
        logger.error(f"Error retrieving task details: {str(e)}", exc_info=True)
        return f"Error retrieving task details: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during get_plexus_task_details: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def find_plexus_score(
    score_identifier: str,
    scorecard_identifier: Optional[str] = None
) -> Union[str, Dict[str, Any]]:
    """
    Intelligent search to find a specific score within a scorecard using flexible identifiers.
    Supports complex queries like "X score on Y scorecard" by searching across scorecard names and score names.
    
    Parameters:
    - score_identifier: Identifier for the score (ID, name, key, or external ID)
    - scorecard_identifier: Optional identifier for the parent scorecard to narrow search. If omitted, searches across all scorecards.
    
    Returns:
    - Information about the found score including its location, configuration summary, and dashboard URL
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Check if Plexus core modules are available
        if not PLEXUS_CORE_AVAILABLE:
            return "Error: Plexus Dashboard components are not available. Core modules failed to import."
        
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
                from plexus.dashboard.api.client import PlexusDashboardClient
                from plexus.cli.client_utils import create_client as create_dashboard_client
                from plexus.cli.ScorecardCommands import resolve_scorecard_identifier
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
            
            # Get configuration preview if champion version exists
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
            
            return {
                "found": True,
                "scoreId": score['id'],
                "scoreName": score['name'],
                "scoreKey": score.get('key'),
                "externalId": score.get('externalId'),
                "description": score.get('description'),
                "type": score.get('type'),
                "championVersionId": champion_version_id,
                "location": {
                    "scorecardId": scorecard['id'],
                    "scorecardName": scorecard['name'],
                    "sectionId": section['id'],
                    "sectionName": section['name']
                },
                "configurationPreview": config_preview,
                "dashboardUrl": get_plexus_url(f"lab/scorecards/{scorecard['id']}/scores/{score['id']}")
            }
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
async def get_plexus_score_configuration(
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
        # Check if Plexus core modules are available
        if not PLEXUS_CORE_AVAILABLE:
            return "Error: Plexus Dashboard components are not available. Core modules failed to import."
        
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
                from plexus.dashboard.api.client import PlexusDashboardClient
                from plexus.cli.client_utils import create_client as create_dashboard_client
                from plexus.cli.ScorecardCommands import resolve_scorecard_identifier
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

        # Resolve scorecard identifier
        scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
        if not scorecard_id:
            return f"Error: Scorecard '{scorecard_identifier}' not found."

        # Find the score within the scorecard
        scorecard_query = f"""
        query GetScorecardForScore {{
            getScorecard(id: "{scorecard_id}") {{
                id
                name
                sections {{
                    items {{
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
        
        result = client.execute(scorecard_query)
        scorecard_data = result.get('getScorecard')
        if not scorecard_data:
            return f"Error: Could not retrieve scorecard data for '{scorecard_identifier}'."

        # Find the specific score
        found_score = None
        for section in scorecard_data.get('sections', {}).get('items', []):
            for score in section.get('scores', {}).get('items', []):
                if (score.get('id') == score_identifier or 
                    score.get('name') == score_identifier or 
                    score.get('key') == score_identifier or 
                    score.get('externalId') == score_identifier):
                    found_score = score
                    break
            if found_score:
                break

        if not found_score:
            return f"Error: Score '{score_identifier}' not found within scorecard '{scorecard_identifier}'."

        # Determine which version to fetch
        target_version_id = version_id or found_score.get('championVersionId')
        if not target_version_id:
            return f"Error: No version specified and no champion version found for score '{score_identifier}'."

        # Get the version configuration
        version_query = f"""
        query GetScoreVersion {{
            getScoreVersion(id: "{target_version_id}") {{
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
            return f"Error: Version '{target_version_id}' not found."

        configuration = version_data.get('configuration')
        if not configuration:
            return f"Error: No configuration found for version '{target_version_id}'."

        return {
            "scoreId": found_score['id'],
            "scoreName": found_score['name'],
            "scorecardName": scorecard_data['name'],
            "versionId": version_data['id'],
            "isChampionVersion": target_version_id == found_score.get('championVersionId'),
            "configuration": configuration,
            "versionMetadata": {
                "createdAt": version_data.get('createdAt'),
                "updatedAt": version_data.get('updatedAt'),
                "note": version_data.get('note'),
                "isFeatured": version_data.get('isFeatured'),
                "parentVersionId": version_data.get('parentVersionId')
            },
            "dashboardUrl": get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{found_score['id']}")
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
async def update_plexus_score_configuration(
    scorecard_identifier: str,
    score_identifier: str,
    yaml_configuration: str,
    version_note: Optional[str] = None
) -> Union[str, Dict[str, Any]]:
    """
    Updates a score's configuration by creating a new version with the provided YAML content.
    This is the first mutation tool in the MCP server.
    
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
        # Check if Plexus core modules are available
        if not PLEXUS_CORE_AVAILABLE:
            return "Error: Plexus Dashboard components are not available. Core modules failed to import."
        
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
                from plexus.dashboard.api.client import PlexusDashboardClient
                from plexus.cli.client_utils import create_client as create_dashboard_client
                from plexus.cli.ScorecardCommands import resolve_scorecard_identifier
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

        # Resolve scorecard identifier
        scorecard_id = resolve_scorecard_identifier(client, scorecard_identifier)
        if not scorecard_id:
            return f"Error: Scorecard '{scorecard_identifier}' not found."

        # Find the score within the scorecard
        scorecard_query = f"""
        query GetScorecardForScore {{
            getScorecard(id: "{scorecard_id}") {{
                id
                name
                sections {{
                    items {{
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
        
        result = client.execute(scorecard_query)
        scorecard_data = result.get('getScorecard')
        if not scorecard_data:
            return f"Error: Could not retrieve scorecard data for '{scorecard_identifier}'."

        # Find the specific score
        found_score = None
        for section in scorecard_data.get('sections', {}).get('items', []):
            for score in section.get('scores', {}).get('items', []):
                if (score.get('id') == score_identifier or 
                    score.get('name') == score_identifier or 
                    score.get('key') == score_identifier or 
                    score.get('externalId') == score_identifier):
                    found_score = score
                    break
            if found_score:
                break

        if not found_score:
            return f"Error: Score '{score_identifier}' not found within scorecard '{scorecard_identifier}'."

        score_id = found_score['id']
        current_champion_version_id = found_score.get('championVersionId')

        # Create new score version
        create_version_mutation = """
        mutation CreateScoreVersion($input: CreateScoreVersionInput!) {
            createScoreVersion(input: $input) {
                id
                scoreId
                configuration
                createdAt
                updatedAt
                note
                isFeatured
                parentVersionId
            }
        }
        """
        
        version_input = {
            'scoreId': score_id,
            'configuration': yaml_configuration,
            'isFeatured': True,  # Mark as featured to make it the new champion
        }
        
        if current_champion_version_id:
            version_input['parentVersionId'] = current_champion_version_id
            
        if version_note:
            version_input['note'] = version_note
        else:
            version_input['note'] = 'Updated via MCP server'

        version_result = client.execute(create_version_mutation, {'input': version_input})
        
        if 'errors' in version_result:
            error_details = json.dumps(version_result['errors'], indent=2)
            logger.error(f"Error creating score version: {error_details}")
            return f"Error creating score version: {error_details}"

        new_version = version_result.get('createScoreVersion')
        if not new_version:
            return "Error: Failed to create new score version."

        new_version_id = new_version['id']

        # Update the score to point to the new champion version
        update_score_mutation = """
        mutation UpdateScore($input: UpdateScoreInput!) {
            updateScore(input: $input) {
                id
                name
                championVersionId
            }
        }
        """
        
        update_input = {
            'id': score_id,
            'championVersionId': new_version_id
        }
        
        update_result = client.execute(update_score_mutation, {'input': update_input})
        
        if 'errors' in update_result:
            error_details = json.dumps(update_result['errors'], indent=2)
            logger.error(f"Error updating score champion version: {error_details}")
            return f"Error updating score champion version: {error_details}"

        updated_score = update_result.get('updateScore')
        if not updated_score:
            return "Warning: New version created but failed to update champion version."

        return {
            "success": True,
            "scoreId": score_id,
            "scoreName": found_score['name'],
            "scorecardName": scorecard_data['name'],
            "newVersionId": new_version_id,
            "previousChampionVersionId": current_champion_version_id,
            "versionNote": version_note or "Updated via MCP server",
            "configurationLength": len(yaml_configuration),
            "createdAt": new_version.get('createdAt'),
            "dashboardUrl": get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score_id}")
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
async def get_plexus_documentation(filename: str) -> str:
    """
    Get documentation content for specific Plexus topics.
    
    Valid filenames:
    - score-yaml-format: Complete guide to Score YAML configuration format including LangGraph, node types, dependencies, and best practices
    
    Args:
        filename (str): The documentation file to retrieve. Must be one of the valid filenames listed above.
    
    Returns:
        str: The complete documentation content in markdown format.
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        import os
        
        # Define mapping of short names to actual filenames
        valid_files = {
            "score-yaml-format": "score-yaml-format.md"
        }
        
        if filename not in valid_files:
            available = ", ".join(valid_files.keys())
            return f"Error: Invalid filename '{filename}'. Valid options are: {available}"
        
        try:
            # Get the path to the plexus docs directory
            # Navigate from MCP/ to plexus/docs/
            current_dir = os.path.dirname(os.path.abspath(__file__))
            plexus_dir = os.path.dirname(current_dir)
            docs_dir = os.path.join(plexus_dir, "plexus", "docs")
            file_path = os.path.join(docs_dir, valid_files[filename])
            
            logger.info(f"Reading documentation file: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            logger.info(f"Successfully read documentation file '{filename}' ({len(content)} characters)")
            return content
            
        except FileNotFoundError:
            error_msg = f"Documentation file '{filename}' not found at expected location: {file_path}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"Error reading documentation file '{filename}': {str(e)}"
            logger.exception(error_msg)
            return f"Error: {error_msg}"
            
    except Exception as e:
        logger.error(f"Error in get_plexus_documentation: {str(e)}", exc_info=True)
        return f"Error: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during get_plexus_documentation: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def get_score_yaml_documentation() -> str:
    """
    Provides comprehensive documentation about the YAML configuration format for scores,
    including examples and field descriptions. Use this tool when working with score configurations
    to understand the expected format and available options.
    
    Returns:
    - Detailed documentation about score YAML configuration format
    """
    return """# Score YAML Configuration Documentation

## Overview
Score configurations in Plexus use YAML format to define how scores are calculated, what prompts are used, and how results are interpreted.

## Basic Structure
```yaml
name: "Score Name"
key: "score-key"
external_id: "score_123"  # or externalId (both formats supported)
description: "Description of what this score measures"
type: "LangGraphScore"
section: "Section Name"

# Core scoring configuration
system_message: |
  You are an expert evaluator. Please assess the following content
  according to the specified criteria.

user_message: |
  Content to evaluate: {item_text}
  
  Please provide a score from 0-100 and explain your reasoning.

# Model configuration  
model_provider: "anthropic"  # or "openai", "azure", etc.
model_name: "claude-3-sonnet-20240229"
temperature: 0.1
max_tokens: 1000

# Scoring parameters
min_score: 0
max_score: 100
threshold: 70
weight: 1.0

# Advanced options
parameters:
  check_grammar: true
  check_style: true
  min_word_count: 50
  
validation_rules:
  - rule: "score >= 0 and score <= 100"
    message: "Score must be between 0 and 100"
```

## Field Descriptions

### Identity Fields
- `name`: Human-readable name for the score
- `key`: Unique identifier (alphanumeric with dashes/underscores)
- `external_id` or `externalId`: External system identifier
- `description`: Brief description of the score's purpose

### Message Templates
- `system_message`: System prompt sent to the AI model (supports multi-line with `|`)
- `user_message`: User prompt template (can include variables like `{item_text}`)

### Model Configuration
- `model_provider`: AI provider ("anthropic", "openai", "azure", etc.)
- `model_name`: Specific model to use
- `temperature`: Randomness (0.0-1.0, lower = more consistent)
- `max_tokens`: Maximum response length

### Scoring Parameters
- `min_score`/`max_score`: Score range bounds
- `threshold`: Minimum passing score
- `weight`: Relative importance in composite scores

### Variable Substitution
Use `{variable_name}` in messages to include dynamic content:
- `{item_text}`: The content being evaluated
- `{item_metadata}`: Additional item information
- `{context}`: Additional evaluation context

## Common Examples

### Binary Classification Score
```yaml
name: "Content Safety"
system_message: |
  Determine if the content is safe for general audiences.
  Respond with either "SAFE" or "UNSAFE" followed by reasoning.
user_message: |
  Content: {item_text}
min_score: 0
max_score: 1
```

### Quality Assessment Score
```yaml
name: "Writing Quality"
system_message: |
  Evaluate writing quality on grammar, clarity, and style.
  Provide a score from 1-10 with detailed feedback.
user_message: |
  Text to evaluate: {item_text}
  
  Consider:
  - Grammar and spelling
  - Clarity of communication
  - Writing style and flow
min_score: 1
max_score: 10
threshold: 7
```

### Custom Parameters Score
```yaml
name: "Technical Accuracy"
parameters:
  domain: "software engineering"
  check_citations: true
  require_examples: true
system_message: |
  You are a technical expert in {domain}.
  Evaluate the technical accuracy of the content.
```

## Best Practices

1. **Use Clear Names**: Make score names descriptive and unique
2. **Multi-line Strings**: Use `|` for multi-line system/user messages
3. **Consistent Scoring**: Define clear min/max ranges and stick to them
4. **Validation**: Include validation rules for complex scores
5. **Documentation**: Add descriptions explaining the score's purpose
6. **Testing**: Test scores with sample content before deployment

## Common Issues

### YAML Syntax Errors
- Ensure proper indentation (2 spaces recommended)
- Quote strings containing special characters
- Use `|` for multi-line strings to preserve formatting

### Field Format Issues
- Use either `external_id` or `externalId` consistently
- Ensure numeric fields (scores, weights) are not quoted
- Boolean values should be `true`/`false` (lowercase)

### Variable Substitution
- Variables in messages must match exactly: `{item_text}` not `{item-text}`
- Undefined variables will be left as-is in the final prompt

## Migration Notes

When updating existing scores:
- New versions preserve the existing format preferences
- Both `external_id` and `externalId` formats are supported
- Changes create new versions; previous versions remain accessible
- Champion version determines which configuration is used for evaluations

For additional help or advanced use cases, consult the Plexus documentation or contact support."""

async def _get_score_results_for_item(item_id: str, client) -> List[Dict[str, Any]]:
    """
    Helper function to get all score results for a specific item, sorted by updatedAt descending.
    This mirrors the functionality from the CLI ItemCommands.get_score_results_for_item function.
    """
    try:
        from plexus.dashboard.api.models.score_result import ScoreResult
        from datetime import datetime
        
        query = f"""
        query ListScoreResultByItemId($itemId: String!) {{
            listScoreResultByItemId(itemId: $itemId) {{
                items {{
                    {ScoreResult.fields()}
                    updatedAt
                    createdAt
                }}
            }}
        }}
        """
        
        result = client.execute(query, {'itemId': item_id})
        score_results_data = result.get('listScoreResultByItemId', {}).get('items', [])
        
        # Convert to ScoreResult objects and add timestamp fields manually
        score_results = []
        for sr_data in score_results_data:
            score_result = ScoreResult.from_dict(sr_data, client)
            
            # Convert to dictionary format and include timestamps
            sr_dict = {
                'id': score_result.id,
                'value': score_result.value,
                'explanation': getattr(score_result, 'explanation', None),
                'confidence': score_result.confidence,
                'correct': score_result.correct,
                'itemId': score_result.itemId,
                'scoreId': getattr(score_result, 'scoreId', None),
                'scoreName': score_result.scoreName,  # Include the score name
                'scoreVersionId': getattr(score_result, 'scoreVersionId', None),
                'scorecardId': score_result.scorecardId,
                'evaluationId': score_result.evaluationId,
                'scoringJobId': getattr(score_result, 'scoringJobId', None),
                'metadata': score_result.metadata,
                'trace': getattr(score_result, 'trace', None)
            }
            
            # Add timestamp fields
            if 'updatedAt' in sr_data:
                if isinstance(sr_data['updatedAt'], str):
                    updatedAt = datetime.fromisoformat(sr_data['updatedAt'].replace('Z', '+00:00'))
                    sr_dict['updatedAt'] = updatedAt.isoformat()
                else:
                    sr_dict['updatedAt'] = sr_data['updatedAt']
                    
            if 'createdAt' in sr_data:
                if isinstance(sr_data['createdAt'], str):
                    createdAt = datetime.fromisoformat(sr_data['createdAt'].replace('Z', '+00:00'))
                    sr_dict['createdAt'] = createdAt.isoformat()
                else:
                    sr_dict['createdAt'] = sr_data['createdAt']
            
            score_results.append(sr_dict)
        
        # Sort by updatedAt in Python since GraphQL doesn't support it
        score_results.sort(
            key=lambda sr: sr.get('updatedAt', '1970-01-01T00:00:00'),
            reverse=True
        )
        
        return score_results
        
    except Exception as e:
        logger.error(f"Error getting score results for item {item_id}: {str(e)}", exc_info=True)
        return []

# Setup dotenv support for loading environment variables
def load_env_file(env_dir=None):
    """Load environment variables from .env file."""
    try:
        from dotenv import load_dotenv
        if env_dir:
            dotenv_path = os.path.join(env_dir, '.env')
            logger.info(f"Attempting to load .env file from specified directory: {dotenv_path}")
            if os.path.isfile(dotenv_path):
                loaded = load_dotenv(dotenv_path=dotenv_path, override=True)
                if loaded:
                    logger.info(f".env file loaded successfully from {dotenv_path}")
                    logger.info(f"Environment contains PLEXUS_API_URL: {'Yes' if os.environ.get('PLEXUS_API_URL') else 'No'}")
                    logger.info(f"Environment contains PLEXUS_API_KEY: {'Yes' if os.environ.get('PLEXUS_API_KEY') else 'No'}")
                    return True
                else:
                    logger.warning(f"Failed to load .env file from {dotenv_path}")
            else:
                logger.warning(f"No .env file found at {dotenv_path}")
        return False
    except ImportError:
        logger.warning("python-dotenv not installed, can't load .env file")
        return False

def initialize_default_account():
    """Initialize the default account ID from the environment variable PLEXUS_ACCOUNT_KEY."""
    global DEFAULT_ACCOUNT_ID, DEFAULT_ACCOUNT_KEY
    
    # Get account key from environment
    account_key = os.environ.get('PLEXUS_ACCOUNT_KEY')
    if not account_key:
        logger.warning("PLEXUS_ACCOUNT_KEY environment variable not set")
        return
    
    DEFAULT_ACCOUNT_KEY = account_key
    
    # Only attempt to resolve if we have the client available
    if not PLEXUS_CORE_AVAILABLE:
        logger.warning("Plexus core not available, can't resolve default account ID")
        return
    
    # Create dashboard client and resolve account ID
    try:
        client = create_dashboard_client()
        if not client:
            logger.warning("Could not create dashboard client to resolve default account")
            return
        
        account_id = resolve_account_identifier(client, account_key)
        if not account_id:
            logger.warning(f"Could not resolve account ID for key: {account_key}")
            return
        
        DEFAULT_ACCOUNT_ID = account_id
        ACCOUNT_CACHE[account_key] = account_id
        logger.info(f"Default account ID initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing default account ID: {str(e)}", exc_info=True)

def get_default_account_id():
    """Get the default account ID, resolving it if necessary."""
    global DEFAULT_ACCOUNT_ID, DEFAULT_ACCOUNT_KEY
    
    # If already resolved, return it
    if DEFAULT_ACCOUNT_ID:
        return DEFAULT_ACCOUNT_ID
    
    # Try to resolve it now
    initialize_default_account()
    return DEFAULT_ACCOUNT_ID

def resolve_account_id_with_cache(client, identifier):
    """Resolve an account identifier to its ID, using cache when possible."""
    if not identifier:
        return get_default_account_id()
    
    # Check cache first
    if identifier in ACCOUNT_CACHE:
        return ACCOUNT_CACHE[identifier]
    
    # Resolve and cache
    account_id = resolve_account_identifier(client, identifier)
    if account_id:
        ACCOUNT_CACHE[identifier] = account_id
    
    return account_id

def get_plexus_url(path: str) -> str:
    """
    Safely concatenates the PLEXUS_APP_URL with the provided path.
    Handles cases where base URL may or may not have trailing slashes
    and path may or may not have leading slashes.
    
    Parameters:
    - path: The URL path to append to the base URL
    
    Returns:
    - Full URL string
    """
    base_url = os.environ.get('PLEXUS_APP_URL', 'https://capacity-plexus.anth.us')
    # Ensure base URL ends with a slash for urljoin to work correctly
    if not base_url.endswith('/'):
        base_url += '/'
    # Strip leading slash from path if present to avoid double slashes
    path = path.lstrip('/')
    return urljoin(base_url, path)

def get_report_url(report_id: str) -> str:
    """
    Generates a URL for viewing a report in the dashboard.
    
    Parameters:
    - report_id: The ID of the report
    
    Returns:
    - Full URL to the report in the dashboard
    """
    return get_plexus_url(f"lab/reports/{report_id}")

def get_item_url(item_id: str) -> str:
    """
    Generates a URL for viewing an item in the dashboard.
    
    Parameters:
    - item_id: The ID of the item
    
    Returns:
    - Full URL to the item in the dashboard
    """
    return get_plexus_url(f"lab/items/{item_id}")

def get_task_url(task_id: str) -> str:
    """
    Generates a URL for viewing a task in the dashboard.
    
    Parameters:
    - task_id: The ID of the task
    
    Returns:
    - Full URL to the task in the dashboard
    """
    return get_plexus_url(f"lab/tasks/{task_id}")

# Main function to run the server
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Plexus MCP Server with FastMCP")
    parser.add_argument("--env-dir", help="Directory containing .env file with Plexus credentials")
    parser.add_argument("--host", default="127.0.0.1", help="Host to run server on")
    parser.add_argument("--port", type=int, default=8002, help="Port to run server on")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="sse", 
                        help="Transport protocol (stdio for MCP process or sse for HTTP)")
    args = parser.parse_args()
    
    # Load environment variables from .env file if specified
    if args.env_dir:
        load_env_file(args.env_dir)
    
    # Initialize default account as early as possible after env vars are loaded
    # but after the Plexus core is available
    if PLEXUS_CORE_AVAILABLE:
        logger.info("Initializing default account from environment...")
        initialize_default_account()
    else:
        logger.warning("Plexus core not available, skipping default account initialization")
    
    # Run the server with appropriate transport
    try:
        logger.info("Starting FastMCP server")
        
        # Flush any pending writes
        sys.stderr.flush()
        
        # For the actual FastMCP run, we need clean stdout for JSON-RPC
        restore_stdout()
        
        # Flush to ensure clean state
        sys.stdout.flush()
        
        if args.transport == "stdio":
            # For stdio transport
            mcp.run(transport="stdio")
        else:
            # For SSE transport
            mcp.run(transport="sse", host=args.host, port=args.port)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Error running server: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        # Always redirect stdout back to stderr when we're done
        redirect_stdout_to_stderr() 