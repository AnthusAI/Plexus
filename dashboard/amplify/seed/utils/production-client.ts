import { AmplifyClassV6 } from '@aws-amplify/core';
import { generateClient } from '@aws-amplify/api-graphql/internals';
import type { ModelIntrospectionSchema } from '@aws-amplify/core/internals/utils';
import type { Schema } from '../../data/resource';

type AmplifyOutputs = {
  data?: {
    model_introspection?: ModelIntrospectionSchema;
  };
};

export function createProductionClient(apiUrl: string, apiKey: string, sandboxOutputs: AmplifyOutputs) {
  // Extract region from API URL
  // Format: https://{api-id}.appsync-api.{region}.amazonaws.com/graphql
  const urlParts = apiUrl.split('.');
  const region = urlParts.length >= 3 ? urlParts[2] : 'us-east-1';

  const amplify = new AmplifyClassV6();
  amplify.configure({
    API: {
      GraphQL: {
        endpoint: apiUrl,
        region,
        defaultAuthMode: 'apiKey',
        apiKey,
        modelIntrospection: sandboxOutputs.data?.model_introspection
      }
    }
  });

  return generateClient<Schema>({ amplify });
}
