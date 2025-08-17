"use client"
import React, { useState, useEffect } from "react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import NodeChatMessages from "./node-chat-messages"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
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
  FileText, 
  PlayCircle, 
  CheckCircle, 
  XCircle, 
  AlertCircle,
  GitCommitVertical,
  GitCompare,
  GitMerge,
  Lightbulb,
  FileJson
} from "lucide-react"
import Editor from "@monaco-editor/react"
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher, getCommonMonacoOptions, configureYamlLanguage } from "@/lib/monaco-theme"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"

// Types based on our GraphQL schema
type ExperimentNode = Schema['ExperimentNode']['type']
type ExperimentNodeVersion = Schema['ExperimentNodeVersion']['type']

interface ExperimentNodeWithLatestVersion extends ExperimentNode {
  latestVersion?: ExperimentNodeVersion
}

const client = generateClient<Schema>()

// Status icons and colors - different icons for root nodes vs hypothesis nodes
const getNodeIcon = (node: ExperimentNodeWithLatestVersion) => {
  // Check if this node has a hypothesis (indicating it's a hypothesis node)
  const hasHypothesis = node.latestVersion?.hypothesis && node.latestVersion.hypothesis.trim() !== ''
  
  if (hasHypothesis) {
    return <GitMerge className="h-4 w-4 text-foreground" />
  } else {
    // Root node or node without hypothesis
    return <GitCommitVertical className="h-4 w-4 text-foreground" />
  }
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'QUEUED':
      return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
    case 'RUNNING':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
    case 'SUCCEEDED':
      return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
    case 'FAILED':
      return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
    default:
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
  }
}

interface Props {
  experimentId: string
}

