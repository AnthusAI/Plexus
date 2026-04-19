# Plexus Documentation Files

This directory contains documentation files that are accessible through the Plexus MCP Server's `get_plexus_documentation` tool.

## Available Documentation

- **score-concepts.md**: Shared score and optimizer mental model
- **score-yaml-format.md**: High-level score-authoring patterns, cross-cutting YAML features, and optimization techniques
- **score-yaml-langgraph.md**: LangGraphScore implementation recipes
- **score-yaml-tactusscore.md**: TactusScore implementation recipes
- **feedback-alignment.md**: Baseline-first workflow for score improvement against human feedback
- **dataset-yaml-format.md**: Dataset source and transformation reference
- **optimizer-cookbook.md**: Change-selection guide for the optimizer
- **optimizer-procedures.md**: Feedback Alignment Optimizer procedure reference

## Adding New Documentation Files

To add a new documentation file that can be accessed via the MCP server:

1. **Add the documentation file** to this directory (`plexus/docs/`)
2. **Update the shared catalog** in `MCP/shared/documentation_catalog.py`:
   - Add the filename key to `DOC_FILENAME_MAP`
   - Add the one-line description to `DOC_DESCRIPTION_MAP`
3. **Run the documentation tests** in `MCP/tools/documentation/docs_test.py`

### Example

To add a new file called `evaluation-metrics.md`:

1. Create `plexus/docs/evaluation-metrics.md`
2. In `MCP/shared/documentation_catalog.py`, update the shared catalog:
   ```python
   DOC_FILENAME_MAP = {
       "score-yaml-format": "score-yaml-format.md",
       "evaluation-metrics": "evaluation-metrics.md",
   }
   ```
3. Add a description entry:
   ```
   "evaluation-metrics": "Guide to evaluation metrics and their configuration"
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
- **Maintainable**: Both MCP loader paths read from one shared documentation catalog
