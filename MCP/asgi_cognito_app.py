#!/usr/bin/env python3
"""
ASGI application wrapper for Plexus FastMCP Server with AWS Cognito OAuth
Enables remote access via uvicorn with enterprise-grade authentication
"""
import os
import sys

# Import FastMCP with OAuth authentication
from fastmcp import FastMCP
from fastmcp.server.auth import OAuthProxy
from fastmcp.server.auth.providers.jwt import JWTVerifier

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

# Cognito configuration from environment variables
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")  # e.g., "us-west-2_AbCdEf123"
COGNITO_REGION = os.environ.get("COGNITO_REGION", "us-west-2")
COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN")  # e.g., "your-domain.auth.us-west-2.amazoncognito.com"
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID")
COGNITO_CLIENT_SECRET = os.environ.get("COGNITO_CLIENT_SECRET")
MCP_SERVER_BASE_URL = os.environ.get("MCP_SERVER_BASE_URL")  # e.g., "https://your-server.com"

# Validate required configuration
required_vars = {
    "COGNITO_USER_POOL_ID": COGNITO_USER_POOL_ID,
    "COGNITO_DOMAIN": COGNITO_DOMAIN,
    "COGNITO_CLIENT_ID": COGNITO_CLIENT_ID,
    "COGNITO_CLIENT_SECRET": COGNITO_CLIENT_SECRET,
    "MCP_SERVER_BASE_URL": MCP_SERVER_BASE_URL
}

missing_vars = [name for name, value in required_vars.items() if not value]
if missing_vars:
    print(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}", file=sys.stderr)
    print("Required Cognito configuration:", file=sys.stderr)
    print("  COGNITO_USER_POOL_ID=us-west-2_AbCdEf123", file=sys.stderr)
    print("  COGNITO_REGION=us-west-2", file=sys.stderr) 
    print("  COGNITO_DOMAIN=your-domain.auth.us-west-2.amazoncognito.com", file=sys.stderr)
    print("  COGNITO_CLIENT_ID=your-client-id", file=sys.stderr)
    print("  COGNITO_CLIENT_SECRET=your-client-secret", file=sys.stderr)
    print("  MCP_SERVER_BASE_URL=https://your-server.com", file=sys.stderr)
    print("", file=sys.stderr)
    print("Add these to your .env file or export them as environment variables.", file=sys.stderr)
    sys.exit(1)

print("Setting up AWS Cognito OAuth authentication", file=sys.stderr)

# Configure JWT verifier for Cognito tokens
jwks_uri = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
issuer = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"

# Token Verifier
token_verifier = JWTVerifier(
    jwks_uri=jwks_uri,
    issuer=issuer,
    algorithm="RS256",
    resource_server_url=MCP_SERVER_BASE_URL
)

# Configure OAuth Proxy for Cognito
auth = OAuthProxy(
    upstream_authorization_endpoint=f"https://{COGNITO_DOMAIN}/oauth2/authorize",
    upstream_token_endpoint=f"https://{COGNITO_DOMAIN}/oauth2/token",
    upstream_client_id=COGNITO_CLIENT_ID,
    upstream_client_secret=COGNITO_CLIENT_SECRET,
    token_verifier=token_verifier,
    base_url=MCP_SERVER_BASE_URL,
    redirect_path="/auth/callback"  # Maintain /mcp prefix for load balancer routing
)

print(f"OAuth configured with Cognito domain: {COGNITO_DOMAIN}", file=sys.stderr)
print(f"Server base URL: {MCP_SERVER_BASE_URL}", file=sys.stderr)
print(f"Callback URL: {MCP_SERVER_BASE_URL}/auth/callback", file=sys.stderr)

# Import the original MCP to get its configuration
from plexus_fastmcp_server import mcp as original_mcp

# Create new authenticated FastMCP with Cognito OAuth
mcp = FastMCP(
    name="Plexus MCP Server (Cognito OAuth)",
    instructions=original_mcp.instructions,
    auth=auth
)

# Dynamically register all tools from the original MCP server
try:
    tools_dict = original_mcp._tool_manager._tools
    
    for tool_name, tool_obj in tools_dict.items():
        mcp.add_tool(tool_obj)
    
    print(f"Successfully registered {len(tools_dict)} tools dynamically for Cognito-authenticated MCP", file=sys.stderr)
    
except Exception as e:
    print(f"Error in dynamic tool registration: {e}", file=sys.stderr)

# Create ASGI application with stateless HTTP
app = mcp.http_app(stateless_http=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)