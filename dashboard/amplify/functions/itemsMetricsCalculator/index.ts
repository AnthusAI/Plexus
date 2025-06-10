import { Handler } from 'aws-lambda';
import { MetricsCalculator } from './metrics-calculator';
import { cleanupCache } from './cache';

// Define the expected return type locally to match the GraphQL schema
interface ItemsMetricsResponse {
  accountId: string;
  hours: number;
  timestamp: string;
  // Items metrics
  totalItems: number;
  itemsLast24Hours: number;
  itemsLastHour: number;
  itemsHourlyBreakdown: any;
  // Score results metrics  
  totalScoreResults: number;
  scoreResultsLast24Hours: number;
  scoreResultsLastHour: number;
  scoreResultsHourlyBreakdown: any;
}

/**
 * Lambda handler for calculating items and score results metrics.
 * This mirrors the Python create_calculator_from_env function for environment variable handling.
 */
export const handler: Handler = async (event): Promise<ItemsMetricsResponse> => {
  console.log('Event:', JSON.stringify(event, null, 2));

  try {
    // Extract parameters from the event arguments
    const { accountId, hours = 24 } = event.arguments;

    if (!accountId) {
      throw new Error('accountId is required');
    }

    // Ensure environment variables are set
    const endpoint = process.env.PLEXUS_API_URL;
    const apiKey = process.env.PLEXUS_API_KEY;

    if (!endpoint || !apiKey) {
      throw new Error('PLEXUS_API_URL and PLEXUS_API_KEY environment variables must be set.');
    }

    console.log(`Using GraphQL endpoint: ${endpoint}`);
    console.log(`Using API key: ***${apiKey.slice(-4)}`);

    // Create metrics calculator instances with 15-minute cache buckets
    const itemsCalculator = new MetricsCalculator(endpoint, apiKey, 15, 'items');
    const scoreResultsCalculator = new MetricsCalculator(endpoint, apiKey, 15, 'score_results');

    // Get metrics for both items and score results
    const [itemsMetrics, scoreResultsMetrics] = await Promise.all([
      itemsCalculator.getItemsSummary(accountId, hours || 24),
      scoreResultsCalculator.getScoreResultsSummary(accountId, hours || 24)
    ]);

    // Combine the results to match the ItemsMetricsResponse type
    const result: ItemsMetricsResponse = {
      accountId,
      hours: hours || 24,
      timestamp: new Date().toISOString(),
      // Items metrics - map from actual return structure
      totalItems: itemsMetrics.itemsTotal24h,
      itemsLast24Hours: itemsMetrics.itemsTotal24h,
      itemsLastHour: itemsMetrics.itemsPerHour,
      itemsHourlyBreakdown: itemsMetrics.chartData,
      // Score results metrics - map from actual return structure
      totalScoreResults: scoreResultsMetrics.scoreResultsTotal24h,
      scoreResultsLast24Hours: scoreResultsMetrics.scoreResultsTotal24h,
      scoreResultsLastHour: scoreResultsMetrics.scoreResultsPerHour,
      scoreResultsHourlyBreakdown: scoreResultsMetrics.chartData
    };

    console.log('Result:', JSON.stringify(result, null, 2));
    
    return result;

  } catch (error) {
    console.error('Error calculating metrics:', error);
    throw error;
  } finally {
    // Clean up cache before Lambda execution completes
    cleanupCache();
  }
}; 