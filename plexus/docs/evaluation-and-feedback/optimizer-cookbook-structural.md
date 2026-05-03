# Optimizer Cookbook: Structural Hypotheses

Use this cookbook for `structural`, `reframe`, and `full_rewrite` slots.

Structural hypotheses change model choice, input source, preprocessing, graph
shape, decomposition, or late prompt attention structure. They should not crowd
out the normal rubric-oriented hypotheses.

## Scan First

Before proposing a structural hypothesis, inspect `score_config.yaml`,
accumulated lessons, smoke-test history, and the RCA. Do not retry a structural
approach that already failed in the run unless the mechanism is materially
different.

## C1. Architecture

Use when one classifier call is doing too much.

### C1a. Decompose Into Sequential Calls

Use when the score evaluates multiple independent elements, such as each school,
disclosure, offer, room, project type, or required question.

- Make one focused call per element.
- Aggregate the element-level results into the final class.
- Keep the final class set unchanged.

### C1b. Add An N/A Gate

Use when applicability is distinct from the final scoring decision.

- First call: decide whether the item is in scope.
- Second call: score only applicable items.
- Return the existing N/A class immediately when the gate determines the item is
  out of scope.

### C1c. Add An Extractor Node

Use when the model must find specific evidence before classifying.

- Use `class: Extractor`.
- Map `output.extracted_text` into a named state field.
- Feed that state field into the final classifier.
- Do not use `Classifier(valid_classes=['Extracted'])` as a pseudo-extractor.

### C1d. Split Parallel Criteria

Use when the score checks several independent criteria and any one failure means
the final answer is negative.

- Score each criterion in a separate focused call.
- Combine the results deterministically.
- Prefer this when errors show the model misses one criterion while attending to
  another.

## C1e. Input Source

Use when the default transcript text hides evidence, timing, speaker identity, or
word order.

Deepgram input can expose structured transcript data such as sentences, words,
speaker labels, timestamps, and channels. Only propose it when item attachments
actually include Deepgram JSON and prior cycles have not shown attachment
failures.

Prefer broad sentence formatting first for readability. Use word-level format
only when exact timing or sequential acknowledgement matters.

## C2. Preprocessing

Use when long transcripts bury decision-relevant content or existing processors
hide needed evidence.

Good candidates:

- Add `RelevantWindowsTranscriptFilter` for keyword-focused scores.
- Broaden a too-narrow relevant-window processor.
- Remove or relax a processor that is suppressing reviewer-relevant evidence.
- Preserve enough surrounding context for short customer answers to remain tied
  to the agent prompt.

Start with broad sentence windows, such as `prev_count=5` and `next_count=8`.
Avoid first attempts with one-word windows on conversational transcripts.

## C3. Model Swap

Use when the score is on a stale or weak model.

- First structural model hypothesis: move to `gpt-5.4-nano` if the score is not
  already using it.
- After multiple stagnant cycles, consider `gpt-5.4-mini`.
- Do not propose a mini model for a cost-efficiency objective unless explicitly
  justified by the objective.
- Do not retry a model that already failed in the run.

## C4. Prompt-Shape / Attention-Structure Transformations

Late structural option. Use when normal policy changes have not moved alignment
and the RCA suggests the model knows the rule but attends to the wrong part of
the prompt or transcript.

These are structural attention experiments, not substitutes for rubric fixes.
They are a lightweight alternative to CoT when the issue appears to be attention
rather than reasoning.

Useful tactics:

- Repeat the decisive question/rule near the transcript and again immediately
  before the final answer instruction.
- Put the transcript first and the classification instruction at the end.
- Alternate compact reminders around long transcript blocks.
- Put a short "decide using this rule" reminder beside the evidence window.
- Lower-priority test: reorder label definitions or valid_classes to check
  label-order sensitivity.

Do not duplicate input transcript text. Repeat only operative instructions or
decision rules.

## C5. Full Rewrite

Use in `full_rewrite` after repeated plateauing.

- Start from the baseline version when useful.
- Redesign major prompt sections, graph structure, preprocessing, or model
  allocation.
- Preserve the classifier shape and valid classes.
- Explain why the old framing was likely exhausted.

## Reframe Slot Guidance

Use the structural cookbook but challenge the dominant assumption from prior
cycles. A reframe can change the decision framework, decomposition, or rubric
interpretation while staying within score YAML.

## Full-Rewrite Slot Guidance

Use the structural cookbook but allow a larger redesign. The rewrite must still
be testable, smoke-testable, and comparable to the same baseline.
