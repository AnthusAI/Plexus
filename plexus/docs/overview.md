# `execute_tactus` Overview

`execute_tactus` is the single Plexus MCP tool. You submit a short Tactus
(Lua) snippet; the runtime executes it inside the Plexus sandbox and
returns a structured envelope. Use this as the only Plexus tool.

## Runtime ground rules

- `plexus` is a global. You do **not** need to import it yourself.
- The runtime captures the result of the **last** Plexus operation your
  snippet calls and returns it as the value of this tool call. You only
  need to write an explicit `return` when you want a custom output shape.
- Always use **table** arguments, never positional arguments:
  `plexus.score.info{ id = "..." }` not `plexus.score.info("...")`.
- Errors are structured. If a Plexus call fails, return the error code,
  message, and retryability. Do not retry forever; missing data is
  usually not retryable.
- Destructive operations (champion promotion, score updates, deletes,
  feedback invalidation) request `Human.approve` automatically before
  mutating. Pass `no_confirm = true` only when the user explicitly asked
  to bypass approval or a higher-level approved workflow already handled
  it.
- Budget caps, streaming events, API call accounting, and HITL approval
  are enforced by the runtime. You do not need to call
  `plexus.budget.remaining()` or build approval flow yourself.
- Long-running async calls (`plexus.evaluation.run`, `plexus.report.run`,
  `plexus.procedure.run` with `async = true`) **must** include an
  explicit child budget table:
  `budget = { usd = <number>, wallclock_seconds = <number>, depth = <int>, tool_calls = <int> }`.
  See `long-running-apis` and `handles-and-budgets`.
- Prefer the cheapest reliable primitive: deterministic reads before LLM
  inference; single predictions before evaluations; bounded evaluations
  before broad runs.

## Helper aliases

The runtime injects short helper aliases so common operations stay
readable. High-frequency aliases include `evaluate`, `predict`,
`scorecards`, `scorecard`, `score`, `item`, `last_item`, `feedback`,
`feedback_alignment`, `dataset`, `report`, `report_configs`,
`procedure`, `procedures`, `procedure_sessions`, `procedure_messages`.
Every advertised API also has a canonical `namespace_method` helper such
as `scorecards_list`, `score_info`, `evaluation_info`, `evaluation_run`,
`handle_status`, `handle_await`, `handle_cancel`, `docs_list`,
`docs_get`, `api_list`. Use helpers when they fit; fall back to
`plexus.<namespace>.<method>{...}` for anything else.

## Discovery

Discover what's available instead of guessing API details from memory.
Two discovery primitives are always free of cost:

```tactus
local apis = plexus.api.list()
local topics = plexus.docs.list()
local overview = plexus.docs.get{ key = "overview" }
```

`plexus.api.list()` returns the catalog of every namespace and method.
`plexus.docs.list()` returns every documentation key (including nested
keys like `evaluation-and-feedback/feedback-alignment`).
`plexus.docs.get{ key = "..." }` returns the markdown content for any
listed key.

The themed docs in `plexus/docs/` are the canonical guide for each area:

- `discovery` — how to enumerate APIs, docs, and runtime context.
- `read-apis` — read-only reference patterns
  (scorecards, scores, items, feedback).
- `long-running-apis` — `async = true` contract and budget requirements.
- `handles-and-budgets` — `handle.peek`, `handle.await`, `handle.cancel`,
  and how parent budgets are carved into child budgets.
- `score-and-dataset-authoring/` — score and dataset YAML, rubric memory.
- `evaluation-and-feedback/` — feedback alignment, evaluation alignment,
  optimizer cookbook and procedures.
- `procedures/` — Plexus Procedures runtime APIs.
- `reports/` — Plexus Reports runtime APIs.

## Examples

### 1. Find a scorecard by name

```tactus
local cards = scorecards{}
for _, card in ipairs(cards) do
  if card.name == "SelectQuote HCS Medium-Risk" then
    return {
      id = card.id,
      key = card.key,
      external_id = card.externalId,
    }
  end
end
return { error = { code = "SCORECARD_NOT_FOUND", retryable = false } }
```

### 2. Inspect a score

```tactus
local detail = score{ id = "score_compliance_tone" }
return {
  score_id = detail.id,
  name = detail.name,
  champion_version_id = detail.championVersionId,
}
```

### 3. Get an item's info

```tactus
return item{ id = "item_1007" }
```

### 4. Run a single prediction

```tactus
local prediction = predict{
  score_id = "score_compliance_tone",
  item_id = "item_1007",
}

return {
  predicted_value = prediction.value,
  explanation = prediction.explanation,
  cost = prediction.cost,
}
```

### 5. Run a bounded evaluation (synchronous)

```tactus
evaluate{
  score_id = "score_compliance_tone",
  item_count = 200,
}
```

The runtime captures the evaluation summary as the tool's return value
and streams progress events to the MCP client automatically.

### 6. Discover more

```tactus
local apis = api_list()
local topics = docs_list()
local feedback_guide = docs_get{ key = "feedback-alignment" }
return {
  api_namespaces = apis,
  topic_count = #topics,
  guide_excerpt = feedback_guide.content:sub(1, 200),
}
```

### 7. Long-running async with handle and explicit budget

```tactus
local handle = evaluate{
  score_id = "score_compliance_tone",
  item_count = 1000,
  async = true,
  budget = {
    usd = 0.50,
    wallclock_seconds = 1800,
    depth = 1,
    tool_calls = 10,
  },
}

return {
  handle_id = handle.id,
  status = handle.status,
  check_later_with = "plexus.handle.status",
}
```

A later `execute_tactus` call can poll or wait:

```tactus
local snapshot = handle_status{ id = "<id>" }
local result = handle_await{ id = "<id>", timeout = "PT10M" }
handle_cancel{ id = "<id>" }
```

## Response envelope

Every `execute_tactus` call returns:

- `ok` — boolean.
- `value` — your `return` value (or the captured last-helper-result).
- `error` — `{ code, message, retryable, ... }` or `null`.
- `cost` — `{ usd, wallclock_seconds, tokens, llm_calls, tool_calls,
  workers, depth_max_observed, budget_remaining_* }`.
- `trace_id` — opaque ID for the full run trace.
- `partial` — true when streaming was cut off.
- `api_calls` — list of every Plexus API the snippet invoked
  (e.g. `["plexus.scorecards.list", "plexus.score.info"]`).
