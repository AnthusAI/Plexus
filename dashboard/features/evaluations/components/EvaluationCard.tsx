import React from 'react'
import { Schema } from '@/amplify/data/resource'
import { Button } from '@/components/ui/button'
import { MoreHorizontal, Trash2 } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import EvaluationTask from '@/components/EvaluationTask'
import { calculateProgress } from '../utils/format'
import type { TaskData, TaskStage } from '@/types/tasks/evaluation'
import type { EvaluationTaskData } from '@/components/EvaluationTask'
import type { ProcessedEvaluation } from '@/utils/data-operations'
import { TaskStatus } from '@/types/shared'

interface EvaluationCardProps {
  evaluation: ProcessedEvaluation
  selectedEvaluationId: string | undefined | null
  scorecardNames: Record<string, string>
  scoreNames: Record<string, string>
  onSelect: (evaluation: ProcessedEvaluation) => void
  onDelete: (evaluationId: string) => Promise<boolean>
  evaluationRefsMap?: React.MutableRefObject<Map<string, HTMLDivElement | null>>
}

interface RawTaskStage {
  id?: string
  name?: string
  order?: number
  status?: string
  statusMessage?: string | null
  startedAt?: string | null
  completedAt?: string | null
  estimatedCompletionAt?: string | null
  processedItems?: number
  totalItems?: number
}

interface RawTask {
  id?: string
  accountId?: string
  type?: string
  status?: string
  target?: string
  command?: string
  description?: string | null
  dispatchStatus?: string
  metadata?: unknown
  createdAt?: string
  startedAt?: string | null
  completedAt?: string | null
  estimatedCompletionAt?: string | null
  errorMessage?: string | null
  errorDetails?: string | null
  currentStageId?: string
  stages?: {
    items?: RawTaskStage[]
    nextToken?: string | null
  }
}

const isValidStatus = (status: string | undefined): status is 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' => {
  return status === 'PENDING' || status === 'RUNNING' || status === 'COMPLETED' || status === 'FAILED';
};

export const EvaluationCard = React.memo(({ 
  evaluation, 
  selectedEvaluationId, 
  scorecardNames, 
  scoreNames,
  onSelect,
  onDelete,
  evaluationRefsMap
}: EvaluationCardProps) => {
  const [taskData, setTaskData] = React.useState<TaskData | null>(null)

  // Transform evaluation data into EvaluationTask format
  const evaluationTaskData: EvaluationTaskData = {
    id: evaluation.id,
    title: scorecardNames[evaluation.id] || 'Unknown Scorecard',
    accuracy: evaluation.accuracy ?? null,
    metrics: [], // Add metrics if available
    processedItems: Number(evaluation.processedItems || 0),
    totalItems: Number(evaluation.totalItems || 0),
    progress: calculateProgress(evaluation.processedItems, evaluation.totalItems),
    inferences: evaluation.inferences || 0,
    cost: evaluation.cost || null,
    status: (evaluation.status?.toLowerCase() || 'pending') as TaskStatus,
    elapsedSeconds: evaluation.elapsedSeconds || null,
    estimatedRemainingSeconds: evaluation.estimatedRemainingSeconds || null,
    startedAt: evaluation.startedAt || undefined,
    errorMessage: evaluation.errorMessage || undefined,
    errorDetails: evaluation.errorDetails || null,
    scoreResults: evaluation.scoreResults as any, // Pass the transformed score results with itemIdentifiers
    task: taskData
  }

  React.useEffect(() => {
    const fetchTaskData = async () => {
      if (typeof evaluation.task === 'function') {
        try {
          const result = await (evaluation.task as any)()
          if (result.data) {
            const rawTask = result.data as RawTask
            // Transform to match TaskData interface
            const transformedTask: TaskData = {
              id: rawTask.id || '',
              accountId: rawTask.accountId || '',
              type: rawTask.type || '',
              status: rawTask.status || '',
              target: rawTask.target || '',
              command: rawTask.command || '',
              description: rawTask.description === null ? undefined : rawTask.description,
              dispatchStatus: rawTask.dispatchStatus as 'DISPATCHED' | undefined,
              metadata: rawTask.metadata,
              createdAt: rawTask.createdAt,
              startedAt: rawTask.startedAt === null ? undefined : rawTask.startedAt,
              completedAt: rawTask.completedAt === null ? undefined : rawTask.completedAt,
              estimatedCompletionAt: rawTask.estimatedCompletionAt === null ? undefined : rawTask.estimatedCompletionAt,
              errorMessage: rawTask.errorMessage === null ? undefined : rawTask.errorMessage,
              errorDetails: rawTask.errorDetails === null ? undefined : rawTask.errorDetails,
              currentStageId: rawTask.currentStageId,
              stages: rawTask.stages ? {
                items: (rawTask.stages.items || []).map((stage: RawTaskStage): TaskStage => ({
                  id: stage.id || '',
                  name: stage.name || '',
                  order: stage.order || 0,
                  status: isValidStatus(stage.status) ? stage.status : 'PENDING',
                  statusMessage: stage.statusMessage === null ? undefined : stage.statusMessage,
                  startedAt: stage.startedAt === null ? undefined : stage.startedAt,
                  completedAt: stage.completedAt === null ? undefined : stage.completedAt,
                  estimatedCompletionAt: stage.estimatedCompletionAt === null ? undefined : stage.estimatedCompletionAt,
                  processedItems: stage.processedItems,
                  totalItems: stage.totalItems
                }))
              } : undefined
            }
            setTaskData(transformedTask)
          }
        } catch (error) {
          console.error('Error fetching task data:', error)
        }
      }
    }

    fetchTaskData()
  }, [evaluation.task])

  // Ref callback to store ref in the evaluationRefsMap
  const refCallback = React.useCallback((el: HTMLDivElement | null) => {
    if (evaluationRefsMap) {
      evaluationRefsMap.current.set(evaluation.id, el);
    }
  }, [evaluation.id, evaluationRefsMap]);

  return (
    <div ref={refCallback}>
      <EvaluationTask
        variant="grid"
        task={{
          id: evaluation.id,
          type: evaluation.type,
          scorecard: scorecardNames[evaluation.id] || 'Unknown Scorecard',
          score: scoreNames[evaluation.id] || 'Unknown Score',
          time: evaluation.createdAt,
          data: evaluationTaskData
        }}
        onClick={() => onSelect(evaluation)}
        isSelected={evaluation.id === selectedEvaluationId}
        controlButtons={
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-8 w-8 p-0">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={async (e) => {
                e.stopPropagation()
                if (window.confirm('Are you sure you want to delete this evaluation?')) {
                  await onDelete(evaluation.id)
                }
              }}>
                <Trash2 className="h-4 w-4 mr-2" /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        }
        extra={true}
      />
    </div>
  )
}) 