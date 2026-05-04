# Plexus Agent Knowledge Base

This directory is the canonical, token-efficient documentation for AI
agents working with Plexus. It is consumed at runtime by the
`plexus.docs.*` APIs inside the `execute_tactus` MCP tool, and it is
also readable by humans browsing the repo.

If you are an agent: do not read these files directly. Start with

```lua
return plexus.docs.list({})
```

and use the metadata summaries to choose what to load with

```lua
return plexus.docs.get({ key = "<id>" })
```

If you are a human: each topic is a small markdown file with YAML
frontmatter at the top. The frontmatter tells you what the topic is
for and what it relates to.

## Layout

```
documentation/agent/
  mcp/                  # execute_tactus runtime, discovery, async/handle protocol
  score-authoring/      # score and dataset YAML, classifiers, processors
  evaluation-feedback/  # alignment, acceptance, optimizer cookbook + objectives
  procedures/           # procedure authoring and runtime
  reports/              # report block authoring and persistence
  optimizer/            # direct CLI optimizer workflows
  repo-workflows/       # Kanbus, Git Flow, local environment
```

Each namespace contains an `_index.md` that summarises the namespace
itself.

## Frontmatter contract

Every topic file (other than this README) starts with a YAML
frontmatter block:

```yaml
---
id: <namespace>.<slug>            # canonical key for plexus.docs.get
title: Human-readable title
summary: One-sentence summary used by plexus.docs.list.
namespace: <namespace>            # one of the directories above
status: canonical | draft | deprecated
disclosure: overview | reference | cookbook | deep-dive
audience: agent
tags: [tag, tag]
related:                          # optional; list of related ids
  - <namespace>.<other-slug>
---
```

The repository module that backs `plexus.docs.*` lives in
`plexus/documentation/repository.py`.

## Companion content

- `documentation/agent-doc-audit.md` is the audit and migration map
  used to build this knowledge base.
- `documentation/supplemental/` holds longer-form architecture notes,
  spike records, and other human reference material that is not part
  of the agent-facing index.
- `documentation/source/` and `documentation/diagrams/` contain the
  Sphinx human documentation. Those are out of scope here.
