---
name: plexus-score-code-editor
description: Edit and update the Tactus DSL code for a Plexus scorecard score. Covers the modern ClassifyProcedure style, the pull/push workflow, and key patterns and pitfalls.
---

## Instructions

This skill helps edit the `code:` field of a Plexus score configuration. Score code is written in the **Tactus DSL** (a Lua-based domain-specific language). The goal is almost always to use the modern standard patterns — not to write arbitrary Lua.

**Before making any code changes**, use the Plexus documentation tool to understand the DSL constructs involved. This is not optional — the DSL has specific semantics that are easy to get wrong.

After any code change you must push a new version and verify the version was created with the correct content.

---

## Workflow

### 1. Understand the score

Use `plexus_score_info` to retrieve the current champion version code. Read it carefully. Understand:
- What class is it? (`TactusScore` is the standard)
- What DSL constructs does it use? (`ClassifyProcedure`, `Procedure`, `Classify`, `Agent`, etc.)
- What model does it use? What metadata does it access?

### 2. Read the documentation

Use `get_plexus_documentation` to look up any DSL constructs you will be touching. Key topics:
- `ClassifyProcedure` — single-step classification with system_message + user_message
- `Classify` — lower-level classification primitive
- `Procedure` — raw procedure with custom run function
- `default_model` — procedure-level model directive
- `field` — input/output field declarations
- `metadata` — how to access call metadata in templates

Do not skip this step. The DSL has quirks (e.g., `system_message` is static, `user_message` is a Jinja2 template; `ClassifyProcedure` classes must be a Lua table).

### 3. Pull the local file (optional)

Use `plexus_score_pull` to get the current champion YAML to a local file. This gives you a working copy to edit. Alternatively, you can pass the full updated YAML content directly to `plexus_score_update`.

### 4. Edit the code

Make targeted changes. See the **Patterns** section below.

### 5. Push the new version

Use `plexus_score_push` (if you edited the local file) or `plexus_score_update` (to pass code directly). Provide a concise `version_note` describing what changed and why.

After pushing, call `plexus_score_info` with the new `version_id` to verify the version was created with the correct code (and guidelines if applicable).

---

## The Modern Code Style

The preferred pattern for a classification score is `ClassifyProcedure`. Use this unless there is a specific reason not to.

```lua
default_model "openai/gpt-5.4-nano"

ClassifyProcedure {
  classes = {"Yes", "No"},          -- Lua table of valid class strings

  system_message = [[
  You are a QA analyst evaluating...

  CRITICAL: The final line of your response must be exactly YES or exactly NO.

  [evaluation rules...]

  Provide brief reasoning, then YES or NO on the final line.
  ]],

  user_message = [[
  [Context for this specific call]

  {% if metadata.schools %}
  {% for school in metadata.schools %}
  {{ loop.index }}. School: {{ school.school_id or "" }}
     Modality: {{ school.modality or "" }}
  {% endfor %}
  {% else %}
  (No school metadata available)
  {% endif %}

  <transcript>
  {{ text }}
  </transcript>

  [Instructions for the model]
  ]]
}
```

### Key rules for ClassifyProcedure

- `system_message` is **static** — no template variables. Put all dynamic content in `user_message`.
- `user_message` is rendered as a **Jinja2 template**. Available variables: `{{ text }}`, `{{ metadata.<field> }}`, `{% for ... in metadata.schools %}`, `{{ results }}`.
- `classes` must be a **Lua table** (`{"Yes", "No"}`), not a Lua set or array.
- `default_model` must be declared **before** `ClassifyProcedure`, at the top of the code block.
- The YAML key is `code:`, not `tactus_code:` (the old deprecated key).
- `valid_classes` in the YAML header must match the classes in the Lua code.

### When to use ClassifyProcedure vs raw Procedure

Use `ClassifyProcedure` when:
- The score makes a single Yes/No (or Yes/No/NA) classification
- All needed context fits in the user_message template
- No multi-step logic, branching, or loop over schools is needed in Lua

