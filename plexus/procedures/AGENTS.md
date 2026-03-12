# Plexus Procedure DSL - Quick Reference

> **📖 Complete Specification**: See [DSL_SPECIFICATION.md](./DSL_SPECIFICATION.md) for the full technical specification.

This document provides a token-efficient overview of the Plexus Procedure DSL for AI coding agents.

## What Is It?

A configuration-based system for defining agentic workflows that combines:
- **Declarative YAML** → Define agents, tools, parameters, outputs
- **Embedded Lua** → Orchestrate workflow control flow
- **High-level Primitives** → `Worker.turn()`, `Human.approve()`, etc. hide LLM mechanics
- **Human-in-the-Loop** → First-class support for approval, input, review
- **Idempotent Execution** → Resume-friendly with checkpoint replay

## Quick Example

```yaml
name: content_reviewer
version: 4.0.0
class: LuaDSL

params:
  document: { type: string, required: true }

outputs:
  approved: { type: boolean, required: true }

agents:
  reviewer:
    system_prompt: "Review this document: {params.document}"
    tools: [analyze, done]

workflow: |
  -- AI reviews
  repeat
    Reviewer.turn()
  until Tool.called("done")

  -- Human approves (BLOCKS until response)
  local approved = Human.approve({
    message = "Approve this document?",
    timeout = 3600,
    default = false
  })

  return {approved = approved}
```

## Document Structure

```yaml
name: procedure_name
version: 4.0.0
class: LuaDSL
description: "..."

params:           # Input schema (validated before execution)
  param_name: { type: string, required: true }

outputs:          # Output schema (validated after execution)
  result_name: { type: string, required: true }

agents:           # Define AI workers
  worker_name:
    system_prompt: "..."
    tools: [tool1, tool2]

stages:           # Optional stage tracking
  - stage_1
  - stage_2

workflow: |       # Lua orchestration code
  -- Your code here
```

## Key Primitives

### Agent Operations
```lua
Worker.turn()                    -- Execute one agent turn
Worker.turn({inject = "..."})    -- Inject context for this turn
```

### Human Interaction (HITL)
```lua
-- Blocking (waits for human response)
approved = Human.approve({message = "...", timeout = 3600, default = false})
text = Human.input({message = "...", timeout = 1800})
review = Human.review({message = "...", artifact = content})

-- Non-blocking (fire and forget)
Human.notify({message = "Starting phase 2", level = "info"})
System.alert({message = "Error threshold exceeded", level = "warning"})
```

### State Management
```lua
State.set("key", value)
State.get("key")
State.get("key", default_value)
State.all()                      -- Get all state as table
```

### Control Flow
```lua
Tool.called("done")              -- Check if tool was called
Tool.last_call("done").args      -- Get tool call arguments
Iterations.current()             -- Current iteration count
Iterations.exceeded(10)          -- Check if limit exceeded
Stop.requested()                 -- Check if stop was requested
```

### Stages
```lua
Stage.set("processing")
Stage.current()
Stage.is("processing")           -- Boolean check
```

## Message Classification

Every chat message has a `humanInteraction` field that controls visibility:

