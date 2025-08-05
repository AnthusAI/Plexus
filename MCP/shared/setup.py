#!/usr/bin/env python3
"""
Shared setup and initialization code for Plexus MCP server
"""
import os
import sys
import io
import logging
from io import StringIO
from typing import Optional

# Save original stdout file descriptor
original_stdout_fd = None
try:
    # Only do this if we're not already redirected
    if sys.stdout.fileno() == 1:  # 1 is the standard fd for stdout
        original_stdout_fd = os.dup(1)  # Duplicate original stdout fd
        os.dup2(2, 1)  # Redirect stdout (fd 1) to stderr (fd 2)
        # Now all stdout fd writes go to stderr
except (AttributeError, io.UnsupportedOperation):
    # Handle non-standard stdout (like in tests or IDEs)
    pass

def restore_stdout():
    """Restore original stdout for controlled JSON-RPC output"""
    if original_stdout_fd is not None:
        try:
            os.dup2(original_stdout_fd, 1)  # Restore original stdout
        except Exception as e:
            print(f"Error restoring stdout: {e}", file=sys.stderr)

def redirect_stdout_to_stderr():
    """Redirect stdout to stderr at the file descriptor level"""
    if original_stdout_fd is not None:
        try:
            os.dup2(2, 1)  # Redirect stdout to stderr again
        except Exception as e:
            print(f"Error redirecting stdout: {e}", file=sys.stderr)

# Configure logging to stderr only
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# Safety measure: Monkey patch builtins.print to always use stderr
original_print = print
def safe_print(*args, **kwargs):
    # If file is explicitly set, honor it; otherwise, force stderr
    if 'file' not in kwargs:
        kwargs['file'] = sys.stderr
    return original_print(*args, **kwargs)
print = safe_print

# Global account cache - stores the resolved account ID
DEFAULT_ACCOUNT_ID = None
DEFAULT_ACCOUNT_KEY = None
ACCOUNT_CACHE = {}  # Maps account keys/names to resolved IDs

# Initialize Global flags and dummy functions first
PLEXUS_CORE_AVAILABLE = False
def create_dashboard_client(): return None
def resolve_account_identifier(client, identifier): return None
def resolve_scorecard_identifier(client, identifier): return None

