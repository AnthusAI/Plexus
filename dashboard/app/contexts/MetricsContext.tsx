"use client"

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react'
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
  chartData: Array<{ 
    time: string; 
    items: number; 
    scoreResults: number; 
    bucketStart: string; 
    bucketEnd: string 
  }>
  lastUpdated: Date
}

interface MetricsContextType {
  // Current metrics data (null when no data available)
  metrics: MetricsData | null
  
  // Loading states
  isInitialLoading: boolean  // True only on first load
  isRefreshing: boolean      // True during background refreshes
  
  // Error state
  error: string | null
  
  // Manual refresh function
  refetch: () => void
  
  // Helper to check if data exists (for progressive disclosure)
  hasData: boolean
}

const MetricsContext = createContext<MetricsContextType | undefined>(undefined)

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

async function fetchMetricsFromAPI(accountId: string): Promise<MetricsData> {
  console.log('📊 MetricsContext: Fetching metrics for account:', accountId);
  
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
    console.log('📊 MetricsContext: API response received');
    
    if (response.data?.getItemsMetrics) {
      const metricsResponse: ItemsMetricsResponse = response.data.getItemsMetrics;
      
      // Transform the response to match the expected UI format
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
        chartData: combinedChartData,
        lastUpdated: new Date(metricsResponse.timestamp)
      };
    } else {
      // Check for GraphQL errors
      if (response.errors) {
        console.error('📊 MetricsContext: GraphQL errors:', response.errors);
        throw new Error(response.errors.map((e: any) => e.message).join(', '));
      }
      throw new Error('Failed to get metrics from API.');
    }
  } catch (error) {
    console.error('📊 MetricsContext: Error fetching metrics:', error);
    const e = error as Error;
    throw new Error(`Failed to fetch metrics: ${e.message}`);
  }
}

export function MetricsProvider({ children }: { children: React.ReactNode }) {
  const [metrics, setMetrics] = useState<MetricsData | null>(null)
  const [isInitialLoading, setIsInitialLoading] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { selectedAccount } = useAccount()
  
  // Ref to track the auto-refresh interval
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const lastAccountIdRef = useRef<string | null>(null)

  const fetchMetrics = useCallback(async (isBackgroundRefresh = false) => {
    if (!selectedAccount) {
      console.log('📊 MetricsContext: No selected account, clearing metrics')
      setMetrics(null)
      setIsInitialLoading(false)
      setIsRefreshing(false)
      return
    }

    console.log('📊 MetricsContext: Fetching metrics...', { 
      isBackgroundRefresh, 
      hasExistingData: !!metrics,
      accountId: selectedAccount.id 
    })
    
    // Set appropriate loading state
    if (!metrics && !isBackgroundRefresh) {
      setIsInitialLoading(true)
    } else if (isBackgroundRefresh) {
      setIsRefreshing(true)
    }
    
    // Clear error on new fetch
    setError(null)

    try {
      const metricsData = await fetchMetricsFromAPI(selectedAccount.id)
      
      console.log('📊 MetricsContext: Successfully fetched metrics', {
        hasData: !!(metricsData.itemsPerHour || metricsData.scoreResultsPerHour),
        lastUpdated: metricsData.lastUpdated
      })
      
      setMetrics(metricsData)

    } catch (err) {
      console.error('📊 MetricsContext: Error fetching metrics:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch metrics')
      
      // On error, don't clear existing data - keep showing previous values
      if (!metrics) {
        setMetrics(null)
      }
    } finally {
      setIsInitialLoading(false)
      setIsRefreshing(false)
    }
  }, [selectedAccount, metrics])

  const refetch = useCallback(() => {
    fetchMetrics(false) // Manual refetch is not a background refresh
  }, [fetchMetrics])

  // Initial fetch when account changes
  useEffect(() => {
    const currentAccountId = selectedAccount?.id || null
    const accountChanged = lastAccountIdRef.current !== currentAccountId
    lastAccountIdRef.current = currentAccountId
    
    if (accountChanged) {
      // Clear existing data when account changes
      setMetrics(null)
      setError(null)
      
      // Clear any existing interval
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
        refreshIntervalRef.current = null
      }
      
      if (selectedAccount) {
        console.log('📊 MetricsContext: Account changed, fetching initial data')
        fetchMetrics(false)
      }
    }
  }, [selectedAccount, fetchMetrics])

  // Set up auto-refresh interval (every minute) when we have data
  useEffect(() => {
    if (metrics && selectedAccount) {
      console.log('📊 MetricsContext: Setting up auto-refresh interval')
      
      // Clear any existing interval
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
      }
      
      // Set up new interval for background refresh every minute
      refreshIntervalRef.current = setInterval(() => {
        console.log('📊 MetricsContext: Auto-refreshing metrics...')
        fetchMetrics(true) // Background refresh
      }, 60000) // 60 seconds = 1 minute
      
      return () => {
        if (refreshIntervalRef.current) {
          clearInterval(refreshIntervalRef.current)
          refreshIntervalRef.current = null
        }
      }
    }
  }, [metrics, selectedAccount, fetchMetrics])

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
      }
    }
  }, [])

  const hasData = !!(metrics && (
    metrics.itemsPerHour > 0 || 
    metrics.scoreResultsPerHour > 0 ||
    metrics.itemsTotal24h > 0 ||
    metrics.scoreResultsTotal24h > 0
  ))

  return (
    <MetricsContext.Provider value={{
      metrics,
      isInitialLoading,
      isRefreshing,
      error,
      refetch,
      hasData
    }}>
      {children}
    </MetricsContext.Provider>
  )
}

export function useMetrics() {
  const context = useContext(MetricsContext)
  if (context === undefined) {
    throw new Error('useMetrics must be used within a MetricsProvider')
  }
  return context
}