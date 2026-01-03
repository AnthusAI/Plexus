import type { ChatMessage } from '@/components/chat-feed'

/**
 * Helper function to create timestamp relative to now
 */
function timestamp(minutesAgo: number = 0): string {
  const now = new Date('2024-01-15T10:00:00Z') // Fixed time for consistent documentation
  return new Date(now.getTime() - minutesAgo * 60 * 1000).toISOString()
}

/**
 * Pre-built example message data for documentation
 *
 * These are plain data objects that can be safely passed from server to client components.
 */
export const MessageExampleData = {
  /**
   * Simple approval workflow
   */
  simpleApproval: [
    {
      id: 'ex-1',
      content: '',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(5),
      metadata: {
        content: 'Analysis complete: accuracy at 72%, below target of 85%'
      }
    },
    {
      id: 'ex-2',
      content: '',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'PENDING_APPROVAL',
      createdAt: timestamp(3),
      metadata: {
        content: 'Should I proceed with optimization?',
        collapsibleSections: [
          {
            title: 'Optimization Plan',
            content: '- Adjust scoring parameters\n- Run test evaluation\n- Deploy if successful'
          }
        ],
        buttons: [
          { label: 'Proceed', value: 'proceed', variant: 'default' },
          { label: 'Cancel', value: 'cancel', variant: 'outline' }
        ]
      }
    }
  ] satisfies ChatMessage[],

  /**
   * Input request with context
   */
  inputRequest: [
    {
      id: 'ex-3',
      content: '',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'PENDING_INPUT',
      createdAt: timestamp(2),
      metadata: {
        content: 'Configure evaluation parameters',
        collapsibleSections: [
          {
            title: 'Help & Guidance',
            content: '**Sample Size**: Number of items to evaluate\n**Confidence**: Minimum threshold (0-1)'
          }
        ],
        inputs: [
          {
            name: 'sample_size',
            label: 'Sample Size',
            placeholder: '500',
            required: true
          },
          {
            name: 'confidence',
            label: 'Confidence Threshold',
            placeholder: '0.85',
            required: true
          }
        ],
        buttons: [
          { label: 'Start Evaluation', value: 'start', variant: 'default' }
        ]
      }
    }
  ] satisfies ChatMessage[],

  /**
   * Progress notifications
   */
  progressUpdates: [
    {
      id: 'ex-4',
      content: 'Starting batch processing',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(10)
    },
    {
      id: 'ex-5',
      content: '',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(7),
      metadata: {
        content: 'Processing: 50% complete',
        collapsibleSections: [
          {
            title: 'Progress Details',
            content: '**Processed**: 250 items\n**Remaining**: 250 items\n**Time elapsed**: 5 minutes'
          }
        ]
      }
    },
    {
      id: 'ex-6',
      content: 'Batch processing completed successfully',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(2)
    }
  ] satisfies ChatMessage[],

  /**
   * Alert severity levels
   */
  alertLevels: [
    {
      id: 'ex-7',
      content: 'System maintenance scheduled for tonight',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'ALERT_INFO',
      createdAt: timestamp(15)
    },
    {
      id: 'ex-8',
      content: 'Memory usage at 85% of threshold',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'ALERT_WARNING',
      createdAt: timestamp(10)
    },
    {
      id: 'ex-9',
      content: '',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'ALERT_ERROR',
      createdAt: timestamp(5),
      metadata: {
        content: 'Database connection failed',
        collapsibleSections: [
          {
            title: 'Error Details',
            content: '**Error**: Connection timeout after 30s\n**Retrying**: Yes (3 attempts remaining)'
          }
        ]
      }
    },
    {
      id: 'ex-10',
      content: 'CRITICAL: Service unavailable - immediate attention required',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'ALERT_CRITICAL',
      createdAt: timestamp(1)
    }
  ] satisfies ChatMessage[],

  /**
   * Review request with collapsible analysis
   */
  reviewRequest: [
    {
      id: 'ex-11',
      content: '',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'PENDING_REVIEW',
      createdAt: timestamp(3),
      metadata: {
        content: '## Review Required\n\nFalse positive analysis identified **12 patterns**',
        collapsibleSections: [
          {
            title: 'Pattern Breakdown',
            content: '- 5 greeting-related mismatches\n- 4 timing issues\n- 3 context problems'
          },
          {
            title: 'Recommendations',
            content: '1. Adjust greeting detection sensitivity\n2. Improve context window handling\n3. Add edge case training examples'
          }
        ],
        buttons: [
          { label: 'Approve Findings', value: 'approve', variant: 'default' },
          { label: 'Request Changes', value: 'changes', variant: 'secondary' },
          { label: 'Reject', value: 'reject', variant: 'destructive' }
        ]
      }
    }
  ] satisfies ChatMessage[],

  /**
   * Complete workflow showing mixed message types
   */
  completeWorkflow: [
    {
      id: 'wf-1',
      content: 'Optimization workflow started',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(20)
    },
    {
      id: 'wf-2',
      content: '',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(18),
      metadata: {
        content: 'Baseline evaluation complete',
        collapsibleSections: [
          {
            title: 'Results',
            content: '**Accuracy**: 72%\n**Target**: 85%\n**Gap**: -13%'
          }
        ]
      }
    },
    {
      id: 'wf-3',
      content: 'Accuracy below target threshold',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'ALERT_WARNING',
      createdAt: timestamp(17)
    },
    {
      id: 'wf-4',
      content: '',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'PENDING_APPROVAL',
      createdAt: timestamp(15),
      metadata: {
        content: 'Should I proceed with optimization?',
        collapsibleSections: [
          {
            title: 'Optimization Plan',
            content: '- Adjust scoring parameters\n- Run test evaluation\n- Deploy if successful'
          }
        ],
        buttons: [
          { label: 'Proceed', value: 'proceed', variant: 'default' },
          { label: 'Cancel', value: 'cancel', variant: 'outline' }
        ]
      }
    },
    {
      id: 'wf-5',
      content: 'Proceed with optimization',
      role: 'USER' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'RESPONSE',
      createdAt: timestamp(12)
    },
    {
      id: 'wf-6',
      content: 'Optimization complete: accuracy improved to 89%',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(5)
    }
  ] satisfies ChatMessage[],

  /**
   * Chat conversation with procedure integration
   */
  chatConversation: [
    {
      id: 'chat-1',
      content: 'Can you analyze the recent evaluation results?',
      role: 'USER' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'CHAT',
      createdAt: timestamp(10)
    },
    {
      id: 'chat-2',
      content: "I'll analyze the evaluation results for you. Let me start by retrieving the latest data.",
      role: 'ASSISTANT' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'CHAT_ASSISTANT',
      createdAt: timestamp(9)
    },
    {
      id: 'chat-3',
      content: 'Analysis started',
      role: 'SYSTEM' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(8)
    },
    {
      id: 'chat-4',
      content: '',
      role: 'ASSISTANT' as const,
      messageType: 'MESSAGE' as const,
      humanInteraction: 'CHAT_ASSISTANT',
      createdAt: timestamp(5),
      metadata: {
        content: "I've completed the analysis. Here's what I found:",
        collapsibleSections: [
          {
            title: 'Key Findings',
            content: '- Current accuracy: 89.2%\n- Improvement over last week: +3.5%\n- No critical issues detected'
          }
        ]
      }
    }
  ] satisfies ChatMessage[]
}
