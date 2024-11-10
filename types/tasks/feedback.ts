import { BaseTaskData, BaseActivity } from '../base'

export interface FeedbackTaskData extends BaseTaskData {
  progress: number
  processedItems: number
  totalItems: number
  elapsedTime: string
  estimatedTimeRemaining: string
}

export interface FeedbackActivity extends BaseActivity {
  type: 'Feedback queue started' | 'Feedback queue completed'
  data: FeedbackTaskData
} 