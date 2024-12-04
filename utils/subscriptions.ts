import { dataClient } from '@/utils/data-operations'
import type { Schema } from "@/amplify/data/resource"

export type SubscriptionCallback<T> = (data: T) => void
export type ErrorCallback = (error: unknown) => void

export interface BatchJobScoringJobSubscriptionData {
  batchJobId: string
  scoringJobId: string 
}

export interface ScoringJobSubscriptionData {
  id: string
  status: string
  startedAt?: string | null
  completedAt?: string | null
  errorMessage?: string | null
  itemId: string
  accountId: string
  scorecardId: string
  evaluationId?: string | null
  scoreId?: string | null
}

export function createBatchJobScoringJobSubscription(
  onData: SubscriptionCallback<BatchJobScoringJobSubscriptionData>,
  onError: ErrorCallback
) {
  // @ts-ignore - Amplify Gen2 typing issue
  return dataClient.models.BatchJobScoringJob.onCreate().subscribe({
    next: onData,
    error: onError
  })
}

export function createScoringJobSubscription(
  onData: SubscriptionCallback<ScoringJobSubscriptionData>,
  onError: ErrorCallback
) {
  // @ts-ignore - Amplify Gen2 typing issue
  return dataClient.models.ScoringJob.onUpdate().subscribe({
    next: onData,
    error: onError
  })
} 