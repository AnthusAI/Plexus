"use client"
import React, { useState, useEffect } from "react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { Button } from "@/components/ui/button"
import { Trash2, MoreHorizontal, Loader2, Network } from "lucide-react"
import { CardButton } from "@/components/CardButton"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Timestamp } from "./ui/timestamp"
import { toast } from "sonner"
import { observeGraphNodeUpdates } from "@/utils/subscriptions"

const client = generateClient<Schema>()

type GraphNode = Schema['GraphNode']['type']

interface GraphNodesListProps {
  procedureId: string
}

const GraphNodesList: React.FC<GraphNodesListProps> = ({ procedureId }) => {
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (procedureId) {
      loadNodes()
    }
  }, [procedureId])

  // Subscribe to node updates
  useEffect(() => {
    const subscription = observeGraphNodeUpdates().subscribe({
      next: (value: any) => {
        const { type, data } = value;
        if (data?.procedureId === procedureId) {
          if (type === 'create') {
            setNodes(prev => [...prev, data]);
            // Expand new nodes by default
            setExpandedNodes(prev => new Set([...prev, data.id]));
          } else if (type === 'update') {
            setNodes(prev => prev.map(node => 
              node.id === data.id ? { ...node, ...data } : node
            ));
          } else if (type === 'delete') {
            setNodes(prev => prev.filter(node => node.id !== data.id));
            // Remove deleted node from expanded set
            setExpandedNodes(prev => {
              const newSet = new Set(prev);
              newSet.delete(data.id);
              return newSet;
            });
          }
        }
      },
      error: (error: any) => {
        console.error('GraphNode subscription error:', error);
      }
    });

    return () => subscription.unsubscribe();
  }, [procedureId]);

  const loadNodes = async () => {
    try {
      setIsLoading(true)
      setError(null)
      
      const result = await client.graphql({
        query: `
          query ListGraphNodeByProcedureIdAndCreatedAt(
            $procedureId: ID!
            $sortDirection: ModelSortDirection
          ) {
            listGraphNodeByProcedureIdAndCreatedAt(
              procedureId: $procedureId
              sortDirection: $sortDirection
            ) {
              items {
                id
                procedureId
                parentNodeId
                name
                status
                metadata
                createdAt
                updatedAt
              }
            }
          }
        `,
        variables: {
          procedureId,
          sortDirection: 'ASC'
        }
      })

      const fetchedNodes = (result as any).data?.listGraphNodeByProcedureIdAndCreatedAt?.items || []
      setNodes(fetchedNodes)
      
      // Set all nodes as expanded by default
      const allNodeIds = new Set(fetchedNodes.map((node: GraphNode) => node.id as string))
      setExpandedNodes(allNodeIds)
    } catch (err) {
      console.error('Error loading nodes:', err)
      setError(err instanceof Error ? err.message : 'Failed to load nodes')
    } finally {
      setIsLoading(false)
    }
  }

  const handleDeleteNode = async (nodeId: string) => {
    const confirmed = window.confirm('Are you sure you want to delete this node? This action cannot be undone.')
    
    if (!confirmed) {
      return
    }

    try {
      await client.graphql({
        query: `
          mutation DeleteGraphNode($input: DeleteGraphNodeInput!) {
            deleteGraphNode(input: $input) {
              id
            }
          }
        `,
        variables: {
          input: { id: nodeId }
        }
      })
      
      setNodes(prev => prev.filter(node => node.id !== nodeId))
      toast.success('Node deleted successfully')
    } catch (error) {
      console.error('Error deleting node:', error)
      toast.error('Failed to delete node')
    }
  }

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

  // Helper function to parse and render node metadata
  const renderNodeMetadata = (node: GraphNode) => {
    let parsedMetadata: any = {}
    
    try {
      if (typeof node.metadata === 'string') {
        parsedMetadata = JSON.parse(node.metadata)
      } else if (node.metadata) {
        parsedMetadata = node.metadata
      }
    } catch (error) {
      // If parsing fails, show raw metadata
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

  const getStatusColor = (status?: string | null) => {
    // Use neutral background color since status names are not standardized
    return 'bg-background text-foreground border'
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span className="ml-2">Loading nodes...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center text-destructive p-8">
        <p>Error loading nodes: {error}</p>
        <Button onClick={loadNodes} variant="outline" className="mt-2">
          Retry
        </Button>
      </div>
    )
  }

  if (nodes.length === 0) {
    return (
      <div className="text-center text-muted-foreground p-8">
        <Network className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>No graph nodes found for this procedure.</p>
      </div>
    )
  }

  // Build tree structure
  const rootNodes = nodes.filter(node => !node.parentNodeId)
  const nodeMap = new Map(nodes.map(node => [node.id, node]))
  
  const getChildNodes = (parentId: string): GraphNode[] => {
    return nodes.filter(node => node.parentNodeId === parentId)
  }

  const renderNode = (node: GraphNode, level: number = 0) => {
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
                <div className="mt-1">
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
                      onSelect={() => handleDeleteNode(node.id)}
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

export default GraphNodesList
