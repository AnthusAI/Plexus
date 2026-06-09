---
id: evaluation-feedback.batch-operations-cookbook
title: Batch Operations Cookbook
summary: Common workflow patterns for scorecard-wide feedback analysis and optimization.
namespace: evaluation-feedback
status: canonical
disclosure: cookbook
audience: agent
tags: [batch, cookbook, workflows, optimizer, feedback]
related:
  - evaluation-feedback.batch-feedback-alignment
  - evaluation-feedback.batch-optimizer-dispatch
  - evaluation-feedback.optimizer-procedures
---

# Batch Operations Cookbook

Common patterns for scorecard-wide feedback analysis and optimization workflows.

---

## Pattern 1: Find and Optimize All Low-Accuracy Scores

The canonical workflow. Identify underperforming scores and dispatch optimizers
in two API calls.

```lua
-- Step 1: Get all scores below 90% accuracy
local alignment = plexus.feedback.alignment_batch({
  scorecard = "My Scorecard",
  days = 90,
  accuracy_threshold = 90,
})

-- Step 2: Collect valid score names
local scores = {}
for _, s in ipairs(alignment.scores) do
  if not s.error then
    table.insert(scores, s.score_name)
  end
end

-- Step 3: Dispatch optimizers
local dispatch = plexus.procedure.optimize_batch({
  scorecard = "My Scorecard",
  scores = scores,
  max_iterations = 3,
  days = 90,
})

return {
  found = #scores,
  dispatched = #dispatch.dispatched,
  failed = #dispatch.failed,
  procedures = dispatch.dispatched,
}
```

---

## Pattern 2: Prioritized Optimization (Worst First)

When you can't optimize all scores at once, start with the lowest performers.

```lua
-- Get all scores
local alignment = plexus.feedback.alignment_batch({
  scorecard = "My Scorecard",
  days = 90,
})

-- Filter out errors and sort ascending by accuracy (worst first)
local valid = {}
for _, s in ipairs(alignment.scores) do
  if not s.error and s.accuracy then
    table.insert(valid, s)
  end
end
table.sort(valid, function(a, b)
  return a.accuracy < b.accuracy
end)

-- Take the bottom 5
local worst_5 = {}
for i = 1, math.min(5, #valid) do
  table.insert(worst_5, valid[i].score_name)
end

-- Optimize with a more generous iteration budget for chronic underperformers
local dispatch = plexus.procedure.optimize_batch({
  scorecard = "My Scorecard",
  scores = worst_5,
  max_iterations = 10,
  days = 180,
})

return dispatch
```

---

## Pattern 3: Dry-Run Before Committing

Validate the optimizer can make progress before running a full batch.

```lua
-- Phase 1: Dry run on a sample (first 3 low-accuracy scores)
local alignment = plexus.feedback.alignment_batch({
  scorecard = "My Scorecard",
  days = 90,
  accuracy_threshold = 85,
})

local sample = {}
for i, s in ipairs(alignment.scores) do
  if i <= 3 and not s.error then
    table.insert(sample, s.score_name)
  end
end

local dry = plexus.procedure.optimize_batch({
  scorecard = "My Scorecard",
  scores = sample,
  max_iterations = 2,
  days = 90,
  dry_run = true,  -- analyze and propose but never promote
})

-- Review procedure results in dashboard, then run full batch with dry_run = false
return {
  dry_run_procedures = dry.dispatched,
  next_step = "Review dashboard results, then re-run with dry_run = false",
}
```

---

## Pattern 4: Scores That Regressed Recently

Catch regressions by comparing a short recent window against a longer baseline.

```lua
-- Get alignment over the last 30 days only
local recent = plexus.feedback.alignment_batch({
  scorecard = "My Scorecard",
  days = 30,
})

-- Find scores that have dropped below 80% recently
local regressed = {}
for _, s in ipairs(recent.scores) do
  if not s.error and s.accuracy and s.accuracy < 80 then
    table.insert(regressed, s.score_name)
  end
end

if #regressed == 0 then
  return { message = "No recent regressions detected." }
end

-- Re-optimize with longer lookback and regression-focused hint
local dispatch = plexus.procedure.optimize_batch({
  scorecard = "My Scorecard",
  scores = regressed,
  max_iterations = 5,
  days = 180,
  hint = "Focus on recent regression causes. Check for norm shifts or new edge case patterns introduced in the last 30 days.",
})

return dispatch
```

---

## Pattern 5: Cross-Run Learning

Inject learnings from a prior optimizer run into the next batch.

```lua
-- After reviewing a prior run's lab report, extract its prescription:
local prescription = "From prior run: broad STT rescue always regresses. Focus only on narrow transcript-anchored evidence rules."

local dispatch = plexus.procedure.optimize_batch({
  scorecard = "My Scorecard",
  scores = {"Score A", "Score B", "Score C"},
  max_iterations = 5,
  days = 90,
  prior_run_prescription = prescription,
})

return dispatch
```

---

## Pattern 6: Monitor a Running Batch

Poll procedure statuses and summarize completion.

```lua
-- Assume proc_ids is a list of procedure IDs from a prior optimize_batch call
local proc_ids = { "uuid-1", "uuid-2", "uuid-3" }

local status = plexus.procedure.status_batch({
  procedure_ids = proc_ids,
})

local summary = { completed = {}, running = {}, failed = {} }
for _, p in ipairs(status.procedures) do
  if p.error then
    table.insert(summary.failed, { id = p.procedure_id, reason = p.error })
  elseif p.status == "COMPLETED" then
    table.insert(summary.completed, p.id)
  elseif p.status == "FAILED" or p.status == "STALLED" then
    table.insert(summary.failed, { id = p.id, reason = p.status })
  else
    table.insert(summary.running, p.id)
  end
end

return summary
```

---

## Error Handling Patterns

Always check `dispatch.failed` before assuming all scores were dispatched:

```lua
local dispatch = plexus.procedure.optimize_batch({
  scorecard = "My Scorecard",
  scores = {"Score A", "Typo Score Naem", "Score B"},
  max_iterations = 3,
})

if #dispatch.failed > 0 then
  for _, fail in ipairs(dispatch.failed) do
    print("FAILED:", fail.score, "-", fail.error)
  end
end

-- Proceed only with successful dispatches
if #dispatch.dispatched > 0 then
  return dispatch.dispatched
end
```

Similarly, check `score_data.error` when iterating alignment results:

```lua
local alignment = plexus.feedback.alignment_batch({
  scorecard = "My Scorecard",
  days = 90,
})

for _, s in ipairs(alignment.scores) do
  if s.error then
    print("No data for:", s.score_name, "-", s.error)
  else
    print(s.score_name, string.format("%.1f%%", s.accuracy))
  end
end
```
