#!/usr/bin/env python3
"""
Documentation tools for Plexus MCP server
"""
import os
import sys
from io import StringIO
from fastmcp import FastMCP

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.documentation_catalog import (
    DOC_FILENAME_MAP,
    build_invalid_filename_error,
    build_tool_docstring,
    get_doc_path,
)
from shared.setup import logger


def register_docs_tool(mcp: FastMCP):
    """Register the documentation retrieval tool with the MCP server."""

    async def get_plexus_documentation(filename: str) -> str:
        """Temporary docstring replaced below from the shared catalog."""
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout

        try:
            if filename not in DOC_FILENAME_MAP:
                return build_invalid_filename_error(filename)

            file_path = get_doc_path(filename)

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

    get_plexus_documentation.__doc__ = build_tool_docstring()
    mcp.tool()(get_plexus_documentation)

