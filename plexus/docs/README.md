# Plexus Documentation

This directory holds documentation that is exposed two ways:

1. **`execute_tactus`** runtime: any markdown file here is reachable via
   `plexus.docs.list()` (returns the keys) and `plexus.docs.get{ key = "..." }`
   (returns the content). The runtime walks the directory recursively and
   skips every `README.md`. Nested files are addressable by their
   slash-separated relative path with the `.md` extension stripped, for
   example `evaluation-and-feedback/feedback-alignment`.

2. **`get_plexus_documentation`** MCP tool: an allowlisted dictionary in
   [MCP/tools/util/docs.py](../../MCP/tools/util/docs.py) and
   [MCP/tools/documentation/docs.py](../../MCP/tools/documentation/docs.py)
   maps short keys (e.g. `feedback-alignment`) to file paths under this
   directory.

## Layout

The files are organized into Tactus-native themes:

```
plexus/docs/
  overview.md               canonical execute_tactus boot prompt
  discovery.md              api.list / docs.list / docs.get patterns
  read-apis.md              read-only API reference (scorecards, scores, items)
  long-running-apis.md      async = true contract and budget requirements
  handles-and-budgets.md    handle.peek/await/cancel, budget carving
  score-and-dataset-authoring/
    README.md
    score-yaml-format.md
    score-concepts.md
    score-yaml-langgraph.md
    score-yaml-tactusscore.md
    dataset-yaml-format.md
    rubric-memory.md
    score-rubric-consistency.md
  evaluation-and-feedback/
    README.md
    feedback-alignment.md
    evaluation-alignment.md
    optimizer-cookbook.md
    optimizer-procedures.md
    optimizer-objective-alignment.md
    optimizer-objective-precision.md
    optimizer-objective-recall.md
    optimizer-objective-cost.md
  procedures/
    README.md
  reports/
    README.md
```

## Backward compatibility

Every key that worked under the old flat layout still resolves. The
resolver in `MCP/tools/tactus_runtime/execute.py` (`_docs_read`) and in
the two MCP `get_plexus_documentation` tool implementations tries the
key as a nested path first, then falls back to a recursive stem search.
That means `feedback-alignment`, `score-yaml-format`,
`dataset-yaml-format`, `rubric-memory`, and every other legacy key keep
working without any changes on the caller side.

`get_plexus_documentation` also exposes the new top-level docs
(`overview`, `discovery`, `read-apis`, `long-running-apis`,
`handles-and-budgets`) and one `theme-*` key per theme directory
(`theme-score-and-dataset-authoring`, `theme-evaluation-and-feedback`,
`theme-procedures`, `theme-reports`) for direct theme-index access.

## Adding new documentation

1. Drop the `.md` file in the appropriate theme directory (or at the
   top level if it is cross-cutting).
2. `execute_tactus` will pick it up automatically through
   `plexus.docs.list()`.
3. If you want it reachable from `get_plexus_documentation`, add an
   entry to the `valid_files` map in
   [MCP/tools/documentation/docs.py](../../MCP/tools/documentation/docs.py)
   (and the matching docstring) and to
   [MCP/tools/util/docs.py](../../MCP/tools/util/docs.py).
4. Use descriptive, hyphenated names; nest by theme; avoid spaces.
