import React, { useCallback, useState, useEffect } from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { BaseTaskData } from '@/types/base'
import { Card, CardContent } from '@/components/ui/card'
import { Waypoints, MoreHorizontal, Square, X, Trash2, Columns2, Edit, Copy, FileText, ChevronRight, ChevronDown, FileJson } from 'lucide-react'
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
import ExperimentNodesList from "./experiment-nodes-list"

const client = generateClient<Schema>()

// Experiment template with realistic examples
const EXPERIMENT_TEMPLATE = `class: "BeamSearch"

value: |
  -- Extract accuracy score from experiment node's structured data
  local score = experiment_node.value.accuracy or 0
  -- Apply cost penalty to balance performance vs efficiency  
  local penalty = (experiment_node.value.cost or 0) * 0.1
  -- Return single scalar value (higher is better)
  return score - penalty

exploration: |
  You are helping optimize an AI system through beam search experimentation.
  
  You have access to previous experiment results including their configurations, 
  performance metrics, and computed values. Your job is to suggest new experiment 
  variations that might improve performance.
  
  Based on the results so far, propose specific changes to try next. Focus on 
  modifications that could address weaknesses or build on promising directions.
  
  Generate concrete, actionable suggestions for the next experiment iteration.
`

// Define the experiment data type
export interface ExperimentTaskData extends BaseTaskData {
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
}

export interface ExperimentTaskProps {
  variant: 'grid' | 'detail'
  experiment: ExperimentTaskData
  onClick?: () => void
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  isSelected?: boolean
  onDelete?: (experimentId: string) => void
  onEdit?: (experimentId: string) => void
  onDuplicate?: (experimentId: string) => void
}


export default function ExperimentTask({
  variant,
  experiment,
  onClick,
  controlButtons,
  isFullWidth = false,
  onToggleFullWidth,
  onClose,
  isSelected = false,
  onDelete,
  onEdit,
  onDuplicate
}: ExperimentTaskProps) {
  const [loadedYaml, setLoadedYaml] = useState<string>('')
  const [isLoadingYaml, setIsLoadingYaml] = useState(false)

  // Load YAML for detail view
  useEffect(() => {
    if (variant === 'detail' && experiment.rootNodeId) {
      loadExperimentYaml()
    }
  }, [variant, experiment.rootNodeId])

  const loadExperimentYaml = async () => {
    if (!experiment.rootNodeId) return
    
    try {
      setIsLoadingYaml(true)
      // Get the latest version for the root node
      const { data: versions } = await (client.models.ExperimentNodeVersion.list as any)({
        filter: { nodeId: { eq: experiment.rootNodeId } },
        limit: 1
      })
      if (versions && versions.length > 0) {
        setLoadedYaml((versions[0] as any).code || EXPERIMENT_TEMPLATE)
      } else {
        setLoadedYaml(EXPERIMENT_TEMPLATE)
      }
    } catch (error) {
      console.warn('Failed to load YAML from experiment node:', error)
      setLoadedYaml(EXPERIMENT_TEMPLATE)
    } finally {
      setIsLoadingYaml(false)
    }
  }
  
  // Function to handle experiment deletion with confirmation
  const handleDelete = useCallback(async () => {
    if (!onDelete) return
    
    const confirmed = window.confirm('Are you sure you want to delete this experiment? This action cannot be undone.')
    if (confirmed) {
      try {
        onDelete(experiment.id)
      } catch (error) {
        console.error('Error deleting experiment:', error)
        toast.error('Failed to delete experiment')
      }
    }
  }, [onDelete, experiment.id])

  // Create action buttons dropdown for both grid and detail views
  const headerContent = (
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
        {onEdit && (
          <DropdownMenuItem onSelect={() => {
            onEdit(experiment.id);
          }}>
            <Edit className="mr-2 h-4 w-4" />
            Edit
          </DropdownMenuItem>
        )}
        {onDuplicate && (
          <DropdownMenuItem onSelect={() => {
            onDuplicate(experiment.id);
          }}>
            <Copy className="mr-2 h-4 w-4" />
            Duplicate
          </DropdownMenuItem>
        )}
        <DropdownMenuItem onSelect={() => {
          handleDelete();
        }}>
          <Trash2 className="mr-2 h-4 w-4" />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )

  // Transform experiment data to match Task component expectations
  const taskData = {
    id: experiment.id,
    type: 'Experiment',
    name: undefined, // Don't show a name - we'll display scorecard/score in content
    description: undefined,
    scorecard: experiment.scorecard?.name || '',
    score: experiment.score?.name || '',
    time: experiment.createdAt,
    command: undefined,
    output: undefined,
    data: experiment,
    status: 'PENDING' as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  }

  const renderHeader = (props: any) => {
    if (variant === 'detail') {
      // Custom header for detail view with status badge
      return (
        <div className="space-y-1.5 p-0 flex flex-col items-start w-full max-w-full px-1">
          <div className="flex justify-between items-start w-full max-w-full gap-3 overflow-hidden">
            <div className="flex flex-col pb-1 leading-none min-w-0 flex-1 overflow-hidden">
              <div className="flex items-center gap-2 mb-3">
                <Waypoints className="h-5 w-5 text-muted-foreground" />
                <span className="text-lg font-semibold text-muted-foreground">Experiment</span>
              </div>
              {props.task.scorecard && props.task.scorecard.trim() !== '' && (
                <div className="font-semibold text-sm truncate">{props.task.scorecard}</div>
              )}
              {props.task.score && props.task.score.trim() !== '' && (
                <div className="font-semibold text-sm truncate">{props.task.score}</div>
              )}
              <Timestamp time={props.task.time} variant="relative" />
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
          task={taskData}
          controlButtons={controlButtons}
          isFullWidth={isFullWidth}
          onToggleFullWidth={onToggleFullWidth}
          onClose={onClose}
        />
      )
    }
  }

  const renderContent = () => (
    <TaskContent variant={variant} task={taskData}>
      {variant === 'grid' ? (
        // Empty grid content since all info is now in header
        null
      ) : (
        <div className="p-3">
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
                      value={loadedYaml || EXPERIMENT_TEMPLATE}
                      onMount={(editor, monaco) => {
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
          
          {/* Experiment Nodes section */}
          <div className="mt-6">
            <ExperimentNodesList experimentId={experiment.id} />
          </div>
        </div>
      )}
    </TaskContent>
  )

  return (
    <Task
      variant={variant}
      task={taskData}
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