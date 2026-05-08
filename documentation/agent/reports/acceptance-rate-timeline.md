---
id: reports.acceptance-rate-timeline
title: Acceptance Rate Timeline Report
summary: "Time-bucketed score-result acceptance-rate trend for a scorecard or score."
namespace: reports
status: canonical
disclosure: reference
audience: agent
tags: [reports, feedback, acceptance, timeline]
related:
  - reports.reports-catalog
  - reports.acceptance-rate
---
# Acceptance Rate Timeline Report

Use Acceptance Rate Timeline when the user wants acceptance rate over time.

## Likely User Wording

- "acceptance timeline"
- "acceptance over time"
- "did acceptance improve?"
- "acceptance trend"

## Inputs

Required:
- `scorecard`

Optional:
- `score`
- `bucket_type`, `bucket_count`
- `show_bucket_details`
- `days`, or `start_date` plus `end_date`

## Tactus Run

```tactus
local h = plexus.report.run({
  block_class = "AcceptanceRateTimeline",
  block_config = {
    scorecard = "<resolved-scorecard-id>",
    score = "<optional-resolved-score-id>",
    days = 90,
    bucket_type = "trailing_7d",
    bucket_count = 12,
    show_bucket_details = false,
  },
  cache_key = "acceptance-rate-timeline:<scope>:90d",
  ttl_hours = 24,
  async = true,
  budget = { usd = 1.0, wallclock_seconds = 600, depth = 1, tool_calls = 3 },
})
return { handle_id = h["id"], task_id = h["dispatch_result"] and h["dispatch_result"]["task_id"] }
```

## Interpretation

Treat single-bucket changes carefully. A trend is meaningful when volume is
adequate and the direction persists across adjacent buckets.
