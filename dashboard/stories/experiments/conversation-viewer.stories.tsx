import type { Meta, StoryObj } from '@storybook/react'
import { ConversationViewer } from '@/components/ui/conversation-viewer'
import type { ChatMessage, ChatSession } from '@/components/ui/conversation-viewer'
import { Card } from '@/components/ui/card'

const meta: Meta<typeof ConversationViewer> = {
  title: 'Experiments/ConversationViewer',
  component: ConversationViewer,
  parameters: {
    layout: 'fullscreen',
    backgrounds: {
      default: 'card',
      values: [
        { name: 'card', value: 'hsl(var(--card))' },
        { name: 'background', value: 'hsl(var(--background))' },
      ],
    },
  },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="p-8 min-h-screen bg-card">
        <Card className="h-[600px] bg-background overflow-hidden">
          <Story />
        </Card>
      </div>
    ),
  ],
}

export default meta
type Story = StoryObj<typeof meta>

// Sample data for stories
const sampleSessions: ChatSession[] = [
  {
    id: 'session-1',
    name: 'Medication Review Analysis',
    status: 'COMPLETED',
    createdAt: '2024-01-15T10:30:00Z',
    messageCount: 12,
  },
  {
    id: 'session-2',
    name: 'False Positive Investigation',
    status: 'ACTIVE',
    createdAt: '2024-01-15T11:45:00Z',
    messageCount: 8,
  },
  {
    id: 'session-3',
    name: 'Hypothesis Generation',
    status: 'ERROR',
    createdAt: '2024-01-15T12:15:00Z',
    messageCount: 3,
  },
  {
    id: 'session-4',
    name: 'Configuration Testing',
    status: 'ACTIVE',
    createdAt: '2024-01-15T13:00:00Z',
    messageCount: 15,
  },
]

const sampleMessages: ChatMessage[] = [
  {
    id: 'msg-1',
    content: `You are part of a hypothesis engine that is part of an automated experiment running process for optimizing scorecard score configurations in a reinforcement learning feedback loop system.

Your role is to analyze feedback patterns, identify improvement opportunities, and generate testable hypotheses for score configuration modifications.

## Score YAML Format

Scores in this system use a YAML configuration format with the following structure:

\`\`\`yaml
class: "StringComparison" 
parameters:
  comparison_type: "fuzzy_match"
  threshold: 0.85
  case_sensitive: false
\`\`\`

The \`class\` field determines the scoring algorithm, and \`parameters\` contains algorithm-specific configuration.`,
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    createdAt: '2024-01-15T10:30:00Z',
    sequenceNumber: 1,
  },
  {
    id: 'msg-2',
    content: 'Begin analyzing the current score configuration and feedback patterns to generate hypotheses. You have access to all the necessary context and tools.',
    role: 'USER',
    messageType: 'MESSAGE',
    createdAt: '2024-01-15T10:30:05Z',
    sequenceNumber: 2,
  },
  {
    id: 'msg-3',
    content: 'I\'ll start by examining the feedback patterns to understand how the current "Medication Review" score is performing. Let me get an overview of the confusion matrix and accuracy patterns.',
    role: 'ASSISTANT',
    messageType: 'MESSAGE',
    createdAt: '2024-01-15T10:30:10Z',
    sequenceNumber: 3,
  },
  {
    id: 'msg-4',
    content: 'plexus_feedback_analysis(scorecard_name="SelectQuote HCS Medium-Risk", score_name="Medication Review", days=30, output_format="json")',
    role: 'ASSISTANT',
    messageType: 'TOOL_CALL',
    toolName: 'plexus_feedback_analysis',
    toolParameters: {
      scorecard_name: "SelectQuote HCS Medium-Risk",
      score_name: "Medication Review",
      days: 30,
      output_format: "json"
    },
    createdAt: '2024-01-15T10:30:15Z',
    sequenceNumber: 4,
  },
  {
    id: 'msg-5',
    content: `{
  "context": {
    "scorecard_name": "SelectQuote HCS Medium-Risk",
    "score_name": "Medication Review",
    "analysis_period": "30 days",
    "total_feedback_items": 45
  },
  "confusion_matrix": {
    "true_positives": 15,
    "false_positives": 8,
    "true_negatives": 18,
    "false_negatives": 4
  },
  "metrics": {
    "accuracy": 0.733,
    "precision": 0.652,
    "recall": 0.789,
    "f1_score": 0.714,
    "specificity": 0.692
  },
  "feedback_patterns": {
    "most_common_false_positives": [
      "Routine medication refills flagged as requiring review",
      "Generic drug switches flagged unnecessarily"
    ],
    "most_common_false_negatives": [
      "Drug interaction warnings missed",
      "Dosage concerns not flagged"
    ]
  }
}`,
    role: 'TOOL',
    messageType: 'TOOL_RESPONSE',
    toolName: 'plexus_feedback_analysis',
    toolResponse: {
      context: {
        scorecard_name: "SelectQuote HCS Medium-Risk",
        score_name: "Medication Review",
        analysis_period: "30 days",
        total_feedback_items: 45
      },
      confusion_matrix: {
        true_positives: 15,
        false_positives: 8,
        true_negatives: 18,
        false_negatives: 4
      },
      metrics: {
        accuracy: 0.733,
        precision: 0.652,
        recall: 0.789,
        f1_score: 0.714,
        specificity: 0.692
      }
    },
    createdAt: '2024-01-15T10:30:20Z',
    sequenceNumber: 5,
  },
  {
    id: 'msg-6',
    content: `Excellent! The feedback analysis reveals some clear patterns. The current "Medication Review" score has:

**Performance Overview:**
- Accuracy: 73.3% (room for improvement)
- Precision: 65.2% (too many false positives)
- Recall: 78.9% (good sensitivity)

**Key Issues Identified:**
1. **False Positives (8 cases)**: Routine refills and generic switches being flagged unnecessarily
2. **False Negatives (4 cases)**: Missing drug interactions and dosage concerns

Let me investigate the false positive cases in detail to understand the specific patterns.`,
    role: 'ASSISTANT',
    messageType: 'MESSAGE',
    createdAt: '2024-01-15T10:30:25Z',
    sequenceNumber: 6,
  },
]

