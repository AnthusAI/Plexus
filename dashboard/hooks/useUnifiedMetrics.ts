import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useAccount } from '@/app/contexts/AccountContext'
import { 
  generalizedMetricsAggregator, 
  MetricsDataSource, 
  MetricsResult 
} from '@/utils/generalizedMetricsAggregator'

// Global state to persist metrics across component mount/unmount cycles
const globalMetricsState = new Map<string, {
  metrics: UnifiedMetricsData | null
  isLoading: boolean
  error: string | null
  lastFetch: number
}>()

// Global refresh timers to prevent multiple timers for the same config
const globalRefreshTimers = new Map<string, NodeJS.Timeout>()

// Helper to generate a unique key for the metrics config
function getConfigKey(accountId: string, config: MetricsConfig): string {
  // Include filtering parameters in the key to ensure different filters get different cache entries
  const sourceDescriptors = Object.entries(config.sources)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, source]) => {
      if (!source) return key
      
      const filters = []
      if (source.createdByType) filters.push(`createdByType:${source.createdByType}`)
      if (source.scoreResultType) filters.push(`scoreResultType:${source.scoreResultType}`)
      
      return filters.length > 0 ? `${key}(${filters.join(',')})` : key
    })
    .join(',')
  
  return `${accountId}:${sourceDescriptors}`
}

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
// Synchronous cache check function (defined outside the hook to avoid initialization issues)
const checkCachedDataSync = (accountId: string, config: MetricsConfig): UnifiedMetricsData | null => {
  try {    
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

    // Check if we have cached data for all required sources
    const cachedResults: { [key: string]: any } = {}
    let hasAllCachedData = true

    for (const [key, source] of Object.entries(preparedSources)) {
      // Create sources for different time ranges (same logic as calculateUnifiedMetrics)
      const now = new Date()
      const nowAligned = new Date(now)
      nowAligned.setSeconds(0, 0)
      const currentHourMinutes = nowAligned.getMinutes()
      const windowMinutes = 60 + currentHourMinutes
      const lastHour = new Date(nowAligned.getTime() - windowMinutes * 60 * 1000)

      const hourlySource: MetricsDataSource = {
        ...source,
        startTime: lastHour,
        endTime: now
      }

      const total24hSource: MetricsDataSource = {
        ...source,
        startTime: new Date(now.getTime() - 24 * 60 * 60 * 1000),
        endTime: now
      }

      // Check cache for both time ranges
      const hourlyCacheKey = generalizedMetricsAggregator.cache.generateKey(hourlySource)
      const total24hCacheKey = generalizedMetricsAggregator.cache.generateKey(total24hSource)
      
      const hourlyCached = generalizedMetricsAggregator.cache.get(hourlyCacheKey)
      const total24hCached = generalizedMetricsAggregator.cache.get(total24hCacheKey)

      if (hourlyCached && total24hCached) {
        // Normalize hourly metrics (same logic as getComprehensiveMetrics)
        const actualWindowMinutes = (now.getTime() - lastHour.getTime()) / (60 * 1000)
        const normalizationFactor = actualWindowMinutes > 0 ? 60 / actualWindowMinutes : 1

        const normalizedHourlyData = {
          ...hourlyCached,
          count: Math.round(hourlyCached.count * normalizationFactor),
          sum: hourlyCached.sum * normalizationFactor,
          avg: hourlyCached.avg
        }

        // Generate chart data from cached 24h data
        const chartData = generalizedMetricsAggregator.generateChartDataFromRecords(total24hCached.items, source)

        cachedResults[key] = {
          hourly: normalizedHourlyData,
          total24h: total24hCached,
          chartData,
          lastUpdated: now
        }
      } else {
        hasAllCachedData = false
        break
      }
    }

    if (!hasAllCachedData) {
      return null
    }

    // Transform cached results into unified format (same logic as calculateUnifiedMetrics)
    const itemsResult = cachedResults.items
    const scoreResultsResult = cachedResults.scoreResults
    const feedbackResult = cachedResults.feedback

    const itemsMetrics = itemsResult || scoreResultsResult || feedbackResult
    const itemsPerHour = itemsMetrics?.hourly.count || 0
    const itemsTotal24h = itemsMetrics?.total24h.count || 0
    const itemsAveragePerHour = itemsTotal24h > 0 ? Math.round(itemsTotal24h / 24) : 0

    const scoreResultsMetrics = scoreResultsResult || feedbackResult
    const scoreResultsPerHour = scoreResultsMetrics?.hourly.count || 0
    const scoreResultsTotal24h = scoreResultsMetrics?.total24h.count || 0
    const scoreResultsAveragePerHour = scoreResultsTotal24h > 0 ? Math.round(scoreResultsTotal24h / 24) : 0

    const chartData = generateCombinedChartData(cachedResults)
    const { itemsPeak, scoreResultsPeak } = config.transformations?.customPeakCalculation?.(chartData) || 
      calculatePeakValues(chartData)
    const { hasErrors, errorCount } = config.transformations?.customErrorDetection?.(cachedResults) || 
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
  } catch (error) {
    console.warn('Error checking cached data synchronously:', error)
    return null
  }
}

