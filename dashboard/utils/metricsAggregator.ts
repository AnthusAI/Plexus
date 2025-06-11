import { graphqlRequest } from './amplify-client'

// Types matching our AggregatedMetrics model
export interface AggregatedMetricsData {
  count: number
  cost?: number
  decisionCount?: number
  externalAiApiCount?: number
  cachedAiApiCount?: number
  errorCount?: number
}

export interface CachedAggregation extends AggregatedMetricsData {
  id: string
  accountId: string
  scorecardId?: string
  scoreId?: string
  recordType: string
  timeRangeStart: string
  timeRangeEnd: string
  numberOfMinutes: number
  complete: boolean
  createdAt: string
  updatedAt: string
}

export type RecordType = 'items' | 'scoreResults'

// In-memory synchronization for bucket computation
// Prevents duplicate computation of the same bucket across parallel requests
const bucketComputationLocks = new Map<string, Promise<AggregatedMetricsData>>()

function getBucketLockKey(
  accountId: string,
  recordType: RecordType,
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string
): string {
  const key = `${accountId}:${recordType}:${startTime.toISOString()}:${endTime.toISOString()}`
  if (scoreId) return `${key}:score:${scoreId}`
  if (scorecardId) return `${key}:scorecard:${scorecardId}`
  return key
}

// Time bucket alignment functions
export function isHourAligned(date: Date): boolean {
  return date.getMinutes() === 0 && date.getSeconds() === 0 && date.getMilliseconds() === 0
}

export function is30MinuteAligned(date: Date): boolean {
  return date.getMinutes() % 30 === 0 && date.getSeconds() === 0 && date.getMilliseconds() === 0
}

export function is15MinuteAligned(date: Date): boolean {
  return date.getMinutes() % 15 === 0 && date.getSeconds() === 0 && date.getMilliseconds() === 0
}

export function is5MinuteAligned(date: Date): boolean {
  return date.getMinutes() % 5 === 0 && date.getSeconds() === 0 && date.getMilliseconds() === 0
}

export function alignToHour(date: Date): Date {
  const aligned = new Date(date)
  aligned.setMinutes(0, 0, 0)
  return aligned
}

export function alignTo30Minutes(date: Date): Date {
  const aligned = new Date(date)
  aligned.setMinutes(Math.floor(aligned.getMinutes() / 30) * 30, 0, 0)
  return aligned
}

export function alignTo15Minutes(date: Date): Date {
  const aligned = new Date(date)
  aligned.setMinutes(Math.floor(aligned.getMinutes() / 15) * 15, 0, 0)
  return aligned
}

export function alignTo5Minutes(date: Date): Date {
  const aligned = new Date(date)
  aligned.setMinutes(Math.floor(aligned.getMinutes() / 5) * 5, 0, 0)
  return aligned
}

export function alignToMinute(date: Date): Date {
  const aligned = new Date(date)
  aligned.setSeconds(0, 0)
  return aligned
}

