# Chat Message System Documentation

## Overview

The Plexus dashboard includes a comprehensive message system for displaying chat conversations, system notifications, alerts, and interactive human-in-the-loop (HITL) prompts. This document provides an overview of the system architecture and how to use it.

## Quick Links

- **Specification**: [message-metadata-spec.md](./message-metadata-spec.md) - Complete message metadata format specification
- **Storybook Stories**:
  - `Chat/Chat Messages` - All message types showcase
  - `Chat/Interactive Messages` - Interactive variations (buttons, inputs)
  - `Chat/Metadata Specification Tests` - Validation tests for all metadata combinations
  - `Chat/Interaction Tests` - Automated interaction tests

## Architecture

### Component Hierarchy

```
ChatFeed (container with data fetching)
  └─ ChatFeedView (presentational)
       └─ For each message:
            ├─ Icon (role/type based)
            ├─ Badge (humanInteraction label)
            ├─ Timestamp
            └─ Content:
                 ├─ InteractiveMessage (PENDING_* only)
                 │    └─ RichMessageContent + Buttons + Inputs
                 └─ RichMessageContent (all other messages)
```

### Core Components

1. **ChatFeed** (`components/chat-feed.tsx`)
   - Container component with GraphQL data fetching
   - Real-time subscriptions for new messages
   - Filters INTERNAL messages by default

2. **ChatFeedView** (`components/chat-feed.tsx`)
   - Presentational component (Storybook-friendly)
   - Three-path rendering logic:
     - PENDING messages → InteractiveMessage
     - Messages with metadata → RichMessageContent
     - Legacy plain content → RichMessageContent

3. **RichMessageContent** (`components/ui/rich-message-content.tsx`)
   - Universal renderer for ALL message types
   - Supports markdown content
   - Supports collapsible sections
   - Used directly by notifications, alerts, chat messages

4. **InteractiveMessage** (`components/ui/interactive-message.tsx`)
   - Extends RichMessageContent for PENDING messages
   - Adds action buttons
   - Adds input fields (text and textarea)
   - Form state management

## Message Types

### Human Interaction Types

| Type | Description | Visual Style |
|------|-------------|--------------|
| `CHAT` | User message | User icon, neutral |
| `CHAT_ASSISTANT` | Assistant response | Assistant icon, neutral |
| `NOTIFICATION` | System notification | Info icon, neutral |
| `ALERT_INFO` | Informational alert | Info icon, blue |
| `ALERT_WARNING` | Warning alert | Warning icon, yellow/orange |
| `ALERT_ERROR` | Error alert | Error icon, red |
| `ALERT_CRITICAL` | Critical alert | Critical icon, dark red |
| `PENDING_APPROVAL` | Awaiting approval | Question icon, interactive |
| `PENDING_INPUT` | Awaiting input | Question icon, interactive |
| `PENDING_REVIEW` | Awaiting review | Question icon, interactive |
| `RESPONSE` | User response | Checkmark icon |
| `TIMED_OUT` | Timeout | Clock icon |
| `CANCELLED` | Cancelled | X icon |
| `INTERNAL` | Tool calls (hidden) | Hidden by default |

### Message Roles

- `USER` - Messages from the user
- `ASSISTANT` - Messages from the AI assistant
- `SYSTEM` - System-generated messages (notifications, alerts, prompts)
- `TOOL` - Tool calls and responses (usually INTERNAL)

## Metadata Format

### Basic Structure

```typescript
{
  content?: string                    // Main content (markdown)
  collapsibleSections?: [             // Expandable sections (ALL message types)
    {
      title: string                   // Always visible
      content: string                 // Markdown, shown when expanded
      defaultOpen?: boolean           // Start expanded (default: false)
    }
  ]
  buttons?: [                         // PENDING messages only
    {
      label: string                   // Button text
      value: string                   // Return value
      variant?: string                // Visual style
    }
  ]
  inputs?: [                          // PENDING messages only
    {
      name: string                    // Field name
      label: string                   // Field label
      placeholder?: string            // Example text
      type?: 'text' | 'textarea'      // Input type
      required?: boolean              // Show asterisk
      description?: string            // Help text
    }
  ]
}
```

### Examples

#### Simple Notification with Collapsible Details

```json
{
  "role": "SYSTEM",
  "humanInteraction": "NOTIFICATION",
  "metadata": {
    "content": "Evaluation completed successfully",
    "collapsibleSections": [
      {
        "title": "Detailed Results",
        "content": "**Accuracy**: 92.5%\n**Precision**: 90.3%"
      }
    ]
  }
}
```

#### Approval Request

