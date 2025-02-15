"""MCP commands for the Plexus CLI."""

import logging
import sys
import os

import click

from plexus.mcp import Plexus

logger = logging.getLogger(__name__)

@click.group()
def mcp():
    """Model Context Protocol (MCP) commands."""
    pass

@mcp.command()
@click.option("--name", default="plexus", help="Name of the MCP server")
@click.option("--loglevel", default="INFO", help="Logging level")
def serve(name: str, loglevel: str):
    """Start the MCP server."""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Configure logging to write to file
    logging.basicConfig(
        level=getattr(logging, loglevel.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/plexus_mcp.log')
        ]
    )
    
    # Suppress MLflow warnings
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="mlflow")
    
    logger.info("Starting MCP server...")
    server = Plexus(name=name)
    server.run() 