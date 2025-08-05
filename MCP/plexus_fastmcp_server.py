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
    # The MCP server is in MCP/ directory, but plexus package is in the parent directory
    mcp_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(mcp_dir)  # Go up one level to project root
    if project_root not in sys.path:
        sys.path.insert(0, project_root)  # Insert at beginning for priority
        logger.info(f"Added project root to Python path: {project_root}")
    
    # Log the paths for debugging
    logger.info(f"MCP directory: {mcp_dir}")
    logger.info(f"Project root: {project_root}")
    logger.info(f"Looking for plexus package at: {os.path.join(project_root, 'plexus')}")
    logger.info(f"Plexus package exists: {os.path.exists(os.path.join(project_root, 'plexus'))}")
    
    # Check if anything was written during path setup
    path_output = path_stdout.getvalue()
    if path_output:
        logger.warning(f"Captured unexpected stdout during path setup: {path_output}")
    # Restore to our main capture buffer
    sys.stdout = temp_stdout
    
    # Import FastMCP
    from fastmcp import FastMCP
    
    # Load YAML configuration first (before importing Plexus modules)
    try:
        from plexus.config import load_config
        load_config()  # This will set environment variables from YAML config
        logger.info("YAML configuration loaded successfully")
    except Exception as e:
        logger.warning(f"Failed to load YAML configuration: {e}")
    
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
    - plexus_scorecards_list: List available scorecards with optional filtering by name or key
    - plexus_scorecard_info: Get detailed information about a specific scorecard, including sections and scores
    
    ## Score Management
    - plexus_score_info: Get detailed information about a specific score, including location, configuration, and optionally all versions. Supports intelligent search across scorecards.
    - plexus_score_configuration: Get the YAML configuration for a specific score version
    - plexus_score_pull: Pull a score's champion version YAML configuration to a local file
    - plexus_score_push: Push a score's local YAML configuration file to create a new version
    - plexus_score_update: Update a score's configuration by creating a new version with provided YAML content
    - plexus_score_delete: Delete a specific score by ID (uses shared ScoreService - includes safety confirmation step)
    
    ## Evaluation Tools
    - run_plexus_evaluation: Dispatches a scorecard evaluation to run in the background. 
      The server will confirm dispatch but will not track progress or results. 
      Monitor evaluation status via Plexus Dashboard or system logs.
    - plexus_evaluation_info: Get detailed information about a specific evaluation by its ID,
      including scorecard name, score name, metrics, progress, and status.
    - plexus_evaluation_last: Get information about the most recent evaluation,
      optionally filtered by evaluation type (e.g., 'accuracy', 'consistency').
    
    ## Report Tools
    - plexus_reports_list: List available reports with optional filtering by report configuration
    - plexus_report_info: Get detailed information about a specific report
    - plexus_report_last: Get the most recent report, optionally filtered by report configuration
    - plexus_report_configurations_list: List available report configurations
    
    ## Item Tools
    - plexus_item_last: Get the most recent item for an account, with optional score results
    - plexus_item_info: Get detailed information about a specific item by its ID, with optional score results
    
    ## Task Tools
    - plexus_task_last: Get the most recent task for an account, with optional filtering by task type
    - plexus_task_info: Get detailed information about a specific task by its ID, including task stages
    
    ## Feedback Analysis & Score Testing Tools
    - plexus_feedback_summary: Generate comprehensive feedback summary with confusion matrix, accuracy, and AC1 agreement - RUN THIS FIRST to understand overall performance before using find
    - plexus_feedback_find: Find feedback items where human reviewers corrected predictions to identify score improvement opportunities
    - plexus_predict: Run predictions on single or multiple items using specific score configurations for testing and validation
    
    ## Documentation Tools
    - get_plexus_documentation: Access specific documentation files by name (e.g., 'score-yaml-format' for Score YAML configuration guide, 'feedback-alignment' for feedback analysis and score testing guide)
    
    ## Utility Tools
    - think: REQUIRED tool to use before other tools to structure reasoning and plan approach
    """
)

# --- Tool Implementations ---

@mcp.tool()
async def debug_plexus_imports() -> str:
    """
    Diagnostic tool to debug Plexus import issues.
    
    Returns detailed information about:
    - Python path setup
    - File system structure
    - Import errors
    - Environment information
    """
    import sys
    import os
    import traceback
    
    debug_info = []
    
    # Basic environment info
    debug_info.append("=== ENVIRONMENT INFO ===")
    debug_info.append(f"Python executable: {sys.executable}")
    debug_info.append(f"Python version: {sys.version}")
    debug_info.append(f"Current working directory: {os.getcwd()}")
    
    # Path info
    debug_info.append("\n=== PYTHON PATH ===")
    for i, path in enumerate(sys.path[:10]):  # Show first 10 paths
        debug_info.append(f"{i}: {path}")
    
    # MCP server location info
    debug_info.append("\n=== MCP SERVER LOCATION ===")
    mcp_file = os.path.abspath(__file__)
    mcp_dir = os.path.dirname(mcp_file)
    project_root = os.path.dirname(mcp_dir)
    
    debug_info.append(f"MCP server file: {mcp_file}")
    debug_info.append(f"MCP directory: {mcp_dir}")
    debug_info.append(f"Project root: {project_root}")
    
    # Check for plexus package
    debug_info.append("\n=== PLEXUS PACKAGE DETECTION ===")
    plexus_dir = os.path.join(project_root, "plexus")
    debug_info.append(f"Looking for plexus at: {plexus_dir}")
    debug_info.append(f"Plexus directory exists: {os.path.exists(plexus_dir)}")
    
    if os.path.exists(plexus_dir):
        debug_info.append(f"Plexus directory contents:")
        try:
            for item in os.listdir(plexus_dir)[:10]:  # First 10 items
                item_path = os.path.join(plexus_dir, item)
                debug_info.append(f"  {item} ({'dir' if os.path.isdir(item_path) else 'file'})")
        except Exception as e:
            debug_info.append(f"  Error listing contents: {e}")
    
    # Check specific plexus modules
    debug_info.append("\n=== PLEXUS MODULE IMPORT TESTS ===")
    
    # Test basic plexus import
    try:
        import plexus
        debug_info.append("✓ Successfully imported 'plexus'")
        debug_info.append(f"  plexus.__file__: {getattr(plexus, '__file__', 'Not available')}")
    except Exception as e:
        debug_info.append(f"✗ Failed to import 'plexus': {e}")
        debug_info.append(f"  Traceback: {traceback.format_exc()}")
    
    # Test dashboard client import
    try:
        from plexus.dashboard.api.client import PlexusDashboardClient
        debug_info.append("✓ Successfully imported PlexusDashboardClient")
    except Exception as e:
        debug_info.append(f"✗ Failed to import PlexusDashboardClient: {e}")
    
    # Test CLI imports
    try:
        from plexus.cli.client_utils import create_client
        debug_info.append("✓ Successfully imported create_client from cli.client_utils")
    except Exception as e:
        debug_info.append(f"✗ Failed to import create_client: {e}")
    
    try:
        from plexus.cli.score import ScoreService
        debug_info.append("✓ Successfully imported ScoreService")
    except Exception as e:
        debug_info.append(f"✗ Failed to import ScoreService: {e}")
    
    # Environment variables
    debug_info.append("\n=== ENVIRONMENT VARIABLES ===")
    plexus_vars = {k: v for k, v in os.environ.items() if 'PLEXUS' in k.upper()}
    if plexus_vars:
        for key, value in plexus_vars.items():
            # Don't show full API keys for security
            display_value = value[:10] + "..." if len(value) > 10 else value
            debug_info.append(f"{key}: {display_value}")
    else:
        debug_info.append("No PLEXUS_* environment variables found")
    
    # Global state
    debug_info.append(f"\n=== GLOBAL STATE ===")
    debug_info.append(f"PLEXUS_CORE_AVAILABLE: {PLEXUS_CORE_AVAILABLE}")
    
    return "\n".join(debug_info)

@mcp.tool()
async def think(thought: str) -> str:
    """
    Use this tool as a scratchpad when working with Plexus tools to:
    - Plan your approach for Plexus operations
    - Verify parameters for Plexus API calls
    - Diagnose issues with Plexus tools
    - Find specific information within Plexus data
    - Plan a sequence of Plexus tool calls
    
    When to use this tool (for Plexus operations only):
    - Before running Plexus evaluations to verify parameters
    - After encountering an error with Plexus tools and need to diagnose the issue
    - When analyzing Plexus scorecard or report data to find specific information
    - When planning a sequence of Plexus tool calls to accomplish a user request
    - When determining what Plexus information is missing from a user request
    - When deciding between multiple possible Plexus approaches
    - When you plan on using multiple Plexus tools in a sequence
    - ESPECIALLY when working with Plexus score configurations - always check if you need documentation first
    
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
    
    <think_tool_example_7>
    User asked about feedback analysis, score improvement, or testing predictions.
    - FIRST: Use get_plexus_documentation(filename="feedback-alignment") to get the complete guide
    - This documentation includes:
      * How to find feedback items where human reviewers corrected predictions
      * Commands for searching feedback by value changes (false positives/negatives)
      * Testing individual score predictions on specific items
      * Analyzing feedback patterns to improve score configurations
      * Complete workflow from feedback discovery to score improvement
    - Use the plexus_feedback_find and plexus_predict tools for hands-on analysis
    - Focus on understanding why predictions were wrong based on human feedback
    </think_tool_example_7>
    
    <think_tool_example_8>
    User asked about data configuration, dataset setup, or data queries for scores.
    - FIRST: Use get_plexus_documentation(filename="dataset-yaml-format") to get the complete guide
    - This documentation includes:
      * CallCriteriaDBCache configuration
      * Queries section for database searches
      * Searches section for working with specific item lists
      * Balancing positive/negative examples
      * Data retrieval and preparation methods
    - Then proceed with configuring the data section of score configurations
    - Always reference the documentation when explaining dataset YAML configuration
    </think_tool_example_8>
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
async def plexus_reports_list(
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
async def plexus_report_info(report_id: str) -> Union[str, Dict[str, Any]]:
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
async def plexus_report_last(
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
        reports = await plexus_reports_list(
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
        report_details = await plexus_report_info(report_id=latest_report_id)
        
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
async def plexus_report_configurations_list() -> Union[str, List[Dict]]:
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
async def plexus_item_last(
    minimal: bool = False
) -> Union[str, Dict[str, Any]]:
    """
    Gets the most recent item for the default account, including score results and feedback items by default.
    
    Parameters:
    - minimal: If True, returns minimal info without score results and feedback items (optional, default: False)
    
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
            'createdByType': item.createdByType,
            'metadata': item.metadata,
            'identifiers': item.identifiers,
            'attachedFiles': item.attachedFiles,
            'createdAt': item.createdAt.isoformat() if item.createdAt else None,
            'updatedAt': item.updatedAt.isoformat() if item.updatedAt else None,
            'url': get_item_url(item.id)
        }
        
        # Get score results and feedback items by default (unless minimal mode)
        if not minimal:
            score_results = await _get_score_results_for_item(item.id, client)
            item_dict['scoreResults'] = score_results
            
            feedback_items = await _get_feedback_items_for_item(item.id, client)
            item_dict['feedbackItems'] = feedback_items
        
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
async def plexus_item_info(
    item_id: str,
    minimal: bool = False
) -> Union[str, Dict[str, Any]]:
    """
    Gets detailed information about a specific item by its ID or external identifier, including score results and feedback items by default.
    
    Parameters:
    - item_id: The unique ID of the item OR an external identifier value (e.g., "277430500")
    - minimal: If True, returns minimal info without score results and feedback items (optional, default: False)
    
    Returns:
    - Detailed information about the item including text content, metadata, identifiers, and timestamps
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
            from plexus.utils.identifier_search import find_item_by_identifier
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

        logger.info(f"Getting item details for ID/identifier: {item_id}")
        
        item = None
        lookup_method = "unknown"
        
        # Try direct ID lookup first
        try:
            item = Item.get_by_id(item_id, client)
            if item:
                lookup_method = "direct_id"
                logger.info(f"Found item by direct ID lookup: {item_id}")
        except ValueError:
            # Not found by ID, continue to identifier search
            logger.info(f"Item not found by direct ID, trying identifier search for: {item_id}")
        except Exception as e:
            logger.warning(f"Error in direct ID lookup: {str(e)}")
        
        # If direct ID lookup failed, try identifier-based lookup
        if not item:
            default_account_id = get_default_account_id()
            if default_account_id:
                try:
                    item = find_item_by_identifier(item_id, default_account_id, client)
                    if item:
                        lookup_method = "identifier_search"
                        logger.info(f"Found item by identifier search: {item.id} (identifier: {item_id})")
                except Exception as e:
                    logger.warning(f"Error in identifier search: {str(e)}")
        
        # If still not found, try Identifiers table GSI lookup as final fallback
        if not item:
            default_account_id = get_default_account_id()
            if default_account_id:
                try:
                    # Use the Identifiers table GSI to find items by identifier value
                    query = """
                    query GetIdentifierByAccountAndValue($accountId: String!, $value: String!) {
                        listIdentifierByAccountIdAndValue(
                            accountId: $accountId,
                            value: {eq: $value},
                            limit: 1
                        ) {
                            items {
                                itemId
                                name
                                value
                                url
                                position
                                item {
                                    id
                                    accountId
                                    evaluationId
                                    scoreId
                                    description
                                    externalId
                                    isEvaluation
                                    text
                                    metadata
                                    identifiers
                                    attachedFiles
                                    createdAt
                                    updatedAt
                                }
                            }
                        }
                    }
                    """
                    
                    result = client.execute(query, {
                        'accountId': default_account_id,
                        'value': item_id
                    })
                    
                    if result and 'listIdentifierByAccountIdAndValue' in result:
                        identifiers = result['listIdentifierByAccountIdAndValue'].get('items', [])
                        if identifiers:
                            identifier_data = identifiers[0]
                            item_data = identifier_data.get('item', {})
                            
                            if item_data:
                                # Create a mock Item object from the data
                                class MockItem:
                                    def __init__(self, data):
                                        for key, value in data.items():
                                            setattr(self, key, value)
                                        # Handle datetime parsing
                                        if hasattr(self, 'createdAt') and self.createdAt:
                                            from datetime import datetime
                                            try:
                                                self.createdAt = datetime.fromisoformat(self.createdAt.replace('Z', '+00:00'))
                                            except:
                                                pass
                                        if hasattr(self, 'updatedAt') and self.updatedAt:
                                            from datetime import datetime
                                            try:
                                                self.updatedAt = datetime.fromisoformat(self.updatedAt.replace('Z', '+00:00'))
                                            except:
                                                pass
                                
                                item = MockItem(item_data)
                                lookup_method = f"identifiers_table_gsi (name: {identifier_data.get('name', 'N/A')})"
                                logger.info(f"Found item by Identifiers table GSI: {item.id} (identifier: {item_id})")
                    
                except Exception as e:
                    logger.warning(f"Error in Identifiers table GSI lookup: {str(e)}")
        
        if not item:
            return f"Item not found: {item_id} (tried direct ID, identifier search, and external ID lookup)"
        
        try:
            # Convert item to dictionary format
            item_dict = {
                'id': item.id,
                'accountId': item.accountId,
                'evaluationId': item.evaluationId,
                'scoreId': item.scoreId,
                'description': item.description,
                'externalId': item.externalId,
                'isEvaluation': item.isEvaluation,
                'createdByType': item.createdByType,
                'text': item.text,  # Include text content
                'metadata': item.metadata,
                'identifiers': item.identifiers,
                'attachedFiles': item.attachedFiles,
                'createdAt': item.createdAt.isoformat() if hasattr(item.createdAt, 'isoformat') else item.createdAt,
                'updatedAt': item.updatedAt.isoformat() if hasattr(item.updatedAt, 'isoformat') else item.updatedAt,
                'url': get_item_url(item.id),
                'lookupMethod': lookup_method  # Include how the item was found for debugging
            }
            
            # Get score results and feedback items by default (unless minimal mode)
            if not minimal:
                score_results = await _get_score_results_for_item(item.id, client)
                item_dict['scoreResults'] = score_results
                
                feedback_items = await _get_feedback_items_for_item(item.id, client)
                item_dict['feedbackItems'] = feedback_items
            
            logger.info(f"Successfully retrieved item details: {item.id} (lookup method: {lookup_method})")
            return item_dict
            
        except Exception as e:
            logger.error(f"Error processing item {item.id}: {str(e)}", exc_info=True)
            return f"Error processing item {item.id}: {str(e)}"
        
    except Exception as e:
        logger.error(f"Error getting item details for ID/identifier '{item_id}': {str(e)}", exc_info=True)
        return f"Error getting item details: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during get_plexus_item_details: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def plexus_task_last(
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
        # Try to import required modules directly
        try:
            from plexus.dashboard.api.client import PlexusDashboardClient
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
async def plexus_task_info(task_id: str) -> Union[str, Dict[str, Any]]:
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
        # Try to import required modules directly
        try:
            from plexus.dashboard.api.client import PlexusDashboardClient
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
            from plexus.cli.client_utils import create_client as create_dashboard_client
            from plexus.cli.ScorecardCommands import resolve_scorecard_identifier
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
        from plexus.cli.ScorecardCommands import resolve_scorecard_identifier
        
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
            from plexus.cli.client_utils import create_client as create_dashboard_client
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
                "dashboardUrl": get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score.id}")
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
                "dashboardUrl": get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score.id}")
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
            from plexus.cli.client_utils import create_client as create_dashboard_client
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
            "dashboardUrl": get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score.id}")
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
            from plexus.cli.client_utils import create_client as create_dashboard_client
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
            "championUpdated": push_result.get("champion_updated", True),
            "skipped": push_result.get("skipped", False),
            "message": push_result["message"],
            "dashboardUrl": get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score.id}")
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
            from plexus.cli.client_utils import create_client as create_dashboard_client
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
            "championUpdated": result.get("champion_updated", True),
            "skipped": result.get("skipped", False),
            "dashboardUrl": get_plexus_url(f"lab/scorecards/{scorecard_id}/scores/{score.id}")
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
async def plexus_feedback_summary(
    scorecard_name: str,
    score_name: str,
    days: Union[int, float, str] = 14,
    output_format: str = "json"
) -> str:
    """
    Generate comprehensive feedback summary with confusion matrix, accuracy, and AC1 agreement.
    
    This tool provides an overview of feedback quality and should be run BEFORE using
    the 'plexus_feedback_find' tool to examine specific feedback items. 
    
    The summary includes:
    - Overall accuracy percentage
    - Gwet's AC1 agreement coefficient  
    - Confusion matrix showing prediction vs actual patterns
    - Precision and recall metrics
    - Class distribution analysis
    - Actionable recommendations for next steps
    
    Use this tool first to understand overall performance before drilling down
    into specific feedback segments with plexus_feedback_find.
    
    Args:
        scorecard_name (str): Name of the scorecard (partial match supported)
        score_name (str): Name of the score (partial match supported) 
        days (int): Number of days back to analyze (default: 14)
        output_format (str): Output format - "json" or "yaml" (default: "json")
    
    Returns:
        str: Comprehensive feedback summary with analysis and recommendations
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # DEBUG: Log what parameters we actually received
        logger.info(f"[MCP DEBUG] Received parameters - scorecard_name: '{scorecard_name}', score_name: '{score_name}', days: '{days}', output_format: '{output_format}'")
        
        # Convert string parameters to appropriate types
        try:
            days = int(float(str(days)))  # Handle both int and float strings
        except (ValueError, TypeError):
            return f"Error: Invalid days parameter: {days}. Must be a number."
        
        logger.info(f"[MCP] Generating feedback summary for '{score_name}' on '{scorecard_name}' (last {days} days)")
        
        # Try to import required modules directly (don't rely on global PLEXUS_CORE_AVAILABLE)
        try:
            from plexus.cli.feedback.feedback_service import FeedbackService
        except ImportError as e:
            return f"Error: Could not import FeedbackService: {e}. Core modules may not be available."
        
        # Get client and account using existing patterns
        from plexus.cli.client_utils import create_client as create_dashboard_client
        from plexus.cli.reports.utils import resolve_account_id_for_command
        
        client = create_dashboard_client()
        if not client:
            return "Error: Could not create Plexus client. Check API credentials."
        
        account_id = resolve_account_id_for_command(client, None)
        if not account_id:
            return "Error: Could not resolve account ID."
        
        # Use the same robust score-finding logic as find_plexus_score
        from plexus.cli.ScorecardCommands import resolve_scorecard_identifier
        
        # Find scorecard using the robust resolver
        scorecard_id = resolve_scorecard_identifier(client, scorecard_name)
        if not scorecard_id:
            return f"Error: Scorecard not found: {scorecard_name}"
            
        # Get scorecard name and score details using the same approach as find_plexus_score
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
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        response = client.execute(scorecard_query)
        if 'errors' in response:
            return f"Error querying scorecard: {response['errors']}"
            
        scorecard_data = response.get('getScorecard')
        if not scorecard_data:
            return f"Error: Could not retrieve scorecard data for '{scorecard_name}'"
        
        # Find score using the same robust matching as find_plexus_score
        score_match = None
        for section in scorecard_data.get('sections', {}).get('items', []):
            for score in section.get('scores', {}).get('items', []):
                # Use same matching criteria as find_plexus_score
                if (score.get('id') == score_name or 
                    score.get('name', '').lower() == score_name.lower() or 
                    score.get('key') == score_name or 
                    score.get('externalId') == score_name or
                    score_name.lower() in score.get('name', '').lower()):
                    score_match = score
                    break
            if score_match:
                break
        
        if not score_match:
            return f"Error: Score not found in scorecard '{scorecard_data['name']}': {score_name}"
        
        # Use the matched scorecard data
        scorecard_match = scorecard_data
        
        logger.info(f"[MCP] Found: {scorecard_match['name']} → {score_match['name']}")
        
        # Generate summary using the shared service
        summary_result = await FeedbackService.summarize_feedback(
            client=client,
            scorecard_name=scorecard_match['name'],
            score_name=score_match['name'],
            scorecard_id=scorecard_match['id'],
            score_id=score_match['id'],
            account_id=account_id,
            days=days
        )
        
        # Convert to dictionary for output
        result_dict = FeedbackService.format_summary_result_as_dict(summary_result)
        
        # Add command context
        result_dict["command_info"] = {
            "description": "Comprehensive feedback analysis with confusion matrix and agreement metrics",
            "tool": f"plexus_feedback_summary(scorecard_name='{scorecard_name}', score_name='{score_name}', days={days}, output_format='{output_format}')",
            "next_steps": result_dict["recommendation"]
        }
        
        # Output in requested format
        if output_format.lower() == 'yaml':
            import yaml
            from datetime import datetime
            # Add contextual comments for YAML
            yaml_comment = f"""# Feedback Summary Analysis