// Add sessionId to messages for filtering
const messagesWithSessions = sampleMessages.map(msg => ({
  ...msg,
  sessionId: 'session-1'
}))

export const Default: Story = {
  args: {
    sessions: sampleSessions,
    messages: messagesWithSessions,
    selectedSessionId: 'session-1',
    onSessionSelect: (sessionId) => console.log('Selected session:', sessionId),
  },
}

export const NoSessionSelected: Story = {
  args: {
    sessions: sampleSessions,
    messages: messagesWithSessions,
    selectedSessionId: undefined,
    onSessionSelect: (sessionId) => console.log('Selected session:', sessionId),
  },
}

export const ExpandedSidebar: Story = {
  args: {
    sessions: sampleSessions,
    messages: messagesWithSessions,
    selectedSessionId: 'session-1',
    onSessionSelect: (sessionId) => console.log('Selected session:', sessionId),
  },
  parameters: {
    docs: {
      description: {
        story: 'Click the expand button in the top-left to see the sidebar expanded with session names and details.',
      },
    },
  },
}

export const EmptySession: Story = {
  args: {
    sessions: sampleSessions,
    messages: [],
    selectedSessionId: 'session-3',
    onSessionSelect: (sessionId) => console.log('Selected session:', sessionId),
  },
}

export const ManySessions: Story = {
  args: {
    sessions: [
      ...sampleSessions,
      ...Array.from({ length: 10 }, (_, i) => ({
        id: `session-${i + 5}`,
        name: `Experiment Session ${i + 5}`,
        status: ['ACTIVE', 'COMPLETED', 'ERROR'][i % 3] as any,
        createdAt: new Date(Date.now() - i * 3600000).toISOString(),
        messageCount: Math.floor(Math.random() * 20) + 1,
      })),
    ],
    messages: messagesWithSessions,
    selectedSessionId: 'session-1',
    onSessionSelect: (sessionId) => console.log('Selected session:', sessionId),
  },
}

export const LongMessages: Story = {
  args: {
    sessions: sampleSessions,
    messages: [
      {
        id: 'long-msg-1',
        content: Array.from({ length: 20 }, (_, i) => 
          `This is line ${i + 1} of a very long message that should be truncated by the CollapsibleText component.`
        ).join('\n'),
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        createdAt: '2024-01-15T10:30:00Z',
        sequenceNumber: 1,
        sessionId: 'session-1',
      },
      {
        id: 'long-msg-2',
        content: 'This is a normal length message that should not be truncated.',
        role: 'USER',
        messageType: 'MESSAGE',
        createdAt: '2024-01-15T10:30:05Z',
        sequenceNumber: 2,
        sessionId: 'session-1',
      },
    ],
    selectedSessionId: 'session-1',
    onSessionSelect: (sessionId) => console.log('Selected session:', sessionId),
  },
}

export const ToolInteractions: Story = {
  args: {
    sessions: sampleSessions,
    messages: [
      {
        id: 'tool-msg-1',
        content: 'I need to analyze the feedback data for this scorecard.',
        role: 'ASSISTANT',
        messageType: 'MESSAGE',
        createdAt: '2024-01-15T10:30:00Z',
        sequenceNumber: 1,
        sessionId: 'session-2',
      },
      {
        id: 'tool-msg-2',
        content: 'plexus_feedback_find(scorecard_name="SelectQuote HCS", initial_value="Yes", final_value="No", limit=10)',
        role: 'ASSISTANT',
        messageType: 'TOOL_CALL',
        toolName: 'plexus_feedback_find',
        toolParameters: {
          scorecard_name: "SelectQuote HCS",
          initial_value: "Yes",
          final_value: "No",
          limit: 10
        },
        createdAt: '2024-01-15T10:30:05Z',
        sequenceNumber: 2,
        sessionId: 'session-2',
      },
      {
        id: 'tool-msg-3',
        content: JSON.stringify({
          feedback_items: [
            { id: 'item-1', text: 'Patient taking routine medication', initial: 'Yes', final: 'No', reason: 'Routine refill' },
            { id: 'item-2', text: 'Generic substitution available', initial: 'Yes', final: 'No', reason: 'Not requiring review' },
          ],
          total_found: 8,
          pattern_analysis: 'Most false positives are routine cases'
        }, null, 2),
        role: 'TOOL',
        messageType: 'TOOL_RESPONSE',
        toolName: 'plexus_feedback_find',
        toolResponse: {
          feedback_items: [
            { id: 'item-1', text: 'Patient taking routine medication', initial: 'Yes', final: 'No' },
            { id: 'item-2', text: 'Generic substitution available', initial: 'Yes', final: 'No' },
          ],
          total_found: 8
        },
        createdAt: '2024-01-15T10:30:10Z',
        sequenceNumber: 3,
        sessionId: 'session-2',
      },
    ],
    selectedSessionId: 'session-2',
    onSessionSelect: (sessionId) => console.log('Selected session:', sessionId),
  },
}