// Cache lookup functions
export async function getCachedAggregation(
  accountId: string,
  recordType: RecordType,
  startTime: Date,
  endTime: Date,
  numberOfMinutes: number,
  scorecardId?: string,
  scoreId?: string
): Promise<CachedAggregation | null> {
  // Align the start time to the appropriate boundary for consistent cache keys
  let alignedStartTime: Date
  switch (numberOfMinutes) {
    case 60:
      alignedStartTime = alignToHour(startTime)
      break
    case 30:
      alignedStartTime = alignTo30Minutes(startTime)
      break
    case 15:
      alignedStartTime = alignTo15Minutes(startTime)
      break
    case 5:
      alignedStartTime = alignTo5Minutes(startTime)
      break
    case 1:
    default:
      alignedStartTime = alignToMinute(startTime)
      break
  }

  const startTimeStr = alignedStartTime.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' })

  try {
    // Choose the appropriate GSI based on segmentation
    let query: string
    let variables: any

    if (scoreId) {
      // Use the working GSI with score filter
      query = /* GraphQL */ `
        query GetCachedAggregationByScore(
          $recordType: String!
          $timeRangeStart: String!
          $scoreId: String!
          $numberOfMinutes: Int!
        ) {
          listAggregatedMetricsByRecordTypeAndTimeRangeStart(
            recordType: $recordType
            timeRangeStart: { eq: $timeRangeStart }
            filter: {
              scoreId: { eq: $scoreId }
              numberOfMinutes: { eq: $numberOfMinutes }
              complete: { eq: true }
            }
          ) {
            items {
              id
              accountId
              scorecardId
              scoreId
              recordType
              timeRangeStart
              timeRangeEnd
              numberOfMinutes
              count
              cost
              decisionCount
              externalAiApiCount
              cachedAiApiCount
              errorCount
              complete
              createdAt
              updatedAt
            }
          }
        }
      `
      variables = {
        recordType,
        timeRangeStart: alignedStartTime.toISOString(),
        scoreId,
        numberOfMinutes
      }
    } else if (scorecardId) {
      // Use the working GSI with scorecard filter
      query = /* GraphQL */ `
        query GetCachedAggregationByScorecard(
          $recordType: String!
          $timeRangeStart: String!
          $scorecardId: String!
          $numberOfMinutes: Int!
        ) {
          listAggregatedMetricsByRecordTypeAndTimeRangeStart(
            recordType: $recordType
            timeRangeStart: { eq: $timeRangeStart }
            filter: {
              scorecardId: { eq: $scorecardId }
              numberOfMinutes: { eq: $numberOfMinutes }
              complete: { eq: true }
            }
          ) {
            items {
              id
              accountId
              scorecardId
              scoreId
              recordType
              timeRangeStart
              timeRangeEnd
              numberOfMinutes
              count
              cost
              decisionCount
              externalAiApiCount
              cachedAiApiCount
              errorCount
              complete
              createdAt
              updatedAt
            }
          }
        }
      `
      variables = {
        recordType,
        timeRangeStart: alignedStartTime.toISOString(),
        scorecardId,
        numberOfMinutes
      }
    } else {
      // Use the working GSI: byRecordTypeAndTime
      query = /* GraphQL */ `
        query GetCachedAggregationByRecordType(
          $recordType: String!
          $timeRangeStart: String!
          $accountId: String!
          $numberOfMinutes: Int!
        ) {
          listAggregatedMetricsByRecordTypeAndTimeRangeStart(
            recordType: $recordType
            timeRangeStart: { eq: $timeRangeStart }
            filter: {
              accountId: { eq: $accountId }
              numberOfMinutes: { eq: $numberOfMinutes }
              complete: { eq: true }
            }
          ) {
            items {
              id
              accountId
              scorecardId
              scoreId
              recordType
              timeRangeStart
              timeRangeEnd
              numberOfMinutes
              count
              cost
              decisionCount
              externalAiApiCount
              cachedAiApiCount
              errorCount
              complete
              createdAt
              updatedAt
            }
          }
        }
      `
      variables = {
        recordType,
        timeRangeStart: alignedStartTime.toISOString(),
        accountId,
        numberOfMinutes
      }
    }

    const response = await graphqlRequest(query, variables)
    
    // All queries now use the same GSI
    const items = (response.data as any)?.listAggregatedMetricsByRecordTypeAndTimeRangeStart?.items || []
    
    if (items.length > 0) {
      return items[0]
    }

    return null
  } catch (error) {
    console.error('❌ Error looking up cached aggregation:', error)
    return null
  }
}