# Scorecard: {scorecard_match['name']}
# Score: {score_match['name']}
# Period: Last {days} days
# Generated: {datetime.now().isoformat()}
#
# This summary provides overview metrics that help identify which specific
# feedback segments to examine using plexus_feedback_find. Use the confusion
# matrix to understand error patterns and follow the recommendation for next steps.

"""
            yaml_output = yaml.dump(result_dict, default_flow_style=False, sort_keys=False)
            return yaml_comment + yaml_output
        else:
            import json
            return json.dumps(result_dict, indent=2, default=str)
            
    except Exception as e:
        logger.error(f"[MCP] Error in plexus_feedback_summary: {e}")
        import traceback
        logger.error(f"[MCP] Traceback: {traceback.format_exc()}")
        return f"Error generating feedback summary: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during plexus_feedback_summary: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout


@mcp.tool()
async def plexus_feedback_find(
    scorecard_name: str,
    score_name: str,
    initial_value: Optional[str] = None,
    final_value: Optional[str] = None,
    limit: Optional[Union[int, float, str]] = 10,
    days: Optional[Union[int, float, str]] = 30,
    output_format: str = "json",
    prioritize_edit_comments: bool = True
) -> Union[str, Dict[str, Any]]:
    """
    Find feedback items where human reviewers have corrected predictions. 
    This helps identify cases where score configurations need improvement.
    
    Parameters:
    - scorecard_name: Name of the scorecard containing the score
    - score_name: Name of the specific score to search feedback for
    - initial_value: Optional filter for the original AI prediction value (e.g., "No", "Yes")
    - final_value: Optional filter for the corrected human value (e.g., "Yes", "No")
    - limit: Maximum number of feedback items to return (default: 10)
    - days: Number of days back to search (default: 30)
    - output_format: Output format - "json" or "yaml" (default: "json")
    - prioritize_edit_comments: Whether to prioritize feedback items with edit comments (default: True)
    
    Returns:
    - Feedback items with correction details, edit comments, and item information
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Try to import required modules directly
        try:
            from plexus.cli.client_utils import create_client as create_dashboard_client
            from plexus.cli.ScorecardCommands import resolve_scorecard_identifier
            from plexus.cli.feedback.feedback_service import FeedbackService
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
                    logger.warning(f"Captured unexpected stdout during client creation in plexus_feedback_find: {client_output}")
                sys.stdout = saved_stdout
        except Exception as client_err:
            logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
            return f"Error creating dashboard client: {str(client_err)}"
            
        if not client:
            return "Error: Could not create dashboard client."

        # Find the scorecard
        scorecard_id = resolve_scorecard_identifier(client, scorecard_name)
        if not scorecard_id:
            return f"Error: Scorecard '{scorecard_name}' not found."

        # Find the score within the scorecard
        scorecard_query = f"""
        query GetScorecardForFeedback {{
            getScorecard(id: "{scorecard_id}") {{
                id
                name
                sections {{
                    items {{
                        id
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
        
        scorecard_result = client.execute(scorecard_query)
        scorecard_data = scorecard_result.get('getScorecard')
        if not scorecard_data:
            return f"Error: Could not retrieve scorecard data for '{scorecard_name}'."

        # Find the specific score
        found_score_id = None
        for section in scorecard_data.get('sections', {}).get('items', []):
            for score in section.get('scores', {}).get('items', []):
                if (score.get('name') == score_name or 
                    score.get('key') == score_name or 
                    score.get('id') == score_name or 
                    score.get('externalId') == score_name):
                    found_score_id = score['id']
                    break
            if found_score_id:
                break

        if not found_score_id:
            return f"Error: Score '{score_name}' not found within scorecard '{scorecard_name}'."

        # Get account ID using the same method as feedback_summary
        try:
            from plexus.cli.reports.utils import resolve_account_id_for_command
            account_id = resolve_account_id_for_command(client, None)
            if not account_id:
                return "Error: Could not determine account ID for feedback query."
        except Exception as e:
            logger.error(f"Error getting account ID: {e}")
            return f"Error getting account ID: {e}"
        
        # Convert days to int if provided
        if days:
            try:
                days_int = int(days)
            except (ValueError, TypeError):
                return f"Error: Invalid days parameter '{days}'. Must be a number."
        else:
            days_int = 30  # Default to 30 days
            
        # Convert limit to int if provided
        limit_int = None
        if limit:
            try:
                limit_int = int(limit)
            except (ValueError, TypeError):
                return f"Error: Invalid limit parameter '{limit}'. Must be a number."
        
        # Use the shared FeedbackService for consistent behavior with CLI
        try:
            result = await FeedbackService.search_feedback(
                client=client,
                scorecard_name=scorecard_name,
                score_name=score_name,
                scorecard_id=scorecard_id,
                score_id=found_score_id,
                account_id=account_id,
                days=days_int,
                initial_value=initial_value,
                final_value=final_value,
                limit=limit_int,
                prioritize_edit_comments=prioritize_edit_comments
            )
            
            logger.info(f"Retrieved {result.context.total_found} feedback items using shared service")
            
        except Exception as e:
            logger.error(f"Error using FeedbackService: {e}")
            return f"Error retrieving feedback items: {e}"

        if not result.feedback_items:
            filter_desc = []
            if initial_value:
                filter_desc.append(f"initial value '{initial_value}'")
            if final_value:
                filter_desc.append(f"final value '{final_value}'")
            if filter_desc:
                filter_text = f" with {' and '.join(filter_desc)}"
            else:
                filter_text = ""
            return f"No feedback items found for score '{score_name}' in scorecard '{scorecard_name}'{filter_text} in the last {days_int} days."

        # Format output using the shared service - same structure as CLI tool
        result_dict = FeedbackService.format_search_result_as_dict(result)
        
        if output_format.lower() == "yaml":
            import yaml
            return yaml.dump(result_dict, default_flow_style=False, sort_keys=False)
        else:
            # Return the same JSON structure as the CLI tool would output
            return result_dict
        
    except Exception as e:
        logger.error(f"Error finding feedback items: {str(e)}", exc_info=True)
        return f"Error finding feedback items: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during plexus_feedback_find: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def plexus_predict(
    scorecard_name: str,
    score_name: str,
    item_id: Optional[str] = None,
    item_ids: Optional[str] = None,
    include_input: bool = False,
    include_trace: bool = False,
    output_format: str = "json",
    no_cache: bool = False,
    yaml_only: bool = False
) -> Union[str, Dict[str, Any]]:
    """
    Run predictions on one or more items using a specific score configuration.
    This helps test score behavior and validate improvements.
    
    Parameters:
    - scorecard_name: Name of the scorecard containing the score
    - score_name: Name of the specific score to run predictions with
    - item_id: ID of a single item to predict on (mutually exclusive with item_ids)
    - item_ids: Comma-separated list of item IDs to predict on (mutually exclusive with item_id)
    - include_input: Whether to include the original input text and metadata in output (default: False)  
    - include_trace: Whether to include detailed execution trace for debugging (default: False)
    - output_format: Output format - "json" or "yaml" (default: "json")
    - no_cache: If True, disable local caching entirely (always fetch from API) (default: False)
    - yaml_only: If True, load only from local YAML files without API calls (default: False)
    
    Returns:
    - Prediction results with scores, explanations, and optional input/trace data
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Validate input parameters
        if not item_id and not item_ids:
            return "Error: Either item_id or item_ids must be provided."
        if item_id and item_ids:
            return "Error: Cannot specify both item_id and item_ids. Use one or the other."
        if no_cache and yaml_only:
            return "Error: Cannot specify both no_cache and yaml_only. Use one or the other."
        
        # Try to import required modules directly
        try:
            from plexus.cli.client_utils import create_client as create_dashboard_client
            from plexus.cli.ScorecardCommands import resolve_scorecard_identifier
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
                    logger.warning(f"Captured unexpected stdout during client creation in plexus_predict: {client_output}")
                sys.stdout = saved_stdout
        except Exception as client_err:
            logger.error(f"Error creating dashboard client: {str(client_err)}", exc_info=True)
            return f"Error creating dashboard client: {str(client_err)}"
            
        if not client:
            return "Error: Could not create dashboard client."

        # Find the scorecard
        scorecard_id = resolve_scorecard_identifier(client, scorecard_name)
        if not scorecard_id:
            return f"Error: Scorecard '{scorecard_name}' not found."

        # Find the score within the scorecard
        scorecard_query = f"""
        query GetScorecardForPrediction {{
            getScorecard(id: "{scorecard_id}") {{
                id
                name
                sections {{
                    items {{
                        id
                        scores {{
                            items {{
                                id
                                name
                                key
                                externalId
                                championVersionId
                                isDisabled
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        scorecard_result = client.execute(scorecard_query)
        scorecard_data = scorecard_result.get('getScorecard')
        if not scorecard_data:
            return f"Error: Could not retrieve scorecard data for '{scorecard_name}'."

        # Find the specific score
        found_score = None
        for section in scorecard_data.get('sections', {}).get('items', []):
            for score in section.get('scores', {}).get('items', []):
                if (score.get('name') == score_name or 
                    score.get('key') == score_name or 
                    score.get('id') == score_name or 
                    score.get('externalId') == score_name):
                    found_score = score
                    break
            if found_score:
                break

        if not found_score:
            return f"Error: Score '{score_name}' not found within scorecard '{scorecard_name}'."

        # Prepare item IDs list
        if item_id:
            target_item_ids = [item_id]
        else:
            target_item_ids = [id.strip() for id in item_ids.split(',')]

        # Validate that all items exist and get their data
        prediction_results_list = []
        
        try:
            for target_id in target_item_ids:
                try:
                    # Get item details
                    item_query = f"""
                query GetItem {{
                    getItem(id: "{target_id}") {{
                        id
                        description
                        metadata
                        attachedFiles
                        externalId
                        createdAt
                        updatedAt
                    }}
                }}
                """
                    
                    item_result = client.execute(item_query)
                    item_data = item_result.get('getItem')
                    
                    if not item_data:
                        prediction_results_list.append({
                            "item_id": target_id,
                            "error": f"Item '{target_id}' not found"
                        })
                        continue

                    # Call the actual prediction service using the shared CLI implementation
                    logger.info(f"Running actual prediction for item '{target_id}' with score '{score_name}'")
                    
                    try:
                        # Get the item text content for prediction
                        item_text = item_data.get('text', '') or item_data.get('description', '')
                        if not item_text:
                            raise Exception("No text content found in item text or description fields")
                        
                        # Parse metadata from JSON string if needed
                        metadata_raw = item_data.get('metadata', {})
                        if isinstance(metadata_raw, str):
                            try:
                                import json
                                metadata = json.loads(metadata_raw)
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse metadata JSON: {metadata_raw}")
                                metadata = {}
                        else:
                            metadata = metadata_raw
                        
                        # Use the canonical Scorecard dependency system for all predictions
                        # This ensures consistent behavior with CLI, evaluations, and production
                        from plexus.Scorecard import Scorecard
                        
                        use_cache = not no_cache
                        cache_mode = "YAML-only" if yaml_only else ("no-cache" if no_cache else "default")
                        logger.info(f"Using canonical Scorecard system to predict '{score_name}' from '{scorecard_name}' with {cache_mode} mode")
                        
                        if yaml_only:
                            # For YAML-only mode, load scorecard from local files
                            logger.info("Loading scorecard from YAML files for dependency resolution")
                            scorecard_instance = Scorecard.load(scorecard_name, use_cache=use_cache, yaml_only=yaml_only)
                        else:
                            # For normal mode, use API data with caching
                            logger.info("Loading scorecard with API data for dependency resolution")
                            scorecard_instance = Scorecard.load(scorecard_name, use_cache=use_cache)
                        
                        # Use the battle-tested score_entire_text method which handles all dependency logic:
                        # - Builds dependency graphs automatically
                        # - Handles conditional dependencies (==, !=, in, not in)
                        # - Processes scores in correct dependency order
                        # - Skips scores when conditions aren't met
                        # - Handles async processing with proper error handling
                        logger.info(f"Running scorecard evaluation with canonical dependency resolution for score '{score_name}'")
                        
                        results = await scorecard_instance.score_entire_text(
                            text=item_text,
                            metadata=metadata,
                            modality=None,
                            subset_of_score_names=[score_name]  # This automatically includes dependencies
                        )
                        
                        # Extract the result for our target score
                        if results and score_name in results:
                            scorecard_result = results[score_name]
                            prediction_result = scorecard_result
                            logger.info(f"Successfully got result from canonical scorecard system for '{score_name}'")
                        else:
                            raise Exception(f"No result found for score '{score_name}' in scorecard evaluation. Available results: {list(results.keys()) if results else 'None'}")
                        
                        # Process results from canonical Scorecard system
                        # All results now come from scorecard_instance.score_entire_text()
                        prediction_results = prediction_result
                        
                        if prediction_results and hasattr(prediction_results, 'value') and prediction_results.value is not None:
                            explanation = (
                                getattr(prediction_results, 'explanation', None) or
                                prediction_results.metadata.get('explanation', '') if hasattr(prediction_results, 'metadata') and prediction_results.metadata else
                                ''
                            )
                            
                            # Extract costs from scorecard result
                            costs = {}
                            if hasattr(prediction_results, 'cost'):
                                costs = prediction_results.cost
                            elif hasattr(prediction_results, 'metadata') and prediction_results.metadata:
                                costs = prediction_results.metadata.get('cost', {})
                            
                            prediction_result = {
                                "item_id": target_id,
                                "scores": [
                                    {
                                        "name": score_name,
                                        "value": prediction_results.value,
                                        "explanation": explanation,
                                        "cost": costs
                                    }
                                ]
                            }
                            
                            # Extract trace information if available
                            if include_trace:
                                trace = None
                                if hasattr(prediction_results, 'trace'):
                                    trace = prediction_results.trace
                                elif hasattr(prediction_results, 'metadata') and prediction_results.metadata:
                                    trace = prediction_results.metadata.get('trace')
                                
                                if trace:
                                    prediction_result["scores"][0]["trace"] = trace
                        else:
                            raise Exception("No valid prediction value returned from canonical scorecard system")
                        
                    except Exception as pred_error:
                        logger.error(f"Error running actual prediction: {str(pred_error)}", exc_info=True)
                        # Fall back to indicating the error
                        prediction_result = {
                            "item_id": target_id,
                            "scores": [
                                {
                                    "name": score_name,
                                    "value": "Error",
                                    "explanation": f"Failed to execute prediction: {str(pred_error)}"
                                }
                            ]
                        }
                    
                    # Add input data if requested
                    if include_input:
                        prediction_result["input"] = {
                            "description": item_data.get('description'),
                            "metadata": item_data.get('metadata'),
                            "attachedFiles": item_data.get('attachedFiles'),
                            "externalId": item_data.get('externalId')
                        }
                                        
                    prediction_results_list.append(prediction_result)
                    
                except Exception as item_error:
                    logger.error(f"Error processing item '{target_id}': {str(item_error)}", exc_info=True)
                    prediction_results_list.append({
                        "item_id": target_id,
                        "error": f"Error processing item: {str(item_error)}"
                    })
        
        except Exception as loop_error:
            logger.error(f"Error in prediction loop: {str(loop_error)}", exc_info=True)
            return f"Error running predictions: {str(loop_error)}"

        # Format output based on requested format
        if output_format.lower() == "yaml":
            import yaml
            
            command_parts = [f"plexus predict --scorecard \"{scorecard_name}\" --score \"{score_name}\""]
            if item_id:
                command_parts.append(f"--item \"{item_id}\"")
            elif item_ids:
                command_parts.append(f"--items \"{item_ids}\"")
            if output_format.lower() == "yaml":
                command_parts.append("--format yaml")
            if include_input:
                command_parts.append("--input")
            if include_trace:
                command_parts.append("--trace")
            
            result = {
                "context": {
                    "description": "Output from plexus predict command",
                    "command": " ".join(command_parts),
                    "scorecard_id": scorecard_id,
                    "score_id": found_score['id'],
                    "item_count": len(target_item_ids)
                },
                "predictions": prediction_results_list
            }
            
            return yaml.dump(result, default_flow_style=False, sort_keys=False)
        else:
            # Return JSON format
            return {
                "success": True,
                "scorecard_name": scorecard_name,
                "score_name": score_name,
                "scorecard_id": scorecard_id,
                "score_id": found_score['id'],
                "score_version_id": found_score.get('championVersionId'),
                "item_count": len(target_item_ids),
                "options": {
                    "include_input": include_input,
                    "include_trace": include_trace,
                    "output_format": output_format
                },
                "predictions": prediction_results_list,
                "note": "This MCP tool executes real predictions using the shared Plexus prediction service."
            }
        
    except Exception as e:
        logger.error(f"Error running predictions: {str(e)}", exc_info=True)
        return f"Error running predictions: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during plexus_predict: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def get_plexus_documentation(filename: str) -> str:
    """
    Get documentation content for specific Plexus topics.
    
    Valid filenames:
    - score-yaml-format: Complete guide to Score YAML configuration format including LangGraph, node types, dependencies, and best practices
    - feedback-alignment: Complete guide to testing score results, finding feedback items, and analyzing prediction accuracy for score improvement
    - dataset-yaml-format: Complete guide to dataset YAML configuration format for data sources
    
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
            "score-yaml-format": "score-yaml-format.md",
            "feedback-alignment": "feedback-alignment.md",
            "dataset-yaml-format": "dataset-yaml-format.md"
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


