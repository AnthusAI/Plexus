# Limerick Writer Example - Actual Output

This document shows the actual output from running the `limerick_writer.yaml` example.

## Execution Summary

**Session ID**: `08990326-38d4-40b5-abde-92156fb7f3cc`
**Procedure ID**: `02249572-9b0d-465e-aed9-2909632296a6`
**Status**: COMPLETED
**Iterations**: 1
**Total Messages**: 6

## Message Flow

### Messages 1-4: Internal Agent Conversation (HIDDEN 🔒)

These messages are marked as `humanInteraction: INTERNAL` and are **NOT visible** in the human chat feed. They're only visible in the procedures dashboard for debugging.

1. **System Message** - Agent system prompt
2. **User Message** - Initial kickoff message
3. **Assistant Response** - AI generated limerick
4. **Tool Call** - `done` tool execution

### Message 5: Start Notification (VISIBLE 👁️)
**Type**: Human-in-the-Loop notification
**Role**: SYSTEM
**humanInteraction**: NOTIFICATION

**Simple Content**: "Starting limerick generation"

**Rich Metadata**:
```json
{
  "content": "**Limerick Writer** is now running\\n\\nGenerating a creative limerick about: **neurosymbolic AI**"
}
```

**Rendered Output**:
> **Limerick Writer** is now running
>
> Generating a creative limerick about: **neurosymbolic AI**

### Message 6: Completion Notification (VISIBLE 👁️)
**Type**: Human-in-the-Loop notification with result
**Role**: SYSTEM
**humanInteraction**: NOTIFICATION

**Simple Content**: "Limerick complete!"

**Rich Metadata**:
```json
{
  "content": "**Limerick Writer** has finished\\n\\nThere once was an AI with a knack,\\nMixing neurons and symbols in its stack.\\nWith logic and flair,\\nIt solved puzzles with care,\\nA brainy machine on the right track!"
}
```

**Rendered Output**:

> **Limerick Writer** has finished
>
> There once was an AI with a knack,
> Mixing neurons and symbols in its stack.
> With logic and flair,
> It solved puzzles with care,
> A brainy machine on the right track!

## Key Features Demonstrated

### ✅ Basic Agent Loop
```lua
repeat
    Poet.turn()
until Tool.called("done") or Iterations.exceeded(10)
```
- Agent executes turns until completion signal
- Iteration limit prevents infinite loops
- Tool detection stops the loop

### ✅ HITL Messaging Integration
```lua
-- Start notification
Human.notify({
    message = "Starting limerick generation",
    content = "**Limerick Writer** is now running\\n\\nGenerating: **" .. topic .. "**"
})

-- Completion notification with result
Human.notify({
    message = "Limerick complete!",
    content = "**Limerick Writer** has finished\\n\\n" .. limerick
})
```
- Rich markdown content with formatting
- Direct presentation of results
- Clean separation of simple vs. rich content

### ✅ Graph Node Storage
```lua
local node = GraphNode.create(limerick, {
    type = "poem",
    genre = "limerick",
    topic = topic,
    author = "AI Poet"
})
```
- Structured storage of outputs
- Metadata tagging for retrieval
- Graph-based knowledge representation

### ✅ Output Validation
```yaml
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
  metadata:
    type: object
    required: false
```
- Enforces output schema compliance
- Automatic validation before completion
- Type checking for all fields

## User Experience

From a user's perspective in the **human chat feed**, they would see:

1. **Start**: A notification that the workflow is starting with the topic
2. **Processing**: Agent loop executes (typically very fast - 1 iteration)
3. **Completion**: A notification with the generated limerick displayed directly

This provides a clean, simple experience - just the essential information humans need to see.

## Key Takeaway: Message Visibility

**In the human chat feed, users only see:**
- ✅ Message #5: Start notification
- ✅ Message #6: Completion notification with the limerick

**Hidden from human view (visible only in procedures dashboard for debugging):**
- 🔒 Messages #1-4: Internal agent conversation (system, user, assistant, tool)

This separation ensures humans only see **intentional status updates**, while the full conversation trace remains available for debugging in the procedures dashboard.
