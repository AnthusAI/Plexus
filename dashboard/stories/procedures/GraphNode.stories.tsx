import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { 
  MoreHorizontal,
  Trash2
} from "lucide-react"
import { CardButton } from "@/components/CardButton"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu"
import { Timestamp } from "@/components/ui/timestamp"

// Individual GraphNode component for Storybook
const GraphNodeDemo = ({ 
  node, 
  level = 0, 
  hasChildren = false, 
  isExpanded = false,
  onToggleExpansion,
  onDelete
}: { 
  node: any,
  level?: number,
  hasChildren?: boolean,
  isExpanded?: boolean,
  onToggleExpansion?: () => void,
  onDelete?: () => void
}) => {
  const getStatusColor = (status?: string | null) => {
    // Use neutral background color since status names are not standardized
    return 'bg-background text-foreground border'
  }

  const renderNodeMetadata = (node: any) => {
    let parsedMetadata: any = {}
    
    try {
      if (typeof node.metadata === 'string') {
        parsedMetadata = JSON.parse(node.metadata)
      } else if (node.metadata) {
        parsedMetadata = node.metadata
      }
    } catch (error) {
      return (
        <div className="text-xs text-muted-foreground">
          <pre className="whitespace-pre-wrap font-mono bg-muted p-2 rounded text-xs overflow-x-auto">
            {typeof node.metadata === 'string' ? node.metadata : JSON.stringify(node.metadata, null, 2)}
          </pre>
        </div>
      )
    }

    if (Object.keys(parsedMetadata).length === 0) {
      return (
        <div className="text-xs text-muted-foreground italic">
          No metadata available
        </div>
      )
    }

    // Extract code for the top metadata section
    const { code, ...otherFields } = parsedMetadata

    // Helper function to format field names
    const formatFieldName = (key: string) => {
      return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
    }

    // Helper function to render field value
    const renderFieldValue = (value: any) => {
      if (value === null || value === undefined) {
        return <span className="text-muted-foreground italic">Not set</span>
      }
      
      if (typeof value === 'string') {
        return <span className="text-sm">{value}</span>
      }
      
      if (typeof value === 'number') {
        return <span className="text-sm font-medium">{value}</span>
      }
      
      if (typeof value === 'boolean') {
        return <span className="text-sm">{value ? 'Yes' : 'No'}</span>
      }
      
      // For objects/arrays, show as JSON
      return (
        <pre className="text-xs font-mono bg-muted p-2 rounded overflow-x-auto">
          {JSON.stringify(value, null, 2)}
        </pre>
      )
    }

    // Helper function to check if field has content
    const hasContent = (value: any) => {
      return value !== null && value !== undefined && value !== ''
    }

    return (
      <div className="space-y-2">
        {/* Metadata section (code) - collapsed by default */}
        <details>
          <summary className={`cursor-pointer p-2 text-sm font-medium hover:bg-muted rounded ${hasContent(code) ? 'text-foreground' : 'text-muted-foreground'}`}>
            Metadata {!hasContent(code) && <span className="text-xs font-normal">(empty)</span>}
          </summary>
          <div className="px-2 pb-2">
            {hasContent(code) ? (
              <pre className="text-xs font-mono bg-muted p-3 rounded max-h-64 overflow-y-auto whitespace-pre-wrap">
                {code}
              </pre>
            ) : (
              <span className="text-xs text-muted-foreground italic">No code available</span>
            )}
          </div>
        </details>

        {/* Other metadata fields - expanded by default */}
        {Object.entries(otherFields).map(([key, value]) => (
          <details key={key} open>
            <summary className={`cursor-pointer p-2 text-sm font-medium hover:bg-muted rounded ${hasContent(value) ? 'text-foreground' : 'text-muted-foreground'}`}>
              {formatFieldName(key)} {!hasContent(value) && <span className="text-xs font-normal">(empty)</span>}
            </summary>
            <div className="px-2 pb-2">
              {renderFieldValue(value)}
            </div>
          </details>
        ))}
      </div>
    )
  }

  return (
    <div className={`${level > 0 ? 'ml-6 border-l border-border pl-4' : ''}`}>
      <Card className="mb-2 border-0 shadow-none">
        <CardHeader className="pb-2">
                                  <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  {hasChildren && (
                    <button
                      onClick={onToggleExpansion}
                      className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {isExpanded ? '▼' : '▶'}
                    </button>
                  )}
                  <h4 className="font-medium text-sm">
                    {node.name || `Node ${node.id.slice(-8)}`}
                  </h4>
                  <Badge variant="secondary" className={getStatusColor(node.status)}>
                    {node.status || 'Unknown'}
                  </Badge>
                </div>
                <div className="mt-1 ml-6">
                  <Timestamp time={node.updatedAt} variant="relative" className="text-xs text-muted-foreground" />
                </div>
              </div>

              <DropdownMenuPrimitive.Root>
                <DropdownMenuPrimitive.Trigger asChild>
                  <div onClick={(e) => e.stopPropagation()}>
                    <CardButton
                      icon={MoreHorizontal}
                      onClick={() => {}}
                      aria-label="Node options"
                    />
                  </div>
                </DropdownMenuPrimitive.Trigger>
                <DropdownMenuPrimitive.Portal>
                  <DropdownMenuPrimitive.Content 
                    align="end" 
                    className="min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md z-50"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <DropdownMenuPrimitive.Item 
                      className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 text-destructive"
                      onSelect={onDelete}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </DropdownMenuPrimitive.Item>
                  </DropdownMenuPrimitive.Content>
                </DropdownMenuPrimitive.Portal>
              </DropdownMenuPrimitive.Root>
            </div>
        </CardHeader>

        <CardContent className="pt-0">
          {renderNodeMetadata(node)}
        </CardContent>
      </Card>
    </div>
  )
}

