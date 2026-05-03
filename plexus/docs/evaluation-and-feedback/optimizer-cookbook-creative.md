# Optimizer Cookbook: Creative Hypotheses

Use this cookbook only for the `creative` slot from cycle 4 onward.

The creative slot is an extra experimental lane. It must not displace the
normal top-three rubric and feedback-policy hypotheses. Pick one weird,
testable prompt transformation, explain why it could affect alignment, and keep
the classifier shape unchanged.

## Creative Rules

- Change only `score_config.yaml`.
- Keep the same classifier and valid class set.
- Do not duplicate input transcript text.
- Repeat or transform operative prompt instructions only.
- Use held-out evaluations and keep only variants that win.
- Prefer one clearly attributable transformation per hypothesis.

## Recipes

### Repeat The Operative Prompt Instructions

Useful when the model appears to forget the decision rule in long calls.

- Repeat the operative prompt instructions 2x.
- Repeat the operative prompt instructions 3x.
- Put the repetitions in separate prompt locations, such as before the
  transcript and before the final answer instruction.
- Do not repeat the raw transcript.

### Translate Operative Instructions

Useful as a deliberately unusual attention and phrasing test.

- Translate the operative rubric or decision instructions to Polish.
- Keep labels, valid classes, parser instructions, and output requirements in
  English.
- Preserve the exact same scoring meaning.

### Transcript First, Instruction Last

Useful when long instructions appear to bury the actual text.

```text
{{text}}

Classify the text above.
Use only the allowed labels.
Return only the label.
```

### Unusual Label-Order Test

Useful only as a low-priority experiment for suspected label-order sensitivity.

- Reverse the order of label definitions.
- Move the expected negative class before the expected positive class.
- Keep labels and valid classes identical.
- Evaluate carefully for regressions.

### Alternating Reminder Pattern

Useful when a prompt has long sections and the model loses the central rule.

- Put a compact reminder before the evidence text.
- Put a second compact reminder after the evidence text.
- Keep each reminder short and identical in meaning.

### Boundary Stress Test

Useful when reviewers consistently disagree around one edge case.

- Temporarily make the edge-case rule extremely explicit and prominent.
- State both "credit" and "do not credit" forms.
- Keep all other policy text stable so the result is attributable.

## What Not To Do

- Do not use creative recipes in normal slots.
- Do not turn this into a general prompt rewrite.
- Do not modify guidelines, parser code, or framework code.
- Do not combine several weird transformations unless prior results justify it.
