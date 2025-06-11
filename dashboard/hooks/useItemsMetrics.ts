import { useState, useEffect, useCallback, useRef } from 'react'
import { useAccount } from '@/app/contexts/AccountContext'
import { getAggregatedMetrics, AggregatedMetricsData } from '@/utils/metricsAggregator'
import { generateChartData, calculatePeakValues, calculateAverageValues, ChartDataPoint } from '@/utils/chartDataGenerator'

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
}

interface UseItemsMetricsResult {
  metrics: MetricsData | null
  isLoading: boolean
  error: string | null
  refetch: () => void
}

/**
 * Calculate a weighted average estimate for the current hour based on:
 * - Most recent completed hour bucket (full weight)
 * - Current incomplete hour bucket (weighted by completion percentage)
 */
async function calculateWeightedHourlyEstimate(
  accountId: string,
  recordType: 'items' | 'scoreResults'
): Promise<{ count: number; cost?: number }> {
  const now = new Date();
  
  // Current hour boundaries
  const currentHourStart = new Date(now);
  currentHourStart.setMinutes(0, 0, 0);
  const currentHourEnd = new Date(currentHourStart.getTime() + 60 * 60 * 1000);
  
  // Previous hour boundaries (most recent completed hour)
  const previousHourStart = new Date(currentHourStart.getTime() - 60 * 60 * 1000);
  const previousHourEnd = new Date(currentHourStart);
  
  // Calculate how much of the current hour is complete (0.0 to 1.0)
  const currentHourProgress = (now.getTime() - currentHourStart.getTime()) / (60 * 60 * 1000);
  
  try {
    // Get both buckets in parallel
    const [currentHourMetrics, previousHourMetrics] = await Promise.all([
      getAggregatedMetrics(accountId, recordType, currentHourStart, now),
      getAggregatedMetrics(accountId, recordType, previousHourStart, previousHourEnd)
    ]);
    
    // If we have no data from either bucket, return zero
    if (currentHourMetrics.count === 0 && previousHourMetrics.count === 0) {
      return { count: 0, cost: 0 };
    }
    
    // If current hour is very early (< 5% complete), just use previous hour
    if (currentHourProgress < 0.05) {
      return {
        count: previousHourMetrics.count,
        cost: previousHourMetrics.cost || 0
      };
    }
    
    // Project current hour's partial data to a full hour estimate
    // Example: if 30 minutes into hour with 10 items, project to 20 items for full hour
    const currentHourProjected = currentHourProgress > 0 ? currentHourMetrics.count / currentHourProgress : 0;
    const currentHourCostProjected = currentHourProgress > 0 ? (currentHourMetrics.cost || 0) / currentHourProgress : 0;
    
    // Weight the estimates based on time completion:
    // - At 0% complete: 100% previous hour, 0% current projection
    // - At 50% complete: 50% previous hour, 50% current projection  
    // - At 100% complete: 0% previous hour, 100% current projection
    const previousWeight = 1 - currentHourProgress;
    const currentWeight = currentHourProgress;
    
    const weightedCount = (previousHourMetrics.count * previousWeight) + (currentHourProjected * currentWeight);
    const weightedCost = ((previousHourMetrics.cost || 0) * previousWeight) + (currentHourCostProjected * currentWeight);
    
    return {
      count: Math.round(weightedCount),
      cost: Math.round(weightedCost)
    };
    
  } catch (error) {
    console.error(`❌ Error calculating weighted estimate for ${recordType}:`, error);
    // Fallback to current hour only
    const currentHourMetrics = await getAggregatedMetrics(accountId, recordType, currentHourStart, now);
    return {
      count: currentHourMetrics.count,
      cost: currentHourMetrics.cost || 0
    };
  }
}

/**
 * Calculate comprehensive metrics for items and score results
 * Implements parallel loading: weighted hourly estimates (for immediate gauge display) and 24-hour data (for charts)
 * Uses bucket-level synchronization to avoid duplicate computation while allowing parallel processing
 */
