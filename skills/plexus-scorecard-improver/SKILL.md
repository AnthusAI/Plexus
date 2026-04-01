---
name: plexus-scorecard-improver
description: Improve Plexus scorecard performance through iterative, evidence-driven changes based on evaluation metrics and feedback analysis. Use when a user asks to raise accuracy, reduce false positives/false negatives, tune prompts or guidelines, or recover score quality after regressions.
---

# Plexus Scorecard Improver

Use this skill to run a repeatable score-improvement loop for an existing Plexus score.

## Improvement Loop

1. Establish baseline.
2. Diagnose error patterns.
3. Propose the smallest high-impact change.
4. Validate with evaluation.
5. Decide to keep, revise, or revert.
6. Summarize impact and next action.

## Step 1: Establish Baseline

Collect the exact scorecard and score being tuned, then capture:
- Current version/config reference.
- Latest evaluation metrics (accuracy, precision/recall, AC1 if available).
- Known pain pattern from the user (for example: too many false positives on disclosures).

If the target metric is unclear, define one primary objective before changing anything.

## Step 2: Diagnose with Evidence

Use feedback/evaluation analysis to separate symptoms from causes:
- Identify top false-positive and false-negative clusters.
- Pull concrete examples, not just aggregate percentages.
- Distinguish guideline ambiguity from prompt/config failure.

Favor the dominant error cluster first. Do not optimize multiple unrelated failure modes in one pass.

## Step 3: Choose the Right Executor

Use specialized agents based on change type:
- Guidelines/content criteria edits: `plexus-score-guidelines-updater`.
- YAML score configuration and scoring logic edits: `plexus-score-config-updater`.
- Pattern diagnosis and confusion analysis: `plexus-alignment-analyzer`.

If a request touches YAML config, delegate that work to `plexus-score-config-updater` instead of editing directly.

## Step 4: Implement Minimal Change

Apply one focused change per iteration:
- Tighten a specific boundary condition.
- Add or revise one decision rule.
- Clarify one ambiguous guideline phrase.

Avoid broad rewrites unless the baseline indicates systemic failure.

## Step 5: Validate

Run a new evaluation after each change and compare against baseline:
- Confirm primary objective improved.
- Check for collateral regressions in other major classes.
- Keep notes on what changed and why.

If results are mixed, prefer rollback and a narrower follow-up change over stacking unverified edits.

## Step 6: Report and Handoff

Return a concise change summary:
- Baseline metric vs. latest metric.
- What changed (guidelines/config/prompt behavior).
- Which error pattern improved.
- Remaining risk and recommended next iteration.

## Guardrails

- Do not declare success without metric comparison against baseline.
- Do not bundle unrelated fixes into one experiment.
- Do not hide uncertainty; call out low sample size or noisy data.
- Keep each loop auditable and reversible.

## Optional Reference

For quick triage patterns and decision rules, use [references/improvement-playbook.md](references/improvement-playbook.md).