// Helper function to get existing aggregation (complete or incomplete)
async function getExistingAggregation(
  accountId: string,
  recordType: RecordType,
  startTime: Date,
  endTime: Date,
  numberOfMinutes: number,
  scorecardId?: string,
  scoreId?: string
): Promise<CachedAggregation | null> {
  try {
    // Choose the appropriate GSI based on segmentation
    let query: string
    let variables: any

    if (scoreId) {
      query = /* GraphQL */ `
        query GetExistingAggregationByScore(
          $recordType: String!
          $timeRangeStart: String!
          $scoreId: String!
          $numberOfMinutes: Int!
        ) {
          listAggregatedMetricsByRecordTypeAndTimeRangeStart(
            recordType: $recordType
            timeRangeStart: { eq: $timeRangeStart }
            filter: {
              scoreId: { eq: $scoreId }
              numberOfMinutes: { eq: $numberOfMinutes }
            }
          ) {
            items {
              id
              accountId
              scorecardId
              scoreId
              recordType
              timeRangeStart
              timeRangeEnd
              numberOfMinutes
              count
              cost
              decisionCount
              externalAiApiCount
              cachedAiApiCount
              errorCount
              complete
              createdAt
              updatedAt
            }
          }
        }
      `
      variables = {
        recordType,
        timeRangeStart: startTime.toISOString(),
        scoreId,
        numberOfMinutes
      }
    } else if (scorecardId) {
      query = /* GraphQL */ `
        query GetExistingAggregationByScorecard(
          $recordType: String!
          $timeRangeStart: String!
          $scorecardId: String!
          $numberOfMinutes: Int!
        ) {
          listAggregatedMetricsByRecordTypeAndTimeRangeStart(
            recordType: $recordType
            timeRangeStart: { eq: $timeRangeStart }
            filter: {
              scorecardId: { eq: $scorecardId }
              numberOfMinutes: { eq: $numberOfMinutes }
            }
          ) {
            items {
              id
              accountId
              scorecardId
              scoreId
              recordType
              timeRangeStart
              timeRangeEnd
              numberOfMinutes
              count
              cost
              decisionCount
              externalAiApiCount
              cachedAiApiCount
              errorCount
              complete
              createdAt
              updatedAt
            }
          }
        }
      `
      variables = {
        recordType,
        timeRangeStart: startTime.toISOString(),
        scorecardId,
        numberOfMinutes
      }
    } else {
      query = /* GraphQL */ `
        query GetExistingAggregationByRecordType(
          $recordType: String!
          $timeRangeStart: String!
          $accountId: String!
          $numberOfMinutes: Int!
        ) {
          listAggregatedMetricsByRecordTypeAndTimeRangeStart(
            recordType: $recordType
            timeRangeStart: { eq: $timeRangeStart }
            filter: {
              accountId: { eq: $accountId }
              numberOfMinutes: { eq: $numberOfMinutes }
            }
          ) {
            items {
              id
              accountId
              scorecardId
              scoreId
              recordType
              timeRangeStart
              timeRangeEnd
              numberOfMinutes
              count
              cost
              decisionCount
              externalAiApiCount
              cachedAiApiCount
              errorCount
              complete
              createdAt
              updatedAt
            }
          }
        }
      `
      variables = {
        recordType,
        timeRangeStart: startTime.toISOString(),
        accountId,
        numberOfMinutes
      }
    }

    const response = await graphqlRequest(query, variables)
    const items = (response.data as any)?.listAggregatedMetricsByRecordTypeAndTimeRangeStart?.items || []
    
    if (items.length > 0) {
      return items[0]
    }

    return null
  } catch (error) {
    console.error('❌ Error looking up existing aggregation:', error)
    return null
  }
}

// Cache storage function with upsert logic
export async function cacheAggregationResult(
  accountId: string,
  recordType: RecordType,
  startTime: Date,
  endTime: Date,
  numberOfMinutes: number,
  metrics: AggregatedMetricsData,
  scorecardId?: string,
  scoreId?: string
): Promise<void> {
  // Align the start time to the appropriate boundary for consistent cache keys
  let alignedStartTime: Date
  switch (numberOfMinutes) {
    case 60:
      alignedStartTime = alignToHour(startTime)
      break
    case 30:
      alignedStartTime = alignTo30Minutes(startTime)
      break
    case 15:
      alignedStartTime = alignTo15Minutes(startTime)
      break
    case 5:
      alignedStartTime = alignTo5Minutes(startTime)
      break
    case 1:
    default:
      alignedStartTime = alignToMinute(startTime)
      break
  }

  // Determine if this time bucket is complete
  // A bucket is complete if its end time is in the past
  const now = new Date()
  const isComplete = endTime <= now

  try {
    // First, check if there's an existing record (complete or incomplete)
    const existingRecord = await getExistingAggregation(
      accountId, recordType, alignedStartTime, endTime, numberOfMinutes, scorecardId, scoreId
    )

    if (existingRecord) {
      // Update existing record
      const updateMutation = /* GraphQL */ `
        mutation UpdateAggregatedMetrics($input: UpdateAggregatedMetricsInput!) {
          updateAggregatedMetrics(input: $input) {
            id
            accountId
            scorecardId
            scoreId
            recordType
            timeRangeStart
            timeRangeEnd
            numberOfMinutes
            count
            cost
            decisionCount
            externalAiApiCount
            cachedAiApiCount
            errorCount
            complete
            createdAt
            updatedAt
          }
        }
      `

      const updateInput = {
        id: existingRecord.id,
        count: metrics.count,
        cost: metrics.cost,
        decisionCount: metrics.decisionCount,
        externalAiApiCount: metrics.externalAiApiCount,
        cachedAiApiCount: metrics.cachedAiApiCount,
        errorCount: metrics.errorCount,
        complete: isComplete
      }

      await graphqlRequest(updateMutation, { input: updateInput })
    } else {
      // Create new record
      const createMutation = /* GraphQL */ `
        mutation CreateAggregatedMetrics($input: CreateAggregatedMetricsInput!) {
          createAggregatedMetrics(input: $input) {
            id
            accountId
            scorecardId
            scoreId
            recordType
            timeRangeStart
            timeRangeEnd
            numberOfMinutes
            count
            cost
            decisionCount
            externalAiApiCount
            cachedAiApiCount
            errorCount
            complete
            createdAt
            updatedAt
          }
        }
      `

      const createInput = {
        accountId,
        scorecardId,
        scoreId,
        recordType,
        timeRangeStart: alignedStartTime.toISOString(),
        timeRangeEnd: endTime.toISOString(),
        numberOfMinutes,
        count: metrics.count,
        cost: metrics.cost,
        decisionCount: metrics.decisionCount,
        externalAiApiCount: metrics.externalAiApiCount,
        cachedAiApiCount: metrics.cachedAiApiCount,
        errorCount: metrics.errorCount,
        complete: isComplete
      }

      await graphqlRequest(createMutation, { input: createInput })
    }
  } catch (error) {
    console.error('❌ Error caching aggregation result:', error)
    // Don't throw - caching failures shouldn't break the main flow
  }
}

