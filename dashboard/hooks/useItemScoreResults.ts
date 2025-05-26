import { useState, useEffect, useCallback } from 'react';
import { amplifyClient, graphqlRequest } from '@/utils/amplify-client';

// Interface for ScoreResult with nested scorecard and score information
export interface ScoreResultWithDetails {
  id: string;
  value: string;
  explanation?: string;
  confidence?: number | null;
  itemId: string;
  accountId: string;
  scorecardId: string;
  scoreId: string;
  updatedAt?: string;
  createdAt?: string;
  scorecard?: {
    id: string;
    name: string;
    externalId?: string;
  };
  score?: {
    id: string;
    name: string;
    externalId?: string;
  };
}

// Group score results by scorecard for better organization
export interface GroupedScoreResults {
  [scorecardId: string]: {
    scorecardId: string;
    scorecardName: string;
    scorecardExternalId?: string;
    scores: ScoreResultWithDetails[];
  };
}

export function useItemScoreResults(itemId: string | null) {
  const [scoreResults, setScoreResults] = useState<ScoreResultWithDetails[]>([]);
  const [groupedResults, setGroupedResults] = useState<GroupedScoreResults>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchScoreResults = useCallback(async (id: string) => {
    if (!id) {
      console.log('useItemScoreResults: No item ID provided');
      return;
    }
    
    console.log('useItemScoreResults: Starting fetch for item ID:', id);
    setIsLoading(true);
    setError(null);
    
    try {
      console.log('useItemScoreResults: Fetching score results for item:', id);
      
      // Query the Item with its scoreResults relationship
      console.log('useItemScoreResults: Querying item with scoreResults relationship');
      
      const graphqlResponse = await graphqlRequest<{
        getItem: {
          id: string;
          scoreResults: {
            items: any[];
            nextToken: string | null;
          };
        };
      }>(`
        query GetItemWithScoreResults($id: ID!) {
          getItem(id: $id) {
            id
            scoreResults {
              items {
                id
                value
                explanation
                confidence
                itemId
                accountId
                scorecardId
                scoreId
                updatedAt
                createdAt
                scorecard {
                  id
                  name
                  externalId
                }
                score {
                  id
                  name
                  externalId
                }
              }
              nextToken
            }
          }
        }
      `, { id });

      console.log('useItemScoreResults: GraphQL response:', graphqlResponse);
      
      const results = graphqlResponse.data?.getItem?.scoreResults?.items || [];
      const response = { data: results };

      console.log('useItemScoreResults: Raw response:', response);
      console.log('useItemScoreResults: Response data length:', results.length);
      console.log('useItemScoreResults: Response data:', results);

      if (results && results.length > 0) {
        console.log(`Found ${results.length} score results for item ${id}`);
        
        // Sort by creation time (most recent first)
        const sortedResults = results.sort((a, b) => {
          const dateA = new Date(a.createdAt || a.updatedAt || '').getTime();
          const dateB = new Date(b.createdAt || b.updatedAt || '').getTime();
          return dateB - dateA; // DESC order (newest first)
        });

        // Group results by scorecard using embedded data
        const grouped: GroupedScoreResults = {};
        
        console.log('useItemScoreResults: Starting to group results, count:', sortedResults.length);
        
        for (const result of sortedResults) {
          const scorecardId = result.scorecardId;
          
          // Add to grouped results
          if (!grouped[scorecardId]) {
            grouped[scorecardId] = {
              scorecardId,
              scorecardName: result.scorecard?.name || 'Unknown Scorecard',
              scorecardExternalId: result.scorecard?.externalId,
              scores: []
            };
          }
          
          // The result already has scorecard and score data from the query
          grouped[scorecardId].scores.push(result);
        }

        const finalResults = sortedResults;
        
        console.log('useItemScoreResults: Final grouped results:', grouped);
        console.log('useItemScoreResults: Grouped results keys:', Object.keys(grouped));
        console.log('useItemScoreResults: Setting state with results');
        
        setScoreResults(finalResults);
        setGroupedResults(grouped);
      } else {
        console.log('No score results found for item:', id);
        setScoreResults([]);
        setGroupedResults({});
      }
    } catch (err) {
      console.error('Error fetching score results:', err);
      setError(err instanceof Error ? err.message : 'Failed to load score results');
      setScoreResults([]);
      setGroupedResults({});
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (itemId) {
      fetchScoreResults(itemId);
    } else {
      // Clear data when itemId is null
      setScoreResults([]);
      setGroupedResults({});
      setError(null);
    }
  }, [itemId, fetchScoreResults]);

  return {
    scoreResults,
    groupedResults,
    isLoading,
    error,
    refetch: () => itemId ? fetchScoreResults(itemId) : undefined
  };
}