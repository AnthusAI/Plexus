"""
Plexus MCP Server implementation.

This module provides the Plexus-specific implementation of the Model Context Protocol server.
"""

import logging
import asyncio
import signal
import sys
import traceback
from typing import Optional
import os

from mcp.server.fastmcp import FastMCP
from .tools import register_tools

logger = logging.getLogger(__name__)


class Plexus:
    """Plexus MCP server implementation."""

    def __init__(self, name: str = "plexus"):
        """Initialize the Plexus MCP server.
        
        Args:
            name: The name of the server
        """
        self._server = FastMCP(name=name)
        self._setup_handlers()
        self._running = False
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging for better debugging."""
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Configure the root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Add file handler
        file_handler = logging.FileHandler('logs/plexus_mcp.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        root_logger.addHandler(file_handler)
        
        # Reduce noise from asyncio and mcp loggers
        logging.getLogger('asyncio').setLevel(logging.WARNING)
        logging.getLogger('mcp').setLevel(logging.WARNING)

    def _setup_handlers(self):
        """Set up the request handlers for the server."""
        try:
            register_tools(self._server)
            logger.info("Successfully registered MCP tools")
        except Exception as e:
            logger.error(f"Failed to register tools: {str(e)}")
            raise
        # TODO: Register resource handlers when implemented

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self._running = False

    async def _keep_alive(self):
        """Send periodic keep-alive messages to maintain connection."""
        while self._running:
            try:
                logger.debug("Server is alive")
                await asyncio.sleep(30)  # Send keep-alive every 30 seconds
            except Exception as e:
                logger.error(f"Keep-alive error: {str(e)}")

    async def run_async(self):
        """Run the server asynchronously."""
        logger.info("Starting MCP server...")
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        
        self._running = True
        
        try:
            # Start keep-alive task
            keep_alive_task = asyncio.create_task(self._keep_alive())
            
            # Run the server with stdio transport
            logger.info("Starting server with stdio transport")
            await self._server.run(transport="stdio")
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        finally:
            self._running = False
            logger.info("Server shutting down...")

    def run(self):
        """Run the server."""
        try:
            asyncio.run(self.run_async())
        except Exception as e:
            logger.error(f"Failed to run server: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise 