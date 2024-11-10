import { BaseTaskData, BaseActivity } from '../base'
import { RelatedBatchJob } from './batch-job'

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

export interface ScoringJobActivity extends BaseActivity {
  type: 'Scoring Job'
  data: ScoringJobTaskData
} 