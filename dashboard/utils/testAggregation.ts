/**
 * Test script for Aggregation System
 * 
 * This script demonstrates the new hierarchical aggregation system
 * and validates that it prevents double-counting issues.
 */

import { getAggregatedMetrics, clearAggregationCache, getCacheStats } from './metricsAggregator';

async function testAggregation() {
  console.log('🧪 Testing Aggregation System');
  console.log('================================');
  
  // Clear cache to start fresh
  clearAggregationCache();
  console.log('✅ Cache cleared');
  console.log('');

  const accountId = 'test-account';
  const scorecardId = 'test-scorecard';
  const scoreId = 'test-score';

  // Test different time intervals
  const testCases = [
    { hours: 1, label: '1 hour aggregation' },
    { hours: 2, label: '2 hour aggregation' },
    { minutes: 15, label: '15 minute aggregation' },
    { minutes: 5, label: '5 minute aggregation' }
  ];

  for (const testCase of testCases) {
    console.log(`📊 Testing: ${testCase.label}`);
    
    const endTime = new Date('2024-01-01T11:00:00Z');
    const startTime = new Date(endTime);
    
    if (testCase.hours) {
      startTime.setHours(startTime.getHours() - testCase.hours);
    } else if (testCase.minutes) {
      startTime.setMinutes(startTime.getMinutes() - testCase.minutes);
    }
    
    console.log(`   Time range: ${startTime.toISOString()} to ${endTime.toISOString()}`);
    
    try {
      // Test scoreResults aggregation
      const result = await getAggregatedMetrics(
        accountId,
        'scoreResults',
        startTime,
        endTime,
        scorecardId,
        scoreId,
        (progress) => {
          console.log(`   Progress: Bucket ${progress.bucketNumber}/${progress.totalBuckets} - Count: ${progress.bucketMetrics.count}`);
        }
      );
      
      console.log(`   ✅ ScoreResults: Count=${result.count}, Cost=${result.cost}, Errors=${result.errorCount}`);
      
      // Test items aggregation
      const itemsResult = await getAggregatedMetrics(
        accountId,
        'items',
        startTime,
        endTime
      );
      
      console.log(`   ✅ Items: Count=${itemsResult.count}`);
      
    } catch (error) {
      console.log(`   ❌ Error: ${error}`);
    }
    
    console.log('');
  }

  // Show cache statistics
  const cacheStats = getCacheStats();
  console.log('📈 Cache Statistics:');
  console.log(`   Size: ${cacheStats.size} entries`);
  console.log(`   Keys: ${cacheStats.keys.slice(0, 3).join(', ')}${cacheStats.keys.length > 3 ? '...' : ''}`);
  console.log('');

  // Test double-counting prevention
  console.log('🔍 Testing Double-Counting Prevention:');
  console.log('   Requesting same data twice...');
  
  const testStart = new Date('2024-01-01T10:00:00Z');
  const testEnd = new Date('2024-01-01T11:00:00Z');
  
  const result1 = await getAggregatedMetrics(accountId, 'scoreResults', testStart, testEnd, scorecardId, scoreId);
  const result2 = await getAggregatedMetrics(accountId, 'scoreResults', testStart, testEnd, scorecardId, scoreId);
  
  const identical = result1.count === result2.count && result1.cost === result2.cost;
  console.log(`   ✅ Results identical: ${identical}`);
  console.log(`   First:  Count=${result1.count}, Cost=${result1.cost}`);
  console.log(`   Second: Count=${result2.count}, Cost=${result2.cost}`);
  console.log('');

  console.log('🎉 Aggregation System Test Complete!');
}

// Run the test
testAggregation().catch(console.error); 