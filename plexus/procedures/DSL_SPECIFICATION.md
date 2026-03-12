# Procedure DSL Specification v4

## Overview

The Procedure DSL enables defining agentic workflows as configuration. It combines declarative YAML for component definitions with embedded Lua for orchestration logic.

**Design Philosophy:**
- **YAML declares components** — agents, prompts, tools, filters, stages
- **Lua defines orchestration** — the actual workflow control flow
- **High-level primitives** — operations like `Worker.turn()` hide LLM mechanics
- **Uniform recursion** — a procedure invoked by another procedure works identically to a top-level procedure
- **Human-in-the-loop** — first-class support for human interaction, approval, and oversight
- **Built-in reliability** — retries, validation, and error handling under the hood

**Key Principles:**

1. **Uniform Recursion** — A procedure is a procedure, whether invoked externally or by another procedure. Same params, outputs, prompts, async capabilities everywhere.

2. **Human-in-the-Loop** — Procedures can request human approval, input, or review. Humans can monitor, intervene, and collaborate with running procedures.

---

## Document Structure

```yaml
name: procedure_name
version: 1.0.0
description: Human-readable description

# Parameter schema (validated before execution)
params:
  param_name:
    type: string
    required: true

# Output schema (validated after execution)
outputs:
  result_name:
    type: string
    required: true

# Summarization prompts
return_prompt: |
  Summarize your work...
error_prompt: |
  Explain what went wrong...
status_prompt: |
  Report your progress...

# Execution control
async: true
max_depth: 5
max_turns: 50

# Validation before execution
guards:
  - |
    return true

# Human-in-the-loop interaction points (optional)
hitl:
  interaction_name:
    type: approval | input | review
    message: "..."
    timeout: 3600

# Required dependencies
dependencies:
  tools:
    - tool_name
  procedures:
    - other_procedure_name

# Prompt templates
prompts:
  template_name: |
    Template content...

# Inline procedure definitions
procedures:
  helper_name:
    # Full procedure definition...

# Agent definitions
agents:
  agent_name:
    # Agent configuration...

# Stage definitions
stages:
  - stage_name

# Orchestration logic
workflow: |
  -- Lua code
```

---

## Parameters

Parameter schema defines what the procedure accepts. Validated before execution.

```yaml
params:
  topic:
    type: string
    required: true
    description: "The topic to research"
    
  depth:
    type: string
    enum: [shallow, deep]
    default: shallow
    
  max_results:
    type: number
    default: 10
    
  include_sources:
    type: boolean
    default: true
```

**Type options:** `string`, `number`, `boolean`, `array`, `object`

Parameters are accessed in templates as `{params.topic}` and in Lua as `params.topic`.

---

## Outputs

Output schema defines what the procedure returns. Validated after execution.

```yaml
outputs:
  findings:
    type: string
    required: true
    description: "Research findings summary"
    
  confidence:
    type: string
    enum: [high, medium, low]
    required: true
    
  sources:
    type: array
    required: false
```

When `outputs:` is present:
1. Required fields are validated to exist
2. Types are checked
3. Only declared fields are returned (internal data stripped)

When `outputs:` is omitted, the workflow can return anything without validation.

---

## Summarization Prompts

These prompts control how the procedure communicates its results:

### `return_prompt:`

Injected when the procedure completes successfully. The agent does one final turn to generate a summary, which becomes the return value.

```yaml
return_prompt: |
  Summarize your work:
  - What was accomplished
  - Key findings or results
  - Any important notes for the caller
```

### `error_prompt:`

Injected when the procedure fails (exception or max iterations exceeded). The agent explains what went wrong.

```yaml
error_prompt: |
  The task could not be completed. Explain:
  - What you were attempting
  - What went wrong
  - Any partial progress made
```

### `status_prompt:`

Injected when a caller requests a status update (async procedures only). The agent reports current progress without stopping.

```yaml
status_prompt: |
  Provide a brief progress update:
  - What has been completed
  - What you're currently working on
  - Estimated remaining work
```

### Defaults

If not specified:

```yaml
return_prompt: |
  Summarize the result of your work concisely.

error_prompt: |
  Explain what went wrong and any partial progress made.

status_prompt: |
  Briefly describe your current progress and remaining work.
```

---

## Async and Recursion Settings

```yaml
# Enable async invocation (caller can spawn and continue)
async: true

# Maximum recursion depth (prevents infinite recursion)
max_depth: 5

# Maximum turns for this procedure
max_turns: 50

# Checkpoint interval for recovery (async only)
checkpoint_interval: 10
```

---

## Execution Contexts

Procedures run identically in two execution contexts:

### Local Execution Context

For development and simple deployments:

- Checkpoints stored in database (ChatMessage with metadata)
- HITL waits create `PENDING_*` messages and exit
- Resume via polling loop or manual trigger
- Same procedure code, no changes needed

### Lambda Durable Execution Context

For production deployments on AWS:

