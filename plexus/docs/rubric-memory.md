# Rubric Memory and Scorecard Knowledge Bases

Rubric memory is Plexus's local knowledge-base system for adding policy history, meeting notes, emails, chat excerpts, scripts, and other supporting material to score analysis. It does not replace the official rubric. The official policy authority is the active `ScoreVersion` for the score, usually the score's champion version through `Score.championVersionId`.

In current storage, rubric text is still stored in fields named `guidelines`, and score code is stored in `configuration`. New rubric-memory code uses `rubric` terminology and translates from `guidelines` only at the storage adapter boundary.

## What Rubric Memory Is For

Rubric memory helps agents and reports answer questions such as:

- What did SMEs, clients, or internal teams say about this policy over time?
- Does the local corpus explain why a disputed classification should be interpreted one way?
- Is the official rubric clear, or does the corpus show a policy gap or stale rubric area?
- Has this issue already been answered, so an optimizer should avoid asking SMEs again?

Corpus evidence can explain, support, conflict with, or contextualize the official rubric. It cannot silently override the active `ScoreVersion` rubric.

## Local Folder Convention

Rubric memory uses the same pulled-score workspace convention as local score YAML and Markdown files. It does not use a separate root and does not require a per-score configuration file.

The score YAML path is derived with `get_score_yaml_path(scorecard_name, score_name)`. The adjacent knowledge-base folders are then derived from that same location.

```text
<SCORECARD_CACHE_DIR>/
  <Scorecard Name>/
    scorecard.knowledge-base/
    <Prefix>.knowledge-base/
    <Score Name Stem>.knowledge-base/
    <Score Name Stem>.yaml
    <Score Name Stem>.md
```

For example, if `SCORECARD_CACHE_DIR=dashboard/scorecards` and the score is `SelectQuote HCS Medium-Risk` / `Medication Review: Dosage`, the score-level knowledge base is:

```text
dashboard/scorecards/SelectQuote HCS Medium-Risk/Medication Review- Dosage.knowledge-base/
```

The name must match the sanitized score file stem used by the pulled-score convention. This keeps the `.yaml`, `.md`, and `.knowledge-base` artifacts visibly aligned.

## Scope Levels

Retrieval combines all applicable canonical roots for a score request:

- `score`: exact score-level material from `<Score Name Stem>.knowledge-base/`.
- `prefix`: shared material from matching prefix folders such as `Information Accuracy.knowledge-base/`.
- `scorecard`: scorecard-wide material from `scorecard.knowledge-base/`.

Ranking prefers score-specific evidence first, prefix evidence second, scorecard-wide evidence third, and unknown scope last.

## Prefix Knowledge Bases

Prefix knowledge bases apply to multiple related scores in a scorecard. They are useful when a composite concept is split into many sub-scores.

Example:

```text
dashboard/scorecards/SelectQuote HCS Medium-Risk/
  Information Accuracy.knowledge-base/
  Information Accuracy- High-Pressure Sales Tactics.yaml
  Information Accuracy- High-Pressure Sales Tactics.knowledge-base/
  Information Accuracy (Composite).yaml
```

`Information Accuracy.knowledge-base/` applies to scores whose sanitized score names begin with `Information Accuracy` at a clear boundary, such as a space, hyphen, or parenthesis. It applies to both `Information Accuracy: High-Pressure Sales Tactics` and `Information Accuracy (Composite)`.

Prefix folders are optional overlays. If no matching prefix folder exists, retrieval still uses the scorecard and exact-score roots. Plexus does not search alternate locations.

## Date Folders

Temporal context matters because policy interpretation changes over time. The canonical date convention is to place raw files under a `YYYY-MM-DD` folder:

```text
<Score Name Stem>.knowledge-base/
  2026-04-24/
    meeting-notes.md
    client-email.txt
  unknown-date/
    pasted-notes-without-date.md
```

The date means the meeting date, email date, chat date, or document date. Plexus infers `source_timestamp` from the nearest ancestor folder matching `YYYY-MM-DD`, even for nested paths:

```text
2026-04-24/client/source.md
```

Files under `unknown-date/` remain retrievable but have no `source_timestamp`, so they do not contribute to chronological history ordering.

