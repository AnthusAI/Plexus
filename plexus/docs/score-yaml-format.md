# Score YAML Patterns and Shared Design Guide

This document is the umbrella reference for score-authoring patterns. It explains
what techniques exist, when to use them, and why they help. It does not try to be
the canonical syntax guide for every score class.

Use this layering:

- `score-concepts.md`: shared score mental model
- `score-yaml-format.md` (this file): cross-cutting design patterns and YAML-level features
- `score-yaml-langgraph.md`: LangGraph-specific implementation recipes
- `score-yaml-tactusscore.md`: Tactus-specific implementation recipes

## Shared Score Shape

Every score YAML defines the same broad concerns even when the implementation style
changes:

```yaml
name: Example Score
class: LangGraphScore or TactusScore
valid_classes:
  - "Yes"
  - "No"
depends_on:
  Upstream Score:
    operator: "=="
    value: "Yes"
item:
  class: DeepgramInputSource
  options:
    pattern: ".*deepgram.*\\.json$"
  processors:
    - class: RelevantWindowsTranscriptFilter
      parameters:
        keywords: ["consent", "agree"]
output:
  value: classification
  explanation: explanation
```

The class-specific docs explain how to express the score logic itself. This file
focuses on the decisions that should drive that implementation.

## Start With the Output Contract

Before deciding on prompts or nodes, define the output contract clearly.

Questions to answer first:

- Is the business decision truly binary?
- Is there a real `NA` or "not scored" state?
- Should the score emit `confidence`, or is `value` plus `explanation` enough?
- What explanation format will downstream users or tooling need?

Guidance:

- Keep `valid_classes` tight and business-meaningful.
- Do not overload a binary classifier with hidden third states.
- If `NA` means "out of scope", treat that as an applicability question, not just a
  third answer choice.

## Decompose Overloaded Decisions

One large prompt that tries to reason about every edge case at once is usually a
bad optimization target. When a score mixes several independent questions, decompose
it into smaller decisions.

Common reasons to decompose:

- several criteria must all be checked independently
- the score must inspect multiple entities in metadata
- the model first needs to find evidence before it can judge it
- applicability and the real business decision are different questions

Decomposition typically improves:

- prompt clarity
- local evidence retrieval
- interpretability of failures
- ability to aggregate deterministically

## Pattern: Split by Criterion

Use this when the score asks a fixed set of questions such as:

- was the school name stated?
- was the modality stated?
- was the location stated?
- did the caller give a school-specific confirmation?

Why it helps:

- each classifier only solves one sub-problem
- the final rule can often be deterministic
- RCA becomes easier because failures attach to specific sub-checks

This pattern works well in both `LangGraphScore` and `TactusScore`.

## Pattern: Split by Entity or Item

Use this when the score must reason over a variable-length list, such as:

- one decision per school
- one decision per medication
- one decision per disclosure or offer

Why it helps:

- it mirrors the human review process
- it avoids one prompt trying to track several entities at once
- aggregation becomes explicit instead of implicit

Implementation guidance:

- fixed, small fan-out can still fit in `LangGraphScore`
- variable-length iteration usually belongs in `TactusScore`

## Pattern: Extract Evidence Before the Final Judgment

If the first challenge is locating the right text span, do not force the final
classifier to both find and evaluate the evidence in one pass.

Use a two-step structure:

1. extract the relevant quote, exchange, or structured evidence
2. classify whether that evidence satisfies the rule

This is especially useful when:

- transcripts are long
- the score is sensitive to a local exchange
- the final rubric is clear once the right evidence is in view

## Pattern: Deterministic Aggregation

If the final rule is mechanical, code it mechanically.

Examples:

- if any required criterion failed, overall result is `"No"`
- if all entity-level checks passed, overall result is `"Yes"`
- if no applicable entities exist, return `"NA"`

Why it helps:

- it removes unnecessary LLM variance
- it makes the score easier to debug
- it makes optimization safer because the final combination logic is explicit

The LLM should usually produce the uncertain business facts. Code should combine
those facts when the combination rule is already known.

## Pattern: Applicability / `NA` Gating

This is common enough to treat as its own first-class pattern.

Use an applicability gate when a score has a Yes/No decision plus an out-of-scope
case. Typical examples:

- the call is not about the product or flow the score evaluates
- the required metadata entity is missing
- the interaction type should not be scored at all

Preferred structure:

1. gate: is this score applicable?
2. if not applicable, return `"NA"` immediately
3. if applicable, run the pure `"Yes"` / `"No"` classifier

Why it helps:

- the downstream classifier stays focused on the real binary question
- `NA` handling becomes cheaper and less error-prone
- evaluation of the actual binary task becomes cleaner

This pattern is a specific, high-value form of decomposition.

## Pattern: Early Termination and Specialized Routing

Not every score should run every step for every item.

Use early exits when:

- a gate already proved the item is out of scope
- an upstream dependency already resolved the business question
- a deterministic check already makes the answer obvious

Use specialized routing when:

- different subtypes need different prompts
- one context benefits from extra extraction while another does not
- different modalities or product families need different logic

The key principle is to route on the easiest reliable signal available.

## Pattern: Score-to-Score Composition

Scores can compose through `depends_on` and prior `results`.

Use score composition when:

- one score produces a reusable upstream fact
- applicability can be decided once and reused
- several scores need the same extracted or classified business context

Good score composition creates reusable business facts. Bad composition creates
tight coupling where downstream prompts depend on a lot of fragile upstream prose.

Prefer:

- small upstream scores with stable output contracts
- downstream scores that consume specific values from `results[...]`

Avoid:

- assuming prior prompt context carries over implicitly
- reusing an upstream explanation as if it were authoritative structured data

## Pattern: Transcript Representation and Input Shaping

Transcript shape is a score-design concern, not just plumbing.

The default transcript may not be the best representation for the business question.
The `item:` section lets you change what text reaches the classifier.

Important shared tools:

- `DeepgramInputSource`: load Deepgram JSON instead of relying on preformatted text
- `DeepgramFormatProcessor`: choose paragraphs, sentences, or words and control
  speaker labels, timestamps, and channel filtering
- `RelevantWindowsTranscriptFilter`: keep only windows around target keywords

Use these deliberately:

- `format: words` when precise local order matters
- sentence or paragraph formatting when readability matters more than timing
- keyword windows when the decision revolves around a small vocabulary in a long call
- speaker filtering when only one side of the conversation matters

Keep processor strategy in the YAML layer, not buried in prompt instructions.

## Pattern: STT / Phonetic Robustness

Speech-to-text errors are often a core part of the score problem, not noise around
the edges. Design for them explicitly when the score depends on:

- proper nouns
- school or company names
- degree abbreviations
- technical vocabulary
- short affirmative responses

Possible fixes:

- add prompt rules about common phonetic substitutions
- use fuzzy or lexical matching before the classifier
- change transcript representation so the relevant local exchange is easier to see
- add an extraction step that focuses on the target phrase first

Do not treat STT robustness as only a prompt-writing issue. Often the better fix is
structural or processor-based.

## Pattern: Fuzzy or Programmatic Matching Outside the LLM

Some checks are mostly lexical:

- did a target phrase appear?
- is a quoted span phonetically close to a known name?
- did any extracted school name match one of the metadata options?

In those cases, deterministic or fuzzy matching can be a better first tool than an
extra LLM judgment.

Use programmatic matching when:

- the rule is mostly string comparison
- explainability matters
- the model is failing because of transcription variants rather than reasoning

Use the LLM when the task still requires contextual judgment after matching.

## Shared Classifier Pattern

Both `LangGraphScore` and `TactusScore` have a standard classifier-centered way to
express a focused decision. Treat that as the default building block.

The standard classifier pattern should:

- answer one narrow question
- expose an explicit class set
- receive only the context relevant to that question
- return a short explanation tied to that question

When a score is struggling, ask whether the fix is:

- better input text
- a narrower classifier task
- a different decomposition
- deterministic aggregation after the classifier

Do not jump immediately to a larger prompt.

## Optional Confidence

Confidence can be useful, but it is secondary to a correct `value` contract.

Use confidence only when:

- downstream workflows genuinely need it
- the score class supports it clearly
- the team knows how confidence will be interpreted

Do not let confidence design distract from the main label contract or structural
quality of the score.

## Choosing the Implementation Style

Choose `LangGraphScore` when:

- the number of steps is fixed
- the routing graph is easy to read
- extraction, routing, and aggregation fit in a short explicit pipeline

Choose `TactusScore` when:

- the score needs loops or explicit early returns
- metadata contains a variable-length list
- deterministic logic is a substantial part of the workflow
- the score should behave like imperative code rather than a graph

Both score types can express the same high-level patterns. The question is which
representation makes the implementation simplest, clearest, and easiest to optimize.

## See Also

- `score-concepts.md` for the shared mental model
- `score-yaml-langgraph.md` for LangGraph-specific recipes
- `score-yaml-tactusscore.md` for Tactus-specific recipes
- `optimizer-cookbook.md` for guidance on when to try each technique during an
  optimization cycle
