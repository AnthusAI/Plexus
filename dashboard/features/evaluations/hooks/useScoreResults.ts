import { useState, useEffect } from 'react';
import { observeScoreResults } from '@/utils/subscriptions';
import type { Schema } from '@/amplify/data/resource';
import { standardizeScoreResults } from '@/utils/data-operations';

type ScoreResult = {
  id: string;
  value: string | number;
  confidence: number | null;
  metadata: any;
  explanation?: string | null;
  trace?: any | null;
  itemId: string | null;
  createdAt?: string;
};

type UseScoreResultsReturn = {
  scoreResults: ScoreResult[];
  isLoading: boolean;
  error: Error | null;
};

/**
 * Hook to fetch and subscribe to score results for a specific evaluation
 * This uses the observeScoreResults function which properly handles pagination
 * to fetch ALL score results, not just the first 100
 * 
 * Implements progressive loading:
 * - Shows the first 100 results immediately from initialResults
 * - Then loads the rest in the background and appends them
 */
export function useScoreResults(
  evaluationId: string | null,
  initialResults?: any // Initial results from the evaluation query
): UseScoreResultsReturn {
  // Initialize with the initial results if available
  const standardizedInitialResults = initialResults ? standardizeScoreResults(initialResults) : [];
  
  const [scoreResults, setScoreResults] = useState<ScoreResult[]>(standardizedInitialResults);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const [hasLoadedAll, setHasLoadedAll] = useState<boolean>(false);

  useEffect(() => {
    // If we have initial results, show them immediately
    if (initialResults && !hasLoadedAll) {
      const standardized = standardizeScoreResults(initialResults);
      console.log('Using initial results while loading all:', {
        count: standardized.length,
        firstResult: standardized[0],
        lastResult: standardized[standardized.length - 1]
      });
      setScoreResults(standardized);
    }
  }, [initialResults, hasLoadedAll]);

  useEffect(() => {
    // Reset loading state when evaluation ID changes
    setIsLoading(true);
    setError(null);
    setHasLoadedAll(false);

    if (!evaluationId) {
      setIsLoading(false);
      return;
    }

    console.log('Setting up score results subscription for evaluation:', evaluationId);
    
    // Set up subscription
    const subscription = observeScoreResults(evaluationId);
    const sub = subscription.subscribe({
      next: (data: { items: Schema['ScoreResult']['type'][], isSynced: boolean }) => {
        console.log('Received score results update:', {
          evaluationId,
          scoreResultCount: data.items.length,
          isSynced: data.isSynced,
          timestamp: new Date().toISOString()
        });
        
        // Transform items to match expected type
        const transformedItems = data.items.map(item => {
          // Create a properly typed object
          const result: ScoreResult = {
            id: item.id,
            value: item.value,
            confidence: item.confidence ?? null,
            metadata: item.metadata ?? null,
            explanation: item.explanation ?? null,
            trace: item.trace ?? null,
            itemId: item.itemId ?? null
          };
          
          // Only add createdAt if it exists and is a string
          if (item.createdAt && typeof item.createdAt === 'string') {
            result.createdAt = item.createdAt;
          }
          
          return result;
        });
        
        // Only update if we have more results than before or if we've synced
        if (transformedItems.length > scoreResults.length || data.isSynced) {
          setScoreResults(transformedItems);
          setHasLoadedAll(data.isSynced);
        }
        
        // Only set loading to false when we've synced
        if (data.isSynced) {
          setIsLoading(false);
        }
      },
      error: (err: Error) => {
        console.error('Error in score results subscription:', err);
        setError(err);
        setIsLoading(false);
      }
    });

    // Clean up subscription
    return () => {
      console.log('Cleaning up score results subscription for evaluation:', evaluationId);
      sub.unsubscribe();
    };
  }, [evaluationId]);

  return { scoreResults, isLoading, error };
} 