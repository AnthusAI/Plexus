# TactusScore YAML Guide

This document explains how to implement shared score-design patterns in
`TactusScore`. Use `score-yaml-format.md` for the high-level pattern catalog. Use
this file for the Tactus-specific "how".

## When TactusScore Fits

Use `TactusScore` when the score logic is easier to express as imperative code than
as a fixed graph. It is the right tool for:

- loops over variable-length metadata lists
- multi-pass logic with explicit early returns
- custom deterministic aggregation
- workflows that mix LLM calls with programmatic logic

If the score naturally reads like "check each school" or "gate, then branch, then
aggregate", Tactus is usually the cleanest fit.

## YAML Wrapper

The Plexus YAML shell still defines the score metadata. The score code lives under
`code:`. Do not use the deprecated `tactus_code:` field for new work.

```yaml
name: Example Score
class: TactusScore
valid_classes:
  - "Yes"
  - "No"

code: |-
  default_model "openai/gpt-5.4-nano"

  ClassifyProcedure {
    classes = {"Yes", "No"},
    system_message = [[
    You are evaluating whether the requirement was met.
    ]],
    user_message = [[
    Transcript:
    {{ text }}
    ]]
  }
```

Keep `valid_classes` aligned with the Lua-side classes.

## Preferred Style: `ClassifyProcedure`

Use `ClassifyProcedure` for a single classification pass whenever possible.

Rules:

- Put `default_model "provider/model"` at the top of the code block.
- `classes` is a Lua table such as `{"Yes", "No"}`.
- `system_message` is static text.
- `user_message` is the dynamic Jinja2 template.
- Use `code:`, not `tactus_code:`.

Variables available in `user_message` typically include:

- `{{ text }}`
- `{{ metadata.<field> }}`
- `{{ results["Other Score"].value }}`

`ClassifyProcedure` is the default because it keeps the score easy to diff, easy for
the optimizer to rewrite, and easy to test.

## Recipe: Applicability Gate Before the Yes/No Classifier

This is the preferred `NA` pattern in Tactus. Use raw `Procedure` so you can make a
cheap first pass, return `"NA"` immediately when out of scope, and keep the main
classifier purely binary.

```yaml
valid_classes:
  - "Yes"
  - "No"
  - "NA"

code: |-
  default_model "openai/gpt-5.4-nano"

  Procedure {
    input = {
      text = field.string{required = true},
      metadata = field.object{}
    },
    output = {
      value = field.string{},
      explanation = field.string{}
    },
    function(input)
      local applicability = Classify {
        classes = {"Applicable", "NA"},
        model = "openai/gpt-5.4-nano",
        prompt = [[
        Decide whether this item is in scope for the check.
        Return Applicable or NA.
        ]],
        input = input.text
      }

      if applicability.value == "NA" then
        return {
          value = "NA",
          explanation = applicability.explanation or "Out of scope."
        }
      end

      local decision = Classify {
        classes = {"Yes", "No"},
        model = "openai/gpt-5.4-nano",
        prompt = [[
        Evaluate only the applicable Yes/No requirement.
        Return Yes or No.
        ]],
        input = input.text
      }

      return {
        value = decision.value,
        explanation = decision.explanation or ""
      }
    end
  }
```

The important design rule is the same as in LangGraph: the second pass should not
carry `NA` logic in its prompt.

## Recipe: Extraction Before Final Judgment

Use raw `Procedure` plus `Classify` when the score should first extract evidence and
only then decide the label.

```yaml
code: |-
  default_model "openai/gpt-5.4-nano"

  Procedure {
    input = {
      text = field.string{required = true}
    },
    output = {
      value = field.string{},
      explanation = field.string{}
    },
    function(input)
      local evidence = Classify {
        classes = {"FOUND", "NOT_FOUND"},
        model = "openai/gpt-5.4-nano",
        prompt = [[
        Find the local exchange where the agent asks for consent.
        Return FOUND or NOT_FOUND and explain what you found.
        ]],
        input = input.text
      }

      local decision = Classify {
        classes = {"Yes", "No"},
        model = "openai/gpt-5.4-nano",
        prompt = [[
        Decide whether the extracted evidence satisfies the business rule.
        ]],
        input = (evidence.explanation or "") .. "\n\nTranscript:\n" .. input.text
      }

      return {
        value = decision.value,
        explanation = decision.explanation or ""
      }
    end
  }
```

