import { dataClient } from '@/utils/data-operations'
import type { Schema } from "@/amplify/data/resource"

export type SubscriptionCallback<T> = (data: T) => void
export type ErrorCallback = (error: unknown) => void

export function createBatchJobScoringJobSubscription(
  onData: SubscriptionCallback<Schema['BatchJobScoringJob']['type']>,
  onError: ErrorCallback
) {
  // @ts-ignore - Amplify Gen2 typing issue
  return dataClient.models.BatchJobScoringJob.onCreate().subscribe({
    next: onData,
    error: onError
  })
}

export function createScoringJobSubscription(
  onData: SubscriptionCallback<Schema['ScoringJob']['type']>,
  onError: ErrorCallback
) {
  // @ts-ignore - Amplify Gen2 typing issue
  return dataClient.models.ScoringJob.onUpdate().subscribe({
    next: onData,
    error: onError
  })
} 