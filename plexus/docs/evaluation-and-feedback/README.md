# Evaluation & Feedback

Topic index for measuring score behavior, comparing predictions to human
judgments, and iterating with the feedback alignment optimizer.

## Files

- `feedback-alignment`: How to test scores against human feedback
  (false-positive / false-negative workflows, baseline-first protocol,
  conventions used by every alignment tool).
- `evaluation-alignment`: How to align a score against a labeled dataset
  using local YAML — distinct from feedback alignment.
- `optimizer-cookbook-normal`: Main-line optimizer change patterns for
  rubric alignment, feedback-direction targeting, policy fixes, and
  conservative prompt clarity.
- `optimizer-cookbook-structural`: Structural optimizer ideas for model
  swaps, input sources, preprocessing, decomposition, extractor nodes, N/A
  gates, and late prompt-shape experiments.
- `optimizer-cookbook-creative`: Cycle-4+ experimental prompt
  transformations for the dedicated creative hypothesis lane.
- `optimizer-cookbook`: Legacy overview for optimizer change patterns.
- `optimizer-procedures`: End-to-end reference for the Feedback Alignment
  Optimizer procedure — how to trigger, monitor, interpret, continue and
  branch, and act on findings.
- `optimizer-objective-alignment`: Default alignment objective (maximize
  AC1-style agreement).
- `optimizer-objective-precision`: Precision / `precision_safe` objective
  guidance (reduce false positives).
- `optimizer-objective-recall`: Recall / `recall_safe` objective guidance
  (reduce false negatives).
- `optimizer-objective-cost`: Cost-efficiency objective guidance
  (maximize agreement per dollar).

## When to use each

- Improving a score against human feedback -> `feedback-alignment`,
  then `optimizer-procedures` to iterate, then the lane-specific
  `optimizer-cookbook-*` file for concrete change patterns.
- Comparing a score to a labeled dataset -> `evaluation-alignment`.
- Choosing the right optimization target -> the matching
  `optimizer-objective-*` file.
- Sanity-checking that a ScoreVersion's code matches its rubric before an
  evaluation or promotion -> see `score-and-dataset-authoring/score-rubric-consistency`.

## Score rubric consistency check

Pass `score_rubric_consistency_check = true` to `plexus.evaluation.run` for a feedback
evaluation to have a lightweight rubric/code consistency check run automatically before
predictions start. The result is persisted in `Evaluation.parameters.score_rubric_consistency_check`.

```lua
return plexus.evaluation.run({
  evaluation_type              = "feedback",
  scorecard                    = "My Scorecard",
  score                        = "My Score",
  score_rubric_consistency_check = true,
})
```

See `score-and-dataset-authoring/score-rubric-consistency` for standalone usage, promotion
gating patterns, and CLI equivalents.

## Reading from `execute_tactus`

```tactus
local guide = plexus.docs.get{ key = "feedback-alignment" }
```

Legacy flat keys (`feedback-alignment`, `evaluation-alignment`,
`optimizer-cookbook`, `optimizer-cookbook-normal`,
`optimizer-cookbook-structural`, `optimizer-cookbook-creative`, `optimizer-procedures`,
`optimizer-objective-alignment`, `optimizer-objective-precision`,
`optimizer-objective-recall`, `optimizer-objective-cost`) keep resolving
for backward compatibility with `get_plexus_documentation`. The nested
form `evaluation-and-feedback/feedback-alignment` works too.
