/**
 * Metrics Aggregation System
 * 
 * This module provides a simplified interface to the hierarchical aggregation engine
 * for both items and score result metrics. It maintains backward compatibility while using the
 * new tested and reliable aggregation logic.
 */

import { hierarchicalAggregator, AggregationRequest, AggregationBucket } from './hierarchicalAggregator';

// Legacy types for backward compatibility
export interface AggregatedMetricsData {
  count: number
  cost?: number
  decisionCount?: number
  externalAiApiCount?: number
  cachedAiApiCount?: number
  errorCount?: number
}

export type RecordType = 'items' | 'scoreResults'

/**
 * Align a date to the nearest hour boundary (for backward compatibility)
 */
export function alignToHour(date: Date): Date {
  const aligned = new Date(date)
  aligned.setMinutes(0, 0, 0)
  return aligned
}

/**
 * Get aggregated metrics using the new hierarchical aggregation engine
 */
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
  
  // Calculate the interval in minutes
  const intervalMs = endTime.getTime() - startTime.getTime();
  const intervalMinutes = Math.round(intervalMs / (1000 * 60));

  // Create aggregation request
  const request: AggregationRequest = {
    accountId,
    recordType, // Pass the record type to the hierarchical aggregator
    startTime: startTime.toISOString(),
    endTime: endTime.toISOString(),
    intervalMinutes,
    ...(scorecardId && { scorecardId }),
    ...(scoreId && { scoreId })
  };

  try {
    // Use the hierarchical aggregator
    const bucket = await hierarchicalAggregator.getAggregatedMetrics(request);
    
    // Convert to legacy format
    const result: AggregatedMetricsData = {
      count: bucket.count,
      cost: 0, // Not calculated in new system yet
      decisionCount: 0, // Not calculated in new system yet
      externalAiApiCount: 0, // Not calculated in new system yet
      cachedAiApiCount: 0, // Not calculated in new system yet
      errorCount: 0 // Not calculated in new system yet
    };

    // Call progress callback if provided
    if (onProgress) {
      onProgress({
        bucketStart: startTime,
        bucketEnd: endTime,
        bucketMetrics: result,
        totalMetrics: result,
        bucketNumber: 1,
        totalBuckets: 1
      });
    }

    return result;
  } catch (error) {
    console.error('Error in getAggregatedMetrics:', error);
    
    // Return empty result on error
    return {
      count: 0,
      cost: 0,
      decisionCount: 0,
      externalAiApiCount: 0,
      cachedAiApiCount: 0,
      errorCount: 0
    };
  }
}

/**
 * Clear the aggregation cache
 */
export function clearAggregationCache(): void {
  hierarchicalAggregator.clearCache();
}

/**
 * Get cache statistics for debugging
 */
export function getCacheStats(): { size: number; keys: string[] } {
  return hierarchicalAggregator.getCacheStats();
}

/**
 * Perform just-in-time aggregation (legacy compatibility)
 */
export async function performJITAggregation(
  accountId: string,
  recordType: RecordType,
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string
): Promise<AggregatedMetricsData> {
  return getAggregatedMetrics(accountId, recordType, startTime, endTime, scorecardId, scoreId);
}

/**
 * Perform hierarchical aggregation (legacy compatibility)
 */
export async function performHierarchicalAggregation(
  accountId: string,
  recordType: RecordType,
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string
): Promise<AggregatedMetricsData> {
  return getAggregatedMetrics(accountId, recordType, startTime, endTime, scorecardId, scoreId);
} 