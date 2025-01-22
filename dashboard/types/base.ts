import { TaskStageConfig } from '@/components/ui/task-status'

// Base types that are shared across all tasks
export interface BaseTaskData {
  id: string
  title: string
  description?: string
  errorMessage?: string
  command?: string
}

export type ActivityType = 
  | 'Alert'
  | 'Batch Job'
  | 'Evaluation started' 
  | 'Evaluation completed'
  | 'Feedback queue started'
  | 'Feedback queue completed'
  | 'Optimization started'
  | 'Report'
  | 'Score updated'
  | 'Scoring Job'

// Base activity type with stage support
export type BaseActivity = {
  id: string
  timestamp: string
  type: ActivityType
  scorecard: string
  score: string
  time: string
  summary?: string
  description?: string
  stages?: TaskStageConfig[]
  currentStageName?: string
  processedItems?: number
  totalItems?: number
  startedAt?: string
  estimatedCompletionAt?: string
  completedAt?: string
  status?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  stageConfigs?: TaskStageConfig[]
  data?: BaseTaskData
}