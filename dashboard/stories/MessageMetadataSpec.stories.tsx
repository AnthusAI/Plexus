import type { Meta, StoryObj } from '@storybook/react'
import { ChatFeedView, type ChatMessage } from '@/components/chat-feed'

/**
 * Message Metadata Specification Tests
 *
 * This story validates the complete message metadata specification.
 * Tests all combinations of metadata fields and ensures proper rendering.
 *
 * @see components/ui/message-metadata-spec.md
 */
const meta = {
  title: 'Chat/Metadata Specification Tests',
  component: ChatFeedView,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'Comprehensive tests validating the message metadata specification. See `components/ui/message-metadata-spec.md` for details.',
      },
    },
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

const timestamp = () => new Date().toISOString()

// ============================================================================
// VALIDATION: Content + Metadata Combinations
// ============================================================================

export const LegacyPlainContent: Story = {
  name: '✓ Legacy: Plain content only',
  args: {
    messages: [{
      id: 'legacy-1',
      content: 'This is a legacy message with only the content field. **Markdown** should work.',
      role: 'ASSISTANT',
      messageType: 'MESSAGE',
      humanInteraction: 'CHAT_ASSISTANT',
      createdAt: timestamp(),
      // No metadata
    }],
    isLoading: false,
  },
}

export const MetadataContentOnly: Story = {
  name: '✓ Metadata: Content only',
  args: {
    messages: [{
      id: 'meta-1',
      content: '',  // Empty legacy field
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(),
      metadata: {
        content: 'This is a notification using **metadata.content** instead of the legacy content field.',
      },
    }],
    isLoading: false,
  },
}

export const CollapsibleSectionsOnly: Story = {
  name: '✓ Metadata: Collapsible sections only',
  args: {
    messages: [{
      id: 'meta-2',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(),
      metadata: {
        // No content field
        collapsibleSections: [
          {
            title: 'View Details',
            content: 'This message has **no main content**, only a collapsible section.',
          },
        ],
      },
    }],
    isLoading: false,
  },
}

export const ContentPlusCollapsible: Story = {
  name: '✓ Metadata: Content + collapsible sections',
  args: {
    messages: [{
      id: 'meta-3',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(),
      metadata: {
        content: 'Main content appears at top',
        collapsibleSections: [
          {
            title: 'Additional Details',
            content: 'Collapsible content appears below main content.',
          },
        ],
      },
    }],
    isLoading: false,
  },
}

export const MultipleCollapsibleSections: Story = {
  name: '✓ Metadata: Multiple collapsible sections',
  args: {
    messages: [{
      id: 'meta-4',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(),
      metadata: {
        content: 'Message with multiple collapsible sections',
        collapsibleSections: [
          {
            title: 'Section 1',
            content: 'First section content',
          },
          {
            title: 'Section 2',
            content: 'Second section content',
          },
          {
            title: 'Section 3',
            content: 'Third section content',
          },
        ],
      },
    }],
    isLoading: false,
  },
}

export const DefaultOpenSection: Story = {
  name: '✓ Metadata: Collapsible section default open',
  args: {
    messages: [{
      id: 'meta-5',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(),
      metadata: {
        content: 'This section starts expanded',
        collapsibleSections: [
          {
            title: 'Details (Default Open)',
            content: 'This section has `defaultOpen: true` so it starts expanded.',
            defaultOpen: true,
          },
        ],
      },
    }],
    isLoading: false,
  },
}

// ============================================================================
// VALIDATION: Markdown Support
// ============================================================================

export const MarkdownInMainContent: Story = {
  name: '✓ Markdown: Main content',
  args: {
    messages: [{
      id: 'md-1',
      content: '',
      role: 'ASSISTANT',
      messageType: 'MESSAGE',
      humanInteraction: 'CHAT_ASSISTANT',
      createdAt: timestamp(),
      metadata: {
        content: `# Heading 1
## Heading 2
### Heading 3

**Bold** and *italic* and \`code\`

- Bullet 1
- Bullet 2
- Bullet 3

1. Numbered 1
2. Numbered 2
3. Numbered 3`,
      },
    }],
    isLoading: false,
  },
}

