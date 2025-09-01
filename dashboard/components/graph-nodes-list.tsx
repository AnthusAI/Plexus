"use client"
import React, { useState, useEffect } from "react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { Button } from "@/components/ui/button"
import { Trash2, MoreHorizontal } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { 
  ChevronDown, 
  ChevronRight, 
  Clock, 
  CheckCircle, 
  XCircle, 
  Loader2,
  Network
} from "lucide-react"
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
          } else if (type === 'update') {
            setNodes(prev => prev.map(node => 
              node.id === data.id ? { ...node, ...data } : node
            ));
          } else if (type === 'delete') {
            setNodes(prev => prev.filter(node => node.id !== data.id));
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
          query ListGraphNodesByProcedureCreatedAt(
            $procedureId: ID!
            $sortDirection: ModelSortDirection
          ) {
            listGraphNodesByProcedureCreatedAt(
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

      const fetchedNodes = (result as any).data?.listGraphNodesByProcedureCreatedAt?.items || []
      setNodes(fetchedNodes)
    } catch (err) {
      console.error('Error loading nodes:', err)
      setError(err instanceof Error ? err.message : 'Failed to load nodes')
    } finally {
      setIsLoading(false)
    }
  }

  const handleDeleteNode = async (nodeId: string) => {
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

  const getStatusIcon = (status?: string | null) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'running':
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />
      default:
        return <Network className="h-4 w-4 text-muted-foreground" />
    }
  }

  const getStatusColor = (status?: string | null) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'running':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      case 'failed':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      case 'pending':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
    }
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
        <Card className="mb-2">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {hasChildren && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleNodeExpansion(node.id)}
                    className="h-6 w-6 p-0"
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                  </Button>
                )}
                {!hasChildren && <div className="w-6" />}
                
                {getStatusIcon(node.status)}
                
                <div>
                  <h4 className="font-medium text-sm">
                    {node.name || `Node ${node.id.slice(-8)}`}
                  </h4>
                  <div className="flex items-center gap-2 mt-1">
                    <Badge variant="secondary" className={getStatusColor(node.status)}>
                      {node.status || 'Unknown'}
                    </Badge>
                    <Timestamp time={node.updatedAt} variant="relative" className="text-xs text-muted-foreground" />
                  </div>
                </div>
              </div>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                    <MoreHorizontal className="h-3 w-3" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem 
                    onClick={() => handleDeleteNode(node.id)}
                    className="text-destructive"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </CardHeader>

          {node.metadata && (
            <CardContent className="pt-0">
              <div className="text-xs text-muted-foreground">
                <pre className="whitespace-pre-wrap font-mono bg-muted p-2 rounded text-xs overflow-x-auto">
                  {typeof node.metadata === 'string' 
                    ? node.metadata 
                    : JSON.stringify(node.metadata, null, 2)
                  }
                </pre>
              </div>
            </CardContent>
          )}
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
