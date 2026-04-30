#!/usr/bin/env python3
"""
Plexus MCP Server using FastMCP - A refactored implementation with modular tools
"""
import sys
from fastmcp import FastMCP

# Import shared setup and utilities
from shared.setup import setup_plexus_imports, restore_stdout, redirect_stdout_to_stderr, logger
from shared.utils import load_env_file, initialize_default_account, get_default_account_id

# Import tool registration functions
from tools.tactus_runtime.execute import register_tactus_tools

# Setup Plexus imports and core functionality
setup_plexus_imports()

# Create FastMCP instance
mcp = FastMCP(
    name="Plexus MCP Server",
    instructions="""
    Plexus is a programmable AI-scoring runtime.  Use the single `execute_tactus`
    tool to interact with it via the `plexus.*` namespaces.

    Call `return plexus.api.list()` to discover all available namespaces and methods.
    Call `return plexus.docs.list({})` to list available documentation topics.
    """
)

# Register all tools with the MCP server
def register_all_tools():
    """Register MCP tools with the server."""
    logger.info("Registering MCP tools...")
    register_tactus_tools(mcp)
    logger.info("Registered execute_tactus tool")

# Function to run the server
def run_server(args):
    """Run the MCP server with the given arguments"""
    # Load environment variables from .env file if specified
    if args.env_dir:
        load_env_file(args.env_dir)

    # Register all tools
    register_all_tools()

    # Initialize default account as early as possible after env vars are loaded
    # but after the Plexus core is available
    logger.info("Initializing default account from environment...")
    initialize_default_account()

    # Setup global exception handler for uncaught exceptions
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception

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
