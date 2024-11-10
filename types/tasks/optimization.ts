import { BaseTaskData, BaseActivity } from '../base'

interface RingData {
  outerRing: Array<{ category: string; value: number; fill: string }>
  innerRing: Array<{ category: string; value: number; fill: string }>
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

export interface OptimizationActivity extends BaseActivity {
  type: 'Optimization started'
  data: OptimizationTaskData
} 