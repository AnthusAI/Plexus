# AI Agent Integration Guide


## Project management with Kanbus

Use Kanbus for Plexus-internal project management only.
Why: Kanbus task management is MANDATORY for changes to Plexus code, docs, infra, tooling, and agent workflows.
Critical confidentiality boundary: NO CLIENT INFORMATION may be stored in Kanbus. This is absolute.
Forbidden in Kanbus titles/descriptions/comments/attachments: client names; client scorecard names; client score names; client evaluation names; client optimization procedure names; client-specific incidents/problems/data.
When: Create/update the Kanbus task before coding on Plexus-internal changes; close it only after the change lands.
How: See CONTRIBUTING_AGENT.md for the Kanbus workflow, hierarchy, status rules, priorities, command examples, and the sins to avoid. Never inspect project/ or issue JSON directly (including with cat or jq); use Kanbus commands only.
Performance: Prefer kbs (Rust) when available; kanbus (Python) is equivalent but slower.
Warning: Editing project/ directly is a sin against The Way. Do not read or write anything in project/; work only through Kanbus.

## Overview

Plexus provides comprehensive AI agent integration through the MCP (Model Context Protocol) server, enabling AI assistants like Claude and Cursor to interact natively with Plexus functionality. This integration transforms Plexus from a passive framework into an active **AI Agent Operating System** where human developers and AI agents collaborate on scoring, evaluation, and improvement workflows.

## MCP Server

### What is the MCP Server?

The Plexus MCP server is the bridge between your AI assistant and the Plexus backend. It exposes a standardized set of tools that allow agents to:

- **Read** data (scorecards, scores, reports, items, evaluations)
- **Write** configurations (create scorecards, update score YAML, run evaluations)
- **Analyze** performance (feedback analysis, confusion matrices)
- **Execute** workflows (run procedures, generate reports)

It is located in the `/MCP` directory and is production-tested for real-world usage, including the ability to safely update mission-critical score configurations.

### Available Tools

The server provides over 45 specialized tools organized by category:

#### Scorecard Management
- `plexus_scorecards_list`: List and filter scorecards
- `plexus_scorecard_info`: Get detailed structure of a scorecard
- `plexus_scorecard_create`: Create new scorecards
- `plexus_scorecard_update`: Update scorecard metadata

#### Score Configuration
- `plexus_score_info`: Get score details and version history
- `plexus_score_update`: **RECOMMENDED** - Update score configuration via YAML
- `plexus_score_create`: Create new scores
- `plexus_score_pull/push`: Local file-based configuration management

#### Evaluation & Testing
- `plexus_evaluation_run`: Run accuracy or feedback evaluations
- `plexus_evaluation_info`: Get detailed evaluation metrics
- `plexus_predict`: Test scores on specific items

#### Feedback Analysis
- `plexus_feedback_analysis`: Generate confusion matrices and AC1 stats
- `plexus_feedback_find`: Find specific feedback items (FN/FP)

#### Task & Item Management
- `plexus_task_last/info`: Monitor background task progress
- `plexus_item_last/info`: Inspect specific content items

#### Procedures & Experiments
- `plexus_procedure_create/run`: Orchestrate multi-step workflows
- `plexus_procedure_list/info`: Manage existing procedures

### Installation and Setup

For detailed installation instructions, see [MCP/README.md](MCP/README.md).

**Quick Setup for Cursor:**
Add to your `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "plexus": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/project/MCP/plexus_fastmcp_wrapper.py"]
    }
  }
}
```

## .claude Directory Structure

Plexus uses the `.claude` directory to define standardized behaviors for AI agents.

### Skills (`/skills/`)
Skills are reusable definitions of **how** to perform specific tasks. They provide the "muscle memory" for agents.

- **plexus-score-setup**: Standard workflow for creating scorecard/score records via the API. Ensures all metadata is captured correctly before creation.
- **plexus-guidelines**: Formatting and validation rules for creating high-quality guidelines documents.

