---
id: reports.feedback-alignment
title: Feedback Alignment Report
summary: "Agreement between score predictions and reviewer feedback, including AC1/alignment and mismatch patterns."
namespace: reports
status: canonical
disclosure: reference
audience: agent
tags: [reports, feedback, alignment, ac1]
related:
  - reports.reports-catalog
  - evaluation-feedback.feedback-alignment
---
# Feedback Alignment Report

Use Feedback Alignment when the user asks how well a score agrees with
reviewer feedback.

## Likely User Wording

- "alignment report"
- "feedback alignment"
- "agreement report"
- "AC1 report"
- "how accurate is this score against feedback?"
- "which scores have bad feedback alignment?"

## Inputs

Required:
- `scorecard`

Optional:
- `score` for a single score
- `days`, or `start_date` plus `end_date`
- `order_scores` for scorecard-wide ranking
- `memory_analysis` for optional LLM topic clustering; default false in Console

## Tactus Run

```tactus
local h = plexus.report.run({
  block_class = "FeedbackAlignment",
  block_config = {
    scorecard = "<resolved-scorecard-id>",
    score = "<optional-resolved-score-id>",
    days = 30,
    order_scores = "best_to_worst",
    memory_analysis = false,
  },
  cache_key = "feedback-alignment:<scorecard-or-score>:30d",
  ttl_hours = 24,
  async = true,
  budget = { usd = 1.0, wallclock_seconds = 600, depth = 1, tool_calls = 3 },
})
return { handle_id = h["id"], task_id = h["dispatch_result"] and h["dispatch_result"]["task_id"] }
```

## Interpretation

The report emphasizes alignment/AC1 and mismatch examples. Low alignment means
predictions and accepted feedback disagree often; inspect examples before
assuming the score is wrong because feedback quality may also be poor.
