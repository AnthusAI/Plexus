# Score Rubric Consistency Check

Before running a full evaluation, it is often worth asking: does this ScoreVersion's code actually
reflect its rubric? The `plexus.score.contradictions` API runs a lightweight LLM preflight that
compares the score code/prompt stored in a `ScoreVersion` against that same version's rubric text
and produces a short structured verdict.

## When to use this

- Before promoting a version to champion — catch mismatches before they affect real evaluations.
- After editing a score prompt to add or tighten a rule — verify the code now matches the rubric.
- During the optimizer loop — inject a preflight check as part of the promotion packet review.
- Debugging surprising evaluation results — rule out a rubric/code divergence as the cause.

## API: `plexus.score.contradictions`

```lua
local result = plexus.score.contradictions({
  scorecard = "My Scorecard",
  score     = "My Score",
  version   = "abc123-version-uuid",
})
return result
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `scorecard` | yes | Scorecard name, key, or UUID. |
| `score` | yes | Score name, key, or UUID. |
| `version` | yes | `ScoreVersion` UUID to inspect. |
| `item_id` | no | Item UUID; its transcript text is appended as spot-check context. Optional. |

### Return value

```json
{
  "status": "consistent",
  "paragraph": "The score code closely matches the rubric. All decision criteria appear covered.",
  "scorecard_identifier": "My Scorecard",
  "score_identifier": "My Score",
  "score_version_id": "abc123-version-uuid",
  "checked_at": "2026-04-28T12:00:00+00:00",
  "model": "gpt-5-mini",
  "diagnostics": {}
}
```

`status` is one of:

- **`consistent`** — Code and rubric appear well-aligned. No meaningful policy mismatches found.
- **`potential_conflict`** — One or more policy areas in the rubric are not (or are incorrectly)
  reflected in the code. Investigate before promoting.
- **`inconclusive`** — The check could not produce a reliable verdict (e.g., the rubric is empty
  or the LLM could not parse the code structure). Treat as a soft warning.

## Common pattern: preflight before promotion

```lua
-- 1. Find the candidate version you are about to promote.
local score = plexus.score.info({
  scorecard = "My Scorecard",
  score     = "My Score",
})
local candidate_version_id = score.championVersionId  -- or whichever version you are promoting

-- 2. Run the consistency check.
local check = plexus.score.contradictions({
  scorecard = "My Scorecard",
  score     = "My Score",
  version   = candidate_version_id,
})

-- 3. Gate the promotion.
if check.status == "potential_conflict" then
  -- Surface the finding; do not auto-promote.
  return {
    blocked  = true,
    reason   = "score_rubric_consistency_check",
    details  = check,
  }
end

-- 4. Promote if clean.
return plexus.score.set_champion({
  score_id   = score.id,
  version_id = candidate_version_id,
})
```

## Common pattern: include in a feedback evaluation

Pass `score_rubric_consistency_check = true` when dispatching a feedback evaluation to have the
check run automatically before predictions start. The result is stored in
`Evaluation.parameters.score_rubric_consistency_check`:

```lua
return plexus.evaluation.run({
  evaluation_type              = "feedback",
  scorecard                    = "My Scorecard",
  score                        = "My Score",
  score_rubric_consistency_check = true,
})
```

This is equivalent to passing `--score-rubric-consistency-check` to `plexus evaluate feedback` on
the CLI.

## Common pattern: spot-check with a real item

Supply `item_id` to include a transcript as example context. The check still examines the
ScoreVersion as a whole; the item is just extra evidence for the model.

```lua
-- Get a recent item to use as context.
local recent = plexus.item.last({})
local item_id = recent.items[1].id

return plexus.score.contradictions({
  scorecard = "My Scorecard",
  score     = "My Score",
  version   = "abc123-version-uuid",
  item_id   = item_id,
})
```

## How to find a ScoreVersion UUID

The champion version UUID is on the score info response:

```lua
local info = plexus.score.info({ scorecard = "My Scorecard", score = "My Score" })
return info.championVersionId
```

Recent evaluation results also carry the version ID in their parameters. You can also list recent
evaluations:

```lua
return plexus.evaluation.find_recent({
  scorecard = "My Scorecard",
  score     = "My Score",
})
```

## CLI equivalent

```bash
plexus score contradictions \
  --scorecard "My Scorecard" \
  --score "My Score" \
  --version abc123-version-uuid

# With an item for spot-check context:
plexus score contradictions \
  --scorecard "My Scorecard" \
  --score "My Score" \
  --version abc123-version-uuid \
  --item item-uuid

# JSON output:
plexus score contradictions ... --format json
```

## Notes

- The check is intentionally lightweight (low reasoning effort, ~2 s latency). It is not a
  substitute for a full evaluation run; it is a fast sanity-check gate.
- The LLM looks only for meaningful policy mismatches — not style, formatting, or architecture
  differences.
- Empty rubric (`guidelines`) fields always produce `inconclusive`. Fill in the rubric before
  expecting a useful result.
- The check is performed synchronously and returns immediately (no handle/poll loop required).
