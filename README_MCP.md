# Plexus MCP (Multi-Agent Cooperative Protocol)

This extension to Plexus provides a Multi-Agent Cooperative Protocol (MCP) server that enables tools and agents (like those in Cursor or other LLM platforms) to interact with Plexus functionality, primarily focused on accessing Plexus Dashboard data.

## Components

The current Plexus MCP system consists of:

1.  **plexus_mcp_server.py**: The core server implementation built using the `mcp.server` library. It handles the MCP communication protocol over `stdio` and defines the available tools (like `list_plexus_scorecards`).
2.  **plexus_mcp_wrapper.py**: A crucial wrapper script that launches `plexus_mcp_server.py`. It ensures that MCP protocol messages (JSON) are sent to `stdout` and all logging/debugging information is sent to `stderr`. This separation is essential for MCP clients.

## Installation

This tool is designed to work directly with your existing Plexus installation.

Prerequisites:

*   Python 3.8+
*   Plexus installed and properly configured (especially dashboard access credentials/configuration).
*   **Important:** The `mcp` library (installed as a dependency of Plexus) requires **Python 3.10 or newer**. Please ensure your environment meets this requirement.
*   `python-dotenv` recommended for managing environment variables (`pip install python-dotenv`).

The server requires dashboard credentials, which it loads from a `.env` file. The required environment variables are `PLEXUS_API_URL`, `PLEXUS_API_KEY`, and `PLEXUS_ACCOUNT_KEY`. The location of this file's directory **must** be specified using the `--env-dir` argument when launching the server via the MCP client configuration.

## Server Operation

The MCP server uses the `mcp.server` library to communicate over standard input (`stdin`) and standard output (`stdout`) using a JSON-based protocol.

-   **Input**: Receives JSON MCP requests (like `initialize`, `listTools`, `executeTool`) via `stdin`.
-   **Output**: Sends JSON MCP responses (like `toolList`, `toolResult`) via `stdout`.
-   **Logging**: All logs (INFO, DEBUG, WARNING, ERROR) are sent to standard error (`stderr`) to avoid interfering with the protocol on `stdout`.

The `plexus_mcp_wrapper.py` script is responsible for launching the `plexus_mcp_server.py` process with the correct environment and working directory (`your-project-directory`) and ensuring the `stdout`/`stderr` separation. **You should always launch the server using the wrapper script.**

## Available Tools

The server currently exposes the following tools via the MCP protocol:

1.  **hello_world**:
    *   Description: A simple tool that returns a greeting.
    *   Input: `{ "name": "string" }`
    *   Output: Text greeting.
2.  **list_plexus_scorecards**:
    *   Description: Lists scorecards directly from the Plexus Dashboard. Does **not** scan local files.
    *   Input (Optional):
        *   `account`: Filter by account name or key.
        *   `name`: Filter scorecards whose name contains this string.
        *   `key`: Filter scorecards whose key contains this string.
        *   `limit`: Maximum number of scorecards to return (integer or null).
    *   Output: JSON string containing a list of scorecard objects or an error message.

## Configuration with MCP Clients (e.g., Cursor)

To use this server with an MCP-compatible client like Cursor, you need to configure the client to launch the server process using the wrapper script.

Create or modify the `mcp.json` file in your client's configuration directory (e.g., `~/.cursor/mcp.json` for Cursor).

**Example `mcp.json` configuration (Verified Working):**

```json
{
  "mcpServers": {
    "plexus-mcp-service": {
      "command": "/path/to/your/python/interpreter",
      "args": [
        "/path/to/your/project/Plexus/MCP/plexus_mcp_wrapper.py",
        "--host", "127.0.0.1",
        "--port", "8002",
        "--transport", "stdio",
        "--env-dir", "/path/to/your/project/your-project-directory"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "/path/to/your/project/Plexus"
      }
    }
  }
}
```

**Explanation:**

*   **`plexus-mcp-service`**: A unique name you give to this server configuration. Tools will be prefixed with this name (e.g., `mcp_plexus-mcp-service_list_plexus_scorecards`).
*   **`command`**: The absolute path to the Python interpreter used to run the wrapper script.
*   **`args`**: A list containing the absolute path to the `Plexus/MCP/plexus_mcp_wrapper.py` script, followed by arguments passed to the wrapper/server. **Crucially, this must include `--env-dir` followed by the absolute path to the directory containing the `.env` file** (e.g., `/Users/derek.norrbom/Capacity/your-project-directory`) which holds the dashboard credentials.
*   **`env`**: Environment variables for the server process. `PYTHONUNBUFFERED` is crucial. `PYTHONPATH` helps ensure Python can find the necessary Plexus modules.
*   **`cwd`**: This key is **omitted** in this working configuration. The wrapper script itself changes the directory to `/path/to/your/project/Plexus` before launching the server script, making this setting unnecessary at the client configuration level.

After configuring `mcp.json` and restarting your MCP client (e.g., Cursor), the defined tools should become available.

## Troubleshooting

If you encounter issues:

1.  **Check Logs**: Examine the `stderr` output from the wrapper/server process. Your MCP client might show this in a dedicated log view or console. Enable debug logging by setting the environment variable `MCP_DEBUG=1` (e.g., in the `env` section of `mcp.json`).
2.  **Verify Paths**: Double-check all absolute paths in `mcp.json` (`command`, `args`, `PYTHONPATH` if used).
3.  **Check Python Environment**: Ensure the Python interpreter specified in `command` has access to the required libraries (`mcp.server`, `plexus`, `python-dotenv`).
4.  **Plexus Configuration**: Ensure your Plexus Dashboard connection is configured correctly. **Verify that the `--env-dir` path specified in the `args` section of `mcp.json` correctly points to the directory containing the `.env` file with your Plexus Dashboard API URL and key.**
5.  **Wrapper Execution**: Confirm the `Plexus/MCP/plexus_mcp_wrapper.py` script has execute permissions (`chmod +x Plexus/MCP/plexus_mcp_wrapper.py`).