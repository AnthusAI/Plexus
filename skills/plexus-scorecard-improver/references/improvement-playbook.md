# Improvement Playbook

## Fast Triage

- False positives dominate: tighten inclusion rules and add explicit exclusions.
- False negatives dominate: broaden qualifying signals and relax over-strict constraints.
- Both are high: likely taxonomy ambiguity or prompt objective conflict; fix definitions first.

## High-Value Data to Gather

- Top 10 representative false positives.
- Top 10 representative false negatives.
- Class distribution and confidence spread (if available).
- Most recent score version and what changed since prior stable version.

## Iteration Rules

- Prefer one hypothesis per iteration.
- Keep a short experiment log: hypothesis, change, metric result, decision.
- Stop after regression and reassess root cause before further edits.

## Exit Criteria

- Primary metric trend is positive across at least one fresh evaluation run.
- No severe regression in critical classes.
- Next risks are clearly documented.
