# Feedback Cohorts

Keep the alignment target and regression guardrail distinct.

## Recent alignment target

- Use the requested recent feedback window to measure the behavior users are
  correcting now.
- Preserve and reuse the exact feedback-item cohort for champion/candidate
  comparisons.
- Do not broaden this target merely to improve its apparent class balance.

## Historical regression cohort

- Use the optimizer's regression-dataset builder as the single canonical
  cohort-selection path. Do not recreate its selection logic in an ad hoc
  script.
- Request a balanced associated dataset from the current score version.
- Resolve every reachable terminal output in the score graph, including
  earlier branches that end before the final node.
- When the recent window lacks a terminal class, extend historical lookback as
  far as necessary and select the most balanced cohort available.
- Freeze and reuse the exact dataset ID for champion/candidate comparisons.

An explicit local CSV or parquet input may transport an already materialized
cohort through the standard evaluator. It must not become a second cohort-
selection algorithm.

Before accepting the cohort, inspect its reported recent, available, and
selected counts for every terminal class. Confirm whether historical lookback
was extended and whether balanced coverage is complete. Reject a claimed
balanced cohort when a reachable class was omitted or the reported
distribution does not support that claim. Verify exact feedback-item set
equality, not merely equal row counts, before using a metric delta as promotion
evidence.

Never silently retry with an unbalanced dataset. If complete balance is not
possible, report the actual distribution and limitation, then decide explicitly
whether the best-available cohort is adequate as a regression guardrail.