### Agents (`/.claude/agents/`)
Agents are specialized personas with specific permissions, tools, and instructions for complex workflows.

- **plexus-score-config-updater**: The **only** agent authorized to touch score YAML configurations. It follows a strict safe-deployment protocol (Load Docs -> Pull -> Edit -> Validate -> Push).
- **plexus-score-guidelines-updater**: Specialist for writing and refining score guidelines based on policy documents.
- **plexus-alignment-analyzer**: Analyzes human feedback to identify patterns in False Positives/Negatives and recommends improvements.
- **evaluation-analyzer**: Statistical analyst for interpreting evaluation results. Examines confusion matrix segments and delegates transcript analysis to `evaluation-score-result-analyzer` to protect its own context window.
- **evaluation-score-result-analyzer**: Sub-agent used internally by `evaluation-analyzer`. Processes individual score results (transcripts, predictions, edit comments) and returns concise, token-efficient insights.
- **development-environment**: Critical setup reference enforcing Python 3.11 and the conda `py311` environment. Consult this agent before running tests or installing dependencies.

## Common Workflows

### 1. Creating a New Score

This workflow uses a chain of skills and agents:

1. **Setup Phase** (User + `plexus-score-setup` skill):
   - User requests new score
   - Agent gathers metadata (Name, Key, Description)
   - Agent creates DB records via `plexus_score_create`

2. **Guidelines Phase** (User + `plexus-score-guidelines-updater`):
   - Agent interviews user about criteria
   - Agent drafts guidelines markdown
   - User reviews and approves

3. **Configuration Phase** (`plexus-score-config-updater`):
   - Agent takes guidelines
   - Agent loads YAML documentation
   - Agent creates configuration YAML
   - Agent runs validation evaluation
   - Agent pushes new version

### 2. Improving Score Accuracy (Feedback Loop)

1. **Analysis** (`plexus-alignment-analyzer`):
   - Run `plexus_feedback_analysis`
   - Identify confusion patterns
   - Find specific examples via `plexus_feedback_find`

2. **Refinement** (`plexus-score-config-updater`):
   - Update prompts/logic in YAML
   - Run `plexus_evaluation_run` (feedback mode) to verify fix
   - Push new version if metrics improve

### 3. Running Evaluations

1. **Execution**:
   - Use `plexus_evaluation_run` to dispatch evaluation
   - Monitor via `plexus_task_info`

2. **Analysis**:
   - Use `plexus_evaluation_info` to get results
   - Agent interprets AC1, Accuracy, and Recall metrics
   - Agent recommends next steps

## Best Practices

- **Use the Specialized Agents**: Don't try to edit YAML yourself. Delegate to `plexus-score-config-updater`.
- **Trust the Tools**: Use MCP tools for reading/writing data, not file edits (unless instructed).
- **Validate First**: Always run an evaluation or prediction test before declaring a task complete.
- **Check Documentation**: Use `get_plexus_documentation` if you are unsure about formats.
- **Do Not Monkeypatch Tactus**: Plexus production code must never replace, wrap, or modify Tactus classes or methods at runtime. We own Tactus; add the required supported API there, release it, and upgrade Plexus to that release. Pytest's `monkeypatch` fixture remains appropriate for isolated test doubles.

## Nested AGENTS.md Guides

Subsystems with their own agent guidance:

- [dashboard/AGENTS.md](dashboard/AGENTS.md) — Dashboard frontend development guide (Next.js 14, Amplify Gen2, task dispatch architecture).
- [plexus/procedures/AGENTS.md](plexus/procedures/AGENTS.md) — Procedure DSL quick reference (LuaDSL, HITL patterns, idempotent execution, CLI commands).

## Troubleshooting

- **"Tool not found"**: Restart the MCP server (in Cursor: CMD+Shift+P -> "Cursor: Restart MCP Server").
- **"GraphQL Error"**: Check your environment variables in `.env`.
- **"Validation Failed"**: The score config updater protects you from pushing bad YAML. Read the error message and correct the format.
