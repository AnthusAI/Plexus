---
id: evaluation-feedback.feedback-analysis-preflight-runbook
title: Feedback Analysis Preflight Runbook
summary: Fail-fast triage steps for contradictions and feedback evaluation prerequisites.
namespace: evaluation-feedback
status: active
disclosure: team
tags:
  - feedback
  - contradictions
  - evaluation
  - preflight
related:
  - evaluation-feedback.feedback-alignment
---

# Feedback Analysis Preflight Runbook

## What changed

Contradictions and `plexus evaluate feedback --version ...` now hard-fail before analysis when prerequisites are unresolved.

Common typed failures:

- `SCORECARD_NOT_FOUND` or `SCORE_NOT_FOUND`
- `SCORE_VERSION_UNRESOLVED` or `SCORE_VERSION_NOT_FOUND`
- `SCORE_VERSION_CONFIGURATION_MISSING`
- `SCORE_GUIDELINES_MISSING`

## Operator triage sequence

1. Run integrity diagnostics for orphaned feedback references:

```bash
plexus feedback report integrity --days 30
```

2. Reproduce contradictions with explicit scope:

```bash
plexus feedback report contradictions \
  --scorecard "<scorecard>" \
  --score "<score>" \
  --days 7 \
  --fresh
```

3. Reproduce feedback evaluation preflight:

```bash
plexus evaluate feedback \
  --scorecard "<scorecard>" \
  --score "<score>" \
  --version "<score_version_id>" \
  --days 30
```

## Interpretation and remediation

- Missing score references in feedback integrity output:
  - `orphaned_feedback_items > 0` means feedback exists for score IDs that no longer resolve.
  - Repair or remap score references before expecting contradictions/evaluation to run cleanly.
- Missing score-version configuration:
  - Republish or restore the referenced `ScoreVersion` so `configuration` is present.
- Missing guidelines payload:
  - Ensure `guidelines` or `configuration` text is populated for the selected score version.

## Retry

After remediation, rerun the same command with identical parameters. Runs should either pass preflight and proceed, or fail with a typed preflight diagnostic that identifies the remaining blocker.
