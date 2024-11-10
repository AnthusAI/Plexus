// Base types that are shared across all tasks
export interface BaseTaskData {
  id: string
  title: string
  description?: string
  errorMessage?: string
}

export type ActivityType = 
  | 'Alert'
  | 'Batch Job'
  | 'Experiment started' 
  | 'Experiment completed'
  | 'Feedback queue started'
  | 'Feedback queue completed'
  | 'Optimization started'
  | 'Report'
  | 'Score updated'
  | 'Scoring Job'

export interface BaseActivity {
  id: string
  timestamp: string
  type: ActivityType
  data: BaseTaskData
  scorecard: string
  score: string
  time: string
  summary: string
  description?: string
}