// Helper function to determine bucket type
function getBucketType(numberOfMinutes: number): string {
  switch (numberOfMinutes) {
    case 1: return 'minute'
    case 5: return '5-minute'
    case 15: return '15-minute'
    case 30: return '30-minute'
    case 60: return 'hour'
    default: return 'custom'
  }
}

// JIT aggregation functions
export async function performJITAggregation(
  accountId: string,
  recordType: RecordType,
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string
): Promise<AggregatedMetricsData> {
  // Check for bucket-level synchronization to prevent duplicate computation
  const lockKey = getBucketLockKey(accountId, recordType, startTime, endTime, scorecardId, scoreId)
  
  // If another request is already computing this exact bucket, wait for it
  if (bucketComputationLocks.has(lockKey)) {
    return await bucketComputationLocks.get(lockKey)!
  }
  
  // Create a promise for this computation and store it in the lock map
  const computationPromise = (async (): Promise<AggregatedMetricsData> => {
    try {
      const durationMinutes = Math.round((endTime.getTime() - startTime.getTime()) / (1000 * 60))
      
      // For large time ranges, use hierarchical aggregation with caching at each level
      if (durationMinutes > 15) {
        return await performHierarchicalAggregation(accountId, recordType, startTime, endTime, scorecardId, scoreId)
      }
      
      // For small ranges, do direct aggregation
      if (recordType === 'items') {
        return await aggregateItemMetrics(accountId, startTime, endTime, scorecardId, scoreId)
      } else {
        return await aggregateScoreResultMetrics(accountId, startTime, endTime, scorecardId, scoreId)
      }
    } finally {
      // Always clean up the lock when computation is complete
      bucketComputationLocks.delete(lockKey)
    }
  })()
  
  // Store the promise in the lock map
  bucketComputationLocks.set(lockKey, computationPromise)
  
  return await computationPromise
}

