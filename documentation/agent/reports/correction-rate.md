---
id: reports.correction-rate
title: Correction Rate Report
summary: "How often feedback edits correct score results for a scorecard or score."
namespace: reports
status: canonical
disclosure: reference
audience: agent
tags: [reports, feedback, correction]
related:
  - reports.reports-catalog
  - reports.acceptance-rate
---
# Correction Rate Report

Use Correction Rate when the user asks about correction or edit behavior rather
than acceptance.

## Likely User Wording

- "correction rate"
- "edit rate"
- "how often do reviewers change it?"
- "correction behavior"

## Inputs

Required:
- `scorecard`

Optional:
- `score`
- `max_items`
- `days`, or `start_date` plus `end_date`

## Tactus Run

```tactus
local h = plexus.report.run({
  block_class = "CorrectionRate",
  block_config = {
    scorecard = "<resolved-scorecard-id>",
    score = "<optional-resolved-score-id>",
    days = 30,
    max_items = 0,
  },
  cache_key = "correction-rate:<scope>:30d",
  ttl_hours = 24,
  async = true,
  budget = { usd = 1.0, wallclock_seconds = 600, depth = 1, tool_calls = 3 },
})
return { handle_id = h["id"], task_id = h["dispatch_result"] and h["dispatch_result"]["task_id"] }
```

## Interpretation

Correction rate is the complement of acceptance-oriented thinking, but the
exact denominator can differ by report mode. Use this for operational review,
not as a full alignment substitute.
