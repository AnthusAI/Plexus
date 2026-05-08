---
id: reports.feedback-alignment-timeline
title: Feedback Alignment Timeline Report
summary: "Time-bucketed feedback alignment trend for a scorecard or score."
namespace: reports
status: canonical
disclosure: reference
audience: agent
tags: [reports, feedback, alignment, timeline]
related:
  - reports.reports-catalog
  - reports.feedback-alignment
---
# Feedback Alignment Timeline Report

Use Feedback Alignment Timeline when the user wants agreement or AC1 over time.

## Likely User Wording

- "alignment timeline"
- "AC1 trend"
- "feedback alignment over time"
- "did alignment improve?"

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
  block_class = "FeedbackAlignmentTimeline",
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
  cache_key = "feedback-alignment-timeline:<scope>:90d",
  ttl_hours = 24,
  async = true,
  budget = { usd = 1.0, wallclock_seconds = 600, depth = 1, tool_calls = 3 },
})
return { handle_id = h["id"], task_id = h["dispatch_result"] and h["dispatch_result"]["task_id"] }
```

## Interpretation

Look for sustained changes across buckets, not one-bucket noise. Sparse buckets
can produce unstable alignment values, so mention volume when interpreting a
trend.
