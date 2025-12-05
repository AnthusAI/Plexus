# Lua DSL v3: Unified Procedure Model

**Status:** Phase 1 Complete - Unified Terminology Implemented
**Date:** 2025-12-03
**Committee Decision:** Approved

---

## Committee Decision Summary

The committee (Ryan + Claude) approved the **Unified Procedure Model** where procedures and sub-agents are the same construct. This eliminates artificial distinctions and enables natural composition and recursion.

---

## What Changed in v3

### Terminology Updates

| v2 (Deprecated) | v3 (Current) | Reason |
|-----------------|--------------|--------|
| `params:` | `inputs:` | Symmetry with `outputs:`, matches sub-agent model |
| `{params.topic}` | `{inputs.topic}` | Template variable consistency |
| `sub_agents:` | `procedures:` | Not yet implemented (Phase 3) |
| `SubAgent.*` | `Procedure.*` | Not yet implemented (Phase 3) |

### Backward Compatibility

- **`params:` still works** with deprecation warning
- **Templates support both** `{inputs.x}` and `{params.x}`
- **Gradual migration** - no breaking changes

---

## Current v3 Syntax

### Complete Example

```yaml
name: limerick_writer_v3
version: 3.0.0
class: LuaDSL
description: "Unified model example"

# INPUTS - Same structure everywhere (formerly params)
inputs:
  topic:
    type: string
    required: true
    default: "neurosymbolic AI"
    description: "The topic for the limerick"

# OUTPUTS - Validated structured results
outputs:
  limerick:
    type: string
    required: true
    description: "The generated limerick text"
  node_id:
    type: string
    required: true
    description: "Graph node ID containing the limerick"
  success:
    type: boolean
    required: true
    description: "Whether creation was successful"

# AGENTS - LLM-powered agents with tools
agents:
  poet:
    system_prompt: |
      You are a creative poet.
      Your task: Write a limerick about {inputs.topic}.

      # Output schema is automatically injected here

    initial_message: |
      Please write a limerick about {inputs.topic}.

    tools:
      - done

# STAGES - Custom workflow stages
stages:
  - writing
  - recording
  - complete

# WORKFLOW - Lua orchestration code
workflow: |
  State.set("stage", "writing")

  repeat
    Poet.turn()
  until Tool.called("done") or Iterations.exceeded(10)

  if Tool.called("done") then
    State.set("stage", "recording")
    local limerick = Tool.last_call("done").args.reason
    local node = GraphNode.create(limerick, {type = "poem"})

    State.set("stage", "complete")

    return {
      limerick = limerick,
      node_id = node.id,
      success = true
    }
  end

  return {
    limerick = "",
    node_id = "",
    success = false
  }
```

---

## Key Features Implemented

### 1. ✅ Output Schema Validation

**What it does:**
- Validates Lua workflow return values against declared schema
- Checks types (string, number, boolean, object, array)
- Enforces required fields
- Converts Lua tables to Python dicts recursively

**Example:**
```yaml
outputs:
  result:
    type: string
    required: true

workflow: |
  return {
    result = "success"  -- ✓ Validates correctly
  }
```

**Validation error example:**
```lua
return {
  result = 123  -- ✗ Error: should be string, got number
}
```

### 2. ✅ Schema Injection into Agent Prompts

**What it does:**
- Automatically appends output schema to agent system prompts
- Helps LLM understand expected output format
- Follows LangChain structured output best practices

**Agent sees:**
```
You are a creative poet...

## Expected Output Format

This workflow must return a structured result with the following fields:

- **limerick** (string) - **REQUIRED**
  The generated limerick text

- **node_id** (string) - **REQUIRED**
  Graph node ID containing the limerick
```

### 3. ✅ Unified Input/Output Model

**Symmetry:**
```yaml
inputs:   # What the procedure needs
  topic: ...

outputs:  # What the procedure returns
  result: ...
```

**Template access:**
```yaml
system_prompt: |
  Your task: {inputs.topic}
```

**Backward compatibility:**
```yaml
params:  # Still works, shows deprecation warning
  topic: ...

system_prompt: |
  {params.topic}  # Still works
  {inputs.topic}  # Preferred
```

---

## What's Next (Phase 3)

The unified model sets the foundation for:

### Inline Procedure Definitions