// Hierarchical aggregation that caches intermediate results
async function performHierarchicalAggregation(
  accountId: string,
  recordType: RecordType,
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string
): Promise<AggregatedMetricsData> {
  const durationMinutes = Math.round((endTime.getTime() - startTime.getTime()) / (1000 * 60))
  
  // Determine the next level down in the hierarchy
  let subBucketMinutes: number
  if (durationMinutes >= 60) {
    subBucketMinutes = 30 // Break 60+ minute buckets into 30-minute sub-buckets
  } else if (durationMinutes >= 30) {
    subBucketMinutes = 15 // Break 30+ minute buckets into 15-minute sub-buckets
  } else if (durationMinutes >= 15) {
    subBucketMinutes = 5  // Break 15+ minute buckets into 5-minute sub-buckets
  } else if (durationMinutes >= 5) {
    subBucketMinutes = 1  // Break 5+ minute buckets into 1-minute sub-buckets
  } else {
    // For buckets smaller than 5 minutes, do direct aggregation
    if (recordType === 'items') {
      return await aggregateItemMetrics(accountId, startTime, endTime, scorecardId, scoreId)
    } else {
      return await aggregateScoreResultMetrics(accountId, startTime, endTime, scorecardId, scoreId)
    }
  }
  
  let totalMetrics: AggregatedMetricsData = { count: 0 }
  let currentTime = new Date(startTime)
  let cachedSubBuckets = 0
  let computedSubBuckets = 0
  
  while (currentTime < endTime) {
    const subBucketEnd = new Date(Math.min(
      currentTime.getTime() + subBucketMinutes * 60 * 1000,
      endTime.getTime()
    ))
    
    // Try to get cached result for this sub-bucket
    const cachedResult = await getCachedAggregation(
      accountId, recordType, currentTime, subBucketEnd, subBucketMinutes, scorecardId, scoreId
    )
    
    let subBucketMetrics: AggregatedMetricsData
    
    if (cachedResult) {
      cachedSubBuckets++
      subBucketMetrics = {
        count: cachedResult.count,
        cost: cachedResult.cost || 0,
        decisionCount: cachedResult.decisionCount || 0,
        externalAiApiCount: cachedResult.externalAiApiCount || 0,
        cachedAiApiCount: cachedResult.cachedAiApiCount || 0,
        errorCount: cachedResult.errorCount || 0
      }
    } else {
      computedSubBuckets++
      
      // Recursively compute this sub-bucket (will continue down the hierarchy)
      subBucketMetrics = await performHierarchicalAggregation(
        accountId, recordType, currentTime, subBucketEnd, scorecardId, scoreId
      )
      
      // Cache this sub-bucket result
      await cacheAggregationResult(
        accountId, recordType, currentTime, subBucketEnd, subBucketMinutes, subBucketMetrics, scorecardId, scoreId
      )
    }
    
    // Aggregate the sub-bucket metrics
    totalMetrics.count += subBucketMetrics.count
    totalMetrics.cost = (totalMetrics.cost || 0) + (subBucketMetrics.cost || 0)
    totalMetrics.decisionCount = (totalMetrics.decisionCount || 0) + (subBucketMetrics.decisionCount || 0)
    totalMetrics.externalAiApiCount = (totalMetrics.externalAiApiCount || 0) + (subBucketMetrics.externalAiApiCount || 0)
    totalMetrics.cachedAiApiCount = (totalMetrics.cachedAiApiCount || 0) + (subBucketMetrics.cachedAiApiCount || 0)
    totalMetrics.errorCount = (totalMetrics.errorCount || 0) + (subBucketMetrics.errorCount || 0)
    
    currentTime = subBucketEnd
  }
  
  return totalMetrics
}

