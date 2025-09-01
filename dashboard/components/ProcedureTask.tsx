import React, { useCallback, useState, useEffect } from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { BaseTaskData } from '@/types/base'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { Waypoints, MoreHorizontal, Square, X, Trash2, Columns2, Edit, Copy, FileText, ChevronRight, ChevronDown, FileJson, Expand, BookOpenCheck } from 'lucide-react'
import { Timestamp } from './ui/timestamp'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { toast } from 'sonner'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import Editor from "@monaco-editor/react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher, getCommonMonacoOptions, configureYamlLanguage } from "@/lib/monaco-theme"
import GraphNodesList from "./graph-nodes-list"
import ProcedureConversationViewer from "./procedure-conversation-viewer"

const client = generateClient<Schema>()

// Minimal fallback for YAML editor - actual templates come from procedure data
const MINIMAL_YAML_FALLBACK = `class: "BeamSearch"
# Loading procedure configuration...`

// Define the procedure data type
export interface ProcedureTaskData extends BaseTaskData {
  id: string
  featured: boolean
  rootNodeId?: string
  createdAt: string
  updatedAt: string
  scorecard?: {
    name: string
  } | null
  score?: {
    name: string
  } | null
  taskId?: string
  task?: {
    id: string
    type: string
    status: string
    target: string
    command: string
    description?: string
    dispatchStatus?: string
    metadata?: string
    createdAt?: string
    startedAt?: string
    completedAt?: string
    estimatedCompletionAt?: string
    errorMessage?: string
    errorDetails?: string
    currentStageId?: string
    stages?: {
      items: Array<{
        id: string
        name: string
        order: number
        status: string
        statusMessage?: string
        startedAt?: string
        completedAt?: string
        estimatedCompletionAt?: string
        processedItems?: number
        totalItems?: number
      }>
    }
  }
}

interface ProcedureTaskProps {
  variant: 'grid' | 'detail'
  procedure: ProcedureTaskData
  onClick?: () => void
  isSelected?: boolean
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  onDelete?: (procedureId: string) => void
  onEdit?: (procedureId: string) => void
  onDuplicate?: (procedureId: string) => void
  onConversationFullscreenChange?: (isFullscreen: boolean) => void
}

