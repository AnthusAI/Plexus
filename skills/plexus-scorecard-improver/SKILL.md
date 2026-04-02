---
name: plexus-scorecard-improver
description: Improve alignment for a single Plexus score using feedback edits as ground-truth labels. Use when a user wants iterative score-code improvements driven by feedback evaluations, contradictions cleanup, and fixed-baseline comparisons.
---

# Plexus Scorecard Improver

Use this skill for feedback-driven alignment improvement of one score at a time.

## Input Contract

Required:
- `scorecard`
- `score`

Optional:
- `days` (default: `90`)

If `days` is omitted, explicitly use `90`.

## Phase Workflow

1. Select target
- Confirm `scorecard` and `score`.
- Confirm `days` window (default `90`).

2. Dataset sufficiency scan
- Run `plexus_feedback_analysis` for the selected scorecard/score/window.
- Treat this as a data sufficiency and coverage scan, not an optimization signal.
- Summarize item count, agreement patterns, and comment richness.

3. Soft data gate (required discussion)
- Discuss with the user whether data is sufficient to proceed.
- No hard minimum item count.
- If sample size is small but comments are high quality, explicitly allow proceeding with caution.
- Do not advance without explicit user agreement.

4. Contradictions analysis
- Run `plexus_report_run` using the parameterized Feedback Contradictions configuration for the same scorecard/score/window.
- Review outcomes with user/SMEs:
  - possible invalid feedback items,
  - policy conflicts,
  - candidate new policies.

5. Contradictions exit gate
- Resolve contradiction/policy gaps before code iteration.
- Route guideline work through `plexus-guidelines` workflow/tooling.
- Require explicit user sign-off that contradictions/guidelines are ready before code iteration starts.

6. Baseline feedback evaluation
- Run `plexus_evaluation_run` with `evaluation_type="feedback"` for current score version.
- Execute synchronously and wait for final output.
- Capture and persist the baseline evaluation ID.

7. Iterative score-code loop
- Make one focused score-code change (new ScoreVersion).
- Record intent in Kanbus comments and ScoreVersion update message.
- Run feedback evaluation synchronously for the new version.
- Always set comparison baseline to the original baseline evaluation ID from phase 6.
- Review metric deltas and root-cause analysis output.
- Repeat until stop criteria are reached.

## Execution Rules

- Feedback evaluations must run in synchronous/wait mode.
- Do not run feedback evaluations in background async mode and poll later.
- Always wait for final output, including root-cause analysis.
- Keep baseline fixed to the original baseline evaluation ID for all post-baseline comparisons.
- Do not promote a new champion unless explicitly authorized by the user.

## Handoff Boundaries

- Guidelines changes: use `plexus-guidelines` workflow/tooling.
- Score code/config changes: use the score config/code updater workflow.

## Iteration Log Requirements

For each iteration, log:
- score version ID,
- hypothesis,
- concrete change,
- evaluation ID,
- baseline ID used,
- key metric deltas,
- keep/revise/revert decision.

## Optional Reference

Use [references/improvement-playbook.md](references/improvement-playbook.md) for discussion prompts, contradiction triage outcomes, and fixed-baseline logging format.
