# Plexus MCP System Overview

The Plexus MCP (Multi-Agent Cooperative Protocol) system enables AI agents and tools to interact with Plexus functionality through a standardized protocol. This document provides an overview of the system architecture and key components.

## Core Components

### Server Implementation
- **Main Server**: [MCP/plexus_mcp_server.py](mdc:Plexus-2/Plexus-2/Plexus-2/MCP/plexus_mcp_server.py) - Core server implementation using the `mcp.server` library
- **Wrapper Script**: [MCP/plexus_mcp_wrapper.py](mdc:Plexus-2/Plexus-2/Plexus-2/MCP/plexus_mcp_wrapper.py) - Handles proper stdout/stderr separation and environment setup

### Key Features
1. **Protocol Communication**
   - Uses JSON-based MCP protocol over stdio
   - All protocol messages go to stdout
   - All logging/debugging goes to stderr
   - Ensures clean separation for MCP clients

2. **Environment Management**
   - Requires dashboard credentials (API URL, API Key)
   - Loads credentials from `.env` file
   - Environment directory must be specified via `--env-dir` argument

3. **Available Tools**
   - `list_plexus_scorecards`: Lists scorecards from the Plexus Dashboard. Can filter by account, name, or key.
   - `get_plexus_scorecard_info`: Gets detailed information about a specific scorecard, including its sections and scores.
   - `get_plexus_score_details`: Gets detailed information for a specific score, including its configuration and version history.
   - `list_plexus_reports`: Lists reports from the Plexus Dashboard. Can be filtered by account or report configuration ID. Results are sorted by most recent first.
   - `get_plexus_report`: Gets information about a report by ID, or the latest report if no ID is provided. Includes a deep link URL to view the report in the dashboard.
   - `run_plexus_evaluation`: Run an accuracy evaluation on a Plexus scorecard. Can accept either scorecard name or key.
   - `debug_python_env`: Debug the Python environment, including available modules and paths.
   - `list_plexus_report_configurations`: Lists report configurations for an account sorted by most recent first.

### Recent Improvements
- Consolidated report tools for simpler, more consistent usage
- Added deep link URL generation for easier access to dashboard resources
- Fixed account resolution in `list_plexus_report_configurations` to properly handle case-insensitive matches
- Improved GraphQL query formatting for consistent results
- Added robust fallback mechanisms for API response handling
- Enhanced logging for better troubleshooting

## Implementation Details

### Server Architecture
- Built on `mcp.server` library
- Uses async/await for non-blocking operations
- Implements proper error handling and logging
- Supports Python 3.10+ (required by MCP library)

### Tool Implementation Pattern
1. Define tool schema with input/output specifications
2. Implement handler function with error handling
3. Register tool with server using decorators
4. Add read-only annotation where appropriate

### Error Handling
- All errors are captured and returned as structured responses
- Detailed logging to stderr for debugging
- Clean error messages for client consumption

## Configuration

### Client Setup
To use with MCP clients (e.g., Cursor), configure `mcp.json`:
```json
{
  "mcpServers": {
    "plexus-mcp-service": {
      "command": "/path/to/python",
      "args": [
        "/path/to/plexus_mcp_wrapper.py",
        "--transport", "stdio",
        "--env-file", "/path/to/env/dir/.env",
        "--target-cwd", "/path/to/project/"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "/path/to/plexus"
      }
    }
  }
}
```

### Environment Requirements
- Python 3.11+
- Plexus installation with dashboard access
- Valid `.env` file with API credentials
- `python-dotenv` package (recommended)

#### Required Environment Variables
- `PLEXUS_API_URL`: The AppSync API endpoint URL
- `PLEXUS_API_KEY`: The API key for authentication
- `PLEXUS_DASHBOARD_URL`: The base URL of the Plexus dashboard (for generating deep links)

#### Optional Environment Variables
- `PLEXUS_ACCOUNT_KEY`: Default account key to use when not specified
- `MCP_DEBUG`: Set to "true" to enable debug logging
- `LOG_LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)

## Best Practices
1. Always use the wrapper script to launch the server
2. Keep stdout clean for protocol messages
3. Use stderr for all logging and debugging
4. Implement proper error handling in tool functions
5. Add read-only annotation for safe tools
6. Document tool schemas clearly

## Troubleshooting
- Check stderr for detailed error messages
- Verify environment variables are loaded
- Ensure Python version is 3.10+
- Confirm proper stdout/stderr separation
- Validate tool schemas and implementations

## Logging
- MCP logs are stored in `~/Library/Logs/Claude`
- You can monitor logs in real-time using `tail -f ~/Library/Logs/Claude/mcp.log`
- Logs contain detailed information about protocol communication and tool execution
- Useful for debugging connection issues and tool failures 