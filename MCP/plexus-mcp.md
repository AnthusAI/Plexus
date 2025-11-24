# Plexus MCP System Overview

The Plexus MCP (Multi-Agent Cooperative Protocol) system enables AI agents and tools to interact with Plexus functionality through a standardized protocol. This document provides an overview of the system architecture and key components.

> **For a user guide on interacting with these tools, please see the [Agent Integration Guide](../AGENTS.md).**

## Core Components

### Server Implementation
- **Main Server**: [MCP/plexus_fastmcp_server.py](mdc:Plexus-2/Plexus-2/Plexus-2/MCP/plexus_fastmcp_server.py) - Core server implementation using the `fastmcp` library
- **Legacy Compatibility**: [MCP/plexus_mcp_server.py](mdc:Plexus-2/Plexus-2/Plexus-2/MCP/plexus_mcp_server.py) - Compatibility wrapper that forwards to the FastMCP server for existing configurations
- **Wrapper Script**: [MCP/plexus_fastmcp_wrapper.py](mdc:Plexus-2/Plexus-2/Plexus-2/MCP/plexus_fastmcp_wrapper.py) - Handles proper stdout/stderr separation and environment setup

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
   
   **Scorecard Management**:
   - `list_plexus_scorecards`: Lists scorecards from the Plexus Dashboard. Can filter by account, name, or key.
   - `get_plexus_scorecard_info`: Gets detailed information about a specific scorecard, including its sections and scores.
   - `get_plexus_score_details`: Gets detailed information for a specific score, including its configuration and version history.
   - `find_plexus_score`: ✅ **TESTED** Intelligent search to find a specific score within a scorecard using flexible identifiers. Supports complex queries like "X score on Y scorecard".
   - `get_plexus_score_configuration`: ✅ **TESTED** Gets the YAML configuration for a specific score version, with syntax highlighting and formatting.
   - `update_plexus_score_configuration`: ✅ **TESTED & WORKING** Updates a score's configuration by creating a new version with the provided YAML content. **First successful mutation tool in MCP server**.
   - `plexus_evaluation_run`: Run an accuracy evaluation on a Plexus scorecard using the same code path as the CLI.
   
   **Report Management**:
   - `list_plexus_reports`: Lists reports from the Plexus Dashboard. Can be filtered by account or report configuration ID. Results are sorted by most recent first.
   - `get_plexus_report_details`: Gets detailed information for a specific report, including its output and any generated blocks.
   - `get_latest_plexus_report`: Gets full details for the most recent report, optionally filtered by account or report configuration ID.
   - `list_plexus_report_configurations`: List available report configurations.
   
   **Item Management**:
   - `get_latest_plexus_item`: Gets the most recent item for the default account, with optional score results.
   - `get_plexus_item_details`: Gets detailed information about a specific item by its ID, with optional score results.
   
   **Task Management** *(NEW)*:
   - `get_latest_plexus_task`: Gets the most recent task for an account, with optional filtering by task type (e.g., 'Evaluation', 'Report').
   - `get_plexus_task_details`: Gets detailed information about a specific task by its ID, including all task stages and progress information.
   
   **Utility Tools**:
   - `think`: Use as a scratchpad when working with Plexus tools to plan approach and verify parameters.
   - `get_score_yaml_documentation`: ✅ **AVAILABLE** Provides comprehensive documentation about the YAML configuration format for scores, including examples and field descriptions.
   - `debug_python_env`: Debug the Python environment, including available modules and paths.

### Recent Improvements
- Consolidated report tools for simpler, more consistent usage
- Added deep link URL generation for easier access to dashboard resources
- Fixed account resolution in `list_plexus_report_configurations` to properly handle case-insensitive matches
- Improved GraphQL query formatting for consistent results
- Added robust fallback mechanisms for API response handling
- Enhanced logging for better troubleshooting
- Added Item management tools for viewing the latest item or looking up items by ID
- Item tools include complete score results and detailed information, mirroring CLI functionality
- **Fixed Item model compatibility**: Updated Item model to use correct GraphQL fields, removing obsolete `data` field
- **Added Task management tools** *(NEW)*: 
  - `get_latest_plexus_task` for retrieving the most recent task with optional type filtering
  - `get_plexus_task_details` for getting complete task information including stages
  - Task tools include progress tracking, stage information, and dashboard URLs
