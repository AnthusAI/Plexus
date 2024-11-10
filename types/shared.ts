export interface RingData {
  outerRing: Array<{ category: string; value: number; fill: string }>
  innerRing: Array<{ category: string; value: number; fill: string }>
}

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface TaskProgress {
  processedItems?: number
  totalItems?: number
  progress?: number
  startedAt?: string
  completedAt?: string
  elapsedTime?: string
  estimatedTimeRemaining?: string
} 