import React, { useCallback, useState, useEffect } from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { BaseTaskData } from '@/types/base'
import { Card, CardContent } from '@/components/ui/card'
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
import ExperimentNodesList from "./experiment-nodes-list"
import ExperimentConversationViewer from "./experiment-conversation-viewer"

const client = generateClient<Schema>()

// Minimal fallback for YAML editor - actual templates come from experiment data
const MINIMAL_YAML_FALLBACK = `class: "BeamSearch"
# Loading experiment configuration...`

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
  onConversationFullscreenChange?: (isFullscreen: boolean) => void
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
  onDuplicate,
  onConversationFullscreenChange
}: ExperimentTaskProps) {
  const [loadedYaml, setLoadedYaml] = useState<string>('')
  const [isLoadingYaml, setIsLoadingYaml] = useState(false)
  const [sessionCount, setSessionCount] = useState<number>(0)
  const [isConversationFullscreen, setIsConversationFullscreen] = useState(false)

  // Notify parent of conversation fullscreen state changes
  useEffect(() => {
    if (onConversationFullscreenChange) {
      onConversationFullscreenChange(isConversationFullscreen)
    }
  }, [isConversationFullscreen, onConversationFullscreenChange])

  // Load YAML for detail view
  useEffect(() => {
    if (variant === 'detail') {
      loadExperimentYaml()
    }
  }, [variant, experiment.id])

  const loadExperimentYaml = async () => {
    try {
      setIsLoadingYaml(true)
      // Load the full experiment data to get the code field
      const { data: fullExperiment } = await (client.models.Experiment.get as any)({ 
        id: experiment.id 
      }, {
        selectionSet: ['code', 'template.template']
      })
      
      if (fullExperiment) {
        // Use experiment's code field first, fallback to template, then to default
        const yamlContent = fullExperiment.code || fullExperiment.template?.template || MINIMAL_YAML_FALLBACK
        setLoadedYaml(yamlContent)
      } else {
        setLoadedYaml(MINIMAL_YAML_FALLBACK)
      }
    } catch (error) {
      console.warn('Failed to load YAML from experiment:', error)
      setLoadedYaml(MINIMAL_YAML_FALLBACK)
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
          
          {/* Experiment Nodes section */}
          <div className="mt-6">
            <ExperimentNodesList experimentId={experiment.id} />
          </div>
          
          {/* Experiment Conversation section */}
          <div className="mt-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold flex items-center gap-2 text-muted-foreground">
                  <BookOpenCheck className="h-5 w-5" />
                  Procedures ({sessionCount})
                </h3>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                  onClick={() => {
                    setIsConversationFullscreen(true)
                  }}
                  aria-label="Fullscreen conversation"
                >
                  <Expand className="h-4 w-4" />
                </Button>
              </div>
              <div>
                <ExperimentConversationViewer 
                  experimentId={experiment.id} 
                  onSessionCountChange={setSessionCount}
                  isFullscreen={false}
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