- **Enhanced MCP protocol organization**: Added structured tool categories and `think` tool requirement
- **Score Configuration Management** ✅ **SUCCESSFULLY IMPLEMENTED & TESTED**: 
  - `find_plexus_score` for intelligent score discovery across scorecards
  - `get_plexus_score_configuration` for retrieving formatted YAML configurations
  - `update_plexus_score_configuration` for updating score configurations (**FIRST WORKING MUTATION TOOL**)
  - `get_score_yaml_documentation` for understanding YAML format and structure
  - Support for complex tool chains like "find Grammar Check score on Quality Assurance scorecard"
  - **Confirmed working in production with real scorecard updates**

### Production Testing Success ✅

**First Successful Mutation Operation** (January 2025):
- **Scorecard**: "CS3 - Audigy TPA" 
- **Score**: "Good Call"
- **Operation**: Updated score configuration via `update_plexus_score_configuration`
- **Changes**: Added note "Claude.app was here (via MCP) for Ryan" to YAML configuration
- **Result**: Successfully created new score version and updated champion version
- **Version Note**: "Updated via Claude.app MCP for Ryan"
- **Status**: ✅ **CONFIRMED WORKING** in Claude.app MCP integration

This represents a major milestone as the first working mutation operation in the Plexus MCP server, enabling AI agents to not just read but also modify Plexus configurations through natural language interactions.

### Known Issues & Upcoming Fixes
- **Task Type Filtering**: The `get_latest_plexus_task` function with evaluation type filtering needs troubleshooting - task type matching may not work correctly for evaluation tasks
- **Case Sensitivity**: Task type filtering may be case-sensitive and not handle variations in task type naming

## Implementation References

### CLI Commands (Reference Implementation)

#### Item Commands
- **Main CLI Implementation**: `plexus/cli/ItemCommands.py`
  - Contains `items.command()` and `item.command()` implementations
  - Includes `get_score_results_for_item()` function for retrieving score results
  - Has `format_item_content()` and `format_score_results_content()` for rich formatting
  - Implements `last` and `info` commands that we mirror in MCP

#### Task Commands
- **Main CLI Implementation**: `plexus/cli/TaskCommands.py`
  - Contains `tasks.command()` and `task.command()` implementations
  - Includes `format_task_content()` function for rich task display formatting
  - Implements `last` and `info` commands for task management
  - Uses GSI queries with `listTaskByAccountIdAndUpdatedAt` for proper ordering
  - Supports task stage retrieval and progress tracking

#### Score Configuration Commands *(NEW)*
- **Main CLI Implementation**: `plexus/cli/ScoreCommands.py`
  - Contains `pull` and `push` commands for score configuration management
  - `pull` downloads score YAML configuration to local file
  - `push` uploads YAML configuration and creates new score version
  - Uses `CreateScoreVersion` and `UpdateScore` GraphQL mutations
  - Includes YAML path utilities for consistent file organization
- **Scorecard CLI Implementation**: `plexus/cli/ScorecardCommands.py`
  - Contains `push` command for uploading entire scorecard YAML files
  - Handles bulk score creation and updates from scorecard definitions
  - Supports complex scorecard structure with sections and multiple scores

### Reusable Components
- **Item Model**: `plexus/dashboard/api/models/item.py`
  - `Item` class with `get_by_id()`, `from_dict()`, and `fields()` methods
  - GraphQL query building and data parsing
- **ScoreResult Model**: `plexus/dashboard/api/models/score_result.py`
  - `ScoreResult` class for handling score result data
  - Includes metadata and trace parsing functionality
- **Task Model**: `plexus/dashboard/api/models/task.py`
  - `Task` class with `get_by_id()`, `from_dict()`, and `fields()` methods
  - Task lifecycle management (create, update, start_processing, complete_processing)
  - Stage management and progress tracking
- **TaskStage Model**: `plexus/dashboard/api/models/task_stage.py`
  - `TaskStage` class for handling individual task stage data
  - Progress tracking with processed/total items
  - Status management (PENDING, RUNNING, COMPLETED, FAILED)
