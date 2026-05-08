---
id: reports.feedback-contradictions
title: Feedback Contradictions Report
summary: "Find reviewer feedback that appears to contradict score guidelines, or aligned examples for comparison."
namespace: reports
status: canonical
disclosure: reference
audience: agent
tags: [reports, feedback, contradictions, guidelines]
related:
  - reports.reports-catalog
  - reports.feedback-alignment
---
# Feedback Contradictions Report

Use Feedback Contradictions when the user wants to identify feedback that may
conflict with the rubric or champion guidelines.

## Likely User Wording

- "contradictions"
- "conflicting feedback"
- "bad feedback"
- "feedback that violates the rubric"
- "aligned examples" when `mode = "aligned"`

## Inputs

Required:
- `scorecard`
- `score`

Optional:
- `score_version_id` to use a version other than the champion as rubric authority
- `mode = "contradictions"` or `"aligned"`
- `max_feedback_items`, `num_topics`, `max_concurrent`
- `days`, or `start_date` plus `end_date`

## Tactus Run

```tactus
local h = plexus.report.run({
  block_class = "FeedbackContradictions",
  block_config = {
    scorecard = "<resolved-scorecard-id>",
    score = "<resolved-score-id>",
    days = 90,
    mode = "contradictions",
    max_feedback_items = 400,
    num_topics = 8,
    max_concurrent = 20,
    include_rubric_memory = false,
  },
  cache_key = "feedback-contradictions:<score>:90d",
  ttl_hours = 24,
  async = true,
  budget = { usd = 2.0, wallclock_seconds = 1200, depth = 1, tool_calls = 3 },
})
return { handle_id = h["id"], task_id = h["dispatch_result"] and h["dispatch_result"]["task_id"] }
```

## Interpretation

Contradictions are review candidates, not proof that the reviewer or rubric is
wrong. Use the report to prepare SME discussion topics and to identify feedback
policy ambiguity.
