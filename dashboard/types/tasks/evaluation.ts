import { BaseTaskData } from '../base'
import { TaskStatus } from '../shared'
import { LazyLoader } from '@/utils/types'

export type TaskStage = {
  id: string
  name: string
  order: number
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  processedItems?: number
  totalItems?: number
  startedAt?: string
  completedAt?: string
  estimatedCompletionAt?: string
  statusMessage?: string
}

export interface ConfusionMatrix {
  matrix: number[][]
  labels: string[]
}

export interface EvaluationMetric {
  name: string
  value: number
  unit?: string
  maximum?: number
  priority: boolean
}

// Combined from both task types
export type EvaluationTaskData = BaseTaskData & {
  accuracy: number | null
  sensitivity?: number | null  // Optional fields from tasks.ts
  specificity?: number | null
  precision?: number | null
  metrics: EvaluationMetric[]
  processedItems: number
  totalItems: number
  progress: number
  inferences: number
  cost: number | null
  status: TaskStatus
  elapsedSeconds: number | null
  estimatedRemainingSeconds: number | null
  startedAt?: string
  errorMessage?: string
  errorDetails?: any
  confusionMatrix?: ConfusionMatrix
  task?: TaskData | null
}

export type TaskData = {
  id: string
  accountId: string
  command: string
  type: string
  status: string
  target: string
  description?: string
  metadata?: any
  createdAt?: string
  startedAt?: string
  completedAt?: string
  estimatedCompletionAt?: string
  errorMessage?: string
  errorDetails?: any
  stdout?: string
  stderr?: string
  currentStageId?: string
  stages?: {
    items: TaskStage[]
  }
  dispatchStatus?: 'DISPATCHED'
  celeryTaskId?: string
  workerNodeId?: string
  updatedAt?: string
  scorecardId?: string
  scoreId?: string
  scorecard?: LazyLoader<{
    id: string
    name: string
  }>
  score?: LazyLoader<{
    id: string
    name: string
  }>
  evaluation?: LazyLoader<{
    id: string
    type: string
    metrics: any
    metricsExplanation?: string
    inferences: number
    accuracy: number
    cost: number | null
    status: string
    startedAt?: string
    elapsedSeconds: number | null
    estimatedRemainingSeconds: number | null
    totalItems: number
    processedItems: number
    errorMessage?: string
    errorDetails?: any
    confusionMatrix?: any
    scoreGoal?: string
    datasetClassDistribution?: any
    isDatasetClassDistributionBalanced?: boolean
    predictedClassDistribution?: any
    isPredictedClassDistributionBalanced?: boolean
    scoreResults?: {
      items?: Array<{
        id: string
        value: string | number
        confidence: number | null
        metadata: any
        explanation: string | null
        itemId: string | null
        createdAt: string
        feedbackItem?: {
          id: string
          editCommentValue: string | null
          initialAnswerValue?: string | null
          finalAnswerValue?: string | null
          editorName?: string | null
          editedAt?: string | null
        } | null
      }>
    }
  }>
}

// Props type for components
export interface EvaluationTaskProps {
  variant?: 'grid' | 'detail'
  task: {
    id: string
    type: string
    scorecard: string
    score: string
    time: string
    data: EvaluationTaskData
  }
  onClick?: () => void
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  isSelected?: boolean
  extra?: boolean
} 