- Uses AWS Lambda Durable Functions SDK
- Native checkpoint/replay mechanism
- HITL waits use Lambda callbacks (zero compute cost while waiting)
- Automatic retry with configurable backoff
- Executions can span up to 1 year

### Abstraction Layer

The runtime provides an `ExecutionContext` that abstracts over both backends:

```
┌─────────────────────────────────────────────┐
│           Procedure DSL (Lua)               │
│  Worker.turn() / Human.approve() / etc.     │
└─────────────────────┬───────────────────────┘
                      │
          ┌───────────┴───────────┐
          │   ExecutionContext    │
          │      (Protocol)       │
          └───────────┬───────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────────┐     ┌───────────────────┐
│ LocalExecution    │     │ DurableExecution  │
│ Context           │     │ Context           │
├───────────────────┤     ├───────────────────┤
│ - DB checkpoints  │     │ - Lambda SDK      │
│ - Manual resume   │     │ - Native suspend  │
│ - Polling loop    │     │ - Callback API    │
└───────────────────┘     └───────────────────┘
```

### Primitive Mapping

| DSL Primitive | Local Context | Lambda Durable Context |
|---------------|---------------|------------------------|
| `Worker.turn()` | DB checkpoint before/after | `context.step()` |
| `Human.approve()` | Create PENDING_*, exit, await RESPONSE | `context.create_callback()` + `callback.result()` |
| `Human.input()` | Create PENDING_*, exit, await RESPONSE | `context.create_callback()` + `callback.result()` |
| `Human.review()` | Create PENDING_*, exit, await RESPONSE | `context.create_callback()` + `callback.result()` |
| `Sleep(seconds)` | DB checkpoint, exit, resume after delay | `context.wait(Duration.from_seconds(n))` |
| `Procedure.spawn()` | Create child procedure record | `context.run_in_child_context()` |

### HITL Response Flow

**Local Context:**
```
1. Human.approve() called
2. Create ChatMessage with humanInteraction: PENDING_APPROVAL
3. Save Lua coroutine state to procedure metadata
4. Exit procedure (return control to runner)
5. [Human responds in UI → creates RESPONSE message]
6. Resume loop detects RESPONSE, reruns procedure
7. Procedure replays, Human.approve() returns the response value
```

**Lambda Durable Context:**
```
1. Human.approve() called
2. context.create_callback() → gets callback_id
3. Create ChatMessage with humanInteraction: PENDING_APPROVAL, callback_id in metadata
4. callback.result() suspends Lambda (zero cost)
5. [Human responds in UI → calls SendDurableExecutionCallbackSuccess API]
6. Lambda resumes automatically
7. callback.result() returns the response value
```

### Writing Portable Procedures

Procedures are automatically portable. The runtime handles the abstraction:

```lua
-- This works identically in both contexts
local approved = Human.approve({
  message = "Deploy to production?",
  timeout = 3600,
  default = false
})

if approved then
  deploy()
end
```

No conditional logic needed. The execution context handles:
- How to persist the pending request
- How to suspend execution
- How to resume when response arrives
- How to return the value to the Lua code

---

## Guards

Validation that runs before the procedure executes:

```yaml
guards:
  - |
    if not File.exists(params.file_path) then
      return false, "File not found: " .. params.file_path
    end
    return true
    
  - |
    if params.depth > 10 then
      return false, "Depth cannot exceed 10"
    end
    return true
```

Guards return `true` to proceed or `false, "error message"` to abort.

---

## Dependencies

Validated before any execution:

```yaml
dependencies:
  tools:
    - web_search
    - read_document
  procedures:
    - researcher
    - analyzer
```

If any dependency is missing, the procedure fails fast with a clear error.

---

## Template Variable Namespaces

| Namespace | Source | Example |
|-----------|--------|---------|
| `params` | Input parameters | `{params.topic}` |
| `outputs` | (In return_prompt) Final values | `{outputs.findings}` |
| `context` | Runtime context from caller | `{context.parent_id}` |
| `state` | Mutable procedure state | `{state.items_processed}` |
| `prepared` | Output of agent's `prepare` hook | `{prepared.file_contents}` |
| `env` | Environment variables | `{env.API_KEY}` |

Templates are re-evaluated before each agent turn.

---

## Human-in-the-Loop (HITL)

Procedures can interact with human operators for approval, input, review, or notification.

### Message Classification

Every chat message has a `humanInteraction` classification that determines visibility and behavior:

| Value | Description | Blocks? | Response Expected? |
|-------|-------------|---------|-------------------|
| `INTERNAL` | Agent-only, hidden from human UI | No | No |
| `CHAT` | Normal human-AI conversation | No | Optional |
| `CHAT_ASSISTANT` | AI response in conversation | No | No |
| `NOTIFICATION` | FYI from procedure to human | No | No |
| `ALERT_INFO` | System info alert | No | No |
| `ALERT_WARNING` | System warning alert | No | No |
| `ALERT_ERROR` | System error alert | No | No |
| `ALERT_CRITICAL` | System critical alert | No | No |
| `PENDING_APPROVAL` | Waiting for yes/no | Yes | Yes |
| `PENDING_INPUT` | Waiting for free-form input | Yes | Yes |
| `PENDING_REVIEW` | Waiting for human review | Yes | Yes |
| `RESPONSE` | Human's response to pending request | No | No |
| `TIMED_OUT` | Request expired without response | No | No |
| `CANCELLED` | Request was cancelled | No | No |

