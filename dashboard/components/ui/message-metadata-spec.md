# Message Metadata Specification

## Overview

All chat messages in the Plexus dashboard support a flexible metadata structure for controlling message appearance, content formatting, and user interactions. This specification defines the universal message metadata format that works across all message types.

## Message Structure

Every chat message has the following base structure:

```typescript
interface ChatMessage {
  id: string
  content: string                    // Legacy plain content (still supported)
  role: 'SYSTEM' | 'ASSISTANT' | 'USER' | 'TOOL'
  messageType?: 'MESSAGE' | 'TOOL_CALL' | 'TOOL_RESPONSE'
  humanInteraction?: string          // See Human Interaction Types below
  toolName?: string
  procedureId?: string
  createdAt: string
  metadata?: MessageMetadata         // NEW: Rich content specification
}
```

## Metadata Format

The `metadata` field supports a universal format for all message types:

```typescript
interface MessageMetadata {
  // Main content (markdown supported, appears at top)
  content?: string

  // Collapsible sections (available to ALL message types)
  collapsibleSections?: CollapsibleSection[]

  // Interactive elements (ONLY for PENDING messages)
  buttons?: MessageButton[]
  inputs?: InputField[]
}
```

### Collapsible Sections

```typescript
interface CollapsibleSection {
  title: string           // Always visible at top
  content: string         // Markdown content, appears when expanded
  defaultOpen?: boolean   // Optional, defaults to false
}
```

**Visual Structure:**
```
Title (always visible)
[Content appears here when expanded]
─────────────────────
      ▼ / ▲
```

### Buttons (PENDING messages only)

```typescript
interface MessageButton {
  label: string                                           // Button text
  value: string                                          // Value returned on click
  variant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'ghost'
}
```

### Input Fields (PENDING messages only)

```typescript
interface InputField {
  name: string              // Field name in submitted data
  label: string             // Field label
  description?: string      // Help text below label
  placeholder?: string      // Input placeholder
  type?: 'text' | 'textarea'
  required?: boolean        // Show asterisk, enforce validation
}
```

## Human Interaction Types

The `humanInteraction` field determines message styling and behavior:

### Standard Chat
- `CHAT` - User message
- `CHAT_ASSISTANT` - Assistant response
- `INTERNAL` - Tool calls/responses (hidden by default)

### Notifications
- `NOTIFICATION` - System notifications (info icon, neutral color)

### Alerts
- `ALERT_INFO` - Informational alerts (blue)
- `ALERT_WARNING` - Warning alerts (yellow/orange)
- `ALERT_ERROR` - Error alerts (red)
- `ALERT_CRITICAL` - Critical alerts (dark red, emphasized)

### Pending Actions (Interactive)
- `PENDING_APPROVAL` - Awaiting user approval/decision
- `PENDING_INPUT` - Awaiting user input/form data
- `PENDING_REVIEW` - Awaiting user review/feedback

### Status Messages
- `RESPONSE` - User response to pending action
- `TIMED_OUT` - Action timed out
- `CANCELLED` - Action cancelled

## Usage Examples

### Simple Notification with Collapsible Details

```json
{
  "id": "msg-1",
  "content": "",
  "role": "SYSTEM",
  "messageType": "MESSAGE",
  "humanInteraction": "NOTIFICATION",
  "createdAt": "2024-01-15T10:30:00Z",
  "metadata": {
    "content": "Evaluation completed successfully",
    "collapsibleSections": [
      {
        "title": "Detailed Results",
        "content": "**Accuracy**: 92.5%\n**Precision**: 90.3%\n**Recall**: 94.1%"
      }
    ]
  }
}
```

### Alert with Multiple Collapsible Sections

```json
{
  "id": "msg-2",
  "content": "",
  "role": "SYSTEM",
  "messageType": "MESSAGE",
  "humanInteraction": "ALERT_WARNING",
  "createdAt": "2024-01-15T10:31:00Z",
  "metadata": {
    "content": "Warning: Accuracy below target threshold",
    "collapsibleSections": [
      {
        "title": "Current Metrics",
        "content": "**Current**: 72%\n**Target**: 85%\n**Gap**: -13%"
      },
      {
        "title": "Affected Scorecards",
        "content": "- CS3 Services v2\n- Healthcare Quality"
      }
    ]
  }
}
```

### Simple Approval Request

