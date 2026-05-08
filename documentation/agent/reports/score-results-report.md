---
id: reports.score-results-report
title: Score Results Report
summary: "Report for specific item identifiers and their score results."
namespace: reports
status: canonical
disclosure: reference
audience: agent
tags: [reports, score-results, items]
related:
  - reports.reports-catalog
---
# Score Results Report

Use Score Results Report when the user asks for report output for specific item
IDs or score-result examples.

## Likely User Wording

- "score results"
- "item results"
- "report on these item IDs"
- "show the result for item 123"

## Inputs

Required:
- `scorecard`
- at least one item identifier in `ids`

Optional:
- `score`

## Tactus Run

```tactus
local h = plexus.report.run({
  block_class = "ScoreResultsReport",
  block_config = {
    scorecard = "<resolved-scorecard-id>",
    score = "<optional-resolved-score-id>",
    ids = { "item-id-1", "item-id-2" },
  },
  cache_key = "score-results:<unique>",
  ttl_hours = 24,
  async = true,
  budget = { usd = 1.0, wallclock_seconds = 600, depth = 1, tool_calls = 3 },
})
return { handle_id = h["id"], task_id = h["dispatch_result"] and h["dispatch_result"]["task_id"] }
```

## Interpretation

Use this report for concrete item inspection. It is not an aggregate metric
report and should not be used to estimate accuracy, alignment, or feedback
quality.