**Usage patterns:**

- **Procedure internals:** `INTERNAL` — LLM reasoning, tool calls, intermediate steps
- **Human-AI chat:** `CHAT` / `CHAT_ASSISTANT` — conversational assistants
- **Procedure notifications:** `NOTIFICATION` — progress updates from workflows
- **System monitoring:** `ALERT_*` — devops alerts, resource warnings, errors
- **Interactive requests:** `PENDING_*` — approval gates, input requests, reviews

### HITL Primitives

#### Approval (Blocking)

Request yes/no approval from a human:

```lua
local approved = Human.approve({
  message = "Should I proceed with this operation?",
  context = operation_details,  -- Any table of relevant data for the human
  timeout = 3600,  -- seconds, nil = wait forever
  default = false  -- return value if timeout
})

if approved then
  perform_operation()
else
  Log.info("Operation cancelled by operator")
end
```

The `context` parameter accepts any table and is displayed to the human in the approval UI:

```lua
-- Example contexts
context = {action = "deploy", environment = "production", version = "2.1.0"}
context = {query = sql_statement, affected_rows = row_count}
context = {amount = transfer_amount, recipient = account_id}
```

#### Input (Blocking)

Request free-form input from a human:

```lua
local response = Human.input({
  message = "What topic should I research next?",
  placeholder = "Enter a topic...",  -- UI hint
  timeout = nil  -- wait forever
})

if response then
  Procedure.run("researcher", {topic = response})
else
  Log.warn("No input received, using default")
end
```

#### Review (Blocking)

Request human review of a work product:

```lua
local review = Human.review({
  message = "Please review this generated content",
  artifact = generated_content,
  artifact_type = "document",  -- document, code, config, score_promotion, etc.
  options = {
    {label = "Approve", type = "action"},
    {label = "Reject", type = "cancel"},
    {label = "Revise", type = "action"}
  },
  timeout = 86400  -- 24 hours
})

if review.decision == "Approve" then
  publish(generated_content)
elseif review.decision == "Revise" then
  -- Human provided feedback, retry with their input
  State.set("human_feedback", review.feedback)
else  -- "Reject"
  Log.warn("Content rejected", {feedback = review.feedback})
end
```

**Options format:**

Each option is a hash with at least a `label` key. The label becomes `review.decision`:

```lua
options = {
  {label = "Approve", type = "action"},     -- Primary action button
  {label = "Reject", type = "cancel"},      -- Cancel/destructive button  
  {label = "Request Changes", type = "action"}
}
-- review.decision will be "Approve", "Reject", or "Request Changes"
```

Additional keys can be added as needed for UI rendering.

**Response fields:**

```lua
review.decision        -- The label of the selected option
review.feedback        -- Optional text feedback from human
review.edited_artifact -- Optional: human's edited version of artifact
review.responded_at    -- ISO timestamp when human responded
```

Note: We don't track responder identity since users aren't first-class records in the schema.

#### Notification (Non-Blocking)

Send information to human without waiting:

```lua
Human.notify({
  message = "Starting phase 2: data processing",
  level = "info"  -- info, warning, error
})

Human.notify({
  message = "Found anomalies that may need attention",
  level = "warning",
  context = {
    anomaly_count = #anomalies,
    details = anomaly_summary
  }
})
```

#### Alert (Non-Blocking, System-Level)

Send system/devops alerts. Unlike other HITL primitives, alerts can be sent programmatically from anywhere—not just from within procedure workflows:

```lua
-- From within a procedure
System.alert({
  message = "Procedure exceeded memory threshold",
  level = "warning",  -- info, warning, error, critical
  source = "batch_processor",
  context = {
    procedure_id = context.procedure_id,
    memory_mb = current_memory,
    threshold_mb = memory_threshold
  }
})
```

```python
# From Python monitoring code (outside any procedure)
create_chat_message(
    session_id=monitoring_session_id,
    role="SYSTEM",
    content="Database connection pool exhausted",
    human_interaction="ALERT_ERROR",
    metadata={
        "source": "db_monitor",
        "pool_size": 100,
        "waiting_connections": 47
    }
)
```

Alert levels map to `humanInteraction` values:

| Level | humanInteraction |
|-------|------------------|
| `info` | `ALERT_INFO` |
| `warning` | `ALERT_WARNING` |
| `error` | `ALERT_ERROR` |
| `critical` | `ALERT_CRITICAL` |

This enables unified alert dashboards that show both AI procedure alerts and traditional system monitoring alerts in the same interface.

#### Escalation (Blocking)

Hand off to human entirely:

