#!/usr/bin/env python3
"""
Stop tool for procedure conversations - allows AI to end conversation with reason
"""
import os
import sys
from fastmcp import FastMCP
from typing import Optional, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.setup import logger


def register_stop_tool(mcp: FastMCP, procedure_context: Optional[Dict[str, Any]] = None):
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

            # Mark the active parent node as completed
            if procedure_context and 'active_parent_node_id' in procedure_context:
                active_parent_id = procedure_context['active_parent_node_id']
                if active_parent_id:
                    try:
                        from plexus.dashboard.api.models.graph_node import GraphNode
                        import json

                        # Get client from context
                        client = procedure_context.get('client')
                        if client:
                            # Get the node
                            node = GraphNode.get_by_id(active_parent_id, client)
                            if node:
                                # Parse existing metadata
                                metadata = json.loads(node.metadata) if isinstance(node.metadata, str) else node.metadata if node.metadata else {}

                                # Mark as completed
                                metadata['state'] = 'completed'

                                # Update the node
                                node.update_content(metadata=metadata)
                                logger.info(f"Marked parent node {active_parent_id} as completed")
                            else:
                                logger.warning(f"Could not find parent node {active_parent_id} to mark as completed")
                        else:
                            logger.warning("No client available in context to mark parent node as completed")
                    except Exception as e:
                        logger.warning(f"Could not mark parent node as completed: {e}")

            # Return a special marker that the conversation system will recognize
            return f"STOP_REQUESTED: {reason}"

        except Exception as e:
            logger.error(f"Error in stop tool: {str(e)}", exc_info=True)
            return f"Error processing stop request: {str(e)}"
