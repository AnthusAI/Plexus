/**
 * Hook for Ad-hoc Feedback Analysis
 * 
 * This hook handles fetching feedback data from GraphQL and computing
 * analysis metrics client-side using the feedback-analysis utilities.
 */

import { useState, useEffect, useCallback } from 'react';
import { generateClient } from 'aws-amplify/api';
import type { Schema } from '@/amplify/data/resource';
import {
  analyzeFeedbackForScore,
  analyzeFeedbackForScorecard,
  filterFeedbackByDateRange,
  convertToScorecardReportFormat,
  type FeedbackItem,
  type ScoreAnalysisResult,
  type AnalysisResult
} from '@/utils/feedback-analysis';
import type { FeedbackAnalysisDisplayData } from '@/components/ui/feedback-analysis-display';

const client = generateClient<Schema>();

export interface FeedbackAnalysisConfig {
  accountId?: string;
  scorecardId?: string;
  scoreId?: string;
  scoreIds?: string[];
  scoreName?: string; // Optional score name to avoid "Unknown Score"
  days?: number;
  startDate?: Date;
  endDate?: Date;
}

export interface FeedbackAnalysisState {
  isLoading: boolean;
  error: string | null;
  data: FeedbackAnalysisDisplayData | null;
  rawFeedback: FeedbackItem[];
}

/**
 * GraphQL query to fetch feedback items
 * Uses the correct field names from the schema: initialAnswerValue, finalAnswerValue
 */
const listFeedbackItemsQuery = `
  query ListFeedbackItems($filter: ModelFeedbackItemFilterInput, $limit: Int) {
    listFeedbackItems(filter: $filter, limit: $limit) {
      items {
        id
        itemId
        scoreId
        scorecardId
        initialAnswerValue
        finalAnswerValue
        updatedAt
        editedAt
        createdAt
        score {
          id
          name
          scorecard {
            id
            name
          }
        }
        item {
          id
          externalId
          description
        }
      }
      nextToken
    }
  }
`;

/**
 * Hook for performing ad-hoc feedback analysis
 */
