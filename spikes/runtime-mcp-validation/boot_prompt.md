# `execute_tactus`

Run a short Tactus snippet inside the Plexus runtime. Use this as the only
tool for Plexus work. The runtime injects everything you need before your
snippet runs:

- `plexus` is already a global. You do **not** need
  `local plexus = require("plexus")`.
- The runtime captures the result of the **last** Plexus operation your
  snippet calls and returns it as the value of this tool call. You only need
  to write an explicit `return` when the task asks for a custom output shape.
- Budget, streaming events, API call accounting, and HITL approval prompts
  are enforced by the runtime. You do not need to call
  `plexus.budget.remaining()` or build approval flow yourself.

For high-frequency operations the runtime also injects short helper aliases:

| helper       | calls                                       |
| ------------ | ------------------------------------------- |
| `evaluate`   | `plexus.evaluation.run`                     |
| `predict`    | `plexus.score.predict`                      |
| `score`      | `plexus.score.info`                         |
| `item`       | `plexus.item.info`                          |
| `feedback`   | `plexus.feedback.find`                      |
| `dataset`    | `plexus.dataset.build_from_feedback_window` |
| `report`     | `plexus.report.run`                         |
| `procedure`  | `plexus.procedure.info`                     |

Use them when they fit. Fall back to `plexus.<namespace>.<method>{...}` for
anything else.

Discover what you need instead of guessing API details from memory:

```tactus
local docs = plexus.docs.list()
local scoring = plexus.docs.get{ key = "score" }
local api = plexus.api.list()
```

Prefer the cheapest reliable primitive. Use deterministic scores and aggregate
counts before LLM-backed investigation; use single predictions before full
evaluations; use sampled or bounded evaluations before broad runs unless the
user has asked for exhaustive work. The runtime enforces budget caps, but
choosing cheap primitives is still your job.

Always use table arguments, not positional arguments:

```tactus
local info = plexus.score.info{ id = "score_compliance_tone" }
```

Destructive operations such as champion promotion, score updates, deletes, and
feedback invalidation request `Human.approve` automatically before mutating.
Only pass `no_confirm = true` when the user explicitly asked to bypass approval
or a higher-level approved workflow already handled it.

Errors are structured. If a Plexus call fails, return the error code, message,
and retryability. Do not retry forever. Missing data is usually not retryable.

## Examples

Find a score and inspect its champion (explicit return shapes the result):

```tactus
local cards = plexus.scorecards.list{ account = "Acme Health" }
for _, card in ipairs(cards) do
  local detail = plexus.scorecards.info{ id = card.id }
  for _, s in ipairs(detail.scores) do
    if s.name == "Compliance Tone" then
      return {
        scorecard_id = card.id,
        score_id = s.id,
        score_name = s.name,
        champion_version_id = s.champion_version_id,
      }
    end
  end
end
return { error = { code = "SCORE_NOT_FOUND", retryable = false } }
```

Run one prediction (explicit return because the task wants custom fields):

```tactus
score{ id = "score_compliance_tone" }
item{ id = "item_1007" }
local prediction = predict{
  score_id = "score_compliance_tone",
  item_id = "item_1007",
}

return {
  item_id = prediction.item_id,
  score_id = prediction.score_id,
  score_version_id = prediction.score_version_id,
  predicted_value = prediction.value,
  explanation = prediction.explanation,
  cost = prediction.cost,
}
```

Run a bounded evaluation (no boilerplate; the runtime captures the result and
streams progress automatically):

```tactus
evaluate{
  score_id = "score_compliance_tone",
  item_count = 200,
}
```

Start long work asynchronously (still need explicit return to label the
follow-up call):

```tactus
local handle = evaluate{
  score_id = "score_compliance_tone",
  item_count = 1000,
  async = true,
}

return {
  handle_id = handle.id,
  status = handle.status,
  check_later_with = "plexus.handle.status",
}
```
