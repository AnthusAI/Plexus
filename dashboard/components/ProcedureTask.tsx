import React, { useCallback, useState, useEffect } from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { BaseTaskData } from '@/types/base'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { Waypoints, MoreHorizontal, Square, X, Trash2, Columns2, Edit, Copy, FileText, ChevronRight, ChevronDown, FileJson, Expand, BookOpenCheck } from 'lucide-react'

import { Timestamp } from './ui/timestamp'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
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
import { ParametersDisplay } from "./ui/ParametersDisplay"
import { parseParametersFromYaml } from "@/lib/parameter-parser"
import type { ParameterDefinition, ParameterValue } from "@/types/parameters"
import * as yaml from 'js-yaml'

const client = generateClient<Schema>()

// Minimal fallback for YAML editor - actual templates come from procedure data
const MINIMAL_YAML_FALLBACK = `class: "BeamSearch"
# Loading procedure configuration...`

// Status display helper function
const getStatusDisplay = (status?: string): { text: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' } => {
  if (!status) return { text: 'Pending', variant: 'secondary' }
  
  const statusMap: Record<string, { text: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
    // Task states
    PENDING: { text: 'Pending', variant: 'secondary' },
    RUNNING: { text: 'Running', variant: 'default' },
    COMPLETED: { text: 'Completed', variant: 'outline' },
    FAILED: { text: 'Failed', variant: 'destructive' },
    // Procedure states (state machine)
    START: { text: 'Start', variant: 'secondary' },
    HYPOTHESIS: { text: 'Hypothesis', variant: 'default' },
    CODE: { text: 'Coding', variant: 'default' },
    ERROR: { text: 'Error', variant: 'destructive' },
  }
  
  const upperStatus = status.toUpperCase()
  return statusMap[upperStatus] || { text: status, variant: 'secondary' }
}

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
    metadata?: any
    createdAt?: string
    startedAt?: string
    completedAt?: string
    estimatedCompletionAt?: string
    errorMessage?: string
    errorDetails?: any
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
  } | null
}

export interface ProcedureTaskProps {
  variant: 'grid' | 'detail'
  procedure: ProcedureTaskData
  onClick?: () => void
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  isSelected?: boolean
  onDelete?: (procedureId: string) => void
  onEdit?: (procedureId: string) => void
  onDuplicate?: (procedureId: string) => void
  onConversationFullscreenChange?: (isFullscreen: boolean) => void
}