```json
{
  "id": "msg-3",
  "content": "",
  "role": "SYSTEM",
  "messageType": "MESSAGE",
  "humanInteraction": "PENDING_APPROVAL",
  "createdAt": "2024-01-15T10:32:00Z",
  "metadata": {
    "content": "Deploy new score configuration **v2.1.5** to production?",
    "buttons": [
      { "label": "Approve", "value": "approve", "variant": "default" },
      { "label": "Reject", "value": "reject", "variant": "destructive" }
    ]
  }
}
```

### Input Request with Collapsible Help

```json
{
  "id": "msg-4",
  "content": "",
  "role": "SYSTEM",
  "messageType": "MESSAGE",
  "humanInteraction": "PENDING_INPUT",
  "createdAt": "2024-01-15T10:33:00Z",
  "metadata": {
    "content": "Configure evaluation parameters",
    "collapsibleSections": [
      {
        "title": "Advanced Options",
        "content": "**Confidence Threshold**: Minimum confidence for predictions\n**Sample Size**: Number of items to process",
        "defaultOpen": true
      }
    ],
    "inputs": [
      {
        "name": "confidence",
        "label": "Confidence Threshold",
        "placeholder": "0.85",
        "required": true
      },
      {
        "name": "sample_size",
        "label": "Sample Size",
        "placeholder": "500",
        "required": true
      }
    ],
    "buttons": [
      { "label": "Start Evaluation", "value": "start" }
    ]
  }
}
```

### Review Request with Analysis

```json
{
  "id": "msg-5",
  "content": "",
  "role": "SYSTEM",
  "messageType": "MESSAGE",
  "humanInteraction": "PENDING_REVIEW",
  "createdAt": "2024-01-15T10:34:00Z",
  "metadata": {
    "content": "## Review Required\n\nFalse positive analysis identified **12 patterns**",
    "collapsibleSections": [
      {
        "title": "Pattern Breakdown",
        "content": "- 5 greeting-related mismatches\n- 4 timing issues\n- 3 context problems"
      },
      {
        "title": "Recommendations",
        "content": "1. Adjust greeting detection\n2. Improve context handling\n3. Add edge case examples"
      }
    ],
    "buttons": [
      { "label": "Approve Findings", "value": "approve", "variant": "default" },
      { "label": "Request Changes", "value": "changes", "variant": "secondary" }
    ]
  }
}
```

## Rendering Logic

The ChatFeed component uses this three-path rendering logic:

```typescript
{message.metadata && (message.humanInteraction === 'PENDING_APPROVAL' ||
                      message.humanInteraction === 'PENDING_INPUT' ||
                      message.humanInteraction === 'PENDING_REVIEW') ? (
  // Interactive messages (with buttons/inputs)
  <InteractiveMessage metadata={message.metadata} />
) : message.metadata ? (
  // Rich content messages (collapsible sections only)
  <RichMessageContent metadata={message.metadata} />
) : (
  // Legacy plain content
  <RichMessageContent content={message.content} />
)}
```

## Markdown Support

Both `metadata.content` and `collapsibleSections[].content` support GitHub-flavored markdown:

- **Bold**, *italic*, `code`
- Headers (##, ###)
- Lists (ordered and unordered)
- Links
- Code blocks with syntax highlighting
- Tables
- Blockquotes

## Validation Rules

### Required Fields
- `content` OR `metadata` must be present (not both empty)
- If using collapsible sections, each section must have `title` and `content`
- If using buttons, each button must have `label` and `value`
- If using inputs, each input must have `name` and `label`

### Interactive Messages
- `PENDING_APPROVAL` messages should have at least 1 button
- `PENDING_INPUT` messages should have at least 1 input field and 1 button
- `PENDING_REVIEW` messages should have at least 1 button

### Content Constraints
- Section titles should be concise (recommended < 50 characters)
- Button labels should be clear and action-oriented (recommended < 20 characters)
- Input placeholders should provide examples or guidance

## Backward Compatibility

The specification maintains full backward compatibility:

- Messages with only `content` field (no `metadata`) render as plain markdown
- Both `content` and `metadata.content` can be present simultaneously
- Legacy messages without `humanInteraction` field still render correctly
- Tool messages (INTERNAL) are filtered by default but can be shown if needed

## Testing

See Storybook stories for comprehensive visual testing:

- **Chat/Chat Messages** - All message types including collapsible sections
- **Chat/Interactive Messages** - All interactive variations (22+ stories)

Each story demonstrates:
- Correct visual rendering
- Proper metadata structure
- Expected user interactions
- Edge cases and variations