Plexus never rewrites raw knowledge-base files to add metadata. Inferred timestamps and scope metadata are attached only in the prepared working corpus.

## Raw Source Files

V1 intentionally keeps raw source organization simple. You do not need separate folders for emails, chats, notes, or scripts. Put source files wherever they fit under the correct scope and date folder.

Overlap and duplication are acceptable. A source can be copied into a scorecard-level folder and a score-level folder if both scopes should retrieve it. Retrieval deduplication and ranking happen at runtime.

## Prepared Corpora

Before retrieval, Plexus prepares the local corpus under ignored repo-local storage:

```text
tmp/rubric-memory/prepared/<stable-cache-key>/
```

The prepared corpus manager:

- resolves the scorecard, prefix, and score roots using the canonical folder convention;
- copies raw files into the prepared cache;
- writes Biblicus sidecar metadata only inside `tmp/rubric-memory/prepared/...`;
- records a manifest with source roots, file counts, retriever id, schema version, fingerprint, and prepared timestamp;
- reuses the cache when the source fingerprint is unchanged;
- rebuilds when paths, sizes, mtimes, inferred timestamps, scope levels, retriever id, or sidecar schema version change.

Manual prewarming uses the same code path as just-in-time runtime preparation:

```bash
SCORECARD_CACHE_DIR=dashboard/scorecards plexus rubric-memory prewarm \
  --scorecard "SelectQuote HCS Medium-Risk" \
  --score "Medication Review: Dosage"
```

Prewarming does not generate analysis. It only prepares the corpus so later retrieval starts faster and uses the same prepared state.

## Product 1: Retrieval-Only Citation Context

The retrieval-only citation context is input to an LLM call. It is deterministic Python/Biblicus work, not an extra synthesis call.

It contains:

- an authority summary for the official `ScoreVersion`;
- one official rubric citation;
- ranked corpus evidence citations;
- a chronological policy memory section from dated snippets;
- compact machine JSON with citation IDs, counts, and provenance.

This is the preferred product for existing per-item agents and reports that already perform their own reasoning. The context is injected into the existing prompt so the existing agent can cite evidence when making decisions.

Current and intended consumers include:

- `FeedbackContradictions` per-item voters;
- RCA classifier/explainer item contexts;
- optimizer hypothesis planning and policy-sensitive reasoning;
- SME question gating.

Citation IDs are stable within a generated context and refer either to official rubric authority or retrieved corpus evidence. Citation validation reports missing, unused, or omitted citations as diagnostics during rollout rather than failing execution.

## Product 2: Rubric Evidence Pack

`RubricEvidencePack` is an optional synthesized analysis output. It is generated by Python retrieval and shaping followed by Tactus synthesis.

Use it when a caller needs a deeper, structured explanation of one disputed item, not merely extra context for an already-running agent.

The pack includes:

- `rubric_reading`;
- `evidence_classification`;
- `supporting_evidence`;
- `conflicting_evidence`;
- `history_of_change`;
- `likely_reason_for_disagreement`;
- `confidence`;
- `confidence_inputs`;
- `open_questions`.

Evidence classifications include `rubric_supported`, `rubric_conflicting`, `rubric_gap`, `historical_context`, and `possible_stale_rubric`.

The evidence pack is useful for drill-through analysis, exemplar review, RCA deep dives, SME question gates, and on-demand tools. It is intentionally heavier than retrieval-only citation context because it adds a separate LLM synthesis step.

## Choosing The Right Product

Use retrieval-only citation context when an existing LLM agent is already about to reason over an item and needs better policy memory as input.

Use `RubricEvidencePack` when the desired output is itself a structured interpretation of the rubric, corpus evidence, chronology, disagreement cause, confidence, and open questions.

Do not use `RubricEvidencePack` as the default per-item input for high-volume report voting. That creates an unnecessary second LLM process per item before the existing voter.

## Authority Rules

The official rubric always wins over contradictory low-authority corpus evidence. Contradictory or older corpus snippets should still be surfaced as conflict, stale-rubric evidence, or history.

If the corpus answers a question but the rubric is unclear, agents should transform the question from "What is the policy?" into "Should the rubric be updated to explicitly say this?" with citations.

If evidence is sparse, conflicting, or undated, agents should lower confidence and produce open questions rather than confident policy claims.

