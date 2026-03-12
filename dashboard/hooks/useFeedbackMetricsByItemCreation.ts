import { useMemo } from 'react'
import { useUnifiedMetrics, type MetricsConfig } from './useUnifiedMetrics'

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
 * 
 * Note: This now uses the standard feedback metrics from AggregatedMetrics table.
 * The Lambda aggregation service handles the filtering by item creation type.
 */
export function useFeedbackMetricsByItemCreation(config: FeedbackMetricsByItemCreationConfig) {
  // Memoize the metrics configuration
  const metricsConfig: MetricsConfig = useMemo(() => ({
    filters: {
      createdByType: config.createdByType,
      scoreResultType: 'feedback'
    }
  }), [config.createdByType])

  return useUnifiedMetrics(metricsConfig)
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