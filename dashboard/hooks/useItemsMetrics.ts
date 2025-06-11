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

// GraphQL response type matching the schema
interface ItemsMetricsResponse {
  accountId: string;
  hours: number;
  timestamp: string;
  totalItems: number;
  itemsLast24Hours: number;
  itemsLastHour: number;
  itemsHourlyBreakdown: any;
  totalScoreResults: number;
  scoreResultsLast24Hours: number;
  scoreResultsLastHour: number;
  scoreResultsHourlyBreakdown: any;
}

async function invokeLambdaFunction(accountId: string): Promise<MetricsData> {
  console.log('Invoking getItemsMetrics GraphQL query for account:', accountId);
  const query = /* GraphQL */ `
    query GetItemsMetrics($accountId: String!, $hours: Int) {
      getItemsMetrics(accountId: $accountId, hours: $hours) {
        accountId
        hours
        timestamp
        totalItems
        itemsLast24Hours
        itemsLastHour
        itemsHourlyBreakdown
        totalScoreResults
        scoreResultsLast24Hours
        scoreResultsLastHour
        scoreResultsHourlyBreakdown
      }
    }
  `;
  
  const variables = {
    accountId: accountId,
    hours: 24
  };

  try {
    const response: any = await graphqlRequest(query, variables);
    console.log('Received response from getItemsMetrics query:', response);
    
    if (response.data?.getItemsMetrics) {
      const metricsResponse: ItemsMetricsResponse = response.data.getItemsMetrics;
      
      // Transform the response to match the expected UI format
      // Parse JSON strings if they come as strings
      const itemsChartData = typeof metricsResponse.itemsHourlyBreakdown === 'string' 
        ? JSON.parse(metricsResponse.itemsHourlyBreakdown) 
        : (metricsResponse.itemsHourlyBreakdown || []);
      const scoreResultsChartData = typeof metricsResponse.scoreResultsHourlyBreakdown === 'string'
        ? JSON.parse(metricsResponse.scoreResultsHourlyBreakdown)
        : (metricsResponse.scoreResultsHourlyBreakdown || []);
      
      // Calculate averages and peaks from chart data
      const itemsValues = itemsChartData.map((d: any) => d.items || 0);
      const scoreResultsValues = scoreResultsChartData.map((d: any) => d.scoreResults || 0);
      
      const itemsAveragePerHour = itemsValues.length > 0 ? itemsValues.reduce((a: number, b: number) => a + b, 0) / itemsValues.length : 0;
      const scoreResultsAveragePerHour = scoreResultsValues.length > 0 ? scoreResultsValues.reduce((a: number, b: number) => a + b, 0) / scoreResultsValues.length : 0;
      const itemsPeakHourly = itemsValues.length > 0 ? Math.max(...itemsValues) : 0;
      const scoreResultsPeakHourly = scoreResultsValues.length > 0 ? Math.max(...scoreResultsValues) : 0;
      
      // Combine chart data from both sources
      const combinedChartData = itemsChartData.map((itemData: any, index: number) => {
        const scoreData = scoreResultsChartData[index] || {};
        return {
          time: itemData.time || itemData.bucketStart || '',
          items: itemData.items || 0,
          scoreResults: scoreData.scoreResults || 0,
          bucketStart: itemData.bucketStart || '',
          bucketEnd: itemData.bucketEnd || ''
        };
      });
      
      return {
        scoreResultsPerHour: metricsResponse.scoreResultsLastHour,
        itemsPerHour: metricsResponse.itemsLastHour,
        scoreResultsAveragePerHour,
        itemsAveragePerHour,
        itemsPeakHourly,
        scoreResultsPeakHourly,
        itemsTotal24h: metricsResponse.itemsLast24Hours,
        scoreResultsTotal24h: metricsResponse.scoreResultsLast24Hours,
        chartData: combinedChartData
      };
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