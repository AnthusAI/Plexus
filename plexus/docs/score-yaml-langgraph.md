# LangGraphScore YAML Guide

This document explains how to implement the shared score-design patterns in
`LangGraphScore`. Use `score-yaml-format.md` for the "what/when/why" of each
pattern. Use this file for the LangGraph-specific "how".

## When LangGraphScore Fits

Use `LangGraphScore` when the control flow is a fixed graph with a known number of
steps. It is the right tool for:

- a single classifier or extractor
- a short sequence of focused LLM calls
- early exits based on a small number of branches
- fixed fan-out plus deterministic aggregation

If you need variable-length loops over metadata, complex iteration, or a lot of
custom control flow, use `TactusScore` instead.

## Minimal Shape

```yaml
name: Example Score
class: LangGraphScore
model_provider: ChatOpenAI
model_name: gpt-5.4-nano
valid_classes:
  - "Yes"
  - "No"
graph:
  - name: decide
    class: Classifier
    valid_classes: ["Yes", "No"]
    system_message: |
      You are evaluating whether the requirement was met.
    user_message: |
      Transcript:
      {{text}}

      Explain briefly, then end with Yes or No.
output:
  value: classification
  explanation: explanation
```

## Core Rules

### Prefer `Classifier`

Use `Classifier` for new LLM classification nodes. Do not introduce new
`YesOrNoClassifier` or `MultiClassClassifier` usage in fresh work.

Production champions still contain legacy `YesOrNoClassifier` and
`MultiClassClassifier` nodes, sometimes paired with `completion_template` and custom
parse behavior. Treat them as older classifier forms when auditing existing scores,
not as the preferred pattern for new work.

### Nodes Are Independent

Each node is its own LLM call. A node only knows what you put in its prompt and
what you alias from prior state. Do not assume later nodes inherit earlier prompt
context.

### Template Explicit State

LangGraph prompts can template state in both `system_message` and `user_message`.
Deployed scores use `text`, `metadata`, aliased state variables such as
`enrollment_type`, extractor outputs, and `results[...]`.

Keep templates simple:

- alias normalized values into named state keys through `edge.output` or
  branch-level `output`
- use direct variable access and filters such as `| default("SRX")`
- avoid assuming Python-style methods will work inside the template sandbox

### Score Defaults Can Be Overridden Per Node

Top-level model and parse settings are only defaults. Individual nodes may
override `model_provider`, `model_name`, `model_region`, `reasoning_effort`,
`verbosity`, or `parse_from_start` when one step needs a different model or parse
strategy from the rest of the graph.

### Route Explicitly

Use `conditions:` for branch-specific routing and `edge:` for the default path.
If a branch needs custom state aliases, put the aliases under that branch's
`output:` block or under `edge.output`.

### Keep Deterministic Logic Deterministic

If the final decision is a rule like "any missing criterion means No", use a
`LogicalNode` or `LogicalClassifier` for the aggregation step instead of asking a
final LLM node to restate an obvious rule.

## Recipe: Applicability Gate Before the Yes/No Classifier

This is the preferred `NA` pattern in LangGraph. The first node decides whether the
item is in scope. If not, it routes directly to `END` with `value: "NA"`. Only
applicable items reach the pure Yes/No classifier.

```yaml
valid_classes:
  - "Yes"
  - "No"
  - "NA"

graph:
  - name: applicability_gate
    class: Classifier
    valid_classes: ["Applicable", "NA"]
    system_message: |
      Decide whether this item is in scope for the check.
    user_message: |
      Metadata:
      {{metadata}}

      Transcript:
      {{text}}

      End with Applicable or NA.
    conditions:
      - value: "NA"
        node: END
        output:
          value: "NA"
          explanation: explanation
    edge:
      node: core_decision

  - name: core_decision
    class: Classifier
    valid_classes: ["Yes", "No"]
    system_message: |
      Evaluate only the applicable Yes/No requirement.
    user_message: |
      Transcript:
      {{text}}

      Explain briefly, then end with Yes or No.

output:
  value: classification
  explanation: explanation
```

Design notes:

- The gate should be cheap and narrow.
- The core decision should not mention out-of-scope logic.
- This keeps the real binary classifier focused on only one decision.

## Recipe: Extract Evidence Before Judging It

When the model first needs to find a quote, list, or local exchange, use an
`Extractor` before the classifier.

```yaml
graph:
  - name: extract_evidence
    class: Extractor
    system_message: |
      Find the transcript lines where the agent asks for explicit consent.
    user_message: |
      Transcript:
      {{text}}
    edge:
      node: classify_evidence
      output:
        consent_evidence: extracted_text

  - name: classify_evidence
    class: Classifier
    valid_classes: ["Yes", "No"]
    system_message: |
      Decide whether the extracted evidence satisfies the consent rule.
    user_message: |
      Evidence:
      {{consent_evidence}}

      Transcript:
      {{text}}

      Explain briefly, then end with Yes or No.
```

This pattern helps when long transcripts hide the relevant local exchange.

Not all extraction is transcript extraction. Production scores also use `Extractor`
nodes over `metadata.schools` to derive normalized program levels and program
names before the main classifier. When the output format is tightly constrained,
`trust_model_output: true` can be appropriate for these helper extractors.

## Recipe: Normalize Metadata Into State Before Classification

Use `LogicalClassifier` when the normalization step is deterministic, or
`Extractor` when the normalization itself still needs LLM help. The point is to
turn messy metadata into a small, named state value before the main classifier.

