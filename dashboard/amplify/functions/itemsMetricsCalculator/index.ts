import { Handler } from 'aws-lambda';
import { MetricsCalculator } from './metrics-calculator';

/**
 * Lambda handler for calculating items and score results metrics.
 * This mirrors the Python create_calculator_from_env function for environment variable handling.
 */
export const handler: Handler = async (event) => {
  console.log('Event:', JSON.stringify(event, null, 2));

  try {
    // Extract parameters from the event
    const { accountId, hours = 24 } = event.arguments || {};

    if (!accountId) {
      throw new Error('accountId is required');
    }

    // Try Amplify environment variables first (for Lambda functions)
    let endpoint = process.env.API_PLEXUSDASHBOARD_GRAPHQLAPIENDPOINTOUTPUT;
    let apiKey = process.env.API_PLEXUSDASHBOARD_GRAPHQLAPIKEYOUTPUT;
    
    // Fall back to custom environment variables (for CLI and local development)
    if (!endpoint) {
      endpoint = process.env.PLEXUS_API_URL;
    }
    if (!apiKey) {
      apiKey = process.env.PLEXUS_API_KEY;
    }

    if (!endpoint || !apiKey) {
      throw new Error(
        'GraphQL endpoint and API key environment variables must be set. ' +
        'For Lambda functions, Amplify provides API_PLEXUSDASHBOARD_GRAPHQLAPIENDPOINTOUTPUT and API_PLEXUSDASHBOARD_GRAPHQLAPIKEYOUTPUT. ' +
        'For CLI/local development, set PLEXUS_API_URL and PLEXUS_API_KEY.'
      );
    }

    console.log(`Creating MetricsCalculator with endpoint: ${endpoint}`);
    console.log(`Using API key: ***${apiKey.slice(-4)}`);

    // Create metrics calculator instance with 15-minute cache buckets
    const calculator = new MetricsCalculator(endpoint, apiKey, 15);

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