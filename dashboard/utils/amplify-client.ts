import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { GraphQLResult } from '@aws-amplify/api'
import type { GraphqlSubscriptionResult } from '@aws-amplify/api-graphql'

let client: ReturnType<typeof generateClient<Schema>> | null = null;

export function getClient(): ReturnType<typeof generateClient<Schema>> {
  if (!client) {
    client = generateClient<Schema>();
  }
  return client;
}

export type GraphQLResponse<T> = GraphQLResult<T>;

export async function graphqlRequest<T>(query: string, variables?: Record<string, any>): Promise<GraphQLResponse<T>> {
  const currentClient = getClient();
  try {
    const response = await currentClient.graphql({
      query,
      variables
    });
    
    // Check if response is a subscription result
    if (response && typeof response === 'object' && 'subscribe' in response) {
      throw new Error('Subscription responses should be handled by observeGraphQL');
    }
    
    return response as GraphQLResponse<T>;
  } catch (error) {
    console.error('GraphQL request error:', error);
    throw error;
  }
}

export function handleGraphQLErrors(response: GraphQLResponse<any>): void {
  if (response.errors?.length) {
    console.error('GraphQL errors:', response.errors);
    throw new Error(`GraphQL errors: ${response.errors.map(e => e.message).join(', ')}`);
  }
}

export type AmplifyResponse<T> = { data: T; nextToken: string | null }
export type SubscriptionResponse<T> = { items: T[] }