async function calculateMetrics(
  accountId: string, 
  onProgressUpdate?: (partialMetrics: Partial<MetricsData>) => void
): Promise<MetricsData> {
  const now = new Date();
  const last24Hours = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  
  // BACKGROUND: Calculate the full rolling 60-minute window (the "correct" approach)
  const rollingLastHour = new Date(now.getTime() - 60 * 60 * 1000);
  
  try {
    // PHASE 1: Get weighted hourly estimates for immediate display
    const immediateMetricsPromise = Promise.all([
      calculateWeightedHourlyEstimate(accountId, 'items'),
      calculateWeightedHourlyEstimate(accountId, 'scoreResults')
    ]).then(([itemsEstimate, scoreResultsEstimate]) => {
      // FIRST PROGRESS UPDATE: Send weighted estimates for immediate display
      if (onProgressUpdate && (itemsEstimate.count > 0 || scoreResultsEstimate.count > 0)) {
        onProgressUpdate({
          itemsPerHour: itemsEstimate.count,
          scoreResultsPerHour: scoreResultsEstimate.count,
          costPerHour: scoreResultsEstimate.cost || 0,
          lastUpdated: now
        })
      }
      return { itemsEstimate, scoreResultsEstimate }
    })

    // PHASE 2: Start background calculation of full rolling 60-minute window
    const fullRollingMetricsPromise = Promise.all([
      getAggregatedMetrics(accountId, 'items', rollingLastHour, now),
      getAggregatedMetrics(accountId, 'scoreResults', rollingLastHour, now)
    ]).then(([itemsMetricsRolling, scoreResultsMetricsRolling]) => {
      // SECOND PROGRESS UPDATE: Send the "correct" rolling window data
      // This replaces the immediate data with the full 60-minute calculation
      if (onProgressUpdate) {
        onProgressUpdate({
          itemsPerHour: itemsMetricsRolling.count,
          scoreResultsPerHour: scoreResultsMetricsRolling.count,
          costPerHour: scoreResultsMetricsRolling.cost || 0,
          lastUpdated: now
        })
      }
      return { itemsMetricsRolling, scoreResultsMetricsRolling }
    })

    // PHASE 3: Start chart data generation in parallel
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

    // Wait for immediate data first (should be fastest - weighted estimates)
    const { itemsEstimate, scoreResultsEstimate } = await immediateMetricsPromise
    
    // Wait for full rolling window calculation (more accurate but slower)
    const { itemsMetricsRolling, scoreResultsMetricsRolling } = await fullRollingMetricsPromise
    
    // Wait for chart data completion
    const chartData = await chartDataPromise
    
    // Get final 24-hour totals (these should be mostly cached from chart generation)
    const [itemsMetrics24h, scoreResultsMetrics24h] = await Promise.all([
      getAggregatedMetrics(accountId, 'items', last24Hours, now),
      getAggregatedMetrics(accountId, 'scoreResults', last24Hours, now)
    ]);
    
    // Calculate derived metrics
    const { itemsAverage, scoreResultsAverage } = calculateAverageValues(chartData);
    const { itemsPeak, scoreResultsPeak } = calculatePeakValues(chartData);
    
    const result: MetricsData = {
      // Use the full rolling window data for final result (most accurate)
      itemsPerHour: itemsMetricsRolling.count,
      scoreResultsPerHour: scoreResultsMetricsRolling.count,
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
      totalErrors24h: scoreResultsMetrics24h.errorCount || 0,
      costPerHour: scoreResultsMetricsRolling.cost || 0,
    };
    
    return result;
  } catch (error) {
    console.error('❌ Error in client-side metrics calculation:', error);
    throw error;
  }
}

// Helper function to add timeout to async operations
function withTimeout<T>(promise: Promise<T>, timeoutMs: number, operation: string): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) => 
      setTimeout(() => reject(new Error(`${operation} timed out after ${timeoutMs}ms`)), timeoutMs)
    )
  ])
}