This is useful when the optimizer learns that the problem is evidence localization,
not the final rubric.

## Recipe: Loop Over Entities, Then Aggregate Deterministically

This is where Tactus usually wins over LangGraph. If the item metadata contains a
variable-length list, loop over it directly.

```yaml
code: |-
  default_model "openai/gpt-5.4-nano"

  Procedure {
    input = {
      text = field.string{required = true},
      metadata = field.object{}
    },
    output = {
      value = field.string{},
      explanation = field.string{}
    },
    function(input)
      local schools = (input.metadata and input.metadata.schools) or {}
      local failures = {}

      for _, school in ipairs(schools) do
        local result = Classify {
          classes = {"Yes", "No"},
          model = "openai/gpt-5.4-nano",
          prompt = [[
          Evaluate this school only. Return No if any required element is missing.
          ]],
          input =
            "School: " .. tostring(school.school_id or "") ..
            "\nProgram: " .. tostring(school.L1_SubjectName or "") ..
            "\nModality: " .. tostring(school.modality or "") ..
            "\n\nTranscript:\n" .. input.text
        }

        if result.value ~= "Yes" then
          table.insert(
            failures,
            tostring(school.school_id or "unknown school") .. ": " .. (result.explanation or "failed")
          )
        end
      end

      if #failures > 0 then
        return { value = "No", explanation = table.concat(failures, "; ") }
      end

      return { value = "Yes", explanation = "All schools passed." }
    end
  }
```

Use this pattern for per-school, per-medication, per-offer, or per-disclosure checks.

## Recipe: Deterministic Aggregation Without Another LLM Call

If the rule is already deterministic, keep it in Lua. Common examples:

- any failed sub-check means overall `"No"`
- at least one applicable item must pass
- if no entities exist, return `"NA"`
- if the gate fails, stop immediately

Do not spend another model call on logic the runtime can express directly.

## When to Drop Down From `ClassifyProcedure` to Raw `Procedure`

Stay with `ClassifyProcedure` unless you need one of these:

- multiple sequential classification passes
- explicit branching or early returns
- loops over metadata arrays
- custom aggregation rules
- advanced primitives like `Agent` or first-class `Model` blocks

That boundary matters because most score optimizations are easier when the code is
still a single standard classifier definition.

## Advanced Primitives in Score Code

Tactus supports more than `ClassifyProcedure`, but use the broader DSL only when the
score needs it.

### `Classify`

Use this inside raw `Procedure` when you want explicit control over several
classification passes.

### `Procedure`

Use this when the score needs imperative orchestration, loops, or early returns.

### `Model`

Use a named `Model` block when the same model configuration should be reused across
multiple calls in the same score.

### `Agent`

Use an `Agent` only when the score truly needs tool-using or multi-turn behavior.
Most scores do not. A standard classifier is easier to optimize and easier to test.

## Metadata, Results, and Templates

In `ClassifyProcedure`, put dynamic content in `user_message`, not in
`system_message`.

Typical patterns:

- list schools from `metadata.schools`
- include prior score results from `results[...]`
- render only the fields the classifier actually needs

If a dynamic list is simple and read-only, Jinja2 in `user_message` is enough. If
the list needs iteration plus decision logic, use raw Lua in `Procedure`.

## Practical Guidance

- Prefer `ClassifyProcedure` for single-pass scores.
- Prefer raw `Procedure` for loops, gates, and aggregation.
- Keep `NA` as a separate applicability decision whenever possible.
- Keep deterministic rules in Lua.
- Keep `valid_classes` aligned with the code.
- Treat `tactus_code:` as legacy configuration to be migrated, not copied.