def setup_plexus_imports():
    """Setup Plexus imports and path configuration"""
    global PLEXUS_CORE_AVAILABLE, create_dashboard_client, resolve_account_identifier, resolve_scorecard_identifier
    
    # Temporarily redirect stdout during initialization to prevent any accidental writing to stdout
    original_stdout = sys.stdout
    temp_stdout = StringIO()
    sys.stdout = temp_stdout

    try:
        # Redirect sys.stdout again to make absolutely sure nothing leaks during path setup
        path_stdout = StringIO()
        sys.stdout = path_stdout
        
        # Add Plexus project root to Python path if necessary
        # The MCP server is in MCP/ directory, but plexus package is in the parent directory
        mcp_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_root = os.path.dirname(mcp_dir)  # Go up one level to project root
        if project_root not in sys.path:
            sys.path.insert(0, project_root)  # Insert at beginning for priority
            logger.info(f"Added project root to Python path: {project_root}")
        
        # Log the paths for debugging
        logger.info(f"MCP directory: {mcp_dir}")
        logger.info(f"Project root: {project_root}")
        logger.info(f"Looking for plexus package at: {os.path.join(project_root, 'plexus')}")
        logger.info(f"Plexus package exists: {os.path.exists(os.path.join(project_root, 'plexus'))}")
        
        # Check if anything was written during path setup
        path_output = path_stdout.getvalue()
        if path_output:
            logger.warning(f"Captured unexpected stdout during path setup: {path_output}")
        # Restore to our main capture buffer
        sys.stdout = temp_stdout
        
        # Load YAML configuration first (before importing Plexus modules)
        try:
            from plexus.config import load_config
            load_config()  # This will set environment variables from YAML config
            logger.info("YAML configuration loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load YAML configuration: {e}")
        
        # Try to import the Plexus core modules
        try:
            # Attempt to import Plexus modules for core functionality
            from plexus.dashboard.api.client import PlexusDashboardClient
            # Assign imported functions to pre-defined names
            from plexus.cli.client_utils import create_client as _create_dashboard_client
            from plexus.cli.ScorecardCommands import resolve_account_identifier as _resolve_account_identifier
            from plexus.cli.identifier_resolution import resolve_scorecard_identifier as _resolve_scorecard_identifier
            
            # Create a wrapper around create_dashboard_client to add better error logging
            def enhanced_create_dashboard_client():
                # Redirect stdout during client creation
                client_stdout = StringIO()
                old_stdout = sys.stdout
                sys.stdout = client_stdout
                
                try:
                    api_url = os.environ.get('PLEXUS_API_URL', '')
                    api_key = os.environ.get('PLEXUS_API_KEY', '')
                    
                    logger.debug(f"API URL exists: {bool(api_url)}, API KEY exists: {bool(api_key)}")
                    
                    if not api_url or not api_key:
                        logger.warning("Missing API credentials: API_URL or API_KEY not set in environment")
                        return None
                    
                    # Call the original function
                    client = _create_dashboard_client()
                    
                    if client:
                        logger.debug(f"Dashboard client created successfully with type: {type(client)}")
                    else:
                        logger.warning("Dashboard client creation returned None - check API credentials")
                    
                    return client
                except Exception as e:
                    logger.error(f"Error creating dashboard client: {str(e)}", exc_info=True)
                    return None
                finally:
                    # Check if anything was written to stdout
                    client_output = client_stdout.getvalue()
                    if client_output:
                        logger.warning(f"Captured unexpected stdout during client creation: {client_output}")
                    # Restore stdout to previous capture
                    sys.stdout = old_stdout
            
            # Create wrappers for identifier resolution functions to capture stdout
            def wrapped_resolve_account_identifier(client, identifier):
                resolve_stdout = StringIO()
                old_stdout = sys.stdout
                sys.stdout = resolve_stdout
                try:
                    result = _resolve_account_identifier(client, identifier)
                    return result
                finally:
                    # Check if anything was written to stdout
                    resolve_output = resolve_stdout.getvalue()
                    if resolve_output:
                        logger.warning(f"Captured unexpected stdout during account resolution: {resolve_output}")
                    # Restore stdout to previous capture
                    sys.stdout = old_stdout
                    
            def wrapped_resolve_scorecard_identifier(client, identifier):
                resolve_stdout = StringIO()
                old_stdout = sys.stdout
                sys.stdout = resolve_stdout
                try:
                    result = _resolve_scorecard_identifier(client, identifier)
                    return result
                finally:
                    # Check if anything was written to stdout
                    resolve_output = resolve_stdout.getvalue()
                    if resolve_output:
                        logger.warning(f"Captured unexpected stdout during scorecard resolution: {resolve_output}")
                    # Restore stdout to previous capture
                    sys.stdout = old_stdout
            
            # Replace the imported functions with our enhanced versions
            create_dashboard_client = enhanced_create_dashboard_client
            resolve_account_identifier = wrapped_resolve_account_identifier
            resolve_scorecard_identifier = wrapped_resolve_scorecard_identifier
            PLEXUS_CORE_AVAILABLE = True
            logger.info("Plexus core modules imported successfully.")
        except ImportError as e:
            logger.warning(f"Could not import core Plexus modules: {e}. Dashboard features will be unavailable.")
            # Dummies are already defined, PLEXUS_CORE_AVAILABLE is already False
        except Exception as import_err:
            # Catch other potential errors during import/setup
            logger.error(f"Error during Plexus core module import/setup: {import_err}", exc_info=True)
        
        # Check for and log any accidental stdout output from imports
        stdout_captured = temp_stdout.getvalue()
        if stdout_captured:
            logger.warning(f"Captured unexpected stdout output during imports: {stdout_captured}")
        
        # Restore stdout for proper JSON-RPC communication
        sys.stdout = original_stdout
    except Exception as e:
        # Ensure stdout is restored in case of exception
        sys.stdout = original_stdout
        # Log error to stderr
        if 'logger' in locals():
            logger.error(f"Error during initialization: {e}", exc_info=True)
        else:
            print(f"Error during initialization: {e}", file=sys.stderr)
        raise

    return PLEXUS_CORE_AVAILABLE