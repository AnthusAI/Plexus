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
- `include_scores`, `exclude_scores`
- `days`, or `start_date` plus `end_date`
- `bucket_type`, `bucket_count`, `timezone`, `week_start`
- `rolling_min_items` (default `100`)
- `show_bucket_details`
- `split_score_timelines` (CLI default `true` for scorecard-level reports)

Use `score` for single-score mode. Use `include_scores` and `exclude_scores`
for scorecard-level reports that should aggregate only a filtered subset of
scores; do not combine `score` with include/exclude filters.

`rolling_min_items` controls the minimum sample size for each timeline point.
If a bucket has fewer than this many feedback items, the report adds older
feedback before the bucket end until it reaches the minimum or runs out of
history. Lookback is unbounded and may include feedback before the report start
date. `show_bucket_details` is still accepted for older callers, but the
dashboard renders timelines instead of per-bucket gauge cards.

The `plexus feedback report timeline` CLI persists scorecard-level reports as
top-level timeline blocks by default: one overall block followed by one block
per included score. The methodology explanation should appear once at the top
of the report or on the overall block, not repeated under every score chart.
Use `--single-block` only when a caller needs the legacy single report block
payload with all score series embedded together.

## Tactus Run

```tactus
local h = plexus.report.run({
  block_class = "FeedbackAlignmentTimeline",
  block_config = {
    scorecard = "<resolved-scorecard-id>",
    exclude_scores = {"<optional-score-id-or-name>"},
    days = 90,
    bucket_type = "trailing_7d",
    bucket_count = 12,
    rolling_min_items = 100,
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

This report measures stored production feedback alignment. Each chart asks:
"When production originally scored these items, how often did the stored score
answer agree with the final human correction recorded in feedback?"

For each feedback record:
- `FeedbackItem.initialAnswerValue` is the original production score answer captured on the feedback record.
- `FeedbackItem.finalAnswerValue` is the final human-corrected answer after review.
- `FeedbackItem.editedAt` determines which time bucket the feedback belongs to.

The time bucket is based on feedback edit time, not call time and not score
version release time. For each bucket, the report first uses feedback edited
inside that bucket. If the bucket has fewer than `rolling_min_items` records,
the point adds older feedback records until the sample reaches
`rolling_min_items` or no earlier feedback exists. That lookback only stabilizes
sparse buckets; the point still ends at the bucket end date.

Feedback items with `isInvalid == true` are excluded before bucketing and
rolling-window construction. Output metadata includes:
- `fetched_feedback_items`
- `ignored_invalid_feedback_items`
- `analyzed_feedback_items`

This report does not rerun historical champion versions, does not backtest
current prompts, and does not reconstruct what every champion version would
have done. It uses the answers already stored on feedback records.

The output includes `sample_policy` metadata that explains the bucket type,
minimum rolling sample size, unbounded lookback, and the answer fields used for
prediction/reference values. Each point includes:

- `bucket_item_count`: feedback items edited inside the bucket.
- `sample_item_count`: items actually used for that point; `item_count` matches this for compatibility.
- `lookback_item_count`: older feedback items added to reach the minimum sample.
- `sample_start`, `sample_end`: edited-time range of the rolling sample.
- `sample_extended`: whether lookback items were added.
- `sample_underfilled`: whether all available history still had fewer than `rolling_min_items`.

Look for sustained changes across buckets. A point with `sample_extended=true`
is still a rolling estimate ending at that bucket, not just the bucket's own
feedback.
