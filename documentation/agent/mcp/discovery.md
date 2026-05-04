---
id: mcp.discovery
title: Discovery
summary: Enumerate available APIs and docs from inside execute_tactus using api.list and docs.list.
namespace: mcp
status: canonical
disclosure: reference
audience: agent
tags: [mcp, discovery]
related:
  - mcp.execute-tactus-overview
  - mcp.read-apis
---
# Discovery

How to enumerate what's available inside the Plexus runtime from
`execute_tactus`. Discovery primitives are read-only and effectively
free of cost.

## API catalog

`plexus.api.list()` returns the full catalog of advertised namespaces
and methods:

```tactus
return plexus.api.list({})
```

Result shape:

```lua
{
  ["plexus.scorecards"] = { "info", "list" },
  ["plexus.score"]      = { "contradictions", "evaluations", "info",
                            "predict", "pull", "set_champion", "test",
                            "update" },
  ["plexus.evaluation"] = { "compare", "find_recent", "info", "run" },
  ["plexus.handle"]     = { "await", "cancel", "peek", "status" },
  ["plexus.docs"]       = { "get", "list" },
  ["plexus.api"]        = { "list" },
  -- ...
}
```

Use `plexus.api.list({})` when you are unsure which namespace owns a
method, when adding a new operation, or when validating that a helper
alias resolves to the API you expect.

## Documentation index

`plexus.docs.list({})` returns metadata summaries for every indexed
documentation topic. Each entry carries `id`, `title`, `summary`,
`namespace`, `status`, `disclosure`, `tags`, and `related` — enough to
decide which topic to fetch in full.

```tactus
return plexus.docs.list({})
```

Example return value:

```lua
{
  {
    id        = "evaluation-feedback.feedback-alignment",
    title     = "Feedback Alignment",
    summary   = "Measuring agreement between AI and human feedback...",
    namespace = "evaluation-feedback",
    tags      = { "feedback", "alignment", "ac1" },
    related   = { "evaluation-feedback.evaluation-alignment" },
    -- ...
  },
  {
    id        = "mcp.execute-tactus-overview",
    title     = "execute_tactus Overview",
    namespace = "mcp",
    -- ...
  },
  -- ...
}
```

You can filter by namespace:

```tactus
return plexus.docs.list({ namespace = "score-authoring" })
```

`README.md` files and `_index.md` namespace landing pages are
intentionally omitted from `plexus.docs.list({})`. Their content lives
elsewhere (top-level project READMEs and namespace `_index` topics
fetched explicitly by id).

## Reading a doc

`plexus.docs.get({ key = "..." })` resolves a topic by its canonical
namespaced id and returns both metadata and content:

```tactus
local doc = plexus.docs.get({ key = "evaluation-feedback.feedback-alignment" })
return {
  title    = doc.metadata.title,
  related  = doc.metadata.related,
  preview  = doc.content:sub(1, 200),
}
```

There is one canonical lookup model. Ids are namespaced (for example
`mcp.discovery`, `score-authoring.score-yaml-format`). There is no
legacy stem-only fallback.

## Discovery patterns

### Find topics relevant to a task

```tactus
local entries = plexus.docs.list({})
local matches = {}
for _, entry in ipairs(entries) do
  if entry.id:find("optimizer") then
    table.insert(matches, entry)
  end
end
return matches
```

### Verify an alias before use

```tactus
local apis = plexus.api.list({})
return {
  has_evaluation_compare = (function()
    for _, m in ipairs(apis["plexus.evaluation"] or {}) do
      if m == "compare" then return true end
    end
    return false
  end)(),
}
```

### Bootstrap context for a new task

A useful first call when you are unsure where to start:

```tactus
return {
  apis     = plexus.api.list({}),
  topics   = plexus.docs.list({}),
  overview = plexus.docs.get({ key = "mcp.execute-tactus-overview" }).content,
}
```

This is moderately verbose but gives downstream calls a complete map
of the runtime surface in one turn.
