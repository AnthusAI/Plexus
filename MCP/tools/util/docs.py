#!/usr/bin/env python3
"""
Documentation tools for Plexus MCP server
"""
import os
import sys
from io import StringIO
from fastmcp import FastMCP

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.setup import logger


def register_docs_tool(mcp: FastMCP):
    """Register the documentation retrieval tool with the MCP server."""

    @mcp.tool()
    async def get_plexus_documentation(filename: str) -> str:
        """
        Get documentation content for specific Plexus topics.

        Valid filenames:
        - score-yaml-format: Complete guide to Score YAML configuration format including LangGraph, node types, dependencies, and best practices
        - feedback-alignment: Complete guide to testing score results, finding feedback items, and analyzing prediction accuracy for score improvement
        - dataset-yaml-format: Complete guide to dataset YAML configuration format for data sources
        """
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout

        try:
            valid_files = {
                "score-yaml-format": "score-yaml-format.md",
                "feedback-alignment": "feedback-alignment.md",
                "dataset-yaml-format": "dataset-yaml-format.md",
            }

            if filename not in valid_files:
                available = ", ".join(valid_files.keys())
                return f"Error: Invalid filename '{filename}'. Valid options are: {available}"

            current_dir = os.path.dirname(os.path.abspath(__file__))
            mcp_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
            plexus_dir = os.path.dirname(mcp_dir)
            docs_dir = os.path.join(plexus_dir, "plexus", "docs")
            file_path = os.path.join(docs_dir, valid_files[filename])

            logger.info(f"Reading documentation file: {file_path}")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                logger.info(
                    f"Successfully read documentation file '{filename}' ({len(content)} characters)"
                )
                return content
            except FileNotFoundError:
                error_msg = (
                    f"Documentation file '{filename}' not found at expected location: {file_path}"
                )
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
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(
                    f"Captured unexpected stdout during get_plexus_documentation: {captured_output}"
                )
            sys.stdout = old_stdout


