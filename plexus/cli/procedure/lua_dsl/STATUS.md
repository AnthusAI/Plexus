# Lua DSL Implementation Status

**Last Updated:** 2025-12-03
**Phase 1:** COMPLETE ✅
**v3 Unified Model:** CORRECTED ✅
**Status:** Production Ready with `params:` + `outputs:` Validation

---

## What's Working

### ✅ Core Runtime (Fully Functional)
```bash
plexus procedure run --yaml workflow.yaml
```

- **YAML Parsing** - Validates structure, detects `class: LuaDSL`
- **Lua Sandbox** - Secure execution (no file I/O, no OS access)
- **MCP Integration** - Full access to 25 Plexus tools
- **Agent Execution** - `Worker.turn()` calls LLM with tools
- **Chat Logging** - All conversations recorded to API ✅
- **Custom Stages** - From YAML, not hard-coded
- **No Auto-Nodes** - Graph nodes only created by your code

### ✅ v3 Unified Model Features

- **Params Schema** - `params:` (Plexus standard, unchanged)
- **Output Schemas** - `outputs:` with type validation
- **Schema Injection** - Output format shown to LLM automatically
- **GraphNode Creation** - `GraphNode.create()` primitive
- **Validation** - Runtime checks for workflow return values

### ✅ Primitives Implemented

**Agent**: `Assistant.turn()`, `Worker.turn()`
**State**: `State.get()`, `State.set()`, `State.increment()`, `State.append()`
**Tool**: `Tool.called()`, `Tool.last_result()`, `Tool.last_call()`
**Control**: `Iterations.current()`, `Iterations.exceeded()`, `Stop.requested()`
**GraphNode**: `GraphNode.create()`, `GraphNode.root()`, `GraphNode.current()`

### ✅ Verified via API
- Procedures created without scorecard/score
- No root nodes unless explicitly created
- Task stages match YAML definition
- Chat sessions contain all messages:
  - SYSTEM prompts
  - USER messages
  - ASSISTANT responses
  - TOOL calls/results

---

## Example Working Workflow (v3 Corrected)

```yaml
name: simple_assistant
version: 1.0.0
class: LuaDSL

params:
  task:
    type: string
    default: "Say hello"

outputs:
  completed:
    type: boolean
    required: true
  iterations:
    type: number
    required: true

agents:
  assistant:
    system_prompt: "Complete this task: {params.task}"
    initial_message: "Begin working."
    tools: [done]

stages:
  - working

workflow: |
  repeat
    Assistant.turn()
  until Tool.called("done") or Iterations.exceeded(50)

  return {
    completed = Tool.called("done"),
    iterations = Iterations.current()
  }
```

Run it:
```bash
plexus procedure run --yaml workflow.yaml
```

Check results in API:
```bash
plexus procedure show <procedure-id>
# Shows: No root node, custom stages, chat session logged
```

---

## Key Design Wins

1. **Script-like UX** - Run YAML like executing a program
2. **Database-optional** - Graph nodes only if you use them
3. **Full Observability** - Every LLM message logged to API
4. **Backward Compatible** - SOP agents unchanged
5. **Language Stable** - No design spec changes needed

---

## What's Next (Phase 2+)

See IMPLEMENTATION_ROADMAP.md for full details:

- **Template System** - Multi-namespace variables, prepare hooks
- **Sub-Agents** - Context isolation, recursion support
- **Async Sub-Agents** - Parallel execution
- **Conversation Filters** - History management
- **Additional Primitives** - GraphNode, Query, File, Session, etc.

---

## Report to Committee

**Language Design Assessment**: ✅ v3 UNIFIED MODEL CORRECTED

Committee directive correctly implemented after initial misunderstanding:
- **KEPT `params:`** - Plexus standard (no changes)
- **ADDED `outputs:`** - Schema validation (new feature)
- **Template vars** - Still use `{params.x}` (unchanged)
- **Phase 3 prep** - Foundation for `procedures:` and `Procedure.*` primitives

**Correction Applied:** Initial implementation wrongly introduced `inputs:` keyword. This has been reverted. The system now correctly uses Plexus standard `params:` for all parameter schemas.

**Implementation Notes**:
- Chat logging uses queue-and-flush pattern (Lua sync → Python async)
- Role values must be ALL CAPS: 'SYSTEM', 'USER', 'ASSISTANT', 'TOOL'
- GraphQL doesn't support 'state' field in CreateProcedureInput
- MCP server setup requires `create_procedure_mcp_server()` from `mcp_transport`
- Output schemas automatically injected into agent prompts
- Lua tables converted recursively to Python dicts for validation
- `params:` maintained as Plexus standard (no deprecation warnings)
