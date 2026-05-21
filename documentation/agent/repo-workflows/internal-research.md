---
id: repo-workflows.internal-research
title: Internal Research (Agent Knowledge Base)
summary: How agents and scripts discover Plexus documentation via progressive disclosure (docs.list then docs.get).
namespace: repo-workflows
status: canonical
disclosure: cookbook
audience: agent
tags: [docs, discovery, research, knowledge-base]
related:
  - mcp.discovery
  - mcp.execute-tactus-overview
  - repo-workflows._index
---
# Internal Research (Agent Knowledge Base)

Plexus keeps agent-facing documentation in `documentation/agent/`. The
runtime exposes it as a **frontmatter-indexed knowledge base**, not a
semantic search engine. Research means listing metadata summaries,
choosing canonical topic ids, then loading full bodies on demand.

## Runtime API (inside `execute_tactus`)

Use the injected helpers or the `plexus.docs` namespace. Both resolve
to the same repository.

```tactus
-- 1. Bootstrap (cheap)
local apis     = api_list()
local overview = docs_get{ id = "mcp.execute-tactus-overview" }

-- 2. Browse summaries only (no markdown bodies)
local index = docs_list{}  -- all namespaces
-- or:
local score_docs = docs_list{ namespace = "score-authoring" }

-- 3. Load one topic by canonical id
local topic = docs_get{ id = "evaluation-feedback.optimizer-procedures" }
return {
  title   = topic.metadata.title,
  related = topic.metadata.related,
  body    = topic.content,
}
```

`docs_list` / `plexus.docs.list` returns entries with `id`, `title`,
`summary`, `namespace`, `status`, `disclosure`, `tags`, and `related`.
`docs_get` / `plexus.docs.get` accepts `id` or `key` (same value).

**Progressive disclosure:** always call `docs_list` first. Summaries are
token-cheap. Call `docs_get` only for ids you intend to use. Follow
`related` links for adjacent topics.

**Namespaces:** `mcp`, `score-authoring`, `evaluation-feedback`,
`procedures`, `reports`, `optimizer`, `repo-workflows`.

**Excluded from listings:** `README.md` and `_index.md` files (fetch
`_index` topics explicitly by id when you need a namespace overview).

There is no full-text search API. Filter by:

- `namespace` on `docs_list`
- Reading `summary` and `tags` in list results
- Matching substrings on `id` in Lua when you know a keyword
- Walking `related` from a seed topic

## Python API (local scripts and tests)

The same index is implemented in
`plexus/documentation/repository.py`:

```python
from pathlib import Path

from plexus.documentation.repository import DocumentationRepository

root = Path("documentation/agent")
repo = DocumentationRepository(str(root))

# Metadata only
result = repo.list_docs(namespace="evaluation-feedback")
for entry in result.entries:
    print(entry["id"], entry["summary"])

# Full document (metadata + body without frontmatter block)
doc = repo.get_doc("mcp.discovery")
print(doc.metadata["related"])
print(doc.body[:500])
```

`list_docs` also reports `invalid` files (missing or malformed
frontmatter) without failing the whole index.

Behave coverage lives in `features/agent_documentation_kb.feature`.
An end-to-end agent integration test wires `docs_list` / `docs_get` tools
through the Tactus `AgentPrimitive` in
`plexus/documentation/test_documentation_kb_integration.py` (marked
`integration`, requires `OPENAI_API_KEY`).

## Research workflow for a new task

1. `docs_get{ id = "mcp.execute-tactus-overview" }` — runtime rules and
   namespace map.
2. `api_list()` — which `plexus.*` methods exist.
3. `docs_list{ namespace = "<area>" }` — pick topics by summary/tags.
4. `docs_get{ id = "<chosen-id>" }` — load bodies; chase `related`.
5. Cite topic ids in your reply so humans can re-fetch the same sources.

## Not the same as rubric-memory search

Scorecard **rubric memory** uses Biblicus corpora under
`*.knowledge-base/` folders (policy PDFs, emails, meeting notes). That
path is documented in `score-authoring.rubric-memory` and uses
`BiblicusRubricEvidenceRetriever`, not `DocumentationRepository`. Use
agent KB research for Plexus product behavior; use rubric memory for
score-specific policy evidence.

## Human-readable tree

Humans may browse `documentation/agent/` directly. Agents should prefer
`docs_list` / `docs_get` so summaries stay consistent with runtime
behavior.
