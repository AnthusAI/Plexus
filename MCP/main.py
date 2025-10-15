#!/usr/bin/env python3
"""
Main entry point for the Plexus MCP Server
"""
import argparse
import sys
import os

# Add the MCP directory to the Python path
mcp_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, mcp_dir)

from server import run_server

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Plexus MCP Server with FastMCP")
    parser.add_argument("--env-dir", help="Directory containing .env file with Plexus credentials")
    parser.add_argument("--host", default="127.0.0.1", help="Host to run server on")
    parser.add_argument("--port", type=int, default=8002, help="Port to run server on")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="sse", 
                        help="Transport protocol (stdio for MCP process or sse for HTTP)")
    args = parser.parse_args()
    
    run_server(args)