```json
{
  "role": "SYSTEM",
  "humanInteraction": "PENDING_APPROVAL",
  "metadata": {
    "content": "Deploy configuration **v2.1.5** to production?",
    "buttons": [
      { "label": "Approve", "value": "approve", "variant": "default" },
      { "label": "Reject", "value": "reject", "variant": "destructive" }
    ]
  }
}
```

#### Input Request with Help

```json
{
  "role": "SYSTEM",
  "humanInteraction": "PENDING_INPUT",
  "metadata": {
    "content": "Configure evaluation parameters",
    "collapsibleSections": [
      {
        "title": "Help & Guidance",
        "content": "**Sample Size**: Number of items to process\n**Confidence**: Minimum threshold (0-1)"
      }
    ],
    "inputs": [
      {
        "name": "sample_size",
        "label": "Sample Size",
        "placeholder": "500",
        "required": true
      }
    ],
    "buttons": [
      { "label": "Run Evaluation", "value": "run" }
    ]
  }
}
```

## TypeScript Types

### Exported Interfaces

```typescript
// From components/chat-feed.tsx
export interface ChatMessage {
  id: string
  content: string               // Legacy field
  role: 'SYSTEM' | 'ASSISTANT' | 'USER' | 'TOOL'
  messageType?: 'MESSAGE' | 'TOOL_CALL' | 'TOOL_RESPONSE'
  humanInteraction?: string     // See types above
  toolName?: string
  procedureId?: string
  createdAt: string
  metadata?: any                // RichMessageMetadata | InteractiveMessageMetadata
}

// From components/ui/rich-message-content.tsx
export interface RichMessageMetadata {
  content?: string
  collapsibleSections?: CollapsibleSection[]
}

export interface CollapsibleSection {
  title: string
  content: string
  defaultOpen?: boolean
}

// From components/ui/interactive-message.tsx
export interface InteractiveMessageMetadata extends RichMessageMetadata {
  buttons?: MessageButton[]
  inputs?: InputField[]
}

export interface MessageButton {
  label: string
  value: string
  variant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'ghost'
}

export interface InputField {
  name: string
  label: string
  description?: string
  placeholder?: string
  type?: 'text' | 'textarea'
  required?: boolean
}
```

## Usage Guide

### Creating Messages in Python (Backend)

```python
from plexus.cli.procedure.chat_recorder import ChatRecorder

# Simple notification
recorder.record_system_message(
    "Evaluation started",
    human_interaction="NOTIFICATION"
)

# Notification with collapsible details
recorder.record_system_message(
    "",  # Empty string when using metadata
    human_interaction="NOTIFICATION",
    metadata={
        "content": "Evaluation completed",
        "collapsibleSections": [
            {
                "title": "Results",
                "content": "**Accuracy**: 89.2%\n**Precision**: 87.5%"
            }
        ]
    }
)

# Warning alert
recorder.record_system_message(
    "",
    human_interaction="ALERT_WARNING",
    metadata={
        "content": "Accuracy below target threshold",
        "collapsibleSections": [
            {
                "title": "Details",
                "content": "**Current**: 72%\n**Target**: 85%"
            }
        ]
    }
)

# Approval request
recorder.record_system_message(
    "",
    human_interaction="PENDING_APPROVAL",
    metadata={
        "content": "Deploy to production?",
        "buttons": [
            {"label": "Approve", "value": "approve", "variant": "default"},
            {"label": "Reject", "value": "reject", "variant": "destructive"}
        ]
    }
)

# Input request
recorder.record_system_message(
    "",
    human_interaction="PENDING_INPUT",
    metadata={
        "content": "Configure parameters",
        "inputs": [
            {
                "name": "sample_size",
                "label": "Sample Size",
                "placeholder": "500",
                "required": True
            }
        ],
        "buttons": [
            {"label": "Submit", "value": "submit"}
        ]
    }
)
```

### Using Components in React

```tsx
import { ChatFeed, ChatFeedView, type ChatMessage } from '@/components/chat-feed'

// Container with data fetching
function MyDashboard() {
  return <ChatFeed accountId={currentAccountId} />
}

// Presentational with mock data (Storybook)
function MyStory() {
  const messages: ChatMessage[] = [
    {
      id: '1',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: new Date().toISOString(),
      metadata: {
        content: 'Hello world',
        collapsibleSections: [
          { title: 'Details', content: 'More info' }
        ]
      }
    }
  ]

  return <ChatFeedView messages={messages} />
}
```

## Testing

### Storybook Stories

Run Storybook to see all message variations:

```bash
npm run storybook
```

Navigate to:
- **Chat/Chat Messages** - Visual showcase of all message types
- **Chat/Interactive Messages** - All interactive variations
- **Chat/Metadata Specification Tests** - Comprehensive validation tests
- **Chat/Interaction Tests** - Automated interaction tests

### Interaction Tests

