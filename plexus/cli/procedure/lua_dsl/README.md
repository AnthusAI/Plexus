# Lua DSL Runtime for Plexus Procedures

A Lua-based domain-specific language for defining agentic workflows declaratively.

## Quick Start

### 1. Install lupa

```bash
pip install lupa
```

### 2. Create a YAML Workflow

Create a YAML file with `class: LuaDSL`:

```yaml
name: simple_assistant
version: 1.0.0
class: LuaDSL

params:
  task:
    type: string
    default: "Say hello"

agents:
  assistant:
    system_prompt: |
      You are a helpful assistant. Complete this task: {params.task}
      When finished, call the done tool with a summary.

    initial_message: |
      Please begin working on the task.

    tools:
      - done

workflow: |
  -- Simple ReAct loop
  repeat
    Assistant.turn()
  until Tool.called("done") or Iterations.exceeded(10)

  return {
    completed = Tool.called("done"),
    iterations = Iterations.current()
  }
```

### 3. Run It

```bash
# Just run it! (Like executing a script)
plexus procedure run --yaml simple_assistant.yaml

# It creates the procedure and runs it in one step
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Plexus CLI Command                    │
│         plexus procedure run <id>               │
└──────────────────┬──────────────────────────────┘
                   │
         ┌─────────▼──────────┐
         │  ProcedureService  │
         │   run_experiment() │
         └─────────┬──────────┘
                   │
         ┌─────────▼──────────┐
         │  Check YAML class  │
         └─────────┬──────────┘
                   │
      ┌────────────┴────────────┐
      │                         │
┌─────▼─────┐           ┌──────▼──────┐
│  LuaDSL   │           │  SOPAgent   │
│  Runtime  │           │  (existing) │
└───────────┘           └─────────────┘
```

##Components

### Core Files

- **runtime.py** - Main LuaDSLRuntime executor
- **yaml_parser.py** - YAML validation and parsing
- **lua_sandbox.py** - Sandboxed Lua environment
- **procedure_executor.py** - Routes based on class field

### Primitives

Python implementations of Lua-callable operations:

- **agent.py** - `Worker.turn()` - Execute agent with LLM
- **state.py** - `State.get/set/increment/append()` - Mutable state
- **control.py** - `Iterations.*`, `Stop.*` - Flow control
- **tool.py** - `Tool.called/last_result()` - Tool tracking

## Lua Primitives Reference

### Agent Primitives

```lua
-- Execute one agent turn (automatically capitalized from YAML)
local response = Assistant.turn()

-- Access response
print(response.content)           -- Agent's text response
print(#response.tool_calls)       -- Number of tools called

-- Inject context for this turn only
Assistant.turn({inject = "Additional guidance..."})
```

### State Primitives

```lua
-- Get/set state
State.set("count", 0)
local count = State.get("count", 0)  -- With default

-- Increment numeric values
State.increment("hypotheses_filed")
State.increment("score", 10)

-- Append to lists
State.append("nodes_created", node_id)

-- Get all state
local all_state = State.all()
```

### Tool Primitives

```lua
-- Check if tool was called
if Tool.called("done") then
    print("Done!")
end

-- Get last result
local result = Tool.last_result("search")

-- Get full call info
local call = Tool.last_call("search")
print(call.name, call.args, call.result)
```

### Control Primitives

```lua
-- Check iterations
local count = Iterations.current()
if Iterations.exceeded(50) then
    return {error = "Too many iterations"}
end

-- Check stop status
if Stop.requested() then
    print("Stopped: " .. Stop.reason())
    print("Success: " .. tostring(Stop.success()))
end
```

## Example: Simple ReAct Loop

This is Example 1 from the design spec:

```yaml
name: simple_assistant
version: 1.0.0
class: LuaDSL

params:
  task:
    type: string
    required: true

agents:
  assistant:
    system_prompt: "Complete this task: {params.task}"
    initial_message: "Begin working."
    tools:
      - search
      - done

workflow: |
  repeat
    Assistant.turn()
  until Tool.called("done") or Iterations.exceeded(50)

  return {
    completed = Tool.called("done"),
    iterations = Iterations.current()
  }
```

## Testing

Run basic tests:

```bash
cd plexus/cli/procedure/lua_dsl
python test_runtime_basic.py
```

## Roadmap

**Phase 1 (Complete)** ✅
- [x] YAML parser and validator
- [x] Lua sandbox with safety restrictions
- [x] Basic primitives (Agent, State, Tool, Control)
- [x] LuaDSLRuntime executor
- [x] Routing integration with existing system

**Phase 2 (Next)**
- [ ] Template system with multiple namespaces
- [ ] Prepare hooks for dynamic context
- [ ] Sub-agents as tools with isolated contexts
- [ ] Conversation filters
- [ ] Async sub-agent primitives

**Phase 3 (Future)**
- [ ] Tree search primitives
- [ ] Parallel execution
- [ ] Checkpointing and recovery
- [ ] Advanced logging and debugging
