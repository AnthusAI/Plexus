# Acceptance Rate Report

Measures how often score results are accepted by human reviewers without correction.
A high acceptance rate means the AI is making decisions that humans agree with.

**Also known as / common synonyms:**
- "acceptance report" → this report
- "score acceptance report" / "score acceptance rate" → this report
- "feedback report" or "feedback analysis" → see `feedback-alignment` instead
- "acceptance rate" by itself → this report

## What it measures

- **`score_result_acceptance_rate`** — fraction of score results that were *not* corrected by
  a human reviewer (primary metric)
- **`feedback_items_total`** — how many feedback items exist in the window
- **`feedback_items_changed`** — how many were corrections (the human disagreed with the AI)
- **`item_acceptance_rate`** (optional) — fraction of *items* where no score result was corrected

## Quick call

```tactus
-- Simplest form: scorecard + score + days window
return acceptance_rate{
  scorecard = "My Scorecard",
  score     = "My Score",
  days      = 30,
  sync      = true,
}
```

`acceptance_rate` is a pre-wired alias for `plexus.report.acceptance_rate`.
`sync = true` runs the block inline and returns the result immediately.
Drop `sync = true` and add `async = true` to fire-and-forget and get a handle back.

## Full parameter reference

| Parameter | Type | Default | Description |
|---|---|---|---|
| `scorecard` | string | required | Scorecard name, key, or ID |
| `score` | string | optional | Score name or ID (omit for all scores on the scorecard) |
| `days` | int | — | Trailing window in days |
| `start_date` | string | — | Inclusive start date `YYYY-MM-DD` |
| `end_date` | string | — | Inclusive end date `YYYY-MM-DD` |
| `include_item_acceptance_rate` | bool | false | Also compute item-level acceptance (slower) |
| `max_items` | int | 0 (no cap) | Cap on item rows in the output |
| `include_items` | bool | false | Include per-item rows in sync output (omitted by default to keep response small) |
| `sync` | bool | false | Run inline and return output now |
| `async` | bool | false | Dispatch and return a handle immediately |
| `fresh` | bool | false | Bypass cache and recompute |
| `cache_key` | string | — | Explicit cache key for deduplication |
| `ttl_hours` | float | 24 | Cache TTL in hours |

## Namespace form

```tactus
-- Via the full namespace (equivalent to the alias above)
return plexus.report.acceptance_rate{
  scorecard = "My Scorecard",
  score     = "My Score",
  days      = 30,
  sync      = true,
}
```

## Async / handle form

```tactus
local handle = acceptance_rate{
  scorecard = "My Scorecard",
  score     = "My Score",
  days      = 30,
  async     = true,
}
return { handle_id = handle.id, status = handle.status }
```

Then poll or await:
```tactus
return handle_status{ id = "<handle_id>" }
-- or block until done:
return handle_await{ id = "<handle_id>", timeout = "PT5M" }
```

## With item-level acceptance

```tactus
return acceptance_rate{
  scorecard                    = "My Scorecard",
  score                        = "My Score",
  days                         = 14,
  include_item_acceptance_rate = true,
  sync                         = true,
}
-- summary will include: total_items, accepted_items, corrected_items, item_acceptance_rate
```

## Output shape

```json
{
  "report_type": "acceptance_rate",
  "scorecard_name": "...",
  "score_name": "...",
  "date_range": { "start": "...", "end": "..." },
  "summary": {
    "total_score_results": 1200,
    "accepted_score_results": 1056,
    "corrected_score_results": 144,
    "score_result_acceptance_rate": 0.88,
    "feedback_items_total": 200,
    "feedback_items_valid": 190,
    "feedback_items_changed": 144
  },
  "items": [ ... ]
}
```

## Typical workflow

1. Run `acceptance_rate` to get the aggregate `score_result_acceptance_rate`.
2. Compare across recent windows (`days = 7` vs `days = 30`) to spot trends.
3. If acceptance is low, run `feedback_alignment` to see *which* classes the AI is getting wrong.
4. Use the optimizer (`plexus.procedure.optimize`) to improve alignment.
