import { BaseTaskData, BaseActivity, ActivityType } from './base'
import { RingData, TaskStatus } from './shared'
import type { Schema } from "@/amplify/data/resource"
import type { LazyLoader } from "@/types/lazy-loader"

// Task Data Types
export type AlertTaskData = BaseTaskData & {
  iconType: 'warning' | 'info' | 'siren'
}

export type BatchJobTaskData = BaseTaskData & {
  modelProvider: string
  modelName: string
  type: string
  status: string
  totalRequests: number
  completedRequests: number
  failedRequests: number
  startedAt?: string
  estimatedEndAt?: string
  completedAt?: string
  errorMessage?: string
  errorDetails?: any
  scoringJobs?: {
    id: string
    status: string
    startedAt?: string | null
    completedAt?: string | null
    errorMessage?: string | null
    scoringJobId: string
    batchJobId: string
  }[]
}

export type EvaluationTaskData = BaseTaskData & {
  accuracy: number | null
  sensitivity: number | null
  specificity: number | null
  precision: number | null
  processedItems: number
  totalItems: number
  progress: number
  inferences: number
  cost: number | null
  status: TaskStatus
  elapsedSeconds: number | null
  estimatedRemainingSeconds: number | null
  startedAt?: string | null
  errorMessage?: string | null
  errorDetails?: any
  confusionMatrix?: {
    matrix: number[][]
    labels: string[]
  }
  scoreGoal?: string | null
  datasetClassDistribution?: { label: string, count: number }[]
  isDatasetClassDistributionBalanced?: boolean | null
  predictedClassDistribution?: { label: string, count: number }[]
  isPredictedClassDistributionBalanced?: boolean | null
  metricsExplanation?: string | null
  metrics?: {
    name: string
    value: number
    unit?: string
    maximum?: number
    priority: boolean
  }[]
  scoreResults?: {
    value: string
    itemId: string
    metadata: any
    confidence: number | null
    explanation: string | null
    createdAt: string
    updatedAt: string
    id: string
  }[]
  selectedScoreResult?: {
    value: string
    itemId: string
    metadata: any
    confidence: number | null
    explanation: string | null
    createdAt: string
    updatedAt: string
    id: string
  } | null
}

export type FeedbackTaskData = BaseTaskData & {
  progress: number
  processedItems: number
  totalItems: number
  elapsedSeconds: number | null
  estimatedRemainingSeconds: number | null
}

export type OptimizationTaskData = BaseTaskData & {
  id: string
  title: string
  progress: number
  accuracy: number
  numberComplete: number
  numberTotal: number
  eta: string
  processedItems: number
  totalItems: number
  before: RingData
  after: RingData
  elapsedTime: string
  estimatedTimeRemaining: string
  elapsedSeconds: number | null
  estimatedRemainingSeconds: number | null
}

export type ReportTaskData = BaseTaskData & {
  command: string
}

export type ScoreUpdatedTaskData = BaseTaskData & {
  before: RingData
  after: RingData
}

export type ScoringJobTaskData = BaseTaskData & {
  status: string
  startedAt?: string
  completedAt?: string
  itemName?: string
  scorecardName?: string
  totalItems: number
  completedItems: number
  batchJobs?: BatchJobTaskData[]
}

// Activity Types
export type AlertActivity = BaseActivity & {
  type: 'Alert'
  data: AlertTaskData
}

export type BatchJobActivity = BaseActivity & {
  type: 'Batch Job'
  data: BatchJobTaskData
}

export type EvaluationActivity = BaseActivity & {
  type: 'Evaluation completed' | 'Evaluation started'
  data: {
    id: string
    title: string
    accuracy: number | null
    metrics: {
      name: string
      value: number
      unit?: string
      maximum?: number
      priority: boolean
    }[]
    processedItems: number
    totalItems: number
    elapsedSeconds: number | null
    estimatedRemainingSeconds: number | null
    confusionMatrix?: {
      matrix: number[][]
      labels: string[]
    }
    progress: number
    inferences: number
    cost: number | null
    status: TaskStatus
  }
}

export type FeedbackActivity = BaseActivity & {
  type: 'Feedback queue started' | 'Feedback queue completed'
  data: FeedbackTaskData
}

export type OptimizationActivity = BaseActivity & {
  type: 'Optimization started'
  data: OptimizationTaskData
}

export type ReportActivity = BaseActivity & {
  type: 'Report'
  data: ReportTaskData
}

export type ScoreUpdatedActivity = BaseActivity & {
  type: 'Score updated'
  data: ScoreUpdatedTaskData
}

export type ScoringJobActivity = BaseActivity & {
  type: 'Scoring Job'
  data: ScoringJobTaskData
}

export type ActivityData =
  | AlertActivity
  | BatchJobActivity
  | EvaluationActivity
  | FeedbackActivity
  | OptimizationActivity
  | ReportActivity
  | ScoreUpdatedActivity
  | ScoringJobActivity

export const isEvaluationActivity = (
  activity: ActivityData
): activity is EvaluationActivity => {
  return (
    activity.type === 'Evaluation started' ||
    activity.type === 'Evaluation completed'
  )
}

// Add this to the exports
export type RelatedBatchJob = {
  id: string
  type: string
  status: string
  modelProvider: string
  modelName: string
  totalRequests: number
  completedRequests: number
  failedRequests: number
  startedAt?: string
  estimatedEndAt?: string
  completedAt?: string
  errorMessage?: string
  errorDetails?: any
  scoringJobs?: {
    id: string
    status: string
    startedAt?: string | null
    completedAt?: string | null
    errorMessage?: string | null
    scoringJobId: string
    batchJobId: string
  }[]
}

// Add this to the existing types in tasks.ts
export interface FeedbackItem {
  id: number
  scorecard: string
  score: number
  date: string
  status: string
  results: number
  inferences: number
  cost: string
  sampleMetadata: Array<{ key: string; value: string }>
  sampleTranscript: Array<{ speaker: string; text: string }>
  sampleScoreResults: Array<{
    section: string
    scores: Array<{
      name: string
      value: string
      explanation: string
      isAnnotated: boolean
      allowFeedback: boolean
      annotations: Array<{
        value: string
        explanation: string
        annotation?: string
        timestamp: string
        user?: {
          name: string
          initials: string
        }
        isSystem?: boolean
        isThumbsUp?: boolean
      }>
    }>
  }>
}