- **Scorecard Model**: `plexus/dashboard/api/models/scorecard.py`
  - `Scorecard` class with `get_by_id()`, `get_by_key()`, and `create()` methods
  - Flexible identifier resolution (ID, name, key, external ID)
  - GraphQL query building for scorecard and section data
- **Score Model**: `plexus/dashboard/api/models/score.py` *(NEW)*
  - `Score` class for score management and configuration
  - Version management and champion version tracking
  - YAML configuration handling and validation
- **Client Utilities**: `plexus/cli/client_utils.py`
  - `create_client()` function for API client creation
- **Account Resolution**: `plexus/cli/reports/utils.py`
  - `resolve_account_id_for_command()` for default account handling from environment variables

### MCP Server Files
- **Main MCP Server**: `MCP/plexus_fastmcp_server.py`
  - Current tool implementations and server setup using FastMCP library
  - Pattern for async tool handlers and error handling
- **Legacy Compatibility**: `MCP/plexus_mcp_server.py`
  - Forwards to FastMCP server for backward compatibility
- **MCP Wrapper**: `MCP/plexus_fastmcp_wrapper.py`
  - Environment setup and stdout/stderr handling

### Key Functions to Reference
1. **Item Retrieval**:
   - `ItemCommands.py:296` - `last()` command implementation
   - `ItemCommands.py:338` - `info()` command implementation
   - `ItemCommands.py:129` - `get_score_results_for_item()` function

2. **Task Retrieval**:
   - `TaskCommands.py:243` - `last()` command implementation for tasks
   - `TaskCommands.py:429` - `info()` command implementation for tasks
   - `TaskCommands.py:19` - `format_task_content()` function for task display

3. **Data Formatting**:
   - `ItemCommands.py:19` - `format_item_content()` for rich item display
   - `ItemCommands.py:172` - `format_score_results_content()` for score results
   - `TaskCommands.py:19` - `format_task_content()` for rich task display including stages

4. **Score Configuration Management** *(NEW)*:
   - `ScoreCommands.py:846` - `pull()` command implementation for downloading YAML
   - `ScoreCommands.py:895` - `push()` command implementation for uploading YAML
   - `ScorecardCommands.py:1558` - Scorecard-level push with score updates
   - `plexus_tool.py:315` - Tool-based score configuration updates

5. **GraphQL Queries and Mutations**:
   - `item.py:fields()` - Field selection for Item queries
   - `score_result.py:fields()` - Field selection for ScoreResult queries
   - `task.py:fields()` - Field selection for Task queries (includes stages)
   - `task_stage.py:fields()` - Field selection for TaskStage queries
   - **Score Mutations** *(NEW)*:
     - `CreateScoreVersion` - Creates new score version with YAML configuration
     - `UpdateScore` - Updates score metadata and champion version
     - Pattern for handling YAML content in GraphQL mutations

### Implementation Strategy
1. **Reuse Models**: Import and use existing model classes for data handling
   - Item/ScoreResult models for item-related functionality
   - Task/TaskStage models for task-related functionality
   - Scorecard/Score models for scorecard and score management *(NEW)*
2. **Adapt Formatting Logic**: Convert rich formatting to plain text for MCP responses
3. **Mirror Query Logic**: Use same GraphQL queries as CLI commands
   - Use GSI queries for proper sorting (e.g., `listTaskByAccountIdAndUpdatedAt`)
   - Include related data (stages for tasks, score results for items)
4. **Account Resolution**: Use same account resolution logic as other MCP tools
5. **URL Generation**: Include dashboard URLs for easy navigation to resources
6. **Score Configuration Management** *(NEW)*:
   - Use existing `pull`/`push` patterns from CLI for YAML handling
   - Implement mutation support following GraphQL patterns
   - Support complex tool chains for score discovery and management
   - Provide YAML documentation and validation support

## Implementation Details

### Server Architecture
- Built on `fastmcp` library for improved performance and easier development
- Uses async/await for non-blocking operations
- Implements proper error handling and logging
- Supports Python 3.11+ (recommended for FastMCP)
- ✅ **Supports both read and write operations** (queries and mutations)
- ✅ **Production-tested** with real scorecard configuration updates