async function aggregateItemMetrics(
  accountId: string,
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string
): Promise<AggregatedMetricsData> {
  
  try {
    // For account-level queries, use the optimized GSI
    if (!scorecardId && !scoreId) {
      const query = /* GraphQL */ `
        query ListItemByAccountIdAndCreatedAt(
          $accountId: String!
          $startTime: String!
          $endTime: String!
          $limit: Int
        ) {
          listItemByAccountIdAndCreatedAt(
            accountId: $accountId
            createdAt: { between: [$startTime, $endTime] }
            limit: $limit
          ) {
            items {
              id
              createdAt
            }
            nextToken
          }
        }
      `
      
      const variables: any = { 
        accountId, 
        startTime: startTime.toISOString(), 
        endTime: endTime.toISOString(),
        limit: 1000
      }

      let totalCount = 0
      let nextToken: string | null = null
      let pageCount = 0
      let allItems: any[] = []
      const maxPages = 100 // Reasonable limit for small time buckets

      do {
        const currentVariables: any = { ...variables }
        if (nextToken) {
          currentVariables.nextToken = nextToken
        }

        const response = await graphqlRequest(query, currentVariables)
        const items = (response.data as any)?.listItemByAccountIdAndCreatedAt?.items || []
        allItems.push(...items)
        totalCount += items.length
        pageCount++

        nextToken = (response.data as any)?.listItemByAccountIdAndCreatedAt?.nextToken
        
        // Break if we've processed too many pages (shouldn't happen for small time buckets)
        if (pageCount >= maxPages) {
          console.warn(`Reached maximum page limit (${maxPages}) while counting items. Partial count: ${totalCount}`)
          break
        }
      } while (nextToken)

      // Debug: Show sample timestamps to verify filtering
      if (allItems.length > 0) {
        // Check for items outside the time range
        const outsideRange = allItems.filter(item => {
          const itemTime = new Date(item.createdAt)
          return itemTime < startTime || itemTime > endTime
        })
        if (outsideRange.length > 0) {
          console.warn(`   ⚠️ ITEMS: Found ${outsideRange.length} items outside time range!`)
          console.warn(`   ⚠️ ITEMS: Sample out-of-range timestamps:`, outsideRange.slice(0, 3).map(item => item.createdAt))
        }
      }

      return { count: totalCount }
    }

    // For scorecard/score-specific queries, fall back to basic queries
    // TODO: Implement GSI queries for scorecard/score segmentation if needed
    let query: string
    let variables: any

    if (scoreId) {
      query = /* GraphQL */ `
        query GetItemsByScore(
          $scoreId: String!
          $startTime: String!
          $endTime: String!
        ) {
          listItems(
            filter: {
              scoreId: { eq: $scoreId }
              createdAt: { between: [$startTime, $endTime] }
            }
          ) {
            items {
              id
              createdAt
            }
          }
        }
      `
      variables = { scoreId, startTime: startTime.toISOString(), endTime: endTime.toISOString() }
    } else if (scorecardId) {
      // For scorecard-level, we need to get items through score results
      query = /* GraphQL */ `
        query GetItemsByScorecard(
          $scorecardId: String!
          $startTime: String!
          $endTime: String!
        ) {
          listScoreResults(
            filter: {
              scorecardId: { eq: $scorecardId }
              createdAt: { between: [$startTime, $endTime] }
            }
          ) {
            items {
              itemId
              createdAt
            }
          }
        }
      `
      variables = { scorecardId, startTime: startTime.toISOString(), endTime: endTime.toISOString() }
    } else {
      // This shouldn't happen since we handle account-level queries above
      throw new Error('Invalid query parameters: no scoreId or scorecardId provided')
    }

    const response = await graphqlRequest(query, variables)
    
    let count = 0
    if (scorecardId && !scoreId) {
      // For scorecard queries, count unique items from score results
      const uniqueItemIds = new Set((response.data as any)?.listScoreResults?.items?.map((sr: any) => sr.itemId) || [])
      count = uniqueItemIds.size
    } else {
      count = (response.data as any)?.listItems?.items?.length || 0
    }

    return { count }
  } catch (error) {
    console.error('❌ Error aggregating item metrics:', error)
    return { count: 0 }
  }
}