| Type | Visible to Human? | Blocks Execution? |
|------|-------------------|-------------------|
| `INTERNAL` | No (agent reasoning, tool calls) | No |
| `CHAT` / `CHAT_ASSISTANT` | Yes (conversational) | No |
| `NOTIFICATION` | Yes (status updates) | No |
| `ALERT_*` | Yes (system alerts) | No |
| `PENDING_APPROVAL` | Yes (waiting for yes/no) | Yes |
| `PENDING_INPUT` | Yes (waiting for text) | Yes |
| `PENDING_REVIEW` | Yes (waiting for review) | Yes |
| `RESPONSE` | Yes (human's answer) | No |

**Default behavior:**
- Agent internal messages (system prompts, turns, tool calls) → `INTERNAL`
- Human.notify() → `NOTIFICATION`
- Human.approve/input/review() → `PENDING_*`

## Execution Contexts

Procedures run in two execution contexts (same code, different backends):

### Local Context (Development)
- Checkpoints stored in database
- HITL creates `PENDING_*` message and exits process
- Resume via `plexus procedure resume <id>` when human responds
- Manual or polling-based resume

### Lambda Durable Context (Production)
- Native AWS Lambda Durable Functions
- HITL uses Lambda callbacks (zero compute cost while waiting)
- Automatic suspend/resume
- Executions can span up to 1 year

**Same Lua code works in both contexts!** The ExecutionContext abstraction handles the differences.

## Common Patterns

### Basic Agent Loop
```lua
repeat
  Worker.turn()
until Tool.called("done") or Iterations.exceeded(10)
```

### Multi-Agent Sequential
```lua
-- Researcher gathers data
repeat
  Researcher.turn()
until Tool.called("done")
local research = Tool.last_call("done").args.reason

-- Analyst processes it
Analyst.turn({inject = "Analyze this: " .. research})
repeat
  Analyst.turn()
until Tool.called("done")
```

### HITL Approval Gate
```lua
-- Do work
local result = generate_report()

-- Ask human
local approved = Human.approve({
  message = "Publish this report?",
  context = {preview = result},
  timeout = 3600,
  default = false
})

if approved then
  publish(result)
end
```

### Progress Notifications
```lua
for i, item in ipairs(items) do
  process(item)

  if i % 100 == 0 then
    Human.notify({
      message = "Progress: " .. i .. "/" .. #items,
      level = "info"
    })
  end
end
```

## Idempotent Execution

Procedures can be run multiple times safely:

1. **Checkpoints**: Each significant operation (agent turn, HITL call) creates a checkpoint
2. **Replay**: On resume, completed checkpoints return stored results immediately
3. **Resume**: When PENDING_* message gets RESPONSE, rerun procedure → skips completed work, continues from checkpoint

```lua
-- First run: Executes LLM call, stores result
response = Worker.turn()  -- Checkpoint created

-- Still first run: Blocks here, exits
approved = Human.approve({message = "Continue?"})  -- Creates PENDING_APPROVAL, exits

-- [Human responds in UI]

-- Second run (resume): Replays checkpoint, continues
response = Worker.turn()  -- Returns stored result instantly
approved = Human.approve({message = "Continue?"})  -- Finds RESPONSE, returns value
-- Continues to next code...
```

## Working Examples

See `/plexus/procedures/` for working examples:
- `limerick_writer.yaml` - Basic single-agent loop
- `creative_writer.yaml` - Multi-agent sequential pipeline (3 agents)

## Reference Files

- **DSL_SPECIFICATION.md** - Complete technical specification (~65KB, comprehensive)
- **README.md** - Working examples with instructions
- **EXAMPLE_OUTPUT.md** - Actual execution output showing message flow
- **limerick_writer.yaml** - Basic example
- **creative_writer.yaml** - Multi-agent example

## CLI Commands

```bash
# Run a procedure
plexus procedure run --yaml path/to/procedure.yaml
plexus procedure run <procedure-id>

# Resume procedures (for HITL workflows)
plexus procedure resume <procedure-id>      # Resume single
plexus procedure resume-all                 # Resume all with responses
plexus procedure watch --interval 10s       # Polling daemon

# List and inspect
plexus procedure list
plexus procedure get <procedure-id>
```

## When to Read the Full Spec

Read [DSL_SPECIFICATION.md](./DSL_SPECIFICATION.md) when you need:
- Complete primitive API reference
- Detailed HITL patterns and examples
- Execution context implementation details
- Advanced features (async, recursion, filters, hooks)
- Migration guides from v3
- Comprehensive examples with all features

This quick reference covers ~80% of common use cases. For the other 20%, consult the full spec.
