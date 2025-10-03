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

# Completely disable Rich logging for stdio transport to prevent BrokenPipeError
using_stdio = os.environ.get('MCP_STDIO_TRANSPORT') == '1' or '--transport' in sys.argv and 'stdio' in sys.argv
if using_stdio:
    # Set environment variables to disable Rich
    os.environ['RICH_NO_COLOR'] = '1'
    os.environ['RICH_CONSOLE_NO_COLOR'] = '1'
    os.environ['RICH_TRACEBACKS_NO_COLOR'] = '1'
    os.environ['RICH_FORCE_TERMINAL'] = '0'
    os.environ['RICH_DISABLE'] = '1'
    os.environ['TERM'] = 'dumb'
    
    # Completely disable Rich by monkey patching before any imports
    import types
    
    # Create a dummy module that replaces rich
    class DummyRichModule(types.ModuleType):
        def __getattr__(self, name):
            # Return a dummy object for any attribute access
            return DummyRichObject()
    
    class DummyRichObject:
        def __init__(self, *args, **kwargs):
            pass
        def __call__(self, *args, **kwargs):
            return self
        def __getattr__(self, name):
            return self
        def __setattr__(self, name, value):
            pass
        def __lt__(self, other):
            return True
        def __le__(self, other):
            return True
        def __eq__(self, other):
            return True
        def __ne__(self, other):
            return False
        def __gt__(self, other):
            return False
        def __ge__(self, other):
            return True
        def __iter__(self):
            # Make DummyRichObject iterable to prevent 'not iterable' errors
            return iter([])
        def __len__(self):
            return 0
        def __getitem__(self, key):
            return self
        def __setitem__(self, key, value):
            pass
    
    # Replace the rich module in sys.modules BEFORE importing FastMCP
    sys.modules['rich'] = DummyRichModule('rich')
    sys.modules['rich.console'] = DummyRichModule('rich.console')
    sys.modules['rich.logging'] = DummyRichModule('rich.logging')
    sys.modules['rich.table'] = DummyRichModule('rich.table')
    sys.modules['rich.traceback'] = DummyRichModule('rich.traceback')
    sys.modules['rich.markdown'] = DummyRichModule('rich.markdown')
    sys.modules['rich.panel'] = DummyRichModule('rich.panel')
    sys.modules['rich.text'] = DummyRichModule('rich.text')
    sys.modules['rich.progress'] = DummyRichModule('rich.progress')
    sys.modules['rich.prompt'] = DummyRichModule('rich.prompt')
    sys.modules['rich.status'] = DummyRichModule('rich.status')
    sys.modules['rich.syntax'] = DummyRichModule('rich.syntax')
    sys.modules['rich.tree'] = DummyRichModule('rich.tree')
    sys.modules['rich.align'] = DummyRichModule('rich.align')
    sys.modules['rich.columns'] = DummyRichModule('rich.columns')
    sys.modules['rich.group'] = DummyRichModule('rich.group')
    sys.modules['rich.layout'] = DummyRichModule('rich.layout')
    sys.modules['rich.live'] = DummyRichModule('rich.live')
    sys.modules['rich.rule'] = DummyRichModule('rich.rule')
    sys.modules['rich.spinner'] = DummyRichModule('rich.spinner')
    sys.modules['rich.style'] = DummyRichModule('rich.style')
    sys.modules['rich.theme'] = DummyRichModule('rich.theme')
    sys.modules['rich.box'] = DummyRichModule('rich.box')
    sys.modules['rich.color'] = DummyRichModule('rich.color')
    sys.modules['rich.console'] = DummyRichModule('rich.console')
    sys.modules['rich.measure'] = DummyRichModule('rich.measure')
    sys.modules['rich.padding'] = DummyRichModule('rich.padding')
    sys.modules['rich.region'] = DummyRichModule('rich.region')
    sys.modules['rich.segment'] = DummyRichModule('rich.segment')
    sys.modules['rich.spacing'] = DummyRichModule('rich.spacing')
    sys.modules['rich.terminal_theme'] = DummyRichModule('rich.terminal_theme')
    
    # Configure FastMCP to not use Rich
    import fastmcp
    fastmcp.settings.enable_rich_tracebacks = False
    
    # Force basic logging configuration and replace Rich handlers
    import logging
    
    # Remove any existing Rich handlers
    for handler in logging.root.handlers[:]:
        if 'rich' in str(type(handler)).lower():
            logging.root.removeHandler(handler)
    
    # Force basic logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s  [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(sys.stderr)],
        force=True
    )
    
    # Disable Rich loggers
    logging.getLogger("rich").disabled = True
    logging.getLogger("rich.logging").disabled = True
    logging.getLogger("rich.console").disabled = True

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
CORE_IMPORTED = False
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
        from plexus.cli.shared.client_utils import create_client as _create_dashboard_client
        from plexus.cli.scorecard.scorecards import resolve_account_identifier as _resolve_account_identifier
        from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier as _resolve_scorecard_identifier
        
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
        CORE_IMPORTED = True
        logger.info("Plexus core modules imported successfully.")
    except ImportError as e:
        logger.error(f"Could not import core Plexus modules: {e}.")
        raise
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

# Require core before continuing
if not CORE_IMPORTED:
    logger.error("Plexus core not available")
    raise RuntimeError("Plexus core not available")

