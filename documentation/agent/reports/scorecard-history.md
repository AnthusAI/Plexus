---
id: reports.scorecard-history
title: Scorecard History Report
summary: "Reference for ScorecardHistory parameters, selection rules, summary behavior, evaluation gauges, and output shape."
namespace: reports
status: canonical
disclosure: reference
audience: agent
tags: [reports, scorecard-history, score-versions, champion]
related:
  - reports._index
---
# Scorecard History Report

`ScorecardHistory` summarizes starred (`isFeatured == "true"`) score-version changes in a date window for either:
- a whole scorecard (all changed scores), or
- one score on that scorecard.

It is designed for stakeholder-ready change reporting, with expandable guidelines/code diffs and optional evaluation gauge context.

## Parameters

Required:
- `scorecard`: scorecard identifier (name, id, external id, or key as resolved by the standard scorecard resolver)

Optional score scope:
- `score`: score identifier on the given scorecard
- `score_id`: alias for `score`

Date window (choose one mode):
- `days` (positive integer), or
- `start_date` + `end_date` (both required together)

Validation rules:
- `days` cannot be combined with `start_date`/`end_date`
- `end_date` must be after `start_date`
- `days` defaults to `30`

## Scope and Selection Rules

- Scorecard-wide mode analyzes all scores on the scorecard and returns only scores that have included versions.
- Single-score mode analyzes only the resolved score on that scorecard.
- Included versions are those where:
  - `isFeatured` is true, and
  - `ScoreVersion.createdAt` is inside the requested window.
- Scores with no included versions are omitted.

For each included version:
- Parent version is resolved via `parentVersionId` when present (fallback fetch by ID when needed).
- Per-version `guidelines` and `configuration` diff payloads are included.
- Champion awareness includes:
  - `is_current_champion` (matches current score championVersionId), and
  - in-window promotions from `metadata.championHistory[].enteredAt`.

For each included score:
- A full-window diff is built from:
  - baseline = latest same-score version before first in-window included version,
  - latest = latest in-window included version.

## Evaluation Gauges and Baselines

Performance payload is attached per changed score (when data exists):
- `current_version_id`: latest in-window included version
- `baseline_version_id`: predecessor described above
- `recent_feedback`: selected `Evaluation.type == "feedback"`
- `regression`: selected `Evaluation.type == "accuracy"` with usable dataset ID

Selection rules:
- only `COMPLETED` evaluations are eligible
- choose best by highest Alignment/AC1, tie-break by newest `createdAt`
- regression baseline is included only if baseline evaluation uses the same dataset ID as current regression evaluation

Metrics payload includes available values for:
- `alignment`, `accuracy`, `precision`, `recall`

Plus metadata:
- `evaluation_id`, `evaluation_type`, `created_at`, `updated_at`,
- `processed_items`, `total_items`,
- `dataset_id` (regression only when present).

Missing metric values are omitted (no synthetic defaults).

## Summary Behavior

Top-level summary is LLM-generated from chronological version context and bounded diffs.

Expected behavior:
- output is categorized stakeholder-oriented bullet sections
- champion coverage is explicitly reported as one of `all`, `some`, `none`
- score-level summaries include version-note driven change notes and intervention counts
- if LLM summary generation/parsing fails, report output contains an `error` state (no fallback summary synthesis path)

## Output Contract (High Level)

Top-level fields:
- `report_type`, `block_title`, `block_description`
- `scope` (`scorecard_all_scores` or `single_score`)
- `scorecard_id`, `scorecard_name`, optional `score_id`, `score_name`
- `date_range` (`start`, `end`)
- `summary`:
  - `text`
  - `champion_coverage` (`all|some|none`)
  - `featured_version_count`
  - `champion_version_count`
  - `scores_changed_count`
- `scores`: array of changed-score payloads

Per-score payload includes:
- identifiers and counts
- `summary`
- `versions` with champion status + per-version guidelines/code diffs
- optional `window_diff` (baseline-to-latest)
- optional `performance` (recent feedback/regression current + baseline)
- optional SME question context extracted from related procedures

## Direct Usage

CLI:
```bash
# Scorecard-wide
plexus feedback report scorecard-history \
  --scorecard "Customer Service QA" \
  --days 10

# Single-score
plexus feedback report scorecard-history \
  --scorecard "Customer Service QA" \
  --score "Medication Review: Dosage" \
  --days 10

# Explicit date range
plexus feedback report scorecard-history \
  --scorecard "Customer Service QA" \
  --start-date 2026-03-01 \
  --end-date 2026-03-31
```

Tactus:
```tactus
return plexus.report.scorecard_history{
  scorecard = "Customer Service QA",
  days = 10,
  sync = true
}
```