```lua
Human.escalate({
  message = "Unable to resolve this automatically",
  context = {
    attempts = State.get("resolution_attempts"),
    last_error = last_error,
    current_state = State.all()
  }
})
-- Procedure pauses until human resolves and resumes
```

### Declarative HITL Points

For predictable workflows, declare interaction points in YAML:

```yaml
hitl:
  review_draft:
    type: review
    message: "Please review the generated document"
    timeout: 86400
    options: [approve, edit, reject]
    
  confirm_publish:
    type: approval
    message: "Publish this document to production?"
    timeout: 3600
    default: false
    
  get_topic:
    type: input
    message: "What topic should be researched?"
    placeholder: "Enter topic..."
```

Reference in workflow:

```lua
-- Uses the declared configuration
local review = Human.review("review_draft", {artifact = draft})
local approved = Human.approve("confirm_publish")
local topic = Human.input("get_topic")
```

### Timeout Handling

```lua
local approved, timed_out = Human.approve({
  message = "Proceed?",
  timeout = 3600
})

if timed_out then
  Log.warn("Approval timed out, using default")
  -- approved contains the default value
end
```

Or with explicit timeout behavior:

```lua
local result = Human.approve({
  message = "Proceed?",
  timeout = 3600,
  on_timeout = "error"  -- "default", "error", or "retry"
})
-- If on_timeout = "error", throws exception on timeout
```

### HITL Stage Integration

When a procedure is waiting for human interaction, its stage reflects this:

```lua
Stage.set("processing")
do_work()

-- Procedure status becomes "waiting_for_human" during this call
local approved = Human.approve({message = "Continue?"})

Stage.set("finalizing")
```

Parent procedures can detect this:

```lua
local handle = Procedure.spawn("deployment", params)

local status = Procedure.status(handle)
if status.waiting_for_human then
  -- Maybe notify via Slack
  notify_channel("Deployment waiting for approval")
end
```

---

## Human-AI Chat (Non-Procedural)

The same `ChatSession` and `ChatMessage` infrastructure supports regular conversational AI assistants that aren't running procedure workflows.

### Chat Assistant Pattern

For interactive AI assistants (help bots, Q&A systems, general chat):

```
ChatSession:
  category: "assistant"
  status: ACTIVE
  
ChatMessage (human):
  role: USER
  humanInteraction: CHAT
  content: "How do I reset my password?"
  
ChatMessage (AI):
  role: ASSISTANT
  humanInteraction: CHAT_ASSISTANT
  content: "You can reset your password by..."
```

Key differences from procedure workflows:

- No `procedureId` on the session (or links to a simple non-workflow procedure)
- Messages use `CHAT` / `CHAT_ASSISTANT` visibility by default
- No stages, no workflow orchestration
- Simple request-response or multi-turn conversation

### Hybrid: Chat with Procedure Invocation

A chat assistant can invoke procedures on behalf of the user:

```
User (CHAT): "Generate a report on Q3 sales"

Assistant (CHAT_ASSISTANT): "I'll generate that report for you..."

-- Assistant spawns a procedure, which creates INTERNAL messages
-- When complete, assistant responds:

Assistant (CHAT_ASSISTANT): "Here's your Q3 sales report: [link]"
```

The procedure's internal messages stay `INTERNAL` while the chat remains natural.

---

## Inline Procedure Definitions

For convenience, procedures can be defined inline:

```yaml
name: coordinator
version: 1.0.0

procedures:
  researcher:
    description: "Researches a topic"
    
    params:
      query:
        type: string
        required: true
    
    outputs:
      findings:
        type: string
        required: true
    
    return_prompt: |
      Summarize your research findings.
    
    agents:
      worker:
        system_prompt: |
          Research: {params.query}
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

Inline procedures follow the **exact same structure** as top-level procedures.

---

## Agent Definitions

Agents are the cognitive workers within a procedure:

```yaml
agents:
  worker:
    prepare: |
      return {
        current_time = os.date(),
        data = load_context_data()
      }
    
    system_prompt: |
      You are processing: {params.task}
      Context: {prepared.data}
    
    initial_message: |
      Begin working on the task.
    
    tools:
      - search
      - analyze
      - researcher  # Another procedure
      - done
    
    filter:
      class: ComposedFilter
      chain:
        - class: TokenBudget
          max_tokens: 120000
        - class: LimitToolResults
          count: 2
    
    response:
      retries: 3
      retry_delay: 1.0
    
    max_turns: 50
```

When you declare an agent named `worker`, the primitive `Worker.turn()` becomes available in Lua.

---

## Invoking Procedures

Procedures can be invoked in multiple ways:

### As a Tool (Implicit)

```yaml
agents:
  coordinator:
    tools:
      - researcher  # Procedure name
```

### Explicit Synchronous

```lua
local result = Procedure.run("researcher", {query = "quantum computing"})
```

### Explicit Asynchronous

```lua
local handle = Procedure.spawn("researcher", {query = "quantum computing"})
local status = Procedure.status(handle)
local result = Procedure.wait(handle)
```

---

## Stages

Stages integrate with TaskStages monitoring:

```yaml
stages:
  - planning
  - executing
  - awaiting_human  # HITL wait
  - complete
