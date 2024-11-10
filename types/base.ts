// Base types that are shared across all tasks
export interface BaseTaskData {
  progress?: number
  processedItems?: number
  totalItems?: number
  elapsedTime?: string
  estimatedTimeRemaining?: string
  status?: string
  errorMessage?: string
  errorDetails?: any
}

export interface BaseActivity {
  id: string
  type: ActivityType
  scorecard: string
  score: string
  time: string
  summary: string
  description?: string
}

export type ActivityType = 
  | 'Alert'
  | 'Score updated'
  | 'Feedback queue started'
  | 'Feedback queue completed'
  | 'Optimization started'
  | 'Experiment started'
  | 'Experiment completed'
  | 'Scoring Job'
  | 'Report'
  | 'Batch Job' 