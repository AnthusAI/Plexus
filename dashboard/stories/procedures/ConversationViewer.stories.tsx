import type { Meta, StoryObj } from '@storybook/react'
import ConversationViewer from '@/components/ui/conversation-viewer'
import { fn } from '@storybook/test'

const meta: Meta<typeof ConversationViewer> = {
  title: 'Procedures/ConversationViewer',
  component: ConversationViewer,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof ConversationViewer>

// Mock the GraphQL client for Storybook
const mockGraphQLClient = {
  graphql: fn().mockImplementation(({ query, variables }) => {
    // Mock response for chat sessions query
    if (query.includes('listChatSessionByProcedureIdAndCreatedAt')) {
      return Promise.resolve({
        data: {
          listChatSessionByProcedureIdAndCreatedAt: {
            items: [
              {
                id: 'session-1',
                procedureId: variables.procedureId,
                nodeId: 'node-root',
                name: 'Initial Setup Session',
                category: 'Setup',
                status: 'COMPLETED',
                createdAt: '2024-01-15T10:30:00Z',
                updatedAt: '2024-01-15T10:45:00Z'
              },
              {
                id: 'session-2',
                procedureId: variables.procedureId,
                nodeId: 'node-hypothesis-1',
                name: 'Hypothesis Generation - Greetings',
                category: 'Hypothesize',
                status: 'COMPLETED',
                createdAt: '2024-01-15T10:45:00Z',
                updatedAt: '2024-01-15T11:30:00Z'
              },
              {
                id: 'session-3',
                procedureId: variables.procedureId,
                nodeId: 'node-hypothesis-2',
                name: 'Context Analysis Session',
                category: 'Analyze',
                status: 'ACTIVE',
                createdAt: '2024-01-15T11:00:00Z',
                updatedAt: '2024-01-15T11:15:00Z'
              }
            ]
          }
        }
      })
    }
    
    // Mock response for chat messages query
    if (query.includes('listChatMessageBySessionIdAndSequenceNumber')) {
      const sessionId = variables.sessionId
      
      if (sessionId === 'session-1') {
        return Promise.resolve({
          data: {
            listChatMessageBySessionIdAndSequenceNumber: {
              items: [
                {
                  id: 'msg-1',
                  sessionId: 'session-1',
                  procedureId: variables.procedureId || 'proc-123',
                  role: 'SYSTEM',
                  content: 'Starting procedure setup for customer service optimization...',
                  messageType: 'MESSAGE',
                  sequenceNumber: 1,
                  createdAt: '2024-01-15T10:30:00Z'
                },
                {
                  id: 'msg-2',
                  sessionId: 'session-1',
                  procedureId: variables.procedureId || 'proc-123',
                  role: 'ASSISTANT',
                  content: 'I\'ll help you set up the procedure for optimizing customer service call analysis. Let me start by examining the current scorecard configuration and identifying areas for improvement.',
                  messageType: 'MESSAGE',
                  sequenceNumber: 2,
                  createdAt: '2024-01-15T10:30:15Z'
                },
                {
                  id: 'msg-3',
                  sessionId: 'session-1',
                  procedureId: variables.procedureId || 'proc-123',
                  role: 'ASSISTANT',
                  content: 'Based on my analysis, I\'ve identified three key areas for optimization:\n\n1. **Greeting Detection**: Current accuracy is 72%, we can improve this\n2. **Context Awareness**: The scoring doesn\'t consider conversation history\n3. **Multi-language Support**: Limited to English greetings only\n\nI\'ll create hypotheses to address each of these areas.',
                  messageType: 'MESSAGE',
                  sequenceNumber: 3,
                  createdAt: '2024-01-15T10:32:00Z'
                }
              ]
            }
          }
        })
      }
      
      if (sessionId === 'session-2') {
        return Promise.resolve({
          data: {
            listChatMessageBySessionIdAndSequenceNumber: {
              items: [
                {
                  id: 'msg-4',
                  sessionId: 'session-2',
                  procedureId: variables.procedureId || 'proc-123',
                  role: 'SYSTEM',
                  content: 'Generating hypothesis for greeting detection improvement...',
                  messageType: 'MESSAGE',
                  sequenceNumber: 1,
                  createdAt: '2024-01-15T10:45:00Z'
                },
                {
                  id: 'msg-5',
                  sessionId: 'session-2',
                  procedureId: variables.procedureId || 'proc-123',
                  role: 'ASSISTANT',
                  content: '## Hypothesis: Enhanced Greeting Detection\n\n**Problem**: Current greeting detection only catches 72% of call openings\n\n**Hypothesis**: Adding more greeting variations and patterns will improve detection accuracy\n\n**Approach**: \n- Expand greeting patterns to include informal variations\n- Add time-of-day contextual greetings\n- Include regional greeting differences\n\n**Expected Improvement**: 15-20% accuracy increase',
                  messageType: 'MESSAGE',
                  sequenceNumber: 2,
                  createdAt: '2024-01-15T10:45:30Z'
                },
                {
                  id: 'msg-6',
                  sessionId: 'session-2',
                  procedureId: variables.procedureId || 'proc-123',
                  role: 'TOOL',
                  content: 'plexus_score_update',
                  messageType: 'TOOL_CALL',
                  toolName: 'plexus_score_update',
                  toolParameters: JSON.stringify({
                    scorecard_identifier: 'CS3 Services v2',
                    score_identifier: 'Good Call',
                    code: 'class: "BeamSearch"\nvalue: |\n  local greeting_score = check_greeting_variations(call_text)\n  return greeting_score * 1.2'
                  }),
                  sequenceNumber: 3,
                  createdAt: '2024-01-15T10:46:00Z'
                },
                {
                  id: 'msg-7',
                  sessionId: 'session-2',
                  procedureId: variables.procedureId || 'proc-123',
                  role: 'TOOL',
                  content: 'Score configuration updated successfully. New version created with enhanced greeting detection patterns.',
                  messageType: 'TOOL_RESPONSE',
                  toolResponse: JSON.stringify({
                    success: true,
                    version_id: 'v2.1.3',
                    changes: 'Enhanced greeting detection patterns'
                  }),
                  sequenceNumber: 4,
                  createdAt: '2024-01-15T10:46:15Z'
                }
              ]
            }
          }
        })
      }
      
      return Promise.resolve({
        data: {
          listChatMessageBySessionIdAndSequenceNumber: {
            items: []
          }
        }
      })
    }
    
    return Promise.resolve({ data: {} })
  })
}

// Note: This story shows the ConversationViewer component structure
// In a real environment, it would connect to GraphQL to load chat sessions and messages

export const Default: Story = {
  args: {
    procedureId: 'proc-123',
    onSessionDelete: fn(),
    onSessionCountChange: fn()
  }
}

export const WithActiveSessions: Story = {
  args: {
    ...Default.args,
    procedureId: 'proc-with-sessions'
  }
}

export const EmptyState: Story = {
  args: {
    ...Default.args,
    procedureId: 'proc-empty'
  },
  parameters: {
    mockData: {
      listChatSessionByProcedureIdAndCreatedAt: {
        items: []
      }
    }
  }
}

export const LoadingState: Story = {
  args: {
    ...Default.args,
    procedureId: 'proc-loading'
  },
  parameters: {
    mockData: 'loading'
  }
}
