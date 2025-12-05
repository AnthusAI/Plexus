# Plexus Procedure DSL: Agentic Workflow Programming

## Table of Contents

- [Overview](#overview)
- [Core Concepts](#core-concepts)
- [Design Philosophy](#design-philosophy)
- [Document Structure](#document-structure)
- [Parameters and Outputs](#parameters-and-outputs)
- [Summarization Prompts](#summarization-prompts)
- [Guards and Validation](#guards-and-validation)
- [Agent Definitions](#agent-definitions)
- [Human-in-the-Loop (HITL)](#human-in-the-loop-hitl)
- [Message Classification System](#message-classification-system)
- [Workflow Orchestration](#workflow-orchestration)
- [Procedure Invocation](#procedure-invocation)
- [State Management](#state-management)
- [Stage Management](#stage-management)
- [Error Handling](#error-handling)
- [Complete API Reference](#complete-api-reference)
- [Example Procedures](#example-procedures)
- [Best Practices](#best-practices)
- [Migration Guide](#migration-guide)

---

## Overview

The Plexus Procedure DSL is a configuration-based system for defining agentic workflows that combine:

- **Declarative YAML** for component definitions (agents, prompts, tools, stages)
- **Embedded Lua** for orchestration logic and control flow
- **High-level primitives** that abstract LLM mechanics
- **First-class human-in-the-loop** support for collaboration
- **Uniform recursion** where procedures work identically at all nesting levels

### Why This DSL?

Traditional code-based AI workflows suffer from:
- Tight coupling between orchestration logic and agent configurations
- Difficulty in composing and reusing workflow components
- No standard patterns for human collaboration
- Complex async/await patterns for parallel AI operations

The Procedure DSL solves these by:
- Separating what components do (YAML) from how they're orchestrated (Lua)
- Providing composable, recursive procedure invocation
- Built-in human interaction primitives
- Simple async primitives that hide complexity

### Quick Example

```yaml
name: content_reviewer
version: 1.0.0
description: Review and approve content with human oversight

params:
  document:
    type: string
    required: true

outputs:
  approved:
    type: boolean
    required: true
  final_version:
    type: string
    required: true

agents:
  reviewer:
    system_prompt: |
      Review this document for quality and accuracy.
    tools: [analyze, done]

workflow: |
  -- AI reviews the document
  repeat
    Reviewer.turn()
  until Tool.called("done")

  -- Human approves
  local approved = Human.approve({
    message = "Approve this document?",
    context = {analysis = State.get("analysis")}
  })

  return {
    approved = approved,
    final_version = params.document
  }
```

---

## Core Concepts

### Procedures as First-Class Components

A **procedure** is a reusable, composable unit of agentic work. It can:
- Accept typed parameters
- Return typed outputs
- Invoke other procedures synchronously or asynchronously
- Request human interaction
- Track stages and state
- Run at any nesting level with identical behavior

### Agents as Cognitive Workers

An **agent** is a configured LLM instance with:
- A system prompt (templated)
- Available tools (including other procedures)
- Response filtering and retry logic
- Message history management

Agents are declared in YAML and invoked via Lua primitives like `Worker.turn()`.

### Human-in-the-Loop (HITL)

**HITL** enables procedures to:
- Request approval before critical operations
- Gather input from human operators
- Submit work for review and editing
- Send notifications and alerts
- Escalate when stuck

HITL operations can be declared in YAML or invoked programmatically in Lua.

### Uniform Recursion

A procedure invoked by another procedure works **identically** to a top-level procedure:
- Same parameter passing
- Same output schema
- Same async capabilities
- Same HITL primitives
- Same summarization prompts

This enables deep composition without special cases.

---

## Design Philosophy

### 1. YAML Declares, Lua Orchestrates

**YAML is for configuration:**
```yaml
agents:
  worker:
    system_prompt: "You are a researcher"
    tools: [search, done]
```

**Lua is for control flow:**
```lua
repeat
  Worker.turn()
until Tool.called("done") or Iterations.exceeded(10)
```

This separation makes procedures readable, testable, and composable.

### 2. High-Level Primitives

Instead of:
```python
response = llm.chat(messages, tools=[search, done])
if response.tool_calls:
    for call in response.tool_calls:
        # handle tool execution...
```

Write:
```lua
Worker.turn()
```

The primitive handles tool execution, message history, retries, and error handling.

### 3. Uniform Recursion

No distinction between:
- Top-level procedure invocation
- Procedure called by another procedure
- Procedure called as a tool
- Async vs sync invocation

All use the same interface and behavior.

### 4. Human-in-the-Loop First

HITL is not an afterthought:
```lua
-- Approval is a first-class primitive
local approved = Human.approve({message = "Proceed?"})

-- Not a callback, not a webhook, not a queue
-- It's built into the control flow
```

### 5. Built-In Reliability

- Automatic retry with exponential backoff
- Response validation before returning
- Message history filtering
- Exception handling patterns
- Checkpoint recovery for long-running procedures

---

## Document Structure

Every procedure is defined in a YAML document with this structure:

```yaml
# Metadata
name: procedure_name
version: 1.0.0
description: Human-readable description

# Input schema
params:
  # parameter definitions...

# Output schema
outputs:
  # output definitions...

# Summarization prompts
return_prompt: |
  # prompt for successful completion...
error_prompt: |
  # prompt for error cases...
status_prompt: |
  # prompt for progress updates...

# Execution control
async: true
max_depth: 5
max_turns: 50

# Pre-execution validation
guards:
  - |
    # Lua validation code...

# Human interaction points
hitl:
  # interaction definitions...

# Dependencies
dependencies:
  tools:
    - tool_name
  procedures:
    - other_procedure

# Templates
prompts:
  template_name: |
    # template content...

# Inline procedures
procedures:
  helper_name:
    # nested procedure definition...

# Agents
agents:
  agent_name:
    # agent configuration...

# Stages
stages:
  - stage_name
  - another_stage

# Orchestration
workflow: |
  -- Lua code here
  Worker.turn()
  return {result = "done"}
```

### Minimal Example

```yaml
name: simple_task
version: 1.0.0

agents:
  worker:
    system_prompt: "Complete the task"
    tools: [done]

workflow: |
  Worker.turn()
```

---

## Parameters and Outputs

### Parameter Schema

Parameters define what the procedure accepts. They are validated **before** execution:

```yaml
params:
  # Required string
  topic:
    type: string
    required: true
    description: "The research topic"

  # Optional enum
  depth:
    type: string
    enum: [shallow, deep]
    default: shallow

  # Number with default
  max_results:
    type: number
    default: 10

  # Boolean
  include_sources:
    type: boolean
    default: true

  # Array
  categories:
    type: array
    default: []

  # Object
  config:
    type: object
    default: {}
```

**Supported types:** `string`, `number`, `boolean`, `array`, `object`

**Validation:**
- `required: true` — must be provided by caller
- `enum: [...]` — must be one of listed values
- `default: value` — used if not provided

**Access in templates:**
```yaml
system_prompt: |
  Research topic: {params.topic}
  Depth: {params.depth}
  Max results: {params.max_results}
```

**Access in Lua:**
```lua
local topic = params.topic
local depth = params.depth or "shallow"
```

### Output Schema

Outputs define what the procedure returns. They are validated **after** execution:

```yaml
outputs:
  # Required string output
  findings:
    type: string
    required: true
    description: "Summary of research findings"

  # Required enum output
  confidence:
    type: string
    enum: [high, medium, low]
    required: true

  # Optional array output
  sources:
    type: array
    required: false
```

**Behavior with outputs defined:**
1. Workflow must return a table with all required fields
2. Types are validated
3. Only declared fields are returned (internal state stripped)

**Behavior without outputs:**
```yaml
# No outputs section = return anything
```

Workflow can return any Lua value without validation.

### Parameter and Output in Lua

```lua
-- Access parameters
local topic = params.topic
local config = params.config or {}

-- Build outputs
local result = {
  findings = "Found 10 relevant papers",
  confidence = "high",
  sources = sources_list
}

return result
```

### Parameter and Output in Invocation

```lua
-- Pass parameters
local result = Procedure.run("researcher", {
  topic = "quantum computing",
  depth = "deep",
  max_results = 20
})

-- Access outputs
Log.info("Findings: " .. result.findings)
Log.info("Confidence: " .. result.confidence)
```

---

## Summarization Prompts

Summarization prompts control how procedures communicate their results. They are injected into the agent's context at specific points.

### `return_prompt`

Injected when the workflow completes successfully. The agent does one final turn to generate a summary, which becomes the procedure's return value.

```yaml
return_prompt: |
  Summarize your work concisely:
  - What was accomplished
  - Key findings or results
  - Important notes for the caller

  Format your response as structured data if outputs are defined.
```

**When it runs:** After `workflow` completes without error

**What happens:**
1. Workflow returns (possibly incomplete data)
2. `return_prompt` is injected into agent's context
3. Agent generates final response
4. Response becomes the return value (validated against `outputs`)

**Example:**
```yaml
outputs:
  summary:
    type: string
    required: true
  count:
    type: number
    required: true

return_prompt: |
  Provide a summary of your analysis and the number of items processed.
  Return: {"summary": "...", "count": N}

workflow: |
  Worker.turn()
  -- Workflow doesn't explicitly return
  -- return_prompt causes agent to generate final output
```

### `error_prompt`

Injected when the workflow fails (exception or max iterations exceeded). The agent explains what went wrong.

```yaml
error_prompt: |
  The task could not be completed. Explain:
  - What you were attempting
  - What went wrong
  - Any partial progress made
  - Recommendations for retry or alternative approach
```

**When it runs:** When workflow throws exception or exceeds max_turns

**What happens:**
1. Error is caught
2. `error_prompt` is injected
3. Agent generates error explanation
4. Explanation is included in exception raised to caller

### `status_prompt`

Injected when a caller requests a status update (async procedures only). The agent reports current progress without stopping.

```yaml
status_prompt: |
  Provide a brief progress update:
  - What has been completed
  - What you're currently working on
  - Estimated remaining work (if applicable)
```

**When it runs:** When `Procedure.status(handle)` is called on an async procedure

**What happens:**
1. Status request arrives
2. `status_prompt` is injected (without interrupting workflow)
3. Agent generates progress report
4. Report is returned to caller

**Example usage:**
```lua
-- Caller
local handle = Procedure.spawn("long_analysis", {data = big_dataset})

-- Later, check progress
local status = Procedure.status(handle)
Log.info("Progress: " .. status.message)

-- Still later, get result
local result = Procedure.wait(handle)
```

### Default Prompts

If not specified, these defaults are used:

```yaml
return_prompt: |
  Summarize the result of your work concisely.

error_prompt: |
  Explain what went wrong and any partial progress made.

status_prompt: |
  Briefly describe your current progress and remaining work.
```

### Best Practices

**DO:**
- Make prompts specific to your procedure's purpose
- Request structured output that matches your `outputs` schema
- Include context about what's expected

**DON'T:**
- Make prompts too verbose (they add to context)
- Duplicate information already in system prompts
- Request information the agent can't possibly have

---

## Guards and Validation

Guards are pre-execution validation checks written in Lua. They run **before** the workflow starts.

### Basic Guard

```yaml
guards:
  - |
    if not params.file_path then
      return false, "file_path parameter is required"
    end
    return true
```

### Multiple Guards

```yaml
guards:
  - |
    -- Check file exists
    if not File.exists(params.file_path) then
      return false, "File not found: " .. params.file_path
    end
    return true

  - |
    -- Check reasonable depth
    if params.depth > 10 then
      return false, "Depth cannot exceed 10"
    end
    return true

  - |
    -- Check API key available
    if not os.getenv("API_KEY") then
      return false, "API_KEY environment variable not set"
    end
    return true
```

### Guard Return Values

```lua
-- Success
return true

-- Failure with message
return false, "Error message explaining what's wrong"
```

### Guard Context

Guards have access to:
- `params` — validated input parameters
- All Lua standard library
- File system utilities (`File.*`)
- Environment variables (`os.getenv`)

Guards do NOT have access to:
- Agent primitives (no `Worker.turn()`)
- State (state is initialized after guards pass)
- Session history (session doesn't exist yet)

### When to Use Guards

**Use guards for:**
- Parameter validation beyond type checking
- File existence checks
- Permission verification
- Resource availability checks
- Environmental precondition validation

**Don't use guards for:**
- Business logic (put in workflow)
- API calls (too slow, use workflow)
- Complex computations (use workflow)

### Example: File Processing Guard

```yaml
name: process_file
version: 1.0.0

params:
  input_file:
    type: string
    required: true
  output_dir:
    type: string
    required: true

guards:
  - |
    -- Input must exist
    if not File.exists(params.input_file) then
      return false, "Input file not found: " .. params.input_file
    end
    return true

  - |
    -- Output directory must exist
    if not File.exists(params.output_dir) then
      return false, "Output directory not found: " .. params.output_dir
    end
    return true

  - |
    -- Input must be readable
    local content, err = File.read(params.input_file)
    if not content then
      return false, "Cannot read input file: " .. err
    end
    return true

workflow: |
  -- Guards passed, proceed with processing
  local content = File.read(params.input_file)
  Worker.turn({inject = "Process this content: " .. content})
```

---

## Agent Definitions

Agents are the cognitive workers that execute agentic turns. Each agent is a configured LLM instance with prompts, tools, and behavior settings.

### Basic Agent

```yaml
agents:
  worker:
    system_prompt: |
      You are a helpful assistant.
    tools:
      - search
      - done
```

This creates a `Worker.turn()` primitive in Lua.

### Complete Agent Configuration

```yaml
agents:
  researcher:
    # Pre-turn preparation
    prepare: |
      return {
        current_time = os.date(),
        context_data = State.get("research_context"),
        progress = Iterations.current()
      }

    # System prompt (templated)
    system_prompt: |
      You are researching: {params.topic}
      Current time: {prepared.current_time}
      Context: {prepared.context_data}
      This is iteration {prepared.progress}

      Follow these guidelines:
      - Be thorough but concise
      - Cite sources when available
      - Mark completion with the 'done' tool

    # Initial user message (optional)
    initial_message: |
      Begin researching {params.topic}.
      Focus on {params.focus_area}.

    # Available tools
    tools:
      - search
      - read_document
      - analyze
      - done

    # Response filtering
    filter:
      class: ComposedFilter
      chain:
        - class: TokenBudget
          max_tokens: 120000
        - class: LimitToolResults
          count: 2

    # Retry configuration
    response:
      retries: 3
      retry_delay: 1.0
      backoff_multiplier: 2.0

    # Per-agent turn limit
    max_turns: 50
```

### Prepare Hook

The `prepare` hook runs **before each agent turn** and can compute values for use in prompts:

```yaml
agents:
  worker:
    prepare: |
      -- Runs before every Worker.turn()
      local stats = {
        iterations = Iterations.current(),
        items_processed = State.get("processed_count") or 0,
        current_stage = Stage.current()
      }
      return stats

    system_prompt: |
      Status: {prepared.iterations} iterations, {prepared.items_processed} items processed
      Stage: {prepared.current_stage}
```

**Prepare context:**
- Has access to `params`, `State`, `Stage`, `Iterations`
- Return value is available as `prepared` in templates
- Runs on every turn (keep it fast)

### System Prompt Templating

System prompts support variable interpolation:

```yaml
system_prompt: |
  # Parameters
  Topic: {params.topic}

  # Prepared data
  Progress: {prepared.iterations} iterations

  # State
  Items: {state.processed_count}

  # Context (from caller)
  Parent: {context.parent_procedure}

  # Environment
  API Key: {env.API_KEY}
```

**Available namespaces:**
- `params.*` — input parameters
- `prepared.*` — output of `prepare` hook
- `state.*` — procedure state
- `context.*` — runtime context from caller
- `env.*` — environment variables

### Initial Message

The `initial_message` is sent as the first user message to kick off the conversation:

```yaml
agents:
  worker:
    system_prompt: "You are a helpful assistant"
    initial_message: |
      Please complete the following task: {params.task_description}

      Requirements:
      - {params.requirement_1}
      - {params.requirement_2}
    tools: [search, done]
```

**Without `initial_message`:**
- Agent waits for first `Worker.turn()` or `Worker.turn({inject = "..."})`

**With `initial_message`:**
- Agent starts with this message on first `Worker.turn()`

### Tools

Tools are functions the agent can call. They can be:

1. **Built-in tools** (defined in Python tool registry)
2. **Other procedures** (automatically available as tools)

```yaml
agents:
  coordinator:
    tools:
      # Built-in tools
      - search
      - read_file
      - write_file

      # Other procedures (called as tools)
      - researcher
      - analyzer

      # Always include done tool for completion signaling
      - done
```

When an agent calls a procedure as a tool, it's invoked synchronously and the result is returned as the tool result.

### Response Filtering

Filters control message history to manage context size:

```yaml
agents:
  worker:
    filter:
      class: ComposedFilter
      chain:
        # Limit total tokens in history
        - class: TokenBudget
          max_tokens: 120000

        # Limit tool results to most recent N
        - class: LimitToolResults
          count: 2

        # Remove old assistant messages
        - class: KeepRecentMessages
          count: 10
```

**Common filters:**
- `TokenBudget` — drop old messages to stay under token limit
- `LimitToolResults` — keep only recent tool results
- `KeepRecentMessages` — keep only recent N messages
- `ComposedFilter` — chain multiple filters

### Retry Configuration

Configure how agent turns retry on failure:

```yaml
agents:
  worker:
    response:
      retries: 3                # Max retry attempts
      retry_delay: 1.0          # Initial delay (seconds)
      backoff_multiplier: 2.0   # Multiply delay after each retry
```

**Retry behavior:**
- Retries on transient failures (network, rate limits)
- Does NOT retry on invalid responses or tool errors
- Uses exponential backoff: 1s, 2s, 4s

### Max Turns

Limit turns for a specific agent:

```yaml
agents:
  worker:
    max_turns: 20  # This agent can take max 20 turns
```

This is separate from the procedure-level `max_turns` setting.

### Multiple Agents

A procedure can have multiple agents:

```yaml
agents:
  planner:
    system_prompt: "You create plans"
    tools: [done]

  executor:
    system_prompt: "You execute plans"
    tools: [search, done]

workflow: |
  -- Planning phase
  Planner.turn({inject = "Create a plan for: " .. params.task})
  local plan = State.get("plan")

  -- Execution phase
  repeat
    Executor.turn()
  until Tool.called("done", "executor")
```

Each agent gets its own primitive (capitalized agent name + `.turn()`).

---

## Human-in-the-Loop (HITL)

HITL enables procedures to interact with human operators for approval, input, review, and notification.

### Core Principles

1. **Blocking by default** — Approval, input, and review block the workflow until human responds
2. **Non-blocking notifications** — Notifications and alerts don't block execution
3. **Timeout support** — All blocking operations support timeouts with fallback behavior
4. **Context-rich** — Always provide context for humans to make informed decisions
5. **Integrated with stages** — Procedure status reflects when waiting for human

### Approval (Blocking)

Request yes/no approval:

```lua
local approved = Human.approve({
  message = "Deploy to production?",
  context = {
    version = "2.1.0",
    environment = "production",
    changes = change_summary
  },
  timeout = 3600,  -- 1 hour
  default = false
})

if approved then
  deploy()
else
  Log.info("Deployment cancelled by operator")
end
```

**Parameters:**
- `message` — question to ask human
- `context` — table of contextual data for decision-making
- `timeout` — seconds to wait (nil = wait forever)
- `default` — return value if timeout occurs
- `on_timeout` — behavior: `"default"`, `"error"`, or `"retry"`

**Return value:**
- `true` — human approved
- `false` — human rejected or timeout with `default = false`

### Input (Blocking)

Request free-form text input:

```lua
local topic = Human.input({
  message = "What topic should I research next?",
  placeholder = "Enter a topic...",
  timeout = nil  -- wait forever
})

if topic then
  Procedure.run("researcher", {topic = topic})
else
  Log.warn("No input received")
end
```

**Parameters:**
- `message` — prompt for input
- `placeholder` — UI hint text
- `timeout` — seconds to wait
- `default` — return value if timeout occurs

**Return value:**
- String containing human input
- `nil` if timeout without default

### Review (Blocking)

Request human review of a work product:

```lua
local review = Human.review({
  message = "Please review this generated report",
  artifact = report_text,
  artifact_type = "document",  -- document, code, config, data
  options = {"approve", "edit", "reject"},
  timeout = 86400  -- 24 hours
})

if review.decision == "approve" then
  publish(report_text)
elseif review.decision == "edit" then
  publish(review.edited_artifact)
else
  Log.warn("Report rejected", {feedback = review.feedback})
end
```

**Parameters:**
- `message` — review request message
- `artifact` — the work product to review
- `artifact_type` — type hint for UI rendering
- `options` — list of decision options
- `timeout` — seconds to wait

**Return value (table):**
- `decision` — which option was selected
- `edited_artifact` — modified version (if edited)
- `feedback` — human comments

### Notification (Non-Blocking)

Send information without waiting:

```lua
Human.notify({
  message = "Starting phase 2: data processing",
  level = "info"  -- info, warning, error
})

-- Execution continues immediately

process_data()

Human.notify({
  message = "Processing complete",
  level = "info",
  context = {
    items_processed = count,
    duration_seconds = elapsed
  }
})
```

**Parameters:**
- `message` — notification text
- `level` — severity: `"info"`, `"warning"`, `"error"`
- `context` — optional contextual data

**Behavior:**
- Returns immediately
- Notification appears in human UI
- Does NOT block workflow execution

### Alert (Non-Blocking, System-Level)

Send system monitoring alerts:

```lua
System.alert({
  message = "Memory usage exceeded threshold",
  level = "warning",  -- info, warning, error, critical
  source = "batch_processor",
  context = {
    memory_mb = current_memory,
    threshold_mb = max_memory,
    procedure_id = context.procedure_id
  }
})
```

**Parameters:**
- `message` — alert text
- `level` — severity: `"info"`, `"warning"`, `"error"`, `"critical"`
- `source` — identifying string for alert source
- `context` — structured data about the alert

**Difference from Human.notify:**
- Alerts are system-level (ops, monitoring, errors)
- Notifications are workflow-level (progress, status updates)
- Alerts can be sent from anywhere (not just procedures)
- Alerts have a `source` field for categorization

### Escalation (Blocking)

Hand off to human entirely when stuck:

```lua
if attempts > 3 then
  Human.escalate({
    message = "Unable to resolve this issue automatically",
    context = {
      attempts = attempts,
      last_error = last_error,
      current_state = State.all()
    }
  })
  -- Procedure pauses until human resolves and resumes
end
```

**Parameters:**
- `message` — escalation reason
- `context` — all relevant debugging information

**Behavior:**
- Procedure pauses
- Human sees all context
- Human can modify state, inject guidance, or abort
- Procedure resumes when human signals

### Declarative HITL Points

For predictable workflows, declare HITL points in YAML:

```yaml
hitl:
  approve_deployment:
    type: approval
    message: "Deploy version {params.version} to {params.environment}?"
    timeout: 3600
    default: false

  review_content:
    type: review
    message: "Review generated content before publishing"
    timeout: 86400
    options: [approve, edit, reject]

  get_topic:
    type: input
    message: "What topic should be researched?"
    placeholder: "Enter topic..."
```

**Use in workflow:**

```lua
-- Reference by name, provide runtime data
local approved = Human.approve("approve_deployment", {
  context = {
    changes = change_list,
    risk_level = "high"
  }
})

local review = Human.review("review_content", {
  artifact = generated_content
})

local topic = Human.input("get_topic")
```

**Benefits:**
- Self-documenting (HITL points visible in YAML)
- Reusable configuration
- Type safety (validates options)

### Timeout Handling

All blocking HITL operations support timeouts:

```lua
-- With default value
local approved = Human.approve({
  message = "Proceed?",
  timeout = 3600,
  default = false
})
-- After 1 hour without response, returns false

-- With explicit timeout handling
local approved, timed_out = Human.approve({
  message = "Proceed?",
  timeout = 3600
})

if timed_out then
  Log.warn("Approval request timed out")
  -- approved contains nil or default value
end

-- With error on timeout
local ok, result = pcall(function()
  return Human.approve({
    message = "Proceed?",
    timeout = 3600,
    on_timeout = "error"  -- throw exception
  })
end)

if not ok then
  Log.error("Approval timed out: " .. tostring(result))
end
```

**Timeout behaviors:**
- `on_timeout = "default"` — return default value (standard)
- `on_timeout = "error"` — throw exception
- `on_timeout = "retry"` — ask again (once)

### HITL and Stages

When a procedure waits for human interaction, its status reflects this:

```lua
Stage.set("processing")
do_work()

-- Procedure shows waiting_for_human = true during this call
local approved = Human.approve({message = "Continue?"})

Stage.set("finalizing")
```

**Parent procedures can detect:**

```lua
local handle = Procedure.spawn("deployment", params)

-- Check status
local status = Procedure.status(handle)

if status.waiting_for_human then
  -- Maybe send Slack notification
  notify_slack("Deployment waiting for approval")
end

-- Continue other work while waiting
do_other_work()

-- Eventually get result
local result = Procedure.wait(handle)
```

### Best Practices

**DO:**
- Provide rich context for human decision-making
- Set reasonable timeouts (don't wait forever)
- Use notifications for progress updates
- Use alerts for system-level monitoring
- Escalate when truly stuck

**DON'T:**
- Over-notify (notification fatigue)
- Request approval for trivial operations
- Omit context (humans need info to decide)
- Use blocking calls in high-throughput paths

---

## Message Classification System

Every chat message in the system has a `humanInteraction` field that determines its visibility and behavior.

### Classification Values

| Value | Purpose | Blocks? | Response Expected? | UI Visibility |
|-------|---------|---------|-------------------|---------------|
| `INTERNAL` | Agent reasoning, tool calls | No | No | Hidden from human |
| `CHAT` | Human message in conversation | No | Optional | Visible |
| `CHAT_ASSISTANT` | AI response in conversation | No | No | Visible |
| `NOTIFICATION` | Workflow progress update | No | No | Visible |
| `ALERT_INFO` | System info alert | No | No | Visible (monitoring) |
| `ALERT_WARNING` | System warning | No | No | Visible (monitoring) |
| `ALERT_ERROR` | System error alert | No | No | Visible (monitoring) |
| `ALERT_CRITICAL` | Critical system alert | No | No | Visible (monitoring) |
| `PENDING_APPROVAL` | Waiting for yes/no | Yes | Yes | Visible (requires action) |
| `PENDING_INPUT` | Waiting for input | Yes | Yes | Visible (requires action) |
| `PENDING_REVIEW` | Waiting for review | Yes | Yes | Visible (requires action) |
| `RESPONSE` | Human's response | No | No | Visible |
| `TIMED_OUT` | Request expired | No | No | Visible |
| `CANCELLED` | Request cancelled | No | No | Visible |

### Usage Patterns

**Procedure internals (hidden from human):**
```lua
-- These create INTERNAL messages
Worker.turn()  -- Agent reasoning
Tool.call("search", {query = "..."})  -- Tool execution
Log.debug("Processing item " .. i)  -- Debug logging
```

**Human-AI conversation (chatbot):**
```yaml
# ChatSession with category: "assistant"
# Messages automatically classified as CHAT / CHAT_ASSISTANT
```

```python
# Human message
create_chat_message(
    session_id=session_id,
    role="USER",
    content="How do I reset my password?",
    human_interaction="CHAT"
)

# AI response
create_chat_message(
    session_id=session_id,
    role="ASSISTANT",
    content="You can reset your password by...",
    human_interaction="CHAT_ASSISTANT"
)
```

**Workflow notifications:**
```lua
Human.notify({
  message = "Starting phase 2",
  level = "info"
})
-- Creates message with humanInteraction = NOTIFICATION
```

**System monitoring:**
```lua
System.alert({
  message = "High memory usage",
  level = "warning",
  source = "batch_processor"
})
-- Creates message with humanInteraction = ALERT_WARNING
```

**Interactive requests:**
```lua
Human.approve({message = "Proceed?"})
-- Creates message with humanInteraction = PENDING_APPROVAL

Human.input({message = "Enter topic"})
-- Creates message with humanInteraction = PENDING_INPUT

Human.review({message = "Review this", artifact = doc})
-- Creates message with humanInteraction = PENDING_REVIEW
```

### UI Filtering

UIs can filter by `humanInteraction` to show relevant messages:

**Human operator dashboard:**
```sql
-- Show only user-facing messages
SELECT * FROM chat_messages
WHERE human_interaction IN (
  'CHAT',
  'CHAT_ASSISTANT',
  'NOTIFICATION',
  'ALERT_WARNING',
  'ALERT_ERROR',
  'ALERT_CRITICAL',
  'PENDING_APPROVAL',
  'PENDING_INPUT',
  'PENDING_REVIEW',
  'RESPONSE'
)
```

**Developer debugging:**
```sql
-- Show all messages including internals
SELECT * FROM chat_messages
-- (no filter)
```

**Monitoring dashboard:**
```sql
-- Show only alerts
SELECT * FROM chat_messages
WHERE human_interaction LIKE 'ALERT_%'
ORDER BY created_at DESC
```

### Message Flow Examples

**Procedure with HITL:**
```
1. INTERNAL       Worker.turn() reasoning
2. INTERNAL       Tool call: search(...)
3. INTERNAL       Tool result: [...]
4. NOTIFICATION   "Analysis complete"
5. PENDING_APPROVAL  "Deploy to production?"
6. RESPONSE       "Yes" (from human)
7. NOTIFICATION   "Deploying..."
8. NOTIFICATION   "Deployment complete"
```

Human sees: 4, 5, 6, 7, 8
System sees: all

**Chat conversation:**
```
1. CHAT           "How do I deploy?"
2. CHAT_ASSISTANT "You can deploy using..."
3. CHAT           "Can you deploy for me?"
4. INTERNAL       (spawns deployment procedure)
5. NOTIFICATION   "Starting deployment"
6. CHAT_ASSISTANT "I've started the deployment"
7. NOTIFICATION   "Deployment complete"
8. CHAT_ASSISTANT "Deployment finished successfully"
```

Human sees: 1, 2, 3, 5, 6, 7, 8
System sees: all

---

## Workflow Orchestration

The `workflow` section contains Lua code that orchestrates the procedure's execution.

### Basic Structure

```yaml
workflow: |
  -- Initialize
  Stage.set("working")

  -- Do work
  repeat
    Worker.turn()
  until Tool.called("done")

  -- Return
  Stage.set("complete")
  return {result = "success"}
```

### Agent Turns

The primary operation is agent turns:

```lua
-- Basic turn
Worker.turn()

-- Turn with injected message
Worker.turn({inject = "Focus on security aspects"})

-- Capture response
local response = Worker.turn()
Log.info("Agent said: " .. response.content)

-- Check tool calls
if response.tool_calls then
  for _, call in ipairs(response.tool_calls) do
    Log.info("Called: " .. call.name)
  end
end
```

### Control Loops

**Repeat until tool called:**
```lua
repeat
  Worker.turn()
until Tool.called("done")
```

**Repeat with iteration limit:**
```lua
repeat
  Worker.turn()
until Tool.called("done") or Iterations.exceeded(20)
```

**For loop:**
```lua
for i = 1, 10 do
  Worker.turn({inject = "Process item " .. i})
end
```

**While loop:**
```lua
while not Tool.called("done") and Iterations.current() < 50 do
  Worker.turn()
end
```

### Conditional Logic

```lua
if params.mode == "fast" then
  Worker.turn({inject = "Be concise"})
else
  Worker.turn({inject = "Be thorough"})
end
```

### State Management in Workflow

```lua
-- Initialize state
State.set("items_processed", 0)
State.set("errors", {})

-- Work loop
for i, item in ipairs(params.items) do
  Worker.turn({inject = "Process: " .. item})

  if Tool.called("success") then
    State.increment("items_processed")
  else
    State.append("errors", {item = item, error = "failed"})
  end
end

-- Return summary
return {
  processed = State.get("items_processed"),
  failed = #State.get("errors")
}
```

### Error Handling

```lua
local ok, result = pcall(function()
  Worker.turn()
end)

if not ok then
  Log.error("Turn failed: " .. tostring(result))
  return {success = false, error = result}
end
```

### Early Return

```lua
if not params.enabled then
  return {skipped = true, reason = "disabled"}
end

-- ... rest of workflow
```

### Invoking Other Procedures

**Synchronous:**
```lua
local research = Procedure.run("researcher", {
  topic = params.topic
})

Log.info("Research findings: " .. research.findings)
```

**Asynchronous:**
```lua
local handles = {}
for _, topic in ipairs(params.topics) do
  local handle = Procedure.spawn("researcher", {topic = topic})
  table.insert(handles, handle)
end

-- Wait for all
Procedure.wait_all(handles)

-- Collect results
local results = {}
for _, handle in ipairs(handles) do
  local result = Procedure.result(handle)
  table.insert(results, result)
end
```

### HITL in Workflow

```lua
-- Progress notification
Human.notify({message = "Starting analysis"})

-- Do work
Worker.turn()

-- Request approval
local approved = Human.approve({
  message = "Publish results?",
  context = {findings = State.get("findings")}
})

if approved then
  publish()
  Human.notify({message = "Published successfully"})
else
  Log.info("Publication cancelled")
end
```

### Stage Transitions

```lua
Stage.set("planning")
Planner.turn()

Stage.set("executing")
repeat
  Executor.turn()
until Tool.called("done")

Stage.set("verifying")
Verifier.turn()

Stage.set("complete")
```

---

## Procedure Invocation

Procedures can invoke other procedures in multiple ways.

### As a Tool (Implicit)

When a procedure is listed in an agent's tools, it can be called implicitly:

```yaml
agents:
  coordinator:
    system_prompt: "You coordinate research tasks"
    tools:
      - researcher  # Another procedure
      - done
```

The agent can call `researcher` as a tool:
```
Agent: I'll use the researcher tool to investigate quantum computing.
Tool call: researcher(topic="quantum computing")
Tool result: {"findings": "...", "confidence": "high"}
```

### Explicit Synchronous

Call a procedure and wait for result:

```lua
local result = Procedure.run("researcher", {
  topic = "quantum computing",
  depth = "deep"
})

Log.info("Findings: " .. result.findings)
```

**Behavior:**
- Blocks until procedure completes
- Returns procedure's output
- Raises exception if procedure fails

### Explicit Asynchronous

Spawn a procedure and continue:

```lua
local handle = Procedure.spawn("researcher", {
  topic = "quantum computing"
})

-- Do other work
do_something_else()

-- Check status
local status = Procedure.status(handle)
if status.stage == "analyzing" then
  Log.info("Still analyzing...")
end

-- Wait for result
local result = Procedure.wait(handle)
```

**Available operations:**

```lua
-- Spawn
local handle = Procedure.spawn(name, params)

-- Check completion
if Procedure.is_complete(handle) then
  local result = Procedure.result(handle)
end

-- Get status
local status = Procedure.status(handle)
-- status = {
--   stage = "executing",
--   waiting_for_human = false,
--   iterations = 5,
--   message = "..."
-- }

-- Wait with timeout
local result = Procedure.wait(handle, {timeout = 300})
if not result then
  Log.warn("Procedure timed out")
  Procedure.cancel(handle)
end

-- Inject guidance
Procedure.inject(handle, "Focus on recent papers")

-- Cancel
Procedure.cancel(handle)
```

### Multiple Async Procedures

**Wait for first to complete:**
```lua
local handles = {
  Procedure.spawn("approach_a", params),
  Procedure.spawn("approach_b", params),
  Procedure.spawn("approach_c", params)
}

local first_handle, result = Procedure.wait_any(handles)
Log.info("First approach finished: " .. first_handle)

-- Cancel others
for _, handle in ipairs(handles) do
  if handle ~= first_handle then
    Procedure.cancel(handle)
  end
end
```

**Wait for all:**
```lua
local handles = {}
for _, topic in ipairs(params.topics) do
  local handle = Procedure.spawn("researcher", {topic = topic})
  table.insert(handles, handle)
end

Procedure.wait_all(handles)

-- All complete, collect results
local results = {}
for _, handle in ipairs(handles) do
  table.insert(results, Procedure.result(handle))
end
```

**Poll for completion:**
```lua
local handles = {...}

while not Procedure.all_complete(handles) do
  Sleep(5)

  for _, handle in ipairs(handles) do
    if Procedure.is_complete(handle) then
      local result = Procedure.result(handle)
      process(result)
      -- Remove from list
    end
  end
end
```

### Inline Procedures

Define helper procedures inline:

```yaml
name: coordinator
version: 1.0.0

procedures:
  researcher:
    params:
      query:
        type: string
        required: true

    outputs:
      findings:
        type: string
        required: true

    agents:
      worker:
        system_prompt: "Research: {params.query}"
        tools: [search, done]

    workflow: |
      repeat
        Worker.turn()
      until Tool.called("done")

agents:
  coordinator:
    tools:
      - researcher
      - done

workflow: |
  Coordinator.turn()
```

The inline `researcher` procedure is available as a tool to `coordinator`.

### Recursion and Depth

Procedures can invoke themselves (direct recursion) or invoke procedures that eventually invoke them (indirect recursion).

**Depth limit:**
```yaml
max_depth: 5
```

Prevents infinite recursion by limiting nesting depth.

**Example recursive procedure:**
```yaml
name: recursive_analyzer
version: 1.0.0

params:
  depth:
    type: number
    required: true

max_depth: 10

workflow: |
  if params.depth <= 0 then
    return {result = "base case"}
  end

  -- Recurse
  local sub_result = Procedure.run("recursive_analyzer", {
    depth = params.depth - 1
  })

  return {result = "depth " .. params.depth .. ": " .. sub_result.result}
```

### Uniform Behavior

A procedure works identically regardless of how it's invoked:

| Feature | Top-level | As tool | Explicit | Async |
|---------|-----------|---------|----------|-------|
| Parameters | ✓ | ✓ | ✓ | ✓ |
| Outputs | ✓ | ✓ | ✓ | ✓ |
| Guards | ✓ | ✓ | ✓ | ✓ |
| HITL | ✓ | ✓ | ✓ | ✓ |
| Stages | ✓ | ✓ | ✓ | ✓ |
| State | ✓ | ✓ | ✓ | ✓ |
| Summarization | ✓ | ✓ | ✓ | ✓ |

This uniformity enables deep composition without special cases.

---

## State Management

Procedures maintain mutable state that persists across agent turns and procedure calls.

### Basic Operations

```lua
-- Set
State.set("count", 0)
State.set("items", {})
State.set("config", {mode = "fast", verbose = true})

-- Get
local count = State.get("count")
local items = State.get("items")

-- Get with default
local config = State.get("config", {mode = "normal"})

-- Increment (numeric values)
State.increment("count")  -- count = 1
State.increment("count")  -- count = 2

-- Append (array values)
State.append("items", "first")
State.append("items", "second")
-- items = {"first", "second"}

-- Get all state
local all = State.all()
-- Returns table with all state keys/values
```

### Common Patterns

**Counter:**
```lua
State.set("processed", 0)

for _, item in ipairs(params.items) do
  process(item)
  State.increment("processed")
end

return {count = State.get("processed")}
```

**Accumulator:**
```lua
State.set("results", {})

repeat
  Worker.turn()
  if Tool.called("found") then
    local result = Tool.last_result("found")
    State.append("results", result)
  end
until Tool.called("done")

return {results = State.get("results")}
```

**Configuration:**
```lua
State.set("config", {
  max_attempts = 3,
  timeout = 30,
  retry = true
})

-- Later
local config = State.get("config")
if config.retry then
  retry_operation()
end
```

**Progress tracking:**
```lua
State.set("progress", {
  total = #params.items,
  completed = 0,
  failed = 0
})

for _, item in ipairs(params.items) do
  local ok = process(item)

  local progress = State.get("progress")
  if ok then
    progress.completed = progress.completed + 1
  else
    progress.failed = progress.failed + 1
  end
  State.set("progress", progress)
end
```

### State in Templates

State is available in prompt templates:

```yaml
agents:
  worker:
    system_prompt: |
      Progress: {state.completed} / {state.total} items processed
      Failed: {state.failed}
```

Templates are re-evaluated before each turn, so they reflect current state.

### State Isolation

State is isolated per procedure instance:

```lua
-- Parent procedure
State.set("count", 10)

-- Call child
Procedure.run("child", params)

-- Parent's state unchanged
Log.info(State.get("count"))  -- Still 10
```

Child procedures have their own state namespace.

### State and Graph Nodes

State can be persisted to graph nodes:

```lua
-- Save to current node
local node = GraphNode.current()
node:set_metadata("state", State.all())

-- Load from node
local node = GraphNode.find(node_id)
local saved_state = node:metadata().state
for k, v in pairs(saved_state) do
  State.set(k, v)
end
```

This enables recovery and resumption of long-running procedures.

---

## Stage Management

Stages provide high-level status tracking for procedures. They integrate with monitoring and HITL systems.

### Defining Stages

```yaml
stages:
  - initializing
  - analyzing
  - processing
  - review
  - complete
```

Stages are optional but recommended for multi-phase workflows.

### Stage Operations

```lua
-- Set stage
Stage.set("analyzing")

-- Get current stage
local current = Stage.current()  -- "analyzing"

-- Check stage
if Stage.is("analyzing") then
  -- Do something
end

-- Advance to next stage (in declaration order)
Stage.advance("processing")
```

### Stage in Workflow

```lua
Stage.set("initializing")
setup()

Stage.set("analyzing")
repeat
  Worker.turn()
until Tool.called("done")

Stage.set("processing")
process_results()

Stage.set("review")
local approved = Human.approve({message = "Approve results?"})

if approved then
  Stage.set("complete")
else
  Stage.set("analyzing")  -- Go back
end
```

### Stage History

```lua
-- Get stage history
local history = Stage.history()
-- [
--   {stage = "initializing", timestamp = "..."},
--   {stage = "analyzing", timestamp = "..."},
--   {stage = "processing", timestamp = "..."}
-- ]
```

### Stage and HITL

When waiting for human interaction, stage status is preserved:

```lua
Stage.set("processing")
Worker.turn()

-- Status becomes waiting_for_human = true during approval
local approved = Human.approve({message = "Continue?"})

-- Stage remains "processing" after approval
```

Parent procedures can check:

```lua
local status = Procedure.status(handle)
-- {
--   stage = "processing",
--   waiting_for_human = true
-- }
```

### Stage vs Status

**Stage:** High-level phase of work (initializing, analyzing, processing)
**Status:** Runtime state (running, waiting_for_human, completed, failed)

Both are tracked independently.

---

## Error Handling

### Try-Catch Pattern

```lua
local ok, result = pcall(function()
  Worker.turn()
  return State.get("result")
end)

if not ok then
  Log.error("Operation failed: " .. tostring(result))
  return {success = false, error = result}
end

return {success = true, result = result}
```

### Retry Pattern

```lua
local attempts = 0
local max_attempts = 3
local result = nil

while attempts < max_attempts do
  local ok, r = pcall(Worker.turn)

  if ok then
    result = r
    break
  else
    attempts = attempts + 1
    Log.warn("Attempt " .. attempts .. " failed: " .. tostring(r))
    Sleep(1)
  end
end

if not result then
  return {success = false, error = "Max retries exceeded"}
end
```

### Built-In Retry

```lua
local result = Retry.with_backoff(function()
  return risky_operation()
end, {
  max_attempts = 3,
  initial_delay = 1.0,
  multiplier = 2.0
})
```

### Validation

```lua
-- Validate before proceeding
if not params.required_field then
  error("Missing required_field parameter")
end

-- Guards provide validation before workflow starts
-- (see Guards section)
```

### Error Prompts

When a procedure fails, the `error_prompt` is injected:

```yaml
error_prompt: |
  Explain what went wrong:
  - What you were attempting
  - The error that occurred
  - Any partial progress
  - Recommendations for recovery
```

The agent generates an explanation, which is included in the exception raised to the caller.

### Exception Propagation

```lua
-- Child procedure throws exception
Procedure.run("child", params)
-- Exception propagates to caller

-- Catch child exception
local ok, result = pcall(function()
  return Procedure.run("child", params)
end)

if not ok then
  Log.error("Child failed: " .. tostring(result))
  -- Handle error
end
```

---

## Complete API Reference

### Procedure Primitives

```lua
-- Synchronous invocation
result = Procedure.run(name, params)

-- Asynchronous invocation
handle = Procedure.spawn(name, params)

-- Status check
status = Procedure.status(handle)
-- status = {stage = "...", waiting_for_human = false, iterations = N, message = "..."}

-- Wait for completion
result = Procedure.wait(handle)
result = Procedure.wait(handle, {timeout = seconds})

-- Check completion
is_done = Procedure.is_complete(handle)
all_done = Procedure.all_complete({handle1, handle2, ...})

-- Get result (if complete)
result = Procedure.result(handle)

-- Wait for multiple
first_handle, result = Procedure.wait_any({handle1, handle2, ...})
Procedure.wait_all({handle1, handle2, ...})

-- Inject guidance (modify behavior mid-flight)
Procedure.inject(handle, "Focus on security aspects")

-- Cancel
Procedure.cancel(handle)
```

### Agent Primitives

```lua
-- Basic turn
response = Agent.turn()

-- Turn with injected message
response = Agent.turn({inject = "Additional instruction"})

-- Response structure
response = {
  content = "Agent's response text",
  tool_calls = {
    {name = "search", arguments = {query = "..."}},
    ...
  }
}
```

### Human Interaction Primitives

```lua
-- Approval (blocking, returns boolean)
approved = Human.approve({
  message = "Approve this action?",
  context = {key = "value", ...},
  timeout = 3600,  -- seconds, nil = forever
  default = false,
  on_timeout = "default"  -- "default", "error", "retry"
})

-- Input (blocking, returns string or nil)
text = Human.input({
  message = "Enter input:",
  placeholder = "Type here...",
  timeout = nil,
  default = nil
})

-- Review (blocking, returns table)
review = Human.review({
  message = "Review this artifact",
  artifact = content,
  artifact_type = "document",  -- "document", "code", "config", "data"
  options = {"approve", "edit", "reject"},
  timeout = 86400
})
-- review = {decision = "approve"|"edit"|"reject", edited_artifact = "...", feedback = "..."}

-- Notification (non-blocking)
Human.notify({
  message = "Progress update",
  level = "info",  -- "info", "warning", "error"
  context = {...}
})

-- Escalation (blocking)
Human.escalate({
  message = "Need human intervention",
  context = {...}
})

-- Alert (non-blocking, system-level)
System.alert({
  message = "System alert",
  level = "warning",  -- "info", "warning", "error", "critical"
  source = "component_name",
  context = {...}
})
```

### State Primitives

```lua
-- Get
value = State.get(key)
value = State.get(key, default)

-- Set
State.set(key, value)

-- Increment (numeric)
State.increment(key)
State.increment(key, amount)

-- Append (array)
State.append(key, value)

-- Get all
all_state = State.all()
```

### Stage Primitives

```lua
-- Set stage
Stage.set(name)

-- Get current
current = Stage.current()

-- Check stage
is_stage = Stage.is(name)

-- Advance to next
Stage.advance(name)

-- Get history
history = Stage.history()
-- [{stage = "...", timestamp = "..."}, ...]
```

### Tool Primitives

```lua
-- Check if tool was called
called = Tool.called(name)
called = Tool.called(name, agent_name)  -- For multi-agent

-- Get last result
result = Tool.last_result(name)
result = Tool.last_result(name, agent_name)

-- Get last call
call = Tool.last_call(name)
-- call = {name = "...", arguments = {...}, result = ...}
```

### Session Primitives

```lua
-- Append message
Session.append({
  role = "user",  -- or "assistant", "system"
  content = "Message text"
})

-- Inject system message
Session.inject_system("Additional context")

-- Clear history
Session.clear()

-- Get history
messages = Session.history()

-- Load from graph node
Session.load_from_node(node)

-- Save to graph node
Session.save_to_node(node)
```

### Control Primitives

```lua
-- Check stop request
if Stop.requested() then
  reason = Stop.reason()
  -- Clean up and exit
end

-- Iterations
current = Iterations.current()
exceeded = Iterations.exceeded(max)
```

### Graph Primitives

```lua
-- Get nodes
root = GraphNode.root()
current = GraphNode.current()

-- Create node
node = GraphNode.create({
  name = "node_name",
  metadata = {...}
})

-- Set current
GraphNode.set_current(node)

-- Node operations
children = node:children()
parent = node:parent()
score = node:score()
metadata = node:metadata()

-- Set metadata
node:set_metadata(key, value)
```

### Utility Primitives

```lua
-- Logging
Log.debug(message, context)
Log.info(message, context)
Log.warn(message, context)
Log.error(message, context)

-- Sleep
Sleep(seconds)

-- JSON
table_value = Json.decode(json_string)
json_string = Json.encode(table_value)

-- File operations
exists = File.exists(path)
content = File.read(path)
File.write(path, content)

-- Retry with backoff
result = Retry.with_backoff(function()
  return operation()
end, {
  max_attempts = 3,
  initial_delay = 1.0,
  multiplier = 2.0
})
```

---

## Example Procedures

### Simple Research Task

```yaml
name: simple_researcher
version: 1.0.0
description: Research a topic and provide summary

params:
  topic:
    type: string
    required: true

outputs:
  summary:
    type: string
    required: true

agents:
  researcher:
    system_prompt: |
      Research the topic: {params.topic}
      Provide a concise summary of key findings.
    tools:
      - search
      - done

return_prompt: |
  Provide a summary of your research findings.

workflow: |
  repeat
    Researcher.turn()
  until Tool.called("done") or Iterations.exceeded(10)
```

### Multi-Stage Analysis

```yaml
name: data_analyzer
version: 1.0.0
description: Analyze data through multiple stages

params:
  dataset:
    type: string
    required: true

outputs:
  insights:
    type: array
    required: true
  confidence:
    type: string
    enum: [high, medium, low]
    required: true

stages:
  - loading
  - cleaning
  - analyzing
  - reporting

agents:
  analyst:
    system_prompt: |
      Analyze dataset: {params.dataset}
      Current stage: {state.current_stage}
    tools:
      - load_data
      - clean_data
      - analyze
      - done

workflow: |
  Stage.set("loading")
  Analyst.turn({inject = "Load the dataset"})

  Stage.set("cleaning")
  Analyst.turn({inject = "Clean the data"})

  Stage.set("analyzing")
  repeat
    Analyst.turn()
  until Tool.called("done")

  Stage.set("reporting")
  return {
    insights = State.get("insights") or {},
    confidence = State.get("confidence") or "medium"
  }
```

### Content Pipeline with HITL

```yaml
name: content_pipeline
version: 1.0.0
description: Generate and publish content with human review

params:
  topic:
    type: string
    required: true
  target:
    type: string
    enum: [blog, docs, social]
    required: true

outputs:
  published:
    type: boolean
    required: true
  url:
    type: string
    required: false

stages:
  - drafting
  - review
  - publishing
  - complete

hitl:
  review_draft:
    type: review
    message: "Review the generated draft"
    timeout: 86400
    options: [approve, edit, reject]

  confirm_publish:
    type: approval
    message: "Publish to {params.target}?"
    timeout: 3600
    default: false

agents:
  writer:
    system_prompt: |
      Write content about: {params.topic}
      Target platform: {params.target}
    tools:
      - research
      - write
      - done

workflow: |
  Stage.set("drafting")
  Human.notify({
    message = "Starting content generation",
    level = "info"
  })

  repeat
    Writer.turn()
  until Tool.called("done") or Iterations.exceeded(20)

  local draft = State.get("draft")
  if not draft then
    return {published = false, error = "No draft generated"}
  end

  Stage.set("review")
  local review = Human.review("review_draft", {
    artifact = draft,
    artifact_type = "document"
  })

  if review.decision == "reject" then
    return {published = false, reason = "rejected"}
  end

  local final_content = review.edited_artifact or draft

  Stage.set("publishing")
  local approved = Human.approve("confirm_publish")

  if not approved then
    return {published = false, reason = "not_approved"}
  end

  local url = publish_content(final_content, params.target)

  Human.notify({
    message = "Content published",
    level = "info",
    context = {url = url}
  })

  Stage.set("complete")
  return {published = true, url = url}
```

### Parallel Research

```yaml
name: parallel_researcher
version: 1.0.0
description: Research multiple topics in parallel

params:
  topics:
    type: array
    required: true

outputs:
  results:
    type: array
    required: true

procedures:
  researcher:
    params:
      topic:
        type: string
        required: true

    outputs:
      findings:
        type: string
        required: true

    agents:
      worker:
        system_prompt: "Research: {params.topic}"
        tools: [search, done]

    workflow: |
      repeat
        Worker.turn()
      until Tool.called("done")

workflow: |
  -- Spawn researchers in parallel
  local handles = {}
  for _, topic in ipairs(params.topics) do
    local handle = Procedure.spawn("researcher", {topic = topic})
    table.insert(handles, handle)
  end

  -- Wait for all
  Procedure.wait_all(handles)

  -- Collect results
  local results = {}
  for _, handle in ipairs(handles) do
    local result = Procedure.result(handle)
    table.insert(results, result)
  end

  return {results = results}
```

### Recursive Task Decomposition

```yaml
name: task_decomposer
version: 1.0.0
description: Recursively decompose and execute tasks

params:
  task:
    type: string
    required: true
  depth:
    type: number
    default: 3

outputs:
  result:
    type: string
    required: true

max_depth: 10

agents:
  planner:
    system_prompt: |
      Task: {params.task}
      Decompose into subtasks if complex, or execute if simple.
    tools:
      - task_decomposer  # Recursive call
      - execute
      - done

workflow: |
  if params.depth <= 0 then
    -- Base case: execute directly
    Planner.turn({inject = "Execute this task directly"})
    return {result = State.get("result") or "completed"}
  end

  -- Recursive case: decompose
  Planner.turn()

  if Tool.called("task_decomposer") then
    -- Subtasks identified, recurse
    local subtasks = State.get("subtasks") or {}
    local results = {}

    for _, subtask in ipairs(subtasks) do
      local sub_result = Procedure.run("task_decomposer", {
        task = subtask,
        depth = params.depth - 1
      })
      table.insert(results, sub_result.result)
    end

    return {result = table.concat(results, "; ")}
  else
    -- Simple task, executed directly
    return {result = State.get("result") or "completed"}
  end
```

---

## Best Practices

### Procedure Design

**DO:**
- Define clear parameter and output schemas
- Use guards for precondition validation
- Provide meaningful summarization prompts
- Use stages for multi-phase workflows
- Include HITL points for critical decisions

**DON'T:**
- Make procedures too granular (compose, don't fragment)
- Put business logic in guards (use workflow)
- Omit output schemas (validation prevents bugs)
- Hard-code values (use parameters)

### Agent Configuration

**DO:**
- Write clear, specific system prompts
- Use prepare hook for dynamic context
- Limit tools to what's necessary
- Configure retry behavior appropriately
- Set reasonable max_turns

**DON'T:**
- Make system prompts too long (context cost)
- Provide too many tools (confuses agent)
- Skip error handling configuration
- Allow unlimited turns (set limits)

### Workflow Orchestration

**DO:**
- Use high-level control structures (repeat/until)
- Check for completion conditions (Tool.called, Stop.requested)
- Use state for accumulation and progress tracking
- Handle errors explicitly (pcall)
- Log important events

**DON'T:**
- Use complex nested conditionals (simplify)
- Ignore iteration limits (infinite loops)
- Forget to return values (outputs expected)
- Skip error handling (catch exceptions)

### Human-in-the-Loop

**DO:**
- Provide rich context for decisions
- Set reasonable timeouts
- Use notifications for progress updates
- Use alerts for system-level monitoring
- Escalate when truly stuck

**DON'T:**
- Over-notify (notification fatigue)
- Request approval for trivial operations
- Omit context (humans need info)
- Block on non-critical operations
- Use HITL in high-throughput paths

### State Management

**DO:**
- Initialize state early in workflow
- Use descriptive keys
- Store structured data (tables)
- Document state schema in comments

**DON'T:**
- Mutate state in templates (read-only)
- Store massive data (memory cost)
- Use state for temporary variables (Lua locals)
- Forget to check for nil values

### Performance

**DO:**
- Use async procedures for parallel work
- Spawn multiple procedures concurrently
- Filter message history (token budget)
- Set appropriate max_turns
- Use prepared data for expensive computations

**DON'T:**
- Use sync calls when async would work
- Let message history grow unbounded
- Recompute values every turn (use state)
- Skip response filtering (context cost)

### Error Handling

**DO:**
- Use pcall for risky operations
- Provide error_prompt for debugging
- Log errors with context
- Return structured error information
- Validate inputs (guards, parameters)

**DON'T:**
- Swallow exceptions silently
- Return generic error messages
- Skip validation (fail fast)
- Ignore partial failures

---

## Migration Guide

### From v3 to v4

v4 is fully backward compatible with v3. All v3 procedures work unchanged.

**New features in v4:**

1. **Human-in-the-Loop primitives:**
```lua
-- New in v4
Human.approve({message = "Proceed?"})
Human.input({message = "Enter topic"})
Human.review({message = "Review this", artifact = doc})
Human.notify({message = "Progress update"})
System.alert({message = "System alert", level = "warning"})
```

2. **Message classification:**
```yaml
# Every message now has humanInteraction field
# Controls visibility and blocking behavior
```

3. **Declarative HITL points:**
```yaml
hitl:
  review_step:
    type: review
    message: "Review the output"
    timeout: 86400
```

4. **Stage integration with HITL:**
```lua
-- Procedures show waiting_for_human = true when blocked
local status = Procedure.status(handle)
if status.waiting_for_human then
  -- Handle appropriately
end
```

**Migration steps:**

1. **No changes required** — v3 procedures work as-is
2. **Add HITL** (optional) — use new primitives for human collaboration
3. **Add message classification** (optional) — control UI visibility
4. **Declare HITL points** (optional) — document interaction points

**Example v3 procedure (unchanged):**
```yaml
name: researcher
version: 1.0.0

params:
  topic:
    type: string
    required: true

agents:
  worker:
    system_prompt: "Research: {params.topic}"
    tools: [search, done]

workflow: |
  repeat
    Worker.turn()
  until Tool.called("done")
```

**Enhanced with v4 HITL:**
```yaml
name: researcher
version: 1.0.0

params:
  topic:
    type: string
    required: true

hitl:
  review_findings:
    type: approval
    message: "Approve these research findings?"
    timeout: 3600

agents:
  worker:
    system_prompt: "Research: {params.topic}"
    tools: [search, done]

workflow: |
  Human.notify({message = "Starting research"})

  repeat
    Worker.turn()
  until Tool.called("done")

  local approved = Human.approve("review_findings")

  if not approved then
    error("Findings not approved")
  end
```

---

## Additional Resources

- **Plexus Documentation:** [plexus.docs.anthus.ai](https://plexus.docs.anthus.ai)
- **Example Procedures:** `/plexus/procedures/examples/`
- **HTML Documentation:** `/plexus/procedures/docs/index.html`
- **API Reference:** This document, API Reference section

---

## Glossary

**Agent:** A configured LLM instance with system prompt, tools, and behavior settings. Invoked via primitives like `Worker.turn()`.

**Async:** Asynchronous execution where a procedure is spawned and continues in the background.

**Guard:** Pre-execution validation check written in Lua.

**HITL:** Human-in-the-loop. Interaction patterns where procedures request human approval, input, review, or notification.

**humanInteraction:** Classification field on every message determining visibility and blocking behavior.

**Inline Procedure:** A procedure defined within another procedure's YAML document.

**Primitive:** High-level Lua function provided by the DSL (e.g., `Worker.turn()`, `State.get()`, `Human.approve()`).

**Procedure:** A reusable, composable unit of agentic work defined in YAML with Lua orchestration.

**Stage:** High-level phase of a workflow (e.g., "planning", "executing", "review").

**State:** Mutable key-value store persisting across agent turns and procedure calls.

**Summarization Prompt:** Prompt injected at workflow completion (`return_prompt`), failure (`error_prompt`), or status check (`status_prompt`).

**Template:** String with variable interpolation (e.g., `{params.topic}`), used in prompts.

**Tool:** Function an agent can call. Can be built-in or another procedure.

**Uniform Recursion:** Design principle where procedures work identically at all nesting levels.

**Workflow:** The Lua orchestration code that controls procedure execution.

---

## Support

For questions, issues, or contributions:

- **GitHub Issues:** [github.com/AnthusAI/Plexus/issues](https://github.com/AnthusAI/Plexus/issues)
- **Documentation:** [plexus.docs.anthus.ai](https://plexus.docs.anthus.ai)
- **Email:** support@anthus.ai

---

*Document Version: 4.0.0*
*Last Updated: 2025-12-04*
