import { graphqlRequest, handleGraphQLErrors } from './amplify-client';
import { 
  GET_SCORECARD_WITH_SECTIONS_AND_SCORES, 
  LIST_SCORECARDS_WITH_SECTIONS_AND_SCORES,
  LIST_SCORECARDS_BY_ACCOUNT_ID
} from '../graphql/scorecard-queries';
import type { Schema } from '@/amplify/data/resource';

// Define types for the GraphQL responses
type ScorecardWithSectionsAndScores = {
  id: string;
  name: string;
  key: string;
  description?: string;
  externalId?: string;
  accountId: string;
  itemId?: string;
  createdAt: string;
  updatedAt: string;
  sections: {
    items: Array<{
      id: string;
      name: string;
      order: number;
      scorecardId: string;
      createdAt: string;
      updatedAt: string;
      scores: {
        items: Array<{
          id: string;
          name: string;
          key?: string;
          description?: string;
          order: number;
          type: string;
          accuracy?: number;
          version?: string;
          aiProvider?: string;
          aiModel?: string;
          sectionId: string;
          configuration?: any;
          externalId: string;
          createdAt: string;
          updatedAt: string;
        }>;
      };
    }>;
  };
};

type GetScorecardResponse = {
  getScorecard: ScorecardWithSectionsAndScores;
};

type ListScorecardsResponse = {
  listScorecards: {
    items: ScorecardWithSectionsAndScores[];
    nextToken: string | null;
  };
};

// Convert GraphQL response to Amplify model format
export function convertToAmplifyScorecard(scorecard: ScorecardWithSectionsAndScores): Schema['Scorecard']['type'] {
  // Create sections with their scores
  const sectionsWithScores = scorecard.sections.items.map(section => {
    const scores = section.scores.items.map(score => ({
      ...score,
      section: async () => ({ data: section }),
      // Add other required properties for Score type
    }));

    return {
      ...section,
      scorecard: async () => ({ data: scorecard }),
      scores: async () => ({ 
        data: scores,
        nextToken: null
      }),
    };
  });

  // Create the full scorecard object with lazy loaders
  const result = {
    ...scorecard,
    account: async () => ({ 
      data: { id: scorecard.accountId } as Schema['Account']['type'] 
    }),
    sections: async () => ({ 
      data: sectionsWithScores,
      nextToken: null
    }),
    evaluations: async () => ({ data: [], nextToken: null }),
    batchJobs: async () => ({ data: [], nextToken: null }),
    item: async () => scorecard.itemId ? 
      { data: { id: scorecard.itemId } as Schema['Item']['type'] } : 
      { data: null },
    scoringJobs: async () => ({ data: [], nextToken: null }),
    scoreResults: async () => ({ data: [], nextToken: null }),
    actions: [],
    datasets: async () => ({ data: [], nextToken: null }),
    tasks: async () => ({ data: [], nextToken: null }),
  };
  
  // Use type assertion to handle the complex type
  return result as unknown as Schema['Scorecard']['type'];
}

// Fetch a single scorecard with all its sections and scores
export async function getScorecardWithSectionsAndScores(id: string): Promise<Schema['Scorecard']['type'] | null> {
  try {
    const response = await graphqlRequest<GetScorecardResponse>(
      GET_SCORECARD_WITH_SECTIONS_AND_SCORES,
      { id }
    );
    
    handleGraphQLErrors(response);
    
    if (!response.data?.getScorecard) {
      return null;
    }
    
    return convertToAmplifyScorecard(response.data.getScorecard);
  } catch (error) {
    console.error('Error fetching scorecard with sections and scores:', error);
    throw error;
  }
}

// List all scorecards with their sections and scores
export async function listScorecardsWithSectionsAndScores(
  filter?: any,
  limit?: number,
  nextToken?: string
): Promise<{
  data: Schema['Scorecard']['type'][];
  nextToken: string | null;
}> {
  try {
    const response = await graphqlRequest<ListScorecardsResponse>(
      LIST_SCORECARDS_WITH_SECTIONS_AND_SCORES,
      { filter, limit, nextToken }
    );
    
    handleGraphQLErrors(response);
    
    if (!response.data?.listScorecards) {
      return { data: [], nextToken: null };
    }
    
    const scorecards = response.data.listScorecards.items.map(convertToAmplifyScorecard);
    
    return {
      data: scorecards,
      nextToken: response.data.listScorecards.nextToken
    };
  } catch (error) {
    console.error('Error listing scorecards with sections and scores:', error);
    throw error;
  }
}

// List scorecards by account ID with their sections and scores
export async function listScorecardsByAccountId(
  accountId: string,
  limit?: number,
  nextToken?: string
): Promise<{
  data: Schema['Scorecard']['type'][];
  nextToken: string | null;
}> {
  try {
    const response = await graphqlRequest<ListScorecardsResponse>(
      LIST_SCORECARDS_BY_ACCOUNT_ID,
      { accountId, limit, nextToken }
    );
    
    handleGraphQLErrors(response);
    
    if (!response.data?.listScorecards) {
      return { data: [], nextToken: null };
    }
    
    const scorecards = response.data.listScorecards.items.map(convertToAmplifyScorecard);
    
    return {
      data: scorecards,
      nextToken: response.data.listScorecards.nextToken
    };
  } catch (error) {
    console.error('Error listing scorecards by account ID:', error);
    throw error;
  }
} 