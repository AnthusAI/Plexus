import { BaseTaskData, BaseActivity } from '../base'

export interface ExperimentTaskData extends Omit<BaseTaskData, 'errorMessage'> {
  accuracy: number | null
  sensitivity: number | null
  specificity: number | null
  precision: number | null
  processedItems: number
  totalItems: number
  progress: number
  inferences: number
  cost: number | null
  status: string
  elapsedTime: string
  estimatedTimeRemaining: string
  startedAt?: string | null
  estimatedEndAt?: string | null
  errorMessage?: string | null
  errorDetails?: any | null
  confusionMatrix?: {
    matrix: number[][]
    labels: string[]
  }
}

export interface ExperimentActivity extends BaseActivity {
  type: 'Experiment started' | 'Experiment completed'
  data: ExperimentTaskData
} 