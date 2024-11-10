import { BaseTaskData, BaseActivity } from '../base'

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

export interface BatchJobActivity extends BaseActivity {
  type: 'Batch Job'
  data: BatchJobTaskData
}

export interface RelatedBatchJob {
  id: string
  provider: string
  type: string
  status: string
  totalRequests: number
  completedRequests: number
  failedRequests: number
  errorMessage?: string
} 