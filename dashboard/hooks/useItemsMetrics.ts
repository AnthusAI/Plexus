import { useState, useEffect, useCallback } from 'react'
import { useAccount } from '@/app/contexts/AccountContext'
import { getAggregatedMetrics, AggregatedMetricsData } from '@/utils/metricsAggregator'
import { generateChartData, calculatePeakValues, calculateAverageValues, ChartDataPoint } from '@/utils/chartDataGenerator'
import { graphqlRequest } from '@/utils/amplify-client'

interface MetricsData {
  scoreResultsPerHour: number
  itemsPerHour: number
  scoreResultsAveragePerHour: number
  itemsAveragePerHour: number
  itemsPeakHourly: number
  scoreResultsPeakHourly: number
  itemsTotal24h: number
  scoreResultsTotal24h: number
  chartData: ChartDataPoint[]
  lastUpdated: Date
  // New comprehensive metrics
  totalCost24h: number
  totalDecisions24h: number
  totalExternalApiCalls24h: number
  totalCachedApiCalls24h: number
  totalErrors24h: number
  costPerHour: number
  // Error detection for dashboard alerts
  hasErrorsLast24h: boolean
}

interface UseItemsMetricsResult {
  metrics: MetricsData | null
  isLoading: boolean
  error: string | null
  refetch: () => void
}

/**
 * Count ScoreResults with errors in the last 24 hours using the efficient GSI
 */
async function countErrorsLast24h(accountId: string): Promise<number> {
  console.log('🔍 countErrorsLast24h called with accountId:', accountId)
  const now = new Date()
  const last24Hours = new Date(now.getTime() - 24 * 60 * 60 * 1000)
  console.log('🕐 Counting errors since:', last24Hours.toISOString())
  
  try {
    // Log the exact query and variables being sent
    const query = `
      query CountErrors($accountId: String!) {
        listScoreResultByAccountIdAndCodeAndUpdatedAt(
          accountId: $accountId,
          codeUpdatedAt: { beginsWith: { code: "5" } },
          sortDirection: DESC,
          limit: 1000
        ) {
          items {
            id
            updatedAt
            code
            value
            explanation
          }
        }
      }
    `
    const variables = { accountId }
    
    console.log('🔍 EXACT GraphQL Query:', query)
    console.log('🔍 EXACT GraphQL Variables:', variables)
    
    // Log the complete GraphQL request as JSON for easy copy/paste
    const completeRequest = {
      query: query.trim(),
      variables: variables
    }
    console.log('📝 COMPLETE GraphQL REQUEST (copy this):', JSON.stringify(completeRequest, null, 2))
    
    // Use the dedicated code GSI to efficiently find 5xx errors
    const response = await graphqlRequest<{
      listScoreResultByAccountIdAndCodeAndUpdatedAt: {
        items: Array<{ id: string; updatedAt: string; code?: string; value?: string; explanation?: string }>
      }
    }>(query, variables)
    
    console.log('📊 Error count GSI query response (FULL):', JSON.stringify(response, null, 2))
    console.log('📊 Number of items returned:', response.data?.listScoreResultByAccountIdAndCodeAndUpdatedAt?.items?.length || 0)
    
    // Log each item returned to see what codes/values they have
    response.data?.listScoreResultByAccountIdAndCodeAndUpdatedAt?.items?.forEach((item, index) => {
      console.log(`📋 Item ${index}:`, {
        id: item.id,
        updatedAt: item.updatedAt,
        code: item.code,
        value: item.value,
        explanation: item.explanation?.substring(0, 100) + '...'
      })
    })
    
    // Filter results to only those in the last 24 hours (client-side filtering on small result set)
    const recentErrors = response.data?.listScoreResultByAccountIdAndCodeAndUpdatedAt?.items?.filter(item => {
      const itemDate = new Date(item.updatedAt)
      const isRecent = itemDate >= last24Hours
      console.log('📅 COUNT: Checking error item:', item.id, 'updatedAt:', item.updatedAt, 'itemDate:', itemDate.toISOString(), 'last24Hours:', last24Hours.toISOString(), 'isRecent:', isRecent)
      return isRecent
    }) || []
    
    console.log('🚨 COUNT: Found recent error ScoreResults:', recentErrors.length)
    return recentErrors.length
  } catch (error) {
    console.error('❌ Error counting ScoreResult errors:', error)
    
    // Check if this is because the GSI doesn't exist yet
    const errorMessage = (error as any)?.message || ''
    if (errorMessage.includes('Field') && errorMessage.includes('undefined')) {
      console.log('⚠️ Code GSI not yet deployed, falling back to keyword search method')
      
      // Fallback to the old keyword-based approach but with higher limit
      return await countErrorsWithKeywordFallback(accountId, last24Hours)
    }
    
    return 0
  }
}

