---
id: reports.acceptance-rate
title: Acceptance Rate Report
summary: "Score-result and optional item-level feedback acceptance rates for a scorecard or score."
namespace: reports
status: canonical
disclosure: reference
audience: agent
tags: [reports, feedback, acceptance]
related:
  - reports.reports-catalog
  - reports.acceptance-rate-timeline
---
# Acceptance Rate Report

Use Acceptance Rate when the user asks how often score results are accepted
versus corrected by feedback.

## Likely User Wording

- "acceptance rate"
- "reviewer acceptance"
- "how often do reviewers accept this?"
- "edit acceptance"

## Inputs

Required:
- `scorecard`

Optional:
- `score`
- `include_item_acceptance_rate`
- `max_items`
- `days`, or `start_date` plus `end_date`

## Tactus Run

```tactus
local h = plexus.report.run({
  block_class = "AcceptanceRate",
  block_config = {
    scorecard = "<resolved-scorecard-id>",
    score = "<optional-resolved-score-id>",
    days = 30,
    include_item_acceptance_rate = false,
    max_items = 0,
  },
  cache_key = "acceptance-rate:<scope>:30d",
  ttl_hours = 24,
  async = true,
  budget = { usd = 1.0, wallclock_seconds = 600, depth = 1, tool_calls = 3 },
})
return { handle_id = h["id"], task_id = h["dispatch_result"] and h["dispatch_result"]["task_id"] }
```

## Interpretation

High acceptance can mean the score is working well, but it can also reflect low
review intensity. Compare with feedback volume and alignment before drawing
strong conclusions.
