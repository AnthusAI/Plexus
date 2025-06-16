import { useState, useEffect, useCallback } from 'react'
import { useAccount } from '@/app/contexts/AccountContext'
import { 
  generalizedMetricsAggregator, 
  MetricsDataSource, 
  MetricsResult 
} from '@/utils/generalizedMetricsAggregator'

// Unified metrics data structure
export interface UnifiedMetricsData {
  // Core metrics
  itemsPerHour: number
  itemsAveragePerHour: number
  itemsPeakHourly: number
  itemsTotal24h: number
  
  scoreResultsPerHour: number
  scoreResultsAveragePerHour: number
  scoreResultsPeakHourly: number
  scoreResultsTotal24h: number
  
  // Chart data
  chartData: Array<{
    time: string
    items: number
    scoreResults: number
    bucketStart?: string
    bucketEnd?: string
  }>
  
  // Metadata
  lastUpdated: Date
  hasErrorsLast24h: boolean
  totalErrors24h: number
}

// Configuration for different metric types
export interface MetricsConfig {
  // Data sources to fetch
  sources: {
    items?: MetricsDataSource
    scoreResults?: MetricsDataSource
    feedback?: MetricsDataSource
  }
  
  // Optional transformations
  transformations?: {
    // Custom peak calculation
    customPeakCalculation?: (chartData: any[]) => { itemsPeak: number; scoreResultsPeak: number }
    // Custom error detection
    customErrorDetection?: (data: any) => { hasErrors: boolean; errorCount: number }
  }
}

export interface UseUnifiedMetricsResult {
  metrics: UnifiedMetricsData | null
  isLoading: boolean
  error: string | null
  refetch: () => void
}

/**
 * Unified metrics hook that can handle different data sources and filtering
 * 
 * Examples:
 * - All items/scoreResults: useUnifiedMetrics({ sources: { items: {...}, scoreResults: {...} } })
 * - Prediction scoreResults only: useUnifiedMetrics({ sources: { scoreResults: { type: 'scoreResults', scoreResultType: 'prediction', ... } } })
 * - Feedback items: useUnifiedMetrics({ sources: { feedback: { type: 'feedbackItems', ... } } })
 */
export function useUnifiedMetrics(config: MetricsConfig): UseUnifiedMetricsResult {
  const [metrics, setMetrics] = useState<UnifiedMetricsData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { selectedAccount } = useAccount()

  const calculateUnifiedMetrics = useCallback(async (accountId: string): Promise<UnifiedMetricsData> => {
    const results: { [key: string]: MetricsResult } = {}
    
    // Prepare data sources with account ID
    const preparedSources: { [key: string]: MetricsDataSource } = {}
    
    Object.entries(config.sources).forEach(([key, source]) => {
      if (source) {
        preparedSources[key] = {
          ...source,
          accountId
        }
      }
    })

    // Fetch all metrics in parallel
    const fetchPromises = Object.entries(preparedSources).map(async ([key, source]) => {
      try {
        const result = await generalizedMetricsAggregator.getComprehensiveMetrics(source)
        return [key, result] as [string, MetricsResult]
      } catch (err) {
        console.error(`Error fetching ${key} metrics:`, err)
        throw err
      }
    })

    const fetchedResults = await Promise.all(fetchPromises)
    fetchedResults.forEach(([key, result]) => {
      results[key] = result
    })

    // Transform results into unified format
    const itemsResult = results.items
    const scoreResultsResult = results.scoreResults
    const feedbackResult = results.feedback

    // Calculate items metrics (from items source or fallback to scoreResults)
    const itemsMetrics = itemsResult || scoreResultsResult
    const itemsPerHour = itemsMetrics?.hourly.count || 0
    const itemsTotal24h = itemsMetrics?.total24h.count || 0
    const itemsAveragePerHour = itemsTotal24h > 0 ? Math.round(itemsTotal24h / 24) : 0

    // Calculate score results metrics
    const scoreResultsPerHour = scoreResultsResult?.hourly.count || 0
    const scoreResultsTotal24h = scoreResultsResult?.total24h.count || 0
    const scoreResultsAveragePerHour = scoreResultsTotal24h > 0 ? Math.round(scoreResultsTotal24h / 24) : 0

    // Generate combined chart data
    const chartData = generateCombinedChartData(results)

    // Calculate peak values from chart data
    const { itemsPeak, scoreResultsPeak } = config.transformations?.customPeakCalculation?.(chartData) || 
      calculatePeakValues(chartData)

    // Detect errors
    const { hasErrors, errorCount } = config.transformations?.customErrorDetection?.(results) || 
      { hasErrors: false, errorCount: 0 }

    return {
      itemsPerHour,
      itemsAveragePerHour,
      itemsPeakHourly: itemsPeak,
      itemsTotal24h,
      
      scoreResultsPerHour,
      scoreResultsAveragePerHour,
      scoreResultsPeakHourly: scoreResultsPeak,
      scoreResultsTotal24h,
      
      chartData,
      lastUpdated: new Date(),
      hasErrorsLast24h: hasErrors,
      totalErrors24h: errorCount
    }
  }, [config])

  const fetchMetrics = useCallback(async () => {
    if (!selectedAccount) {
      setMetrics(null)
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const result = await calculateUnifiedMetrics(selectedAccount.id)
      setMetrics(result)
    } catch (err) {
      console.error('❌ useUnifiedMetrics: Error calculating metrics:', err)
      setError(err instanceof Error ? err.message : 'Failed to calculate unified metrics')
    } finally {
      setIsLoading(false)
    }
  }, [selectedAccount, calculateUnifiedMetrics])

  const refetch = useCallback(() => {
    setMetrics(null)
    setIsLoading(true)
    fetchMetrics()
  }, [fetchMetrics])

  useEffect(() => {
    fetchMetrics()
  }, [fetchMetrics])

  return {
    metrics,
    isLoading,
    error,
    refetch
  }
}

