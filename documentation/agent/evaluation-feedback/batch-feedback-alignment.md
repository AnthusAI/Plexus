---
id: evaluation-feedback.batch-feedback-alignment
title: Batch Feedback Alignment
summary: Get feedback alignment metrics for all scores in a scorecard with one API call.
namespace: evaluation-feedback
status: canonical
disclosure: reference
audience: agent
tags: [feedback, alignment, batch]
related:
  - evaluation-feedback.feedback-alignment
  - evaluation-feedback.batch-optimizer-dispatch
  - evaluation-feedback.batch-operations-cookbook
---

# Batch Feedback Alignment

Use `plexus.feedback.alignment_batch` when you need feedback alignment metrics
for multiple scores in a scorecard. This avoids making N separate
`plexus.feedback.alignment` calls — one per score — for scorecard-wide analysis.

## When to Use

- **Scorecard-wide analysis**: "Which scores are below 90% accuracy?"
- **Batch optimization prep**: Get alignment for all scores, then optimize low performers
- **Health dashboards**: Show all score alignment metrics at once

## Tactus API

```lua
local result = plexus.feedback.alignment_batch({
  scorecard = "My Scorecard",
  days = 90,
  accuracy_threshold = 90,  -- optional: only return scores below this %
})

for _, score_data in ipairs(result.scores) do
  print(score_data.score_name, score_data.accuracy, score_data.ac1)
end
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `scorecard` | string | yes | — | Scorecard name, key, or ID |
| `days` | int | no | 7 | Feedback lookback window in days |
| `accuracy_threshold` | float | no | none | Only return scores below this accuracy % |
| `include_scores` | array[string] | no | all | Only return metrics for these score names |
| `exclude_scores` | array[string] | no | none | Exclude these score names from results |

## Return Shape

```lua
{
  scorecard_id = "uuid",
  scorecard_name = "My Scorecard",
  days = 90,
  total_scores = 26,       -- total scores found in scorecard
  scores_analyzed = 13,    -- count after threshold/include/exclude filtering
  scores = {
    {
      score_id = "uuid",
      score_name = "Acknowledgement AI",
      accuracy = 81.25,
      ac1 = 0.7547,
      total_items = 16,
      confusion_matrix = { ... },
      precision = 58.33,
      recall = 55.56,
      warning = "Imbalanced classes",  -- nil if no warning
    },
    -- scores with no feedback data or errors:
    {
      score_id = "uuid",
      score_name = "Cancellation Reason",
      error = "no feedback data found",
    },
    ...
  }
}
```

## Comparison with Single-Score API

| Aspect | `feedback.alignment` | `feedback.alignment_batch` |
|--------|---------------------|---------------------------|
| API calls needed | N (one per score) | 1 |
| Score filtering | manual in Lua | built-in via `accuracy_threshold` |
| Error handling | raises exception | errors included per-score in results |
| Use case | Deep dive on one score | Scorecard-wide analysis |

## Example: Full Batch Optimization Workflow

```lua
-- Step 1: Find all scores under 90% accuracy
local alignment = plexus.feedback.alignment_batch({
  scorecard = "My Scorecard",
  days = 90,
  accuracy_threshold = 90,
})

-- Step 2: Extract score names
local low_accuracy_scores = {}
for _, score_data in ipairs(alignment.scores) do
  if not score_data.error then
    table.insert(low_accuracy_scores, score_data.score_name)
  end
end

-- Step 3: Batch dispatch optimizers
local dispatch = plexus.procedure.optimize_batch({
  scorecard = "My Scorecard",
  scores = low_accuracy_scores,
  max_iterations = 3,
  days = 90,
})

return {
  scores_found = #low_accuracy_scores,
  procedures_dispatched = #dispatch.dispatched,
  procedures_failed = #dispatch.failed,
}
```

See also: `evaluation-feedback.batch-operations-cookbook` for more workflow patterns.
