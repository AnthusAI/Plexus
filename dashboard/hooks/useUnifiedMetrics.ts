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
    useFeedbackItems?: boolean // Special flag to query feedbackItems instead of items
  }
  
  // Time range configuration
  timeRange?: {
    start: Date
    end: Date
    period: 'hour' | 'day' | 'week'
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

// Bucket sizes in descending order for hierarchical selection
const BUCKET_SIZES = [60, 15, 5, 1] as const

/**
 * Check if a time is aligned to a specific bucket size
 */
function isAlignedToBucket(time: Date, bucketMinutes: number): boolean {
  const minutes = time.getMinutes()
  const hours = time.getHours()
  
  switch (bucketMinutes) {
    case 60:
      return minutes === 0
    case 15:
      return minutes % 15 === 0
    case 5:
      return minutes % 5 === 0
    case 1:
      return true // Always aligned to 1-minute buckets
    default:
      return false
  }
}

/**
 * Align a time down to the nearest bucket boundary
 */
function alignTimeToBucket(time: Date, bucketMinutes: number): Date {
  const aligned = new Date(time)
  const totalMinutes = aligned.getHours() * 60 + aligned.getMinutes()
  const alignedMinutes = Math.floor(totalMinutes / bucketMinutes) * bucketMinutes
  
  aligned.setHours(Math.floor(alignedMinutes / 60))
  aligned.setMinutes(alignedMinutes % 60)
  aligned.setSeconds(0)
  aligned.setMilliseconds(0)
  
  return aligned
}

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
          accountId
          compositeKey
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
    
    // Return all records (including incomplete ones for rolling window calculations)
    return items
  } catch (error) {
    console.error(`Error querying AggregatedMetrics for ${recordType}:`, error)
    // Return empty array on error instead of throwing - allows graceful degradation
    return []
  }
}

/**
 * Calculate metrics from AggregatedMetrics records using hierarchical bucket selection
 * 
 * This algorithm avoids double-counting by preferring larger buckets and only using
 * smaller buckets to fill gaps. For example, if we have a 60-minute bucket covering
 * 8:00-9:00, we won't also count the twelve 5-minute buckets within that same period.
 * 
 * Algorithm:
 * 1. Sort records by bucket size (largest first: 60, 15, 5, 1)
 * 2. Track which time ranges have been "covered" by selected buckets
 * 3. For each record (largest first), select it only if it doesn't overlap with already-covered time
 * 4. Sum the counts from selected records
 */