# Create FastMCP instance
mcp = FastMCP(
    name="Plexus MCP Server",
    instructions="""
    Access Plexus Dashboard functionality, run evaluations, and manage scorecards.
    
    ## Scorecard Management
    - plexus_scorecards_list: List available scorecards with optional filtering by name or key
    - plexus_scorecard_info: Get detailed information about a specific scorecard, including sections and scores
    
    ## Score Management
    - plexus_score_info: Get detailed information about a specific score, including location, configuration, champion version details, and version history. Supports intelligent search across scorecards.
    - plexus_score_update: **RECOMMENDED** - Update a score's configuration by creating a new version with provided YAML content. Supports parent_version_id for version lineage. Use this for most score updates.
    - plexus_score_pull: Pull a score's champion version YAML configuration to a local file (for local development workflows)
    - plexus_score_push: Push a score's local YAML configuration file to create a new version (for local development workflows)
    - plexus_score_delete: Delete a specific score by ID (uses shared ScoreService - includes safety confirmation step)
    
    ## Evaluation Tools
    - plexus_evaluation_run: Run an accuracy evaluation on a Plexus scorecard using the same code path as the CLI. 
      The server will confirm dispatch but will not track progress or results. 
      Monitor evaluation status via Plexus Dashboard or system logs.
    - plexus_evaluation_info: Get detailed information about a specific evaluation by ID or get the latest evaluation.
      Supports multiple output formats (json, yaml, text) and optional examples/quadrants.
    
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
    - plexus_feedback_analysis: Generate comprehensive feedback analysis with confusion matrix, accuracy, and AC1 agreement - RUN THIS FIRST to understand overall performance before using find
    - plexus_feedback_find: Find feedback items where human reviewers corrected predictions to identify score improvement opportunities
    - plexus_predict: Run predictions on single or multiple items using specific score configurations for testing and validation
    
    ## Documentation Tools
    - get_plexus_documentation: Access specific documentation files by name (e.g., 'score-yaml-format' for Score YAML configuration guide, 'feedback-alignment' for feedback analysis and score testing guide)
    
    ## Experiment Tools
    - plexus_procedure_create: Create a new procedure
    - plexus_procedure_list: List procedures for an account
    - plexus_procedure_info: Get detailed procedure information
    - plexus_procedure_run: Run a procedure 
    - plexus_procedure_chat_sessions: Get chat sessions for a procedure (optional - shows conversation activity)
    - plexus_procedure_chat_messages: Get detailed chat messages for debugging conversation flow and tool calls/responses
    
    ## Utility Tools
    - think: REQUIRED tool to use before other tools to structure reasoning and plan approach
    """
)

# --- Tool Registrations ---

# Register tools from separate modules
try:
    from tools.util.think import register_think_tool
    from tools.scorecard.scorecards import register_scorecard_tools
    from tools.report.reports import register_report_tools
    from tools.score.scores import register_score_tools
    from tools.item.items import register_item_tools
    from tools.task.tasks import register_task_tools
    from tools.feedback.feedback import register_feedback_tools
    from tools.evaluation.evaluations import register_evaluation_tools
    from tools.prediction.predictions import register_prediction_tools
    from tools.documentation.docs import register_documentation_tools
    from tools.cost.analysis import register_cost_analysis_tools
    from tools.dataset.datasets import register_dataset_tools
    from tools.procedure.procedures import register_procedure_tools
    
    register_think_tool(mcp)
    register_scorecard_tools(mcp)
    register_report_tools(mcp)
    register_score_tools(mcp)
    register_item_tools(mcp)
    register_task_tools(mcp)
    register_feedback_tools(mcp)
    register_evaluation_tools(mcp)
    register_prediction_tools(mcp)
    register_documentation_tools(mcp)
    register_cost_analysis_tools(mcp)
    register_dataset_tools(mcp)
    register_procedure_tools(mcp)
    
    logger.info("Successfully registered separated tools")
except ImportError as e:
    logger.warning(f"Could not import separated tools: {e}")
except Exception as e:
    logger.error(f"Error registering separated tools: {e}", exc_info=True)

# --- Tool Implementations ---























# Note: .env file loading is no longer needed - Plexus uses config files and environment variables

def initialize_default_account():
    """Initialize the default account ID from the environment variable PLEXUS_ACCOUNT_KEY."""
    global DEFAULT_ACCOUNT_ID, DEFAULT_ACCOUNT_KEY
    
    # Get account key from environment
    account_key = os.environ.get('PLEXUS_ACCOUNT_KEY')
    if not account_key:
        logger.warning("PLEXUS_ACCOUNT_KEY environment variable not set")
        return
    
    DEFAULT_ACCOUNT_KEY = account_key
    
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




# Main function to run the server
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Plexus MCP Server with FastMCP")

    parser.add_argument("--host", default="127.0.0.1", help="Host to run server on")
    parser.add_argument("--port", type=int, default=8002, help="Port to run server on")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="sse", 
                        help="Transport protocol (stdio for MCP process or sse for HTTP)")
    args = parser.parse_args()
    
    # Load Plexus configuration (including secrets) using DRY configuration loader
    try:
        from plexus.config.loader import load_config
        load_config()  # This loads .plexus/config.yaml and sets environment variables
        logger.info("Loaded Plexus configuration at MCP server startup")
    except Exception as e:
        logger.warning(f"Failed to load Plexus configuration: {e}")
    
    # Credentials are now handled by Plexus config files and environment variables
    
    # Require core and initialize default account
    if not CORE_IMPORTED:
        logger.error("Plexus core not available")
        sys.exit(1)
    logger.info("Initializing default account from environment...")
    initialize_default_account()
    
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