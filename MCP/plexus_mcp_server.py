#!/usr/bin/env python3
"""
Legacy MCP server entry point that forwards to the FastMCP server.
This ensures compatibility with existing configurations that reference plexus_mcp_server.py.
"""
import sys
import os
import subprocess

def main():
    # Get the directory containing this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to the actual FastMCP server
    fastmcp_server = os.path.join(current_dir, "plexus_fastmcp_server.py")
    
    # Forward all arguments to the FastMCP server
    cmd = [sys.executable, fastmcp_server] + sys.argv[1:]
    
    # Execute the FastMCP server with the same environment and working directory
    try:
        result = subprocess.run(cmd, 
                               stdin=sys.stdin, 
                               stdout=sys.stdout, 
                               stderr=sys.stderr,
                               env=os.environ.copy())
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(f"Error executing FastMCP server: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main() 