export const MarkdownInCollapsible: Story = {
  name: '✓ Markdown: Collapsible section content',
  args: {
    messages: [{
      id: 'md-2',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(),
      metadata: {
        content: 'Collapsible sections support full markdown',
        collapsibleSections: [
          {
            title: 'Markdown Examples',
            content: `**Bold**, *italic*, \`code\`

- Lists
- Work
- Great

\`\`\`python
def example():
    return "Code blocks too!"
\`\`\``,
          },
        ],
      },
    }],
    isLoading: false,
  },
}

// ============================================================================
// VALIDATION: All Message Types Support Rich Content
// ============================================================================

export const NotificationWithRichContent: Story = {
  name: '✓ Message Type: NOTIFICATION with metadata',
  args: {
    messages: [{
      id: 'type-1',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(),
      metadata: {
        content: 'Notification supports rich content',
        collapsibleSections: [
          { title: 'Details', content: 'Detailed notification info' },
        ],
      },
    }],
    isLoading: false,
  },
}

export const AlertInfoWithRichContent: Story = {
  name: '✓ Message Type: ALERT_INFO with metadata',
  args: {
    messages: [{
      id: 'type-2',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'ALERT_INFO',
      createdAt: timestamp(),
      metadata: {
        content: 'Info alert supports rich content',
        collapsibleSections: [
          { title: 'See More', content: 'Additional alert information' },
        ],
      },
    }],
    isLoading: false,
  },
}

export const AlertWarningWithRichContent: Story = {
  name: '✓ Message Type: ALERT_WARNING with metadata',
  args: {
    messages: [{
      id: 'type-3',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'ALERT_WARNING',
      createdAt: timestamp(),
      metadata: {
        content: 'Warning alert supports rich content',
        collapsibleSections: [
          { title: 'Warning Details', content: 'What caused this warning' },
        ],
      },
    }],
    isLoading: false,
  },
}

export const AlertErrorWithRichContent: Story = {
  name: '✓ Message Type: ALERT_ERROR with metadata',
  args: {
    messages: [{
      id: 'type-4',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'ALERT_ERROR',
      createdAt: timestamp(),
      metadata: {
        content: 'Error alert supports rich content',
        collapsibleSections: [
          { title: 'Error Details', content: 'Stack trace or error details' },
        ],
      },
    }],
    isLoading: false,
  },
}

export const AlertCriticalWithRichContent: Story = {
  name: '✓ Message Type: ALERT_CRITICAL with metadata',
  args: {
    messages: [{
      id: 'type-5',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'ALERT_CRITICAL',
      createdAt: timestamp(),
      metadata: {
        content: 'Critical alert supports rich content',
        collapsibleSections: [
          { title: 'Critical Details', content: 'Immediate action required' },
        ],
      },
    }],
    isLoading: false,
  },
}

export const AssistantWithRichContent: Story = {
  name: '✓ Message Type: CHAT_ASSISTANT with metadata',
  args: {
    messages: [{
      id: 'type-6',
      content: '',
      role: 'ASSISTANT',
      messageType: 'MESSAGE',
      humanInteraction: 'CHAT_ASSISTANT',
      createdAt: timestamp(),
      metadata: {
        content: 'Assistant responses support rich content',
        collapsibleSections: [
          { title: 'Technical Details', content: 'More in-depth explanation' },
        ],
      },
    }],
    isLoading: false,
  },
}

// ============================================================================
// VALIDATION: Interactive Messages
// ============================================================================

export const PendingApprovalBasic: Story = {
  name: '✓ Interactive: PENDING_APPROVAL basic',
  args: {
    messages: [{
      id: 'int-1',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_APPROVAL',
      createdAt: timestamp(),
      metadata: {
        content: 'Approve this action?',
        buttons: [
          { label: 'Approve', value: 'approve', variant: 'default' },
          { label: 'Reject', value: 'reject', variant: 'destructive' },
        ],
      },
    }],
    isLoading: false,
  },
}

export const PendingApprovalWithCollapsible: Story = {
  name: '✓ Interactive: PENDING_APPROVAL with collapsible',
  args: {
    messages: [{
      id: 'int-2',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_APPROVAL',
      createdAt: timestamp(),
      metadata: {
        content: 'Review and approve the changes',
        collapsibleSections: [
          {
            title: 'Change Details',
            content: 'Detailed list of changes to review',
          },
        ],
        buttons: [
          { label: 'Approve', value: 'approve', variant: 'default' },
          { label: 'Reject', value: 'reject', variant: 'destructive' },
        ],
      },
    }],
    isLoading: false,
  },
}