async function aggregateScoreResultMetrics(
  accountId: string,
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string
): Promise<AggregatedMetricsData> {
  
  try {
    // For account-level queries, use the optimized GSI
    if (!scorecardId && !scoreId) {
      const query = /* GraphQL */ `
        query ListScoreResultByAccountIdAndUpdatedAt(
          $accountId: String!
          $startTime: String!
          $endTime: String!
          $limit: Int
        ) {
          listScoreResultByAccountIdAndUpdatedAt(
            accountId: $accountId
            updatedAt: { between: [$startTime, $endTime] }
            limit: $limit
          ) {
            items {
              id
              cost
              updatedAt
            }
            nextToken
          }
        }
      `
      
      const variables: any = { 
        accountId, 
        startTime: startTime.toISOString(), 
        endTime: endTime.toISOString(),
        limit: 1000
      }

      let allScoreResults: any[] = []
      let nextToken: string | null = null
      let pageCount = 0
      const maxPages = 100 // Reasonable limit for small time buckets

      do {
        const currentVariables: any = { ...variables }
        if (nextToken) {
          currentVariables.nextToken = nextToken
        }

        const response = await graphqlRequest(query, currentVariables)
        const scoreResults = (response.data as any)?.listScoreResultByAccountIdAndUpdatedAt?.items || []
        allScoreResults.push(...scoreResults)
        pageCount++

        nextToken = (response.data as any)?.listScoreResultByAccountIdAndUpdatedAt?.nextToken
        
        // Break if we've processed too many pages (shouldn't happen for small time buckets)
        if (pageCount >= maxPages) {
          console.warn(`Reached maximum page limit (${maxPages}) while counting score results. Partial count: ${allScoreResults.length}`)
          break
        }
      } while (nextToken)

      let metrics: AggregatedMetricsData = { count: allScoreResults.length }

      // Debug: Show sample timestamps to verify filtering
      if (allScoreResults.length > 0) {
        // Check for results outside the time range
        const outsideRange = allScoreResults.filter(result => {
          const resultTime = new Date(result.updatedAt)
          return resultTime < startTime || resultTime > endTime
        })
        if (outsideRange.length > 0) {
          console.warn(`   ⚠️ SCORERESULTS: Found ${outsideRange.length} results outside time range!`)
          console.warn(`   ⚠️ SCORERESULTS: Sample out-of-range timestamps:`, outsideRange.slice(0, 3).map(result => result.updatedAt))
        }
      }

      // Aggregate metrics from score results
      for (const result of allScoreResults) {
        if (result.cost) {
          // Assuming cost is stored as JSON with structure like { totalCost: number, apiCalls: number }
          const costData = typeof result.cost === 'string' ? JSON.parse(result.cost) : result.cost
          metrics.cost = (metrics.cost || 0) + (costData.totalCost || 0)
          metrics.externalAiApiCount = (metrics.externalAiApiCount || 0) + (costData.apiCalls || 0)
        }
        // Additional metric calculations can be added here based on ScoreResult data structure
      }

      return metrics
    }

    // For scorecard/score-specific queries, fall back to basic queries
    // TODO: Implement GSI queries for scorecard/score segmentation if needed
    let query: string
    let variables: any

    if (scoreId) {
      query = /* GraphQL */ `
        query GetScoreResultsByScore(
          $scoreId: String!
          $startTime: String!
          $endTime: String!
        ) {
          listScoreResults(
            filter: {
              scoreId: { eq: $scoreId }
              createdAt: { between: [$startTime, $endTime] }
            }
          ) {
            items {
              id
              cost
              createdAt
            }
          }
        }
      `
      variables = { scoreId, startTime: startTime.toISOString(), endTime: endTime.toISOString() }
    } else if (scorecardId) {
      query = /* GraphQL */ `
        query GetScoreResultsByScorecard(
          $scorecardId: String!
          $startTime: String!
          $endTime: String!
        ) {
          listScoreResults(
            filter: {
              scorecardId: { eq: $scorecardId }
              createdAt: { between: [$startTime, $endTime] }
            }
          ) {
            items {
              id
              cost
              createdAt
            }
          }
        }
      `
      variables = { scorecardId, startTime: startTime.toISOString(), endTime: endTime.toISOString() }
    } else {
      // This shouldn't happen since we handle account-level queries above
      throw new Error('Invalid query parameters: no scoreId or scorecardId provided')
    }

    const response = await graphqlRequest(query, variables)
    const scoreResults = (response.data as any)?.listScoreResults?.items || []

    let metrics: AggregatedMetricsData = { count: scoreResults.length }

    // Aggregate metrics from score results
    for (const result of scoreResults) {
      if (result.cost) {
        // Assuming cost is stored as JSON with structure like { totalCost: number, apiCalls: number }
        const costData = typeof result.cost === 'string' ? JSON.parse(result.cost) : result.cost
        metrics.cost = (metrics.cost || 0) + (costData.totalCost || 0)
        metrics.externalAiApiCount = (metrics.externalAiApiCount || 0) + (costData.apiCalls || 0)
      }
      // Additional metric calculations can be added here based on ScoreResult data structure
    }

    return metrics
  } catch (error) {
    console.error('❌ Error aggregating score result metrics:', error)
    return { count: 0 }
  }
}