export function useUnifiedMetrics(config: MetricsConfig): UseUnifiedMetricsResult {
  const { selectedAccount } = useAccount()
  
  // Generate unique key for this config
  const configKey = useMemo(() => {
    if (!selectedAccount) return null
    const key = getConfigKey(selectedAccount.id, config)
    return key
  }, [selectedAccount?.id, config])
  
  // Get or initialize global state for this config
  const getGlobalState = useCallback(() => {
    if (!configKey) return { metrics: null, isLoading: false, error: null, lastFetch: 0 }
    
    if (!globalMetricsState.has(configKey)) {
      // Try to get cached data first
      const cachedData = selectedAccount ? checkCachedDataSync(selectedAccount.id, config) : null
      globalMetricsState.set(configKey, {
        metrics: cachedData,
        isLoading: !cachedData,
        error: null,
        lastFetch: cachedData ? Date.now() : 0
      })
      
    }
    
    return globalMetricsState.get(configKey)!
  }, [configKey, selectedAccount, config])
  
  // Initialize local state from global state
  const globalState = getGlobalState()
  const [metrics, setMetrics] = useState<UnifiedMetricsData | null>(globalState.metrics)
  const [isLoading, setIsLoading] = useState(globalState.isLoading)
  const [error, setError] = useState<string | null>(globalState.error)
  
  // Update global state when local state changes
  const updateGlobalState = useCallback((updates: Partial<typeof globalState>) => {
    if (!configKey) return
    
    const current = globalMetricsState.get(configKey)!
    const newState = { ...current, ...updates }
    globalMetricsState.set(configKey, newState)
    
    // Update local state
    if (updates.metrics !== undefined) setMetrics(updates.metrics)
    if (updates.isLoading !== undefined) setIsLoading(updates.isLoading)
    if (updates.error !== undefined) setError(updates.error)
  }, [configKey])

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

    // Calculate items metrics (from items source or fallback to scoreResults or feedback)
    const itemsMetrics = itemsResult || scoreResultsResult || feedbackResult
    const itemsPerHour = itemsMetrics?.hourly.count || 0
    const itemsTotal24h = itemsMetrics?.total24h.count || 0
    const itemsAveragePerHour = itemsTotal24h > 0 ? Math.round(itemsTotal24h / 24) : 0

    // Calculate score results metrics (from scoreResults or fallback to feedback for feedback-only hooks)
    const scoreResultsMetrics = scoreResultsResult || feedbackResult
    const scoreResultsPerHour = scoreResultsMetrics?.hourly.count || 0
    const scoreResultsTotal24h = scoreResultsMetrics?.total24h.count || 0
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
    if (!selectedAccount || !configKey) {
      updateGlobalState({ metrics: null, isLoading: false, error: null })
      return
    }

    // Check for cached data first and show it immediately
    const cachedData = checkCachedDataSync(selectedAccount.id, config)
    if (cachedData) {
      updateGlobalState({ metrics: cachedData, isLoading: false, error: null, lastFetch: Date.now() })
      return
    }

    updateGlobalState({ isLoading: true, error: null })

    try {
      const result = await calculateUnifiedMetrics(selectedAccount.id)
      updateGlobalState({ metrics: result, isLoading: false, error: null, lastFetch: Date.now() })
    } catch (err) {
      updateGlobalState({ 
        error: err instanceof Error ? err.message : 'Failed to calculate unified metrics',
        isLoading: false 
      })
    }
  }, [selectedAccount, calculateUnifiedMetrics, config, configKey, updateGlobalState])

  // Background fetch that never shows loading states - just smoothly updates data
  const fetchMetricsInBackground = useCallback(async () => {
    if (!selectedAccount || !configKey) {
      return
    }

    try {
      const result = await calculateUnifiedMetrics(selectedAccount.id)
      // Update metrics without changing loading state - smooth update
      updateGlobalState({ metrics: result, error: null, lastFetch: Date.now() })
    } catch (err) {
      console.error('❌ useUnifiedMetrics: Error in background fetch:', err)
      // Don't update error state for background fetches - keep showing last known data
      console.log('🔄 useUnifiedMetrics: Background fetch failed, keeping last known data')
    }
  }, [selectedAccount, calculateUnifiedMetrics, configKey, updateGlobalState])

  const refetch = useCallback(() => {
    if (!selectedAccount || !configKey) {
      updateGlobalState({ metrics: null, isLoading: false, error: null })
      return
    }

    // Check if we have existing data (global state or cache)
    const currentGlobalState = globalMetricsState.get(configKey)
    const cachedData = checkCachedDataSync(selectedAccount.id, config)
    
    if (currentGlobalState?.metrics || cachedData) {
      // We have existing data - show it immediately and fetch in background
      const existingData = currentGlobalState?.metrics || cachedData
      if (existingData) {
        updateGlobalState({ metrics: existingData, isLoading: false, error: null })
        // Fetch fresh data in background without showing loading
        fetchMetricsInBackground()
      }
    } else {
      // No existing data - show loading state for first fetch
      updateGlobalState({ metrics: null, isLoading: true, error: null })
      fetchMetrics()
    }
  }, [selectedAccount, config, configKey, updateGlobalState, fetchMetrics, fetchMetricsInBackground])

  // Setup automatic refresh mechanism
  const setupAutoRefresh = useCallback(() => {
    if (!selectedAccount || !configKey) return

    // Clear any existing timer for this config
    const existingTimer = globalRefreshTimers.get(configKey)
    if (existingTimer) {
      clearInterval(existingTimer)
    }

    // Set up new 30-second refresh timer
    const refreshTimer = setInterval(() => {
      fetchMetricsInBackground()
    }, 30000) // 30 seconds

    globalRefreshTimers.set(configKey, refreshTimer)

    // Cleanup function
    return () => {
      clearInterval(refreshTimer)
      globalRefreshTimers.delete(configKey)
    }
  }, [selectedAccount, configKey, fetchMetricsInBackground])

  // Handle account changes and trigger background refresh
  useEffect(() => {
    if (!selectedAccount || !configKey) {
      updateGlobalState({ metrics: null, isLoading: false, error: null })
      return
    }

    // Check if we already have data in global state
    const currentGlobalState = globalMetricsState.get(configKey)
    if (currentGlobalState?.metrics) {
      // Always trigger a background refresh to get fresh data, but don't show loading
      fetchMetricsInBackground()
    } else {
      // No data available, fetch fresh data (this will show loading only for first time)
      fetchMetrics()
    }

    // Setup automatic refresh
    const cleanup = setupAutoRefresh()
    return cleanup
  }, [selectedAccount, config, configKey, updateGlobalState, fetchMetrics, fetchMetricsInBackground, setupAutoRefresh])

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

  // Use the longest chart data as the base, including feedback data
  const baseChartData = itemsResult?.chartData || scoreResultsResult?.chartData || feedbackResult?.chartData || []
  
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
  const config = useMemo(() => ({
    sources: {
      items: {
        type: 'items' as const,
        accountId: '', // Will be filled by the hook
      },
      scoreResults: {
        type: 'scoreResults' as const,
        accountId: '', // Will be filled by the hook
      }
    }
  }), [])

  return useUnifiedMetrics(config)
}

