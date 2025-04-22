#!/usr/bin/env python3
"""
Wrapper script for Plexus MCP server that properly handles stdout/stderr separation.
This ensures that only proper JSON protocol messages go to stdout while all logs go to stderr.
"""
import os
import sys
import subprocess
import json

def main():
    # Get current script directory (now /Users/derek.norrbom/Capacity/Plexus/MCP/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Get the parent directory (now /Users/derek.norrbom/Capacity/Plexus/)
    parent_dir = os.path.dirname(script_dir)
    # The server needs to run from the Plexus root directory
    target_cwd = parent_dir # Use the parent directory as the target CWD
    
    # Path to the actual server script relative to the script dir
    # (e.g., /Users/derek.norrbom/Capacity/Plexus/MCP/plexus_mcp_server.py)
    server_script = os.path.join(script_dir, "plexus_mcp_server.py")
    
    # Get all command line arguments to pass through
    args = sys.argv[1:]
    
    # Set environment variables
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    # env["PYTHONPATH"] = script_dir # Keep commented out
    
    # Start the server, connecting stdin/stdout directly to allow MCP protocol communication
    cmd = [sys.executable, server_script] + args
    
    # Print launch info to stderr
    print(f"wrapper argv: {' '.join(cmd)}", file=sys.stderr)
    print(f"wrapper launching server with cwd: {target_cwd}", file=sys.stderr) # Log the CORRECT CWD
    
    # Check if target CWD exists
    if not os.path.isdir(target_cwd):
        print(f"wrapper ERROR: Target CWD does not exist: {target_cwd}", file=sys.stderr)
        return 1
        
    try:
        # Use Popen to connect I/O streams properly
        process = subprocess.Popen(
            cmd,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=env,
            # Set the CWD for the server process to the target directory
            cwd=target_cwd, 
            bufsize=0  # Unbuffered
        )
        
        # Wait for the process to complete
        return_code = process.wait()
        # Log the return code to stderr for debugging
        print(f"wrapper: server process exited with code {return_code}", file=sys.stderr)
        return return_code
    except Exception as e:
        print(f"Error running MCP server from wrapper: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 