export const PendingInputBasic: Story = {
  name: '✓ Interactive: PENDING_INPUT basic',
  args: {
    messages: [{
      id: 'int-3',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_INPUT',
      createdAt: timestamp(),
      metadata: {
        content: 'Please provide the required information',
        inputs: [
          {
            name: 'value',
            label: 'Value',
            placeholder: 'Enter value',
            required: true,
          },
        ],
        buttons: [
          { label: 'Submit', value: 'submit', variant: 'default' },
        ],
      },
    }],
    isLoading: false,
  },
}

export const PendingInputWithCollapsible: Story = {
  name: '✓ Interactive: PENDING_INPUT with collapsible',
  args: {
    messages: [{
      id: 'int-4',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_INPUT',
      createdAt: timestamp(),
      metadata: {
        content: 'Configure the parameters',
        collapsibleSections: [
          {
            title: 'Help & Guidance',
            content: 'Information about what values to provide',
          },
        ],
        inputs: [
          {
            name: 'param1',
            label: 'Parameter 1',
            description: 'First parameter',
            placeholder: 'Value 1',
            required: true,
          },
          {
            name: 'param2',
            label: 'Parameter 2',
            description: 'Second parameter',
            placeholder: 'Value 2',
            type: 'textarea',
            required: false,
          },
        ],
        buttons: [
          { label: 'Submit', value: 'submit', variant: 'default' },
          { label: 'Cancel', value: 'cancel', variant: 'outline' },
        ],
      },
    }],
    isLoading: false,
  },
}

export const PendingReviewBasic: Story = {
  name: '✓ Interactive: PENDING_REVIEW basic',
  args: {
    messages: [{
      id: 'int-5',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_REVIEW',
      createdAt: timestamp(),
      metadata: {
        content: '## Review Required\n\nPlease review the following items',
        buttons: [
          { label: 'Approve', value: 'approve', variant: 'default' },
          { label: 'Request Changes', value: 'changes', variant: 'secondary' },
        ],
      },
    }],
    isLoading: false,
  },
}

export const PendingReviewWithCollapsible: Story = {
  name: '✓ Interactive: PENDING_REVIEW with collapsible',
  args: {
    messages: [{
      id: 'int-6',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_REVIEW',
      createdAt: timestamp(),
      metadata: {
        content: 'Review the analysis results',
        collapsibleSections: [
          {
            title: 'Detailed Analysis',
            content: '## Findings\n\n- Finding 1\n- Finding 2\n- Finding 3',
          },
          {
            title: 'Recommendations',
            content: '1. Recommendation 1\n2. Recommendation 2',
          },
        ],
        buttons: [
          { label: 'Approve Findings', value: 'approve', variant: 'default' },
          { label: 'Request Changes', value: 'changes', variant: 'secondary' },
          { label: 'Reject', value: 'reject', variant: 'destructive' },
        ],
      },
    }],
    isLoading: false,
  },
}

// ============================================================================
// VALIDATION: Edge Cases
// ============================================================================

export const EmptyMetadata: Story = {
  name: '✓ Edge Case: Empty metadata object',
  args: {
    messages: [{
      id: 'edge-1',
      content: 'Falls back to legacy content rendering',
      role: 'ASSISTANT',
      messageType: 'MESSAGE',
      humanInteraction: 'CHAT_ASSISTANT',
      createdAt: timestamp(),
      metadata: {
        // Empty metadata object
      },
    }],
    isLoading: false,
  },
}

export const VeryLongContent: Story = {
  name: '✓ Edge Case: Very long content',
  args: {
    messages: [{
      id: 'edge-2',
      content: '',
      role: 'ASSISTANT',
      messageType: 'MESSAGE',
      humanInteraction: 'CHAT_ASSISTANT',
      createdAt: timestamp(),
      metadata: {
        content: Array(20).fill('This is a very long message. ').join('') +
                 '\n\nLorem ipsum dolor sit amet, consectetur adipiscing elit. ' +
                 'Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. ' +
                 'Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.',
        collapsibleSections: [
          {
            title: 'Even More Content',
            content: Array(30).fill('Additional content here. ').join(''),
          },
        ],
      },
    }],
    isLoading: false,
  },
}

