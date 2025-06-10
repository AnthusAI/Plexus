import { Handler } from 'aws-lambda';
import { MetricsCalculator } from './metrics-calculator';

/**
 * Lambda handler for calculating items and score results metrics
 */
export const handler: Handler = async (event) => {
  console.log('Event:', JSON.stringify(event, null, 2));

  try {
    // Extract parameters from the event
    const { accountId, hours = 24 } = event.arguments || {};

    if (!accountId) {
      throw new Error('accountId is required');
    }

    // Get environment variables
    const graphqlEndpoint = process.env.PLEXUS_API_URL;
    const apiKey = process.env.PLEXUS_API_KEY;

    if (!graphqlEndpoint || !apiKey) {
      throw new Error('PLEXUS_API_URL and PLEXUS_API_KEY environment variables must be set');
    }

    // Create metrics calculator instance
    const calculator = new MetricsCalculator(graphqlEndpoint, apiKey);

    // Get metrics for both items and score results
    const [itemsMetrics, scoreResultsMetrics] = await Promise.all([
      calculator.getItemsSummary(accountId, hours),
      calculator.getScoreResultsSummary(accountId, hours)
    ]);

    // Combine the results
    const result = {
      ...itemsMetrics,
      ...scoreResultsMetrics,
      accountId,
      hours,
      timestamp: new Date().toISOString()
    };

    console.log('Result:', JSON.stringify(result, null, 2));
    return result;

  } catch (error) {
    console.error('Error calculating metrics:', error);
    throw error;
  }
}; 