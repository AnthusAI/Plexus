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
  code?: string; // HTTP response code (e.g., "200", "404", "500")
  updatedAt?: string;
  createdAt?: string;
  attachments?: string[] | null;
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
  isNew?: boolean; // Flag for animation purposes
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

  const fetchScoreResults = useCallback(async (id: string, silent: boolean = false) => {
    if (!id) {
      return;
    }
    
    if (!silent) {
      setIsLoading(true);
    }
    setError(null);
    
    try {
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
                code
                updatedAt
                createdAt
                attachments
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
      
      const results = graphqlResponse.data?.getItem?.scoreResults?.items || [];
      const response = { data: results };

      if (results && results.length > 0) {        
        // Sort by creation time (most recent first)
        const sortedResults = results.sort((a, b) => {
          const dateA = new Date(a.createdAt || a.updatedAt || '').getTime();
          const dateB = new Date(b.createdAt || b.updatedAt || '').getTime();
          return dateB - dateA; // DESC order (newest first)
        });

        // If this is a silent refetch, identify new results for animation
        if (silent) {
          // Use functional update to access current state without dependency
          setScoreResults(prevResults => {
            const existingIds = new Set(prevResults.map(result => result.id));
            const finalResults = sortedResults.map(result => ({
              ...result,
              isNew: !existingIds.has(result.id)
            }));
            
            // After a delay, remove the "isNew" flag to stop the animation
            setTimeout(() => {
              setScoreResults(currentResults => 
                currentResults.map(result => ({ ...result, isNew: false }))
              );
              setGroupedResults(currentGrouped => {
                const newGrouped = { ...currentGrouped };
                Object.keys(newGrouped).forEach(scorecardId => {
                  newGrouped[scorecardId] = {
                    ...newGrouped[scorecardId],
                    scores: newGrouped[scorecardId].scores.map(score => ({ ...score, isNew: false }))
                  };
                });
                return newGrouped;
              });
            }, 3000); // Remove animation after 3 seconds
            
            return finalResults;
          });
          
          // Group results by scorecard using embedded data (with isNew flags)
          setGroupedResults(prevGrouped => {
            const grouped: GroupedScoreResults = {};
            const existingIds = new Set(Object.values(prevGrouped).flatMap(g => g.scores.map(s => s.id)));
            
            for (const result of sortedResults) {
              const scorecardId = result.scorecardId;
              const resultWithNew = {
                ...result,
                isNew: !existingIds.has(result.id)
              };
              
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
              grouped[scorecardId].scores.push(resultWithNew);
            }
            
            return grouped;
          });
        } else {
          // Regular fetch - no animation needed
          const finalResults = sortedResults;
          
          // Group results by scorecard using embedded data
          const grouped: GroupedScoreResults = {};
          
          for (const result of finalResults) {
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
          
          setScoreResults(finalResults);
          setGroupedResults(grouped);
        }
      } else {
        setScoreResults([]);
        setGroupedResults({});
      }
    } catch (err) {
      console.error('Error fetching score results:', err);
      setError(err instanceof Error ? err.message : 'Failed to load score results');
      setScoreResults([]);
      setGroupedResults({});
    } finally {
      if (!silent) {
        setIsLoading(false);
      }
          }
    }, []); // Don't include scoreResults to avoid infinite loop

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
    refetch: () => itemId ? fetchScoreResults(itemId) : undefined,
    silentRefetch: () => itemId ? fetchScoreResults(itemId, true) : undefined
  };
}