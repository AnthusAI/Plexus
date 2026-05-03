# Optimizer Cookbook: Normal Hypotheses

Use this cookbook for the three main-line hypothesis slots:
`recent_incremental`, `recent_bold`, and `regression_fix`.

These lanes should stay focused on rubric alignment, feedback evidence, and
conservative prompt clarity. They should not use experimental prompt
transformations.

## Scan First

Before proposing a normal hypothesis, inspect the score YAML, feedback RCA,
accuracy RCA, and rubric-memory briefing for these policy-level signals.

### Missing Policy

Use when the RCA shows a recurring reviewer rule that the prompt does not state.

- Add one explicit rule for the disputed pattern.
- Name the exact confusion direction it targets.
- Prefer general policy language over examples.
- Do not change unrelated score behavior.

### Ambiguous Criterion

Use when the prompt contains a rule but does not define what counts.

- Replace vague words with operational criteria.
- Clarify boundary cases using reviewer language from feedback.
- State what should not count if the false-positive pattern is dominant.
- State what should count if the false-negative pattern is dominant.

### Feedback-Direction Targeting

Each hypothesis should usually target one confusion direction:

- `Predicted: Yes / Actual: No`: tighten the rule, require stronger evidence,
  or add exclusions.
- `Predicted: No / Actual: Yes`: broaden acceptable evidence, credit equivalent
  phrasing, or make implicit acceptable patterns explicit.
- Mixed errors: choose the larger or more costly segment unless the slot
  objective explicitly asks for a synthesis.

### Guidelines -> Prompt Alignment

If the official guidelines and prompt disagree, update the prompt to match the
guidelines. Do not edit guidelines during optimizer runs.

- Preserve the existing class set.
- Keep the classifier's output shape unchanged.
- Keep the scoring question recognizable to reviewers.
- Use the rubric's own words when practical.

## Category A: Incremental Prompt Fix

Use for a small targeted change aimed at the top RCA issue.

Good candidates:

- Add a missing rule.
- Sharpen an existing rule.
- Add a short exclusion list for a false-positive pattern.
- Add a short inclusion list for a false-negative pattern.
- Move a key rule closer to the decision instruction when it is already present
  but easy to miss.

Few-shot examples are a last resort. Use them only for recurring
speech-to-text or phonetic transcription patterns where policy language alone is
unlikely to help. Limit to one or two examples.

## Category B: Bold Prompt Fix

Use when the RCA points to several related policy failures.

Good candidates:

- Rewrite a confusing prompt section into a step-by-step decision policy.
- Replace scattered edge cases with one ordered decision framework.
- Merge duplicated rules that conflict with each other.
- Add a compact "credit / do not credit" boundary table.
- Reorder existing sections so the classifier sees eligibility, exclusions, and
  final decision criteria in a stable sequence.

## Conservative Prompt Presentation

These tactics are allowed in normal lanes only when they directly support a
rubric or feedback-policy fix:

- Put the decisive rule immediately before the final decision instruction.
- Restate a single key boundary once when the RCA shows the model skipped it.
- Use shorter headings and bullets to reduce prompt ambiguity.
- Remove obsolete or contradictory prompt text.

Do not spend a normal slot on mechanics alone. If the hypothesis is mostly about
prompt shape rather than rubric alignment, use the structural lane.

## What To Avoid

- Do not modify guidelines.
- Do not change parser or framework code.
- Do not add examples for generic classification edge cases.
- Do not try label-order experiments in normal lanes.
- Do not propose a broad rewrite unless the slot is `recent_bold` and the RCA
  supports it.