async def _get_feedback_items_for_item(item_id: str, client) -> List[Dict[str, Any]]:
    """
    Helper function to get all feedback items for a specific item, sorted by updatedAt descending.
    This mirrors the functionality from the CLI ItemCommands.get_feedback_items_for_item function.
    """
    try:
        from plexus.dashboard.api.models.feedback_item import FeedbackItem
        from datetime import datetime
        
        # Use the FeedbackItem.list method with filtering
        feedback_items, _ = FeedbackItem.list(
            client=client,
            filter={'itemId': {'eq': item_id}},
            limit=1000
        )
        
        # Convert to dictionary format and sort by updatedAt descending
        feedback_items_list = []
        for fi in feedback_items:
            fi_dict = {
                'id': fi.id,
                'accountId': fi.accountId,
                'scorecardId': fi.scorecardId,
                'scoreId': fi.scoreId,
                'itemId': fi.itemId,
                'cacheKey': fi.cacheKey,
                'initialAnswerValue': fi.initialAnswerValue,
                'finalAnswerValue': fi.finalAnswerValue,
                'initialCommentValue': fi.initialCommentValue,
                'finalCommentValue': fi.finalCommentValue,
                'editCommentValue': fi.editCommentValue,
                'isAgreement': fi.isAgreement,
                'editorName': fi.editorName,
                'editedAt': fi.editedAt.isoformat() if hasattr(fi.editedAt, 'isoformat') and fi.editedAt else fi.editedAt,
                'createdAt': fi.createdAt.isoformat() if hasattr(fi.createdAt, 'isoformat') and fi.createdAt else fi.createdAt,
                'updatedAt': fi.updatedAt.isoformat() if hasattr(fi.updatedAt, 'isoformat') and fi.updatedAt else fi.updatedAt,
            }
            feedback_items_list.append(fi_dict)
        
        # Sort by updatedAt descending
        feedback_items_list.sort(
            key=lambda fi: fi.get('updatedAt', '1970-01-01T00:00:00'),
            reverse=True
        )
        
        return feedback_items_list
        
    except Exception as e:
        logger.error(f"Error getting feedback items for item {item_id}: {str(e)}", exc_info=True)
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
    base_url = os.environ.get('PLEXUS_APP_URL', 'https://plexus.anth.us')
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
        if not PLEXUS_CORE_AVAILABLE:
            return "Error: Plexus Dashboard components are not available. Core modules failed to import."
        
        # Ensure project root is in Python path for ScoreService import
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