export const ManyButtons: Story = {
  name: '✓ Edge Case: Many buttons (wrapping)',
  args: {
    messages: [{
      id: 'edge-3',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_APPROVAL',
      createdAt: timestamp(),
      metadata: {
        content: 'Multiple choices (buttons should wrap)',
        buttons: Array.from({ length: 8 }, (_, i) => ({
          label: `Choice ${i + 1}`,
          value: `choice-${i + 1}`,
          variant: 'secondary' as const,
        })),
      },
    }],
    isLoading: false,
  },
}

export const ManyInputs: Story = {
  name: '✓ Edge Case: Many input fields',
  args: {
    messages: [{
      id: 'edge-4',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_INPUT',
      createdAt: timestamp(),
      metadata: {
        content: 'Complex form with many fields',
        inputs: [
          { name: 'field1', label: 'Field 1', required: true },
          { name: 'field2', label: 'Field 2', required: true },
          { name: 'field3', label: 'Field 3', required: false },
          { name: 'field4', label: 'Field 4', type: 'textarea' as const, required: false },
          { name: 'field5', label: 'Field 5', required: true },
        ],
        buttons: [
          { label: 'Submit', value: 'submit' },
        ],
      },
    }],
    isLoading: false,
  },
}

export const ManySections: Story = {
  name: '✓ Edge Case: Many collapsible sections',
  args: {
    messages: [{
      id: 'edge-5',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(),
      metadata: {
        content: 'Report with many sections',
        collapsibleSections: Array.from({ length: 10 }, (_, i) => ({
          title: `Section ${i + 1}`,
          content: `Content for section ${i + 1}`,
        })),
      },
    }],
    isLoading: false,
  },
}

// ============================================================================
// VALIDATION: Complete Conversation Flow
// ============================================================================

export const CompleteConversation: Story = {
  name: '✓ Integration: Complete conversation flow',
  args: {
    messages: [
      {
        id: 'conv-1',
        content: 'Start the optimization workflow',
        role: 'USER',
        messageType: 'MESSAGE',
        humanInteraction: 'CHAT',
        createdAt: new Date(Date.now() - 600000).toISOString(),
      },
      {
        id: 'conv-2',
        content: '',
        role: 'ASSISTANT',
        messageType: 'MESSAGE',
        humanInteraction: 'CHAT_ASSISTANT',
        createdAt: new Date(Date.now() - 590000).toISOString(),
        metadata: {
          content: "I'll start the optimization workflow. Let me analyze the current configuration.",
          collapsibleSections: [
            {
              title: 'Analysis Plan',
              content: '1. Fetch current configuration\n2. Run baseline evaluation\n3. Identify improvement opportunities',
            },
          ],
        },
      },
      {
        id: 'conv-3',
        content: '',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'NOTIFICATION',
        createdAt: new Date(Date.now() - 580000).toISOString(),
        metadata: {
          content: 'Baseline evaluation completed',
          collapsibleSections: [
            {
              title: 'Results',
              content: '**Accuracy**: 72%\n**Target**: 85%\n**Gap**: -13%',
            },
          ],
        },
      },
      {
        id: 'conv-4',
        content: '',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'ALERT_WARNING',
        createdAt: new Date(Date.now() - 570000).toISOString(),
        metadata: {
          content: 'Warning: Accuracy below target threshold',
        },
      },
      {
        id: 'conv-5',
        content: '',
        role: 'SYSTEM',
        messageType: 'MESSAGE',
        humanInteraction: 'PENDING_APPROVAL',
        createdAt: new Date(Date.now() - 560000).toISOString(),
        metadata: {
          content: 'Should I proceed with optimization?',
          collapsibleSections: [
            {
              title: 'Optimization Plan',
              content: '- Adjust scoring parameters\n- Run test evaluation\n- Deploy if successful',
            },
          ],
          buttons: [
            { label: 'Proceed', value: 'proceed', variant: 'default' },
            { label: 'Cancel', value: 'cancel', variant: 'outline' },
          ],
        },
      },
    ],
    isLoading: false,
  },
}
