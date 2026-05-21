# Agent Guide

This is the entry point for AI coding agents working in this repository. It
is intentionally short. Canonical, token-efficient documentation lives in
`documentation/agent/` and is exposed to Tactus and chat agents through the
Plexus MCP server's `execute_tactus` tool.

## Repository rules

These rules apply to every change, human or agent.

- **Project management is mandatory.** Every source-code change must be
recorded in Kanbus before code is written. The full ritual lives in
`[CONTRIBUTING_AGENT.md](CONTRIBUTING_AGENT.md)`. Use `kbs` (Rust) or
`kanbus` (Python) commands; never read or edit `project/` directly.
- **One way to do everything.** Do not add fallback logic, compatibility
layers, or alternate paths unless the user explicitly asks for them.
- **Git Flow.** Branch from `develop` (`feature/...`, `bugfix/...`,
`chore/...`). Never commit directly to `develop` or `main`. Open a PR
into `develop` only after Kanbus tasks are `done`/`closed` and the
user confirms.
- **Outside-in BDD.** Stories define behavior in Gherkin. Production
code exists only to make a failing specification pass.
- **Direct CLI policy.** Procedures and reports are run directly via
`plexus procedure ...` or `plexus report ...` during development; do
not diagnose runs from dispatcher state alone.
- **Report persistence.** ReportBlock output goes to S3 attachments;
DynamoDB stores only a compact metadata envelope.

## Internal research (agent knowledge base)

Before guessing how a feature works, research the indexed docs in two
steps (progressive disclosure):

1. **`plexus.docs.list`** — metadata only (`id`, `title`, `summary`,
   `namespace`, `tags`, `related`). Cheap; safe to call often.
2. **`plexus.docs.get`** — full markdown body for one canonical `id`.

```lua
return plexus.docs.list({ namespace = "score-authoring" })
return plexus.docs.get({ key = "repo-workflows.internal-research" })
```

There is no semantic search over agent docs; filter by namespace and
read summaries, then follow `related` links. The Python implementation
is `plexus/documentation/repository.py` (`DocumentationRepository`).
Canonical cookbook: load topic `repo-workflows.internal-research` via
`plexus.docs.get`, or read `skills/internal-research/SKILL.md` when not
using MCP.

Scorecard **rubric memory** (Biblicus corpora under `*.knowledge-base/`)
is a separate system — see `score-authoring.rubric-memory`, not agent KB.

## How agents discover APIs and documentation

Plexus exposes a single MCP tool: `**execute_tactus`**. Inside that tool,
all functionality is accessed through the injected `plexus.`* runtime.
Documentation is part of that runtime:

```lua
-- Discover available namespaces and methods.
return plexus.api.list({})

-- List every documentation topic with metadata summaries.
return plexus.docs.list({})

-- Filter to a specific namespace.
return plexus.docs.list({ namespace = "score-authoring" })

-- Load a topic by its canonical id.
return plexus.docs.get({ key = "mcp.execute-tactus-overview" })
```

Each entry returned by `plexus.docs.list` carries `id`, `title`,
`summary`, `namespace`, `status`, `disclosure`, `tags`, and `related`
fields parsed from YAML frontmatter. Use those summaries to decide
which topic to fetch in full.

## Documentation namespaces

- `mcp` — execute_tactus, discovery, read APIs, long-running APIs,
handles, and budgets.
- `score-authoring` — score and dataset YAML, classifier interface,
scorecard processors, rubric memory and consistency.
- `evaluation-feedback` — feedback and evaluation alignment, acceptance
rate, optimizer cookbook, optimizer objectives.
- `procedures` — authoring and running Plexus procedures.
- `reports` — report block authoring and persistence.
- `optimizer` — direct CLI optimizer workflows.
- `repo-workflows` — Kanbus, Git Flow, and local environment.

The full audit and target layout are in
`[documentation/agent-doc-audit.md](documentation/agent-doc-audit.md)`.

## Skills and personas

Project-specific skills live in `skills/` and `.claude/agents/`. They
delegate the heavy reading to `plexus.docs.*`, so each persona file
stays small and focused on its workflow.

## MCP setup

See `[MCP/README.md](MCP/README.md)` for installation and how to run a
local server against the current working tree.