/**
 * Hook for prediction items and score results
 */
export function usePredictionMetrics(): UseUnifiedMetricsResult {
  const config = useMemo(() => ({
    sources: {
      items: {
        type: 'items' as const,
        createdByType: 'prediction',
        accountId: '', // Will be filled by the hook
      },
      scoreResults: {
        type: 'scoreResults' as const,
        scoreResultType: 'prediction',
        accountId: '', // Will be filled by the hook
      }
    }
  }), [])

  return useUnifiedMetrics(config)
}

/**
 * Hook for evaluation items and score results
 */
export function useEvaluationMetrics(): UseUnifiedMetricsResult {
  const config = useMemo(() => ({
    sources: {
      items: {
        type: 'items' as const,
        createdByType: 'evaluation',
        accountId: '', // Will be filled by the hook
      },
      scoreResults: {
        type: 'scoreResults' as const,
        scoreResultType: 'evaluation',
        accountId: '', // Will be filled by the hook
      }
    }
  }), [])

  return useUnifiedMetrics(config)
}

/**
 * Hook for feedback items
 */
export function useFeedbackMetrics(): UseUnifiedMetricsResult {
  const config = useMemo(() => ({
    sources: {
      // For feedback, we track score results with feedback type
      scoreResults: {
        type: 'scoreResults' as const,
        scoreResultType: 'feedback',
        accountId: '', // Will be filled by the hook
      }
    }
  }), [])

  return useUnifiedMetrics(config)
}

