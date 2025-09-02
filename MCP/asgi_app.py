#!/usr/bin/env python3
"""
ASGI application wrapper for Plexus FastMCP Server
Enables remote access via uvicorn for production deployment with mandatory authentication
"""
import os
import sys
import secrets

# Add project root to path
mcp_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(mcp_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment from .env file first
try:
    from dotenv import load_dotenv
    # Load from project root .env file
    env_file = os.path.join(project_root, '.env')
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"Loaded .env from: {env_file}", file=sys.stderr)
    else:
        print(f"No .env file found at: {env_file}", file=sys.stderr)
except ImportError:
    print("python-dotenv not available - install with: pip install python-dotenv", file=sys.stderr)

# Load Plexus configuration
try:
    from plexus.config.loader import load_config
    load_config()
except Exception as e:
    print(f"Warning: Failed to load Plexus configuration: {e}", file=sys.stderr)

# Import FastMCP with authentication
from fastmcp import FastMCP
from fastmcp.server.auth import StaticTokenVerifier

# Require authentication token - fail if not provided
auth_token = os.environ.get("MCP_AUTH_TOKEN")
if not auth_token:
    # Generate a secure random token as suggestion
    suggested_token = secrets.token_urlsafe(32)
    print(f"ERROR: MCP_AUTH_TOKEN environment variable is required for security!", file=sys.stderr)
    print(f"Set it to a secure value, for example:", file=sys.stderr)
    print(f"export MCP_AUTH_TOKEN='{suggested_token}'", file=sys.stderr)
    sys.exit(1)

print(f"Setting up mandatory authentication", file=sys.stderr)
auth_provider = StaticTokenVerifier(
    tokens={
        auth_token: {
            "client_id": "plexus-mcp-client",
            "scopes": ["mcp:read", "mcp:write"]
        }
    }
)

# Import the original MCP to get its configuration
from plexus_fastmcp_server import mcp as original_mcp

# Create new authenticated FastMCP with same config but with auth
mcp = FastMCP(
    name="Plexus MCP Server (Authenticated)",
    instructions=original_mcp.instructions,
    auth=auth_provider
)

# Register all tools from the original MCP server
# Since we can't directly copy private attributes, we'll import and re-register the tools
try:
    from tools.util.think import register_think_tool
    from tools.scorecard.scorecards import register_scorecard_tools
    from tools.report.reports import register_report_tools
    from tools.score.scores import register_score_tools
    from tools.item.items import register_item_tools
    from tools.task.tasks import register_task_tools
    from tools.feedback.feedback import register_feedback_tools
    from tools.evaluation.evaluations import register_evaluation_tools
    from tools.prediction.predictions import register_prediction_tools
    from tools.documentation.docs import register_documentation_tools
    from tools.cost.analysis import register_cost_analysis_tools
    from tools.dataset.datasets import register_dataset_tools
    
    register_think_tool(mcp)
    register_scorecard_tools(mcp)
    register_report_tools(mcp)
    register_score_tools(mcp)
    register_item_tools(mcp)
    register_task_tools(mcp)
    register_feedback_tools(mcp)
    register_evaluation_tools(mcp)
    register_prediction_tools(mcp)
    register_documentation_tools(mcp)
    register_cost_analysis_tools(mcp)
    register_dataset_tools(mcp)
    
    print("Successfully registered all tools for authenticated MCP", file=sys.stderr)
except Exception as e:
    print(f"Error registering tools: {e}", file=sys.stderr)

# Create ASGI application
app = mcp.http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)