/**
 * Generate combined chart data from multiple metric results
 */
function generateCombinedChartData(results: { [key: string]: MetricsResult }): Array<{
  time: string
  items: number
  scoreResults: number
  bucketStart?: string
  bucketEnd?: string
}> {
  const itemsResult = results.items
  const scoreResultsResult = results.scoreResults
  const feedbackResult = results.feedback

  // Use the longest chart data as the base
  const baseChartData = itemsResult?.chartData || scoreResultsResult?.chartData || []
  
  return baseChartData.map((point: any, index: number) => {
    // Get corresponding data points from other sources
    const scoreResultsPoint = scoreResultsResult?.chartData[index]
    const feedbackPoint = feedbackResult?.chartData[index]

    // If we don't have items data, use scoreResults data for items line too
    const itemsValue = itemsResult ? point.value : (scoreResultsPoint?.value || 0)

    return {
      time: point.time,
      items: itemsValue,
      scoreResults: scoreResultsPoint?.value || 0,
      feedback: feedbackPoint?.value || 0,
      bucketStart: point.bucketStart,
      bucketEnd: point.bucketEnd
    }
  })
}

/**
 * Calculate peak values from chart data
 */
function calculatePeakValues(chartData: Array<{ items: number; scoreResults: number }>): {
  itemsPeak: number
  scoreResultsPeak: number
} {
  if (!chartData || chartData.length === 0) {
    return { itemsPeak: 50, scoreResultsPeak: 300 }
  }

  const itemsPeak = Math.max(...chartData.map(point => point.items), 50)
  const scoreResultsPeak = Math.max(...chartData.map(point => point.scoreResults), 300)

  return { itemsPeak, scoreResultsPeak }
}

// Convenience hooks for common use cases

/**
 * Hook for all items and score results (no filtering) - backward compatible
 */
export function useAllItemsMetrics(): UseUnifiedMetricsResult {
  return useUnifiedMetrics({
    sources: {
      items: {
        type: 'items',
        accountId: '', // Will be filled by the hook
      },
      scoreResults: {
        type: 'scoreResults',
        accountId: '', // Will be filled by the hook
      }
    }
  })
}

/**
 * Hook for prediction items and score results
 */
export function usePredictionMetrics(): UseUnifiedMetricsResult {
  return useUnifiedMetrics({
    sources: {
      items: {
        type: 'items',
        createdByType: 'prediction',
        accountId: '', // Will be filled by the hook
      },
      scoreResults: {
        type: 'scoreResults',
        scoreResultType: 'prediction',
        accountId: '', // Will be filled by the hook
      }
    }
  })
}

/**
 * Hook for evaluation items and score results
 */
export function useEvaluationMetrics(): UseUnifiedMetricsResult {
  return useUnifiedMetrics({
    sources: {
      items: {
        type: 'items',
        createdByType: 'evaluation',
        accountId: '', // Will be filled by the hook
      },
      scoreResults: {
        type: 'scoreResults',
        scoreResultType: 'evaluation',
        accountId: '', // Will be filled by the hook
      }
    }
  })
}

/**
 * Hook for feedback items
 */
export function useFeedbackMetrics(): UseUnifiedMetricsResult {
  return useUnifiedMetrics({
    sources: {
      feedback: {
        type: 'feedbackItems',
        accountId: '', // Will be filled by the hook
      }
    }
  })
} 