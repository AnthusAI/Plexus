# Lua DSL Implementation Roadmap

**Last Updated:** 2025-12-03
**Status:** Phase 1 Complete, Phase 2+ Planned

## Design Fidelity

✅ **No design changes required** - Implementation follows spec without modifications
✅ **Language specification stable** - All features map directly to spec
✅ **Examples work as designed** - Example 1 (Simple ReAct) runs successfully

---

## Phase 1: Core Runtime (COMPLETE ✅)

### YAML Parser & Validation
- ✅ Parse procedure YAML structure
- ✅ Validate required fields (name, version, agents, workflow)
- ✅ Support both `LuaDSL` and `SOPAgent` classes
- ✅ Extract custom stages from YAML

### Lua Sandbox
- ✅ lupa (LuaJIT) integration
- ✅ Blocked dangerous operations (io, os, debug, package)
- ✅ Primitive injection system
- ✅ Safe execution environment

### Basic Primitives
- ✅ **Agent**: `Worker.turn()`, `Manager.turn()`
- ✅ **State**: `State.get()`, `State.set()`, `State.increment()`, `State.append()`
- ✅ **Tool**: `Tool.called()`, `Tool.last_result()`, `Tool.last_call()`
- ✅ **Control**: `Iterations.current()`, `Iterations.exceeded()`, `Stop.requested()`

### CLI Integration
- ✅ Route based on `class: LuaDSL` field
- ✅ `plexus procedure run --yaml workflow.yaml` (script-like execution)
- ✅ Standalone procedures (no scorecard/score required)
- ✅ Custom stages from YAML (not hard-coded SOP stages)
- ✅ No automatic graph node creation

### Architecture
- ✅ Parallel system (coexists with SOP Agent)
- ✅ Clean separation (Lua runtime independent)
- ✅ MCP tool integration
- ✅ LangChain agent execution
- ✅ Chat session logging (all messages recorded to API)
- ✅ Queue-based recording (sync Lua → async recording)

---

## Phase 2: Template System (PLANNED 📋)

### Multi-Namespace Variables
- ⏳ `{params.score_id}` - Input parameters
- ⏳ `{context.current_config}` - Runtime context
- ⏳ `{state.hypotheses_filed}` - Mutable state
- ⏳ `{env.OPENAI_API_KEY}` - Environment variables
- ⏳ `{prepared.file_contents}` - Prepare hook output
- ⏳ `{input.topic}` - Sub-agent input args

### Prepare Hooks
- ⏳ Execute before each agent turn
- ⏳ Dynamic context injection
- ⏳ Access to params, state, input
- ⏳ Return values available as `{prepared.*}`

### Guards
- ⏳ Validation functions for sub-agents
- ⏳ Pre-execution checks
- ⏳ Error handling

---

## Phase 3: Sub-Agents (PLANNED 📋)

### Core Sub-Agent System
- ⏳ Context isolation (parent doesn't see sub-agent conversation)
- ⏳ Sub-agents as tools
- ⏳ `SubAgent.run(name, args)` primitive
- ⏳ Return prompt injection
- ⏳ Error prompt injection
- ⏳ Max depth limits

### Recursion Support
- ⏳ Self-referential sub-agents
- ⏳ Depth tracking
- ⏳ Circular dependency detection

---

## Phase 4: Async Sub-Agents (PLANNED 📋)

### Async Execution
- ⏳ `SubAgent.spawn_async(name, args)` - Non-blocking spawn
- ⏳ `SubAgent.wait(handle)` - Block until complete
- ⏳ `SubAgent.wait_any(handles)` - First to complete
- ⏳ `SubAgent.wait_all(handles)` - All complete
- ⏳ `SubAgent.is_complete(handle)` - Poll status
- ⏳ `SubAgent.status(handle)` - Get progress (status_prompt)
- ⏳ `SubAgent.inject(handle, message)` - Send guidance
- ⏳ `SubAgent.cancel(handle)` - Abort execution

### Checkpointing
- ⏳ Periodic state saves
- ⏳ Recovery from failures
- ⏳ `checkpoint_interval` config

---

## Phase 5: Conversation Filters (PLANNED 📋)

### Built-in Filters
- ⏳ `StandardFilter` - Full history with token limit
- ⏳ `TokenBudget` - Fit within limit, summarize as needed
- ⏳ `LimitToolResults` - Keep only last N tool results
- ⏳ `SummarizeOlderThan` - Summarize messages older than N
- ⏳ `ManagerFilter` - Excludes tool messages
- ⏳ `SlidingWindow` - Keep only last N messages
- ⏳ `ComposedFilter` - Chain multiple filters

---

## Phase 6: Additional Primitives (PLANNED 📋)

### Session Management
- ⏳ `Session.append()`, `Session.inject_system()`, `Session.clear()`
- ⏳ `Session.load_from_node()`, `Session.save_to_node()`

### Stage Control
- ⏳ `Stage.set()`, `Stage.advance()`, `Stage.is()`, `Stage.history()`

### Graph Operations
- ⏳ `GraphNode.root()`, `GraphNode.current()`, `GraphNode.create()`
- ⏳ Node traversal and metadata

### Query Operations
- ⏳ `Query.scorecards_with_feedback()`, `Query.scores_for_scorecard()`
- ⏳ `Query.feedback_summary()`, `Query.evaluations()`

### Procedure Spawning
- ⏳ `Procedure.spawn()`, `Procedure.wait()`, `Procedure.spawn_and_wait()`

### File Operations
- ⏳ `File.read()`, `File.write()`, `File.exists()`, `File.size()`

### Utilities
- ⏳ `Log.debug/info/warn/error()`, `Retry.with_backoff()`, `Sleep()`
- ⏳ `Json.encode/decode()`, `Docs.load()`

---

## Testing & Examples

### Completed
- ✅ Example 1: Simple ReAct loop
- ✅ Unit tests for all Phase 1 primitives
- ✅ Integration with existing CLI

### Planned
- ⏳ Example 2: Manager-Worker coordination
- ⏳ Example 3: Sub-agent specialization
- ⏳ Example 4: Recursive problem decomposition
- ⏳ Example 5: Dynamic context injection
- ⏳ Example 6: Parallel async sub-agents
- ⏳ Example 7: Linear pipeline
- ⏳ Example 8: Batch processing with concurrency

---

## Known Issues / Notes

1. **Graph Nodes**: Only created when Lua code explicitly requests them (not automatic) ✅
2. **Task Stages**: Custom stages from YAML work correctly ✅
3. **MCP Integration**: Fixed import path for `create_procedure_mcp_server()` ✅
4. **Routing**: Lua DSL procedures properly detected and routed ✅

---

## Architecture Decisions

- **Parallel System**: Coexists with SOP Agent, no migration required
- **Capitalized Primitives**: Lua convention (looks like classes)
- **Agent-Centric**: Each YAML agent becomes a Lua primitive
- **Sandboxed**: No file I/O without explicit primitives
- **Script-Like UX**: `plexus procedure run --yaml` feels like running a script

---

## Language Stability

**Current Assessment**: Language design is sound. All Phase 1 features implemented without requiring design changes. Examples from spec work as written. No committee updates needed at this time.
