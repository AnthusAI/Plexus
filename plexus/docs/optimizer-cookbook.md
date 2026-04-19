# Optimizer Cookbook

This document tells the optimizer **which kind of change to try**. It is not the
canonical syntax reference for score code. When you decide on a structural move,
use:

- `score-yaml-format.md` for the pattern-level rationale
- `score-yaml-langgraph.md` for LangGraph implementation details
- `score-yaml-tactusscore.md` for Tactus implementation details

## Terminology Policy

Do not use legacy positive/negative error shorthand or any two-letter abbreviation
that depends on an implied "positive class".

Use either:

- `P"No"->A"Yes"`
- `P"Yes"->A"No"`

or the full prose equivalent. Target one prediction-outcome segment per hypothesis.
A change that helps `P"No"->A"Yes"` often hurts `P"Yes"->A"No"`.

## Mandatory Scan Before Proposing Hypotheses

Before you suggest prompt edits, scan the current score configuration for structural
signals. If one of these signals is present, include the matching hypothesis in the
candidate set even if you also include prompt-level options.

### 1. Stale model signal

If the score still uses `gpt-4o-mini`, include a model-swap hypothesis unless the
run history already shows the same swap failed recently.

Why:

- cheapest structural change
- very low implementation risk
- often enough to improve basic classification stability

### 2. Applicability mixed into the main classifier

If the score has `"Yes"`, `"No"`, and `"NA"` semantics in one overloaded decision,
add an applicability-gate hypothesis.

Look for:

- prompts that explain out-of-scope logic at length
- a three-way classifier where `NA` really means "not this kind of call"
- RCA categories that mix in-scope misses with out-of-scope items

Preferred fix:

- first decide applicability
- return `"NA"` immediately when out of scope
- keep the downstream classifier purely `"Yes"` / `"No"`

### 3. Several independent criteria in one prompt

If the score asks one prompt to check multiple independent elements, include a
decomposition hypothesis.

Look for:

- long rule lists with many distinct "must include" conditions
- explanations that mention different missing elements on different items
- RCA that clusters around one criterion being forgotten while others are handled

Preferred fixes:

- split by criterion, then aggregate deterministically
- split by entity when the score evaluates several metadata objects

### 4. Evidence retrieval failure

If the decision appears correct once the evidence is visible, but the model keeps
missing the relevant local exchange, include an extraction or transcript-shaping
hypothesis.

Look for:

- long transcripts where the decisive exchange is brief
- RCA comments that say the required phrase was present but ignored
- patterns where the explanation reasons correctly about the wrong text span

Preferred fixes:

- extraction before final judgment
- `RelevantWindowsTranscriptFilter`
- a tighter local transcript slice

### 5. Precise timing or local ordering

If the business rule depends on exactly which response followed which item, include
a word-level transcript hypothesis.

Look for:

- one-by-one confirmations
- interruption or overlap logic
- list items that each require their own short response
- questions where sentence grouping can reorder the evidence

Preferred fix:

- `DeepgramInputSource` plus word-level formatting

Do not try to solve this purely with prompt wording if the underlying transcript
format does not preserve the required local order.

### 6. STT / phonetic confusion

If the score depends on names, degree abbreviations, or jargon that are commonly
mistranscribed, include a phonetic-robustness hypothesis.

Look for:

- school names or program names that sound like common words
- abbreviations such as `AS`, `AAS`, `BS`, `MBA`, or `HVAC`
- human corrections that clearly credit speech the transcript mangled

Preferred fixes:

- explicit prompt rules for known phonetic substitutions
- fuzzy or lexical matching before the classifier
- decomposition that isolates the fuzzy-matching problem from the final decision

## Hypothesis Categories

### Category A: Incremental prompt fix

Choose this when the structure is already sound and the RCA points to a missing or
ambiguous rule.

Good uses:

- add a missing policy rule
- sharpen an ambiguous threshold
- clarify what counts as evidence
- add at most one or two targeted speech-to-text examples when the issue is clearly
  phonetic

Do not use this category to paper over a transcript-format problem or a deeply
overloaded prompt.

### Category B: Bold prompt overhaul

Choose this when the structure is still roughly right but the prompt needs a major
reorganization.

Good uses:

- rewrite the decision framework
- restructure the prompt into explicit stages
- collapse redundant instructions into a clearer rubric

Use this when several prompt-level problems share the same root cause and a local
edit is unlikely to be enough.

### Category C: Structural change

Choose this when the problem is not primarily about wording.

Typical structural moves:

- applicability / `NA` gate
- split by criterion
- split by entity
- extraction before judgment
- deterministic aggregation
- processor or input-source redesign
- model swap

Structural changes are usually the highest-upside option and should appear in every
cycle unless the run history already ruled them out.

## Choosing Between the Main Structural Moves

### Use an applicability gate when

- the score mixes scope detection with the real decision
- out-of-scope items are common
- the `"Yes"` / `"No"` classifier would be simpler without `NA`

### Split by criterion when

- the business rule has a fixed set of required elements
- the model misses one element while handling others correctly
- the final rule is deterministic once the sub-checks exist

### Split by entity when

- the item contains several schools, medications, offers, or disclosures
- each entity should be evaluated independently
- failures should attach to one entity at a time

### Extract before judging when

- the main difficulty is finding the evidence
- the final rule is clear after the evidence is isolated
- transcripts are long and noisy

### Change transcript shape when

- sentence-level formatting loses local order
- the decisive content is only a small fraction of the transcript
- one speaker or one time range matters much more than the rest

## How to Read RCA Before Choosing a Fix

Read the RCA in this order:

1. Which segment is the optimizer targeting: `P"No"->A"Yes"` or `P"Yes"->A"No"`?
2. Is the failure about missing policy, missing evidence, transcript shape, or
   aggregation logic?
3. Is the score solving one question or several?
4. Would a deterministic rule remove one source of variance immediately?

If the RCA mostly says "the model did not see the right evidence", start with input
shape or extraction. If it mostly says "the model saw the evidence but applied the
wrong rule", start with prompt or decomposition changes. If it says both, prefer the
smallest structural change that separates those concerns.

## Anti-Patterns

Avoid these moves unless the evidence clearly supports them:

- adding more examples for a structural problem
- adding another large rule block to a prompt that already tries to do too much
- using a three-way classifier when `NA` is really an applicability gate
- asking an LLM to restate a deterministic final rule
- changing prompt wording to solve a transcript-order problem

## Final Rule

The cookbook chooses the move. The score docs define how to implement it. Do not
duplicate long YAML or Lua recipes here; point to the canonical score documentation
instead.
