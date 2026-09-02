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

**IMPORTANT**: `plexus.procedure.optimize_batch` is limited to **5 scores maximum** per call.
Each optimizer consumes 1-2GB RAM during execution. For larger batches, process in sequential
groups of 5.

---

## Pattern 0: Complete Account-Wide Feedback Research

For a request covering every scorecard, enumerate the canonical collection completely before
analysis. Keep returned IDs in the same program, retry a failed page once, aggregate the bounded
batch result in Lua, and return coverage evidence instead of the raw batch payload.

```lua
local token, pages, scorecard_ids = nil, 0, {}
repeat
  local ok, page = pcall(function()
    return plexus.scorecards.list({ return_metadata = true, next_token = token })
  end)
  if ok and page == nil then ok = false end
  if not ok then
    ok, page = pcall(function()
      return plexus.scorecards.list({ return_metadata = true, next_token = token })
    end)
  end
  if ok and page == nil then ok = false end
  if not ok then
    return { complete = false, pages = pages, error = tostring(page) }
  end
  pages = pages + 1
  for _, record in ipairs(page.items or {}) do
    scorecard_ids[#scorecard_ids + 1] = record.id
  end
  token = page.nextToken
until not token

if #scorecard_ids == 0 then
  return {
    complete = true,
    pages = pages,
    discovered = 0,
    coverage = {
      target_count = 0,
      completed_count = 0,
      failed_count = 0,
      complete = true,
    },
  }
end

local analysis = plexus.feedback.alignment_batch({
  scorecards = scorecard_ids,
  days = 14,
})
local priorities, failures = {}, {}
local scorecards_with_feedback, scores_analyzed, feedback_items = 0, 0, 0
for _, scorecard_result in ipairs(analysis.scorecards or {}) do
  if scorecard_result.error then
    failures[#failures + 1] = {
      scorecard_name = scorecard_result.scorecard_name,
      error = string.sub(tostring(scorecard_result.error), 1, 240),
    }
  else
    local has_feedback = false
    for _, score_result in ipairs(scorecard_result.scores or {}) do
      scores_analyzed = scores_analyzed + 1
      local item_count = tonumber(score_result.total_items) or 0
      feedback_items = feedback_items + item_count
      if item_count > 0 then
        has_feedback = true
        priorities[#priorities + 1] = {
          scorecard_name = scorecard_result.scorecard_name,
          score_name = score_result.score_name,
          total_items = item_count,
          accuracy = score_result.accuracy,
          ac1 = score_result.ac1,
          warning = score_result.warning,
        }
      end
    end
    if has_feedback then scorecards_with_feedback = scorecards_with_feedback + 1 end
  end
end

table.sort(priorities, function(a, b)
  local a_accuracy = tonumber(a.accuracy) or 101
  local b_accuracy = tonumber(b.accuracy) or 101
  if a_accuracy == b_accuracy then return a.total_items > b.total_items end
  return a_accuracy < b_accuracy
end)
local highlights = {}
for index = 1, math.min(#priorities, 10) do
  highlights[index] = priorities[index]
end

return {
  complete = analysis.coverage.complete,
  pages = pages,
  discovered = #scorecard_ids,
  coverage = analysis.coverage,
  totals = {
    scorecards_with_feedback = scorecards_with_feedback,
    scores_analyzed = scores_analyzed,
    feedback_items = feedback_items,
  },
  ranked_from_count = #priorities,
  priorities = highlights,
  failures = failures,
}
```

---

## Pattern 1: Find and Optimize Low-Accuracy Scores (Small Batch)

Identify underperforming scores and dispatch optimizers (up to 5 at once).

```lua
-- Step 1: Get all scores below 90% accuracy
local alignment = plexus.feedback.alignment_batch({
  scorecard = "My Scorecard",
  days = 90,
  accuracy_threshold = 90,
})

-- Step 2: Collect valid score names (limit to 5 for batch constraints)
local scores = {}
for _, s in ipairs(alignment.scores) do
  if not s.error and #scores < 5 then
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

## Pattern 1b: Scorecard-Wide Optimization (Sequential Batches)

For scorecards with 10+ low-accuracy scores, process in batches of 5.

```lua
-- Step 1: Get all scores below threshold
local alignment = plexus.feedback.alignment_batch({
  scorecard = "My Scorecard",
  days = 90,
  accuracy_threshold = 85,
})

local all_scores = {}
for _, s in ipairs(alignment.scores) do
  if not s.error then
    table.insert(all_scores, s.score_name)
  end
end

-- Step 2: Process in batches of 5
local all_procedures = {}
for i = 1, #all_scores, 5 do
  local batch = {}
  for j = i, math.min(i + 4, #all_scores) do
    table.insert(batch, all_scores[j])
  end
  
  local dispatch = plexus.procedure.optimize_batch({
    scorecard = "My Scorecard",
    scores = batch,
    max_iterations = 3,
    days = 90,
  })
  
  for _, proc in ipairs(dispatch.dispatched) do
    table.insert(all_procedures, proc)
  end
  
  -- NOTE: In practice, wait for this batch to complete before dispatching next
  -- Check status with plexus.procedure.status_batch before continuing
end

return {
  total_scores = #all_scores,
  total_procedures = #all_procedures,
  procedures = all_procedures,
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
