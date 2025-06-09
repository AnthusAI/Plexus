import { useState, useEffect, useCallback } from 'react'
import { useAccount } from '@/app/contexts/AccountContext'

interface MetricsData {
  scoreResultsPerHour: number
  itemsPerHour: number
  scoreResultsAveragePerHour: number
  itemsAveragePerHour: number
  itemsPeakHourly: number
  scoreResultsPeakHourly: number
  itemsTotal24h: number
  scoreResultsTotal24h: number
  chartData: Array<{ time: string; items: number; scoreResults: number; bucketStart: string; bucketEnd: string }>
}

interface UseItemsMetricsLambdaResult {
  metrics: MetricsData | null
  isLoading: boolean
  error: string | null
  refetch: () => void
}

async function invokeLambdaFunction(accountId: string): Promise<MetricsData> {
  // For now, this is a placeholder that would call your Lambda function
  // You would replace this with actual Lambda invocation code
  
  // Simulate API call delay
  await new Promise(resolve => setTimeout(resolve, 1000))
  
  // Return mock data for testing
  return {
    scoreResultsPerHour: 42,
    itemsPerHour: 18,
    scoreResultsAveragePerHour: 35,
    itemsAveragePerHour: 15,
    itemsPeakHourly: 60,
    scoreResultsPeakHourly: 120,
    itemsTotal24h: 360,
    scoreResultsTotal24h: 840,
    chartData: [
      { time: '00:00', items: 10, scoreResults: 15, bucketStart: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 23 * 60 * 60 * 1000).toISOString() },
      { time: '04:00', items: 8, scoreResults: 12, bucketStart: new Date(Date.now() - 20 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 19 * 60 * 60 * 1000).toISOString() },
      { time: '08:00', items: 25, scoreResults: 38, bucketStart: new Date(Date.now() - 16 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 15 * 60 * 60 * 1000).toISOString() },
      { time: '12:00', items: 30, scoreResults: 45, bucketStart: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 11 * 60 * 60 * 1000).toISOString() },
      { time: '16:00', items: 28, scoreResults: 42, bucketStart: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString() },
      { time: '20:00', items: 15, scoreResults: 22, bucketStart: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString() },
    ]
  }
}

export function useItemsMetricsLambda(): UseItemsMetricsLambdaResult {
  const [metrics, setMetrics] = useState<MetricsData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { selectedAccount } = useAccount()

  const fetchMetrics = useCallback(async () => {
    console.log('🔍 useItemsMetricsLambda: Starting fetchMetrics')
    
    if (!selectedAccount) {
      console.log('❌ useItemsMetricsLambda: No selected account, clearing metrics')
      setMetrics(null)
      setIsLoading(false)
      return
    }

    console.log('✅ useItemsMetricsLambda: Selected account:', selectedAccount)
    
    if (!metrics) {
      setIsLoading(true)
    }
    setError(null)

    try {
      console.log('🚀 useItemsMetricsLambda: Invoking Lambda function...')
      
      const metricsData = await invokeLambdaFunction(selectedAccount.id)
      
      console.log('✅ useItemsMetricsLambda: Lambda function returned metrics:', {
        ...metricsData,
        chartDataLength: metricsData.chartData?.length || 0
      })
      
      setMetrics(metricsData)

    } catch (err) {
      console.error('❌ useItemsMetricsLambda: Error fetching metrics:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch metrics from Lambda function')
    } finally {
      setIsLoading(false)
    }
  }, [selectedAccount, metrics])

  const refetch = useCallback(() => {
    fetchMetrics()
  }, [fetchMetrics])

  useEffect(() => {
    fetchMetrics()
  }, [selectedAccount])

  return {
    metrics,
    isLoading,
    error,
    refetch
  }
} 