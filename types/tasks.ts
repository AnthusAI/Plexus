import { BaseTaskData, BaseActivity, ActivityType } from './base'
import { RingData, TaskStatus, TaskProgress } from './shared'

// Task Data Types
export interface AlertTaskData extends BaseTaskData {
  iconType: 'warning' | 'info' | 'siren'
}

export interface RelatedBatchJob extends BaseTaskData {
  provider: string
  type: string
  status: string
  totalRequests: number
  completedRequests: number
  failedRequests: number
}

export interface BatchJobTaskData extends BaseTaskData {
  provider: string
  type: string
  status: string
  totalRequests: number
  completedRequests: number
  failedRequests: number
  startedAt?: string
  completedAt?: string
  errorMessage?: string
  batchJobs?: RelatedBatchJob[]
}

export interface ExperimentTaskData extends BaseTaskData {
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

export interface FeedbackTaskData extends BaseTaskData {
  progress: number
  processedItems: number
  totalItems: number
  elapsedTime: string
  estimatedTimeRemaining: string
}

export interface OptimizationTaskData extends BaseTaskData {
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

export interface ReportTaskData extends BaseTaskData {
  // Report-specific fields can be added here
}

export interface ScoreUpdatedTaskData extends BaseTaskData {
  before: RingData
  after: RingData
}

export interface ScoringJobTaskData extends BaseTaskData {
  status: string
  startedAt?: string
  completedAt?: string
  itemName?: string
  scorecardName?: string
  totalItems: number
  completedItems: number
  batchJobs?: RelatedBatchJob[]
}

// Activity Types - each includes the common fields from BaseActivity
export interface AlertActivity extends BaseActivity {
  type: Extract<ActivityType, 'Alert'>
  data: AlertTaskData
}

export interface BatchJobActivity extends BaseActivity {
  type: Extract<ActivityType, 'Batch Job'>
  data: BatchJobTaskData
}

export interface ExperimentActivity extends BaseActivity {
  type: Extract<ActivityType, 'Experiment started' | 'Experiment completed'>
  data: ExperimentTaskData
}

export interface FeedbackActivity extends BaseActivity {
  type: Extract<ActivityType, 'Feedback queue started' | 'Feedback queue completed'>
  data: FeedbackTaskData
}

export interface OptimizationActivity extends BaseActivity {
  type: Extract<ActivityType, 'Optimization started'>
  data: OptimizationTaskData
}

export interface ReportActivity extends BaseActivity {
  type: Extract<ActivityType, 'Report'>
  data: ReportTaskData
}

export interface ScoreUpdatedActivity extends BaseActivity {
  type: Extract<ActivityType, 'Score updated'>
  data: ScoreUpdatedTaskData
}

export interface ScoringJobActivity extends BaseActivity {
  type: Extract<ActivityType, 'Scoring Job'>
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