export function useFeedbackAnalysis(config: FeedbackAnalysisConfig) {
  const [state, setState] = useState<FeedbackAnalysisState>({
    isLoading: false,
    error: null,
    data: null,
    rawFeedback: []
  });

  const fetchFeedbackData = useCallback(async () => {
    if (!config.accountId) {
      setState(prev => ({ ...prev, error: 'accountId must be provided' }));
      return;
    }
    
    if (!config.scorecardId && !config.scoreId && !config.scoreIds?.length) {
      setState(prev => ({ ...prev, error: 'Either scorecardId, scoreId, or scoreIds must be provided' }));
      return;
    }

    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      // Build filter based on configuration
      const filter: any = {};

      // Filter by scorecard or score
      if (config.scorecardId) {
        filter.scorecardId = { eq: config.scorecardId };
      }
      
      if (config.scoreId) {
        filter.scoreId = { eq: config.scoreId };
      } else if (config.scoreIds?.length) {
        filter.scoreId = { in: config.scoreIds };
      }

      console.log('🔍 Query strategy based on config:', {
        hasScorecardId: !!config.scorecardId,
        hasScoreId: !!config.scoreId,
        hasScoreIds: !!config.scoreIds?.length,
        days: config.days
      });

      let allFeedbackItems: any[] = [];
      let nextToken: string | null = null;
      let pageCount = 0;
      let scoreNameLookup: Record<string, string> = {};

      // Calculate date range for potential GSI queries
      const startDate = config.startDate || new Date(Date.now() - (config.days || 30) * 24 * 60 * 60 * 1000);
      const endDate = config.endDate || new Date();

      // For scorecard analysis, we need to fetch scoreIds first, then query each one
      if (config.scorecardId && !config.scoreId && config.accountId) {
        console.log(`🚀 Using GSI for scorecard analysis: scorecardId=${config.scorecardId}`);
        console.log(`📅 Date range: ${startDate.toISOString()} to ${endDate.toISOString()}`);

        try {
          // First, get all scores in this scorecard directly from the Scorecard
          console.log('🔍 Step 1: Getting list of scores in scorecard directly...');
          
          const scorecardQuery = `
            query GetScorecardScores($scorecardId: ID!) {
              getScorecard(id: $scorecardId) {
                scores {
                  items {
                    id
                    name
                  }
                }
              }
            }
          `;
          
          const scorecardResponse = await client.graphql({
            query: scorecardQuery,
            variables: { scorecardId: config.scorecardId }
          }) as any;
          
          const scores = scorecardResponse.data?.getScorecard?.scores?.items || [];
          console.log(`📋 Found ${scores.length} scores directly from scorecard`);
          
          // Build scoreId -> scoreName mapping
          scores.forEach((score: any) => {
            if (score.id && score.name) {
              scoreNameLookup[score.id] = score.name;
            }
          });
          
          const uniqueScoreIds = scores.map((score: any) => score.id).filter(Boolean);
          
          console.log(`📋 Found ${uniqueScoreIds.length} unique scores in scorecard:`);
          uniqueScoreIds.forEach((scoreId: string) => {
            console.log(`  - ${scoreId}: ${scoreNameLookup[scoreId] || 'Unknown'}`);
          });
          
          if (uniqueScoreIds.length === 0) {
            console.log('⚠️ No scores found in scorecard');
            allFeedbackItems = [];
          } else {
            // Step 2: Query each score individually using the efficient GSI
            console.log('🔍 Step 2: Querying each score individually using GSI...');
            
            for (let i = 0; i < uniqueScoreIds.length; i++) {
              const scoreId = uniqueScoreIds[i];
              console.log(`🎯 Querying score ${i + 1}/${uniqueScoreIds.length}: ${scoreId}`);
              
              let scorePageCount = 0;
              let scoreNextToken: string | null = null;
              
              let scoreItemCount = 0;
              
              do {
                scorePageCount++;
                
                const gsiParams = {
                  accountId: config.accountId,
                  scorecardIdScoreIdUpdatedAt: {
                    between: [
                      {
                        scorecardId: config.scorecardId,
                        scoreId: scoreId,
                        updatedAt: startDate.toISOString()
                      },
                      {
                        scorecardId: config.scorecardId,
                        scoreId: scoreId,
                        updatedAt: endDate.toISOString()
                      }
                    ]
                  },
                  limit: 1000,
                  nextToken: scoreNextToken
                };
                
                console.log(`🔍 Score ${scoreId} Page ${scorePageCount} query with nextToken: ${scoreNextToken ? 'yes' : 'no'}`);
                
                const response: any = await (client.models.FeedbackItem as any).listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAt(gsiParams);
                
                if (response.errors && response.errors.length > 0) {
                  console.error(`🚨 GSI query errors for score ${scoreId}:`, response.errors);
                  break;
                }

                const pageItems = response.data || [];
                const newNextToken = response.nextToken;
                
                scoreItemCount += pageItems.length;
                allFeedbackItems.push(...pageItems);
                
                console.log(`📄 Score ${scoreId} Page ${scorePageCount}: ${pageItems.length} items (score total: ${scoreItemCount}, overall total: ${allFeedbackItems.length})`);
                console.log(`🔗 Score ${scoreId} nextToken: ${newNextToken ? 'has more pages' : 'end of data'}`);
                
                scoreNextToken = newNextToken;
                
                if (scorePageCount > 10) {
                  console.warn(`🚨 Score ${scoreId} GSI taking too many pages`);
                  break;
                }
                
                // Important: If no more items on this page, break the pagination loop
                if (pageItems.length === 0) {
                  console.log(`📄 Score ${scoreId}: No more items, ending pagination`);
                  break;
                }
                
              } while (scoreNextToken);
              
              console.log(`✅ Score ${scoreId} complete: ${scoreItemCount} total items in ${scorePageCount} pages`);
            }
            
            console.log(`📋 Scorecard GSI queries complete: ${allFeedbackItems.length} total items across ${uniqueScoreIds.length} scores`);
          }

        } catch (scorecardError) {
          console.warn('🔄 Scorecard GSI approach failed, falling back to basic query:', scorecardError);
          allFeedbackItems = [];
        }
      }
      
      // For per-score analysis, use the efficient GSI
      else if (config.scoreId && config.accountId) {
        console.log(`🚀 Using GSI for per-score analysis: scoreId=${config.scoreId}`);
        console.log(`📅 Date range: ${startDate.toISOString()} to ${endDate.toISOString()}`);

        try {
          // Use the byAccountScorecardScoreEditedAt GSI for efficient per-score queries
          do {
            pageCount++;
            
            const gsiParams = {
              accountId: config.accountId,
              scorecardIdScoreIdUpdatedAt: {
                between: [
                  {
                    scorecardId: config.scorecardId,
                    scoreId: config.scoreId,
                    updatedAt: startDate.toISOString()
                  },
                  {
                    scorecardId: config.scorecardId,
                    scoreId: config.scoreId,
                    updatedAt: endDate.toISOString()
                  }
                ]
              },
              limit: 1000,
              nextToken
            };

            console.log(`🔍 GSI Query Page ${pageCount} with params:`, gsiParams);

            const response: any = await (client.models.FeedbackItem as any).listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAt(gsiParams);

            console.log(`📄 GSI Response:`, {
              hasData: !!response.data,
              dataLength: response.data?.length || 0,
              hasErrors: !!response.errors,
              errors: response.errors
            });

            if (response.errors && response.errors.length > 0) {
              console.error('🚨 GSI query errors:', response.errors);
              throw new Error(`GSI failed: ${response.errors.map((e: any) => e.message).join(', ')}`);
            }

            const pageItems = response.data || [];
            nextToken = response.nextToken;
            
            allFeedbackItems.push(...pageItems);
            console.log(`📄 GSI Page ${pageCount}: ${pageItems.length} items (total: ${allFeedbackItems.length})`);
            
            if (pageCount > 3) {
              console.warn('🚨 GSI taking too many pages, something is wrong');
              break;
            }
            
          } while (nextToken);

          console.log(`📋 GSI query complete: ${allFeedbackItems.length} items`);

        } catch (gsiError) {
          console.warn('🔄 GSI failed, falling back to basic query:', gsiError);
          allFeedbackItems = []; // Reset since GSI failed
          nextToken = null;
          pageCount = 0;
          
          // Fall through to basic query
        }
      }

      // Use basic GraphQL query as fallback or for scorecard queries
      if (allFeedbackItems.length === 0) {
        console.log('🔍 Using basic GraphQL query with filter:', filter);
        
          do {
            pageCount++;
            const variables: any = {
              filter,
              limit: 1000,
              nextToken
            };

            console.log(`📄 Basic Query Page ${pageCount}`);

            const response = await client.graphql({
              query: listFeedbackItemsQuery,
              variables
            }) as any;

            const pageItems = response.data?.listFeedbackItems?.items || [];
            nextToken = response.data?.listFeedbackItems?.nextToken;
            
            // Log sample item structure on first page
            if (pageItems.length > 0 && pageCount === 1) {
              console.log('📋 Sample feedback item structure:', {
                id: pageItems[0].id,
                scoreId: pageItems[0].scoreId,
                scorecardId: pageItems[0].scorecardId,
                initialAnswerValue: pageItems[0].initialAnswerValue,
                finalAnswerValue: pageItems[0].finalAnswerValue,
                updatedAt: pageItems[0].updatedAt,
                editedAt: pageItems[0].editedAt,
                hasScore: !!pageItems[0].score,
                hasItem: !!pageItems[0].item
              });
            }
            
            allFeedbackItems.push(...pageItems);
            console.log(`📄 Basic Page ${pageCount}: ${pageItems.length} items (total: ${allFeedbackItems.length})`);
            
            if (pageCount > 10) {
              console.warn('🚨 Basic query taking too many pages, stopping');
              break;
            }
            
          } while (nextToken);
        }

      console.log(`📋 Total feedback items fetched: ${allFeedbackItems.length}`);

      // scoreNameLookup is already populated by scorecard queries above

      // Transform to our internal format (using correct field names)
      const transformedItems: FeedbackItem[] = allFeedbackItems.map((item: any) => ({
        id: item.id,
        itemId: item.itemId,
        scoreId: item.scoreId,
        initialValue: item.initialAnswerValue,
        finalValue: item.finalAnswerValue,
        editedAt: item.editedAt || item.updatedAt,
        createdAt: item.createdAt,
        scoreName: item.score?.name || scoreNameLookup[item.scoreId] || config.scoreName || `Score ${item.scoreId}`,
        item: item.item ? {
          id: item.item.id,
          externalId: item.item.externalId,
          description: item.item.description
        } : undefined
      }));

      // Apply client-side date filtering if needed (GSI queries already filter by date)
      let filteredItems = transformedItems;
      if ((config.startDate || config.days) && !config.scoreId && !config.scorecardId) {
        // Only apply client-side date filtering for non-GSI queries (scorecard queries)
        const startDate = config.startDate || new Date(Date.now() - (config.days || 30) * 24 * 60 * 60 * 1000);
        const endDate = config.endDate || new Date();
        filteredItems = filterFeedbackByDateRange(transformedItems, startDate, endDate);
        
        console.log(`📅 Client-side date filtering: ${transformedItems.length} → ${filteredItems.length} items`);
        console.log(`📅 Date range: ${startDate.toISOString()} to ${endDate.toISOString()}`);
      } else if (config.scoreId || config.scorecardId) {
        console.log(`📅 GSI already filtered by date: ${transformedItems.length} items`);
        console.log(`📅 Date range: ${startDate.toISOString()} to ${endDate.toISOString()}`);
      }

      console.log(`📋 Final filtered items: ${filteredItems.length}`);

      // Perform analysis
      let analysisResult: { scores: ScoreAnalysisResult[]; overall: AnalysisResult };

      if (config.scoreId) {
        // Single score analysis
        const scoreAnalysis = analyzeFeedbackForScore(
          filteredItems, 
          config.scoreId, 
          filteredItems[0]?.scoreName || config.scoreName || 'Unknown Score'
        );
        analysisResult = {
          scores: [scoreAnalysis],
          overall: {
            accuracy: scoreAnalysis.accuracy,
            totalItems: scoreAnalysis.totalItems,
            totalAgreements: scoreAnalysis.totalAgreements,
            totalMismatches: scoreAnalysis.totalMismatches,
            ac1: scoreAnalysis.ac1,
            confusionMatrix: scoreAnalysis.confusionMatrix,
            labelDistribution: scoreAnalysis.labelDistribution,
            predictedLabelDistribution: scoreAnalysis.predictedLabelDistribution
          }
        };
      } else {
        // Multi-score or scorecard analysis
        analysisResult = analyzeFeedbackForScorecard(filteredItems, config.scoreIds);
      }

      // Convert to display format
      const dateRange = {
        start: config.startDate?.toISOString() || new Date(Date.now() - (config.days || 30) * 24 * 60 * 60 * 1000).toISOString(),
        end: config.endDate?.toISOString() || new Date().toISOString()
      };

      const displayData = convertToScorecardReportFormat(analysisResult, dateRange);

      const feedbackAnalysisData: FeedbackAnalysisDisplayData = {
        ...displayData,
        overall_ac1: displayData.overall_ac1,
        date_range: dateRange,
        block_title: config.scoreId ? 'Score Feedback Analysis' : 'Scorecard Feedback Analysis',
        block_description: `Analysis of ${filteredItems.length} feedback items over ${config.days || 30} days`
      };

      setState({
        isLoading: false,
        error: null,
        data: feedbackAnalysisData,
        rawFeedback: filteredItems
      });

    } catch (error) {
      console.error('❌ Error fetching feedback data:', error);
      setState({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch feedback data',
        data: null,
        rawFeedback: []
      });
    }
  }, [config]);

  const refresh = useCallback(() => {
    fetchFeedbackData();
  }, [fetchFeedbackData]);

  // Auto-fetch when config changes
  useEffect(() => {
    fetchFeedbackData();
  }, [fetchFeedbackData]);

  return {
    ...state,
    refresh
  };
}

/**
 * Simplified hook for score-level analysis
 */
export function useScoreFeedbackAnalysis(scoreId: string, days: number = 30) {
  return useFeedbackAnalysis({ scoreId, days });
}

/**
 * Simplified hook for scorecard-level analysis
 */
export function useScorecardFeedbackAnalysis(scorecardId: string, days: number = 30) {
  return useFeedbackAnalysis({ scorecardId, days });
}