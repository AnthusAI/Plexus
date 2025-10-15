# Plexus MCP Server - Refactored Structure

This directory contains a refactored version of the Plexus MCP server where each tool is organized into separate files for better maintainability and organization.

## Directory Structure

```
MCP/
├── server.py                    # Main server entry point
├── shared/                      # Shared utilities and setup
│   ├── setup.py                # Core setup and Plexus imports
│   └── utils.py                # Common utility functions
└── tools/                      # Individual tool implementations
    ├── scorecard/              # Scorecard management tools
    │   └── scorecards.py       # List, info, evaluation tools
    ├── score/                  # Score management tools
    │   └── management.py       # Score CRUD, configuration tools
    ├── report/                 # Report management tools
    │   └── reports.py          # Report listing and details
    ├── item/                   # Item management tools
    ├── task/                   # Task management tools
    ├── feedback/               # Feedback analysis tools
    └── util/                   # Utility tools
        └── debug.py            # Debug, think, documentation tools
```

## Key Changes

### 1. Modular Organization
- Each category of tools is in its own directory
- Individual tool files focus on related functionality
- Clear separation of concerns

### 2. Shared Infrastructure
- `shared/setup.py`: Handles Plexus imports, stdout redirection, and core initialization
- `shared/utils.py`: Common utility functions like URL generation, account management, helper functions

### 3. Tool Registration Pattern
Each tool file exports a `register_*_tools(mcp: FastMCP)` function that registers its tools with the MCP server:

```python
def register_scorecard_tools(mcp: FastMCP):
    """Register scorecard tools with the MCP server"""
    
    @mcp.tool()
    async def plexus_scorecards_list(...):
        # Implementation
```

### 4. Consistent Error Handling
All tools use the same pattern for:
- Stdout capture and redirection
- Error logging
- Import error handling
- Client creation and credential validation

## Usage

### Running the Server
```bash
# With environment directory
python server.py --env-dir /path/to/env/dir

# With specific transport
python server.py --transport stdio

# With custom host/port for SSE
python server.py --host 0.0.0.0 --port 8003
```

### Setting Up MCP Server with Claude Code

To use the Plexus MCP server with Claude Code, you need to configure it properly to handle complex arguments.

#### Simple Setup (without complex arguments)
```bash
bclaude mcp add plexus /opt/anaconda3/envs/py311/bin/python /Users/ryan.porter/Projects/Plexus/MCP/plexus_fastmcp_wrapper.py
```

#### Advanced Setup (with arguments like --target-cwd)
The `bclaude mcp add` command has limitations with complex arguments. For advanced configurations, manually edit your `~/.claude.json` file:

```json
{
  "mcpServers": {
    "plexus": {
      "command": "/opt/anaconda3/envs/py311/bin/python",
      "args": [
        "/Users/ryan.porter/Projects/Plexus/MCP/plexus_fastmcp_wrapper.py",
        "--target-cwd",
        "/Users/ryan.porter/Projects/Plexus/"
      ]
    }
  }
}
```

**Why this is necessary:** The `bclaude mcp add` command cannot properly parse complex argument strings with flags. When you try to pass a quoted string like `"command --flag value"`, it treats the entire string as the command name rather than parsing the arguments separately.

#### Verifying the Connection
```bash
bclaude mcp list
```

You should see:
```
plexus: /opt/anaconda3/envs/py311/bin/python /Users/ryan.porter/Projects/Plexus/MCP/plexus_fastmcp_wrapper.py - ✓ Connected
```

### Adding New Tools
1. Create a new tool file in the appropriate category directory
2. Implement the tool functions with `@mcp.tool()` decorators
3. Create a `register_*_tools(mcp)` function
4. Import and call the registration function in `server.py`

Example:
```python
# tools/new_category/new_tools.py
def register_new_tools(mcp: FastMCP):
    @mcp.tool()
    async def new_tool():
        # Implementation
        pass

# server.py
from tools.new_category.new_tools import register_new_tools

def register_all_tools():
    # ... existing registrations
    register_new_tools(mcp)
```

## Migration Status

### Completed
- ✅ Shared setup and utilities
- ✅ Utility tools (debug, think, documentation)
- ✅ Scorecard tools (list, info, evaluation)
- ✅ Score management tools (info, delete - partial)
- ✅ Report tools (list, info - partial)
- ✅ Main server structure

### Remaining
- ⏳ Complete score tools (configuration, pull, push, update)
- ⏳ Complete report tools (last, configurations)
- ⏳ Item management tools (last, info)
- ⏳ Task management tools (last, info)
- ⏳ Feedback analysis tools (summary, find, predict)

## Benefits of This Structure

1. **Maintainability**: Easier to find and modify specific functionality
2. **Testability**: Individual tool modules can be tested in isolation
3. **Scalability**: Easy to add new tool categories without bloating main file
4. **Collaboration**: Multiple developers can work on different tool categories
5. **Code Reuse**: Shared utilities prevent duplication
6. **Clear Dependencies**: Import structure makes dependencies explicit

## Backward Compatibility

The refactored server provides the same MCP tool interface as the original monolithic file, ensuring existing clients continue to work without changes.