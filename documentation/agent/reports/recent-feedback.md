---
id: reports.recent-feedback
title: Recent Feedback Report
summary: "Recent feedback rows for a scorecard or score, useful for inspection and examples."
namespace: reports
status: canonical
disclosure: reference
audience: agent
tags: [reports, feedback, recent, examples]
related:
  - reports.reports-catalog
---
# Recent Feedback Report

Use Recent Feedback when the user wants examples or the latest feedback rows,
not aggregate metrics.

## Likely User Wording

- "recent feedback"
- "latest feedback"
- "show feedback rows"
- "examples of feedback"

## Inputs

Required:
- `scorecard`

Optional:
- `score`
- `max_feedback_items`
- `days`, or `start_date` plus `end_date`

## Tactus Run

```tactus
local h = plexus.report.run({
  block_class = "RecentFeedback",
  block_config = {
    scorecard = "<resolved-scorecard-id>",
    score = "<optional-resolved-score-id>",
    days = 30,
    max_feedback_items = 500,
  },
  cache_key = "recent-feedback:<scope>:30d",
  ttl_hours = 24,
  async = true,
  budget = { usd = 1.0, wallclock_seconds = 600, depth = 1, tool_calls = 3 },
})
return { handle_id = h["id"], task_id = h["dispatch_result"] and h["dispatch_result"]["task_id"] }
```

## Interpretation

Use this report to inspect concrete feedback examples. It does not estimate
alignment or acceptance by itself.
