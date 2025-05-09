#!/usr/bin/env python3
import os
import sys
import json
import asyncio
import logging
import argparse
from typing import Dict, Any, List, Union, Optional

# Use mcp.server library components
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

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


# Create the Server instance
# Use a more specific name now that Plexus code is included
server = Server("Plexus MCP Server", "0.3.0")

# --- Tool Definitions (Dictionaries) ---

HELLO_WORLD_TOOL_DEF = {
    "name": "hello_world",
    "description": "A simple tool that returns a greeting.",
    "inputSchema": { # Note: Correct casing
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name to greet."}
        },
        "required": ["name"]
    }
}

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
    }
}

# --- Tool Implementation Function (Hello World) ---
def hello_world_impl(name: str) -> str:
    return f"Hello, {name}! This is the Plexus MCP server using mcp.server library."

# --- MCP Server Handlers using Decorators ---

@server.list_tools()
async def list_tools() -> List[Tool]:
    """Returns the list of available tools."""
    tools = [
        Tool(**HELLO_WORLD_TOOL_DEF),
        Tool(**LIST_PLEXUS_SCORECARDS_TOOL_DEF)
        # Add other Plexus tool definitions here later
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
        if name == "hello_world":
            name_arg = arguments.get("name")
            if not name_arg:
                raise ValueError("Missing required argument: name")
            result = hello_world_impl(name=name_arg)

        elif name == "list_plexus_scorecards":
            # Always use dashboard without local fallback
            result = list_dashboard_scorecards(
                account=arguments.get("account"),
                name=arguments.get("name"),
                key=arguments.get("key"),
                limit=arguments.get("limit") 
            )
        
        # Add other tool handlers here later
        # elif name == "get_plexus_scorecard_info":
        #     ...
        # elif name == "run_plexus_evaluation":
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
        await server.run(read_stream, write_stream, options, raise_exceptions=True)
        logger.info("MCP Server finished.")

if __name__ == "__main__":
    # Basic argument parsing primarily for compatibility with the wrapper script
    parser = argparse.ArgumentParser(description="Plexus MCP Server (Library)")
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