```

```lua
Stage.set("planning")
Stage.advance("executing")
Stage.is("planning")  -- false
Stage.current()       -- "executing"
```

---

## Exception Handling

```lua
local ok, result = pcall(Worker.turn)
if not ok then
  Log.error("Failed: " .. tostring(result))
  return {success = false, error = result}
end
```

---

## Primitive Reference

### Procedure Primitives

```lua
Procedure.run(name, params)              -- Sync invocation
Procedure.spawn(name, params)            -- Async invocation
Procedure.status(handle)                 -- Get status
Procedure.wait(handle)                   -- Wait for completion
Procedure.wait(handle, {timeout = n})    -- Wait with timeout
Procedure.inject(handle, message)        -- Send guidance
Procedure.cancel(handle)                 -- Abort
Procedure.wait_any(handles)              -- Wait for first
Procedure.wait_all(handles)              -- Wait for all
Procedure.is_complete(handle)            -- Check completion
Procedure.all_complete(handles)          -- Check all complete
```

### Step Primitives

For checkpointing arbitrary operations (not agent turns):

```lua
-- Execute fn and checkpoint result. On replay, return cached result.
Step.run(name, fn)

-- Examples:
local champion = Step.run("load_champion", function()
  return Tools.plexus_get_score({score_id = params.score_id})
end)

local metrics = Step.run("evaluate_champion", function()
  return Tools.plexus_run_evaluation({
    score_id = params.score_id,
    version = "champion"
  })
end)

-- Named steps allow targeted cache clearing for testing
```

Step names must be unique within a procedure execution. Use descriptive names or append counters for loops:

```lua
for i, item in ipairs(items) do
  local result = Step.run("process_item_" .. i, function()
    return process(item)
  end)
end
```

### Checkpoint Control Primitives

For testing and debugging:

```lua
Checkpoint.clear_all()              -- Clear all checkpoints
Checkpoint.clear_after(name)        -- Clear this checkpoint and all after
Checkpoint.exists(name)             -- Check if checkpoint exists
Checkpoint.get(name)                -- Get cached value (or nil)
```

### Human Interaction Primitives

```lua
Human.approve({message, context, timeout, default, on_timeout})
-- Returns: boolean (approved or not)

Human.input({message, placeholder, timeout, default, on_timeout})
-- Returns: string (user input) or nil

Human.review({message, artifact, artifact_type, options, timeout})
-- Returns: {decision, feedback, edited_artifact, responded_at}

Human.notify({message, level, context})  -- level: info, warning, error
-- Returns: nil (non-blocking)

Human.escalate({message, context})
-- Blocks until human resolves

System.alert({message, level, source, context})  -- level: info, warning, error, critical
-- Returns: nil (non-blocking, can be called from anywhere)
```

### Agent Primitives

```lua
Worker.turn()
Worker.turn({inject = "..."})
response.content
response.tool_calls
```

### Session Primitives

```lua
Session.append({role, content})
Session.inject_system(text)
Session.clear()
Session.history()
Session.load_from_node(node)
Session.save_to_node(node)
```

### State Primitives

```lua
State.get(key)
State.get(key, default)
State.set(key, value)
State.increment(key)
State.append(key, value)
State.all()
```

### Stage Primitives

```lua
Stage.current()
Stage.set(name)
Stage.advance(name)
Stage.is(name)
Stage.history()
```

### Control Primitives

```lua
Stop.requested()
Stop.reason()
Tool.called(name)
Tool.last_result(name)
Tool.last_call(name)
Iterations.current()
Iterations.exceeded(n)
```

### Graph Primitives

```lua
GraphNode.root()
GraphNode.current()
GraphNode.create({...})
GraphNode.set_current(node)
node:children()
node:parent()
node:score()
node:metadata()
node:set_metadata(key, value)
```

### Utility Primitives

```lua
Log.debug/info/warn/error(msg)
Retry.with_backoff(fn, opts)
Sleep(seconds)
Json.encode(table)
Json.decode(string)
File.read(path)
File.write(path, contents)
File.exists(path)
```

---

## Example: HITL Workflow

```yaml
name: content_pipeline
version: 1.0.0
description: Generate and publish content with human oversight

params:
  topic:
    type: string
    required: true
  target:
    type: string
    enum: [blog, docs, internal]
    required: true

outputs:
  published:
    type: boolean
    required: true
  url:
    type: string
    required: false

hitl:
  review_content:
    type: review
    message: "Review the generated content before publishing"
    timeout: 86400
    options:
      - {label: "Approve", type: "action"}
      - {label: "Reject", type: "cancel"}
      - {label: "Revise", type: "action"}
    
  confirm_publish:
    type: approval
    message: "Publish to {params.target}?"
    timeout: 3600
    default: false

agents:
  writer:
    system_prompt: |
      You write content about: {params.topic}
      Target: {params.target}
    tools:
      - research
      - write_draft
      - done
    filter:
      class: StandardFilter

