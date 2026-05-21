# Internal research (agent knowledge base)

Use this skill when you need to learn how Plexus works before changing
code, running procedures, or answering architecture questions.

## Do not

- Read `documentation/agent/` markdown files directly unless the MCP
  runtime is unavailable.
- Invent documentation ids; every id comes from `docs_list` or `related`.
- Assume semantic / vector search over agent docs (there is none).

## Do

1. Inside `execute_tactus`, run the progressive-disclosure pattern:

```lua
local overview = docs_get{ id = "mcp.execute-tactus-overview" }
local index    = docs_list{ namespace = "<namespace-if-known>" }
-- pick id from summaries, then:
local topic    = docs_get{ id = "<canonical-id>" }
return { overview = overview.content, topic = topic.content }
```

2. Load full canonical topic: `repo-workflows.internal-research`
   (`plexus.docs.get({ key = "repo-workflows.internal-research" })`).

3. For local Python (tests, one-off scripts):

```python
from plexus.documentation.repository import DocumentationRepository

repo = DocumentationRepository("documentation/agent")
print(repo.list_docs(namespace="mcp").entries)
doc = repo.get_doc("mcp.discovery")
```

4. Cite the topic ids you relied on in your final answer.

## Namespaces

| Namespace | Use when |
|-----------|----------|
| `mcp` | execute_tactus, APIs, handles, budgets |
| `score-authoring` | YAML, classifiers, rubric memory |
| `evaluation-feedback` | alignment, optimizer |
| `procedures` | procedure authoring/runtime |
| `reports` | report blocks |
| `optimizer` | CLI optimizer |
| `repo-workflows` | Kanbus, git, internal research |

## Related skills

- Score work: `skills/score-setup/`, `skills/score-optimizer/`
- MCP install: `MCP/README.md`
