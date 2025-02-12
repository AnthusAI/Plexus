import { BaseTaskData } from '../base'
import { TaskStatus } from '../shared'

export interface TaskStage {
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

export interface TaskData {
  id: string
  accountId: string
  type: string
  status: string
  target: string
  command: string
  description?: string
  dispatchStatus?: 'DISPATCHED'
  metadata?: any
  createdAt?: string
  startedAt?: string
  completedAt?: string
  estimatedCompletionAt?: string
  errorMessage?: string
  errorDetails?: string
  currentStageId?: string
  stages?: {
    items: TaskStage[]
    nextToken?: string | null
  }
}

// Props type for components
export interface EvaluationTaskProps {
  id: string
  type: string
  scorecard: string
  score: string
  time: string
  data: EvaluationTaskData
} 