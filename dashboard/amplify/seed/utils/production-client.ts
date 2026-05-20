import { Amplify } from 'aws-amplify';
import { generateClient } from 'aws-amplify/data';
import type { Schema } from '../../data/resource';

export function createProductionClient(apiUrl: string, apiKey: string) {
  // Extract region from API URL
  // Format: https://{api-id}.appsync-api.{region}.amazonaws.com/graphql
  const urlParts = apiUrl.split('.');
  const region = urlParts.length >= 3 ? urlParts[2] : 'us-east-1';

  // Configure Amplify to point to production
  Amplify.configure({
    API: {
      GraphQL: {
        endpoint: apiUrl,
        region: region,
        defaultAuthMode: 'apiKey',
        apiKey: apiKey
      }
    }
  }, { ssr: false });

  return generateClient<Schema>();
}
