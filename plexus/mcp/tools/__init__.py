"""
MCP tools package for Plexus.

This package contains all the tool implementations that can be exposed
through the MCP server.
"""

from mcp.server import FastMCP
from .demo import DemoTaskTool

__all__ = ["register_tools"]

def register_tools(server: FastMCP):
    """Register MCP tools with the server.
    
    Args:
        server: The FastMCP server instance to register tools with.
    """
    demo_tool = DemoTaskTool()
    server.add_tool(demo_tool.execute, name="demo", description=demo_tool.description) 