function calculateMetricsFromRecords(
  records: AggregatedMetricsRecord[],
  startTime: Date,
  endTime: Date
): { count: number; errorCount: number } {
  console.log(`[calculateMetricsFromRecords] Processing ${records.length} records for time range ${startTime.toISOString()} to ${endTime.toISOString()}`)
  
  // Filter records that overlap with our time range
  const overlappingRecords = records.filter(record => {
    const recordStart = new Date(record.timeRangeStart)
    const recordEnd = new Date(record.timeRangeEnd)
    return recordStart < endTime && recordEnd > startTime
  })

  console.log(`[calculateMetricsFromRecords] Found ${overlappingRecords.length} overlapping records`)
  
  if (overlappingRecords.length === 0) {
    return { count: 0, errorCount: 0 }
  }

  // Sort by bucket size (largest first), then by start time
  const sortedRecords = [...overlappingRecords].sort((a, b) => {
    // First by bucket size (descending)
    if (b.numberOfMinutes !== a.numberOfMinutes) {
      return b.numberOfMinutes - a.numberOfMinutes
    }
    // Then by start time (ascending)
    return new Date(a.timeRangeStart).getTime() - new Date(b.timeRangeStart).getTime()
  })

  // Track covered time ranges as [start, end] pairs in milliseconds
  const coveredRanges: Array<[number, number]> = []
  
  // Helper: Check if a time range overlaps with any covered range
  const isOverlapping = (start: number, end: number): boolean => {
    return coveredRanges.some(([coveredStart, coveredEnd]) => {
      return start < coveredEnd && end > coveredStart
    })
  }
  
  // Helper: Add a time range to covered ranges
  const addCoveredRange = (start: number, end: number) => {
    coveredRanges.push([start, end])
  }

  // Select non-overlapping records (hierarchically)
  const selectedRecords: AggregatedMetricsRecord[] = []
  
  for (const record of sortedRecords) {
    const recordStart = new Date(record.timeRangeStart).getTime()
    const recordEnd = new Date(record.timeRangeEnd).getTime()
    
    // Clamp to our query range
    const clampedStart = Math.max(recordStart, startTime.getTime())
    const clampedEnd = Math.min(recordEnd, endTime.getTime())
    
    // Only select if this time range isn't already covered
    if (!isOverlapping(clampedStart, clampedEnd)) {
      selectedRecords.push(record)
      addCoveredRange(clampedStart, clampedEnd)
    }
  }

  console.log(`[calculateMetricsFromRecords] Selected ${selectedRecords.length} non-overlapping records (from ${overlappingRecords.length} overlapping)`)
  
  if (selectedRecords.length > 0 && selectedRecords.length <= 10) {
    selectedRecords.forEach(r => {
      console.log(`[calculateMetricsFromRecords]   Selected: ${r.timeRangeStart} to ${r.timeRangeEnd}, ${r.numberOfMinutes}min, count=${r.count}`)
    })
  }

  // Sum up the counts from selected records
  const count = selectedRecords.reduce((sum, record) => sum + (record.count || 0), 0)
  const errorCount = selectedRecords.reduce((sum, record) => sum + (record.errorCount || 0), 0)

  console.log(`[calculateMetricsFromRecords] Result: count=${count}, errorCount=${errorCount}`)

  return { count, errorCount }
}

/**
 * Generate chart data from AggregatedMetrics records
 * Groups records into buckets using hierarchical selection to avoid double-counting
 * Bucket size adapts based on the time period
 */
