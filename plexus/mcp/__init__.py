"""
Plexus MCP (Model Context Protocol) Server Implementation.

This package provides MCP server capabilities for Plexus, allowing AI assistants
to interact with Plexus functionality in a standardized way.
"""

__version__ = "0.1.0"

from .server import Plexus
from .tools import register_tools

__all__ = ["Plexus", "register_tools"] 