@mcp.tool()
async def plexus_evaluation_info(
    evaluation_id: str,
    include_score_results: bool = False
) -> str:
    """
    Get detailed information about a specific evaluation by its ID.
    
    This tool provides comprehensive information about an evaluation including:
    - Basic details (ID, type, status)
    - Scorecard and score names (resolved from IDs)
    - Progress and metrics information
    - Timing details
    - Error information (if any)
    - Cost information
    
    Parameters:
    - evaluation_id: The unique ID of the evaluation to look up
    - include_score_results: Whether to include score results information (default: False)
    
    Returns:
    - Formatted string with comprehensive evaluation information
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Import the evaluation functionality
        try:
            from plexus.Evaluation import Evaluation
        except ImportError as e:
            return f"Import error: Could not import Evaluation class: {str(e)}"
        
        if not evaluation_id or not evaluation_id.strip():
            return "Error: evaluation_id is required"
        
        try:
            # Get evaluation information using the shared method
            evaluation_info = Evaluation.get_evaluation_info(evaluation_id, include_score_results)
            
            # Format the output in a readable way
            output_lines = []
            output_lines.append("=== Evaluation Information ===")
            output_lines.append(f"ID: {evaluation_info['id']}")
            output_lines.append(f"Type: {evaluation_info['type']}")
            output_lines.append(f"Status: {evaluation_info['status']}")
            
            if evaluation_info['scorecard_name']:
                output_lines.append(f"Scorecard: {evaluation_info['scorecard_name']}")
            elif evaluation_info['scorecard_id']:
                output_lines.append(f"Scorecard ID: {evaluation_info['scorecard_id']}")
            else:
                output_lines.append("Scorecard: Not specified")
                
            if evaluation_info['score_name']:
                output_lines.append(f"Score: {evaluation_info['score_name']}")
            elif evaluation_info['score_id']:
                output_lines.append(f"Score ID: {evaluation_info['score_id']}")
            else:
                output_lines.append("Score: Not specified")
            
            output_lines.append("\n=== Progress & Metrics ===")
            if evaluation_info['total_items']:
                output_lines.append(f"Total Items: {evaluation_info['total_items']}")
            if evaluation_info['processed_items'] is not None:
                output_lines.append(f"Processed Items: {evaluation_info['processed_items']}")
            if evaluation_info['accuracy'] is not None:
                output_lines.append(f"Accuracy: {evaluation_info['accuracy']:.2f}%")
            
            if evaluation_info['metrics']:
                output_lines.append("\n=== Detailed Metrics ===")
                for metric in evaluation_info['metrics']:
                    if isinstance(metric, dict) and 'name' in metric and 'value' in metric:
                        output_lines.append(f"{metric['name']}: {metric['value']:.2f}")
                    else:
                        output_lines.append(f"Metric: {metric}")
            
            output_lines.append("\n=== Timing ===")
            if evaluation_info['started_at']:
                output_lines.append(f"Started At: {evaluation_info['started_at']}")
            if evaluation_info['elapsed_seconds']:
                output_lines.append(f"Elapsed Time: {evaluation_info['elapsed_seconds']} seconds")
            if evaluation_info['estimated_remaining_seconds']:
                output_lines.append(f"Estimated Remaining: {evaluation_info['estimated_remaining_seconds']} seconds")
            
            output_lines.append("\n=== Timestamps ===")
            output_lines.append(f"Created At: {evaluation_info['created_at']}")
            output_lines.append(f"Updated At: {evaluation_info['updated_at']}")
            
            if evaluation_info['cost']:
                output_lines.append("\n=== Cost ===")
                output_lines.append(f"Total Cost: ${evaluation_info['cost']:.6f}")
            
            if evaluation_info['error_message']:
                output_lines.append("\n=== Error Information ===")
                output_lines.append(f"Error Message: {evaluation_info['error_message']}")
                if evaluation_info['error_details']:
                    output_lines.append(f"Error Details: {evaluation_info['error_details']}")
            
            if evaluation_info['task_id']:
                output_lines.append("\n=== Task ===")
                output_lines.append(f"Task ID: {evaluation_info['task_id']}")
                
            if include_score_results and evaluation_info.get('score_results_available'):
                output_lines.append("\n=== Score Results ===")
                output_lines.append("Score results functionality available (can be implemented if needed)")
            
            return "\n".join(output_lines)
            
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Unexpected error getting evaluation info: {str(e)}"
            
    except Exception as e:
        return f"Unexpected error: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during plexus_evaluation_info: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def plexus_evaluation_last(
    account_key: str = 'call-criteria',
    evaluation_type: str = ""
) -> str:
    """
    Get information about the most recent evaluation.
    
    This tool finds and returns detailed information about the latest evaluation,
    optionally filtered by evaluation type (e.g., 'accuracy', 'consistency').
    
    Parameters:
    - account_key: Account key to filter by (default: 'call-criteria')
    - evaluation_type: Optional filter by evaluation type (e.g., 'accuracy', 'consistency')
    
    Returns:
    - Formatted string with comprehensive information about the latest evaluation
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Import the evaluation functionality
        try:
            from plexus.Evaluation import Evaluation
        except ImportError as e:
            return f"Import error: Could not import Evaluation class: {str(e)}"
        
        # Convert empty string to None for evaluation_type filter
        eval_type_filter = evaluation_type.strip() if evaluation_type and evaluation_type.strip() else None
        
        try:
            # Get latest evaluation information using the shared method
            latest_evaluation = Evaluation.get_latest_evaluation(account_key, eval_type_filter)
            
            if not latest_evaluation:
                if eval_type_filter:
                    return f"No evaluations found for account '{account_key}' with type '{eval_type_filter}'"
                else:
                    return f"No evaluations found for account '{account_key}'"
            
            # Format the output in a readable way (same as info command)
            output_lines = []
            output_lines.append("=== Latest Evaluation Information ===")
            output_lines.append(f"ID: {latest_evaluation['id']}")
            output_lines.append(f"Type: {latest_evaluation['type']}")
            output_lines.append(f"Status: {latest_evaluation['status']}")
            
            if latest_evaluation['scorecard_name']:
                output_lines.append(f"Scorecard: {latest_evaluation['scorecard_name']}")
            elif latest_evaluation['scorecard_id']:
                output_lines.append(f"Scorecard ID: {latest_evaluation['scorecard_id']}")
            else:
                output_lines.append("Scorecard: Not specified")
                
            if latest_evaluation['score_name']:
                output_lines.append(f"Score: {latest_evaluation['score_name']}")
            elif latest_evaluation['score_id']:
                output_lines.append(f"Score ID: {latest_evaluation['score_id']}")
            else:
                output_lines.append("Score: Not specified")
            
            output_lines.append("\n=== Progress & Metrics ===")
            if latest_evaluation['total_items']:
                output_lines.append(f"Total Items: {latest_evaluation['total_items']}")
            if latest_evaluation['processed_items'] is not None:
                output_lines.append(f"Processed Items: {latest_evaluation['processed_items']}")
            if latest_evaluation['accuracy'] is not None:
                output_lines.append(f"Accuracy: {latest_evaluation['accuracy']:.2f}%")
            
            if latest_evaluation['metrics']:
                output_lines.append("\n=== Detailed Metrics ===")
                for metric in latest_evaluation['metrics']:
                    if isinstance(metric, dict) and 'name' in metric and 'value' in metric:
                        output_lines.append(f"{metric['name']}: {metric['value']:.2f}")
                    else:
                        output_lines.append(f"Metric: {metric}")
            
            output_lines.append("\n=== Timing ===")
            if latest_evaluation['started_at']:
                output_lines.append(f"Started At: {latest_evaluation['started_at']}")
            if latest_evaluation['elapsed_seconds']:
                output_lines.append(f"Elapsed Time: {latest_evaluation['elapsed_seconds']} seconds")
            if latest_evaluation['estimated_remaining_seconds']:
                output_lines.append(f"Estimated Remaining: {latest_evaluation['estimated_remaining_seconds']} seconds")
            
            output_lines.append("\n=== Timestamps ===")
            output_lines.append(f"Created At: {latest_evaluation['created_at']}")
            output_lines.append(f"Updated At: {latest_evaluation['updated_at']}")
            
            if latest_evaluation['cost']:
                output_lines.append("\n=== Cost ===")
                output_lines.append(f"Total Cost: ${latest_evaluation['cost']:.6f}")
            
            if latest_evaluation['error_message']:
                output_lines.append("\n=== Error Information ===")
                output_lines.append(f"Error Message: {latest_evaluation['error_message']}")
                if latest_evaluation['error_details']:
                    output_lines.append(f"Error Details: {latest_evaluation['error_details']}")
            
            if latest_evaluation['task_id']:
                output_lines.append("\n=== Task ===")
                output_lines.append(f"Task ID: {latest_evaluation['task_id']}")
            
            return "\n".join(output_lines)
            
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Unexpected error getting latest evaluation: {str(e)}"
            
    except Exception as e:
        return f"Unexpected error: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during plexus_evaluation_last: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout

