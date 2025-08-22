#!/usr/bin/env python3
"""
Stop tool for experiment conversations - allows AI to end conversation with reason
"""
import os
import sys
from fastmcp import FastMCP

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.setup import logger


def register_stop_tool(mcp: FastMCP):
    """Register the stop tool with the MCP server."""

    @mcp.tool()
    async def stop_conversation(reason: str) -> str:
        """
        Stop the current conversation with a specific reason.
        
        Use this tool when you need to end the conversation because:
        - You cannot proceed due to insufficient information
        - Tools are repeatedly failing and blocking progress
        - No feedback data exists to analyze (no mistakes found)
        - You've completed your analysis and created sufficient hypotheses
        - Any other blocking condition that prevents meaningful progress
        
        Parameters:
        - reason: Clear explanation of why you're stopping the conversation
        
        Returns:
        - Confirmation that the stop request has been recorded
        """
        try:
            logger.info(f"Stop tool invoked with reason: {reason}")
            
            # Return a special marker that the conversation system will recognize
            return f"STOP_REQUESTED: {reason}"
            
        except Exception as e:
            logger.error(f"Error in stop tool: {str(e)}", exc_info=True)
            return f"Error processing stop request: {str(e)}"