/**
 * Comprehensive method for counting errors using keyword search to catch all error patterns
 */
async function countErrorsWithKeywordFallback(accountId: string, last24Hours: Date): Promise<number> {
  try {
    const response = await graphqlRequest<{
      listScoreResultByAccountIdAndUpdatedAt: {
        items: Array<{ 
          id: string; 
          updatedAt: string; 
          value?: string; 
          explanation?: string; 
        }>;
        nextToken: string | null;
      }
    }>(`
      query CountErrorsFallback($accountId: String!) {
        listScoreResultByAccountIdAndUpdatedAt(
          accountId: $accountId,
          sortDirection: DESC,
          limit: 10000
        ) {
          items {
            id
            updatedAt
            value
            explanation
          }
          nextToken
        }
      }
    `, {
      accountId
    })
    
    console.log('📊 Comprehensive error count query response (first 10000 results):', response)
    
    if (response.data?.listScoreResultByAccountIdAndUpdatedAt?.items) {
      // Filter results to only those in the last 24 hours with error patterns
      const recentErrorResults = response.data.listScoreResultByAccountIdAndUpdatedAt.items.filter(item => {
        const itemDate = new Date(item.updatedAt)
        const isRecent = itemDate >= last24Hours
        
        if (!isRecent) return false
        
        // Check for error patterns in value and explanation
        const value = item.value?.toLowerCase() || ''
        const explanation = item.explanation?.toLowerCase() || ''
        
        const hasError = value.includes('error') || 
                        value.includes('fail') || 
                        value.includes('exception') || 
                        explanation.includes('error') || 
                        explanation.includes('fail') || 
                        explanation.includes('exception') ||
                        explanation.includes('timeout') ||
                        explanation.includes('not found') ||
                        explanation.includes('invalid')
        
        return hasError
      })
      
      console.log('🚨 Found recent error ScoreResults (comprehensive):', recentErrorResults.length)
      return recentErrorResults.length
    }
    
    console.log('🚫 No ScoreResults found in comprehensive response')
    return 0
  } catch (error) {
    console.error('❌ Error in comprehensive counting method:', error)
    return 0
  }
}

/**
 * Check if there are any ScoreResults with error codes (5xx) in the last 24 hours
 */