@mcp.tool()
async def plexus_dataset_load(
    source_identifier: str,
    fresh: bool = False
) -> str:
    """
    Load a dataset from a DataSource using the existing CLI functionality.
    
    This tool reuses the core dataset loading logic from the CLI command to ensure DRY principles.
    It loads a dataframe from the specified data source, generates a Parquet file,
    and creates a new DataSet record in the database.
    
    Parameters:
    - source_identifier: Identifier (ID, key, or name) of the DataSource to load
    - fresh: Force a fresh load, ignoring any caches (default: False)
    
    Returns:
    - Status message indicating success/failure and dataset information
    """
    # Temporarily redirect stdout to capture any unexpected output
    old_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Import the core dataset loading functionality
        try:
            from plexus.cli.DatasetCommands import create_client
            from plexus.cli.identifier_resolution import resolve_data_source
            from plexus.cli.DatasetCommands import create_initial_data_source_version, get_amplify_bucket
            import yaml
            import pandas as pd
            import pyarrow as pa
            import pyarrow.parquet as pq
            from io import BytesIO
            from datetime import datetime, timezone
            import importlib
            import boto3
            from botocore.exceptions import NoCredentialsError
        except ImportError as e:
            return f"Error: Could not import required modules: {e}. Dataset loading functionality may not be available."
        
        # Create client using the existing function
        client = create_client()
        
        # Reuse the core dataset loading logic from DatasetCommands.py
        # This is the exact same logic as in the CLI command's _load() function
        
        # 1. Fetch the DataSource
        logger.info(f"Resolving DataSource with identifier: {source_identifier}")
        data_source = await resolve_data_source(client, source_identifier)
        if not data_source:
            return f"Error: Could not resolve DataSource with identifier: {source_identifier}"
        
        logger.info(f"Found DataSource: {data_source.name} (ID: {data_source.id})")

        # 2. Parse YAML configuration
        if not data_source.yamlConfiguration:
            return f"Error: DataSource '{data_source.name}' has no yamlConfiguration."

        try:
            config = yaml.safe_load(data_source.yamlConfiguration)
        except yaml.YAMLError as e:
            return f"Error parsing yamlConfiguration: {e}"

        if not isinstance(config, dict):
            return f"Error: yamlConfiguration must be a YAML dictionary, but got {type(config).__name__}: {config}"

        # Handle both scorecard format (with 'data' section) and dataset format (direct config)
        data_config = config.get('data')
        if not data_config:
            # Check if this is a direct dataset configuration (recommended format)
            if 'class' in config:
                logger.info("Detected direct dataset configuration format")
                
                # Handle built-in Plexus classes vs client-specific extensions
                class_name = config['class']
                if class_name in ['FeedbackItems']:
                    # Built-in Plexus classes (single file modules)
                    class_path = f"plexus.data.{class_name}"
                else:
                    # Client-specific extensions (existing behavior)
                    class_path = f"plexus_extensions.{class_name}.{class_name}"
                
                data_config = {
                    'class': class_path,
                    'parameters': {k: v for k, v in config.items() if k != 'class'}
                }
            else:
                return "Error: No 'data' section in yamlConfiguration and no 'class' specified."

        # 3. Dynamically load DataCache class
        data_cache_class_path = data_config.get('class')
        if not data_cache_class_path:
            return "Error: No 'class' specified in data configuration."

        try:
            module_path, class_name = data_cache_class_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            data_cache_class = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            return f"Error: Could not import data cache class '{data_cache_class_path}': {e}"

        # 4. Load dataframe
        logger.info(f"Loading dataframe using {data_cache_class_path}...")
        data_cache_params = data_config.get('parameters', {})
        data_cache = data_cache_class(**data_cache_params)

        # Pass the parameters to load_dataframe
        dataframe = data_cache.load_dataframe(data=data_cache_params, fresh=fresh)
        logger.info(f"Loaded dataframe with {len(dataframe)} rows and columns: {dataframe.columns.tolist()}")

        # 5. Generate Parquet file in memory
        if dataframe.empty:
            return "Warning: Dataframe is empty, no dataset created."

        logger.info("Generating Parquet file in memory...")
        buffer = BytesIO()
        table = pa.Table.from_pandas(dataframe)
        pq.write_table(table, buffer)
        buffer.seek(0)
        logger.info("Parquet file generated successfully.")

        # 6. Get the current DataSource version and resolve score version
        logger.info("Creating new DataSet record...")
        
        if not hasattr(data_source, 'accountId') or not data_source.accountId:
            return "Error: DataSource is missing accountId. Cannot proceed."
        account_id = data_source.accountId

        # Get the current version of the DataSource, creating one if it doesn't exist
        if not data_source.currentVersionId:
            logger.info("DataSource has no currentVersionId. Creating initial version...")
            data_source_version_id = await create_initial_data_source_version(client, data_source)
            if not data_source_version_id:
                return "Error: Failed to create initial DataSource version."
        else:
            data_source_version_id = data_source.currentVersionId
            logger.info(f"Using existing DataSource version ID: {data_source_version_id}")

        # Get the score version - use the score linked to the DataSource if available (optional)
        score_version_id = None
        if hasattr(data_source, 'scoreId') and data_source.scoreId:
            logger.info(f"DataSource is linked to score ID: {data_source.scoreId}")
            # Get the champion version of this score
            score_query = client.execute(
                """
                query GetScore($id: ID!) {
                    getScore(id: $id) {
                        id
                        name
                        championVersionId
                    }
                }
                """,
                {"id": data_source.scoreId}
            )
            
            if score_query and score_query.get('getScore') and score_query['getScore'].get('championVersionId'):
                score_version_id = score_query['getScore']['championVersionId']
                logger.info(f"Using champion version ID: {score_version_id}")
            else:
                logger.warning(f"Score {data_source.scoreId} has no champion version. Creating DataSet without score version.")
        else:
            logger.info("DataSource is not linked to a specific score. Creating DataSet without score version.")

        # Create a DataSet linked to the DataSource version and optionally to a score version
        dataset_input = {
            "name": f"{data_source.name} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
            "accountId": account_id,
            "dataSourceVersionId": data_source_version_id,
        }
        
        # Add optional fields only if they have values
        if score_version_id:
            dataset_input["scoreVersionId"] = score_version_id
        if hasattr(data_source, 'scorecardId') and data_source.scorecardId:
            dataset_input["scorecardId"] = data_source.scorecardId
        if hasattr(data_source, 'scoreId') and data_source.scoreId:
            dataset_input["scoreId"] = data_source.scoreId
            
        new_dataset_record = client.execute(
            """
            mutation CreateDataSet($input: CreateDataSetInput!) {
                createDataSet(input: $input) {
                    id
                    name
                    dataSourceVersionId
                    scoreVersionId
                }
            }
            """,
            {
                "input": dataset_input
            }
        )
        new_dataset = new_dataset_record['createDataSet']
        new_dataset_id = new_dataset['id']
        
        logger.info(f"Created DataSet record with ID: {new_dataset_id}")

        # 7. Upload Parquet to S3
        file_name = "dataset.parquet"
        s3_key = f"datasets/{account_id}/{new_dataset_id}/{file_name}"
        
        logger.info(f"Uploading Parquet file to S3 at: {s3_key}")
        
        bucket_name = get_amplify_bucket()
        if not bucket_name:
             logger.error("S3 bucket name not found. Cannot upload file.")
             client.execute("""
                mutation UpdateDataSet($input: UpdateDataSetInput!) {
                    updateDataSet(input: $input) { id }
                }
             """, {"input": {"id": new_dataset_id, "description": "FAILED: S3 bucket not configured."}})
             return "Error: S3 bucket name not found. Cannot upload file."

        try:
            s3_client = boto3.client('s3')
            s3_client.upload_fileobj(buffer, bucket_name, s3_key)
            logger.info("File uploaded successfully to S3.")
        except NoCredentialsError:
            return "Error: AWS credentials not found."
        except Exception as e:
            logger.error(f"Failed to upload file to S3: {e}")
            client.execute("""
               mutation UpdateDataSet($input: UpdateDataSetInput!) {
                   updateDataSet(input: $input) { id }
               }
            """, {"input": {"id": new_dataset_id, "description": f"FAILED: S3 upload failed: {e}"}})
            return f"Error: Failed to upload file to S3: {e}"

        # 8. Update DataSet with file path
        logger.info(f"Updating DataSet record with file path...")
        client.execute(
            """
            mutation UpdateDataSet($input: UpdateDataSetInput!) {
                updateDataSet(input: $input) {
                    id
                    file
                }
            }
            """,
            {
                "input": {
                    "id": new_dataset_id,
                    "file": s3_key,
                }
            }
        )
        logger.info("DataSet record updated successfully.")
        
        return f"Successfully loaded dataset '{data_source.name}':\n" + \
               f"- DataSet ID: {new_dataset_id}\n" + \
               f"- Rows: {len(dataframe)}\n" + \
               f"- Columns: {dataframe.columns.tolist()}\n" + \
               f"- S3 Path: {s3_key}\n" + \
               f"- Fresh Load: {fresh}"

    except Exception as e:
        logger.error(f"Error in dataset load: {str(e)}", exc_info=True)
        return f"Error loading dataset: {str(e)}"
    finally:
        # Check if anything was written to stdout
        captured_output = temp_stdout.getvalue()
        if captured_output:
            logger.warning(f"Captured unexpected stdout during dataset_load: {captured_output}")
        # Restore original stdout
        sys.stdout = old_stdout


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