# Score Concepts

This document defines the shared mental model for Plexus scores. Use it to reason
about what a score is, what data it can see, what it should return, and how the
optimizer should talk about mistakes. Use `score-yaml-format.md` for the high-level
design patterns, then use `score-yaml-langgraph.md` or `score-yaml-tactusscore.md`
for concrete implementation syntax.

## Core Objects

### Scorecard

A scorecard is the container for related scores. The scorecard groups the checks
that run against the same item or transcript.

### Score

A score is one evaluative judgment. Most scores are classifiers that at minimum
return a `value` such as `"Yes"`, `"No"`, or `"NA"`. Many scores also expose an
`explanation`.

### Score Version

Each score change creates a new version. Optimizer work should treat the current
champion as the starting point, edit locally, and verify changes against a fixed
baseline before pushing any new version.

### Champion Version

The champion is the currently deployed version. It is the production baseline for
feedback, but it is not automatically the best local candidate during an optimizer
iteration.

## Score Execution Contract

Every score is effectively a function over shared inputs:

- `text`: the primary transcript or document text the score sees
- `metadata`: structured item metadata, such as school lists, modalities, caller
  attributes, or attachment-derived fields
- `results`: prior score outputs when this score depends on other scores

Every score should produce a consistent output contract:

- `value`: the final class label, with exact spelling and casing treated as part
  of the business contract
- `explanation`: optional but common evidence-oriented reasoning for the final
  class
- `confidence`: optional secondary signal when the implementation supports it

The optimizer should treat the output contract as part of the score design, not as
an afterthought. If a score really has three business states, the contract should
say so. If the business question is truly binary, keep the core classifier binary
and handle side conditions separately.

Final `output:` mapping is explicit. Some production scores expose only `value`,
while others also map `explanation` and intermediate fields.

## Dependencies and Composition

Scores can depend on earlier scores. That lets you separate one business question
from another instead of forcing one prompt to do everything at once.

Typical dependency uses:

- Gate a score on an earlier applicability decision
- Reuse prior extracted evidence
- Reuse a prior business decision as an input to a downstream score
- Avoid repeating expensive work across related checks

The shared design rule is simple: upstream scores should provide reusable business
facts, and downstream scores should consume those facts explicitly through
`results[...]`. Do not rely on implicit context.

## Two Implementation Families

### LangGraphScore

Use `LangGraphScore` when the flow is a fixed graph with a known number of steps.
It is best for:

- short, explicit pipelines
- routing between a small number of branches
- extractor -> classifier flows
- deterministic aggregation after a fixed number of checks

### TactusScore

Use `TactusScore` when the logic is easier to express imperatively. It is best for:

- loops over variable-length metadata lists
- multi-pass logic with explicit early returns
- custom aggregation in Lua
- workflows that mix LLM calls with deterministic code

If the flow needs "for each school", "for each medication", or "return immediately
once a failure is found", Tactus is often the better fit.

## Optimizer Mental Model

The optimizer should reason about score changes in layers:

1. What business question is the score answering?
2. What information does the score need to answer it well?
3. Should the question be decomposed into smaller decisions?
4. Which parts should be deterministic instead of LLM-driven?
5. Which score family expresses that structure most clearly?

The highest-leverage improvements are often structural rather than prompt-only:

- separate applicability from the core Yes/No decision
- extract evidence before judging it
- split one overloaded prompt into multiple focused decisions
- aggregate intermediate decisions with deterministic logic
- reshape the transcript before it reaches the model

## Applicability vs. Core Decision

`NA` is not just another label in a three-class classifier. In many business scores,
`NA` means "this check does not apply to this item at all." That is usually a
different question from the real Yes/No judgment.

Preferred pattern:

1. Decide applicability first.
2. If not applicable, return `"NA"` immediately.
3. If applicable, continue to a pure `"Yes"` / `"No"` classifier that does not
   need to reason about out-of-scope cases.

This preserves the accuracy of the true binary decision because the main classifier
is only solving one problem.

## Transcript Shape Is Part of the Score

The score is not just the prompt. The input text format matters. Transcript
representation choices can dominate performance:

- sentence-level text is easier to read
- keyword-window filtering can keep evidence in focus
- word-level timing can preserve exact local order
- speaker filtering can remove irrelevant turns
- timestamp slicing can isolate the relevant call segment

Treat `item:` sources and processors as score design tools, not as implementation
details.

## Error-Segment Language Policy

Optimizer-facing documentation must avoid `false positive`, `false negative`, `FP`,
and `FN`. Those terms are ambiguous whenever the business-negative class is the
label of interest.

Use one of these instead:

- Compact shorthand: `P"No"->A"Yes"`
- Full prose: `cases where the model predicted "No" but the actual label was "Yes"`

`P` means predicted and `A` means actual. Use the exact class labels from the score.
For example:

- `P"No"->A"Yes"` means the model predicted `"No"` but the actual label was `"Yes"`
- `P"Yes"->A"No"` means the model predicted `"Yes"` but the actual label was `"No"`

Target one prediction-outcome segment at a time when forming a hypothesis. A fix
for `P"No"->A"Yes"` often pulls in the opposite direction from a fix for
`P"Yes"->A"No"`.