function generateChartData(
  itemsRecords: AggregatedMetricsRecord[],
  scoreResultsRecords: AggregatedMetricsRecord[],
  startTime?: Date,
  endTime?: Date,
  period?: 'hour' | 'day' | 'week'
): Array<{
  time: string
  items: number
  scoreResults: number
  bucketStart: string
  bucketEnd: string
}> {
  const now = new Date()
  const end = endTime || now
  const start = startTime || new Date(now.getTime() - 24 * 60 * 60 * 1000)
  const actualPeriod = period || 'day'
  
  const chartData: Array<{
    time: string
    items: number
    scoreResults: number
    bucketStart: string
    bucketEnd: string
  }> = []

  // Determine bucket size and count based on period
  let bucketSizeMs: number
  let bucketCount: number
  
  switch (actualPeriod) {
    case 'hour':
      // For 1 hour period: 12 buckets of 5 minutes each
      bucketSizeMs = 5 * 60 * 1000
      bucketCount = 12
      break
    case 'day':
      // For 24 hour period: 24 buckets of 1 hour each
      bucketSizeMs = 60 * 60 * 1000
      bucketCount = 24
      break
    case 'week':
      // For 7 day period: 28 buckets of 6 hours each
      bucketSizeMs = 6 * 60 * 60 * 1000
      bucketCount = 28
      break
  }

  // Generate buckets from start to end
  for (let i = bucketCount - 1; i >= 0; i--) {
    const bucketEnd = new Date(end.getTime() - i * bucketSizeMs)
    const bucketStart = new Date(bucketEnd.getTime() - bucketSizeMs)

    // Use hierarchical selection to avoid double-counting
    const itemsMetrics = calculateMetricsFromRecords(itemsRecords, bucketStart, bucketEnd)
    const scoreResultsMetrics = calculateMetricsFromRecords(scoreResultsRecords, bucketStart, bucketEnd)

    chartData.push({
      time: bucketStart.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
      items: itemsMetrics.count,
      scoreResults: scoreResultsMetrics.count,
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
      
      // Use custom time range if provided, otherwise default to last 24h
      const timeRange = memoizedConfig.timeRange
      const rangeEnd = timeRange?.end || now
      const rangeStart = timeRange?.start || new Date(now.getTime() - 24 * 60 * 60 * 1000)
      const period = timeRange?.period || 'day'
      
      // Calculate the time window for per-hour gauge (last 60 minutes within the range)
      // For historical periods, use the last hour of that period
      const gaugeEnd = rangeEnd
      const gaugeStart = new Date(Math.max(
        gaugeEnd.getTime() - 60 * 60 * 1000,
        rangeStart.getTime()
      ))

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
        queryAggregatedMetrics(selectedAccount.id, itemsRecordType, rangeStart, rangeEnd),
        queryAggregatedMetrics(selectedAccount.id, scoreResultsRecordType, rangeStart, rangeEnd)
      ])

      // Debug logging
      console.log(`[useUnifiedMetrics] Fetched ${itemsRecords.length} items records, ${scoreResultsRecords.length} scoreResults records`)
      if (itemsRecords.length > 0) {
        console.log(`[useUnifiedMetrics] Sample items record:`, itemsRecords[0])
        console.log(`[useUnifiedMetrics] Available bucket sizes:`, [...new Set(itemsRecords.map(r => r.numberOfMinutes))].sort((a, b) => a - b))
      }

      // Calculate hourly metrics (last 60 minutes within the range)
      const itemsHourly = calculateMetricsFromRecords(itemsRecords, gaugeStart, gaugeEnd)
      const scoreResultsHourly = calculateMetricsFromRecords(scoreResultsRecords, gaugeStart, gaugeEnd)
      
      console.log(`[useUnifiedMetrics] Hourly: ${itemsHourly.count} items, ${scoreResultsHourly.count} scoreResults`)

      // Calculate totals for the entire range
      const itemsTotal = calculateMetricsFromRecords(itemsRecords, rangeStart, rangeEnd)
      const scoreResultsTotal = calculateMetricsFromRecords(scoreResultsRecords, rangeStart, rangeEnd)

      // Generate chart data with custom time range
      const chartData = generateChartData(itemsRecords, scoreResultsRecords, rangeStart, rangeEnd, period)

      // Calculate peaks
      const { itemsPeak, scoreResultsPeak } = memoizedConfig.transformations?.customPeakCalculation?.(chartData) || 
        calculatePeakValues(chartData)

      // Calculate averages based on the time period
      const rangeHours = (rangeEnd.getTime() - rangeStart.getTime()) / (60 * 60 * 1000)
      const itemsAveragePerHour = Math.round(itemsTotal.count / rangeHours)
      const scoreResultsAveragePerHour = Math.round(scoreResultsTotal.count / rangeHours)

      // Detect errors
      const hasErrorsInRange = (itemsTotal.errorCount + scoreResultsTotal.errorCount) > 0
      const totalErrorsInRange = itemsTotal.errorCount + scoreResultsTotal.errorCount

      const metricsData: UnifiedMetricsData = {
        itemsPerHour: itemsHourly.count,
        itemsAveragePerHour,
        itemsPeakHourly: itemsPeak,
        itemsTotal24h: itemsTotal.count,
        
        scoreResultsPerHour: scoreResultsHourly.count,
        scoreResultsAveragePerHour,
        scoreResultsPeakHourly: scoreResultsPeak,
        scoreResultsTotal24h: scoreResultsTotal.count,
        
        chartData,
        lastUpdated: now,
        hasErrorsLast24h: hasErrorsInRange,
        totalErrors24h: totalErrorsInRange
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
      const chartData = generateChartData(tasksRecords, [], last24h, now, 'day')

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
      const chartData = generateChartData(proceduresRecords, graphNodesRecords, last24h, now, 'day')

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

