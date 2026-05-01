# AI Agent Integration Guide


## Project management with Kanbus

Use Kanbus for task management.
Why: Kanbus task management is MANDATORY here; every task must live in Kanbus.
When: Create/update the Kanbus task before coding; close it only after the change lands.
How: See CONTRIBUTING_AGENT.md for the Kanbus workflow, hierarchy, status rules, priorities, command examples, and the sins to avoid. Never inspect project/ or issue JSON directly (including with cat or jq); use Kanbus commands only.
Performance: Prefer kbs (Rust) when available; kanbus (Python) is equivalent but slower.
Warning: Editing project/ directly is a sin against The Way. Do not read or write anything in project/; work only through Kanbus.
Architecture rule: NEVER EVER add 'fallback' logic for ANYTHING unless the user EXPLICITLY says to do that. Never add additional complexity that creates additional ways to do things. There should be one correct way to do everything. Do not add layers of complexity for backward compatibility. Our goal is to make ONE WAY work. Do not add fallbacks.
Report persistence policy: ReportBlock output must always be stored as S3 file attachments. DynamoDB `ReportBlock.output` is metadata-only (`output_compacted` envelope + attachment pointer), never full report payload.

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

### The Tool: `execute_tactus`

The server exposes a single tool: **`execute_tactus`**.  It accepts a `tactus`
string (a Lua-flavoured DSL snippet) and executes it inside a sandboxed Plexus
runtime that injects a `plexus` module.  All Plexus functionality is reached
through sub-namespaces on that module.

#### Key namespaces

| Namespace | Methods | Purpose |
|---|---|---|
| `plexus.scorecards` | `list`, `info` | Enumerate and inspect scorecards |
| `plexus.score` | `info`, `evaluations`, `predict`, `set_champion` | Score details and predictions |
| `plexus.evaluation` | `run`, `info`, `find_recent`, `compare` | Run and inspect evaluations |
| `plexus.feedback` | `find`, `alignment` | Feedback items and confusion matrices |
| `plexus.item` | `last`, `info` | Inspect content items |
| `plexus.procedure` | `run`, `list`, `info`, `chat_sessions`, `chat_messages` | Procedures |
| `plexus.report` | `run`, `configurations_list` | Reports |
| `plexus.dataset` | `build_from_feedback_window`, `check_associated` | Datasets |
| `plexus.docs` | `list`, `get` | Built-in documentation |
| `plexus.api` | `list` | Discover all available namespaces/methods |

#### Quick examples

```lua
-- List scorecards
return plexus.scorecards.list({})

-- Get score info
return plexus.score.info({ id = "my-score-key" })

-- Run an evaluation
return plexus.evaluation.run({
  scorecard = "My Scorecard", score = "My Score", count = 50
})

-- Predict on an item
return plexus.score.predict({
  scorecard_name = "My Scorecard",
  score_name     = "My Score",
  item_id        = "abc-123"
})

-- Self-discovery
return plexus.api.list()
return plexus.docs.list({})
return plexus.docs.get({ name = "score-yaml-format" })
```

### Testing the Current MCP Code From CLI

When the Codex IDE MCP server cannot be restarted, use the CLI harness in
`MCP/test_harness.py` to start a fresh stdio MCP server from the current
working tree. The harness defaults may point at old local paths, so override
them at runtime instead of editing the file:

```bash
python - <<'PY'
import json, sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "MCP"))
import test_harness

test_harness.PYTHON = sys.executable
test_harness.WRAPPER = str(root / "MCP" / "plexus_fastmcp_wrapper.py")
test_harness.TARGET_CWD = str(root)
test_harness.SERVER_ENV = {
    **test_harness.os.environ,
    "PYTHONUNBUFFERED": "1",
    "PYTHONPATH": str(root),
}

with test_harness.MCPServer(timeout=180, verbose=False) as server:
    resp = server.call_tool(
        "execute_tactus",
        {"tactus": "return plexus.api.list({})"},
        timeout=180,
    )
    print(json.dumps(resp, indent=2))
PY
```

This is the preferred way to verify MCP changes against the latest local code
when the IDE is still holding an older loaded MCP process.

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
   - Agent creates DB records via `plexus.score.*` (through `execute_tactus`)

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
   - Run `plexus.feedback.alignment` (through `execute_tactus`)
   - Identify confusion patterns
   - Find specific examples via `plexus.feedback.find`

2. **Refinement** (`plexus-score-config-updater`):
   - Update prompts/logic in YAML
   - Run `plexus.evaluation.run` (feedback mode) to verify fix
   - Push new version if metrics improve

### 3. Running Evaluations

1. **Execution**:
   - Use `plexus.evaluation.run` (through `execute_tactus`) to dispatch evaluation
   - Monitor via `plexus.evaluation.info`

2. **Analysis**:
   - Use `plexus.evaluation.info` to get results
   - Agent interprets AC1, Accuracy, and Recall metrics
   - Agent recommends next steps

## Best Practices

- **Use the Specialized Agents**: Don't try to edit YAML yourself. Delegate to `plexus-score-config-updater`.
- **Use execute_tactus**: All Plexus data access and actions go through `execute_tactus`. There are no other MCP tools.
- **Trust the Runtime**: Use `plexus.*` namespaces for reading/writing data, not file edits (unless instructed).
- **Validate First**: Always run an evaluation or prediction test before declaring a task complete.
- **Check Documentation**: Use `plexus.docs.get({ name = "..." })` inside `execute_tactus` if you are unsure about formats.

## Direct CLI Policy (Critical)

- **Procedures and reports must be executed directly via CLI** (`plexus procedure ...`, `plexus report ...`) during development/debugging.
- **Do not use dispatcher state as evidence** that a direct CLI procedure/report is running or healthy.
- **Do not diagnose procedure/report crashes from task status alone**. Use process-level evidence first:
  1. Live process check (`ps`/PID)
  2. Direct CLI stdout/stderr logs
  3. Then dashboard task/procedure records for corroboration
- If a direct CLI run exits unexpectedly, capture and report the exact exception/traceback from that CLI run before proposing fixes.

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
