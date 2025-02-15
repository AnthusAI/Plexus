"""
MCP tool definitions for Plexus.

This module contains the tool implementations that will be exposed through
the MCP server, allowing AI assistants to interact with Plexus functionality.
"""

# This file is deprecated in favor of the tools package.
# All tool implementations should go in the tools/ directory.

import logging
from typing import Any, Dict
from mcp.server import Server, NotificationOptions

from .tools import register_tools

__all__ = ["register_tools"]

logger = logging.getLogger(__name__)

def register_tools(server: Server) -> None:
    """
    Register all MCP tools with the server.
    
    Args:
        server: The MCP server instance to register tools with.
    """
    logger.info("Registering MCP tools...")
    
    # Register demo task tool
    server.register_tool(DemoTaskTool()) 