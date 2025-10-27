import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { MoreHorizontal, Trash2 } from "lucide-react"
import { CardButton } from "@/components/CardButton"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu"
import { Timestamp } from "@/components/ui/timestamp"

// Mock data for the nodes
const mockNodes = [
  {
    id: 'node-root',
    procedureId: 'proc-123',
    parentNodeId: null,
    name: 'Root Node',
    status: 'ACTIVE',
    metadata: JSON.stringify({
      code: `class: "BeamSearch"
value: |
  local score = experiment_node.value.accuracy or 0
  local penalty = (experiment_node.value.cost or 0) * 0.1
  return score - penalty`,
      hypothesis: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
      created_by: 'system:programmatic',
      version: '1.0.0',
      last_modified: '2024-01-15T10:30:00Z'
    }),
    createdAt: '2024-01-15T10:30:00Z',
    updatedAt: '2024-01-15T10:30:00Z'
  },
  {
    id: 'node-hypothesis-1',
    procedureId: 'proc-123',
    parentNodeId: 'node-root',
    name: 'Hypothesis: Improve Greeting Detection',
    status: 'COMPLETED',
    metadata: JSON.stringify({
      code: `class: "BeamSearch"
value: |
  -- Enhanced greeting detection with more variations
  local greeting_score = check_greeting_variations(call_text)
  return greeting_score * 1.2`,
      hypothesis: 'Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.',
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
  },
  {
    id: 'node-hypothesis-2',
    procedureId: 'proc-123',
    parentNodeId: 'node-root',
    name: 'Hypothesis: Context-Aware Scoring',
    status: 'RUNNING',
    metadata: JSON.stringify({
      code: `class: "BeamSearch"
value: |
  -- Context-aware scoring implementation
  local context_score = analyze_conversation_context(call_history)
  local base_score = get_base_score(current_turn)
  return (base_score + context_score) / 2`,
      hypothesis: 'Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium.',
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
  },
  {
    id: 'node-hypothesis-3',
    procedureId: 'proc-123',
    parentNodeId: 'node-hypothesis-1',
    name: 'Refinement: Multi-Language Greetings',
    status: 'PENDING',
    metadata: JSON.stringify({
      code: `class: "BeamSearch"
value: |
  -- Multi-language greeting detection
  local lang = detect_language(call_text)
  local greeting_score = check_multilang_greetings(call_text, lang)
  return greeting_score * 1.3`,
      hypothesis: 'Eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo.',
      insight: '',
      accuracy: null,
      cost: null,
      languages_supported: ['en', 'es', 'fr', 'de'],
      depends_on: ['node-hypothesis-1'],
      estimated_effort: 'medium',
      validated: false
    }),
    createdAt: '2024-01-15T11:45:00Z',
    updatedAt: '2024-01-15T11:45:00Z'
  },
  {
    id: 'node-minimal',
    procedureId: 'proc-123',
    parentNodeId: 'node-root',
    name: 'Minimal Node',
    status: 'PENDING',
    metadata: JSON.stringify({
      code: `-- Simple test
return true`,
      hypothesis: 'At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium.'
    }),
    createdAt: '2024-01-15T12:00:00Z',
    updatedAt: '2024-01-15T12:00:00Z'
  },
  {
    id: 'node-empty',
    procedureId: 'proc-123',
    parentNodeId: 'node-root',
    name: 'Empty Metadata Node',
    status: 'PENDING',
    metadata: JSON.stringify({}),
    createdAt: '2024-01-15T12:15:00Z',
    updatedAt: '2024-01-15T12:15:00Z'
  }
]

// Simplified GraphNodesList component for Storybook
const GraphNodesListDemo = ({ nodes = mockNodes, initiallyExpanded }: { nodes?: typeof mockNodes, initiallyExpanded?: string[] }) => {
  // Find root nodes and expand them by default, plus any additionally specified nodes
  const rootNodeIds = nodes.filter(node => !node.parentNodeId).map(node => node.id)
  const defaultExpanded = initiallyExpanded ? [...rootNodeIds, ...initiallyExpanded] : rootNodeIds
  
  const [expandedNodes, setExpandedNodes] = React.useState(new Set(defaultExpanded))

  const toggleNodeExpansion = (nodeId: string) => {
    setExpandedNodes(prev => {
      const newSet = new Set(prev)
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId)
      } else {
        newSet.add(nodeId)
      }
      return newSet
    })
  }

  const getStatusColor = (status?: string | null) => {
    // Use neutral background color since status names are not standardized
    return 'bg-background text-foreground border'
  }

  const renderNodeMetadata = (node: typeof mockNodes[0]) => {
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

  const rootNodes = nodes.filter(node => !node.parentNodeId)
  const getChildNodes = (parentId: string) => {
    return nodes.filter(node => node.parentNodeId === parentId)
  }

  const renderNode = (node: typeof mockNodes[0], level: number = 0) => {
    const childNodes = getChildNodes(node.id)
    const hasChildren = childNodes.length > 0
    const isExpanded = expandedNodes.has(node.id)

    return (
      <div key={node.id} className={`${level > 0 ? 'ml-6 border-l border-border pl-4' : ''}`}>
        <Card className="mb-2 border-0 shadow-none">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  {hasChildren && (
                    <button
                      onClick={() => toggleNodeExpansion(node.id)}
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
                      onSelect={() => console.log('Delete node:', node.id)}
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

        {hasChildren && isExpanded && (
          <div className="ml-4">
            {childNodes.map(childNode => renderNode(childNode, level + 1))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Graph Nodes</h3>
        <Badge variant="outline">{nodes.length} nodes</Badge>
      </div>
      
      <div className="space-y-2">
        {rootNodes.map(node => renderNode(node))}
      </div>
    </div>
  )
}

const meta: Meta<typeof GraphNodesListDemo> = {
  title: 'Procedures/GraphNodesList',
  component: GraphNodesListDemo,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof GraphNodesListDemo>

export const Default: Story = {
  args: {
    nodes: mockNodes
  }
}

export const EmptyState: Story = {
  args: {
    nodes: []
  }
}

export const SingleNode: Story = {
  args: {
    nodes: [mockNodes[0]]
  }
}

export const CompletedHypothesis: Story = {
  args: {
    nodes: [mockNodes[0], mockNodes[1]]
  }
}

export const RunningHypothesis: Story = {
  args: {
    nodes: [mockNodes[0], mockNodes[2]]
  }
}

export const PendingRefinement: Story = {
  args: {
    nodes: [mockNodes[0], mockNodes[1], mockNodes[3]]
  }
}

export const RichMetadata: Story = {
  args: {
    nodes: [mockNodes[1]] // The hypothesis node with lots of metadata fields
  }
}

export const MinimalMetadata: Story = {
  args: {
    nodes: [mockNodes[4]] // The minimal node with just code and type
  }
}

export const EmptyMetadata: Story = {
  args: {
    nodes: [mockNodes[5]] // The empty metadata node
  }
}

export const MixedMetadata: Story = {
  args: {
    nodes: [mockNodes[0], mockNodes[1], mockNodes[4], mockNodes[5]] // Mix of different metadata scenarios
  }
}

// Complex hierarchy test data
const complexHierarchyNodes = [
  // Root node
  {
    id: 'root',
    procedureId: 'proc-complex',
    parentNodeId: null,
    name: 'Root Strategy Node',
    status: 'ACTIVE',
    metadata: JSON.stringify({
      code: `-- Root strategy
return "base_strategy"`,
      hypothesis: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.'
    }),
    createdAt: '2024-01-15T10:00:00Z',
    updatedAt: '2024-01-15T10:00:00Z'
  },
  
  // First level children (3 nodes)
  {
    id: 'child-1',
    procedureId: 'proc-complex',
    parentNodeId: 'root',
    name: 'Branch A: Heavy Processing',
    status: 'COMPLETED',
    metadata: JSON.stringify({
      code: `-- Heavy processing branch
return process_heavy_load()`,
      hypothesis: 'Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.'
    }),
    createdAt: '2024-01-15T10:05:00Z',
    updatedAt: '2024-01-15T10:05:00Z'
  },
  {
    id: 'child-2',
    procedureId: 'proc-complex',
    parentNodeId: 'root',
    name: 'Branch B: Quick Filter',
    status: 'RUNNING',
    metadata: JSON.stringify({
      code: `-- Quick filter
return apply_filter()`,
      hypothesis: 'Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.'
    }),
    createdAt: '2024-01-15T10:06:00Z',
    updatedAt: '2024-01-15T10:06:00Z'
  },
  {
    id: 'child-3',
    procedureId: 'proc-complex',
    parentNodeId: 'root',
    name: 'Branch C: Fallback Strategy',
    status: 'PENDING',
    metadata: JSON.stringify({
      code: `-- Fallback strategy
return fallback_method()`,
      hypothesis: 'Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.'
    }),
    createdAt: '2024-01-15T10:07:00Z',
    updatedAt: '2024-01-15T10:07:00Z'
  },

  // Child-1 has 3 children (grandchildren level)
  {
    id: 'grandchild-1-1',
    procedureId: 'proc-complex',
    parentNodeId: 'child-1',
    name: 'A1: CPU Intensive Task',
    status: 'COMPLETED',
    metadata: JSON.stringify({
      code: `-- CPU intensive
return cpu_heavy_task()`,
      hypothesis: 'Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    }),
    createdAt: '2024-01-15T10:10:00Z',
    updatedAt: '2024-01-15T10:10:00Z'
  },
  {
    id: 'grandchild-1-2',
    procedureId: 'proc-complex',
    parentNodeId: 'child-1',
    name: 'A2: Memory Optimization',
    status: 'RUNNING',
    metadata: JSON.stringify({
      code: `-- Memory optimization
return optimize_memory()`,
      hypothesis: 'Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    }),
    createdAt: '2024-01-15T10:11:00Z',
    updatedAt: '2024-01-15T10:11:00Z'
  },
  {
    id: 'grandchild-1-3',
    procedureId: 'proc-complex',
    parentNodeId: 'child-1',
    name: 'A3: Cache Management',
    status: 'FAILED',
    metadata: JSON.stringify({
      code: `-- Cache management
return manage_cache()`,
      hypothesis: 'Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    }),
    createdAt: '2024-01-15T10:12:00Z',
    updatedAt: '2024-01-15T10:12:00Z'
  },

  // Child-2 has 0 children (leaf node)

  // Child-3 has 2 children
  {
    id: 'grandchild-3-1',
    procedureId: 'proc-complex',
    parentNodeId: 'child-3',
    name: 'C1: Error Recovery',
    status: 'PENDING',
    metadata: JSON.stringify({
      code: `-- Error recovery
return recover_from_error()`,
      hypothesis: 'Duis aute irure dolor in reprehenderit in voluptate velit esse cillum.'
    }),
    createdAt: '2024-01-15T10:15:00Z',
    updatedAt: '2024-01-15T10:15:00Z'
  },
  {
    id: 'grandchild-3-2',
    procedureId: 'proc-complex',
    parentNodeId: 'child-3',
    name: 'C2: Graceful Degradation',
    status: 'PENDING',
    metadata: JSON.stringify({
      code: `-- Graceful degradation
return degrade_gracefully()`,
      hypothesis: 'Duis aute irure dolor in reprehenderit in voluptate velit esse cillum.'
    }),
    createdAt: '2024-01-15T10:16:00Z',
    updatedAt: '2024-01-15T10:16:00Z'
  },

  // Great-grandchildren (third level) - add a couple under grandchild-1-1
  {
    id: 'great-grandchild-1-1-1',
    procedureId: 'proc-complex',
    parentNodeId: 'grandchild-1-1',
    name: 'A1.1: Thread Pool Management',
    status: 'COMPLETED',
    metadata: JSON.stringify({
      code: `-- Thread pool
return manage_thread_pool()`,
      hypothesis: 'Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia.'
    }),
    createdAt: '2024-01-15T10:20:00Z',
    updatedAt: '2024-01-15T10:20:00Z'
  },
  {
    id: 'great-grandchild-1-1-2',
    procedureId: 'proc-complex',
    parentNodeId: 'grandchild-1-1',
    name: 'A1.2: Resource Allocation',
    status: 'RUNNING',
    metadata: JSON.stringify({
      code: `-- Resource allocation
return allocate_resources()`,
      hypothesis: 'Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia.'
    }),
    createdAt: '2024-01-15T10:21:00Z',
    updatedAt: '2024-01-15T10:21:00Z'
  },

  // And one more level under grandchild-3-1 for maximum complexity
  {
    id: 'great-grandchild-3-1-1',
    procedureId: 'proc-complex',
    parentNodeId: 'grandchild-3-1',
    name: 'C1.1: Retry Logic',
    status: 'PENDING',
    metadata: JSON.stringify({
      code: `-- Retry logic
return implement_retry()`,
      hypothesis: 'Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia.'
    }),
    createdAt: '2024-01-15T10:25:00Z',
    updatedAt: '2024-01-15T10:25:00Z'
  }
]

export const ComplexHierarchy: Story = {
  args: {
    nodes: complexHierarchyNodes,
    initiallyExpanded: ['child-1', 'child-3', 'grandchild-1-1'] // Expand some branches to show the hierarchy
  },
  parameters: {
    docs: {
      description: {
        story: `
This story tests a complex hierarchy with multiple levels:
- 1 Root node
- 3 First-level children (branches A, B, C)
- Branch A: 3 children (A1, A2, A3)
- Branch B: 0 children (leaf node)  
- Branch C: 2 children (C1, C2)
- A1 has 2 great-grandchildren (A1.1, A1.2)
- C1 has 1 great-grandchild (C1.1)

Total: 13 nodes across 4 levels of nesting.
        `
      }
    }
  }
}
