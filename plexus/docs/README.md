# Plexus Documentation Files

This directory contains documentation files that are accessible through the Plexus MCP Server's `get_plexus_documentation` tool.

## Available Documentation

- **score-yaml-format.md**: Complete guide to Score YAML configuration format including LangGraph, node types, dependencies, and best practices

## Adding New Documentation Files

To add a new documentation file that can be accessed via the MCP server:

1. **Add the documentation file** to this directory (`plexus/docs/`)
2. **Update the tool configuration** in `MCP/plexus_fastmcp_server.py`:
   - Locate the `get_plexus_documentation` tool function
   - Add your new file to the `valid_files` dictionary mapping
   - Update the tool's docstring to list the new filename option

### Example

To add a new file called `evaluation-metrics.md`:

1. Create `plexus/docs/evaluation-metrics.md`
2. In `MCP/plexus_fastmcp_server.py`, update the `valid_files` dictionary:
   ```python
   valid_files = {
       "score-yaml-format": "score-yaml-format.md",
       "evaluation-metrics": "evaluation-metrics.md"  # Add this line
   }
   ```
3. Update the tool's docstring to include:
   ```
   - evaluation-metrics: Guide to evaluation metrics and their configuration
   ```

## File Naming Conventions

- Use descriptive, hyphenated names for the file keys (e.g., `score-yaml-format`)
- Use `.md` extension for all documentation files
- Keep file names concise but clear
- File keys should be easy to remember and type

## Benefits of This Approach

- **Easy to update**: Documentation can be updated by simply editing the markdown files
- **Version controlled**: Documentation changes are tracked in git
- **Accessible to AI**: The MCP server can provide documentation on-demand to AI agents
- **Maintainable**: No need to modify server code when updating documentation content 