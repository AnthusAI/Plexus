---
id: evaluation-feedback.batch-optimizer-dispatch
title: Batch Optimizer Dispatch
summary: Start optimizer procedures for multiple scores in one API call.
namespace: evaluation-feedback
status: canonical
disclosure: reference
audience: agent
tags: [optimizer, batch, procedures]
related:
  - evaluation-feedback.optimizer-procedures
  - evaluation-feedback.batch-feedback-alignment
  - evaluation-feedback.batch-operations-cookbook
---

# Batch Optimizer Dispatch

Use `plexus.procedure.optimize_batch` to start feedback alignment optimizer
procedures for multiple scores in a single API call.

Use `plexus.procedure.status_batch` to check the status of multiple procedures
at once.

## When to Use

- **Batch remediation**: Fix multiple low-performing scores at once (max 5 per batch)
- **Scheduled automation**: Run optimizers on a regular cadence for a score set

## Resource Constraints

**IMPORTANT**: `plexus.procedure.optimize_batch` is limited to **5 scores maximum** per call
to prevent resource exhaustion. Each optimizer procedure consumes 1-2GB RAM during
LLM-intensive phases (hypothesis generation, evaluation analysis). Dispatching more than
5 concurrent optimizers can overwhelm shared infrastructure.

For larger batches, dispatch in sequential groups:
```lua
-- Process 15 scores in 3 batches of 5
local all_scores = {...}  -- 15 scores
for i = 1, #all_scores, 5 do
  local batch = {}
  for j = i, math.min(i + 4, #all_scores) do
    table.insert(batch, all_scores[j])
  end
  plexus.procedure.optimize_batch({
    scorecard = "My Scorecard",
    scores = batch,
    max_iterations = 3,
  })
  -- Wait for batch to complete before dispatching next
end
```

## Tactus API — Dispatch

```lua
local result = plexus.procedure.optimize_batch({
  scorecard = "My Scorecard",
  scores = {"Acknowledgement AI", "Assumptive Reschedule AI", "Not Interested"},
  max_iterations = 3,
  days = 90,
  dry_run = false,
})

for _, proc in ipairs(result.dispatched) do
  print("Started:", proc.score, proc.procedure_id)
end
```

## Parameters

All parameters from `plexus.procedure.optimize` are supported, plus:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scorecard` | string | yes | Scorecard name, key, or ID |
| `scores` | array[string] | yes | Array of score names, keys, or IDs (max 5) |
| `max_iterations` | int | no (default 3) | Maximum optimization cycles per score |
| `days` | int | no (default 90) | Feedback lookback window per score |
| `dry_run` | bool | no (default false) | If true, analyze but never promote champion |
| `hint` | string | no | Expert guidance injected into planning context for all runs |
| `prior_run_prescription` | string | no | Learnings from a prior run, injected into all runs |

## Return Shape — Dispatch

```lua
{
  scorecard = "My Scorecard",
  total_scores = 3,
  dispatched = {
    {
      score = "Acknowledgement AI",
      procedure_id = "uuid-1",
      status = "dispatched",
      dashboard_url = "https://lab.callcriteria.com/lab/procedures/uuid-1",
    },
    ...
  },
  failed = {
    {
      score = "Invalid Score Name",
      error = "score not found in scorecard",
    }
  }
}
```

## Tactus API — Status Check

```lua
local proc_ids = {}
for _, proc in ipairs(dispatch.dispatched) do
  table.insert(proc_ids, proc.procedure_id)
end

local status = plexus.procedure.status_batch({
  procedure_ids = proc_ids,
})

for _, proc in ipairs(status.procedures) do
  print(proc.id, proc.status)
end
```

## Return Shape — Status

```lua
{
  total = 3,
  procedures = {
    {
      id = "uuid-1",
      name = "Optimizer: ...",
      status = "COMPLETED",   -- RUNNING, COMPLETED, FAILED, STALLED
      scorecard_id = "uuid",
      score_id = "uuid",
      created_at = "...",
      updated_at = "...",
    },
    {
      procedure_id = "uuid-bad",
      error = "procedure not found",
    },
    ...
  }
}
```

## Cost & Resource Considerations

Each optimizer procedure consumes:
- **LLM tokens**: 10k–100k+ per run (depending on `context_window` and `max_iterations`)
- **RAM**: 1-2GB during LLM-intensive phases
- **CPU**: Moderate during evaluation, high during hypothesis generation

Before batch dispatch:

1. **Start with `dry_run = true`** on a sample to estimate quality and costs
2. **Use `max_iterations = 2`** for a first pass; continue with more cycles if promising
3. **Respect the 5-score limit** — the API will reject larger batches
4. **For scorecard-wide optimization** (10+ scores), process in sequential batches of 5 and wait for completion between batches

## Example: Complete Batch Workflow

```lua
-- Step 1: Find low-accuracy scores
local alignment = plexus.feedback.alignment_batch({
  scorecard = "My Scorecard",
  days = 90,
  accuracy_threshold = 85,
})

-- Step 2: Extract valid score names (skip errors)
local to_optimize = {}
for _, s in ipairs(alignment.scores) do
  if not s.error then
    table.insert(to_optimize, s.score_name)
  end
end

-- Step 3: Dispatch optimizers
local dispatch = plexus.procedure.optimize_batch({
  scorecard = "My Scorecard",
  scores = to_optimize,
  max_iterations = 3,
  days = 90,
})

-- Step 4: Collect IDs for monitoring
local proc_ids = {}
for _, p in ipairs(dispatch.dispatched) do
  table.insert(proc_ids, p.procedure_id)
end

-- Step 5: Check status (run this later, after procedures have had time to complete)
local status = plexus.procedure.status_batch({
  procedure_ids = proc_ids,
})

local completed, running, failed = 0, 0, 0
for _, p in ipairs(status.procedures) do
  if p.status == "COMPLETED" then completed = completed + 1
  elseif p.status == "FAILED" then failed = failed + 1
  else running = running + 1
  end
end

return {
  dispatched = #dispatch.dispatched,
  completed = completed,
  running = running,
  failed = failed,
}
```

See also: `evaluation-feedback.batch-operations-cookbook` for more workflow patterns.
