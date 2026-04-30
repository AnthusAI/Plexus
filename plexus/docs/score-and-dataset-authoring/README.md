# Score & Dataset Authoring

Topic index for authoring Plexus scores, datasets, and the rubric memory that
backs them. Read these when you are creating or modifying score
configurations rather than running them.

## Files

- `score-yaml-format`: Complete reference for the Score YAML format —
  LangGraph nodes, graph wiring, dependencies, prompts, and proven patterns.
  Read this first when authoring or editing any score YAML.
- `score-concepts`: Short conceptual primer on score structure, applicable
  to all score class types. Useful as a warm-up before the format reference.
- `score-yaml-langgraph`: LangGraphScore-specific YAML reference — node
  types, classifiers, extractors, conditions, routing.
- `score-yaml-tactusscore`: TactusScore-specific YAML reference — Lua DSL
  syntax, procedures, model directives.
- `dataset-yaml-format`: Dataset YAML configuration for data sources,
  joins, filters, and pagination.
- `rubric-memory`: Scorecard knowledge-base folders, temporal source
  conventions, retrieval-only citation contexts, and RubricEvidencePack
  synthesis.
- `score-rubric-consistency`: Lightweight preflight check that compares a
  ScoreVersion's code against its rubric before promotion or evaluation.
  Use `plexus.score.contradictions` in `execute_tactus` or
  `plexus score contradictions` on the CLI.

## When to use each

- Editing a score's prompts or node graph -> `score-yaml-format`
  (and `score-yaml-langgraph` for LangGraph-specific node types).
- Creating a new score from scratch -> `score-concepts` first, then
  `score-yaml-format`.
- Wiring up a new data source -> `dataset-yaml-format`.
- Adding policy/rubric documents that the score should cite ->
  `rubric-memory`.
- Checking that edited code still matches the rubric before promoting ->
  `score-rubric-consistency`.

## Reading from `execute_tactus`

```tactus
local guide = plexus.docs.get{ key = "score-yaml-format" }
```

Legacy flat keys (`score-yaml-format`, `score-concepts`,
`score-yaml-langgraph`, `score-yaml-tactusscore`, `dataset-yaml-format`,
`rubric-memory`) keep resolving for backward compatibility with
`get_plexus_documentation`. The nested form
`score-and-dataset-authoring/score-yaml-format` works too.
