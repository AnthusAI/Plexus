---
id: score-authoring.score-yaml-format
title: Score YAML Format (TactusScore)
summary: Authoring reference for Plexus score YAML configurations. TactusScore is the default and recommended score type.
namespace: score-authoring
status: canonical
disclosure: reference
audience: agent
tags: [score, yaml, authoring, tactus]
related:
  - score-authoring.langgraph-score-yaml-format
  - score-authoring.classifier-interface
  - score-authoring.dataset-yaml-format
  - score-authoring.rubric-memory
---
# TactusScore YAML Configuration

TactusScore is the default and recommended score type for Plexus. It executes Tactus DSL (Lua-based) code for classification. Two patterns exist:

1. **ClassifyProcedure** — single-step classification (most common)
2. **Procedure** — multi-step custom logic with full Lua control

For legacy LangGraphScore configurations, see `score-authoring.langgraph-score-yaml-format`.

## Top-Level YAML Fields

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `name` | string | yes | Score display name |
| `key` | string | no | URL-safe identifier |
| `id` | string | no | Score ID in database |
| `description` | string | no | Human-readable description |
| `class` | string | yes | Must be `TactusScore` |
| `valid_classes` | list | no | Valid output values (validates result) |
| `code` | string | yes | Tactus DSL code block |
| `output` | object | no | Maps procedure output fields to Score.Result fields |
| `version` | string | no | Version UUID (managed by system) |
| `model_provider` | string | no | Identity metadata (model specified in Lua code) |
| `model_name` | string | no | Identity metadata |
| `base_model_name` | string | no | Identity metadata |

## Runtime Parameters (Optional)

These set score-wide defaults. Lua code can override per-call.

| Field | Type | Purpose |
|-------|------|---------|
| `temperature` | float | Sampling temperature |
| `max_tokens` | int | Max response tokens |
| `reasoning_effort` | string | GPT-5-family reasoning control |
| `verbosity` | string | GPT-5-family response verbosity |

---

## Pattern 1: ClassifyProcedure

For single-step classification — the most common pattern. Combines `Procedure` + `Classify` into one declaration.

### Minimal Structure

```yaml
name: "Score Name"
class: TactusScore
valid_classes: ["Yes", "No", "NA"]
code: |-
  default_model "openai/gpt-5.4-nano"

  ClassifyProcedure {
    classes = {"Yes", "No", "NA"},
    system_message = [[
  Classification instructions go here.
  ]],
    user_message = [[
  Evaluate: <transcript>{{ text }}</transcript>
  ]]
  }
```

### ClassifyProcedure Parameters

| Param | Required | Purpose |
|-------|----------|---------|
| `classes` | yes | List of valid classification values |
| `system_message` | yes* | LLM system prompt with classification instructions |
| `user_message` | yes* | Jinja2 template for user message |
| `prompt` | legacy | Alias for user_message (or system prompt in legacy mode) |
| `model` | no | Override model (otherwise uses `default_model`) |
| `temperature` | no | Sampling temperature |
| `max_tokens` | no | Max response tokens |
| `reasoning_effort` | no | Reasoning effort control |
| `verbosity` | no | Response verbosity |
| `max_retries` | no | Retry count on failure |
| `name` | no | Model name (for mocking) |
| `input_field` | no | Input field name (default: "text") |

*Either `system_message` + `user_message`, or `prompt` alone (legacy mode).

### Template Variables in user_message

- `{{ text }}` — the transcript/content being classified
- `{{ metadata.field }}` — metadata fields from the item
- `{{ results }}` — previous score results (for dependency chains)

### Output

ClassifyProcedure automatically returns `{ value, explanation }`. No `output:` mapping needed in YAML.

### Full Example

```yaml
name: "Acknowledges Before Redirecting"
key: "acknowledges-before-redirecting"
description: >-
  When the beneficiary raises a concern, the agent validates it before redirecting.
class: TactusScore
valid_classes:
  - "Yes"
  - "No"
  - "Partially Met"
  - "NA"
code: |-
  default_model "openai/gpt-5.4-nano"

  ClassifyProcedure {
    classes = {"Yes", "No", "Partially Met", "NA"},
    system_message = [[
  You are a QA analyst. Classify the agent behavior.

  Decision criteria:
  - Yes: Agent acknowledges concern before redirecting.
  - No: Agent immediately counters without acknowledging.
  - Partially Met: Acknowledgment is scripted or inconsistent.
  - NA: No objection raised by the beneficiary.

  Return reasoning, then final label on last line.
  ]],
    user_message = [[
  Evaluate the transcript below.

  <transcript>
  {{ text }}
  </transcript>
  ]]
  }
version: 90d96bcf-d85d-4720-a9e8-743106c89273
```

