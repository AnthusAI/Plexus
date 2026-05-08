---
id: reports.score-champion-version-timeline
title: Score Champion Version Timeline Report
summary: "Timeline of champion score-version changes for a scorecard or one score."
namespace: reports
status: canonical
disclosure: reference
audience: agent
tags: [reports, score-versions, champion, timeline]
related:
  - reports.reports-catalog
  - reports.scorecard-history
---
# Score Champion Version Timeline Report

Use Score Champion Version Timeline when the user wants to see champion
promotions over time.

## Likely User Wording

- "champion timeline"
- "champion versions"
- "promotion timeline"
- "what changed from champion to champion?"

## Inputs

Required:
- `scorecard`

Optional:
- `score`
- `days`, or `start_date` plus `end_date`
- `include_unchanged` to include initial champion entries

## Tactus Run

```tactus
local h = plexus.report.run({
  block_class = "ScoreChampionVersionTimeline",
  block_config = {
    scorecard = "<resolved-scorecard-id>",
    score = "<optional-resolved-score-id>",
    days = 365,
    include_unchanged = false,
  },
  cache_key = "champion-version-timeline:<scope>:365d",
  ttl_hours = 24,
  async = true,
  budget = { usd = 1.0, wallclock_seconds = 600, depth = 1, tool_calls = 3 },
})
return { handle_id = h["id"], task_id = h["dispatch_result"] and h["dispatch_result"]["task_id"] }
```

## Interpretation

This report is best for change chronology and champion promotion history. Use
Scorecard History when the user wants richer version notes, diffs, and
stakeholder summaries.
