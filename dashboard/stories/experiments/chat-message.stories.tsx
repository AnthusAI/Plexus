import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { 
  MessageSquare,
  User,
  Bot,
  Settings,
  Wrench,
  Terminal,
  Clock,
  ChevronRight
} from 'lucide-react'
import { Timestamp } from '@/components/ui/timestamp'
import { Card } from '@/components/ui/card'

// Individual Chat Message Component
interface ChatMessageProps {
  content: string
  role: 'SYSTEM' | 'ASSISTANT' | 'USER' | 'TOOL'
  messageType?: 'MESSAGE' | 'TOOL_CALL' | 'TOOL_RESPONSE'
  toolName?: string
  toolParameters?: any
  toolResponse?: any
  createdAt: string
  className?: string
}

// Collapsible text component (duplicated for this story)
function CollapsibleText({ 
  content, 
  maxLines = 10, 
  className = "whitespace-pre-wrap break-words" 
}: { 
  content: string, 
  maxLines?: number,
  className?: string 
}) {
  const [isExpanded, setIsExpanded] = React.useState(false)
  const lines = content.split('\n')
  const shouldTruncate = lines.length > maxLines
  const displayContent = shouldTruncate && !isExpanded 
    ? lines.slice(0, maxLines).join('\n') + '...'
    : content

  if (!shouldTruncate) {
    return <p className={className}>{content}</p>
  }

  return (
    <div>
      <p className={className}>{displayContent}</p>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsExpanded(!isExpanded)}
        className="mt-2 p-0 h-auto text-xs text-muted-foreground hover:text-foreground"
      >
        {isExpanded ? 'Show less' : `Show more (${lines.length - maxLines} more lines)`}
      </Button>
    </div>
  )
}

// Message type icons and colors
const getMessageIcon = (role?: string, messageType?: string) => {
  if (messageType === 'TOOL_CALL') {
    return <Wrench className="h-4 w-4 text-blue-500" />
  }
  if (messageType === 'TOOL_RESPONSE') {
    return <Terminal className="h-4 w-4 text-green-600" />
  }
  
  switch (role) {
    case 'SYSTEM':
      return <Settings className="h-4 w-4 text-purple-600" />
    case 'ASSISTANT':
      return <Bot className="h-4 w-4 text-blue-600" />
    case 'USER':
      return <User className="h-4 w-4 text-green-600" />
    case 'TOOL':
      return <Terminal className="h-4 w-4 text-orange-600" />
    default:
      return <MessageSquare className="h-4 w-4 text-muted-foreground" />
  }
}

const getMessageTypeColor = (role?: string, messageType?: string) => {
  if (messageType === 'TOOL_CALL') return 'bg-blue-100 text-blue-800'
  if (messageType === 'TOOL_RESPONSE') return 'bg-green-100 text-green-800'
  
  switch (role) {
    case 'SYSTEM':
      return 'bg-purple-100 text-purple-800'
    case 'ASSISTANT':
      return 'bg-blue-100 text-blue-800'
    case 'USER':
      return 'bg-green-100 text-green-800'
    case 'TOOL':
      return 'bg-orange-100 text-orange-800'
    default:
      return 'bg-gray-100 text-gray-800'
  }
}