```yaml
procedures:
  analyzer:
    # Full procedure definition inline
    inputs:
      data: ...
    outputs:
      result: ...
    agents:
      worker: ...
    workflow: |
      -- Same structure as top-level
```

### Procedure Invocation

```lua
-- Sync invocation
local result = Procedure.run("analyzer", {data = "..."})

-- Result is validated against analyzer's outputs schema
print(result.result)  -- Guaranteed to exist
```

### Uniform Recursion

```yaml
name: recursive_solver
inputs:
  problem: ...
outputs:
  solution: ...

workflow: |
  if simple(problem) then
    return solve_directly(problem)
  else
    -- Call self recursively (with depth limit)
    local sub_result = Procedure.run("recursive_solver", {
      problem = simplify(problem)
    })
    return combine(sub_result)
  end
```

### Async Sub-Procedures

```lua
-- Spawn multiple procedures in parallel
local handles = {}
for i = 1, 5 do
  handles[i] = Procedure.spawn("analyzer", {data = dataset[i]})
end

-- Wait for all to complete
local results = Procedure.wait_all(handles)
```

---

## Migration Guide

### For Existing Procedures

**Option 1: Keep as-is (deprecated syntax)**
- `params:` still works
- Shows deprecation warning
- No immediate action needed

**Option 2: Migrate to v3 (recommended)**
```diff
- params:
+ inputs:
    topic:
      type: string

  agents:
    worker:
      system_prompt: |
-       Task: {params.topic}
+       Task: {inputs.topic}
```

### For New Procedures

Always use v3 syntax:
- `inputs:` not `params:`
- `{inputs.x}` not `{params.x}`
- Add `outputs:` schema for validation

---

## Testing Results

### ✅ Backward Compatibility Test
```bash
# Old syntax (params:) still works
plexus procedure run --yaml old_syntax.yaml
# Warning: DEPRECATION: 'params:' is deprecated, use 'inputs:' instead
# ✓ Output validation passed
```

### ✅ New Syntax Test
```bash
# New syntax (inputs:) works without warnings
plexus procedure run --yaml new_syntax.yaml
# ✓ Output validation passed
```

### ✅ Validation Test
```bash
# Wrong output type caught
plexus procedure run --yaml bad_output.yaml
# ERROR: Output validation failed:
#   Field 'result' should be string, got number
```

---

## Architecture Notes

### Why Unify?

1. **Composability** - Procedures are like functions, can call each other
2. **No Special Cases** - Same validation everywhere
3. **Simpler Mental Model** - One concept instead of two
4. **Natural Recursion** - Self-reference just works
5. **Uniform Testing** - Test procedures the same way

### Design Principles

1. **Procedures are procedures** - No distinction between top-level and nested
2. **Backward compatible** - Gradual migration path
3. **Validation everywhere** - Same rules for inputs and outputs
4. **Schema-guided** - LLMs see expected output format

---

## Committee Approval

✅ **Approved by committee (Ryan + Claude)**
✅ **Implementation complete for Phase 1**
✅ **Ready for Phase 3 (sub-agent/procedure invocation)**

---

## Files Modified

1. `plexus/cli/procedure/lua_dsl/yaml_parser.py`
   - Added `_normalize_params_to_inputs()` for backward compat
   - Renamed `_validate_params()` → `_validate_inputs()`
   - Deprecation warnings for `params:`

2. `plexus/cli/procedure/lua_dsl/runtime.py`
   - Template processing supports both `inputs` and `params`
   - Output schema injection into agent prompts
   - Validation of workflow return values

3. `plexus/cli/procedure/lua_dsl/output_validator.py`
   - Recursive Lua table → dict conversion
   - Type checking with clear error messages
   - Required field validation

4. **Examples updated:**
   - `tmp/example_simple_assistant.yaml` → uses `inputs:`
   - `tmp/limerick_with_schema.yaml` → renamed to v3

---

## Next Steps

For **Phase 3** implementation:

1. Add `return_prompt`, `error_prompt`, `status_prompt` fields
2. Implement `procedures:` section for inline definitions
3. Create `Procedure.*` primitives (run, spawn, wait, etc.)
4. Add recursion depth limits
5. Implement async procedure execution
6. Update IMPLEMENTATION_ROADMAP.md with Phase 3 plan

---

**End of v3 Unified Model Documentation**
