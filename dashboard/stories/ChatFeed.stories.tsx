import type { Meta, StoryObj } from '@storybook/react'
import { ChatFeedView, type ChatMessage } from '@/components/chat-feed'

const meta = {
  title: 'Chat/Components/Feed (Read-Only)',
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

// Mock messages
const mockMessages: ChatMessage[] = [
  {
    id: 'msg-1',
    content: 'Starting evaluation for CS3 Services v2 scorecard on "Good Call" score',
    role: 'ASSISTANT',
    messageType: 'MESSAGE',
    humanInteraction: 'CHAT_ASSISTANT',
    procedureId: 'proc-123',
    createdAt: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
  },
  {
    id: 'msg-2',
    content: 'Evaluation progress: 42% complete',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'NOTIFICATION',
    procedureId: 'proc-123',
    createdAt: new Date(Date.now() - 8 * 60 * 1000).toISOString(),
  },
  {
    id: 'msg-3',
    content: 'Low accuracy detected: Current score is 67.5%, below target of 85%',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'ALERT_WARNING',
    procedureId: 'proc-123',
    createdAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  },
  {
    id: 'msg-4',
    content: 'Evaluation completed with 89.2% accuracy',
    role: 'ASSISTANT',
    messageType: 'MESSAGE',
    humanInteraction: 'CHAT_ASSISTANT',
    procedureId: 'proc-123',
    createdAt: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
  },
]

const notificationMessages: ChatMessage[] = [
  {
    id: 'notif-1',
    content: 'New batch of items has been processed',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'NOTIFICATION',
    procedureId: 'proc-batch',
    createdAt: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
  },
  {
    id: 'notif-2',
    content: 'Scorecard configuration updated successfully',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'NOTIFICATION',
    procedureId: 'proc-config',
    createdAt: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
  },
  {
    id: 'notif-3',
    content: 'Training job started for feedback integration',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'NOTIFICATION',
    procedureId: 'proc-train',
    createdAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  },
]

const alertMessages: ChatMessage[] = [
  {
    id: 'alert-1',
    content: 'System maintenance scheduled for tonight at 2 AM EST',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'ALERT_INFO',
    procedureId: 'proc-system',
    createdAt: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
  },
  {
    id: 'alert-2',
    content: 'Warning: API rate limit approaching - 85% of quota used',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'ALERT_WARNING',
    procedureId: 'proc-monitor',
    createdAt: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
  },
  {
    id: 'alert-3',
    content: 'Error: Failed to fetch scorecard data from external API. Retrying...',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'ALERT_ERROR',
    procedureId: 'proc-fetch',
    createdAt: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
  },
  {
    id: 'alert-4',
    content: 'CRITICAL: Database connection lost. All procedures halted.',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'ALERT_CRITICAL',
    procedureId: 'proc-db',
    createdAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  },
]

const pendingMessages: ChatMessage[] = [
  {
    id: 'pending-1',
    content: 'Please approve the new scorecard configuration before deployment',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'PENDING_APPROVAL',
    procedureId: 'proc-deploy',
    createdAt: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
  },
  {
    id: 'pending-2',
    content: 'Please provide the target accuracy threshold for the new score',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'PENDING_INPUT',
    procedureId: 'proc-config',
    createdAt: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
  },
  {
    id: 'pending-3',
    content: 'Please review the following 15 low-confidence predictions before proceeding',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'PENDING_REVIEW',
    procedureId: 'proc-review',
    createdAt: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
  },
]

const longContentMessages: ChatMessage[] = [
  {
    id: 'long-1',
    content: `# Evaluation Summary

## Results
- **Total Items**: 1,250
- **Accuracy**: 89.2%
- **Precision**: 87.5%
- **Recall**: 91.3%

## Confusion Matrix
- True Positives: 523
- True Negatives: 592
- False Positives: 72
- False Negatives: 63

## Analysis
The model performed well overall, with particularly strong recall. The false positive rate is slightly elevated in cases where customer sentiment is ambiguous.

### Recommendations:
1. Review false positive cases for pattern identification
2. Consider adjusting classification threshold
3. Add more training examples for ambiguous cases`,
    role: 'ASSISTANT',
    messageType: 'MESSAGE',
    humanInteraction: 'CHAT_ASSISTANT',
    procedureId: 'proc-eval',
    createdAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  },
]

export const Empty: Story = {
  args: {
    messages: [],
    isLoading: false,
  },
}

export const Loading: Story = {
  args: {
    messages: [],
    isLoading: true,
  },
}

export const Error: Story = {
  args: {
    messages: [],
    isLoading: false,
    error: 'Failed to connect to database',
  },
}

export const MixedMessages: Story = {
  args: {
    messages: mockMessages,
  },
}

export const NotificationsOnly: Story = {
  args: {
    messages: notificationMessages,
  },
}

export const Alerts: Story = {
  args: {
    messages: alertMessages,
  },
}

export const PendingActions: Story = {
  args: {
    messages: pendingMessages,
  },
}

export const LongContent: Story = {
  args: {
    messages: longContentMessages,
  },
}

export const CompleteFeed: Story = {
  args: {
    messages: [
      ...pendingMessages,
      ...alertMessages,
      ...notificationMessages,
      ...mockMessages,
      ...longContentMessages,
    ].sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()),
  },
}