function ChatMessage({ 
  content, 
  role, 
  messageType, 
  toolName, 
  toolParameters, 
  toolResponse, 
  createdAt,
  className = ""
}: ChatMessageProps) {
  return (
    <div className={`flex items-start gap-3 ${className}`}>
      <div className="flex-shrink-0 mt-1">
        {getMessageIcon(role, messageType)}
      </div>
      
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <Badge 
            variant="secondary" 
            className={`text-xs ${getMessageTypeColor(role, messageType)}`}
          >
            {messageType || role}
          </Badge>
          
          {toolName && (
            <Badge variant="outline" className="text-xs">
              {toolName}
            </Badge>
          )}
          
          <div className="flex items-center gap-1 text-xs text-muted-foreground ml-auto">
            <Clock className="h-3 w-3" />
            <Timestamp time={createdAt} variant="relative" showIcon={false} />
          </div>
        </div>
        
        <div className="text-sm">
          <CollapsibleText content={content} maxLines={10} />
        </div>
        
        {/* Tool parameters and responses */}
        {(toolParameters || toolResponse) && (
          <Collapsible className="mt-3">
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm" className="p-0 h-auto text-xs text-muted-foreground hover:text-foreground">
                <ChevronRight className="h-3 w-3 mr-1 transition-transform group-data-[state=open]:rotate-90" />
                View {toolParameters ? 'parameters' : 'response'} details
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-2">
              <div className="bg-muted rounded-md p-3 text-xs">
                {toolParameters && (
                  <div className="mb-2">
                    <div className="font-semibold mb-1">Parameters:</div>
                    <div className="font-mono text-xs">
                      <CollapsibleText 
                        content={JSON.stringify(toolParameters, null, 2)} 
                        maxLines={5}
                        className="whitespace-pre-wrap break-words font-mono"
                      />
                    </div>
                  </div>
                )}
                {toolResponse && (
                  <div>
                    <div className="font-semibold mb-1">Response:</div>
                    <div className="font-mono text-xs">
                      <CollapsibleText 
                        content={JSON.stringify(toolResponse, null, 2)} 
                        maxLines={5}
                        className="whitespace-pre-wrap break-words font-mono"
                      />
                    </div>
                  </div>
                )}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}
      </div>
    </div>
  )
}

const meta: Meta<typeof ChatMessage> = {
  title: 'Experiments/ChatMessage',
  component: ChatMessage,
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
        <Card className="p-4 bg-background">
          <Story />
        </Card>
      </div>
    ),
  ],
}

export default meta
type Story = StoryObj<typeof meta>

export const SystemMessage: Story = {
  args: {
    content: `You are part of a hypothesis engine that is part of an automated experiment running process for optimizing scorecard score configurations in a reinforcement learning feedback loop system.

Your role is to analyze feedback patterns, identify improvement opportunities, and generate testable hypotheses for score configuration modifications.`,
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    createdAt: '2024-01-15T10:30:00Z',
  },
}

export const UserMessage: Story = {
  args: {
    content: 'Begin analyzing the current score configuration and feedback patterns to generate hypotheses. You have access to all the necessary context and tools.',
    role: 'USER',
    messageType: 'MESSAGE',
    createdAt: '2024-01-15T10:30:05Z',
  },
}

export const AssistantMessage: Story = {
  args: {
    content: 'I\'ll start by examining the feedback patterns to understand how the current "Medication Review" score is performing. Let me get an overview of the confusion matrix and accuracy patterns.',
    role: 'ASSISTANT',
    messageType: 'MESSAGE',
    createdAt: '2024-01-15T10:30:10Z',
  },
}

export const ToolCall: Story = {
  args: {
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
  },
}

export const ToolResponse: Story = {
  args: {
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
  },
}

export const LongMessage: Story = {
  args: {
    content: Array.from({ length: 20 }, (_, i) => 
      `This is line ${i + 1} of a very long system message that should be truncated by the CollapsibleText component. This demonstrates how long content is handled in the chat interface.`
    ).join('\n'),
    role: 'SYSTEM',
    messageType: 'MESSAGE',
    createdAt: '2024-01-15T10:30:00Z',
  },
}

export const ComplexToolCall: Story = {
  args: {
    content: 'create_experiment_node(experiment_id="abc123", hypothesis_description="GOAL: Reduce false positives for routine medication refills\\nMETHOD: Add exclusion rules for routine refill patterns", node_name="Routine Refill Filter")',
    role: 'ASSISTANT',
    messageType: 'TOOL_CALL',
    toolName: 'create_experiment_node',
    toolParameters: {
      experiment_id: "abc123",
      hypothesis_description: "GOAL: Reduce false positives for routine medication refills\nMETHOD: Add exclusion rules for routine refill patterns",
      node_name: "Routine Refill Filter",
      yaml_configuration: "class: \"MedicationReview\"\nparameters:\n  exclude_routine_refills: true\n  refill_threshold_days: 30"
    },
    createdAt: '2024-01-15T10:30:25Z',
  },
}