async function checkForErrorsLast24h(accountId: string): Promise<boolean> {
  console.log('🔍 checkForErrorsLast24h called with accountId:', accountId)
  const now = new Date()
  const last24Hours = new Date(now.getTime() - 24 * 60 * 60 * 1000)
  console.log('🕐 Checking for errors since:', last24Hours.toISOString())
  
  try {
    // Log the exact query and variables being sent
    const query = `
      query CheckForErrors($accountId: String!) {
        listScoreResultByAccountIdAndCodeAndUpdatedAt(
          accountId: $accountId,
          codeUpdatedAt: { beginsWith: { code: "5" } },
          sortDirection: DESC,
          limit: 1000
        ) {
          items {
            id
            updatedAt
            code
            value
            explanation
          }
        }
      }
    `
    const variables = { accountId }
    
    console.log('🔍 CHECK: EXACT GraphQL Query:', query)
    console.log('🔍 CHECK: EXACT GraphQL Variables:', variables)
    
    // Log the complete GraphQL request as JSON for easy copy/paste
    const completeRequest = {
      query: query.trim(),
      variables: variables
    }
    console.log('📝 CHECK: COMPLETE GraphQL REQUEST (copy this):', JSON.stringify(completeRequest, null, 2))
    
    // Use the dedicated code GSI to efficiently find 5xx errors
    const response = await graphqlRequest<{
      listScoreResultByAccountIdAndCodeAndUpdatedAt: {
        items: Array<{ id: string; updatedAt: string; code?: string; value?: string; explanation?: string }>
      }
    }>(query, variables)
    
    console.log('📊 CHECK: GSI query response (FULL):', JSON.stringify(response, null, 2))
    console.log('📊 CHECK: Number of items returned:', response.data?.listScoreResultByAccountIdAndCodeAndUpdatedAt?.items?.length || 0)
    
    // Log each item returned to see what codes/values they have
    response.data?.listScoreResultByAccountIdAndCodeAndUpdatedAt?.items?.forEach((item, index) => {
      console.log(`📋 CHECK Item ${index}:`, {
        id: item.id,
        updatedAt: item.updatedAt,
        code: item.code,
        value: item.value,
        explanation: item.explanation?.substring(0, 100) + '...'
      })
    })
    
    // Filter results to only those in the last 24 hours (client-side filtering on small result set)
    const recentErrors = response.data?.listScoreResultByAccountIdAndCodeAndUpdatedAt?.items?.filter(item => {
      const itemDate = new Date(item.updatedAt)
      console.log('📅 Checking item:', item.id, 'updatedAt:', item.updatedAt, 'isRecent:', itemDate >= last24Hours)
      return itemDate >= last24Hours
    }) || []
    
    console.log('🚨 Found recent errors:', recentErrors.length)
    return recentErrors.length > 0
  } catch (error) {
    console.error('❌ Error checking for ScoreResult errors:', error)
    
    // Check if this is because the GSI doesn't exist yet
    const errorMessage = (error as any)?.message || ''
    if (errorMessage.includes('Field') && errorMessage.includes('undefined')) {
      console.log('Code GSI not yet deployed, error detection disabled until deployment')
    }
    
    // Return false on error - no fallback to avoid table scans on huge tables
    console.log('🚫 Returning false due to error')
    return false
  }
}

/**
 * Calculate comprehensive metrics for items and score results
 * Implements parallel loading: hourly metrics (for immediate gauge display) and 24-hour data (for charts)
 * Uses bucket-level synchronization to avoid duplicate computation while allowing parallel processing
 */