Interaction tests automatically verify:
- ✅ Collapsible sections expand/collapse correctly
- ✅ Multiple sections toggle independently
- ✅ Buttons are clickable and enabled
- ✅ Input fields accept text
- ✅ Textarea fields support multiline input
- ✅ Required fields show asterisks
- ✅ Keyboard navigation works (Tab key)
- ✅ Collapsible sections work alongside buttons/inputs

Run interaction tests:

```bash
npm run test-storybook
```

## Validation Rules

### Content Requirements

- Either `content` OR `metadata` must be present (not both empty)
- If using collapsible sections, each must have `title` and `content`
- If using buttons, each must have `label` and `value`
- If using inputs, each must have `name` and `label`

### Interactive Messages

- `PENDING_APPROVAL` should have ≥1 button
- `PENDING_INPUT` should have ≥1 input field and ≥1 button
- `PENDING_REVIEW` should have ≥1 button

### Content Constraints

- Section titles: concise, ~50 chars max recommended
- Button labels: clear and action-oriented, ~20 chars max recommended
- Input placeholders: provide examples or guidance
- All content fields support GitHub-flavored markdown

## Backward Compatibility

The system maintains full backward compatibility:

- ✅ Messages with only `content` field (no `metadata`) render correctly
- ✅ Both `content` and `metadata.content` can coexist
- ✅ Legacy messages without `humanInteraction` still render
- ✅ INTERNAL tool messages filtered by default but can be shown

## Common Patterns

### Progress Updates

```python
# Initial notification
recorder.record_system_message(
    "Starting evaluation...",
    human_interaction="NOTIFICATION"
)

# Progress notification
recorder.record_system_message(
    "Processing: 50% complete",
    human_interaction="NOTIFICATION"
)

# Completion with results
recorder.record_system_message(
    "",
    human_interaction="NOTIFICATION",
    metadata={
        "content": "Evaluation completed successfully",
        "collapsibleSections": [
            {"title": "Results", "content": "**Accuracy**: 92.5%"}
        ]
    }
)
```

### Error Handling

```python
# Try operation
try:
    result = run_evaluation()
except Exception as e:
    # Record error with details
    recorder.record_system_message(
        "",
        human_interaction="ALERT_ERROR",
        metadata={
            "content": f"Error: {str(e)}",
            "collapsibleSections": [
                {"title": "Stack Trace", "content": traceback.format_exc()}
            ]
        }
    )
```

### Multi-Step Workflows

```python
# Step 1: Inform
recorder.record_system_message(
    "Starting optimization workflow",
    human_interaction="NOTIFICATION"
)

# Step 2: Request approval
recorder.record_system_message(
    "",
    human_interaction="PENDING_APPROVAL",
    metadata={
        "content": "Should I proceed with optimization?",
        "collapsibleSections": [
            {"title": "Plan", "content": "- Adjust parameters\n- Run test\n- Deploy"}
        ],
        "buttons": [
            {"label": "Proceed", "value": "proceed"},
            {"label": "Cancel", "value": "cancel"}
        ]
    }
)

# Step 3: After approval, request parameters
recorder.record_system_message(
    "",
    human_interaction="PENDING_INPUT",
    metadata={
        "content": "Configure optimization parameters",
        "inputs": [
            {"name": "target", "label": "Target Accuracy", "required": True}
        ],
        "buttons": [{"label": "Start", "value": "start"}]
    }
)
```

## Troubleshooting

### Messages not appearing

1. Check `humanInteraction` field - INTERNAL messages are hidden by default
2. Verify `accountId` is set correctly in ChatMessage
3. Check browser console for subscription errors
4. Verify GraphQL schema includes `accountId` field and GSI

### Collapsible sections not working

1. Ensure `metadata.collapsibleSections` is an array
2. Each section must have `title` and `content` strings
3. Check browser console for React errors

### Buttons not clickable

1. Verify `humanInteraction` is one of: PENDING_APPROVAL, PENDING_INPUT, PENDING_REVIEW
2. Check that `buttons` array is in `metadata` object
3. Each button needs `label` and `value` properties

### Markdown not rendering

1. Content must be in `metadata.content` or legacy `content` field
2. Use GitHub-flavored markdown syntax
3. Code blocks need triple backticks with language: \`\`\`python

## Future Enhancements

Potential improvements to consider:

- [ ] Message reactions/acknowledgements
- [ ] Message threading/replies
- [ ] Rich media attachments (images, files)
- [ ] Message search/filtering
- [ ] Export conversation history
- [ ] Message templates/snippets
- [ ] Custom message types with plugins
- [ ] Message scheduling/delayed delivery

## Support

For questions or issues:
1. Check the [specification](./message-metadata-spec.md)
2. Review Storybook stories for examples
3. Run interaction tests to validate behavior
4. Check browser console for errors
5. File GitHub issue with reproduction steps