```yaml
graph:
  - name: normalize_enrollment_type
    class: LogicalClassifier
    code: |
      def score(parameters: Score.Parameters, input: Score.Input) -> Score.Result:
          import json

          other_data = input.metadata.get("other_data", "{}")
          parsed = json.loads(other_data) if isinstance(other_data, str) else (other_data or {})
          enrollment_type = "SPM" if parsed.get("SPMEnrollment") else "SRX"
          return Score.Result(
              parameters=parameters,
              value=enrollment_type,
              metadata={"enrollment_type": enrollment_type},
          )
    edge:
      node: classify
      output:
        enrollment_type: enrollment_type

  - name: classify
    class: Classifier
    valid_classes: ["Yes", "No"]
    system_message: |
      {% set enrollment_type = enrollment_type | default("SRX") %}
      Evaluate this transcript using the {{ enrollment_type }} ruleset.
    user_message: |
      Transcript:
      {{text}}
```

Use this when the classifier would otherwise need to parse raw JSON, mixed-key
metadata, or long metadata titles inside the prompt itself.

## Recipe: Split by Criterion, Then Aggregate Programmatically

If the business rule has a fixed set of independent criteria, create one node per
criterion and combine them with `LogicalNode`.

```yaml
graph:
  - name: school_name_check
    class: Classifier
    valid_classes: ["Yes", "No"]
    system_message: |
      Check only whether the school name was stated.
    user_message: |
      Transcript:
      {{text}}
    edge:
      node: modality_check
      output:
        school_name_result: classification

  - name: modality_check
    class: Classifier
    valid_classes: ["Yes", "No"]
    system_message: |
      Check only whether the modality was stated.
    user_message: |
      Transcript:
      {{text}}
    edge:
      node: aggregate
      output:
        modality_result: classification

  - name: aggregate
    class: LogicalNode
    code: |
      def execute(context):
          school_name = context["metadata"].get("school_name_result")
          modality = context["metadata"].get("modality_result")
          if school_name != "Yes":
              return {"value": "No", "explanation": "School name missing."}
          if modality != "Yes":
              return {"value": "No", "explanation": "Modality missing."}
          return {"value": "Yes", "explanation": "All required criteria passed."}
    edge:
      node: END
      output:
        value: value
        explanation: explanation
```

Use this when the number of criteria is fixed. If the number of entities is dynamic
and comes from metadata, Tactus is usually cleaner.

## Recipe: Fixed Per-Entity Fan-Out

LangGraph can still work when you have a small, known set of entities. The pattern
is the same as split-by-criterion, but each node checks one explicit entity.

Use this only when:

- the number of entities is fixed at authoring time, or
- the graph is still easy to read after expansion

If the entity count is variable or large, move the score to `TactusScore` and loop.

## Recipe: Early Exit on a Deterministic Rule

Not every branch needs another LLM call. Use `LogicalClassifier` or `LogicalNode`
when the answer is already implied by prior outputs.

Typical uses:

- any failed sub-check means overall `"No"`
- a fuzzy match found the exact required phrase, so skip a fallback classifier
- a dependency result already makes the current score inapplicable

## Recipe: Score Dependencies

Use `depends_on` when another score should run first. Access prior outputs in node
prompts through `results`.

```yaml
depends_on:
  Applicability Check:
    operator: "=="
    value: "Yes"

graph:
  - name: use_prior_result
    class: Classifier
    valid_classes: ["Yes", "No"]
    user_message: |
      Upstream applicability result: {{results["Applicability Check"].value}}
      Upstream explanation: {{results["Applicability Check"].explanation}}

      Transcript:
      {{text}}
```

Keep dependencies crisp. Use them to pass business facts, not to smear unrelated
reasoning across scores.

## Recipe: Input Shaping and Processors

The `item:` section is shared across score types, but it is often essential for a
LangGraph score because the graph assumes each node receives usable text.

Example:

```yaml
item:
  class: DeepgramInputSource
  options:
    pattern: ".*deepgram.*\\.json$"
  processors:
    - class: DeepgramFormatProcessor
      parameters:
        format: words
        speaker_labels: true
    - class: RelevantWindowsTranscriptFilter
      parameters:
        keywords:
          - consent
          - agree
        before: 2
        after: 2
```

Guidance:

- Use `format: words` when exact local ordering matters.
- Use `RelevantWindowsTranscriptFilter` when the decision revolves around a small
  vocabulary in a long transcript.
- Keep processor strategy in the score YAML layer, not inside node prompts.

## Output Mapping and Parse Controls

`output:` is explicit at both node and score levels.

- Node-level `output` maps `classification`, `explanation`, `extracted_text`, or
  computed metadata into named state keys.
- `conditions[].output` and `edge.output` are the normal way to alias values into
  later prompts.
- Final score-level `output` can expose only `value`, or both `value` and
  `explanation`.

`parse_from_start` can be set at the score level or per node. Use per-node
overrides when one node returns label-first output, uses a `completion_template`,
or otherwise needs different parse behavior from the rest of the graph.

## Helpful Node Choices

### `Extractor`

Use when the next step needs a local quote or evidence span.

### `BeforeAfterSlicer`

Use when you need only the conversation before or after a known quote.

### `FuzzyMatchClassifier`

Use when the business rule is mostly lexical and the main problem is phonetic or
transcription variation, not high-level reasoning.

### `LogicalClassifier` / `LogicalNode`

Use when the business rule is already deterministic after prior steps.

## Practical Limits

`LangGraphScore` is strongest when the graph is readable at a glance. Once the YAML
starts simulating loops, dynamic lists, or heavy custom state management, move the
score to `TactusScore` instead of forcing LangGraph to imitate imperative code.
