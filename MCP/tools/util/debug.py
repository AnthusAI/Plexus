#!/usr/bin/env python3
"""
Debug utilities for Plexus MCP server
"""
import os
import sys
import traceback
from io import StringIO
from fastmcp import FastMCP
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.setup import logger, PLEXUS_CORE_AVAILABLE

def register_debug_tools(mcp: FastMCP):
    """Register debug tools with the MCP server"""
    
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
        mcp_dir = os.path.dirname(os.path.dirname(os.path.dirname(mcp_file)))
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
                # Navigate from MCP/tools/util to plexus/docs/
                current_dir = os.path.dirname(os.path.abspath(__file__))
                mcp_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                plexus_dir = os.path.dirname(mcp_dir)
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