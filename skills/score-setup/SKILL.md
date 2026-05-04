---
name: Score Setup
description: Standard workflow for creating Plexus scorecard and score records via the GraphQL API. Administrative setup (name, external_id, description) only - NOT guidelines or configuration.
---

## Purpose

Create scorecard and score records in Plexus. Administrative setup
only — names, external ids, and short descriptions. Guidelines and
configuration are handled by separate agents and happen after these
records exist.

## Tooling

The Plexus MCP server exposes a single tool: `execute_tactus`. All
Plexus operations go through it via the injected `plexus.*` runtime.
Do not call the `plexus` CLI for setup.

```lua
return plexus.scorecards.list({})
return plexus.scorecards.info({ name = "<scorecard-name>" })
return plexus.scorecards.create({
  name        = "Acme Content Quality",
  key         = "acme-content-quality",
  external_id = "acme-content-quality",
  description = "Short description.",
})
return plexus.score.info({ id = "<score-id>" })
return plexus.score.create({
  scorecard_name = "Acme Content Quality",
  name           = "Medical Advice Detection",
  external_id    = "medical-advice",
  description    = "Detects whether content contains medical advice.",
})
```

## When to use this skill

- A user asks to "set up" or "create" a scorecard or score.
- A user needs the database records before working on guidelines or
  configuration.

## When NOT to use this skill

- Guidelines work — delegate to `plexus-score-guidelines-updater`.
- YAML configuration — delegate to `plexus-score-config-updater`.
- Classifier types, classes, labels, or scoring logic — those are
  handled during guidelines and configuration phases.

## Workflow

### Phase 1: Information gathering

For a scorecard, collect: `name`, `key` (web slug), `external_id`
(required, can equal `key`), `description`.

For a score, collect: scorecard name, `name`, `external_id`
(kebab-case), `description`.

Stop and ask the user if anything is missing. Do not invent values.

### Phase 2: Creation

For a scorecard:

1. Check if it exists with `plexus.scorecards.list({})`.
2. Create it with `plexus.scorecards.create({...})` if it does not
   exist.
3. Verify with `plexus.scorecards.info({ name = "..." })`.

For a score:

1. Check the parent scorecard with `plexus.scorecards.info`.
2. Create the score with `plexus.score.create({...})`.
3. Verify with `plexus.score.info({ id = "..." })`.

### Phase 3: Handoff

Summarize what was created and tell the user about the next steps:

- Guidelines via the `plexus-score-guidelines-updater` agent.
- Configuration via the `plexus-score-config-updater` agent.

## Critical rules

- Administrative scope only. Do not gather classifier mechanics here.
- Always verify creation after the create call.
- Use only `execute_tactus`; no CLI commands.
- For YAML or guidelines work, delegate to the dedicated agents.

## Pointers to canonical docs

- Score YAML format reference (read inside `execute_tactus`):
  `plexus.docs.get({ key = "score-authoring.score-yaml-format" })`
- Dataset YAML format reference:
  `plexus.docs.get({ key = "score-authoring.dataset-yaml-format" })`
- Scorecard processors:
  `plexus.docs.get({ key = "score-authoring.scorecard-processors" })`

## Success criteria

1. Scorecard or score record exists with correct metadata.
2. Existence verified via the runtime info call.
3. User informed about what was created and what comes next.