/**
 * Hook for task metrics
 */
export function useTaskMetrics(): UseUnifiedMetricsResult {
  const config = useMemo(() => ({
    sources: {
      // For tasks, we track task records
      items: {
        type: 'tasks' as const,
        accountId: '', // Will be filled by the hook
      }
    },
    transformations: {
      // Custom peak calculation for tasks (use higher baseline since tasks are less frequent)
      customPeakCalculation: (chartData: Array<{ items: number; scoreResults: number }>) => {
        const itemsPeak = Math.max(...chartData.map(point => point.items), 10) // Minimum 10 for tasks
        const scoreResultsPeak = Math.max(...chartData.map(point => point.scoreResults), 10)
        return { itemsPeak, scoreResultsPeak }
      }
    }
  }), [])

  return useUnifiedMetrics(config)
}

/**
 * Hook for evaluation task metrics (actual task records + score results)
 */
export function useEvaluationTaskMetrics(): UseUnifiedMetricsResult {
  const config = useMemo(() => ({
    sources: {
      // For evaluation tasks, we track actual task records (not items)
      items: {
        type: 'tasks' as const,
        taskType: 'evaluation', // Filter for evaluation-related tasks
        accountId: '', // Will be filled by the hook
      }
    },
    transformations: {
      // Custom peak calculation for evaluation tasks
      customPeakCalculation: (chartData: Array<{ items: number; scoreResults: number }>) => {
        const itemsPeak = Math.max(...chartData.map(point => point.items), 10) // Minimum 10 for evaluation tasks
        const scoreResultsPeak = Math.max(...chartData.map(point => point.scoreResults), 300) // Higher baseline for score results
        return { itemsPeak, scoreResultsPeak }
      }
    }
  }), [])

  return useUnifiedMetrics(config)
} 