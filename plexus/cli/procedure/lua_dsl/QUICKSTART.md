# Lua DSL Quick Start Guide

## How to Run Your First Lua DSL Procedure

### Step 1: Verify Installation

The `lupa` library has already been installed in your py311 conda environment:

```bash
python -c "import lupa; print('lupa installed successfully')"
```

### Step 2: Use the Example YAML

We've created a simple example for you: `example_simple_assistant.yaml`

```yaml
name: simple_assistant
version: 1.0.0
class: LuaDSL  # <-- This routes to the Lua DSL runtime!

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

stages:
  - working
  - complete

workflow: |
  -- Simple ReAct loop
  repeat
    Assistant.turn()
  until Tool.called("done") or Iterations.exceeded(50)

  return {
    completed = Tool.called("done"),
    iterations = Iterations.current()
  }
```

### Step 3: Run Your Workflow

```bash
# Just run it! (Like executing a script)
plexus procedure run --yaml tmp/example_simple_assistant.yaml

# Or with the full path:
plexus procedure run --yaml plexus/cli/procedure/lua_dsl/example_simple_assistant.yaml

# With options:
plexus procedure run --yaml tmp/example_simple_assistant.yaml --dry-run
plexus procedure run -y tmp/example_simple_assistant.yaml --max-iterations 10
```

That's it! No need to create and then run - just point at your YAML and execute.

### Alternative: Run by ID

If you already created a procedure, you can run it by ID:

```bash
# First time: creates the procedure
plexus procedure create --yaml workflow.yaml  # → Returns ID

# Subsequent runs: use the ID
plexus procedure run <procedure-id>
```

## What Happens When You Run It

1. **CLI Command** → `plexus procedure run`
2. **Service Router** → Checks YAML for `class: LuaDSL`
3. **Lua DSL Runtime** → Parses YAML, sets up Lua sandbox
4. **Agent Setup** → Creates LLM with tools bound
5. **Workflow Execution** → Runs your Lua code
6. **Results** → Returns execution summary

## Debugging

### Check if routing works:

Look for this log message:
```
Routing procedure <id> to Lua DSL runtime
```

### View execution logs:

The runtime logs detailed information:
```
LuaDSLRuntime initialized for procedure <id>
Step 1: Parsing YAML configuration
Step 2: Setting up Lua sandbox
Step 3: Initializing primitives
Step 4: Setting up agents
Step 5: Injecting primitives into Lua environment
Step 6: Executing Lua workflow
```

### Common Issues:

**"lupa library not available"**
```bash
/opt/anaconda3/envs/py311/bin/pip install lupa
```

**"No agents defined in configuration"**
- Make sure your YAML has an `agents:` section
- At least one agent must be defined

**"Lua runtime error"**
- Check your Lua syntax in the `workflow:` section
- Common issues: unmatched parentheses, calling undefined primitives

## What's Working

✅ **YAML Parsing** - Validates structure and required fields
✅ **Lua Sandbox** - Secure execution (no file I/O, no OS access)
✅ **State Management** - `State.get/set/increment/append()`
✅ **Agent Execution** - `Assistant.turn()` calls LLM with tools
✅ **Tool Tracking** - `Tool.called()`, `Tool.last_result()`
✅ **Control Flow** - `Iterations.*`, `Stop.*`
✅ **CLI Integration** - Seamless routing based on `class` field

## Next Steps

Want to build more complex workflows? Check out the design spec for:

- **Sub-agents** - Hierarchical agent decomposition
- **Prepare hooks** - Dynamic context injection
- **Template variables** - Multiple namespaces (params, context, state)
- **Conversation filters** - History management
- **Async execution** - Parallel sub-agents

## Examples

We've included several examples:

1. **example_simple_assistant.yaml** - Basic ReAct loop (ready to run!)
2. **test_runtime_basic.py** - Unit tests for primitives

More examples coming as we implement Phase 2 features!

## Need Help?

Check the logs:
```bash
# The procedure run command shows detailed logs
plexus procedure run <id> 2>&1 | grep -i "lua\|routing"
```

Review the architecture:
```bash
cat plexus/cli/procedure/lua_dsl/README.md
```

## Architecture Summary

```
Your YAML (class: LuaDSL)
         │
         ▼
  ProcedureService
         │
         ▼
  Check class field
         │
    ┌────┴────┐
    │ LuaDSL? │ YES
    └────┬────┘
         │
         ▼
   LuaDSLRuntime
         │
    ┌────┴────────────────┐
    │                     │
    │  1. Parse YAML      │
    │  2. Setup Lua       │
    │  3. Inject Prims    │
    │  4. Setup Agents    │
    │  5. Execute         │
    │                     │
    └─────────────────────┘
```

Happy coding! 🎉