const ProcedureTask: React.FC<ProcedureTaskProps> = ({
  variant,
  procedure,
  onClick,
  isSelected = false,
  isFullWidth = false,
  onToggleFullWidth,
  onClose,
  onDelete,
  onEdit,
  onDuplicate,
  onConversationFullscreenChange
}) => {
  const [isCodeExpanded, setIsCodeExpanded] = useState(false)
  const [isNodesExpanded, setIsNodesExpanded] = useState(false)
  const [isConversationExpanded, setIsConversationExpanded] = useState(false)
  const [procedureCode, setProcedureCode] = useState<string>('')
  const [isLoadingCode, setIsLoadingCode] = useState(false)
  const [sessionCount, setSessionCount] = useState(0)

  // Monaco theme watcher will be setup in editor onMount

  // Load procedure code when detail view is opened
  useEffect(() => {
    if (variant === 'detail' && procedure.id && !procedureCode && !isLoadingCode) {
      loadProcedureCode()
    }
  }, [variant, procedure.id, procedureCode, isLoadingCode])

  const loadProcedureCode = async () => {
    if (!procedure.id) return
    
    try {
      setIsLoadingCode(true)
      const result = await client.graphql({
        query: `
          query GetProcedure($id: ID!) {
            getProcedure(id: $id) {
              id
              code
            }
          }
        `,
        variables: { id: procedure.id }
      })
      
      const fetchedProcedure = (result as any).data?.getProcedure
      if (fetchedProcedure?.code) {
        setProcedureCode(fetchedProcedure.code)
      } else {
        setProcedureCode(MINIMAL_YAML_FALLBACK)
      }
    } catch (error) {
      console.error('Error loading procedure code:', error)
      setProcedureCode(MINIMAL_YAML_FALLBACK)
    } finally {
      setIsLoadingCode(false)
    }
  }

  const handleDelete = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    if (onDelete && procedure.id) {
      if (window.confirm('Are you sure you want to delete this procedure?')) {
        onDelete(procedure.id)
      }
    }
  }, [onDelete, procedure.id])

  const handleEdit = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    if (onEdit && procedure.id) {
      onEdit(procedure.id)
    }
  }, [onEdit, procedure.id])

  const handleDuplicate = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    if (onDuplicate && procedure.id) {
      onDuplicate(procedure.id)
    }
  }, [onDuplicate, procedure.id])

  const handleCopyId = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    if (procedure.id) {
      navigator.clipboard.writeText(procedure.id)
      toast.success('Procedure ID copied to clipboard')
    }
  }, [procedure.id])

  const handleConversationFullscreenChange = useCallback((isFullscreen: boolean) => {
    if (onConversationFullscreenChange) {
      onConversationFullscreenChange(isFullscreen)
    }
  }, [onConversationFullscreenChange])

  if (variant === 'grid') {
    return (
      <Card 
        className={cn(
          "cursor-pointer transition-all duration-200 hover:shadow-md border-2",
          isSelected ? "border-primary shadow-md" : "border-border hover:border-accent"
        )}
        onClick={onClick}
      >
        <CardContent className="p-4">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              <Waypoints className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium text-muted-foreground">
                Procedure
              </span>
              {procedure.featured && (
                <div className="px-2 py-1 bg-primary/10 text-primary text-xs rounded-full">
                  Featured
                </div>
              )}
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                <Button variant="ghost" size="icon" className="h-6 w-6">
                  <MoreHorizontal className="h-3 w-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleEdit}>
                  <Edit className="mr-2 h-4 w-4" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleDuplicate}>
                  <Copy className="mr-2 h-4 w-4" />
                  Duplicate
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleCopyId}>
                  <FileText className="mr-2 h-4 w-4" />
                  Copy ID
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleDelete} className="text-destructive">
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          <div className="space-y-2">
            <h3 className="font-semibold text-sm line-clamp-2">
              {procedure.title}
            </h3>
            
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Timestamp time={procedure.updatedAt} variant="relative" />
            </div>

            {procedure.task && (
              <div className="mt-3 p-2 bg-muted/50 rounded-md">
                <div className="flex items-center gap-2 text-xs">
                  <Badge variant="outline" className="text-xs">
                    {procedure.task.status || 'Unknown'}
                  </Badge>
                  <span className="text-muted-foreground">
                    {procedure.task.description || procedure.task.type}
                  </span>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    )
  }

  // Detail variant
  return (
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="flex-shrink-0 p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Waypoints className="h-5 w-5 text-primary" />
            <div>
              <h2 className="text-lg font-semibold">{procedure.title}</h2>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Timestamp time={procedure.updatedAt} variant="relative" />
                {procedure.featured && (
                  <div className="px-2 py-1 bg-primary/10 text-primary text-xs rounded-full">
                    Featured
                  </div>
                )}
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {onToggleFullWidth && (
              <Button
                variant="ghost"
                size="icon"
                onClick={onToggleFullWidth}
                className="h-8 w-8"
              >
                {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Expand className="h-4 w-4" />}
              </Button>
            )}
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleEdit}>
                  <Edit className="mr-2 h-4 w-4" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleDuplicate}>
                  <Copy className="mr-2 h-4 w-4" />
                  Duplicate
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleCopyId}>
                  <FileText className="mr-2 h-4 w-4" />
                  Copy ID
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleDelete} className="text-destructive">
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {onClose && (
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
                className="h-8 w-8"
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-4 space-y-4">
          {/* Task Status */}
          {procedure.task && (
            <div className="p-4 bg-muted/30 rounded-md">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium">Task Status</h4>
                <Badge variant="outline" className={
                  procedure.task.status === 'COMPLETED' ? 'bg-green-100 text-green-800' :
                  procedure.task.status === 'RUNNING' ? 'bg-blue-100 text-blue-800' :
                  procedure.task.status === 'FAILED' ? 'bg-red-100 text-red-800' :
                  'bg-gray-100 text-gray-800'
                }>
                  {procedure.task.status || 'Unknown'}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                {procedure.task.description || procedure.task.type}
              </p>
              {procedure.task.errorMessage && (
                <p className="text-sm text-red-600 mt-2">
                  {procedure.task.errorMessage}
                </p>
              )}
            </div>
          )}

          {/* Expandable Sections */}
          <Accordion type="multiple" value={[
            ...(isCodeExpanded ? ['code'] : []),
            ...(isNodesExpanded ? ['nodes'] : []),
            ...(isConversationExpanded ? ['conversation'] : [])
          ]}>
            {/* Code Section */}
            <AccordionItem value="code">
              <AccordionTrigger 
                onClick={() => setIsCodeExpanded(!isCodeExpanded)}
                className="hover:no-underline"
              >
                <div className="flex items-center gap-2">
                  <FileJson className="h-4 w-4" />
                  <span>Configuration</span>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div className="border rounded-md overflow-hidden">
                  <Editor
                    height="400px"
                    defaultLanguage="yaml"
                    value={isLoadingCode ? "# Loading..." : procedureCode}
                    options={{
                      ...getCommonMonacoOptions(),
                      readOnly: true,
                    }}
                    onMount={(editor, monaco) => {
                      defineCustomMonacoThemes(monaco)
                      applyMonacoTheme(monaco)
                      configureYamlLanguage(monaco)
                    }}
                  />
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Nodes Section */}
            <AccordionItem value="nodes">
              <AccordionTrigger 
                onClick={() => setIsNodesExpanded(!isNodesExpanded)}
                className="hover:no-underline"
              >
                <div className="flex items-center gap-2">
                  <Waypoints className="h-4 w-4" />
                  <span>Graph Nodes</span>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <GraphNodesList procedureId={procedure.id} />
              </AccordionContent>
            </AccordionItem>

            {/* Conversation Section */}
            <AccordionItem value="conversation">
              <AccordionTrigger 
                onClick={() => setIsConversationExpanded(!isConversationExpanded)}
                className="hover:no-underline"
              >
                <div className="flex items-center gap-2">
                  <BookOpenCheck className="h-4 w-4" />
                  <span>Procedures</span>
                  {sessionCount > 0 && (
                    <span className="ml-1 px-2 py-0.5 bg-muted text-muted-foreground text-xs rounded-full">
                      {sessionCount}
                    </span>
                  )}
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <ProcedureConversationViewer 
                  procedureId={procedure.id}
                  onSessionCountChange={setSessionCount}
                  onFullscreenChange={handleConversationFullscreenChange}
                />
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </div>
    </div>
  )
}

export default ProcedureTask
