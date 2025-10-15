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
    async def think(thought: str = "") -> str:
        """
        Use this tool as a scratchpad when working with Plexus tools to:
        - Plan your approach for Plexus operations
        - Verify parameters for Plexus API calls
        - Diagnose issues with Plexus tools
        - Find specific information within Plexus data
        - Plan a sequence of Plexus tool calls

        BEFORE YOU START FEEDBACK ALIGNMENT:
        - Open the documentation: get_plexus_documentation(filename="feedback-alignment").
        - Follow the baseline-first workflow below. Do NOT edit YAML until a baseline is captured.

        SCORE WORKFLOW RECOMMENDATIONS:
        
        FOR MOST SCORE UPDATES (Recommended):
        - Use plexus_score_update with the 'code' parameter to directly update score YAML
        - This is the simplest and most efficient approach for most score modifications
        - Supports specifying parent_version_id for version lineage control
        
        FOR LOCAL DEVELOPMENT WORKFLOWS:
        - Use pull/push when you need to work with local files for complex editing
        - Pull with plexus_score_pull to get YAML locally in `scorecards/<Scorecard>/<Score>.yaml`
        - Edit the local file, then push with plexus_score_push
        - Useful for: complex multi-file workflows, external editor usage, version control integration
        
        FEEDBACK ALIGNMENT SPECIFIC POLICY:
        - During feedback alignment iteration, DO NOT push new versions. Keep all changes local.
        - DO NOT PROMOTE CHAMPION. Champion promotion is disabled for agents and must not be attempted.
        - For feedback alignment: use local YAML files and evaluations with yaml=true, remote=false.

        REQUIRED BASELINE STEPS (no edits yet):
        1) Pull champion YAML locally (score pull). Confirm the local path.
        2) Collect recent metrics: plexus_feedback_analysis (e.g., 30 days) and plexus_feedback_find for FP (Yes→No) and FN (No→Yes).
        3) Run a LOCAL baseline evaluation using ONLY local YAML:
           - Evaluations must set remote=false and yaml=true.
           - Path overrides are handled automatically; you do not need to pass any folder parameters.
           - Record AC1, accuracy, and confusion matrix.

        EDIT-AND-TEST LOOP:
        4) Make minimal YAML edits targeting the observed error patterns.
        5) Re-run the same LOCAL evaluation and compare against baseline.
           - If metrics regress, revert edits.

        PREDICTIONS (sanity checks):
        - Predictions must use LOCAL YAML only: yaml_only=true.
        - Prefer testing on recent FP/FN item_ids gathered from feedback_find.

        Typical flow:
          A) Pull config → run baseline (summary + FP/FN + local evaluation) → then edit locally
          B) Test via MCP predictions/evaluations in LOCAL mode (yaml_only / yaml)
          C) Iterate until improvement is demonstrated
          D) Only after explicit written approval, a human may push a new version (never auto-promote)

        APPROVAL GATE (disabled by default):
        - The agent may NOT perform any push or promotion.
        - Only if the user types the exact lines below in this session may a release persona proceed:
            APPROVE PUSH: YES
            APPROVE CHAMPION: YES
        - This Think tool should remind the agent that champion promotion is not available from MCP tools.

        IMPORTANT: Do NOT shell out to CLI tools (e.g., `python -m plexus.cli...`) from the MCP environment.
        The CLI produces excessive log output, which is not token-efficient for MCP usage. Always prefer MCP tools.
        """
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout

        try:
            # Log the thought content
            if thought:
                logger.info(f"Think tool used: {thought[:200]}...")
                return "Thought processed successfully"
            else:
                logger.info("Think tool used with empty thought")
                return "Empty thought processed"
        except Exception as e:
            logger.error(f"Error in think tool: {str(e)}", exc_info=True)
            return f"Error processing thought: {str(e)}"
        finally:
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during think: {captured_output}")
            sys.stdout = old_stdout


