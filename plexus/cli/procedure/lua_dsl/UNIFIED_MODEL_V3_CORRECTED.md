# Lua DSL v3: Unified Procedure Model (CORRECTED)

**Status:** Committee Correction Applied
**Date:** 2025-12-03
**Correction:** Implementation team misunderstood directive - reverted to `params:` (Plexus standard)

---

## Committee Correction

The implementation team initially misunderstood the committee's directive and introduced `inputs:` as a new keyword. This was incorrect.

### What Was Wrong:
- ❌ Introduced `inputs:` keyword
- ❌ Deprecated `params:` with warnings
- ❌ Created confusion with parallel concepts

### What Is Correct:
- ✅ **KEEP `params:`** - This is the Plexus standard
- ✅ **ADD `outputs:`** - Schema validation (correct)
- ✅ **Future: Rename `sub_agents:` → `procedures:`** (Phase 3)

---

## The ACTUAL v3 Unified Model

### Core Principle
**A procedure is a procedure.** Use Plexus standard `params:` everywhere. Don't invent new keywords.

### Correct v3 Syntax

```yaml
name: limerick_writer_v3
version: 3.0.0
class: LuaDSL

# PARAMS - Plexus standard (DO NOT change to inputs:)
params:
  topic:
    type: string
    required: true
    default: "neurosymbolic AI"

# OUTPUTS - New feature (correct addition)
outputs:
  limerick:
    type: string
    required: true
  node_id:
    type: string
    required: true
  success:
    type: boolean
    required: true

agents:
  poet:
    system_prompt: |
      Write a limerick about {params.topic}.
      # Output schema automatically injected here

    tools:
      - done

workflow: |
  repeat
    Poet.turn()
  until Tool.called("done")

  local limerick = Tool.last_call("done").args.reason
  local node = GraphNode.create(limerick, {type = "poem"})

  return {
    limerick = limerick,
    node_id = node.id,
    success = true
  }
```

---

## What v3 Actually Changes

### ✅ What We Added (Correct)

1. **`outputs:` Schema** - Validated return values
2. **Schema Injection** - Output format shown to LLM
3. **GraphNode Primitive** - Tree-based storage
4. **Type Validation** - Runtime checks

### ❌ What We Initially Did Wrong (Now Fixed)

1. ~~Introduced `inputs:` keyword~~ → REVERTED
2. ~~Deprecated `params:`~~ → RESTORED
3. ~~Changed template variables to `{inputs.x}`~~ → BACK TO `{params.x}`

---

## Terminology Table (Corrected)

| Feature | v2 | v3 (Actual) | Notes |
|---------|----|----|-------|
| Parameter schema | `params:` | `params:` | **NO CHANGE** - Plexus standard |
| Template vars | `{params.x}` | `{params.x}` | **NO CHANGE** |
| Output schema | *(none)* | `outputs:` | **NEW** - Added validation |
| Sub-agents | `sub_agents:` | `procedures:` | **FUTURE** - Phase 3 |
| Invocation | *(none)* | `Procedure.*` | **FUTURE** - Phase 3 |

---

## Implementation Status

### ✅ Completed (Correct Features)

1. **Output Schema Validation**
   - Type checking (string, number, boolean, object, array)
   - Required field enforcement
   - Recursive Lua table conversion
   - Clear error messages

2. **Schema Injection**
   - Appended to agent system prompts
   - Follows LangChain best practices
   - Helps LLM understand expected format

3. **GraphNode Primitive**
   - `GraphNode.create(content, metadata, parent_id)`
   - `GraphNode.root()` and `GraphNode.current()`
   - Enables tree-based knowledge structures

4. **Backward Compatibility Maintained**
   - `params:` works as always (no warnings)
   - Existing procedures unchanged
   - No breaking changes

### ❌ Reverted (Mistaken Features)

1. ~~`inputs:` keyword~~ → Removed
2. ~~Deprecation warnings for `params:`~~ → Removed
3. ~~`{inputs.x}` template variables~~ → Reverted to `{params.x}`

---

## Why `params:` Not `inputs:`

**Plexus Standard:** The entire Plexus system uses `params:` for dynamic parameters. Introducing `inputs:` would:
- Conflict with existing infrastructure
- Create two ways to do the same thing
- Add unnecessary cognitive load
- Break uniformity across the system

**Committee Decision:** Keep Plexus standards. Don't introduce parallel concepts.

---

## Testing Results (Corrected)

```bash
# ✅ Correct usage (params:)
$ plexus procedure run --yaml example_simple_assistant.yaml
✓ Output validation passed for 2 fields
# NO deprecation warnings

# ✅ Output validation works
$ plexus procedure run --yaml limerick_with_schema.yaml
✓ Created graph node
✓ Output validation passed for 4 fields

# ✅ Validation catches errors
$ plexus procedure run --yaml bad_output.yaml
ERROR: Output validation failed:
  Field 'result' should be string, got number
```

---

## What's Next (Phase 3 - Unchanged)

The unified model still needs:

1. **`procedures:` Section** - Inline procedure definitions
   ```yaml
   procedures:
     helper:
       params: ...    # Uses params, not input_schema
       outputs: ...
       agents: ...
       workflow: |
   ```

2. **`Procedure.*` Primitives**
   ```lua
   Procedure.run(name, params)        -- Sync
   Procedure.spawn(name, params)      -- Async
   Procedure.wait(handle)             -- Wait
   ```

3. **Uniform Recursion** - Procedures call procedures
4. **Depth Limits** - `max_depth: 5`
5. **Status/Error/Return Prompts** - Summarization

---

## Files Modified (Corrected)

### Reverted Changes
1. `yaml_parser.py` - Removed `_normalize_params_to_inputs()`, restored `_validate_params()`
2. `runtime.py` - Back to `params:` only (no `inputs:` support)
3. `examples/*.yaml` - Changed back to `params:` and `{params.x}`

### Kept Changes (Correct)
1. `output_validator.py` - Schema validation (correct)
2. `primitives/graph.py` - GraphNode primitive (correct)
3. `runtime.py` - Schema injection into prompts (correct)

---

## Apology and Correction

The implementation team apologizes for misunderstanding the committee's directive. We incorrectly introduced `inputs:` when the committee wanted to:
- Keep `params:` (Plexus standard)
- Add `outputs:` (schema validation)
- Focus on `sub_agents:` → `procedures:` rename (Phase 3)

All incorrect changes have been reverted. The system now correctly uses:
- `params:` for inputs (Plexus standard)
- `outputs:` for validated returns (new feature)
- `{params.x}` for templates (unchanged)

---

## Committee Approval

✅ **Correction Applied**
✅ **`params:` Restored as Plexus Standard**
✅ **`outputs:` Feature Retained (Correct)**
✅ **Ready for Phase 3 with Correct Foundation**

---

**End of Corrected v3 Documentation**