stages:
  - researching
  - writing
  - review
  - publishing
  - complete

workflow: |
  Stage.set("researching")
  Human.notify({
    message = "Starting content generation",
    level = "info",
    context = {topic = params.topic, target = params.target}
  })
  
  Stage.set("writing")
  repeat
    Writer.turn()
  until Tool.called("done") or Iterations.exceeded(20)
  
  local draft = State.get("draft")
  if not draft then
    return {published = false, error = "No draft generated"}
  end
  
  -- Human review
  Stage.set("review")
  local review = Human.review("review_content", {
    artifact = draft,
    artifact_type = "document"
  })
  
  if review.decision == "Reject" then
    Human.notify({
      message = "Content rejected",
      level = "warning",
      context = {feedback = review.feedback}
    })
    return {published = false, reason = "rejected"}
  elseif review.decision == "Revise" then
    -- Could loop back to writing with feedback
    State.set("revision_feedback", review.feedback)
    -- ... revision logic ...
  end
  
  local final_content = review.edited_artifact or draft
  
  -- Approval to publish
  Stage.set("publishing")
  local approved = Human.approve("confirm_publish")
  
  if not approved then
    return {published = false, reason = "not_approved"}
  end
  
  local url = Step.run("publish", function()
    return publish_content(final_content, params.target)
  end)
  
  Human.notify({
    message = "Content published successfully",
    level = "info",
    context = {url = url}
  })
  
  Stage.set("complete")
  return {published = true, url = url}
```

---

## Example: System Monitoring with Alerts

```yaml
name: batch_processor
version: 1.0.0

params:
  items:
    type: array
    required: true
  threshold:
    type: number
    default: 0.1

outputs:
  processed:
    type: number
    required: true
  failed:
    type: number
    required: true

stages:
  - processing
  - complete

workflow: |
  local processed = 0
  local failed = 0
  local total = #params.items
  
  Stage.set("processing")
  
  for i, item in ipairs(params.items) do
    local ok, result = pcall(process_item, item)
    
    if ok then
      processed = processed + 1
    else
      failed = failed + 1
      Log.error("Item failed", {index = i, error = result})
    end
    
    -- Progress notification every 100 items
    if i % 100 == 0 then
      Human.notify({
        message = "Processing progress: " .. i .. "/" .. total,
        level = "info"
      })
    end
    
    -- Alert if failure rate exceeds threshold
    local failure_rate = failed / i
    if failure_rate > params.threshold then
      System.alert({
        message = "Failure rate exceeded threshold",
        level = "warning",
        source = "batch_processor",
        context = {
          failure_rate = failure_rate,
          threshold = params.threshold,
          processed = i,
          failed = failed
        }
      })
      
      -- Ask human whether to continue
      local continue = Human.approve({
        message = "Failure rate is " .. (failure_rate * 100) .. "%. Continue processing?",
        default = false,
        timeout = 300
      })
      
      if not continue then
        break
      end
    end
  end
  
  Stage.set("complete")
  
  -- Final status
  local level = failed > 0 and "warning" or "info"
  Human.notify({
    message = "Batch processing complete",
    level = level,
    context = {processed = processed, failed = failed, total = total}
  })
  
  return {processed = processed, failed = failed}
```

---

---

---

## Example: Self-Optimizing Score System

A comprehensive example showing HITL with checkpointed tool calls, evaluation, and conditional retry:

```yaml
name: score_optimizer
version: 1.0.0
description: |
  Self-optimizing system that drafts new Score configurations,
  evaluates them against the champion, and requests approval
  to promote improvements.

params:
  score_id:
    type: string
    required: true
  improvement_threshold:
    type: number
    default: 0.05
  max_attempts:
    type: number
    default: 3

outputs:
  promoted:
    type: boolean
    required: true
  new_version_id:
    type: string
    required: false
  improvement:
    type: number
    required: false
  rejection_reason:
    type: string
    required: false

hitl:
  approval_to_promote:
    type: review
    message: "Review candidate Score performance and approve promotion"
    timeout: 86400
    options:
      - {label: "Approve", type: "action"}
      - {label: "Reject", type: "cancel"}
      - {label: "Revise", type: "action"}

stages:
  - analyzing
  - drafting
  - evaluating
  - awaiting_approval
  - promoting
  - complete

prompts:
  analysis_system: |
    You are a Score optimization specialist. Analyze the current 
    champion Score's performance and identify improvement opportunities.
    
    Score ID: {params.score_id}
    Champion metrics: {state.champion_metrics}
    Error patterns: {state.error_analysis}

  drafting_system: |
    Based on your analysis, draft an improved Score configuration.
    
    Analysis findings: {state.analysis_findings}
    Human feedback (if any): {state.human_feedback}
    
    Be conservative - small targeted improvements are better than
    sweeping changes.

