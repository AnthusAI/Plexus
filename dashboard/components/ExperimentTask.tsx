import React, { useCallback } from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { BaseTaskData } from '@/types/base'
import { Card, CardContent } from '@/components/ui/card'
import { Waypoints, MoreHorizontal, Square, X, Trash2, Columns2, Edit, Copy } from 'lucide-react'
import { Timestamp } from './ui/timestamp'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { toast } from 'sonner'

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
        <div className="p-3 space-y-3">
          <div className="flex items-center gap-2">
            <Waypoints className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Experiment</span>
          </div>
          
          <div className="space-y-1">
            {experiment.scorecard?.name ? (
              <div className="font-semibold text-sm truncate">{experiment.scorecard.name}</div>
            ) : (
              <div className="text-sm text-muted-foreground truncate">No scorecard selected</div>
            )}
            {experiment.score?.name ? (
              <div className="font-semibold text-sm truncate">{experiment.score.name}</div>
            ) : experiment.scorecard?.name ? (
              <div className="text-sm text-muted-foreground truncate">No score selected</div>
            ) : null}
            <Timestamp time={experiment.createdAt} variant="relative" />
          </div>
          
        </div>
      ) : (
        <div className="p-6">
          {/* Detail view content - simplified */}
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