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
from tools.util.debug import register_debug_tools
from tools.scorecard.scorecards import register_scorecard_tools
from tools.score.management import register_score_tools

# Setup Plexus imports and core functionality
PLEXUS_CORE_AVAILABLE = setup_plexus_imports()

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

# Register all tools with the MCP server
def register_all_tools():
    """Register all MCP tools with the server"""
    logger.info("Registering MCP tools...")
    
    # Register utility tools
    register_debug_tools(mcp)
    logger.info("Registered debug/utility tools")
    
    # Register scorecard tools
    register_scorecard_tools(mcp)
    logger.info("Registered scorecard tools")
    
    # Register score management tools
    register_score_tools(mcp)
    logger.info("Registered score management tools")
    
    # TODO: Register additional tool modules here as they are created
    # register_report_tools(mcp)
    # register_item_tools(mcp)
    # register_task_tools(mcp)
    # register_feedback_tools(mcp)
    
    logger.info("All MCP tools registered successfully")

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