agents:
  analyzer:
    system_prompt: prompts.analysis_system
    tools:
      - plexus_get_score
      - plexus_get_evaluation_metrics
      - plexus_analyze_errors
      - done
    max_turns: 20

  drafter:
    system_prompt: prompts.drafting_system
    tools:
      - plexus_draft_score_config
      - plexus_validate_config
      - done
    max_turns: 15

workflow: |
  local attempt = 1
  
  -----------------------------------------------------------------
  -- Evaluate champion FIRST (checkpointed, runs once)
  -----------------------------------------------------------------
  Stage.set("analyzing")
  
  State.set("champion_config", Step.run("load_champion", function()
    return Tools.plexus_get_score({score_id = params.score_id})
  end))
  
  -- Run fresh evaluation on champion (checkpointed)
  State.set("champion_metrics", Step.run("evaluate_champion", function()
    return Tools.plexus_run_evaluation({
      score_id = params.score_id,
      version = "champion",
      test_set = "validation"
    })
  end))
  
  State.set("error_analysis", Step.run("analyze_errors", function()
    return Tools.plexus_analyze_errors({
      score_id = params.score_id,
      limit = 100
    })
  end))
  
  while attempt <= params.max_attempts do
    Log.info("Optimization attempt " .. attempt)
    
    -- Agent analyzes the data
    repeat
      Analyzer.turn()
    until Tool.called("done") or Iterations.exceeded(20)
    
    State.set("analysis_findings", Tool.last_result("done"))
    
    -----------------------------------------------------------------
    -- Draft improved configuration
    -----------------------------------------------------------------
    Stage.set("drafting")
    
    repeat
      Drafter.turn()
    until Tool.called("done") or Iterations.exceeded(15)
    
    local candidate_config = Tool.last_result("plexus_draft_score_config")
    if not candidate_config then
      return {promoted = false, rejection_reason = "drafting_failed"}
    end
    
    State.set("candidate_config", candidate_config)
    
    -----------------------------------------------------------------
    -- Evaluate candidate (checkpointed per attempt)
    -----------------------------------------------------------------
    Stage.set("evaluating")
    
    local eval_result = Step.run("evaluate_candidate_" .. attempt, function()
      return Tools.plexus_run_evaluation({
        score_id = params.score_id,
        config = candidate_config,
        test_set = "validation"
      })
    end)
    
    State.set("candidate_metrics", eval_result.metrics)
    
    local comparison = Step.run("compare_" .. attempt, function()
      return Tools.plexus_compare_metrics({
        champion = State.get("champion_metrics"),
        candidate = eval_result.metrics
      })
    end)
    
    local improvement = comparison.improvement_percentage
    Log.info("Improvement: " .. (improvement * 100) .. "%")
    
    if improvement < params.improvement_threshold then
      if attempt < params.max_attempts then
        State.set("human_feedback", "Auto-retry: " .. 
          (improvement * 100) .. "% below threshold")
        attempt = attempt + 1
      else
        return {
          promoted = false,
          improvement = improvement,
          rejection_reason = "below_threshold"
        }
      end
    else
      -----------------------------------------------------------------
      -- Request human approval
      -----------------------------------------------------------------
      Stage.set("awaiting_approval")
      
      local review = Human.review("approval_to_promote", {
        artifact = {
          candidate_config = candidate_config,
          comparison = comparison,
          champion_metrics = State.get("champion_metrics"),
          candidate_metrics = State.get("candidate_metrics")
        },
        artifact_type = "score_promotion"
      })
      
      if review.decision == "Approve" then
        Stage.set("promoting")
        
        local result = Step.run("promote", function()
          return Tools.plexus_promote_score_version({
            score_id = params.score_id,
            config = candidate_config
          })
        end)
        
        Human.notify({
          message = "Score promoted to new version",
          level = "info",
          context = {version_id = result.version_id}
        })
        
        Stage.set("complete")
        return {
          promoted = true,
          new_version_id = result.version_id,
          improvement = improvement
        }
        
      elseif review.decision == "Revise" then
        State.set("human_feedback", review.feedback)
        if review.edited_artifact then
          State.set("candidate_config", review.edited_artifact)
        end
        attempt = attempt + 1
        
      else  -- "Reject"
        Stage.set("complete")
        return {
          promoted = false,
          improvement = improvement,
          rejection_reason = review.feedback or "rejected_by_human"
        }
      end
    end
  end
  
  Stage.set("complete")
  return {promoted = false, rejection_reason = "max_attempts_exhausted"}