Use raw `Procedure { run = function(input) ... end }` + `Classify{}` when:
- The score needs conditional logic before classifying
- Multiple sequential LLM calls are needed
- The classification depends on intermediate computed results

### Metadata access in user_message

Metadata is accessed via Jinja2 in `user_message`:
- `{{ metadata.schools }}` — array of school objects
- `{{ school.school_id }}` — school identifier (may include location or modality keywords)
- `{{ school.modality }}` — campus/online/hybrid
- `{{ school.origin }}` — portal type (e.g., "PEC Portal", "PEC 1")
- `{{ school.L1_SubjectName }}` — program name

Use `{{ school.field or "fallback" }}` to handle missing values. Jinja2 `or` returns the right-hand side when the left is falsy (None/null/empty).

---

## YAML Structure

A complete score YAML looks like:

```yaml
name: Score Name
key: score-key
id: '12345'
version: <uuid>        # current version ID (informational)
description: What this score evaluates
class: TactusScore
valid_classes:
  - 'Yes'
  - 'No'

code: |-
  default_model "openai/gpt-5.4-nano"

  ClassifyProcedure {
    ...
  }
```

The `version:` field in the local YAML is informational — pushing always creates a new version regardless.

---

## Common Conversions

### Agent{} or tactus_code: → ClassifyProcedure

Old pattern (do not use):
```yaml
tactus_code: |-
  Agent {
    model_provider = "openai",
    model_name = "gpt-4o",
    max_tokens = 1000,
    ...
  }
```

New pattern:
```yaml
code: |-
  default_model "openai/gpt-5.4-nano"

  ClassifyProcedure {
    classes = {"Yes", "No"},
    system_message = [[ ... ]],
    user_message = [[ ... ]]
  }
```

### Procedure + per-school Classify loop → ClassifyProcedure

When the old code loops over `metadata.schools` making one `Classify{}` call per school, replace with a single `ClassifyProcedure` that lists all schools in the `user_message` Jinja2 template and makes one LLM call for the whole transcript.

### raw Procedure + Classify → ClassifyProcedure

When the old code has:
```lua
Procedure {
  input = { text = ..., metadata = ... },
  output = { value = ..., explanation = ... },
  run = function(input)
    local user_message = build_user_message(input)
    local result = Classify { classes = ..., prompt = PROMPT, input = user_message }
    return { value = result.value, explanation = result.explanation }
  end
}
```
Replace the whole block with a `ClassifyProcedure`, moving the dynamic user message construction into the Jinja2 `user_message` template.

---

## Pitfalls

- **Wrong model IDs**: Use `"openai/gpt-5.4-nano"` — the provider prefix is required. `"gpt-5.4-nano"` alone will fail.
- **`tactus_code:` is deprecated**: Always use `code:`.
- **system_message with template vars**: Variables like `{{ text }}` are silently ignored in `system_message`. Move dynamic content to `user_message`.
- **NA class**: If the score can abstain (e.g., no schools in metadata), add `"NA"` to both `classes` and `valid_classes`, and instruct the model in `system_message` to output NA when applicable.
- **Guidelines file naming**: The guidelines file must be named `<Score Name>.md` (same base name as the `.yaml` file, `.md` extension) for `plexus_score_push` to pick it up. A file named `<Score Name> guidelines.md` will be silently ignored.
- **isFeatured**: Versions pushed via `plexus_score_push` are created as non-featured drafts. The champion is not automatically updated — promotion is a separate step.
- **LLMModel registry collision**: When using raw `Classify{}` in a Lua loop, each call creates a `LLMModel` internally. The Tactus stdlib handles this with a counter to avoid name collisions — but this is a known historical bug source. Prefer `ClassifyProcedure` (single call) to avoid the loop entirely.

---

## Tools Reference

| Task | Tool |
|------|------|
| Look up DSL constructs | `get_plexus_documentation` |
| Get current score code | `plexus_score_info` with optional `version_id` |
| Pull champion to local file | `plexus_score_pull` |
| Push local file as new version | `plexus_score_push` |
| Push code content directly | `plexus_score_update` with `code=` parameter |
| Verify the pushed version | `plexus_score_info` with the new `version_id` |
