import { useState, useEffect, useCallback } from 'react'
import { useAccount } from '@/app/contexts/AccountContext'
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
  chartData: Array<{ time: string; items: number; scoreResults: number; bucketStart: string; bucketEnd: string }>
}

interface UseItemsMetricsResult {
  metrics: MetricsData | null
  isLoading: boolean
  error: string | null
  refetch: () => void
}

async function invokeLambdaFunction(accountId: string): Promise<MetricsData> {
  console.log('Invoking getItemsMetrics GraphQL query for account:', accountId);
  const query = /* GraphQL */ `
    query GetItemsMetrics($accountId: String!, $hours: Int, $bucketMinutes: Int) {
      getItemsMetrics(accountId: $accountId, hours: $hours, bucketMinutes: $bucketMinutes)
    }
  `;
  
  const variables = {
    accountId: accountId,
    hours: 24,
    // We get 6 hourly buckets for 24 hours. The chart can decide how to display them.
    // The previous implementation had 24 hourly buckets. Let's ask for 24 buckets of 60 mins.
    bucketMinutes: 60
  };

  try {
    const response: any = await graphqlRequest(query, variables);
    console.log('Received response from getItemsMetrics query:', response);
    
    if (response.data?.getItemsMetrics) {
      // The resolver returns a JSON object which is what we need.
      return response.data.getItemsMetrics;
    } else {
      // Check for GraphQL errors
      if (response.errors) {
        console.error('GraphQL errors:', response.errors);
        throw new Error(response.errors.map((e: any) => e.message).join(', '));
      }
      throw new Error('Failed to get metrics from Lambda via GraphQL.');
    }
  } catch (error) {
    console.error('Error invoking getItemsMetrics query:', error);
    const e = error as Error;
    throw new Error(`Failed to fetch metrics: ${e.message}`);
  }
}

export function useItemsMetrics(): UseItemsMetricsResult {
  const [metrics, setMetrics] = useState<MetricsData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { selectedAccount } = useAccount()

  const fetchMetrics = useCallback(async () => {
    console.log('🔍 useItemsMetrics: Starting fetchMetrics')
    
    if (!selectedAccount) {
      console.log('❌ useItemsMetrics: No selected account, clearing metrics')
      setMetrics(null)
      setIsLoading(false)
      return
    }

    console.log('✅ useItemsMetrics: Selected account:', selectedAccount)
    
    if (!metrics) {
      setIsLoading(true)
    }
    setError(null)

    try {
      console.log('🚀 useItemsMetrics: Invoking Lambda function...')
      
      const metricsData = await invokeLambdaFunction(selectedAccount.id)
      
      console.log('✅ useItemsMetrics: Lambda function returned metrics:', {
        ...metricsData,
        chartDataLength: metricsData.chartData?.length || 0
      })
      
      setMetrics(metricsData)

    } catch (err) {
      console.error('❌ useItemsMetrics: Error fetching metrics:', err)
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