const meta: Meta<typeof GraphNodeDemo> = {
  title: 'Procedures/GraphNode',
  component: GraphNodeDemo,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  argTypes: {
    level: {
      control: { type: 'range', min: 0, max: 4, step: 1 },
      description: 'Nesting level for indentation'
    },
    hasChildren: {
      control: 'boolean',
      description: 'Whether the node has child nodes'
    },
    isExpanded: {
      control: 'boolean',
      description: 'Whether the node is expanded (only relevant if hasChildren is true)'
    }
  }
}

export default meta
type Story = StoryObj<typeof GraphNodeDemo>

// Sample node data
const rootNode = {
  id: 'root-node',
  procedureId: 'proc-123',
  parentNodeId: null,
  name: 'Root Strategy Node',
  status: 'ACTIVE',
  metadata: JSON.stringify({
    code: `class: "BeamSearch"
value: |
  local score = experiment_node.value.accuracy or 0
  local penalty = (experiment_node.value.cost or 0) * 0.1
  return score - penalty`,
    hypothesis: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.',
    created_by: 'system:programmatic',
    version: '1.0.0'
  }),
  createdAt: '2024-01-15T10:30:00Z',
  updatedAt: '2024-01-15T10:30:00Z'
}

const hypothesisNode = {
  id: 'hypothesis-node',
  procedureId: 'proc-123',
  parentNodeId: 'root-node',
  name: 'Hypothesis: Improve Greeting Detection',
  status: 'COMPLETED',
  metadata: JSON.stringify({
    code: `class: "BeamSearch"
value: |
  -- Enhanced greeting detection with more variations
  local greeting_score = check_greeting_variations(call_text)
  return greeting_score * 1.2`,
    hypothesis: 'Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.',
    insight: 'Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.',
    accuracy: 0.87,
    cost: 0.05,
    test_results: {
      samples_tested: 1000,
      improvement: 0.15,
      confidence: 0.95
    },
    tags: ['greeting', 'detection', 'optimization'],
    priority: 'high',
    validated: true
  }),
  createdAt: '2024-01-15T10:45:00Z',
  updatedAt: '2024-01-15T11:30:00Z'
}

const runningNode = {
  id: 'running-node',
  procedureId: 'proc-123',
  parentNodeId: 'root-node',
  name: 'Context-Aware Scoring Analysis',
  status: 'RUNNING',
  metadata: JSON.stringify({
    code: `class: "BeamSearch"
value: |
  -- Context-aware scoring implementation
  local context_score = analyze_conversation_context(call_history)
  local base_score = get_base_score(current_turn)
  return (base_score + context_score) / 2`,
    hypothesis: 'Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam.',
    insight: null,
    accuracy: null,
    cost: 0.08,
    estimated_completion: '2024-01-15T12:00:00Z',
    progress: 0.65,
    current_phase: 'testing',
    validated: false
  }),
  createdAt: '2024-01-15T11:00:00Z',
  updatedAt: '2024-01-15T11:15:00Z'
}

