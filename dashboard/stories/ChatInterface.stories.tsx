import type { Meta, StoryObj } from '@storybook/react'
import { ChatInterfaceView } from '@/components/chat-interface'
import type { ChatMessage } from '@/components/chat-feed'
import { fn } from '@storybook/test'

const meta = {
  title: 'Chat/Components/Interface (Interactive)',
  component: ChatInterfaceView,
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
  args: {
    onSendMessage: fn(),
    onVoiceInput: fn(),
    onVoiceMode: fn(),
  },
} satisfies Meta<typeof ChatInterface>

export default meta
type Story = StoryObj<typeof meta>

// Mock messages for various scenarios
const mockConversation: ChatMessage[] = [
  {
    id: 'msg-1',
    content: 'Start a new evaluation run on the "CS3 Services v2" scorecard for the "Good Call" score.',
    role: 'USER',
    messageType: 'MESSAGE',
    humanInteraction: 'CHAT',
    createdAt: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
  },
  {
    id: 'msg-2',
    content: 'Certainly! I\'m starting a new evaluation run for the "CS3 Services v2" scorecard on the "Good Call" score.',
    role: 'ASSISTANT',
    messageType: 'MESSAGE',
    humanInteraction: 'CHAT_ASSISTANT',
    createdAt: new Date(Date.now() - 14 * 60 * 1000).toISOString(),
  },
  {
    id: 'msg-3',
    content: 'Evaluation started with 500 items',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'NOTIFICATION',
    createdAt: new Date(Date.now() - 13 * 60 * 1000).toISOString(),
  },
  {
    id: 'msg-4',
    content: 'What\'s the best accuracy on Pain Points on AW IB Sales?',
    role: 'USER',
    messageType: 'MESSAGE',
    humanInteraction: 'CHAT',
    createdAt: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
  },
  {
    id: 'msg-5',
    content: 'The best accuracy was from a version two days ago, at 92%. That was using a fine-tuned model.',
    role: 'ASSISTANT',
    messageType: 'MESSAGE',
    humanInteraction: 'CHAT_ASSISTANT',
    createdAt: new Date(Date.now() - 9 * 60 * 1000).toISOString(),
  },
  {
    id: 'msg-6',
    content: 'Evaluation completed: 92% accuracy',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'NOTIFICATION',
    createdAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  },
  {
    id: 'msg-7',
    content: 'Run that again with fresh data.',
    role: 'USER',
    messageType: 'MESSAGE',
    humanInteraction: 'CHAT',
    createdAt: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
  },
  {
    id: 'msg-8',
    content: 'Okay, I started a new run with fresh data from the last 24 hours.',
    role: 'ASSISTANT',
    messageType: 'MESSAGE',
    humanInteraction: 'CHAT_ASSISTANT',
    createdAt: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
  },
]

const alertMessages: ChatMessage[] = [
  {
    id: 'alert-1',
    content: 'System maintenance scheduled for tonight at 2 AM EST',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'ALERT_INFO',
    createdAt: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
  },
  {
    id: 'alert-2',
    content: 'Warning: API rate limit approaching - 85% of quota used',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'ALERT_WARNING',
    createdAt: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
  },
  {
    id: 'alert-3',
    content: 'Error: Failed to fetch scorecard data from external API. Retrying...',
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    humanInteraction: 'ALERT_ERROR',
    createdAt: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
  },
]

// Empty state
export const Empty: Story = {
  args: {
    messages: [],
    isLoading: false,
    placeholder: 'Type a message to get started...',
  },
}

// Loading state
export const Loading: Story = {
  args: {
    messages: [],
    isLoading: true,
  },
}

// Error state
export const Error: Story = {
  args: {
    messages: [],
    isLoading: false,
    error: 'Failed to connect to chat service',
  },
}

// Active conversation
export const ActiveConversation: Story = {
  args: {
    messages: mockConversation,
    isLoading: false,
  },
}

// With system alerts
export const WithAlerts: Story = {
  args: {
    messages: [...alertMessages, ...mockConversation.slice(-2)],
    isLoading: false,
  },
}

// Input disabled
export const InputDisabled: Story = {
  args: {
    messages: mockConversation,
    isLoading: false,
    disabled: true,
    placeholder: 'Chat is currently disabled',
  },
}

// Without voice buttons
export const NoVoiceButtons: Story = {
  args: {
    messages: mockConversation.slice(0, 4),
    isLoading: false,
    showVoiceButtons: false,
  },
}

// Read-only mode (no input at all)
export const ReadOnly: Story = {
  args: {
    messages: mockConversation,
    isLoading: false,
    showInput: false,
    showVoiceButtons: false,
  },
}

// Single user message waiting for response
export const WaitingForResponse: Story = {
  args: {
    messages: [
      ...mockConversation.slice(0, 6),
      {
        id: 'msg-waiting',
        content: 'Can you explain the confusion matrix results?',
        role: 'USER',
        messageType: 'MESSAGE',
        humanInteraction: 'CHAT',
        createdAt: new Date().toISOString(),
      },
    ],
    isLoading: false,
  },
}

// Complex conversation with markdown
export const WithMarkdownContent: Story = {
  args: {
    messages: [
      {
        id: 'msg-md-1',
        content: 'Can you analyze the performance metrics?',
        role: 'USER',
        messageType: 'MESSAGE',
        humanInteraction: 'CHAT',
        createdAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      },
      {
        id: 'msg-md-2',
        content: `# Performance Analysis

## Key Metrics
- **Accuracy**: 89.2%
- **Precision**: 87.5%
- **Recall**: 91.3%

## Findings
1. Strong recall indicates good detection of positive cases
2. Precision could be improved to reduce false positives
3. Overall performance is within acceptable range

### Recommendations
- Review false positive cases for pattern identification
- Consider adjusting classification threshold
- Add more training examples for edge cases`,
        role: 'ASSISTANT',
        messageType: 'MESSAGE',
        humanInteraction: 'CHAT_ASSISTANT',
        createdAt: new Date(Date.now() - 4 * 60 * 1000).toISOString(),
      },
    ],
    isLoading: false,
  },
}