// Main aggregation function implementing hierarchical time bucket strategy
export async function getAggregatedMetrics(
  accountId: string,
  recordType: RecordType,
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string,
  onProgress?: (progress: { 
    bucketStart: Date, 
    bucketEnd: Date, 
    bucketMetrics: AggregatedMetricsData, 
    totalMetrics: AggregatedMetricsData,
    bucketNumber: number,
    totalBuckets: number
  }) => void
): Promise<AggregatedMetricsData> {
  const totalDurationMinutes = Math.round((endTime.getTime() - startTime.getTime()) / (1000 * 60))

  let totalMetrics: AggregatedMetricsData = { count: 0 }
  let bucketNumber = 1
  let currentTime = new Date(startTime)

  // Generate optimal buckets that cover the entire time range
  const buckets = generateOptimalBuckets(startTime, endTime)

  for (const bucket of buckets) {
    const bucketStartTime = bucket.start.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' })
    const bucketEndTime = bucket.end.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' })
    
    // First, try to get a complete cached result
    const cachedResult = await getCachedAggregation(
      accountId, recordType, bucket.start, bucket.end, bucket.minutes, scorecardId, scoreId
    )

    let bucketMetrics: AggregatedMetricsData
    let cacheStatus = ''

    if (cachedResult) {
      cacheStatus = '💾'
      bucketMetrics = {
        count: cachedResult.count,
        cost: cachedResult.cost || 0,
        decisionCount: cachedResult.decisionCount || 0,
        externalAiApiCount: cachedResult.externalAiApiCount || 0,
        cachedAiApiCount: cachedResult.cachedAiApiCount || 0,
        errorCount: cachedResult.errorCount || 0
      }
    } else {
      // No complete cache found - compute the bucket
      cacheStatus = '🔄' // Computing bucket
      
      bucketMetrics = await performJITAggregation(
        accountId, recordType, bucket.start, bucket.end, scorecardId, scoreId
      )

      await cacheAggregationResult(
        accountId, recordType, bucket.start, bucket.end, bucket.minutes, bucketMetrics, scorecardId, scoreId
      )
    }

    // Aggregate metrics
    totalMetrics.count += bucketMetrics.count
    totalMetrics.cost = (totalMetrics.cost || 0) + (bucketMetrics.cost || 0)
    totalMetrics.decisionCount = (totalMetrics.decisionCount || 0) + (bucketMetrics.decisionCount || 0)
    totalMetrics.externalAiApiCount = (totalMetrics.externalAiApiCount || 0) + (bucketMetrics.externalAiApiCount || 0)
    totalMetrics.cachedAiApiCount = (totalMetrics.cachedAiApiCount || 0) + (bucketMetrics.cachedAiApiCount || 0)
    totalMetrics.errorCount = (totalMetrics.errorCount || 0) + (bucketMetrics.errorCount || 0)

    // Call progress callback for real-time UI updates
    if (onProgress) {
      onProgress({
        bucketStart: bucket.start,
        bucketEnd: bucket.end,
        bucketMetrics,
        totalMetrics: { ...totalMetrics },
        bucketNumber,
        totalBuckets: buckets.length
      })
    }

    bucketNumber++
  }

  return totalMetrics
}

// Generate optimal time buckets that efficiently cover the entire time range
function generateOptimalBuckets(startTime: Date, endTime: Date): Array<{start: Date, end: Date, minutes: number}> {
  const buckets: Array<{start: Date, end: Date, minutes: number}> = []
  let currentTime = new Date(startTime)

  while (currentTime < endTime) {
    const remainingMs = endTime.getTime() - currentTime.getTime()
    const remainingMinutes = remainingMs / (1000 * 60)

    let bucketMinutes: number
    let bucketEnd: Date

    // Choose the largest bucket that fits and is aligned
    if (remainingMinutes >= 60 && isHourAligned(currentTime)) {
      bucketMinutes = 60
      bucketEnd = new Date(currentTime.getTime() + 60 * 60 * 1000)
    } else if (remainingMinutes >= 30 && is30MinuteAligned(currentTime)) {
      bucketMinutes = 30
      bucketEnd = new Date(currentTime.getTime() + 30 * 60 * 1000)
    } else if (remainingMinutes >= 15 && is15MinuteAligned(currentTime)) {
      bucketMinutes = 15
      bucketEnd = new Date(currentTime.getTime() + 15 * 60 * 1000)
    } else if (remainingMinutes >= 5 && is5MinuteAligned(currentTime)) {
      bucketMinutes = 5
      bucketEnd = new Date(currentTime.getTime() + 5 * 60 * 1000)
    } else {
      // For the final partial bucket or small segments, use 1-minute buckets
      bucketMinutes = Math.min(Math.ceil(remainingMinutes), 1)
      bucketEnd = new Date(Math.min(currentTime.getTime() + bucketMinutes * 60 * 1000, endTime.getTime()))
    }

    // Don't exceed the end time
    if (bucketEnd > endTime) {
      bucketEnd = new Date(endTime)
      bucketMinutes = Math.ceil((bucketEnd.getTime() - currentTime.getTime()) / (1000 * 60))
    }

    buckets.push({
      start: new Date(currentTime),
      end: new Date(bucketEnd),
      minutes: bucketMinutes
    })

    currentTime = bucketEnd
  }

  return buckets
}

 