import { BaseTaskData, BaseActivity, ActivityType } from './base'
import { RingData, TaskStatus } from './shared'

// Task Data Types
export type AlertTaskData = BaseTaskData & {
  iconType: 'warning' | 'info' | 'siren'
}

export type BatchJobTaskData = BaseTaskData & {
  provider: string
  type: string
  status: string
  totalRequests: number
  completedRequests: number
  failedRequests: number
  startedAt?: string
  completedAt?: string
  errorMessage?: string
  batchJobs?: BatchJobTaskData[]
}

export type ExperimentTaskData = BaseTaskData & {
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
  elapsedTime: string
  estimatedTimeRemaining: string
  startedAt?: string
  estimatedEndAt?: string
  errorMessage?: string
  errorDetails?: any
  confusionMatrix?: {
    matrix: number[][]
    labels: string[]
  }
}

export type FeedbackTaskData = BaseTaskData & {
  progress: number
  processedItems: number
  totalItems: number
  elapsedTime: string
  estimatedTimeRemaining: string
}

export type OptimizationTaskData = BaseTaskData & {
  progress: number
  accuracy: number
  numberComplete: number
  numberTotal: number
  eta: string
  elapsedTime: string
  estimatedTimeRemaining: string
  processedItems: number
  totalItems: number
  before: RingData
  after: RingData
}

export type ReportTaskData = BaseTaskData & {
  // Report-specific fields can be added here
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

export type ExperimentActivity = BaseActivity & {
  type: 'Experiment started' | 'Experiment completed'
  data: ExperimentTaskData
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
  | ExperimentActivity
  | FeedbackActivity
  | OptimizationActivity
  | ReportActivity
  | ScoreUpdatedActivity
  | ScoringJobActivity

export const isExperimentActivity = (
  activity: ActivityData
): activity is ExperimentActivity => {
  return (
    activity.type === 'Experiment started' ||
    activity.type === 'Experiment completed'
  )
}

// Add this to the exports
export type RelatedBatchJob = BaseTaskData & {
  provider: string
  type: string
  status: string
  totalRequests: number
  completedRequests: number
  failedRequests: number
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