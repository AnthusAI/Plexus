# Discovery

How to enumerate what's available inside the Plexus runtime from
`execute_tactus`. Discovery primitives are read-only and effectively free
of cost.

## API catalog

`plexus.api.list()` returns the full catalog of advertised namespaces
and methods:

```tactus
return api_list()
```

Result shape:

```lua
{
  ["plexus.scorecards"] = { "info", "list" },
  ["plexus.score"] = { "contradictions", "evaluations", "info", "predict", "pull", "test", "update" },
  ["plexus.evaluation"] = { "compare", "find_recent", "info", "run" },
  ["plexus.handle"] = { "await", "cancel", "peek", "status" },
  ["plexus.docs"] = { "get", "list" },
  ["plexus.api"] = { "list" },
  -- ...
}
```

Use `api_list()` whenever you are unsure which namespace owns a method,
when adding a new operation, or when validating that an alias resolves
to the API you expect.

## Documentation index

`plexus.docs.list()` returns every documentation key that
`plexus.docs.get` will resolve, including nested keys:

```tactus
return docs_list()
```

Example return value:

```lua
{
  "discovery",
  "evaluation-and-feedback/evaluation-alignment",
  "evaluation-and-feedback/feedback-alignment",
  "evaluation-and-feedback/optimizer-cookbook",
  "handles-and-budgets",
  "long-running-apis",
  "overview",
  "procedures",
  "read-apis",
  "reports",
  "score-and-dataset-authoring/dataset-yaml-format",
  "score-and-dataset-authoring/score-yaml-format",
  -- ...
}
```

`README.md` files at any depth are intentionally omitted from
`docs_list()` (they are still readable through the `theme-*` aliases
exposed by `get_plexus_documentation`).

## Reading a doc

`plexus.docs.get{ key = "..." }` returns the raw markdown content for a
single key. Both nested and legacy flat keys resolve:

```tactus
local nested = docs_get{ key = "evaluation-and-feedback/feedback-alignment" }
local legacy = docs_get{ key = "feedback-alignment" }
return { same_content = nested.content == legacy.content }
```

The legacy flat keys are kept for backward compatibility with the
`get_plexus_documentation` MCP tool used by other agents during the
transition.

## Discovery patterns

### Find the right doc for a task

```tactus
local topics = docs_list()
local matches = {}
for _, key in ipairs(topics) do
  if key:find("optimizer") then
    table.insert(matches, key)
  end
end
return matches
```

### Verify an alias before use

```tactus
local apis = api_list()
return {
  has_evaluation_compare = (function()
    for _, m in ipairs(apis["plexus.evaluation"] or {}) do
      if m == "compare" then return true end
    end
    return false
  end)(),
}
```

### Bootstrap context for a new agent

A useful first call when you are not sure where to start:

```tactus
return {
  apis = api_list(),
  topics = docs_list(),
  overview = docs_get{ key = "overview" }.content,
}
```

This is moderately verbose but gives downstream calls a complete map of
the runtime surface in one turn.