export function useItemsMetrics(): UseItemsMetricsResult {
  const [metrics, setMetrics] = useState<MetricsData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { selectedAccount } = useAccount()
  
  // Ref to store the latest refresh function to avoid stale closures
  const refreshHourlyMetricsRef = useRef<(() => Promise<void>) | null>(null)

  const fetchMetrics = useCallback(async (isRefresh = false) => {
    if (!selectedAccount) {
      setMetrics(null)
      setIsLoading(false)
      return
    }

    // Only show loading if we don't have any metrics yet AND this is not a refresh
    if (!metrics && !isRefresh) {
      setIsLoading(true)
    }
    setError(null)

    try {
      await calculateMetrics(
        selectedAccount.id,
        (partialMetrics) => {
          // Progressive update: merge partial metrics with existing data
          setMetrics(prevMetrics => ({
            ...prevMetrics,
            ...partialMetrics
          } as MetricsData))
          
          // CRITICAL: Only set loading to false when we have meaningful non-zero data
          // This prevents showing zeros and ensures we display real activity
          if (partialMetrics.itemsPerHour !== undefined && partialMetrics.scoreResultsPerHour !== undefined) {
            // Only stop loading if we have at least some non-zero data OR if this is the final complete result
            const hasNonZeroData = partialMetrics.itemsPerHour > 0 || partialMetrics.scoreResultsPerHour > 0
            const hasChartData = partialMetrics.chartData && partialMetrics.chartData.length > 0
            
            // Stop loading if we have non-zero hourly data OR if we have complete chart data (final result)
            if (hasNonZeroData || hasChartData) {
              setIsLoading(false)
            }
          }
        }
      )
      
      // Final result is already set through progressive updates
      // No need to overwrite - the last progressive update contains the complete data

    } catch (err) {
      console.error('❌ useItemsMetrics: Error calculating metrics:', err)
      setError(err instanceof Error ? err.message : 'Failed to calculate metrics using client-side aggregation')
      setIsLoading(false)
    }
  }, [selectedAccount, metrics])

  // Lightweight refresh that updates rolling window AND incomplete cache buckets
  const refreshHourlyMetrics = useCallback(async () => {
    console.log('🔄 refreshHourlyMetrics called', { 
      hasSelectedAccount: !!selectedAccount, 
      hasMetrics: !!metrics,
      accountId: selectedAccount?.id 
    })
    
    if (!selectedAccount || !metrics) {
      console.log('⏭️ Skipping refresh - missing selectedAccount or metrics')
      return
    }

    const now = new Date()
    const rollingLastHour = new Date(now.getTime() - 60 * 60 * 1000)

    console.log('🚀 Starting refresh phases...')
    try {
      // PHASE 1: Update incomplete cache buckets for current time ranges FIRST
      // This ensures that current hour buckets get refreshed with new data
      const currentHourStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), 0, 0, 0)
      const currentHourEnd = new Date(currentHourStart.getTime() + 60 * 60 * 1000)
      
      console.log('📊 Phase 1: Refreshing current hour buckets...')
      // Force refresh of current hour bucket (this will update incomplete cache entries)
      const phase1CurrentHourStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), 0, 0, 0)
      const phase1CurrentHourEnd = new Date(phase1CurrentHourStart.getTime() + 60 * 60 * 1000)
      await Promise.all([
        getAggregatedMetrics(selectedAccount.id, 'items', phase1CurrentHourStart, phase1CurrentHourEnd),
        getAggregatedMetrics(selectedAccount.id, 'scoreResults', phase1CurrentHourStart, phase1CurrentHourEnd)
      ])
      console.log('✅ Phase 1 complete')

      console.log('📊 Phase 2: Getting rolling window metrics...')
      // PHASE 2: Calculate rolling window that matches chart data logic
      // Get current hour (calendar-aligned) and previous hour data
      const phase2CurrentHourStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), 0, 0, 0)
      const phase2CurrentHourEnd = new Date(phase2CurrentHourStart.getTime() + 60 * 60 * 1000)
      const phase2PreviousHourStart = new Date(phase2CurrentHourStart.getTime() - 60 * 60 * 1000)
      const phase2PreviousHourEnd = phase2CurrentHourStart
      
      // Calculate how much of the current hour is complete
      const currentHourProgress = (now.getTime() - phase2CurrentHourStart.getTime()) / (60 * 60 * 1000)
      
      const [currentHourItems, currentHourScoreResults, previousHourItems, previousHourScoreResults] = await Promise.all([
        getAggregatedMetrics(selectedAccount.id, 'items', phase2CurrentHourStart, now),
        getAggregatedMetrics(selectedAccount.id, 'scoreResults', phase2CurrentHourStart, now),
        getAggregatedMetrics(selectedAccount.id, 'items', phase2PreviousHourStart, phase2PreviousHourEnd),
        getAggregatedMetrics(selectedAccount.id, 'scoreResults', phase2PreviousHourStart, phase2PreviousHourEnd)
      ])
      
      // Calculate rolling window: current hour data + portion of previous hour
      // If 45 minutes into current hour, include 15 minutes from previous hour
      const previousHourPortion = 1 - currentHourProgress
      const rollingItems = currentHourItems.count + Math.round(previousHourItems.count * previousHourPortion)
      const rollingScoreResults = currentHourScoreResults.count + Math.round(previousHourScoreResults.count * previousHourPortion)
      const rollingCost = (currentHourScoreResults.cost || 0) + Math.round((previousHourScoreResults.cost || 0) * previousHourPortion)
      
      console.log('✅ Phase 2 complete', {
        currentHourProgress: Math.round(currentHourProgress * 100) + '%',
        currentHourItems: currentHourItems.count,
        previousHourItems: previousHourItems.count,
        previousHourPortion: Math.round(previousHourPortion * 100) + '%',
        rollingItems,
        rollingScoreResults
      })

      console.log('📊 Phase 3: Skipping 24-hour totals (use existing values to avoid timeout)')
      // SKIP Phase 3: The 24-hour metrics are consistently timing out
      // We'll keep the existing 24-hour totals and only update the rolling window metrics
      // This allows the gauges to update properly without being blocked by slow 24-hour queries

      // Update hourly metrics AND 24-hour totals, preserving everything else
      console.log('📊 Phase 4: Updating metrics state...')
      setMetrics(prevMetrics => {
        if (!prevMetrics) return prevMetrics
        
        const updated = {
          ...prevMetrics,
          // Update rolling window metrics (gauges)
          itemsPerHour: rollingItems,
          scoreResultsPerHour: rollingScoreResults,
          costPerHour: rollingCost,
          lastUpdated: now
          // Keep 24-hour totals unchanged (to avoid timeout issues)
          // Keep other metrics unchanged (chartData, averages, peaks)
        }
        
        console.log('✅ Refresh complete - updated metrics', {
          itemsPerHour: updated.itemsPerHour,
          scoreResultsPerHour: updated.scoreResultsPerHour,
          itemsTotal24h: updated.itemsTotal24h,
          scoreResultsTotal24h: updated.scoreResultsTotal24h,
          lastUpdated: updated.lastUpdated,
          lastUpdatedISO: updated.lastUpdated.toISOString(),
          previousLastUpdated: prevMetrics?.lastUpdated?.toISOString()
        })
        
        return updated
      })

    } catch (err) {
      console.error('❌ Error refreshing hourly metrics:', err)
      console.error('❌ Error details:', {
        message: err instanceof Error ? err.message : String(err),
        stack: err instanceof Error ? err.stack : undefined,
        selectedAccountId: selectedAccount?.id,
        hasMetrics: !!metrics
      })
    }
  }, [selectedAccount, metrics])
  
  // Update the ref whenever the function changes
  refreshHourlyMetricsRef.current = refreshHourlyMetrics

  const refetch = useCallback(() => {
    // Clear existing metrics to force fresh calculation
    setMetrics(null)
    fetchMetrics()
  }, [fetchMetrics])

  // Initial fetch when account changes
  useEffect(() => {
    fetchMetrics()
  }, [selectedAccount])

  // Automatic refresh every 15 seconds to pick up new data and update incomplete buckets
  useEffect(() => {
    if (!selectedAccount) return

    console.log('🔄 Setting up 15-second auto-refresh interval')
    const interval = setInterval(() => {
      console.log('⏰ 15-second refresh triggered at', new Date().toISOString())
      // Use ref to call the latest version of refreshHourlyMetrics
      if (refreshHourlyMetricsRef.current) {
        refreshHourlyMetricsRef.current()
      } else {
        console.warn('⚠️ refreshHourlyMetricsRef.current is null')
      }
    }, 15000) // 15 seconds

    return () => {
      console.log('🛑 Clearing auto-refresh interval')
      clearInterval(interval)
    }
  }, [selectedAccount]) // Only depend on selectedAccount to prevent interval reset

  return {
    metrics,
    isLoading,
    error,
    refetch
  }
}