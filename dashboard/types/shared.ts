import type { Schema } from "@/amplify/data/resource"

export type ModelListResult<T> = Promise<{
  data: T[]
  nextToken: string | null
}>

// Helper type for Amplify Gen2 list responses
export type AmplifyListResult<T> = {
  data: T[]
  nextToken: string | null
}

// Helper type for Amplify Gen2 get responses
export type AmplifyGetResult<T> = {
  data: T | null
}

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