### Tool Implementation Pattern
1. Define tool schema with input/output specifications using FastMCP decorators
2. Implement handler function with error handling
3. Register tool with server using `@mcp.tool()` decorators
4. Add read-only annotation where appropriate (skip for mutation tools)
5. **Mutation Tools** ✅ **IMPLEMENTED & TESTED**: Follow GraphQL mutation patterns for updating data
   - Use `CreateScoreVersion` and `UpdateScore` mutations for configuration updates
   - Implement proper YAML validation and error handling
   - Return detailed results including new version IDs and dashboard URLs
   - **Successfully tested** with production scorecard updates

### Error Handling
- All errors are captured and returned as structured responses
- Detailed logging to stderr for debugging
- Clean error messages for client consumption

## Configuration

### Claude Code Installation
To install the Plexus MCP server for use with Claude Code for all projects for the current user, use the following command:

```bash
claude mcp add -s user plexus-mcp-service: /opt/anaconda3/envs/py311/bin/python /Users/username/Projects/MCP/plexus_fastmcp_wrapper.py
```

Replace `/Users/username/Projects/Plexus` with the actual path to your Plexus project directory.

This command will:
1. Add the MCP server to Claude Code's configuration
2. Set the correct transport mode (`stdio`) 
3. Configure the necessary environment variables
4. Enable access to all Plexus tools within Claude Code conversations

### Client Setup (Other MCP Clients)
To use with other MCP clients (e.g., Cursor), configure `mcp.json`:
```json
{
  "mcpServers": {
    "plexus-mcp-service": {
      "command": "/path/to/python",
      "args": [
        "/path/to/plexus_fastmcp_wrapper.py",
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

**Important**: Ensure the paths point to the correct Plexus project directory you want to use. The MCP server will import Plexus modules from the `PYTHONPATH` and current working directory, so make sure these point to the development version you're working with, not an unrelated installed package.

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

### Development Environment Considerations
- **Multiple Plexus Installations**: Development workstations often have multiple Plexus project clones and installations
- **Python Path Priority**: The MCP server imports Plexus modules from the current working directory first, then falls back to installed packages
- **CLI vs MCP Imports**: Be careful about which client creation functions to import:
  - ✅ Use `plexus.cli.client_utils.create_client()` - properly sets up account context from environment variables
  - ❌ Avoid `plexus.cli.ScorecardCommands.create_client()` - doesn't configure account context
- **Testing Approach**: When testing MCP functionality, run from the project directory you want to test against
- **Environment Variables**: Ensure `.env` file is in the correct project directory and loaded properly

## Troubleshooting
- Check stderr for detailed error messages
- Verify environment variables are loaded
- Ensure Python version is 3.11+
- Confirm proper stdout/stderr separation
- Validate tool schemas and implementations

### Common Issues
- **Account Resolution Errors**: If you see `Variable 'key' has coerced Null value for NonNull type 'String!'`, check:
  - `PLEXUS_ACCOUNT_KEY` environment variable is set
  - Using `client_utils.create_client()` instead of `ScorecardCommands.create_client()`
  - `.env` file is in the correct directory and loaded
- **Import Errors**: If MCP tools fail to import Plexus modules, verify:
  - Running from the correct project directory
  - Python path includes the current project
  - Not accidentally importing from a different Plexus installation
- **Wrong Plexus Version**: If CLI behavior doesn't match expectations:
  - Check `which plexus` to see which installation is being used
  - Use `python -m plexus.cli.CommandLineInterface` to run from current directory
  - Verify project directory has the expected CLI commands available
- **GraphQL Field Errors**: If you see `Cannot query field 'data' on type 'Item'`:
  - This indicates an outdated Item model is being used
  - Restart the MCP server to ensure latest code is loaded
  - Check that the correct `plexus_fastmcp_server.py` is being executed
  - Verify that test files are using the current Item model structure
- **Task Type Filtering Issues**: If `get_latest_plexus_task` with task type filtering doesn't work:
  - Task type values may not match expected strings (case sensitivity)
  - Task type field might contain different values than expected
  - Check actual task data with `get_latest_plexus_task()` (no filter) to see available task types
  - Verify that task type filtering logic matches the actual data structure

## Logging
- MCP logs are stored in `~/Library/Logs/Claude`
- You can monitor logs in real-time using `tail -f ~/Library/Logs/Claude/mcp.log`
- Logs contain detailed information about protocol communication and tool execution
- Useful for debugging connection issues and tool failures