async function calculateMetrics(
  accountId: string, 
  onProgressUpdate?: (partialMetrics: Partial<MetricsData>) => void
): Promise<MetricsData> {
  const now = new Date();
  const last24Hours = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  
  // Fix for rolling 60-minute window: ensure we capture complete time periods
  // The issue: a simple "60 minutes ago" misses data when crossing hour boundaries
  // Solution: extend the window to ensure we get at least 60 minutes of complete data
  const nowAligned = new Date(now);
  nowAligned.setSeconds(0, 0); // Align current time to minute boundary
  
  // Calculate how much of the current hour we have
  const currentHourMinutes = nowAligned.getMinutes();
  
  // Extend the window to ensure we get at least 60 complete minutes
  // If we're 5 minutes into the hour, we need to go back 65 minutes to get the full previous hour
  const windowMinutes = 60 + currentHourMinutes;
  const lastHour = new Date(nowAligned.getTime() - windowMinutes * 60 * 1000);
  
  try {
    // PARALLEL EXECUTION STRATEGY:
    // 1. Start hourly metrics computation immediately (Priority 1 - for gauges)
    // 2. Start 24-hour chart data generation in parallel (Priority 2 - for charts)
    // 3. The hierarchical caching system prevents duplicate bucket computation
    // 4. Both can work on different time buckets simultaneously
    
    const hourlyMetricsPromise = Promise.all([
      getAggregatedMetrics(accountId, 'items', lastHour, now),
      getAggregatedMetrics(accountId, 'scoreResults', lastHour, now)
    ]).then(([itemsMetricsLastHour, scoreResultsMetricsLastHour]) => {
      // FIRST PROGRESS UPDATE: Send hourly gauge data as soon as it's ready
      // This allows the UI to show meaningful values immediately

      // Normalize the count to a true hourly rate.
      // The window (`lastHour` to `now`) is slightly larger than 60 minutes to ensure complete bucket coverage.
      const actualWindowMinutes = (now.getTime() - lastHour.getTime()) / (60 * 1000);
      const normalizationFactor = actualWindowMinutes > 0 ? 60 / actualWindowMinutes : 1;
      
      const itemsPerHour = Math.round(itemsMetricsLastHour.count * normalizationFactor);
      const scoreResultsPerHour = Math.round(scoreResultsMetricsLastHour.count * normalizationFactor);
      const costPerHour = (scoreResultsMetricsLastHour.cost || 0) * normalizationFactor;

      if (onProgressUpdate) {
        onProgressUpdate({
          itemsPerHour,
          scoreResultsPerHour,
          costPerHour,
          lastUpdated: now
        })
      }
      return { itemsMetricsLastHour, scoreResultsMetricsLastHour, itemsPerHour, scoreResultsPerHour, costPerHour };
    });

    // Start chart data generation in parallel (this will also compute 24-hour totals)
    // This benefits from any caching done by the hourly computation above
    const chartDataPromise = generateChartData(
      accountId, 
      last24Hours, 
      now,
      undefined, // scorecardId
      undefined, // scoreId
      (progressChartData) => {
        // PROGRESSIVE CHART UPDATES: Update chart as buckets are computed
        const { itemsAverage, scoreResultsAverage } = calculateAverageValues(progressChartData)
        const { itemsPeak, scoreResultsPeak } = calculatePeakValues(progressChartData)
        
        if (onProgressUpdate) {
          onProgressUpdate({
            chartData: progressChartData,
            itemsAveragePerHour: itemsAverage,
            scoreResultsAveragePerHour: scoreResultsAverage,
            itemsPeakHourly: itemsPeak,
            scoreResultsPeakHourly: scoreResultsPeak,
            itemsTotal24h: progressChartData.reduce((sum, point) => sum + point.items, 0),
            scoreResultsTotal24h: progressChartData.reduce((sum, point) => sum + point.scoreResults, 0),
            lastUpdated: now
          })
        }
      }
    )

    // Wait for hourly metrics first (should be fastest - smaller time range)
    const { itemsMetricsLastHour, scoreResultsMetricsLastHour, itemsPerHour, scoreResultsPerHour, costPerHour } = await hourlyMetricsPromise;
    
    // Wait for chart data completion
    const chartData = await chartDataPromise
    
    // Get final 24-hour totals and check for errors in parallel (these should be mostly cached from chart generation)
    const [itemsMetrics24h, scoreResultsMetrics24h, hasErrorsLast24h, totalErrors24h] = await Promise.all([
      getAggregatedMetrics(accountId, 'items', last24Hours, now),
      getAggregatedMetrics(accountId, 'scoreResults', last24Hours, now),
      checkForErrorsLast24h(accountId),
      countErrorsLast24h(accountId)
    ]);
    
    console.log('🎯 Final hasErrorsLast24h value:', hasErrorsLast24h);
    
    // Calculate derived metrics
    const { itemsAverage, scoreResultsAverage } = calculateAverageValues(chartData);
    const { itemsPeak, scoreResultsPeak } = calculatePeakValues(chartData);
    
    const result: MetricsData = {
      itemsPerHour,
      scoreResultsPerHour,
      itemsTotal24h: itemsMetrics24h.count,
      scoreResultsTotal24h: scoreResultsMetrics24h.count,
      itemsAveragePerHour: itemsAverage,
      scoreResultsAveragePerHour: scoreResultsAverage,
      itemsPeakHourly: itemsPeak,
      scoreResultsPeakHourly: scoreResultsPeak,
      chartData,
      lastUpdated: now,
      // New comprehensive metrics
      totalCost24h: scoreResultsMetrics24h.cost || 0,
      totalDecisions24h: scoreResultsMetrics24h.decisionCount || 0,
      totalExternalApiCalls24h: scoreResultsMetrics24h.externalAiApiCount || 0,
      totalCachedApiCalls24h: scoreResultsMetrics24h.cachedAiApiCount || 0,
      totalErrors24h: totalErrors24h,
      costPerHour,
      // Error detection for dashboard alerts
      hasErrorsLast24h,
    };
    
    console.log('🎯 Final metrics result hasErrorsLast24h:', result.hasErrorsLast24h);
    return result;
  } catch (error) {
    console.error('❌ Error in client-side metrics calculation:', error);
    throw error;
  }
}