```

**Key patterns demonstrated:**

1. **Checkpointed tool calls** — `Step.run()` ensures expensive operations (evaluations) run once
2. **Champion evaluation at start** — Fresh baseline before any optimization attempts
3. **Named checkpoints per attempt** — `"evaluate_candidate_" .. attempt` allows reruns of specific attempts
4. **Three-way review decision** — Approve, Reject, or Revise with feedback loop
5. **State persistence across HITL** — All intermediate data survives the approval wait
6. **Automatic retry below threshold** — Doesn't bother human if improvement is too small

---

## Idempotent Execution Model

Procedures are designed for idempotent re-execution. Running a procedure multiple times produces the same result, with completed work skipped via checkpoints.

### The Core Algorithm

```
procedure_run(procedure_id):
    1. Load procedure and its chat session
    
    2. Find any PENDING_* messages (approval/input/review)
    
    3. For each PENDING_* message:
       - Look for a RESPONSE message with parentMessageId pointing to it
       - If no response exists: EXIT (still waiting, nothing to do)
       - If response exists: That's our resume value
    
    4. If we have pending messages with no responses:
       - This is a no-op, exit immediately
    
    5. If we have responses OR no pending messages:
       - Execute/resume the workflow
       - Replay completed checkpoints (return stored values)
       - Continue from where we left off
    
    6. Execute until:
       - Completion → mark complete, exit
       - HITL event → create PENDING_* message, checkpoint, exit
       - Error → handle per error_prompt, exit
```

### Checkpoint Storage

All checkpoints are stored in the `Procedure.metadata` field as JSON:

```yaml
# Procedure.metadata structure
checkpoints:
  load_champion:
    result: {config: {...}, version: "v2.3"}
    completed_at: "2024-12-04T10:00:00Z"
    
  run_evaluation_1:
    result: {metrics: {...}, evaluation_id: "eval_123"}
    completed_at: "2024-12-04T10:05:00Z"
    
  compare_metrics_1:
    result: {improvement_percentage: 0.08, ...}
    completed_at: "2024-12-04T10:05:30Z"

state:
  champion_config: {...}
  champion_metrics: {accuracy: 0.847, ...}
  candidate_config: {...}
  attempt: 2

lua_state:
  # Serialized coroutine position for resume
  checkpoint_index: 5
```

**Why procedure metadata:**
- Single record to load/save
- Atomic updates
- No additional tables or indexes needed
- Simple to inspect and debug

**Flushing checkpoints for testing:**

```bash
# Clear all checkpoints (restart from beginning)
plexus procedure reset <procedure_id>

# Clear checkpoints after a specific point
plexus procedure reset <procedure_id> --after "run_evaluation_1"

# Clear and rerun
plexus procedure reset <procedure_id> && plexus procedure run <procedure_id>
```

```lua
-- Programmatic checkpoint control (for testing)
Checkpoint.clear_all()
Checkpoint.clear_after("step_name")
Checkpoint.exists("step_name")  -- returns boolean
```

### Replay Behavior

On re-execution:

```lua
-- First run: executes LLM call, stores result
local response = Worker.turn()  -- Checkpoint: turn_1

-- Second run (replay): returns stored result immediately
local response = Worker.turn()  -- Returns checkpoint turn_1's result

-- Continues to next uncompleted operation
local approved = Human.approve({message = "Continue?"})
-- If no response: exit
-- If response exists: return it and continue
```

### Determinism Requirements

Code between checkpoints must be deterministic:

```lua
-- GOOD: Deterministic
local items = params.items
for i, item in ipairs(items) do
  Worker.turn({inject = "Process: " .. item})
end

-- BAD: Non-deterministic (different on replay)
local items = fetch_items_from_api()  -- Might return different results!
for i, item in ipairs(items) do
  Worker.turn({inject = "Process: " .. item})
end

-- FIXED: Wrap non-deterministic operations in checkpointed steps
local items = Step.run("fetch_items", function()
  return fetch_items_from_api()
end)
for i, item in ipairs(items) do
  Worker.turn({inject = "Process: " .. item})
end
```

### Resume Strategies

**Local Context:**

```bash
# Manual single procedure
plexus procedure resume <procedure_id>

# Resume all with pending responses
plexus procedure resume-all

# Polling daemon
plexus procedure watch --interval 10s
```

**Lambda Durable Context:**

Automatic. Lambda handles suspend/resume via callbacks. No polling needed.

---

## Migration from v3

| v3 | v4 | Notes |
|----|-----|-------|
| (none) | `hitl:` section | New: declarative HITL points |
| (none) | `Human.*` primitives | New: HITL interaction |
| (none) | `System.alert()` | New: programmatic alerts |
| (none) | `Step.run()` | New: checkpointed arbitrary operations |
| (none) | `Checkpoint.*` | New: checkpoint control for testing |
| (none) | Execution Contexts | New: Local vs Lambda Durable abstraction |

All v3 procedures work unchanged in v4. HITL features are additive.

### v4.1 Clarifications

- **Checkpoint storage:** All in `Procedure.metadata`, not separate table
- **Review options:** Array of `{label, type}` hashes; label becomes decision value
- **Response fields:** `responded_at` timestamp included; no `responder_id` (no user records)
- **Step.run():** For checkpointing tool calls outside agent loops

---

## Summary

**Uniform Recursion:** Procedures work identically at all levels—same params, outputs, prompts, async, HITL.

**Human-in-the-Loop:** First-class primitives for approval, input, review, notification, and escalation.

**Message Classification:** Every message has a `humanInteraction` type controlling visibility and behavior.

**Declarative + Imperative:** Declare HITL points in YAML for documentation, invoke them in Lua for control.