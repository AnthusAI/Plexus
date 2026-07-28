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

### Ranking scope

Use account-wide ranking when no selector is supplied:

```lua
plexus.optimization.rank({})
```

To restrict the portfolio, supply exact opaque IDs, literal name prefixes, or
both. Prefix matching is case-insensitive and begins at the complete scorecard
name; it is not fuzzy matching or a regular expression.

```lua
plexus.optimization.rank({ scorecard_ids = { "opaque-scorecard-id" } })
plexus.optimization.rank({ scorecard_name_prefixes = { "Example Portfolio" } })
plexus.optimization.rank({
  scorecard_ids = { "opaque-scorecard-id" },
  scorecard_name_prefixes = { "Example Portfolio" },
})
```

Preserve IDs exactly. When both selectors are present, use their deduplicated
union. Reject an explicitly supplied empty selector instead of treating it as
account-wide. The ranker exhaustively paginates the canonical account-wide
collection, filters locally, and analyzes only the matched returned IDs.

Return requested, matched, and unmatched selectors; inspected and matched
counts; and collection and analysis coverage. A fully enumerated zero-match
scope is an exact empty result and does not invoke feedback analysis. A failed
page or downstream read remains incomplete after one retry: return partial
evidence, never an exact rank or count, and never include out-of-scope rows.

The CLI can deterministically re-rank already collected complete evidence:

```bash
plexus optimization rank --input @complete-rank-evidence.json \
  --option 'scorecard_ids=["opaque-scorecard-id"]'
```

This CLI form consumes the supplied evidence file; use the Tactus method above
when live exhaustive discovery and feedback analysis are required.

### Seven-day anti-churn policy

Every live rank applies fixed policy `score-activity-cooldown-v1`. The request
freezes one UTC `as_of` and excludes a score when the later of its record
`updatedAt` and newest version `createdAt` is at or after the rolling 168-hour
cutoff. This includes an unpromoted new version and a promotion or metadata edit
that updates the score record. Score results and evaluations do not start the
cooldown.

Excluded scores remain in `unranked` as `recent_score_activity` with activity
source/timestamp, newest opaque version ID/timestamp, cutoff, and eligibility
timestamp. Missing or malformed recency evidence fails closed and prevents an
exact ranking. Assessment preserves this evidence and returns
`cooldown_active` plus `wait_for_cooldown`. Launch rechecks the same live fields;
a new edit or version after assessment is rejected without optimizer dispatch.
Scores whose scalar champion ID does not resolve through the champion
relationship are structurally unranked as `unresolved_champion_reference`;
they cannot be optimized and do not make otherwise complete cooldown coverage
incomplete.

Offline CLI evidence must include complete activity coverage with the fixed
policy version and frozen `as_of`, plus complete per-score activity evidence.
Older evidence files without those fields can be inspected, but cannot claim an
exact ranking. The policy is not a caller option and cannot be disabled.

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
