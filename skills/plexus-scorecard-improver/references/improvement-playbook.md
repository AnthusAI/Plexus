# Feedback-Driven Alignment Playbook

## Data Sufficiency Discussion Prompts

Use these prompts after the initial `plexus_feedback_analysis` scan:
- How many feedback items are available in the selected window?
- Are comments detailed enough to support policy and coding decisions?
- Is there enough class coverage to trust metric movement?
- If sample size is low, do we still have enough high-quality examples to proceed cautiously?

Decision rule:
- No hard minimum threshold.
- Proceed only with explicit user agreement (soft gate).

## Contradiction Triage Outcomes

After the Feedback Contradictions report, classify each finding into one outcome:
- `invalidate_feedback_item`: feedback label/edit is not reliable and should be excluded.
- `guideline_update_needed`: current policy is incomplete or ambiguous and must be updated.
- `code_behavior_gap`: guideline is clear, feedback is valid, and score code must be changed.
- `needs_sme_decision`: unresolved policy conflict; hold iteration until clarified.

Do not start score-code iteration until contradiction/guideline cleanup is complete and user sign-off is explicit.

## Fixed-Baseline Iteration Log Format

Use one log entry per iteration in Kanbus comments and working notes:

```text
Iteration: <n>
Scorecard: <scorecard_id>
Score: <score_id>
Days: <days>
Baseline Evaluation ID: <baseline_eval_id>
Candidate Score Version ID: <score_version_id>
Hypothesis: <one-sentence expected improvement>
Change Summary: <what changed in score code>
Evaluation ID: <new_eval_id>
Comparison Baseline Used: <baseline_eval_id>
Metrics: <accuracy/precision/recall/ac1 with deltas vs baseline>
RCA Highlights: <key root-cause topics>
Decision: <keep|revise|revert>
Next Step: <single concrete next action>
```

Non-negotiable:
- Run feedback evaluations synchronously.
- Wait for final output (including RCA) before deciding.
- Keep the original baseline ID fixed across all comparisons.
