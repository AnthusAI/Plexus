import { useState, useEffect, useCallback } from 'react'
import { useAccount } from '@/app/contexts/AccountContext'
import { getAggregatedMetrics, AggregatedMetricsData } from '@/utils/metricsAggregator'
import { generateChartData, calculatePeakValues, calculateAverageValues, ChartDataPoint } from '@/utils/chartDataGenerator'

interface TypeSpecificMetrics {
  scoreResultsPerHour: number
  scoreResultsTotal24h: number
  scoreResultsAveragePerHour: number
  chartData: ChartDataPoint[]
}

interface MetricsWithTypeData {
  // Overall metrics (all types combined)
  overall: {
    scoreResultsPerHour: number
    itemsPerHour: number
    scoreResultsTotal24h: number
    itemsTotal24h: number
    chartData: ChartDataPoint[]
  }
  // Type-specific breakdowns
  predictions: TypeSpecificMetrics
  evaluations: TypeSpecificMetrics
  lastUpdated: Date
}

interface UseItemsMetricsWithTypeResult {
  metrics: MetricsWithTypeData | null
  isLoading: boolean
  error: string | null
  refetch: () => void
}

/**
 * Enhanced metrics hook that provides both overall and type-specific metrics
 * for showing prediction vs evaluation breakdowns in the dashboard
 */
export function useItemsMetricsWithType(): UseItemsMetricsWithTypeResult {
  const [metrics, setMetrics] = useState<MetricsWithTypeData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { selectedAccount } = useAccount()

  const calculateMetricsWithType = useCallback(async (accountId: string): Promise<MetricsWithTypeData> => {
    const now = new Date()
    const last24Hours = new Date(now.getTime() - 24 * 60 * 60 * 1000)
    
    // Calculate rolling 60-minute window for hourly metrics
    const nowAligned = new Date(now)
    nowAligned.setSeconds(0, 0)
    const currentHourMinutes = nowAligned.getMinutes()
    const windowMinutes = 60 + currentHourMinutes
    const lastHour = new Date(nowAligned.getTime() - windowMinutes * 60 * 1000)

    // Get all metrics in parallel for efficiency
    const [
      // Overall metrics
      itemsMetricsHour,
      scoreResultsMetricsHour,
      itemsMetrics24h,
      scoreResultsMetrics24h,
      overallChartData,
      
      // Prediction metrics
      predictionMetricsHour,
      predictionMetrics24h,
      predictionChartData,
      
      // Evaluation metrics
      evaluationMetricsHour,
      evaluationMetrics24h,
      evaluationChartData
    ] = await Promise.all([
      // Overall metrics
      getAggregatedMetrics(accountId, 'items', lastHour, now),
      getAggregatedMetrics(accountId, 'scoreResults', lastHour, now),
      getAggregatedMetrics(accountId, 'items', last24Hours, now),
      getAggregatedMetrics(accountId, 'scoreResults', last24Hours, now),
      generateChartData(accountId, last24Hours, now),
      
      // Prediction-specific metrics
      getAggregatedMetrics(accountId, 'scoreResults', lastHour, now, undefined, undefined, 'prediction'),
      getAggregatedMetrics(accountId, 'scoreResults', last24Hours, now, undefined, undefined, 'prediction'),
      generateChartData(accountId, last24Hours, now, undefined, undefined, 'prediction'),
      
      // Evaluation-specific metrics
      getAggregatedMetrics(accountId, 'scoreResults', lastHour, now, undefined, undefined, 'evaluation'),
      getAggregatedMetrics(accountId, 'scoreResults', last24Hours, now, undefined, undefined, 'evaluation'),
      generateChartData(accountId, last24Hours, now, undefined, undefined, 'evaluation')
    ])

    // Normalize hourly metrics
    const actualWindowMinutes = (now.getTime() - lastHour.getTime()) / (60 * 1000)
    const normalizationFactor = actualWindowMinutes > 0 ? 60 / actualWindowMinutes : 1

    const result: MetricsWithTypeData = {
      overall: {
        scoreResultsPerHour: Math.round(scoreResultsMetricsHour.count * normalizationFactor),
        itemsPerHour: Math.round(itemsMetricsHour.count * normalizationFactor),
        scoreResultsTotal24h: scoreResultsMetrics24h.count,
        itemsTotal24h: itemsMetrics24h.count,
        chartData: overallChartData
      },
      predictions: {
        scoreResultsPerHour: Math.round(predictionMetricsHour.count * normalizationFactor),
        scoreResultsTotal24h: predictionMetrics24h.count,
        scoreResultsAveragePerHour: Math.round(predictionMetrics24h.count / 24),
        chartData: predictionChartData
      },
      evaluations: {
        scoreResultsPerHour: Math.round(evaluationMetricsHour.count * normalizationFactor),
        scoreResultsTotal24h: evaluationMetrics24h.count,
        scoreResultsAveragePerHour: Math.round(evaluationMetrics24h.count / 24),
        chartData: evaluationChartData
      },
      lastUpdated: now
    }

    return result
  }, [])

  const fetchMetrics = useCallback(async () => {
    if (!selectedAccount) {
      setMetrics(null)
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const result = await calculateMetricsWithType(selectedAccount.id)
      setMetrics(result)
      setIsLoading(false)
    } catch (err) {
      console.error('❌ useItemsMetricsWithType: Error calculating metrics:', err)
      setError(err instanceof Error ? err.message : 'Failed to calculate type-specific metrics')
      setIsLoading(false)
    }
  }, [selectedAccount, calculateMetricsWithType])

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