export const amplifyClient = {
  Account: {
    list: async (params: any) => {
      const response = await (getClient().models.Account as any).list(params)
      return response as AmplifyResponse<Schema['Account']['type'][]>
    },
    get: async (params: any) => {
      const response = await (getClient().models.Account as any).get(params)
      return { data: response.data as Schema['Account']['type'] | null }
    },
    create: async (data: {
      name: string;
      key: string;
      description?: string;
    }) => {
      const response = await (getClient().models.Account as any).create(data)
      return { data: response.data as Schema['Account']['type'] }
    }
  },
  Scorecard: {
    list: async (params?: any) => {
      const response = await (getClient().models.Scorecard as any).list(params)
      return response as AmplifyResponse<Schema['Scorecard']['type'][]>
    },
    get: async (params: any) => {
      const response = await (getClient().models.Scorecard as any).get(params)
      return { data: response.data as Schema['Scorecard']['type'] | null }
    },
    create: async (data: {
      name: string
      key: string
      externalId: string
      description?: string
      accountId: string
      itemId?: string
    }) => {
      const response = await (getClient().models.Scorecard as any).create(data)
      return { data: response.data as Schema['Scorecard']['type'] }
    },
    update: async (data: {
      id: string
      name?: string
      key?: string
      externalId?: string
      description?: string
      itemId?: string
    }) => {
      const response = await (getClient().models.Scorecard as any).update(data)
      return { data: response.data as Schema['Scorecard']['type'] }
    },
    observeQuery: (params: any) => {
      return (getClient().models.Scorecard as any).observeQuery(params) as {
        subscribe: (handlers: {
          next: (response: SubscriptionResponse<Schema['Scorecard']['type']>) => void;
          error: (error: Error) => void;
        }) => { unsubscribe: () => void };
      }
    }
  },
  ScorecardSection: {
    list: async (params: any) => {
      const response = await (getClient().models.ScorecardSection as any).list(params)
      return response as AmplifyResponse<Schema['ScorecardSection']['type'][]>
    },
    create: async (data: {
      name: string
      order: number
      scorecardId: string
    }) => {
      const response = await (getClient().models.ScorecardSection as any).create(data)
      return { data: response.data as Schema['ScorecardSection']['type'] }
    },
    update: async (data: {
      id: string
      name?: string
      order?: number
    }) => {
      const response = await (getClient().models.ScorecardSection as any).update(data)
      return { data: response.data as Schema['ScorecardSection']['type'] }
    },
    delete: async (params: { id: string }) => {
      const response = await (getClient().models.ScorecardSection as any).delete(params)
      return { data: response.data as Schema['ScorecardSection']['type'] }
    }
  },
  Score: {
    list: async (params: any) => {
      const response = await (getClient().models.Score as any).list(params)
      return response as AmplifyResponse<Schema['Score']['type'][]>
    },
    get: async (params: any) => {
      const response = await (getClient().models.Score as any).get(params)
      return { data: response.data as Schema['Score']['type'] | null }
    },
    create: async (data: {
      name: string
      type: string
      order: number
      sectionId: string
      accuracy?: number
      version?: string
      aiProvider?: string
      aiModel?: string
      isFineTuned?: boolean
      configuration?: any
      distribution?: any[]
      versionHistory?: any[]
    }) => {
      const response = await (getClient().models.Score as any).create(data)
      return { data: response.data as Schema['Score']['type'] }
    },
    update: async (data: {
      id: string
      name?: string
      externalId?: string
      championVersionId?: string
      type?: string
      order?: number
      sectionId?: string
      accuracy?: number
      version?: string
      aiProvider?: string
      aiModel?: string
      isDisabled?: boolean
    }) => {
      const response = await graphqlRequest<{ updateScore: Schema['Score']['type'] }>(`
        mutation UpdateScore($input: UpdateScoreInput!) {
          updateScore(input: $input) {
            id
            name
            externalId
            championVersionId
            type
            order
            sectionId
            accuracy
            version
            aiProvider
            aiModel
            isDisabled
            createdAt
            updatedAt
          }
        }
      `, { input: data });
      return { data: response.data.updateScore };
    },
    delete: async (params: { id: string }) => {
      const response = await (getClient().models.Score as any).delete(params)
      return { data: response.data as Schema['Score']['type'] }
    }
  },
  ScoreVersion: {
    list: async (params: any) => {
      const response = await graphqlRequest<{ listScoreVersions: AmplifyResponse<Schema['ScoreVersion']['type'][]> }>(`
        query ListScoreVersions($filter: ScoreVersionFilterInput, $limit: Int, $nextToken: String) {
          listScoreVersions(filter: $filter, limit: $limit, nextToken: $nextToken) {
            items {
              id
              scoreId
              configuration
              isFeatured
              comment
              createdAt
              updatedAt
            }
            nextToken
          }
        }
      `, params);
      return response.data.listScoreVersions;
    },
    create: async (data: {
      scoreId: string
      configuration: string
      isFeatured: boolean
      comment?: string
      createdAt: string
      updatedAt: string
    }) => {
      const response = await graphqlRequest<{ createScoreVersion: Schema['ScoreVersion']['type'] }>(`
        mutation CreateScoreVersion($input: CreateScoreVersionInput!) {
          createScoreVersion(input: $input) {
            id
            scoreId
            configuration
            isFeatured
            comment
            createdAt
            updatedAt
          }
        }
      `, { input: data });
      return { data: response.data.createScoreVersion };
    },
    update: async (data: {
      id: string
      configuration?: any
      isFeatured?: boolean
      comment?: string
    }) => {
      const response = await graphqlRequest<{ updateScoreVersion: Schema['ScoreVersion']['type'] }>(`
        mutation UpdateScoreVersion($input: UpdateScoreVersionInput!) {
          updateScoreVersion(input: $input) {
            id
            scoreId
            configuration
            isFeatured
            comment
            createdAt
            updatedAt
          }
        }
      `, { input: data });
      return { data: response.data.updateScoreVersion };
    },
    delete: async (params: { id: string }) => {
      const response = await (getClient().models.ScoreVersion as any).delete(params)
      return { data: response.data as Schema['ScoreVersion']['type'] }
    }
  },
  Evaluation: {
    list: async (params: any) => {
      const response = await (getClient().models.Evaluation as any).list(params)
      return response as AmplifyResponse<Schema['Evaluation']['type'][]>
    },
    get: async (params: any) => {
      const response = await (getClient().models.Evaluation as any).get(params)
      return { data: response.data as Schema['Evaluation']['type'] | null }
    }
  },
  BatchJob: {
    list: async (params: any) => {
      const response = await (getClient().models.BatchJob as any).list(params)
      return response as AmplifyResponse<Schema['BatchJob']['type'][]>
    },
    get: async (params: any) => {
      const response = await (getClient().models.BatchJob as any).get(params)
      return { data: response.data as Schema['BatchJob']['type'] | null }
    }
  },
  Item: {
    list: async (params: any) => {
      const response = await (getClient().models.Item as any).list(params)
      return response as AmplifyResponse<Schema['Item']['type'][]>
    },
    get: async (params: any) => {
      const response = await (getClient().models.Item as any).get(params)
      return { data: response.data as Schema['Item']['type'] | null }
    },
    create: async (data: {
      externalId?: string;
      description?: string;
      text?: string;
      metadata?: Record<string, any>;
      attachedFiles?: string[];
      accountId: string;
      scoreId?: string;
      evaluationId?: string;
      isEvaluation: boolean;
      createdByType?: string;
    }) => {
      const response = await (getClient().models.Item as any).create(data)
      return { data: response.data as Schema['Item']['type'] }
    },
    update: async (data: {
      id: string;
      externalId?: string;
      description?: string;
      text?: string;
      metadata?: Record<string, any>;
      attachedFiles?: string[];
    }) => {
      const response = await (getClient().models.Item as any).update(data)
      return { data: response.data as Schema['Item']['type'] }
    }
  },
  ScorecardExampleItem: {
    create: async (data: {
      itemId: string;
      scorecardId: string;
      addedAt?: string;
      addedBy?: string;
      notes?: string;
    }) => {
      const response = await (getClient().models.ScorecardExampleItem as any).create(data)
      return { data: response.data as Schema['ScorecardExampleItem']['type'] }
    },
    delete: async (params: {
      itemId: string;
      scorecardId: string;
    }) => {
      // First find the record by the composite key
      const listResponse = await (getClient().models.ScorecardExampleItem as any).list({
        filter: {
          and: [
            { itemId: { eq: params.itemId } },
            { scorecardId: { eq: params.scorecardId } }
          ]
        }
      });
      
      if (listResponse.data && listResponse.data.length > 0) {
        const record = listResponse.data[0];
        const response = await (getClient().models.ScorecardExampleItem as any).delete({ id: record.id });
        return { data: response.data as Schema['ScorecardExampleItem']['type'] };
      } else {
        throw new Error('ScorecardExampleItem association not found');
      }
    },
    listByScorecard: async (scorecardId: string) => {
      const response = await (getClient().models.ScorecardExampleItem as any).list({
        filter: { scorecardId: { eq: scorecardId } }
      });
      return response as AmplifyResponse<Schema['ScorecardExampleItem']['type'][]>;
    },
    listByItem: async (itemId: string) => {
      const response = await (getClient().models.ScorecardExampleItem as any).list({
        filter: { itemId: { eq: itemId } }
      });
      return response as AmplifyResponse<Schema['ScorecardExampleItem']['type'][]>;
    },
    list: async (params?: any) => {
      const response = await (getClient().models.ScorecardExampleItem as any).list(params)
      return response as AmplifyResponse<Schema['ScorecardExampleItem']['type'][]>
    }
  },
  ScorecardProcessedItem: {
    create: async (data: {
      itemId: string;
      scorecardId: string;
      processedAt?: string;
      lastScoreResultId?: string;
    }) => {
      const response = await (getClient().models.ScorecardProcessedItem as any).create(data)
      return { data: response.data as Schema['ScorecardProcessedItem']['type'] }
    },
    delete: async (params: {
      itemId: string;
      scorecardId: string;
    }) => {
      // First find the record by the composite key
      const listResponse = await (getClient().models.ScorecardProcessedItem as any).list({
        filter: {
          and: [
            { itemId: { eq: params.itemId } },
            { scorecardId: { eq: params.scorecardId } }
          ]
        }
      });
      
      if (listResponse.data && listResponse.data.length > 0) {
        const record = listResponse.data[0];
        const response = await (getClient().models.ScorecardProcessedItem as any).delete({ id: record.id });
        return { data: response.data as Schema['ScorecardProcessedItem']['type'] };
      } else {
        throw new Error('ScorecardProcessedItem association not found');
      }
    },
    listByScorecard: async (scorecardId: string) => {
      const response = await (getClient().models.ScorecardProcessedItem as any).list({
        filter: { scorecardId: { eq: scorecardId } }
      });
      return response as AmplifyResponse<Schema['ScorecardProcessedItem']['type'][]>;
    },
    listByItem: async (itemId: string) => {
      const response = await (getClient().models.ScorecardProcessedItem as any).list({
        filter: { itemId: { eq: itemId } }
      });
      return response as AmplifyResponse<Schema['ScorecardProcessedItem']['type'][]>;
    },
    list: async (params?: any) => {
      const response = await (getClient().models.ScorecardProcessedItem as any).list(params)
      return response as AmplifyResponse<Schema['ScorecardProcessedItem']['type'][]>
    }
  },
  ScoringJob: {
    list: async (params: any) => {
      const response = await (getClient().models.ScoringJob as any).list(params)
      return response as AmplifyResponse<Schema['ScoringJob']['type'][]>
    },
    get: async (params: any) => {
      const response = await (getClient().models.ScoringJob as any).get(params)
      return { data: response.data as Schema['ScoringJob']['type'] | null }
    }
  },
  ScoreResult: {
    list: async (params: any) => {
      const response = await (getClient().models.ScoreResult as any).list(params)
      return response as AmplifyResponse<Schema['ScoreResult']['type'][]>
    },
    get: async (params: any) => {
      const response = await (getClient().models.ScoreResult as any).get(params)
      return { data: response.data as Schema['ScoreResult']['type'] | null }
    }
  },
  ShareLink: {
    create: async (data: {
      token: string;
      resourceType: string;
      resourceId: string;
      createdBy: string;
      accountId: string;
      expiresAt?: string;
      viewOptions?: string;
      accessCount?: number;
      isRevoked?: boolean;
    }) => {
      try {
        const client = getClient();
        if (!client.models || !client.models.ShareLink) {
          console.error('ShareLink model not found in client');
          throw new Error('ShareLink model not available');
        }
        const response = await (client.models.ShareLink as any).create(data);
        return { data: response.data as Schema['ShareLink']['type'] };
      } catch (error) {
        console.error('Error in amplifyClient.ShareLink.create:', error);
        throw error;
      }
    },
    get: async (params: { id: string }) => {
      try {
        const client = getClient();
        if (!client.models || !client.models.ShareLink) {
          console.error('ShareLink model not found in client');
          throw new Error('ShareLink model not available');
        }
        const response = await (client.models.ShareLink as any).get(params);
        return { data: response.data as Schema['ShareLink']['type'] | null };
      } catch (error) {
        console.error('Error in amplifyClient.ShareLink.get:', error);
        throw error;
      }
    },
    list: async (params: any) => {
      try {
        const client = getClient();
        if (!client.models || !client.models.ShareLink) {
          console.error('ShareLink model not found in client');
          throw new Error('ShareLink model not available');
        }
        const response = await (client.models.ShareLink as any).list(params);
        return response as AmplifyResponse<Schema['ShareLink']['type'][]>;
      } catch (error) {
        console.error('Error in amplifyClient.ShareLink.list:', error);
        throw error;
      }
    },
    update: async (data: {
      id: string;
      token?: string;
      resourceType?: string;
      resourceId?: string;
      expiresAt?: string;
      viewOptions?: string;
      lastAccessedAt?: string;
      accessCount?: number;
      isRevoked?: boolean;
    }) => {
      try {
        const client = getClient();
        if (!client.models || !client.models.ShareLink) {
          console.error('ShareLink model not found in client');
          throw new Error('ShareLink model not available');
        }
        const response = await (client.models.ShareLink as any).update(data);
        return { data: response.data as Schema['ShareLink']['type'] };
      } catch (error) {
        console.error('Error in amplifyClient.ShareLink.update:', error);
        throw error;
      }
    }
  },
  DataSource: {
    list: async (params?: any) => {
      const response = await (getClient().models.DataSource as any).list(params)
      return response as AmplifyResponse<Schema['DataSource']['type'][]>
    },
    get: async (params: any) => {
      const response = await (getClient().models.DataSource as any).get(params)
      return { data: response.data as Schema['DataSource']['type'] | null }
    },
    create: async (data: {
      name: string
      key?: string
      description?: string
      yamlConfiguration?: string
      attachedFiles?: string[]
      accountId: string
      scorecardId?: string
      scoreId?: string
      currentVersionId?: string
    }) => {
      const response = await (getClient().models.DataSource as any).create(data)
      return { data: response.data as Schema['DataSource']['type'] }
    },
    update: async (data: {
      id: string
      name?: string
      key?: string
      description?: string
      yamlConfiguration?: string
      attachedFiles?: string[]
      scorecardId?: string
      scoreId?: string
      currentVersionId?: string
    }) => {
      const response = await (getClient().models.DataSource as any).update(data)
      return { data: response.data as Schema['DataSource']['type'] }
    },
    delete: async (params: { id: string }) => {
      const response = await (getClient().models.DataSource as any).delete(params)
      return { data: response.data as Schema['DataSource']['type'] }
    }
  },
  DataSourceVersion: {
    list: async (params?: any) => {
      const response = await (getClient().models.DataSourceVersion as any).list(params)
      return response as AmplifyResponse<Schema['DataSourceVersion']['type'][]>
    },
    get: async (params: any) => {
      const response = await (getClient().models.DataSourceVersion as any).get(params)
      return { data: response.data as Schema['DataSourceVersion']['type'] | null }
    },
    create: async (data: {
      dataSourceId: string;
      yamlConfiguration: string;
      isFeatured: boolean;
      note?: string;
      parentVersionId?: string;
    }) => {
      const response = await (getClient().models.DataSourceVersion as any).create(data)
      return { data: response.data as Schema['DataSourceVersion']['type'] }
    },
    update: async (data: {
      id: string;
      yamlConfiguration?: string;
      isFeatured?: boolean;
      note?: string;
      parentVersionId?: string;
    }) => {
      const response = await (getClient().models.DataSourceVersion as any).update(data)
      return { data: response.data as Schema['DataSourceVersion']['type'] }
    },
    delete: async (params: { id: string }) => {
      const response = await (getClient().models.DataSourceVersion as any).delete(params)
      return { data: response.data as Schema['DataSourceVersion']['type'] }
    }
  },
  DataSet: {
    list: async (params?: any) => {
      const response = await (getClient().models.DataSet as any).list(params)
      return response as AmplifyResponse<Schema['DataSet']['type'][]>
    },
    get: async (params: any) => {
      const response = await (getClient().models.DataSet as any).get(params)
      return { data: response.data as Schema['DataSet']['type'] | null }
    },
    create: async (data: {
      name?: string
      description?: string
      file?: string
      attachedFiles?: string[]
      accountId: string
      scorecardId?: string
      scoreId?: string
      scoreVersionId: string
      dataSourceVersionId: string
    }) => {
      const response = await (getClient().models.DataSet as any).create(data)
      return { data: response.data as Schema['DataSet']['type'] }
    },
    update: async (data: {
      id: string
      name?: string
      description?: string
      file?: string
      attachedFiles?: string[]
      scorecardId?: string
      scoreId?: string
      scoreVersionId?: string
      dataSourceVersionId?: string
    }) => {
      const response = await (getClient().models.DataSet as any).update(data)
      return { data: response.data as Schema['DataSet']['type'] }
    },
    delete: async (params: { id: string }) => {
      const response = await (getClient().models.DataSet as any).delete(params)
      return { data: response.data as Schema['DataSet']['type'] }
    }
  }
} 