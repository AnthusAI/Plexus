#!/usr/bin/env python3
"""
Documentation tools for Plexus MCP Server
"""
import sys
import logging
from io import StringIO
from fastmcp import FastMCP

from shared.documentation_catalog import (
    DOC_FILENAME_MAP,
    build_invalid_filename_error,
    build_tool_docstring,
    get_doc_path,
)

logger = logging.getLogger(__name__)


def register_documentation_tools(mcp: FastMCP):
    """Register documentation tools with the MCP server"""

    async def get_plexus_documentation(filename: str) -> str:
        """Temporary docstring replaced below from the shared catalog."""
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout

        try:
            if filename not in DOC_FILENAME_MAP:
                return build_invalid_filename_error(filename)

            try:
                file_path = get_doc_path(filename)

                logger.info(f"Reading documentation file: {file_path}")

                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                logger.info(
                    f"Successfully read documentation file '{filename}' ({len(content)} characters)"
                )
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

    get_plexus_documentation.__doc__ = build_tool_docstring()
    mcp.tool()(get_plexus_documentation)
