import { useState, useCallback } from 'react';
import { generateClient } from 'aws-amplify/api';
import type { Schema } from '@/amplify/data/resource';

const client = generateClient<Schema>();

// GraphQL query to fetch feedback items with nested item data including identifiers
const FEEDBACK_ITEMS_WITH_IDENTIFIERS_QUERY = `
  query ListFeedbackItemsWithIdentifiers(
    $accountId: String!,
    $scorecardId: String!,
    $scoreId: String!,
    $startDate: String!,
    $endDate: String!,
    $limit: Int
  ) {
    listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt(
      accountId: $accountId,
      scorecardIdScoreIdEditedAt: {
        between: [
          {
            scorecardId: $scorecardId,
            scoreId: $scoreId,
            editedAt: $startDate
          },
          {
            scorecardId: $scorecardId,
            scoreId: $scoreId,
            editedAt: $endDate
          }
        ]
      },
      limit: $limit
    ) {
      items {
        id
        initialAnswerValue
        finalAnswerValue
        initialCommentValue
        finalCommentValue
        editCommentValue
        isAgreement
        createdAt
        updatedAt
        editedAt
        editorName
        itemId
        item {
          id
          identifiers
          externalId
          itemIdentifiers {
            items {
              name
              value
              url
              position
            }
          }
        }
      }
      nextToken
    }
  }
`;

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
      // Use provided date range or fall back to 30 days
      const startDate = filter.startDate || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
      const endDate = filter.endDate || new Date();

      // Use raw GraphQL query to get nested item data with identifiers
      const response: any = await client.graphql({
        query: FEEDBACK_ITEMS_WITH_IDENTIFIERS_QUERY,
        variables: {
          accountId: filter.accountId,
          scorecardId: filter.scorecardId,
          scoreId: filter.scoreId,
          startDate: startDate.toISOString(),
          endDate: endDate.toISOString(),
          limit: 1000
        }
      });

      const allItems = response.data?.listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt?.items || [];

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

      return sortedItems.map((item: any) => {
        // Process identifiers from the nested item data
        let processedIdentifiers = undefined;

        if (item.item) {
          // First check for the itemIdentifiers relationship (preferred)
          if (item.item.itemIdentifiers?.items && Array.isArray(item.item.itemIdentifiers.items)) {
            // Sort by position and map to the expected format
            processedIdentifiers = item.item.itemIdentifiers.items
              .sort((a: any, b: any) => (a.position || 0) - (b.position || 0))
              .map((identifier: any) => ({
                name: identifier.name,
                value: identifier.value,
                url: identifier.url || undefined
              }));
          }
          // Fallback to the identifiers field if itemIdentifiers is not available
          else if (item.item.identifiers) {
            // If identifiers is a string, try to parse it
            if (typeof item.item.identifiers === 'string') {
              try {
                const parsed = JSON.parse(item.item.identifiers);
                // Check if it's already in the correct array format
                if (Array.isArray(parsed)) {
                  processedIdentifiers = parsed;
                } else if (typeof parsed === 'object') {
                  // Convert object format to array format
                  processedIdentifiers = Object.entries(parsed).map(([key, value]) => ({
                    name: key,
                    value: String(value)
                  }));
                }
              } catch (e) {
                console.warn('Failed to parse identifiers JSON:', e);
              }
            } else if (typeof item.item.identifiers === 'object' && !Array.isArray(item.item.identifiers)) {
              // Convert object format to array format
              processedIdentifiers = Object.entries(item.item.identifiers).map(([key, value]) => ({
                name: key,
                value: String(value)
              }));
            }
          }
        }

        return {
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
            id: item.item.id || item.itemId,
            identifiers: processedIdentifiers,
            externalId: item.item.externalId || undefined
          } : undefined
        };
      });
      
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