export function useItemsMetrics(): UseItemsMetricsResult {
  const [metrics, setMetrics] = useState<MetricsData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { selectedAccount } = useAccount()

  const fetchMetrics = useCallback(async () => {
    if (!selectedAccount) {
      setMetrics(null)
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const finalMetrics = await calculateMetrics(
        selectedAccount.id,
        (partialMetrics) => {
          // Progressive update: merge partial metrics with existing data
          setMetrics(prevMetrics => {
            const newMetrics = {
              ...prevMetrics,
              ...partialMetrics
            } as MetricsData
            
            return newMetrics
          })
          
          // Set loading to false as soon as we have any meaningful data
          // This allows the component to show and update progressively
          if (partialMetrics.itemsPerHour !== undefined || partialMetrics.scoreResultsPerHour !== undefined) {
            setIsLoading(false)
          }
        }
      )
      
      // Ensure final metrics (including hasErrorsLast24h) are set
      console.log('🔥 Setting final metrics with hasErrorsLast24h:', finalMetrics.hasErrorsLast24h)
      setMetrics(finalMetrics)
      setIsLoading(false)

    } catch (err) {
      console.error('❌ useItemsMetrics: Error calculating metrics:', err)
      setError(err instanceof Error ? err.message : 'Failed to calculate metrics using client-side aggregation')
      setIsLoading(false)
    }
  }, [selectedAccount])

  const refetch = useCallback(() => {
    // Clear existing metrics to force fresh calculation and show loading spinner
    setMetrics(null)
    setIsLoading(true)
    fetchMetrics()
  }, [fetchMetrics])

  // Lightweight refresh for hourly metrics (gauges)
  const refreshHourlyMetrics = useCallback(async () => {
    if (!selectedAccount || !metrics) return;

    const now = new Date();
    const nowAligned = new Date(now);
    nowAligned.setSeconds(0, 0);
    const currentHourMinutes = nowAligned.getMinutes();
    const windowMinutes = 60 + currentHourMinutes;
    const lastHour = new Date(nowAligned.getTime() - windowMinutes * 60 * 1000);

    try {
      const [itemsMetricsLastHour, scoreResultsMetricsLastHour] = await Promise.all([
        getAggregatedMetrics(selectedAccount.id, 'items', lastHour, now),
        getAggregatedMetrics(selectedAccount.id, 'scoreResults', lastHour, now)
      ]);

      const actualWindowMinutes = (now.getTime() - lastHour.getTime()) / (60 * 1000);
      const normalizationFactor = actualWindowMinutes > 0 ? 60 / actualWindowMinutes : 1;
      
      const itemsPerHour = Math.round(itemsMetricsLastHour.count * normalizationFactor);
      const scoreResultsPerHour = Math.round(scoreResultsMetricsLastHour.count * normalizationFactor);
      const costPerHour = (scoreResultsMetricsLastHour.cost || 0) * normalizationFactor;

      setMetrics(prevMetrics => {
        if (!prevMetrics) return null
        
        // Preserve existing chart data, totals, averages, peaks
        // Only update the rolling 60-min window metrics for a smooth refresh
        return {
          ...prevMetrics,
          itemsPerHour,
          scoreResultsPerHour,
          costPerHour,
          lastUpdated: now,
        }
      })
    } catch (error) {
      console.error('Error during silent refresh of hourly metrics:', error);
      // Don't set a global error state for silent refresh failures
    }
  }, [selectedAccount, metrics]);

  useEffect(() => {
    fetchMetrics()
  }, [fetchMetrics])

  // Set up auto-refresh interval for hourly metrics
  useEffect(() => {
    const intervalId = setInterval(() => {
      refreshHourlyMetrics()
    }, 30000) // Refresh every 30 seconds

    return () => clearInterval(intervalId)
  }, [refreshHourlyMetrics])

  return {
    metrics,
    isLoading,
    error,
    refetch
  }
}