export default function ProcedureTask({
  variant,
  procedure,
  onClick,
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  isSelected,
  onDelete,
  onEdit,
  onDuplicate,
  onConversationFullscreenChange
}: ProcedureTaskProps) {
  const [loadedYaml, setLoadedYaml] = useState<string>('')
  const [isLoadingYaml, setIsLoadingYaml] = useState(false)
  const [sessionCount, setSessionCount] = useState(0)
  const [isConversationFullscreen, setIsConversationFullscreen] = useState(false)
  const [parameters, setParameters] = useState<ParameterDefinition[]>([])
  const [parameterValues, setParameterValues] = useState<ParameterValue>({})

  // Load procedure YAML when component mounts or procedure changes
  useEffect(() => {
    if (variant === 'detail' && procedure.id) {
      loadProcedureYaml()
    }
  }, [variant, procedure.id])

  // Parse parameters from YAML whenever it changes
  useEffect(() => {
    if (loadedYaml) {
      try {
        const parsedParams = parseParametersFromYaml(loadedYaml)
        console.log('[ProcedureTask] Parsed parameters:', parsedParams.length, parsedParams)
        setParameters(parsedParams)
        
        // Extract values from the YAML
        const config = yaml.load(loadedYaml) as any
        console.log('[ProcedureTask] YAML config:', config)
        if (config && config.parameters && Array.isArray(config.parameters)) {
          const values: ParameterValue = {}
          config.parameters.forEach((param: any) => {
            if (param.value !== undefined) {
              values[param.name] = param.value
            }
          })
          console.log('[ProcedureTask] Parameter values:', values)
          setParameterValues(values)
        } else {
          console.log('[ProcedureTask] No parameters array found in config')
          setParameterValues({})
        }
      } catch (error) {
        console.error('Error parsing parameters:', error)
        setParameters([])
        setParameterValues({})
      }
    }
  }, [loadedYaml])

  const loadProcedureYaml = async () => {
    if (!procedure.id) return
    
    try {
      setIsLoadingYaml(true)
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
      
      const procedureData = (result as any).data?.getProcedure
      if (procedureData?.code) {
        setLoadedYaml(procedureData.code)
      }
    } catch (error) {
      console.error('Error loading procedure YAML:', error)
      toast.error('Failed to load procedure configuration')
    } finally {
      setIsLoadingYaml(false)
    }
  }

  const handleConversationFullscreenChange = useCallback((isFullscreen: boolean) => {
    setIsConversationFullscreen(isFullscreen)
    if (onConversationFullscreenChange) {
      onConversationFullscreenChange(isFullscreen)
    }
  }, [onConversationFullscreenChange])

  // Convert procedure data to task data format
  const taskData: BaseTaskData = {
    id: procedure.id,
    title: procedure.title,
    description: procedure.description,
    errorMessage: procedure.errorMessage,
    command: procedure.command
  }

  // Create the task object that matches the Task component's expected interface
  // Format stages with proper colors based on status
  const formattedStages = (procedure.task?.stages?.items || []).map((stage: any) => {
    const isCompleted = stage.status === 'COMPLETED';
    const isRunning = stage.status === 'RUNNING';
    const isFailed = stage.status === 'FAILED';
    
    return {
      id: stage.id,
      key: stage.name,
      label: stage.name,
      color: isCompleted ? 'bg-primary' :
             isRunning ? 'bg-secondary' :
             isFailed ? 'bg-false' :
             'bg-neutral',
      name: stage.name,
      order: stage.order,
      status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
      statusMessage: stage.statusMessage,
      startedAt: stage.startedAt,
      completedAt: stage.completedAt,
      estimatedCompletionAt: stage.estimatedCompletionAt,
      processedItems: stage.processedItems,
      totalItems: stage.totalItems,
      completed: isCompleted
    };
  });
  
  const taskObject = {
    id: procedure.id,
    type: 'Procedure',
    name: procedure.title,
    description: procedure.description,
    scorecard: procedure.scorecard?.name || '',
    score: procedure.score?.name || '',
    time: procedure.createdAt,
    command: procedure.command,
    output: (procedure as any).output, // May not exist in type definition yet
    data: taskData,
    stages: formattedStages, // Use formatted stages with colors
    currentStageName: procedure.task?.currentStageId, // Get from task
    processedItems: (procedure as any).processedItems, // May not exist in type definition yet
    totalItems: (procedure as any).totalItems, // May not exist in type definition yet
    startedAt: procedure.task?.startedAt, // Get from task
    estimatedCompletionAt: procedure.task?.estimatedCompletionAt, // Get from task
    completedAt: procedure.task?.completedAt, // Get from task
    status: (procedure.task?.status || 'PENDING') as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
    errorMessage: procedure.task?.errorMessage || procedure.errorMessage
  }

  const headerContent = (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
        >
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {onEdit && (
          <DropdownMenuItem onClick={() => onEdit(procedure.id)}>
            <Edit className="mr-2 h-4 w-4" />
            Edit
          </DropdownMenuItem>
        )}
        {onDuplicate && (
          <DropdownMenuItem onClick={() => onDuplicate(procedure.id)}>
            <Copy className="mr-2 h-4 w-4" />
            Duplicate
          </DropdownMenuItem>
        )}
        {onDelete && (
          <DropdownMenuItem 
            onClick={() => onDelete(procedure.id)}
            className="text-destructive focus:text-destructive"
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )

  const renderHeader = (props: any) => {
    if (variant === 'detail') {
      // Custom header for detail view with status badge
      return (
        <div className="space-y-1.5 p-0 flex flex-col items-start w-full max-w-full px-1">
          <div className="flex justify-between items-start w-full max-w-full gap-3 overflow-hidden">
            <div className="flex flex-col pb-1 leading-none min-w-0 flex-1 overflow-hidden">
              <div className="flex items-center gap-2 mb-1">
                <Waypoints className="h-5 w-5 text-muted-foreground" />
                <span className="text-lg font-semibold text-muted-foreground">Procedure</span>
              </div>
              
              {/* Timestamp */}
              <div className="mb-2">
                <Timestamp time={props.task.time} variant="relative" />
              </div>
              
              {/* Only show scorecard/score if there are no parameters */}
              {parameters.length === 0 && (
                <>
                  {props.task.scorecard && props.task.scorecard.trim() !== '' && (
                    <div className="text-sm text-muted-foreground truncate">{props.task.scorecard}</div>
                  )}
                  {props.task.score && props.task.score.trim() !== '' && (
                    <div className="text-sm text-muted-foreground truncate">{props.task.score}</div>
                  )}
                </>
              )}
            </div>
            <div className="flex flex-col items-end flex-shrink-0 gap-2">
              <div className="flex gap-2">
                {headerContent}
                {onToggleFullWidth && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                    onClick={onToggleFullWidth}
                    aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
                  >
                    {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                  </Button>
                )}
                {onClose && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                    onClick={onClose}
                    aria-label="Close"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )
    } else {
      // Use default TaskHeader for grid view
      return (
        <TaskHeader
          variant={variant}
          task={taskObject}
          controlButtons={controlButtons}
          isFullWidth={isFullWidth}
          onToggleFullWidth={onToggleFullWidth}
          onClose={onClose}
        />
      )
    }
  }

  const renderContent = () => (
    <TaskContent variant={variant} task={taskObject}>
      {variant === 'grid' ? (
        // Empty grid content since all info is now in header
        null
      ) : (
        <div className="p-3">
          {/* Parameters section - show at top if parameters exist */}
          {parameters.length > 0 && (
            <div className="mb-4">
              <ParametersDisplay
                parameters={parameters}
                values={parameterValues}
                variant="table"
              />
            </div>
          )}
          
          {/* Configuration section */}
          <Accordion type="multiple" className="w-full">
            <AccordionItem value="configuration" className="border-b-0">
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
                  {isLoadingYaml ? (
                    <div className="flex items-center justify-center h-32">
                      <span className="text-sm text-muted-foreground">Loading configuration...</span>
                    </div>
                  ) : (
                    <Editor
                      height="400px"
                      defaultLanguage="yaml"
                      value={loadedYaml || MINIMAL_YAML_FALLBACK}
                      onMount={(_, monaco) => {
                        // Configure Monaco editor for YAML
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
                        tabSize: 2,
                        insertSpaces: true,
                      }}
                    />
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
          
          
          {/* Procedure Nodes section */}
          <div className="mt-6 bg-background rounded-lg p-4">
            <GraphNodesList procedureId={procedure.id} />
          </div>
          
          {/* Procedure Conversation section */}
          <div className="mt-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold flex items-center gap-2 text-muted-foreground">
                  <BookOpenCheck className="h-5 w-5" />
                  Tasks ({sessionCount})
                </h3>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                  onClick={() => {
                    handleConversationFullscreenChange(true)
                  }}
                  aria-label="Fullscreen conversation"
                >
                  <Expand className="h-4 w-4" />
                </Button>
              </div>
              <div>
                <ProcedureConversationViewer 
                  procedureId={procedure.id} 
                  onSessionCountChange={setSessionCount}
                  onFullscreenChange={handleConversationFullscreenChange}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </TaskContent>
  )

  // Conversation fullscreen is now handled at the parent level
  // No need to render fullscreen view here anymore

  return (
    <Task
      variant={variant}
      task={taskObject}
      onClick={onClick}
      controlButtons={headerContent}
      isFullWidth={isFullWidth}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
      isSelected={isSelected}
      renderHeader={renderHeader}
      renderContent={renderContent}
    />
  )
}