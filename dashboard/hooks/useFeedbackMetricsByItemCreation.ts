import { useMemo } from 'react'
import { useUnifiedMetrics } from './useUnifiedMetrics'
import type { MetricsDataSource } from '../utils/generalizedMetricsAggregator'

interface FeedbackMetricsByItemCreationConfig {
  accountId: string
  createdByType?: 'evaluation' | 'prediction' // Filter items by creation type
  scorecardId?: string
  scoreId?: string
}

/**
 * Hook to get feedback metrics for items created in specific time ranges.
 * This is different from regular feedback metrics which are based on when feedback was updated.
 * 
 * Use cases:
 * - "How much feedback did we get on items created from evaluations vs predictions?"
 * - "What's the feedback rate on items created in the last hour?"
 * - "Show feedback trends based on when the underlying items were created"
 */
export function useFeedbackMetricsByItemCreation(config: FeedbackMetricsByItemCreationConfig) {
  // Memoize the data source configuration to prevent infinite re-renders
  const dataSource: MetricsDataSource = useMemo(() => ({
    type: 'feedbackItemsByItemCreation',
    accountId: config.accountId,
    createdByType: config.createdByType,
    scorecardId: config.scorecardId,
    scoreId: config.scoreId,
    cacheKey: `feedback-by-item-creation-${config.accountId}-${config.createdByType || 'all'}-${config.scorecardId || 'all'}-${config.scoreId || 'all'}`,
    cacheTTL: 5 * 60 * 1000 // 5 minutes
  }), [config.accountId, config.createdByType, config.scorecardId, config.scoreId])

  return useUnifiedMetrics(dataSource)
}

// Convenience hooks for specific use cases
export function useEvaluationFeedbackMetrics(accountId: string, scorecardId?: string, scoreId?: string) {
  return useFeedbackMetricsByItemCreation({
    accountId,
    createdByType: 'evaluation',
    scorecardId,
    scoreId
  })
}

export function usePredictionFeedbackMetrics(accountId: string, scorecardId?: string, scoreId?: string) {
  return useFeedbackMetricsByItemCreation({
    accountId,
    createdByType: 'prediction',
    scorecardId,
    scoreId
  })
} 