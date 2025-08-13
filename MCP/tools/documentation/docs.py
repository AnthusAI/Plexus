#!/usr/bin/env python3
"""
Documentation tools for Plexus MCP Server
"""
import os
import sys
import logging
from io import StringIO
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_documentation_tools(mcp: FastMCP):
    """Register documentation tools with the MCP server"""
    
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
                plexus_dir = os.path.dirname(os.path.dirname(current_dir))  # Go up from MCP/tools/documentation to project root
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