const failedNode = {
  id: 'failed-node',
  procedureId: 'proc-123',
  parentNodeId: 'root-node',
  name: 'Memory Optimization Attempt',
  status: 'FAILED',
  metadata: JSON.stringify({
    code: `class: "BeamSearch"
value: |
  -- Memory optimization that failed
  local optimized = optimize_memory_usage()
  return optimized`,
    hypothesis: 'Eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo.',
    insight: 'Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores.',
    accuracy: null,
    cost: 0.12,
    error_message: 'OutOfMemoryError: Java heap space',
    failure_reason: 'Aggressive memory optimization caused instability'
  }),
  createdAt: '2024-01-15T09:30:00Z',
  updatedAt: '2024-01-15T10:15:00Z'
}

const minimalNode = {
  id: 'minimal-node',
  procedureId: 'proc-123',
  parentNodeId: 'root-node',
  name: 'Simple Test Node',
  status: 'PENDING',
  metadata: JSON.stringify({
    code: `-- Simple test
return true`,
    hypothesis: 'At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium.'
  }),
  createdAt: '2024-01-15T12:00:00Z',
  updatedAt: '2024-01-15T12:00:00Z'
}

const emptyNode = {
  id: 'empty-node',
  procedureId: 'proc-123',
  parentNodeId: 'root-node',
  name: 'Empty Metadata Node',
  status: 'PENDING',
  metadata: JSON.stringify({}),
  createdAt: '2024-01-15T12:15:00Z',
  updatedAt: '2024-01-15T12:15:00Z'
}

export const RootNode: Story = {
  args: {
    node: rootNode,
    level: 0,
    hasChildren: true,
    isExpanded: false,
    onToggleExpansion: () => console.log('Toggle expansion'),
    onDelete: () => console.log('Delete node')
  }
}

export const CompletedHypothesis: Story = {
  args: {
    node: hypothesisNode,
    level: 1,
    hasChildren: false,
    isExpanded: false,
    onToggleExpansion: () => console.log('Toggle expansion'),
    onDelete: () => console.log('Delete node')
  }
}

export const RunningNode: Story = {
  args: {
    node: runningNode,
    level: 1,
    hasChildren: true,
    isExpanded: true,
    onToggleExpansion: () => console.log('Toggle expansion'),
    onDelete: () => console.log('Delete node')
  }
}

export const FailedNode: Story = {
  args: {
    node: failedNode,
    level: 2,
    hasChildren: false,
    isExpanded: false,
    onToggleExpansion: () => console.log('Toggle expansion'),
    onDelete: () => console.log('Delete node')
  }
}

export const MinimalMetadata: Story = {
  args: {
    node: minimalNode,
    level: 0,
    hasChildren: false,
    isExpanded: false,
    onToggleExpansion: () => console.log('Toggle expansion'),
    onDelete: () => console.log('Delete node')
  }
}

export const EmptyMetadata: Story = {
  args: {
    node: emptyNode,
    level: 0,
    hasChildren: false,
    isExpanded: false,
    onToggleExpansion: () => console.log('Toggle expansion'),
    onDelete: () => console.log('Delete node')
  }
}

export const DeepNested: Story = {
  args: {
    node: {
      ...hypothesisNode,
      name: 'Deep Nested Node (Level 3)'
    },
    level: 3,
    hasChildren: true,
    isExpanded: false,
    onToggleExpansion: () => console.log('Toggle expansion'),
    onDelete: () => console.log('Delete node')
  }
}

export const Interactive: Story = {
  args: {
    node: rootNode,
    level: 0,
    hasChildren: true,
    isExpanded: false
  },
  render: (args) => {
    const [isExpanded, setIsExpanded] = React.useState(args.isExpanded)
    
    return (
      <GraphNodeDemo
        {...args}
        isExpanded={isExpanded}
        onToggleExpansion={() => setIsExpanded(!isExpanded)}
        onDelete={() => alert('Node deleted!')}
      />
    )
  }
}
