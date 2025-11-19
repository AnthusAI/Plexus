import { useState, useEffect, useCallback, useMemo } from 'react'
import { useAccount } from '@/app/contexts/AccountContext'
import { graphqlRequest } from '@/utils/amplify-client'
import type { Schema } from '../amplify/data/resource'

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
  // Filtering options
  filters?: {
    createdByType?: string // For items: "evaluation", "prediction", etc.
    scoreResultType?: string // For scoreResults: "prediction", "evaluation", etc.
    taskType?: string // For tasks: filter by task type
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

type AggregatedMetricsRecord = Schema['AggregatedMetrics']['type']

/**
 * Query AggregatedMetrics table for a specific time range and record type
 * Uses the byAccountRecordType GSI for efficient querying
 */
async function queryAggregatedMetrics(
  accountId: string,
  recordType: 'items' | 'scoreResults' | 'tasks' | 'procedures' | 'graphNodes' | 'predictionItems' | 'evaluationItems' | 'feedbackItems' | 'predictionScoreResults' | 'evaluationScoreResults',
  startTime: Date,
  endTime: Date
): Promise<AggregatedMetricsRecord[]> {
  // Use the byAccountRecordType GSI for efficient querying
  // GSI: idx("accountId").sortKeys(["recordType", "timeRangeStart"])
  const query = `
    query ListAggregatedMetricsByAccountRecordType(
      $accountId: String!
      $recordType: String!
      $startTime: String!
      $endTime: String!
    ) {
      listAggregatedMetricsByAccountIdAndRecordTypeAndTimeRangeStart(
        accountId: $accountId
        recordTypeTimeRangeStart: {
          between: [
            { recordType: $recordType, timeRangeStart: $startTime }
            { recordType: $recordType, timeRangeStart: $endTime }
          ]
        }
        limit: 10000
      ) {
        items {
          id
          accountId
          recordType
          timeRangeStart
          timeRangeEnd
          numberOfMinutes
          count
          cost
          errorCount
          complete
          createdAt
          updatedAt
        }
        nextToken
      }
    }
  `

  const variables = {
    accountId,
    recordType,
    startTime: startTime.toISOString(),
    endTime: endTime.toISOString()
  }

  try {
    const response = await graphqlRequest<any>(query, variables)
    const items = response.data?.listAggregatedMetricsByAccountIdAndRecordTypeAndTimeRangeStart?.items || []
    
    // Filter to only complete records
    return items.filter((item: AggregatedMetricsRecord) => item.complete)
  } catch (error) {
    console.error(`Error querying AggregatedMetrics for ${recordType}:`, error)
    // Return empty array on error instead of throwing - allows graceful degradation
    return []
  }
}

/**
 * Calculate metrics from AggregatedMetrics records
 */
function calculateMetricsFromRecords(
  records: AggregatedMetricsRecord[],
  startTime: Date,
  endTime: Date
): { count: number; errorCount: number } {
  // Filter records that fall within our time range and are complete
  const relevantRecords = records.filter(record => {
    if (!record.complete) return false
    
    const recordStart = new Date(record.timeRangeStart)
    const recordEnd = new Date(record.timeRangeEnd)
    
    // Check if record overlaps with our time range
    return recordStart < endTime && recordEnd > startTime
  })

  // Sum up the counts
  const count = relevantRecords.reduce((sum, record) => sum + (record.count || 0), 0)
  const errorCount = relevantRecords.reduce((sum, record) => sum + (record.errorCount || 0), 0)

  return { count, errorCount }
}

/**
 * Generate chart data from AggregatedMetrics records
 * Groups records into hourly buckets
 */
function generateChartData(
  itemsRecords: AggregatedMetricsRecord[],
  scoreResultsRecords: AggregatedMetricsRecord[]
): Array<{
  time: string
  items: number
  scoreResults: number
  bucketStart: string
  bucketEnd: string
}> {
  const now = new Date()
  const chartData: Array<{
    time: string
    items: number
    scoreResults: number
    bucketStart: string
    bucketEnd: string
  }> = []

  // Generate 24 hourly buckets
  for (let i = 23; i >= 0; i--) {
    const bucketEnd = new Date(now)
    bucketEnd.setHours(bucketEnd.getHours() - i, 0, 0, 0)
    
    const bucketStart = new Date(bucketEnd)
    bucketStart.setHours(bucketStart.getHours() - 1)

    // Sum counts from all records that overlap with this hour bucket
    const itemsCount = itemsRecords
      .filter(record => {
        if (!record.complete) return false
        const recordStart = new Date(record.timeRangeStart)
        const recordEnd = new Date(record.timeRangeEnd)
        return recordStart < bucketEnd && recordEnd > bucketStart
      })
      .reduce((sum, record) => sum + (record.count || 0), 0)

    const scoreResultsCount = scoreResultsRecords
      .filter(record => {
        if (!record.complete) return false
        const recordStart = new Date(record.timeRangeStart)
        const recordEnd = new Date(record.timeRangeEnd)
        return recordStart < bucketEnd && recordEnd > bucketStart
      })
      .reduce((sum, record) => sum + (record.count || 0), 0)

    chartData.push({
      time: bucketStart.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
      items: itemsCount,
      scoreResults: scoreResultsCount,
      bucketStart: bucketStart.toISOString(),
      bucketEnd: bucketEnd.toISOString()
    })
  }

  return chartData
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

/**
 * Unified metrics hook that queries AggregatedMetrics table
 */
export function useUnifiedMetrics(config: MetricsConfig = {}): UseUnifiedMetricsResult {
  const { selectedAccount } = useAccount()
  const [metrics, setMetrics] = useState<UnifiedMetricsData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Memoize config to prevent unnecessary re-renders
  const memoizedConfig = useMemo(() => config, [JSON.stringify(config)])

  const fetchMetrics = useCallback(async () => {
    if (!selectedAccount) {
      setMetrics(null)
      setIsLoading(false)
      setError(null)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const now = new Date()
      const last24h = new Date(now.getTime() - 24 * 60 * 60 * 1000)
      const last60min = new Date(now.getTime() - 60 * 60 * 1000)

      // Determine which items recordType to query based on filters
      let itemsRecordType: 'items' | 'predictionItems' | 'evaluationItems' | 'feedbackItems' = 'items'
      if (memoizedConfig.filters?.useFeedbackItems) {
        itemsRecordType = 'feedbackItems'
      } else if (memoizedConfig.filters?.createdByType === 'prediction') {
        itemsRecordType = 'predictionItems'
      } else if (memoizedConfig.filters?.createdByType === 'evaluation') {
        itemsRecordType = 'evaluationItems'
      }

      // Determine which scoreResults recordType to query based on filters
      let scoreResultsRecordType: 'scoreResults' | 'predictionScoreResults' | 'evaluationScoreResults' = 'scoreResults'
      if (memoizedConfig.filters?.scoreResultType === 'prediction') {
        scoreResultsRecordType = 'predictionScoreResults'
      } else if (memoizedConfig.filters?.scoreResultType === 'evaluation') {
        scoreResultsRecordType = 'evaluationScoreResults'
      }

      // Query AggregatedMetrics for items and scoreResults (or filtered variants)
      const [itemsRecords, scoreResultsRecords] = await Promise.all([
        queryAggregatedMetrics(selectedAccount.id, itemsRecordType, last24h, now),
        queryAggregatedMetrics(selectedAccount.id, scoreResultsRecordType, last24h, now)
      ])

      // Calculate hourly metrics (last 60 minutes)
      const itemsHourly = calculateMetricsFromRecords(itemsRecords, last60min, now)
      const scoreResultsHourly = calculateMetricsFromRecords(scoreResultsRecords, last60min, now)

      // Calculate 24h totals
      const items24h = calculateMetricsFromRecords(itemsRecords, last24h, now)
      const scoreResults24h = calculateMetricsFromRecords(scoreResultsRecords, last24h, now)

      // Generate chart data
      const chartData = generateChartData(itemsRecords, scoreResultsRecords)

      // Calculate peaks
      const { itemsPeak, scoreResultsPeak } = memoizedConfig.transformations?.customPeakCalculation?.(chartData) || 
        calculatePeakValues(chartData)

      // Calculate averages
      const itemsAveragePerHour = Math.round(items24h.count / 24)
      const scoreResultsAveragePerHour = Math.round(scoreResults24h.count / 24)

      // Detect errors
      const hasErrorsLast24h = (items24h.errorCount + scoreResults24h.errorCount) > 0
      const totalErrors24h = items24h.errorCount + scoreResults24h.errorCount

      const metricsData: UnifiedMetricsData = {
        itemsPerHour: itemsHourly.count,
        itemsAveragePerHour,
        itemsPeakHourly: itemsPeak,
        itemsTotal24h: items24h.count,
        
        scoreResultsPerHour: scoreResultsHourly.count,
        scoreResultsAveragePerHour,
        scoreResultsPeakHourly: scoreResultsPeak,
        scoreResultsTotal24h: scoreResults24h.count,
        
        chartData,
        lastUpdated: now,
        hasErrorsLast24h,
        totalErrors24h
      }

      setMetrics(metricsData)
      setIsLoading(false)
    } catch (err) {
      console.error('Error fetching unified metrics:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch metrics')
      setIsLoading(false)
    }
  }, [selectedAccount, memoizedConfig])

  // Setup subscriptions for real-time updates
  useEffect(() => {
    if (!selectedAccount) return

    let handles: Array<{ unsubscribe: () => void }> = []

    // Import subscription functions dynamically to avoid circular dependencies
    import('@/utils/subscriptions').then(({ observeAggregatedMetricsCreation, observeAggregatedMetricsUpdates }) => {
      // Subscribe to AggregatedMetrics creation
      if (observeAggregatedMetricsCreation) {
        const createSub = observeAggregatedMetricsCreation(selectedAccount.id, () => {
          console.log('AggregatedMetrics created, refetching...')
          fetchMetrics()
        })
        handles.push(createSub)
      }

      // Subscribe to AggregatedMetrics updates
      if (observeAggregatedMetricsUpdates) {
        const updateSub = observeAggregatedMetricsUpdates(selectedAccount.id, () => {
          console.log('AggregatedMetrics updated, refetching...')
          fetchMetrics()
        })
        handles.push(updateSub)
      }
    }).catch(err => {
      console.warn('Could not setup AggregatedMetrics subscriptions:', err)
    })

    return () => {
      handles.forEach(handle => handle.unsubscribe())
    }
  }, [selectedAccount?.id, fetchMetrics])

  // Initial fetch and periodic refresh
  useEffect(() => {
    fetchMetrics()

    // Refresh every 30 seconds
    const refreshInterval = setInterval(() => {
      fetchMetrics()
    }, 30000)

    return () => clearInterval(refreshInterval)
  }, [fetchMetrics])

  const refetch = useCallback(() => {
    fetchMetrics()
  }, [fetchMetrics])

  return {
    metrics,
    isLoading,
    error,
    refetch
  }
}

// Convenience hooks for common use cases

/**
 * Hook for all items and score results (no filtering) - backward compatible
 */
export function useAllItemsMetrics(): UseUnifiedMetricsResult {
  return useUnifiedMetrics({})
}

/**
 * Hook for prediction items and score results
 */
export function usePredictionMetrics(): UseUnifiedMetricsResult {
  return useUnifiedMetrics({
    filters: {
      createdByType: 'prediction',
      scoreResultType: 'prediction'
    }
  })
}

/**
 * Hook for evaluation items and score results
 */
export function useEvaluationMetrics(): UseUnifiedMetricsResult {
  return useUnifiedMetrics({
    filters: {
      createdByType: 'evaluation',
      scoreResultType: 'evaluation'
    }
  })
}

/**
 * Hook for feedback items
 * Note: Feedback items are tracked in the FeedbackItem table, not as a filter on Items
 */
export function useFeedbackMetrics(): UseUnifiedMetricsResult {
  return useUnifiedMetrics({
    filters: {
      useFeedbackItems: true  // Special flag to query feedbackItems instead of items
    }
  })
}

/**
 * Hook for task metrics
 * Queries the tasks recordType from AggregatedMetrics
 */
export function useTaskMetrics(): UseUnifiedMetricsResult {
  const { selectedAccount } = useAccount()
  const [metrics, setMetrics] = useState<UnifiedMetricsData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchMetrics = useCallback(async () => {
    if (!selectedAccount) {
      setMetrics(null)
      setIsLoading(false)
      setError(null)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const now = new Date()
      const last24h = new Date(now.getTime() - 24 * 60 * 60 * 1000)
      const last60min = new Date(now.getTime() - 60 * 60 * 1000)

      // Query AggregatedMetrics for tasks only
      const tasksRecords = await queryAggregatedMetrics(selectedAccount.id, 'tasks', last24h, now)

      // Calculate hourly metrics (last 60 minutes)
      const tasksHourly = calculateMetricsFromRecords(tasksRecords, last60min, now)

      // Calculate 24h totals
      const tasks24h = calculateMetricsFromRecords(tasksRecords, last24h, now)

      // Generate chart data (only tasks, no scoreResults)
      const chartData = generateChartData(tasksRecords, [])

      // Calculate peaks with higher baseline for tasks
      const itemsPeak = Math.max(...chartData.map(point => point.items), 10) // Minimum 10 for tasks

      // Calculate averages
      const itemsAveragePerHour = Math.round(tasks24h.count / 24)

      // Detect errors
      const hasErrorsLast24h = tasks24h.errorCount > 0
      const totalErrors24h = tasks24h.errorCount

      const metricsData: UnifiedMetricsData = {
        itemsPerHour: tasksHourly.count,
        itemsAveragePerHour,
        itemsPeakHourly: itemsPeak,
        itemsTotal24h: tasks24h.count,
        
        // No scoreResults for tasks
        scoreResultsPerHour: 0,
        scoreResultsAveragePerHour: 0,
        scoreResultsPeakHourly: 10,
        scoreResultsTotal24h: 0,
        
        chartData,
        lastUpdated: now,
        hasErrorsLast24h,
        totalErrors24h
      }

      setMetrics(metricsData)
      setIsLoading(false)
    } catch (err) {
      console.error('Error fetching task metrics:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch metrics')
      setIsLoading(false)
    }
  }, [selectedAccount])

  // Setup subscriptions for real-time updates
  useEffect(() => {
    if (!selectedAccount) return

    let handles: Array<{ unsubscribe: () => void }> = []

    // Import subscription functions dynamically to avoid circular dependencies
    import('@/utils/subscriptions').then(({ observeAggregatedMetricsCreation, observeAggregatedMetricsUpdates }) => {
      // Subscribe to AggregatedMetrics creation
      if (observeAggregatedMetricsCreation) {
        const createSub = observeAggregatedMetricsCreation(selectedAccount.id, () => {
          console.log('AggregatedMetrics created, refetching task metrics...')
          fetchMetrics()
        })
        handles.push(createSub)
      }

      // Subscribe to AggregatedMetrics updates
      if (observeAggregatedMetricsUpdates) {
        const updateSub = observeAggregatedMetricsUpdates(selectedAccount.id, () => {
          console.log('AggregatedMetrics updated, refetching task metrics...')
          fetchMetrics()
        })
        handles.push(updateSub)
      }
    }).catch(err => {
      console.warn('Could not setup AggregatedMetrics subscriptions:', err)
    })

    return () => {
      handles.forEach(handle => handle.unsubscribe())
    }
  }, [selectedAccount?.id, fetchMetrics])

  // Initial fetch and periodic refresh
  useEffect(() => {
    fetchMetrics()

    // Refresh every 30 seconds
    const refreshInterval = setInterval(() => {
      fetchMetrics()
    }, 30000)

    return () => clearInterval(refreshInterval)
  }, [fetchMetrics])

  const refetch = useCallback(() => {
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
 * Hook for procedures metrics (procedures + graph nodes)
 */
export function useProceduresMetrics(): UseUnifiedMetricsResult {
  const { selectedAccount } = useAccount()
  const [metrics, setMetrics] = useState<UnifiedMetricsData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchMetrics = useCallback(async () => {
    if (!selectedAccount) {
      setMetrics(null)
      setIsLoading(false)
      setError(null)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const now = new Date()
      const last24h = new Date(now.getTime() - 24 * 60 * 60 * 1000)
      const last60min = new Date(now.getTime() - 60 * 60 * 1000)

      // Query AggregatedMetrics for procedures and graphNodes
      const [proceduresRecords, graphNodesRecords] = await Promise.all([
        queryAggregatedMetrics(selectedAccount.id, 'procedures', last24h, now),
        queryAggregatedMetrics(selectedAccount.id, 'graphNodes', last24h, now)
      ])

      // Calculate hourly metrics (last 60 minutes)
      const proceduresHourly = calculateMetricsFromRecords(proceduresRecords, last60min, now)
      const graphNodesHourly = calculateMetricsFromRecords(graphNodesRecords, last60min, now)

      // Calculate 24h totals
      const procedures24h = calculateMetricsFromRecords(proceduresRecords, last24h, now)
      const graphNodes24h = calculateMetricsFromRecords(graphNodesRecords, last24h, now)

      // Generate chart data
      const chartData = generateChartData(proceduresRecords, graphNodesRecords)

      // Calculate peaks with higher baselines for procedures
      const itemsPeak = Math.max(...chartData.map(point => point.items), 10) // Minimum 10 for procedures
      const scoreResultsPeak = Math.max(...chartData.map(point => point.scoreResults), 50) // Minimum 50 for graph nodes

      // Calculate averages
      const itemsAveragePerHour = Math.round(procedures24h.count / 24)
      const scoreResultsAveragePerHour = Math.round(graphNodes24h.count / 24)

      // Detect errors
      const hasErrorsLast24h = (procedures24h.errorCount + graphNodes24h.errorCount) > 0
      const totalErrors24h = procedures24h.errorCount + graphNodes24h.errorCount

      const metricsData: UnifiedMetricsData = {
        itemsPerHour: proceduresHourly.count,
        itemsAveragePerHour,
        itemsPeakHourly: itemsPeak,
        itemsTotal24h: procedures24h.count,
        
        scoreResultsPerHour: graphNodesHourly.count,
        scoreResultsAveragePerHour,
        scoreResultsPeakHourly: scoreResultsPeak,
        scoreResultsTotal24h: graphNodes24h.count,
        
        chartData,
        lastUpdated: now,
        hasErrorsLast24h,
        totalErrors24h
      }

      setMetrics(metricsData)
      setIsLoading(false)
    } catch (err) {
      console.error('Error fetching procedures metrics:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch metrics')
      setIsLoading(false)
    }
  }, [selectedAccount])

  // Setup subscriptions for real-time updates
  useEffect(() => {
    if (!selectedAccount) return

    let handles: Array<{ unsubscribe: () => void }> = []

    // Import subscription functions dynamically to avoid circular dependencies
    import('@/utils/subscriptions').then(({ observeAggregatedMetricsCreation, observeAggregatedMetricsUpdates }) => {
      // Subscribe to AggregatedMetrics creation
      if (observeAggregatedMetricsCreation) {
        const createSub = observeAggregatedMetricsCreation(selectedAccount.id, () => {
          console.log('AggregatedMetrics created, refetching procedures metrics...')
          fetchMetrics()
        })
        handles.push(createSub)
      }

      // Subscribe to AggregatedMetrics updates
      if (observeAggregatedMetricsUpdates) {
        const updateSub = observeAggregatedMetricsUpdates(selectedAccount.id, () => {
          console.log('AggregatedMetrics updated, refetching procedures metrics...')
          fetchMetrics()
        })
        handles.push(updateSub)
      }
    }).catch(err => {
      console.warn('Could not setup AggregatedMetrics subscriptions:', err)
    })

    return () => {
      handles.forEach(handle => handle.unsubscribe())
    }
  }, [selectedAccount?.id, fetchMetrics])

  // Initial fetch and periodic refresh
  useEffect(() => {
    fetchMetrics()

    // Refresh every 30 seconds
    const refreshInterval = setInterval(() => {
      fetchMetrics()
    }, 30000)

    return () => clearInterval(refreshInterval)
  }, [fetchMetrics])

  const refetch = useCallback(() => {
    fetchMetrics()
  }, [fetchMetrics])

  return {
    metrics,
    isLoading,
    error,
    refetch
  }
}

