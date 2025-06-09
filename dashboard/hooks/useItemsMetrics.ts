import { useState, useEffect, useCallback } from 'react'
import { graphqlRequest } from '@/utils/amplify-client'
import { useAccount } from '@/app/contexts/AccountContext'

interface MetricsData {
  scoreResultsPerHour: number
  itemsPerHour: number
  scoreResultsAveragePerHour: number
  itemsAveragePerHour: number
  itemsPeakHourly: number
  scoreResultsPeakHourly: number
  chartData: Array<{ time: string; items: number; scoreResults: number }>
}

interface UseItemsMetricsResult {
  metrics: MetricsData | null
  isLoading: boolean
  error: string | null
  refetch: () => void
}

// Helper function to get hourly time buckets for the last 24 hours
function getHourlyBuckets(): string[] {
  const buckets: string[] = []
  const now = new Date()
  
  for (let i = 23; i >= 0; i--) {
    const hour = new Date(now)
    hour.setHours(hour.getHours() - i, 0, 0, 0)
    buckets.push(hour.toISOString())
  }
  
  return buckets
}

// Helper function to format time for display
function formatTimeForDisplay(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleTimeString('en-US', { 
    hour: '2-digit', 
    minute: '2-digit',
    hour12: false 
  })
}

export function useItemsMetrics(): UseItemsMetricsResult {
  const [metrics, setMetrics] = useState<MetricsData | null>(null)
  const [isLoading, setIsLoading] = useState(true) // Start as loading
  const [error, setError] = useState<string | null>(null)
  const { selectedAccount } = useAccount()

  const fetchMetrics = useCallback(async () => {
    console.log('🔍 useItemsMetrics: Starting fetchMetrics')
    
    if (!selectedAccount) {
      console.log('❌ useItemsMetrics: No selected account, clearing metrics')
      setMetrics(null)
      return
    }

    console.log('✅ useItemsMetrics: Selected account:', selectedAccount)
    // Only show loading initially, keep old data during updates
    if (!metrics) {
      setIsLoading(true)
    }
    setError(null)

    try {
      const oneHourAgo = new Date()
      oneHourAgo.setHours(oneHourAgo.getHours() - 1)
      const oneHourAgoISO = oneHourAgo.toISOString()

      const twentyFourHoursAgo = new Date()
      twentyFourHoursAgo.setHours(twentyFourHoursAgo.getHours() - 24)
      const twentyFourHoursAgoISO = twentyFourHoursAgo.toISOString()

      console.log('📅 useItemsMetrics: Time ranges:', {
        oneHourAgo: oneHourAgoISO,
        twentyFourHoursAgo: twentyFourHoursAgoISO
      })

      console.log('🔄 useItemsMetrics: Starting GraphQL queries...')

      // Helper function to get all paginated results
      const getAllPaginatedResults = async <T>(
        query: string,
        variables: Record<string, any>,
        dataPath: string[]
      ): Promise<T[]> => {
        let allItems: T[] = []
        let nextToken: string | null = null
        let pageCount = 0
        
        do {
          const queryWithPagination: string = query.replace(
            'limit: 10000',
            nextToken ? `limit: 10000, nextToken: "${nextToken}"` : 'limit: 10000'
          )
          
          const response: any = await graphqlRequest<any>(queryWithPagination, variables)
          pageCount++
          
          // Navigate to the correct data path
          let data: any = response.data
          for (const path of dataPath) {
            data = data?.[path]
          }
          
          if (data?.items) {
            allItems = allItems.concat(data.items)
            nextToken = data.nextToken
            console.log(`📄 Page ${pageCount}: Got ${data.items.length} items, nextToken: ${!!nextToken}`)
          } else {
            nextToken = null
          }
        } while (nextToken)
        
        console.log(`✅ Total pages: ${pageCount}, Total items: ${allItems.length}`)
        return allItems
      }

      // Query for items created in the last hour
      console.log('📊 useItemsMetrics: Querying items from last hour with params:', {
        accountId: selectedAccount.id,
        createdAt: oneHourAgoISO
      })
      
      const itemsLastHour = await getAllPaginatedResults<{ id: string; createdAt: string }>(
        `query GetItemsLastHour($accountId: String!, $createdAt: String!) {
          listItemByAccountIdAndCreatedAt(
            accountId: $accountId
            createdAt: { ge: $createdAt }
            sortDirection: DESC
            limit: 10000
          ) {
            items {
              id
              createdAt
            }
            nextToken
          }
        }`,
        {
          accountId: selectedAccount.id,
          createdAt: oneHourAgoISO
        },
        ['listItemByAccountIdAndCreatedAt']
      )

      console.log('📈 useItemsMetrics: Items last hour response:', {
        itemCount: itemsLastHour.length,
        sampleItems: itemsLastHour.slice(0, 3)
      })

      // Query for score results updated in the last hour (using actual GSI query)
      console.log('🎯 useItemsMetrics: Querying score results from last hour with params:', {
        accountId: selectedAccount.id,
        updatedAt: oneHourAgoISO
      })
      
      const scoreResultsLastHour = await getAllPaginatedResults<{ id: string; updatedAt: string; createdAt: string }>(
        `query GetScoreResultsLastHour($accountId: String!, $updatedAt: String!) {
          listScoreResultByAccountIdAndUpdatedAt(
            accountId: $accountId
            updatedAt: { ge: $updatedAt }
            sortDirection: DESC
            limit: 10000
          ) {
            items {
              id
              updatedAt
              createdAt
            }
            nextToken
          }
        }`,
        {
          accountId: selectedAccount.id,
          updatedAt: oneHourAgoISO
        },
        ['listScoreResultByAccountIdAndUpdatedAt']
      )

      console.log('🏆 useItemsMetrics: Score results last hour response:', {
        scoreResultCount: scoreResultsLastHour.length,
        sampleItems: scoreResultsLastHour.slice(0, 3)
      })

      // Query for items created in the last 24 hours for chart data
      console.log('📊 useItemsMetrics: Querying items from last 24 hours with params:', {
        accountId: selectedAccount.id,
        createdAt: twentyFourHoursAgoISO
      })
      
      const itemsLast24Hours = await getAllPaginatedResults<{ id: string; createdAt: string }>(
        `query GetItemsLast24Hours($accountId: String!, $createdAt: String!) {
          listItemByAccountIdAndCreatedAt(
            accountId: $accountId
            createdAt: { ge: $createdAt }
            sortDirection: DESC
            limit: 10000
          ) {
            items {
              id
              createdAt
            }
            nextToken
          }
        }`,
        {
          accountId: selectedAccount.id,
          createdAt: twentyFourHoursAgoISO
        },
        ['listItemByAccountIdAndCreatedAt']
      )

      console.log('📈 useItemsMetrics: Items last 24 hours response:', {
        itemCount: itemsLast24Hours.length,
        sampleItems: itemsLast24Hours.slice(0, 3)
      })

      // Query for score results updated in the last 24 hours for chart data
      console.log('🏆 useItemsMetrics: Querying score results from last 24 hours with params:', {
        accountId: selectedAccount.id,
        updatedAt: twentyFourHoursAgoISO
      })
      
      const scoreResultsLast24Hours = await getAllPaginatedResults<{ id: string; updatedAt: string; createdAt: string }>(
        `query GetScoreResultsLast24Hours($accountId: String!, $updatedAt: String!) {
          listScoreResultByAccountIdAndUpdatedAt(
            accountId: $accountId
            updatedAt: { ge: $updatedAt }
            sortDirection: DESC
            limit: 10000
          ) {
            items {
              id
              updatedAt
              createdAt
            }
            nextToken
          }
        }`,
        {
          accountId: selectedAccount.id,
          updatedAt: twentyFourHoursAgoISO
        },
        ['listScoreResultByAccountIdAndUpdatedAt']
      )

      console.log('🏆 useItemsMetrics: Score results last 24 hours response:', {
        scoreResultCount: scoreResultsLast24Hours.length,
        sampleItems: scoreResultsLast24Hours.slice(0, 3)
      })

      // Calculate metrics - data is now directly from paginated results
      // (itemsLastHour, scoreResultsLastHour, itemsLast24Hours, scoreResultsLast24Hours are already arrays)
      
      console.log('🧮 useItemsMetrics: Extracted data arrays:', {
        itemsLastHour: {
          count: itemsLastHour.length,
          items: itemsLastHour.slice(0, 3) // Show first 3 for debugging
        },
        scoreResultsLastHour: {
          count: scoreResultsLastHour.length,
          items: scoreResultsLastHour.slice(0, 3) // Show first 3 for debugging
        },
        itemsLast24Hours: {
          count: itemsLast24Hours.length,
          items: itemsLast24Hours.slice(0, 3) // Show first 3 for debugging
        },
        scoreResultsLast24Hours: {
          count: scoreResultsLast24Hours.length,
          items: scoreResultsLast24Hours.slice(0, 3) // Show first 3 for debugging
        }
      })

      // Create hourly buckets and count items per hour
      const hourlyBuckets = getHourlyBuckets()
      console.log('📅 useItemsMetrics: Hourly buckets generated:', {
        totalBuckets: hourlyBuckets.length,
        firstBucket: hourlyBuckets[0],
        lastBucket: hourlyBuckets[hourlyBuckets.length - 1],
        allBuckets: hourlyBuckets
      })

      const chartData = hourlyBuckets.map((bucketStart, index) => {
        const bucketEnd = index < hourlyBuckets.length - 1 
          ? hourlyBuckets[index + 1] 
          : new Date().toISOString()

        const itemsInBucket = itemsLast24Hours.filter(item => {
          const itemTime = new Date(item.createdAt).getTime()
          const bucketStartTime = new Date(bucketStart).getTime()
          const bucketEndTime = new Date(bucketEnd).getTime()
          return itemTime >= bucketStartTime && itemTime < bucketEndTime
        })

        const scoreResultsInBucket = scoreResultsLast24Hours.filter(scoreResult => {
          const scoreResultTime = new Date(scoreResult.updatedAt).getTime()
          const bucketStartTime = new Date(bucketStart).getTime()
          const bucketEndTime = new Date(bucketEnd).getTime()
          return scoreResultTime >= bucketStartTime && scoreResultTime < bucketEndTime
        })

        const bucketData = {
          time: formatTimeForDisplay(bucketStart),
          items: itemsInBucket.length,
          scoreResults: scoreResultsInBucket.length
        }

        console.log(`📊 useItemsMetrics: Bucket ${index}:`, {
          bucketStart,
          bucketEnd,
          bucketStartTime: new Date(bucketStart).getTime(),
          bucketEndTime: new Date(bucketEnd).getTime(),
          itemsInBucket: itemsInBucket.length,
          scoreResultsInBucket: scoreResultsInBucket.length,
          formattedTime: bucketData.time,
          sampleItems: itemsInBucket.slice(0, 2).map(item => ({
            id: item.id,
            createdAt: item.createdAt,
            createdAtTime: new Date(item.createdAt).getTime()
          })),
          sampleScoreResults: scoreResultsInBucket.slice(0, 2).map(sr => ({
            id: sr.id,
            updatedAt: sr.updatedAt,
            updatedAtTime: new Date(sr.updatedAt).getTime()
          }))
        })

        return bucketData
      }) // Show all 24 hours

      console.log('📈 useItemsMetrics: Final chart data (last 24 hours):', {
        chartData,
        totalDataPoints: chartData.length,
        totalItems: chartData.reduce((sum, point) => sum + point.items, 0),
        totalScoreResults: chartData.reduce((sum, point) => sum + point.scoreResults, 0),
        detailedChartData: chartData.map((point, index) => ({
          index,
          time: point.time,
          items: point.items,
          scoreResults: point.scoreResults,
          hasActivity: point.items > 0 || point.scoreResults > 0
        }))
      })

      // Calculate 24-hour averages
      const itemsAveragePerHour = Math.round(itemsLast24Hours.length / 24)
      const scoreResultsAveragePerHour = Math.round(scoreResultsLast24Hours.length / 24)

      // Calculate peak hourly rates for dynamic gauge scaling
      const itemsPeakHourly = Math.max(...chartData.map(point => point.items), 1) // Minimum 1 to avoid zero
      const scoreResultsPeakHourly = Math.max(...chartData.map(point => point.scoreResults), 1) // Minimum 1 to avoid zero

      const finalMetrics = {
        scoreResultsPerHour: scoreResultsLastHour.length,
        itemsPerHour: itemsLastHour.length,
        scoreResultsAveragePerHour,
        itemsAveragePerHour,
        itemsPeakHourly,
        scoreResultsPeakHourly,
        chartData
      }
      
      console.log('✅ useItemsMetrics: Final metrics calculated:', {
        ...finalMetrics,
        calculations: {
          itemsLast24HoursTotal: itemsLast24Hours.length,
          scoreResultsLast24HoursTotal: scoreResultsLast24Hours.length,
          itemsAveragePerHour: `${itemsLast24Hours.length} / 24 = ${itemsAveragePerHour}`,
          scoreResultsAveragePerHour: `${scoreResultsLast24Hours.length} / 24 = ${scoreResultsAveragePerHour}`,
          itemsPeakHourly: `Peak items in any hour: ${itemsPeakHourly}`,
          scoreResultsPeakHourly: `Peak score results in any hour: ${scoreResultsPeakHourly}`
        }
      })
      
      setMetrics(finalMetrics)

    } catch (err) {
      console.error('Error fetching items metrics:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch metrics')
    } finally {
      setIsLoading(false)
    }
  }, [selectedAccount])

  const refetch = useCallback(() => {
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