---
id: reports.feedback-volume-timeline
title: Feedback Volume Timeline Report
summary: "Time-bucketed feedback volume trend for a scorecard or score."
namespace: reports
status: canonical
disclosure: reference
audience: agent
tags: [reports, feedback, volume, timeline]
related:
  - reports.reports-catalog
---
# Feedback Volume Timeline Report

Use Feedback Volume Timeline when the user wants to understand feedback volume
over time.

## Likely User Wording

- "feedback volume"
- "volume timeline"
- "feedback trend"
- "how much feedback did we get?"

## Inputs

Required:
- `scorecard`

Optional:
- `score`
- `days`, or `start_date` plus `end_date`
- `bucket_type`, `bucket_count`, `timezone`, `week_start`
- `show_bucket_details`

## Tactus Run

```tactus
local h = plexus.report.run({
  block_class = "FeedbackVolumeTimeline",
  block_config = {
    scorecard = "<resolved-scorecard-id>",
    score = "<optional-resolved-score-id>",
    days = 90,
    bucket_type = "trailing_7d",
    bucket_count = 12,
    timezone = "UTC",
    week_start = "monday",
    show_bucket_details = false,
  },
  cache_key = "feedback-volume-timeline:<scope>:90d",
  ttl_hours = 24,
  async = true,
  budget = { usd = 1.0, wallclock_seconds = 600, depth = 1, tool_calls = 3 },
})
return { handle_id = h["id"], task_id = h["dispatch_result"] and h["dispatch_result"]["task_id"] }
```

## Interpretation

Use volume to contextualize alignment, acceptance, and contradiction reports.
Low volume makes other feedback metrics less reliable.
