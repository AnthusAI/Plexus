import { useState, useCallback } from 'react';
import { generateClient } from 'aws-amplify/api';
import type { Schema } from '@/amplify/data/resource';

const client = generateClient<Schema>();

export interface FeedbackItemFilter {
  accountId: string;
  scorecardId: string;
  scoreId: string;
  predicted: string;
  actual: string;
  startDate?: Date;
  endDate?: Date;
}

export interface FeedbackItemWithRelations {
  id: string;
  initialAnswerValue?: string;
  finalAnswerValue?: string;
  initialCommentValue?: string;
  finalCommentValue?: string;
  editCommentValue?: string;
  isAgreement?: boolean;
  createdAt?: string;
  updatedAt?: string;
  editedAt?: string;
  editorName?: string;
  item?: {
    id: string;
    identifiers?: string;
    externalId?: string;
  };
}

/**
 * Hook for fetching feedback items by predicted and actual answer values
 * Used for confusion matrix drill-down functionality in on-demand feedback analysis
 */
export const useFeedbackItemsByAnswers = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchFeedbackItems = useCallback(async (filter: FeedbackItemFilter): Promise<FeedbackItemWithRelations[]> => {
    setLoading(true);
    setError(null);

    try {
      // Use the same GSI method that works in main feedback analysis
      // Use provided date range or fall back to 30 days
      const startDate = filter.startDate || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
      const endDate = filter.endDate || new Date();
      
      const response: any = await (client.models.FeedbackItem as any).listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt({
        accountId: filter.accountId,
        scorecardIdScoreIdEditedAt: {
          between: [
            {
              scorecardId: filter.scorecardId,
              scoreId: filter.scoreId,
              editedAt: startDate.toISOString()
            },
            {
              scorecardId: filter.scorecardId,
              scoreId: filter.scoreId,
              editedAt: endDate.toISOString()
            }
          ]
        },
        limit: 1000
      });
      
      const allItems = response.data || [];
      
      // Filter client-side to exact predicted/actual values
      const matchingItems = allItems.filter((item: any) => 
        item.initialAnswerValue === filter.predicted && 
        item.finalAnswerValue === filter.actual
      );
      
      // Sort by editedAt in reverse chronological order (most recent first)
      const sortedItems = matchingItems.sort((a: any, b: any) => {
        const dateA = new Date(a.editedAt || a.updatedAt || a.createdAt);
        const dateB = new Date(b.editedAt || b.updatedAt || b.createdAt);
        return dateB.getTime() - dateA.getTime();
      });
      
      return sortedItems.map((item: any) => ({
        id: item.id,
        initialAnswerValue: item.initialAnswerValue,
        finalAnswerValue: item.finalAnswerValue,
        initialCommentValue: item.initialCommentValue,
        finalCommentValue: item.finalCommentValue,
        editCommentValue: item.editCommentValue,
        isAgreement: item.isAgreement,
        createdAt: item.createdAt,
        updatedAt: item.updatedAt,
        editedAt: item.editedAt,
        editorName: item.editorName,
        item: item.item ? {
          id: item.item.id,
          identifiers: item.item.identifiers,
          externalId: item.item.externalId
        } : undefined
      }));
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      console.error('Error fetching feedback items by answers:', err);
      setError(errorMessage);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    fetchFeedbackItems,
    loading,
    error
  };
};