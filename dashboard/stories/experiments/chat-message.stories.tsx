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
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'

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

// Collapsible text component with Markdown support
function CollapsibleText({ 
  content, 
  maxLines = 10, 
  className = "whitespace-pre-wrap break-words",
  enableMarkdown = true
}: { 
  content: string, 
  maxLines?: number,
  className?: string,
  enableMarkdown?: boolean
}) {
  const [isExpanded, setIsExpanded] = React.useState(false)
  const lines = content.split('\n')
  const shouldTruncate = lines.length > maxLines
  const displayContent = shouldTruncate && !isExpanded 
    ? lines.slice(0, maxLines).join('\n') + '...'
    : content

  const renderContent = (text: string) => {
    if (!enableMarkdown) {
      return <p className={className}>{text}</p>
    }

    return (
      <div className={`max-w-none ${className}`} style={{lineHeight: 1, gap: 0}}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkBreaks]}
          components={{
            p: ({ children }: { children: React.ReactNode }) => {
              // Hide empty paragraphs that cause spacing
              if (!children || (typeof children === 'string' && children.trim() === '')) {
                return null;
              }
              return <p className="mb-0 last:mb-0 leading-tight" style={{lineHeight: '1.2', margin: 0, padding: 0, display: 'block'}}>{children}</p>;
            },
            ul: ({ children }: { children: React.ReactNode }) => <ul className="mb-0 ml-4 list-disc leading-tight" style={{margin: 0, padding: 0}}>{children}</ul>,
            ol: ({ children }: { children: React.ReactNode }) => <ol className="mb-0 ml-4 list-decimal leading-tight" style={{margin: 0, padding: 0}}>{children}</ol>,
            li: ({ children }: { children: React.ReactNode }) => <li className="mb-0 leading-tight" style={{margin: 0, padding: 0}}>{children}</li>,
            strong: ({ children }: { children: React.ReactNode }) => <strong className="font-semibold text-foreground">{children}</strong>,
            em: ({ children }: { children: React.ReactNode }) => <em className="italic">{children}</em>,
            code: ({ children }: { children: React.ReactNode }) => <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
            pre: ({ children }: { children: React.ReactNode }) => <pre className="bg-muted p-3 rounded overflow-x-auto text-sm">{children}</pre>,
            h1: ({ children }: { children: React.ReactNode }) => <h1 className="text-lg font-semibold text-foreground" style={{margin: 0, padding: 0, lineHeight: 1}}>{children}</h1>,
            h2: ({ children }: { children: React.ReactNode }) => <h2 className="text-base font-semibold text-foreground" style={{margin: 0, padding: 0, lineHeight: 1}}>{children}</h2>,
            h3: ({ children }: { children: React.ReactNode }) => <h3 className="text-sm font-medium text-foreground" style={{margin: 0, padding: 0, lineHeight: 1}}>{children}</h3>,
            blockquote: ({ children }: { children: React.ReactNode }) => <blockquote className="border-l-4 border-muted-foreground/20 pl-4 italic text-muted-foreground mb-0 leading-tight">{children}</blockquote>,
            a: ({ children, href }: { children: React.ReactNode; href?: string }) => <a href={href} className="text-blue-600 hover:text-blue-800 underline" target="_blank" rel="noopener noreferrer">{children}</a>,
            br: () => <br style={{margin: 0, padding: 0, lineHeight: 0}} />,
          }}
        >
          {text}
        </ReactMarkdown>
      </div>
    )
  }

  if (!shouldTruncate) {
    return renderContent(content)
  }

  return (
    <div>
      {renderContent(displayContent)}
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
        
        {/* Tool call parameters display - primary for tool calls */}
        {messageType === 'TOOL_CALL' && toolParameters ? (
          <div>
            <div className="bg-card rounded-md p-3">
              {toolName && (
                <h4 className="font-semibold text-sm mb-2 text-foreground">{toolName}</h4>
              )}
              <div className="space-y-1">
                {Object.entries(toolParameters).map(([key, value]) => (
                  <div key={key} className="grid grid-cols-3 gap-2 text-xs">
                    <div className="font-medium text-muted-foreground">{key}:</div>
                    <div className="col-span-2 font-mono text-foreground break-words">
                      {typeof value === 'string' ? value : JSON.stringify(value)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Raw tool call - collapsible */}
            <div className="mt-3">
              <Collapsible>
                <CollapsibleTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-auto p-0 text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                  >
                    <ChevronRight className="h-3 w-3" />
                    Raw
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <div className="mt-2 text-sm font-mono">
                    <CollapsibleText content={content} maxLines={10} />
                  </div>
                </CollapsibleContent>
              </Collapsible>
            </div>
          </div>
        ) : messageType === 'TOOL_RESPONSE' ? (
          // Don't show plain text content for tool responses - only show the formatted response card below
          null
        ) : (
          <div className="text-sm">
            <CollapsibleText content={content} maxLines={10} />
          </div>
        )}
        
        {/* Tool response display */}
        {messageType === 'TOOL_RESPONSE' && toolResponse && (
          <div className="mt-3">
            <div className="bg-card rounded-md p-3 text-xs">
              <div className="font-mono">
                <CollapsibleText 
                  content={JSON.stringify(toolResponse, null, 2)} 
                  maxLines={12}
                  className="whitespace-pre-wrap break-words font-mono"
                  enableMarkdown={false}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

const meta = {
  title: 'Chat/Internal/Single Message Component',
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
      <div className="p-8 min-h-screen bg-background">
        <div className="p-4">
          <Story />
        </div>
      </div>
    ),
  ],
} satisfies Meta<typeof ChatMessage>

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
    content: `I'll start by examining the feedback patterns to understand how the current **"Medication Review"** score is performing. Let me get an overview of the confusion matrix and accuracy patterns.

## Analysis Plan

1. **Performance Metrics** - Check accuracy and precision
2. **Pattern Identification** - Look for systematic errors
3. **Hypothesis Generation** - Create testable improvements

> Note: This analysis will focus on the last 30 days of data for statistical significance.`,
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

export const RichMarkdownMessage: Story = {
  args: {
    content: `# Experiment Analysis Summary

Based on my analysis of the **SelectQuote HCS Medium-Risk** scorecard data, I've identified several key opportunities for improvement:

## Key Findings

### Performance Metrics
- **Accuracy**: 73.3% (33/45 items correctly classified)
- **Precision**: 65.2% (15 true positives out of 23 positive predictions)  
- **Recall**: 78.9% (15 true positives out of 19 actual positives)

### Problem Areas Identified

1. **False Positives** (8 cases)
   - Routine medication refills being flagged as requiring review
   - Standard dosage adjustments triggering unnecessary alerts
   
2. **False Negatives** (4 cases)
   - Complex drug interactions not being detected
   - Missing review requirements for high-risk medications

## Proposed Hypotheses

I will create \`3 experiment nodes\` to test different improvement strategies:

| Hypothesis | Method | Expected Impact |
|------------|---------|-----------------|
| **Routine Refill Filter** | Exclude standard refill patterns | ↓ 5-7 false positives |
| **Drug Interaction Enhancement** | Enhanced interaction database | ↓ 2-3 false negatives |
| **Risk Stratification** | Tiered review requirements | ↑ Overall precision |

### Implementation Code

\`\`\`yaml
class: "MedicationReview"
parameters:
  exclude_routine_refills: true
  refill_threshold_days: 30
  enhanced_interactions: true
\`\`\`

> **Next Steps**: Creating experiment nodes to validate these hypotheses with A/B testing on recent feedback data.

---
*Analysis completed at 2024-01-15 10:30:30Z*`,
    role: 'ASSISTANT',
    messageType: 'MESSAGE',
    createdAt: '2024-01-15T10:30:30Z',
  },
}