export default function ExperimentNodesList({ experimentId }: Props) {
  const [nodes, setNodes] = useState<ExperimentNodeWithLatestVersion[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deletingNodeId, setDeletingNodeId] = useState<string | null>(null)

  // Load experiment nodes
  useEffect(() => {
    const loadExperimentNodes = async () => {
      if (!experimentId) {
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        setError(null)
        
        console.log('ExperimentNodesList: Loading nodes for experiment ID:', experimentId)
        
        // Query experiment nodes using the GSI for better performance and complete results
        const { data: nodesData, errors } = await client.models.ExperimentNode.listExperimentNodeByExperimentIdAndCreatedAt({
          experimentId: experimentId,
          limit: 1000 // Ensure we get all nodes
        })

        console.log('ExperimentNodesList: Filtered GraphQL response:', { nodesData, errors })

        if (errors) {
          console.error('GraphQL errors loading experiment nodes:', errors)
          setError('Failed to load experiment nodes: ' + errors.map((e: any) => e.message).join(', '))
          return
        }

        if (!nodesData || nodesData.length === 0) {
          console.log('ExperimentNodesList: No nodes found for experiment', experimentId)
          setNodes([])
          setIsLoading(false)
          return
        }

        console.log('ExperimentNodesList: Found', nodesData.length, 'nodes')

        // For each node, get its latest version
        const nodesWithVersions: ExperimentNodeWithLatestVersion[] = []
        
        for (const node of nodesData) {
          try {
            // Get the latest version for this node
            console.log(`ExperimentNodesList: Loading versions for node ${node.id}`)
            // Try using the GSI first for better performance
            let versionsData = null
            let versionErrors = null
            
            try {
              const gsiResult = await (client.models.ExperimentNodeVersion.listExperimentNodeVersionByNodeIdAndCreatedAt as any)({
                nodeId: node.id,
                limit: 10
              })
              versionsData = gsiResult.data
              versionErrors = gsiResult.errors
              console.log(`ExperimentNodesList: GSI query for node ${node.id} returned ${versionsData ? versionsData.length : 0} versions`)
            } catch (gsiError) {
              console.warn(`ExperimentNodesList: GSI query failed for node ${node.id}, falling back to filter:`, gsiError)
              
              // Fallback to filter-based query
              const filterResult = await (client.models.ExperimentNodeVersion.list as any)({
                filter: { nodeId: { eq: node.id } },
                limit: 10
              })
              versionsData = filterResult.data
              versionErrors = filterResult.errors
              console.log(`ExperimentNodesList: Filter query for node ${node.id} returned ${versionsData ? versionsData.length : 0} versions`)
            }
            
            console.log(`ExperimentNodesList: Version query result for node ${node.id}:`, {
              versionsCount: versionsData ? versionsData.length : 0,
              errors: versionErrors,
              firstVersion: versionsData && versionsData.length > 0 ? versionsData[0] : null
            })

            let latestVersion = null

            if (versionsData && versionsData.length > 0) {
              // Sort versions by createdAt to get the latest
              const sortedVersions = versionsData.sort((a: any, b: any) => {
                if (a.createdAt && b.createdAt) {
                  return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
                }
                return 0
              })
              latestVersion = sortedVersions[0]
              
              // Debug logging to see what's in the version data
              console.log(`ExperimentNodesList: Latest version for node ${node.id}:`, {
                id: latestVersion.id,
                hypothesis: latestVersion.hypothesis,
                hasHypothesis: !!latestVersion.hypothesis,
                hypothesisLength: latestVersion.hypothesis ? latestVersion.hypothesis.length : 0,
                allFields: Object.keys(latestVersion)
              })
            }

            nodesWithVersions.push({
              ...node,
              latestVersion: latestVersion || undefined
            })
          } catch (versionError) {
            console.warn(`Failed to load versions for node ${node.id}:`, versionError)
            // Add node without version info
            nodesWithVersions.push({
              ...node
            })
          }
        }

        // Sort nodes in chronological order by createdAt (oldest first, so root appears at top)
        nodesWithVersions.sort((a, b) => {
          if (a.createdAt && b.createdAt) {
            return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
          }
          return 0
        })
        
        setNodes(nodesWithVersions)
        
      } catch (err) {
        console.error('Error loading experiment nodes:', err)
        setError(err instanceof Error ? err.message : 'Failed to load experiment nodes')
      } finally {
        setIsLoading(false)
      }
    }

    loadExperimentNodes()
  }, [experimentId])

  const handleDeleteNode = async (nodeId: string) => {
    if (!nodeId) return
    
    try {
      setDeletingNodeId(nodeId)
      console.log('Deleting experiment node:', nodeId)
      
      // Delete the node using GraphQL mutation
      const { data: deleteResult, errors } = await (client.models.ExperimentNode.delete as any)({
        id: nodeId
      })
      
      console.log('Delete result:', { deleteResult, errors })
      
      if (errors) {
        console.error('GraphQL errors deleting node:', errors)
        setError('Failed to delete node: ' + errors.map((e: any) => e.message).join(', '))
        return
      }
      
      // Remove the node from local state
      setNodes(prevNodes => prevNodes.filter(node => node.id !== nodeId))
      
      console.log('Successfully deleted node:', nodeId)
      
    } catch (err) {
      console.error('Error deleting node:', err)
      setError(err instanceof Error ? err.message : 'Failed to delete node')
    } finally {
      setDeletingNodeId(null)
    }
  }


  if (isLoading) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <GitCompare className="h-5 w-5" />
          Nodes
        </h3>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse bg-background border-none">
              <CardContent className="p-4">
                <div className="space-y-2">
                  <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
                  <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <GitCompare className="h-5 w-5" />
          Nodes
        </h3>
        <Card className="bg-background border-none">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
              <XCircle className="h-4 w-4" />
              <span>Error: {error}</span>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (nodes.length === 0) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <GitCompare className="h-5 w-5" />
          Nodes
        </h3>
        <Card className="bg-background border-none">
          <CardContent className="p-6 text-center">
            <GitCommitVertical className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
            <p className="text-muted-foreground">No experiment nodes found</p>
            <p className="text-sm text-muted-foreground mt-1">
              Nodes will appear here when AI agents create new hypotheses
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2">
        <GitCompare className="h-5 w-5" />
        Nodes ({nodes.length})
      </h3>
      
      <div className="space-y-3">
        {nodes.map((node) => {
          const latestStatus = node.latestVersion?.status || 'UNKNOWN'
          
          return (
            <Card 
              key={node.id} 
              className="bg-background border-none"
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      {getNodeIcon(node)}
                      <p className="text-sm font-medium">
                        {node.name || "Untitled"}
                      </p>
                    </div>
                    <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                      <Clock className="h-3 w-3" />
                      {node.createdAt ? new Date(node.createdAt).toLocaleString() : "Unknown time"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Status badge moved to left side of action buttons */}
                    <Badge 
                      variant="secondary" 
                      className={`text-xs ${getStatusColor(latestStatus)}`}
                    >
                      {latestStatus}
                    </Badge>
                    
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                          aria-label="More options"
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <DropdownMenuItem 
                              onSelect={(e) => e.preventDefault()}
                              disabled={deletingNodeId === node.id}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete Experiment Node</AlertDialogTitle>
                              <AlertDialogDescription>
                                Are you sure you want to delete this experiment node? This will permanently 
                                delete the node and all its versions. This action cannot be undone.
                                <br /><br />
                                <strong>Node:</strong> {node.name || "Untitled"}
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() => handleDeleteNode(node.id)}
                                className="bg-red-600 hover:bg-red-700"
                              >
                                {deletingNodeId === node.id ? 'Deleting...' : 'Delete Node'}
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>

                {/* Collapsible sections for hypothesis, code, and insight */}
                {node.latestVersion && (
                  <Accordion type="multiple" className="w-full">
                    {/* Hypothesis Section */}
                    {node.latestVersion.hypothesis && (
                      <AccordionItem value="hypothesis" className="border-b-0">
                        <AccordionTrigger className="hover:no-underline py-2 px-0 justify-start [&>svg]:hidden group">
                          <div className="flex items-center gap-2">
                            <Lightbulb className="h-3 w-3 text-muted-foreground" />
                            <span className="text-sm font-medium leading-none text-muted-foreground">Hypothesis</span>
                            <ChevronRight className="h-3 w-3 text-muted-foreground transition-transform duration-200 group-data-[state=open]:hidden" />
                            <ChevronDown className="h-3 w-3 text-muted-foreground transition-transform duration-200 hidden group-data-[state=open]:block" />
                          </div>
                        </AccordionTrigger>
                        <AccordionContent className="pt-0 pb-4">
                          <div className="text-sm text-muted-foreground whitespace-pre-wrap">
                            {node.latestVersion.hypothesis}
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    )}

                    {/* Code Configuration Section */}
                    {node.latestVersion.code && (
                      <AccordionItem value="code" className="border-b-0">
                        <AccordionTrigger className="hover:no-underline py-2 px-0 justify-start [&>svg]:hidden group">
                          <div className="flex items-center gap-2">
                            <FileJson className="h-3 w-3 text-muted-foreground" />
                            <span className="text-sm font-medium leading-none text-muted-foreground">Code</span>
                            <ChevronRight className="h-3 w-3 text-muted-foreground transition-transform duration-200 group-data-[state=open]:hidden" />
                            <ChevronDown className="h-3 w-3 text-muted-foreground transition-transform duration-200 hidden group-data-[state=open]:block" />
                          </div>
                        </AccordionTrigger>
                        <AccordionContent className="pt-0 pb-4">
                          <div className="overflow-hidden">
                            <Editor
                              height="300px"
                              defaultLanguage="yaml"
                              value={node.latestVersion.code}
                              onMount={(editor, monaco) => {
                                defineCustomMonacoThemes(monaco)
                                applyMonacoTheme(monaco)
                                setupMonacoThemeWatcher(monaco)
                                configureYamlLanguage(monaco)
                              }}
                              options={{
                                ...getCommonMonacoOptions(),
                                readOnly: true,
                                minimap: { enabled: false },
                                scrollBeyondLastLine: false,
                                wordWrap: 'on',
                                fontSize: 13,
                                lineHeight: 20,
                                tabSize: 2,
                                insertSpaces: true
                              }}
                            />
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    )}

                    {/* Insight Section */}
                    {node.latestVersion.insight && (
                      <AccordionItem value="insight" className="border-b-0">
                        <AccordionTrigger className="hover:no-underline py-2 px-0 justify-start [&>svg]:hidden group">
                          <div className="flex items-center gap-2">
                            <FileText className="h-3 w-3 text-muted-foreground" />  
                            <span className="text-sm font-medium leading-none text-muted-foreground">Insight</span>
                            <ChevronRight className="h-3 w-3 text-muted-foreground transition-transform duration-200 group-data-[state=open]:hidden" />
                            <ChevronDown className="h-3 w-3 text-muted-foreground transition-transform duration-200 hidden group-data-[state=open]:block" />
                          </div>
                        </AccordionTrigger>
                        <AccordionContent className="pt-0 pb-4">
                          <div className="text-sm text-muted-foreground whitespace-pre-wrap">
                            {node.latestVersion.insight}
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    )}
                    
                    {/* Chat Messages Section */}
                    <NodeChatMessages nodeId={node.id} />
                  </Accordion>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}