---

## Pattern 2: Procedure (Multi-Step)

For scores requiring custom logic: chaining models, conditional branching, fine-tuned + explainer combos, etc.

### Structure

```yaml
name: "Score Name"
class: TactusScore
code: |-
  Procedure {
    input = {
      text = field.string{required = true}
    },
    output = {
      value = field.string{},
      explanation = field.string{}
    },
    run = function(input)
      -- Custom Lua logic here
      return { value = "Yes", explanation = "reason" }
    end
  }

output:
  value: value
  explanation: explanation
```

### Key Differences from ClassifyProcedure

- Explicit `input`, `output`, and `run` function
- Must define field schemas with `field.string{}`, `field.number{}`, etc.
- `output:` YAML mapping required to wire procedure output to Score.Result
- Full Lua available: variables, conditionals, loops, require()

### Available Primitives Inside Procedure

#### Classify

Single classification call (same engine as ClassifyProcedure):

```lua
local result = Classify {
  classes = {"YES", "NO"},
  model = "openai/gpt-4o-mini",
  temperature = 0.0,
  max_tokens = 16,
  prompt = [[Classification instructions...]],
  input = input.text
}
-- result.value = "YES" or "NO"
-- result.explanation = "..."
```

#### LLM Models

Lower-level model calls for custom prompting:

```lua
local models = require("tactus.models.llm")
local explainer = models.LLMModel {
  name = "my_explainer",
  model = "openai/gpt-4o-mini",
  temperature = 0.2,
  max_tokens = 500,
  prompt = [[System instructions...]]
}

local result = explainer({text = "User prompt here"})
local response = result.output.response or tostring(result.output)
```

#### default_model

Set at top of code block — applies to all Classify/ClassifyProcedure calls that don't specify their own model:

```lua
default_model "openai/gpt-5.4-nano"
```

### Output Mapping

When using `Procedure`, the YAML `output:` section maps procedure return keys to Score.Result fields:

```yaml
output:
  value: value          # Maps procedure's "value" to Score.Result.value
  explanation: explanation  # Maps procedure's "explanation" to Score.Result.explanation
```

### Multi-Step Example

```yaml
name: Pain Points
id: '45342'
class: TactusScore
model_provider: ChatOpenAI
model_name: ft:gpt-4o-mini-2024-07-18:call-criteria:aw-ib-sales-pain-points:BXS9SszP

code: |-
  Procedure {
    input = {
      text = field.string{required = true}
    },
    output = {
      value = field.string{},
      explanation = field.string{}
    },
    run = function(input)
      -- Step 1: Classify with fine-tuned model
      local result = Classify {
        classes = {"YES", "NO"},
        model = "openai/ft:gpt-4o-mini-2024-07-18:call-criteria:aw-ib-sales-pain-points:BXS9SszP",
        temperature = 0.0,
        max_tokens = 16,
        prompt = [[Classification instructions...]],
        input = input.text
      }

      local classification = tostring(result.value or "")

      -- Step 2: Get explanation from standard model
      local models = require("tactus.models.llm")
      local explainer = models.LLMModel {
        name = "explainer",
        model = "openai/gpt-4o-mini",
        temperature = 0.2,
        max_tokens = 500,
        prompt = [[Explanation instructions...]]
      }

      local explain_result = explainer({
        text = "Explain classification: " .. classification .. "\n\n<transcript>\n" .. input.text .. "\n</transcript>"
      })
      local explanation = explain_result.output.response or tostring(explain_result.output)

      return {
        value = classification,
        explanation = tostring(explanation)
      }
    end
  }

output:
  value: value
  explanation: explanation
```

---

## Model Naming

Models use LiteLLM format: `provider/model-id`

Common patterns:
- `openai/gpt-5.4-nano` — standard OpenAI
- `openai/gpt-4o-mini` — mini model
- `openai/ft:gpt-4o-mini-2024-07-18:org:name:id` — fine-tuned
- `anthropic/claude-sonnet-4-6-20250514` — Anthropic

## Automatic Features

TactusScore provides these without explicit code:

- **Timestamp enrichment**: If metadata contains Deepgram data, explanation quotes get `[M:SS.ff-M:SS.ff]` timestamps automatically
- **Cost tracking**: All API calls recorded to `CostAccumulator`
- **Validation**: `valid_classes` YAML field validates output against allowed values
- **Confidence conversion**: Numeric or string labels (`high`/`medium`/`low`) converted to 0.0-1.0 float
