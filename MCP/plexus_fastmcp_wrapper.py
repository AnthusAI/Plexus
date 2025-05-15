#!/usr/bin/env python3
"""
Wrapper script for Plexus FastMCP server that properly handles stdout/stderr separation.
This ensures that only proper JSON protocol messages go to stdout while all logs go to stderr.
"""
import os
import sys
import subprocess
import json
import argparse
from io import StringIO

class StderrArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that writes all output to stderr instead of stdout."""
    def _print_message(self, message, file=None):
        if message:
            if file is None:
                file = sys.stderr
            file.write(message)
    
    def exit(self, status=0, message=None):
        if message:
            self._print_message(message, sys.stderr)
        sys.exit(status)

def parse_args():
    """Parse command line arguments with support for --env-file."""
    parser = StderrArgumentParser(description="Plexus FastMCP Server Wrapper")
    parser.add_argument("--host", default="localhost", help="Host (passed to server)")
    parser.add_argument("--port", type=int, default=8000, help="Port (passed to server)")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse"], help="Transport (passed to server)")
    parser.add_argument("--env-dir", help="Directory containing the .env file (passed to server)")
    parser.add_argument("--env-file", help="Direct path to the .env file to load")
    parser.add_argument("--target-cwd", help="Working directory for the server process")
    parser.add_argument("--python-path", help="Path to Python interpreter to use for running the server")
    return parser.parse_known_args()

def get_target_cwd_from_config():
    """Attempt to determine target working directory from Claude desktop config."""
    config_path = os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
    default_cwd = "/Users/derek.norrbom/Capacity/Call-Criteria-Python"
    
    if not os.path.exists(config_path):
        print(f"wrapper: Claude desktop config not found at {config_path}, using default CWD", file=sys.stderr)
        return default_cwd
        
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        # Look for env_file path in the config and extract the directory
        for server_name, server_config in config.get('mcpServers', {}).items():
            args = server_config.get('args', [])
            for i, arg in enumerate(args):
                if arg == "--env-file" and i + 1 < len(args):
                    env_file = args[i + 1]
                    # Extract directory from env file path
                    target_dir = os.path.dirname(env_file)
                    if os.path.isdir(target_dir):
                        print(f"wrapper: Using target CWD from config: {target_dir}", file=sys.stderr)
                        return target_dir
        
        print(f"wrapper: Could not determine target CWD from config, using default", file=sys.stderr)
        return default_cwd
    except Exception as e:
        print(f"wrapper: Error reading config: {e}, using default CWD", file=sys.stderr)
        return default_cwd

def main():
    # Temporarily capture stdout during initialization
    original_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout
    
    try:
        # Parse known arguments, keeping other args to pass through to the server
        args, unknown_args = parse_args()
        
        # Get current script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        
        # Determine target working directory - use command line arg if provided, otherwise read from config
        if args.target_cwd:
            target_cwd = args.target_cwd
            print(f"wrapper: Using command-line specified target CWD: {target_cwd}", file=sys.stderr)
        else:
            target_cwd = get_target_cwd_from_config()
        
        # Path to the FastMCP server script
        server_script = os.path.join(script_dir, "plexus_fastmcp_server.py")
        
        # Prepare arguments for the server process
        server_args = []
        
        # Handle the --env-file argument (wrapper-specific)
        env_file_path = None
        if args.env_file:
            env_file_path = os.path.abspath(args.env_file)
            env_dir = os.path.dirname(env_file_path)
            print(f"wrapper: Using specified .env file: {env_file_path}", file=sys.stderr)
            # Convert --env-file to --env-dir for the server
            server_args.extend(["--env-dir", env_dir])
        elif not args.env_dir:
            print("\n", file=sys.stderr)
            print("===================== IMPORTANT =====================", file=sys.stderr)
            print("No --env-file or --env-dir specified. API credentials may be missing.", file=sys.stderr)
            print("If the server fails to find credentials, update your", file=sys.stderr)
            print("Claude desktop config to include:", file=sys.stderr)
            print('  "--env-file", "/path/to/your/.env"', file=sys.stderr)
            print("=====================================================", file=sys.stderr)
            print("\n", file=sys.stderr)
        
        # Pass through all known arguments except --env-file
        if args.host:
            server_args.extend(["--host", args.host])
        if args.port:
            server_args.extend(["--port", str(args.port)])
        if args.transport:
            server_args.extend(["--transport", args.transport])
        if args.env_dir:
            server_args.extend(["--env-dir", args.env_dir])
        
        # Add any unknown arguments
        server_args.extend(unknown_args)
        
        # Set environment variables
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        
        # Try to properly load environment variables from the specified .env file
        if env_file_path:
            if os.path.isfile(env_file_path):
                try:
                    print(f"wrapper: loading environment from {env_file_path}", file=sys.stderr)
                    loaded_vars = []
                    with open(env_file_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                try:
                                    key, value = line.split('=', 1)
                                    key = key.strip()
                                    value = value.strip().strip("'").strip('"')
                                    if key and value:
                                        env[key] = value
                                        loaded_vars.append(key)
                                except ValueError:
                                    # Skip malformed lines
                                    pass
                    print(f"wrapper: loaded {len(loaded_vars)} variables", file=sys.stderr)
                    
                    # Check for specific Plexus variables
                    plexus_vars = ['PLEXUS_API_URL', 'PLEXUS_API_KEY']
                    for var_name in plexus_vars:
                        if var_name in env:
                            print(f"wrapper: found {var_name} in environment", file=sys.stderr)
                        else:
                            print(f"wrapper: {var_name} NOT FOUND in environment", file=sys.stderr)
                except Exception as e:
                    print(f"wrapper WARNING: error loading .env file: {e}", file=sys.stderr)
            else:
                print(f"wrapper ERROR: Specified .env file not found: {env_file_path}", file=sys.stderr)
                print("Please provide the correct path to your .env file using --env-file", file=sys.stderr)
        
        # Check and log any accidental stdout output
        stdout_captured = temp_stdout.getvalue()
        if stdout_captured:
            print(f"wrapper WARNING: Captured unexpected stdout output during initialization: {stdout_captured}", file=sys.stderr)
        
        # Restore stdout for proper child process communication
        sys.stdout = original_stdout
        
        # Use the current Python interpreter (much simpler approach)
        python_executable = sys.executable
        print(f"wrapper: Using current Python interpreter: {python_executable}", file=sys.stderr)
        
        # Start the server, connecting stdin/stdout directly to allow MCP protocol communication
        cmd = [python_executable, server_script] + server_args
        
        # Print launch info to stderr
        print(f"wrapper argv: {' '.join(cmd)}", file=sys.stderr)
        print(f"wrapper launching server with cwd: {target_cwd}", file=sys.stderr)
        
        # Check if target CWD exists
        if not os.path.isdir(target_cwd):
            print(f"wrapper ERROR: Target CWD does not exist: {target_cwd}", file=sys.stderr)
            return 1
        
        try:
            # Use Popen to connect I/O streams properly
            process = subprocess.Popen(
                cmd,
                stdin=sys.stdin,
                stdout=subprocess.PIPE,  # Capture output to filter it
                stderr=sys.stderr,
                env=env,
                cwd=target_cwd, 
                bufsize=0  # Unbuffered
            )
            
            # Filter stdout to ensure only valid JSON-RPC messages pass through
            # while trapping any unexpected text output
            while process.poll() is None:
                try:
                    line = process.stdout.readline().decode('utf-8')
                    if line:
                        # Check if the line starts with valid JSON (object or array)
                        stripped = line.strip()
                        if stripped and stripped[0] in ['{', '[']:
                            # This looks like valid JSON, pass it through
                            sys.stdout.write(line)
                            sys.stdout.flush()
                        else:
                            # This is not JSON, redirect to stderr
                            print(f"wrapper filtered non-JSON stdout: {stripped}", file=sys.stderr)
                except Exception as read_err:
                    print(f"wrapper: Error reading from subprocess: {read_err}", file=sys.stderr)
            
            # Process any remaining output after process ends
            remaining_output = process.stdout.read().decode('utf-8')
            if remaining_output:
                for line in remaining_output.splitlines(True):  # Keep line endings
                    stripped = line.strip()
                    if stripped and stripped[0] in ['{', '[']:
                        sys.stdout.write(line)
                        sys.stdout.flush()
                    else:
                        print(f"wrapper filtered remaining non-JSON: {stripped}", file=sys.stderr)
            
            # Wait for the process to complete
            return_code = process.wait()
            print(f"wrapper: server process exited with code {return_code}", file=sys.stderr)
            return return_code
        except Exception as e:
            print(f"Error running FastMCP server from wrapper: {e}", file=sys.stderr)
            return 1
    except Exception as e:
        # Make sure to restore stdout even if there's an error
        sys.stdout = original_stdout
        print(f"wrapper ERROR: Unhandled exception: {e}", file=sys.stderr)
        return 1
    finally:
        # Ensure stdout is restored in all cases
        sys.stdout = original_stdout

if __name__ == "__main__":
    sys.exit(main()) 