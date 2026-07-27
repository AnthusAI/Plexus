# Optimization Decision Toolchain

Use this reference when selecting optimization work across scorecards or when
turning an optimizer result into a stakeholder or promotion decision.

## Canonical sequence

1. Call `plexus.optimization.rank` for the complete requested scope.
2. Call `plexus.optimization.assess` with exact score IDs from that result.
3. Call `plexus.optimization.diagnose` for semantic rubric and feedback checks.
4. Present the exact ready target list and obtain approval.
5. Call `plexus.optimization.run` only for that approved list.
6. Let every legitimate evaluation and RCA stage finish.
7. Call `plexus.optimization.review` on terminal optimizer evidence.
8. Call `plexus.optimization.summary` for the user-facing portfolio update.

Do not replace these methods with a second ranking formula, cohort builder,
optimizer, or promotion path.

## Ranking

The first-pass rank is deterministic:

```text
reviewed_error_opportunity = valid_feedback_count * disagreement_rate
```

This is the number of reviewed disagreements. It measures the observed volume
of correctable work, not business importance. Report business importance as a
separate qualifier when it is known.

An exact portfolio ranking requires complete collection coverage. If any page
or downstream score read remains incomplete after its allowed retry, report a
partial result and do not describe ranks or counts as exact. A compact top-N
response may still be complete when it states the full `ranked_from_count` and
coverage evidence; compact output is not sampling.

## Assessment and diagnosis

Preserve the frozen UTC window, champion version, feedback watermark, policy
version, and evidence fingerprint from the decision packet.

Treat these axes independently:

- `feedback_collection`: whether broad collection should continue, become
  targeted, pause during repair or clarification, or reduce to monitoring.
- `guideline_health`: whether guidelines are present, syntactically valid, and
  consistent with score behavior.
- `feedback_rubric_health`: whether reviewed labels expose contradictions,
  policy gaps, or feedback-curation candidates.
- `optimization`: whether the score is ready, blocked, running, or complete.
- `promotion`: whether a tested candidate is ready for explicit approval.

Numeric policy gates are deterministic. Semantic diagnosis must reuse the
existing score/rubric consistency, rubric-memory, contradiction-report, and SME
question-gate capabilities. Do not infer that missing semantic evidence means
the score is safe to optimize.

## Launch approval

`plexus.optimization.run` is an execution-mode operation. It requires:

- `approved = true`;
- the exact approved targets, never more than five;
- complete ready assessments;
- unchanged champion versions and feedback watermarks;
- explicit sample, iteration, cost, and concurrency limits.

The method launches the existing feedback-alignment optimizer. It must not
recreate its balanced regression cohort or evaluation logic.

## Review and promotion

Treat `promotion_ready` as a request for human approval, not a promotion.
Require terminal matched recent evaluation, independent historical regression
evidence, class-specific metrics, no prediction-mode collapse, complete RCA and
artifacts, and a measurable safe improvement. Continue to use
`plexus.score.set_champion` only after explicit approval.

Never automatically invalidate feedback, promote a candidate, stop an
evaluation, or mutate feedback-collection settings.

## Persistence and reporting

Read methods default to `persist = false`. Use `persist = true` when the result
must be durable. Persistence uses the existing Task, Report, and S3-backed
ReportBlock path; persistence failure is a failed request, not permission to
silently return an unpersisted success.

Every summary must account for every selected score and include its outcome,
collection recommendation, blockers, stakeholder questions, approval request,
failures, and next action.
