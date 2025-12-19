import type { Meta, StoryObj } from '@storybook/react'
import { ChatFeedView, type ChatMessage } from '@/components/chat-feed'

/**
 * Chat Messages - Comprehensive showcase of ALL message types
 *
 * This story shows every possible message variant that can appear in the chat system,
 * including standard chat messages, system notifications, alerts, and interactive messages.
 */
const meta = {
  title: 'Chat/Chat Messages',
  component: ChatFeedView,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="h-screen w-full bg-background">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ChatFeedView>

export default meta
type Story = StoryObj<typeof meta>

// Helper for consistent timestamps
const timestamp = (minutesAgo: number) =>
  new Date(Date.now() - minutesAgo * 60 * 1000).toISOString()

// ============================================================================
// STANDARD CHAT MESSAGES (humanInteraction: CHAT / CHAT_ASSISTANT)
// ============================================================================

const standardMessages: ChatMessage[] = [
  {
    id: 'chat-1',
    content: 'Start a new evaluation run on the "CS3 Services v2" scorecard.',
    role: 'USER',
    messageType: 'MESSAGE',
    humanInteraction: 'CHAT',
    createdAt: timestamp(10),
  },
  {
    id: 'chat-2',
    content: 'I\'ll start the evaluation for CS3 Services v2. This will analyze the current score configuration.',
    role: 'ASSISTANT',
    messageType: 'MESSAGE',
    humanInteraction: 'CHAT_ASSISTANT',
    createdAt: timestamp(9),
  },
]

export const StandardChat: Story = {
  args: {
    messages: standardMessages,
    isLoading: false,
  },
}

// ============================================================================
// NOTIFICATIONS (humanInteraction: NOTIFICATION)
// ============================================================================

const notificationMessages: ChatMessage[] = [
  {
    id: 'notif-1',
    content: 'Evaluation started with 500 items',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'NOTIFICATION',
    createdAt: timestamp(15),
  },
  {
    id: 'notif-2',
    content: 'Progress: 50% complete (250/500 items processed)',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'NOTIFICATION',
    createdAt: timestamp(12),
  },
  {
    id: 'notif-3',
    content: 'Evaluation completed: 92% accuracy achieved',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'NOTIFICATION',
    createdAt: timestamp(8),
  },
]

export const Notifications: Story = {
  args: {
    messages: notificationMessages,
    isLoading: false,
  },
}

// ============================================================================
// ALERTS (humanInteraction: ALERT_INFO, ALERT_WARNING, ALERT_ERROR, ALERT_CRITICAL)
// ============================================================================

const alertMessages: ChatMessage[] = [
  {
    id: 'alert-info',
    content: 'System maintenance scheduled for tonight at 2 AM EST. Evaluations may be temporarily paused.',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'ALERT_INFO',
    createdAt: timestamp(20),
  },
  {
    id: 'alert-warning',
    content: 'Low accuracy detected: 67.5% (below target threshold of 85%). Consider reviewing score configuration.',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'ALERT_WARNING',
    createdAt: timestamp(15),
  },
  {
    id: 'alert-error',
    content: 'Error: Failed to fetch scorecard data from external API. Retrying in 30 seconds...',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'ALERT_ERROR',
    createdAt: timestamp(10),
  },
  {
    id: 'alert-critical',
    content: 'CRITICAL: Database connection lost. All evaluation runs have been paused. Contact support immediately.',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'ALERT_CRITICAL',
    createdAt: timestamp(5),
  },
]

export const Alerts: Story = {
  args: {
    messages: alertMessages,
    isLoading: false,
  },
}

// ============================================================================
// PENDING ACTIONS (humanInteraction: PENDING_APPROVAL, PENDING_INPUT, PENDING_REVIEW)
// ============================================================================

const pendingMessages: ChatMessage[] = [
  {
    id: 'pending-approval',
    content: '', // Content in metadata
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'PENDING_APPROVAL',
    createdAt: timestamp(10),
    metadata: {
      content: 'Deploy new score configuration **v2.1.5** to production?\n\nThis will affect 3 active scorecards.',
      buttons: [
        { label: 'Approve', value: 'approve', variant: 'default' },
        { label: 'Reject', value: 'reject', variant: 'destructive' },
      ],
    },
  },
  {
    id: 'pending-input',
    content: '', // Content in metadata
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'PENDING_INPUT',
    createdAt: timestamp(8),
    metadata: {
      content: 'Please provide the target accuracy threshold for the **Good Call** score.',
      inputs: [
        {
          name: 'accuracy_threshold',
          label: 'Target Accuracy (%)',
          placeholder: 'e.g., 85',
          required: true,
        },
      ],
      buttons: [
        { label: 'Submit', value: 'submit', variant: 'default' },
        { label: 'Cancel', value: 'cancel', variant: 'outline' },
      ],
    },
  },
  {
    id: 'pending-review',
    content: '', // Content in metadata
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'PENDING_REVIEW',
    createdAt: timestamp(5),
    metadata: {
      content: '## Review Required\n\nFalse positive analysis identified **12 patterns**:\n\n- 5 greeting-related mismatches\n- 4 timing issues\n- 3 context problems',
      buttons: [
        { label: 'Approve Findings', value: 'approve', variant: 'default' },
        { label: 'Request Changes', value: 'changes', variant: 'secondary' },
        { label: 'Reject', value: 'reject', variant: 'destructive' },
      ],
    },
  },
]

export const PendingActions: Story = {
  args: {
    messages: pendingMessages,
    isLoading: false,
  },
}

// ============================================================================
// RESPONSE & STATUS (humanInteraction: RESPONSE, TIMED_OUT, CANCELLED)
// ============================================================================

const statusMessages: ChatMessage[] = [
  {
    id: 'response',
    content: 'Approval confirmed. Deploying configuration v2.1.5 to production...',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'RESPONSE',
    createdAt: timestamp(12),
  },
  {
    id: 'timed-out',
    content: 'Request timed out: No response received within 5 minutes. The evaluation has been queued for retry.',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'TIMED_OUT',
    createdAt: timestamp(8),
  },
  {
    id: 'cancelled',
    content: 'Evaluation cancelled by user. 250/500 items were processed before cancellation.',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'CANCELLED',
    createdAt: timestamp(3),
  },
]

export const StatusMessages: Story = {
  args: {
    messages: statusMessages,
    isLoading: false,
  },
}

// ============================================================================
// TOOL CALLS & RESPONSES (humanInteraction: INTERNAL - usually hidden)
// ============================================================================

const toolMessages: ChatMessage[] = [
  {
    id: 'tool-call',
    content: 'plexus_evaluation_run({"scorecard_id": "cs3-v2", "sample_size": 500})',
    role: 'TOOL',
    messageType: 'TOOL_CALL',
    toolName: 'plexus_evaluation_run',
    humanInteraction: 'INTERNAL',
    createdAt: timestamp(10),
  },
  {
    id: 'tool-response',
    content: '{"success": true, "evaluation_id": "eval-123", "status": "running"}',
    role: 'TOOL',
    messageType: 'TOOL_RESPONSE',
    toolName: 'plexus_evaluation_run',
    humanInteraction: 'INTERNAL',
    createdAt: timestamp(9),
  },
]

export const ToolMessages: Story = {
  args: {
    messages: toolMessages,
    isLoading: false,
  },
}

// ============================================================================
// MARKDOWN CONTENT - Rich formatting examples
// ============================================================================

const markdownMessages: ChatMessage[] = [
  {
    id: 'markdown',
    content: `# Analysis Summary

## Key Findings
- **Accuracy**: 89.2%
- **Precision**: 87.5%
- **Recall**: 91.3%

## Patterns Identified
1. Strong recall indicates good detection
2. Precision could be improved
3. Performance within acceptable range

### Code Example
\`\`\`python
def check_accuracy(results):
    return sum(r.correct for r in results) / len(results)
\`\`\`

### Next Steps
- Review false positive cases
- Adjust classification threshold
- Add more training examples`,
    role: 'ASSISTANT',
    messageType: 'MESSAGE',
    humanInteraction: 'CHAT_ASSISTANT',
    createdAt: timestamp(5),
  },
]

export const MarkdownContent: Story = {
  args: {
    messages: markdownMessages,
    isLoading: false,
  },
}

// ============================================================================
// INTERACTIVE MESSAGES IN CONTEXT - Showing how they appear in conversation
// ============================================================================

export const InteractiveConversation: Story = {
  args: {
    messages: [
      {
        id: 'conv-1',
        content: 'Start the optimization workflow for CS3 Services v2',
        role: 'USER',
        messageType: 'MESSAGE',
        humanInteraction: 'CHAT',
        createdAt: timestamp(20),
      },
      {
        id: 'conv-2',
        content: 'I\'ll start the optimization workflow. First, let me analyze the current configuration.',
        role: 'ASSISTANT',
        messageType: 'MESSAGE',
        humanInteraction: 'CHAT_ASSISTANT',
        createdAt: timestamp(19),
      },
      {
        id: 'conv-notif',
        content: 'Analysis complete: Current accuracy is 72%',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'NOTIFICATION',
        createdAt: timestamp(18),
      },
      {
        id: 'conv-warning',
        content: 'Warning: Accuracy below target threshold of 85%',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'ALERT_WARNING',
        createdAt: timestamp(17),
      },
      {
        id: 'conv-approval',
        content: '',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'PENDING_APPROVAL',
        createdAt: timestamp(15),
        metadata: {
          content: 'Should I proceed with optimization? This will:\n\n- Adjust scoring parameters\n- Run a test evaluation\n- Deploy if successful',
          buttons: [
            { label: 'Proceed', value: 'proceed', variant: 'default' },
            { label: 'Review First', value: 'review', variant: 'secondary' },
            { label: 'Cancel', value: 'cancel', variant: 'outline' },
          ],
        },
      },
      // Simulating user approved
      {
        id: 'conv-3',
        content: 'Proceed with optimization',
        role: 'USER',
        messageType: 'MESSAGE',
        humanInteraction: 'CHAT',
        createdAt: timestamp(12),
      },
      {
        id: 'conv-4',
        content: 'Starting optimization process...',
        role: 'ASSISTANT',
        messageType: 'MESSAGE',
        humanInteraction: 'CHAT_ASSISTANT',
        createdAt: timestamp(11),
      },
      {
        id: 'conv-input',
        content: '',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'PENDING_INPUT',
        createdAt: timestamp(8),
        metadata: {
          content: 'Please specify the optimization parameters:',
          inputs: [
            {
              name: 'target_accuracy',
              label: 'Target Accuracy (%)',
              placeholder: '85',
              required: true,
            },
            {
              name: 'sample_size',
              label: 'Test Sample Size',
              placeholder: '500',
              required: true,
            },
          ],
          buttons: [
            { label: 'Start Optimization', value: 'start', variant: 'default' },
            { label: 'Use Defaults', value: 'defaults', variant: 'secondary' },
          ],
        },
      },
    ],
    isLoading: false,
  },
}

// ============================================================================
// COMPLETE MESSAGE ZOO - Everything together
// ============================================================================

export const CompleteZoo: Story = {
  args: {
    messages: [
      // Standard chat
      {
        id: 'zoo-chat-1',
        content: 'Show me the current evaluation status',
        role: 'USER',
        messageType: 'MESSAGE',
        humanInteraction: 'CHAT',
        createdAt: timestamp(25),
      },
      // Notification
      {
        id: 'zoo-notif',
        content: 'Evaluation started with 500 items',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'NOTIFICATION',
        createdAt: timestamp(24),
      },
      // Info Alert
      {
        id: 'zoo-info',
        content: 'Info: Using cached scorecard configuration from 2 hours ago',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'ALERT_INFO',
        createdAt: timestamp(23),
      },
      // Assistant response
      {
        id: 'zoo-assistant',
        content: 'The evaluation is currently running. I\'ll notify you when it completes.',
        role: 'ASSISTANT',
        messageType: 'MESSAGE',
        humanInteraction: 'CHAT_ASSISTANT',
        createdAt: timestamp(22),
      },
      // Warning Alert
      {
        id: 'zoo-warning',
        content: 'Warning: Accuracy dropped to 72% - below target of 85%',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'ALERT_WARNING',
        createdAt: timestamp(20),
      },
      // Pending Input
      {
        id: 'zoo-pending',
        content: 'Input Required: Should we retry with adjusted parameters?',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'PENDING_INPUT',
        createdAt: timestamp(18),
      },
      // User response
      {
        id: 'zoo-chat-2',
        content: 'Yes, please retry with higher confidence threshold',
        role: 'USER',
        messageType: 'MESSAGE',
        humanInteraction: 'CHAT',
        createdAt: timestamp(15),
      },
      // Response confirmation
      {
        id: 'zoo-response',
        content: 'Confirmed. Restarting evaluation with adjusted parameters...',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'RESPONSE',
        createdAt: timestamp(14),
      },
      // Error Alert
      {
        id: 'zoo-error',
        content: 'Error: Failed to connect to external API. Retrying...',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'ALERT_ERROR',
        createdAt: timestamp(10),
      },
      // Notification
      {
        id: 'zoo-notif-2',
        content: 'Retry successful. Evaluation resumed.',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'NOTIFICATION',
        createdAt: timestamp(8),
      },
      // Completion
      {
        id: 'zoo-completion',
        content: 'Evaluation completed: 89% accuracy achieved!',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'NOTIFICATION',
        createdAt: timestamp(2),
      },
    ],
    isLoading: false,
  },
}

// ============================================================================
// RICH CONTENT - Non-interactive messages with collapsible sections
// ============================================================================

export const NotificationWithCollapsible: Story = {
  args: {
    messages: [{
      id: 'rich-notif',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(5),
      metadata: {
        content: 'Evaluation completed successfully',
        collapsibleSections: [
          {
            title: 'Detailed Results',
            content: '**Accuracy**: 92.5%\n**Precision**: 90.3%\n**Recall**: 94.1%\n\n**Sample Size**: 500 items',
          },
        ],
      },
    }],
    isLoading: false,
  },
}

export const AlertWithCollapsible: Story = {
  args: {
    messages: [{
      id: 'rich-alert',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'ALERT_WARNING',
      createdAt: timestamp(5),
      metadata: {
        content: 'Warning: Accuracy below target threshold',
        collapsibleSections: [
          {
            title: 'See Details',
            content: '**Current Accuracy**: 72%\n**Target**: 85%\n**Gap**: -13%\n\n**Affected Scorecards**:\n- CS3 Services v2\n- Healthcare Quality',
          },
        ],
      },
    }],
    isLoading: false,
  },
}

export const MultipleCollapsibleInNotification: Story = {
  args: {
    messages: [{
      id: 'rich-multi',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(5),
      metadata: {
        content: 'Weekly performance report generated',
        collapsibleSections: [
          {
            title: 'This Week',
            content: '**Evaluations Run**: 24\n**Average Accuracy**: 89.3%\n**Total Items**: 12,000',
          },
          {
            title: 'Compared to Last Week',
            content: '**Accuracy Change**: +2.1%\n**Volume Change**: +15%\n**Improvement**: ✓',
            defaultOpen: true,
          },
          {
            title: 'Top Performers',
            content: '1. Good Call Score: 94.2%\n2. Pain Points: 91.8%\n3. Quality Metrics: 88.5%',
          },
        ],
      },
    }],
    isLoading: false,
  },
}

export const AssistantMessageWithCollapsible: Story = {
  args: {
    messages: [{
      id: 'rich-assistant',
      content: '',
      role: 'ASSISTANT',
      messageType: 'MESSAGE',
      humanInteraction: 'CHAT_ASSISTANT',
      createdAt: timestamp(5),
      metadata: {
        content: 'I\'ve completed the analysis. Here are my findings.',
        collapsibleSections: [
          {
            title: 'Key Findings',
            content: '1. Strong performance on standard cases\n2. Weakness in edge case handling\n3. Opportunity for 10-15% improvement',
          },
          {
            title: 'Recommended Next Steps',
            content: '- Run focused evaluation on edge cases\n- Adjust classification threshold\n- Add 100 more training examples',
          },
        ],
      },
    }],
    isLoading: false,
  },
}
