#!/usr/bin/env python3
"""
Think tool registration for Plexus MCP server
"""
import os
import sys
from io import StringIO
from fastmcp import FastMCP

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.setup import logger


def register_think_tool(mcp: FastMCP):
    """Register the think tool with the MCP server."""

    @mcp.tool()
    async def think(thought: str) -> str:
        """
        Use this tool as a scratchpad when working with Plexus tools to:
        - Plan your approach for Plexus operations
        - Verify parameters for Plexus API calls
        - Diagnose issues with Plexus tools
        - Find specific information within Plexus data
        - Plan a sequence of Plexus tool calls

        CRITICAL WORKFLOW POLICY (Score YAML work):
        - Always work from a LOCAL YAML file. Pull with the score pull tool and edit the file in `scorecards/<Scorecard>/<Score>.yaml`.
        - During iteration, DO NOT push new versions. Keep all changes local.
        - Never promote a champion version unless the user explicitly instructs it after thorough evaluation.
        - For predictions/evaluations while iterating, always load from local YAML using the MCP tools. Do NOT run CLI commands from the MCP context.
          - Use MCP prediction/evaluation tools which are designed to be token-efficient and avoid verbose logging.
          - If you need YAML mode, set the MCP tool parameters accordingly (local YAML should be the default where available).
        - Typical flow:
          1) Pull config → local edit → lint locally if needed
          2) Test via MCP predictions/evaluations in LOCAL mode
          3) Repeat until approved
          4) Only then push a new version (and do NOT set champion without explicit user approval)

        IMPORTANT: Do NOT shell out to CLI tools (e.g., `python -m plexus.cli...`) from the MCP environment.
        The CLI produces excessive log output, which is not token-efficient for MCP usage. Always prefer MCP tools.
        """
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout

        try:
            logger.info(f"Think tool used: {thought[:100]}...")
            return "Thought processed"
        except Exception as e:
            logger.error(f"Error in think tool: {str(e)}", exc_info=True)
            return f"Error processing thought: {str(e)}"
        finally:
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during think: {captured_output}")
            sys.stdout = old_stdout


