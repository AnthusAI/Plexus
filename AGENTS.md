# AI Agent Integration Guide


## Project management with Kanbus

Use Kanbus for task management.
Why: Kanbus task management is MANDATORY here; every task must live in Kanbus.
When: Create/update the Kanbus task before coding; close it only after the change lands.
How: See CONTRIBUTING_AGENT.md for the Kanbus workflow, hierarchy, status rules, priorities, command examples, and the sins to avoid. Never inspect project/ or issue JSON directly (including with cat or jq); use Kanbus commands only.
Performance: Prefer kbs (Rust) when available; kanbus (Python) is equivalent but slower.
Warning: Editing project/ directly is a sin against The Way. Do not read or write anything in project/; work only through Kanbus.
Architecture rule: NEVER EVER add 'fallback' logic for ANYTHING unless the user EXPLICITLY says to do that. Never add additional complexity that creates additional ways to do things. There should be one correct way to do everything. Do not add layers of complexity for backward compatibility. Our goal is to make ONE WAY work. Do not add fallbacks.

## SOP compliance

** When completing an epic/milestone/task/feature/fix, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds AND the CI passes in GitHub, which you need to check with `gh`.  Set a timer and wait for it to finish, and if it's not done yet then wait longer.  Iterate on fixing the problem until CI passes in GitHub Actions.

## Git Flow policy (mandatory)

- This repository uses git-flow. Do not commit directly to `develop` or `main`.
- Start every change on a dedicated branch from `develop` (for example `feature/...`, `bugfix/...`, or `chore/...`).
- Commit and push only to that branch, then open a PR into `develop` only when all related Kanbus tasks are `done`/`closed` and the user confirms to open a PR (or explicitly requests a PR).
- Only merge to `main` via PR from `develop` after required checks pass.
- If you accidentally commit to `develop` or `main`, stop and ask before applying any history rewrite or revert strategy.

**MANDATORY WORKFLOW:**

0. **You should have already filed an Epic and Stories with behavior specs for what you're doing!** - Do that now if you made a mistake and didn't.
1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

- Work is NOT complete until `git push` succeeds and it passes in GitHub Actions CI.

## Overview

Plexus provides comprehensive AI agent integration through the MCP (Model Context Protocol) server, enabling AI assistants like Claude and Cursor to interact natively with Plexus functionality. This integration transforms Plexus from a passive framework into an active **AI Agent Incubator** where human developers and AI agents collaborate on scoring, evaluation, and improvement workflows.

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

### Skills (`/.claude/skills/`)
Skills are reusable definitions of **how** to perform specific tasks. They provide the "muscle memory" for agents.

- **plexus-score-setup**: Standard workflow for creating scorecard/score records via the API. Ensures all metadata is captured correctly before creation.
- **plexus-guidelines**: Formatting and validation rules for creating high-quality guidelines documents.

### Agents (`/.claude/agents/`)
Agents are specialized personas with specific permissions, tools, and instructions for complex workflows.

- **plexus-score-config-updater**: The **only** agent authorized to touch score YAML configurations. It follows a strict safe-deployment protocol (Load Docs -> Pull -> Edit -> Validate -> Push).
- **plexus-score-guidelines-updater**: Specialist for writing and refining score guidelines based on policy documents.
- **plexus-alignment-analyzer**: Analyzes human feedback to identify patterns in False Positives/Negatives and recommends improvements.
- **evaluation-analyzer**: statistical analyst for interpreting evaluation results.

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

## Debugging Procedures

### LLM Debug Mode (`PLEXUS_DEBUG_LLM`)

When developing or troubleshooting procedures, you can enable full visibility into what the LLM sees and produces by setting the `PLEXUS_DEBUG_LLM` environment variable:

```bash
PLEXUS_DEBUG_LLM=1 plexus procedure run --id <procedure-id>
```

This logs to stderr (via Rich logging) at every LLM turn:

- **`[LLM_DEBUG] SYSTEM PROMPT`** — The full system prompt sent to the model
- **`[LLM_DEBUG] HISTORY`** — Every message in the conversation history, with role labels and sequence numbers
- **`[LLM_DEBUG] USER MESSAGE`** — The user message for this turn
- **`[LLM_DEBUG] TOOLS`** — All tools available to the agent, listed by name
- **`[LLM_DEBUG] MODEL RESPONSE`** — The model's full text response
- **`[LLM_DEBUG] TOOL CALLS`** — Any tool calls the model made

This works for both streaming and non-streaming agent turns. The debug output is implemented in the Tactus agent layer (`tactus/dspy/agent.py`) and is triggered by any non-empty value of `PLEXUS_DEBUG_LLM`.

**When to use this:**
- Verifying that conversation context is constructed correctly for the optimizer agent
- Checking that tool responses are being included/excluded as expected
- Debugging unexpected model behavior by inspecting the exact input it received
- Confirming that the system prompt, history, and injected context look correct

### ChatMessage toolResponse Storage

ChatMessage records store only compact references (IDs, status, short scalars) in the `toolResponse` field — not full evaluation data. Large structures like `confusionMatrix`, `misclassification_analysis`, and `root_cause` are dropped at storage time because they already live in the referenced Evaluation record. The frontend dereferences evaluation IDs via `useEvaluationById` to fetch the full data for display. See `_slim_tool_response_for_storage()` in `plexus/cli/procedure/chat_recorder.py`.

## Troubleshooting

- **"Tool not found"**: Restart the MCP server (in Cursor: CMD+Shift+P -> "Cursor: Restart MCP Server").
- **"GraphQL Error"**: Check your environment variables in `.env`.
- **"Validation Failed"**: The score config updater protects you from pushing bad YAML. Read the error message and correct the format.
