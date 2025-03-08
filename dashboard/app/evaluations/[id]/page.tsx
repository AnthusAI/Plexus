'use client'

import React, { useState, useEffect } from 'react'
import { useParams, usePathname } from 'next/navigation'
import { AlertCircle } from 'lucide-react'
import { generateClient } from 'aws-amplify/api'
import { Schema } from '@/amplify/data/resource'
import EvaluationTask from '@/components/EvaluationTask'
import { getValueFromLazyLoader } from '@/utils/amplify-helpers'
import { Evaluation } from '@/types/evaluation'
import EvaluationsDashboard from '@/components/evaluations-dashboard'

// Utility function to standardize score results
function standardizeScoreResults(scoreResults: any): any[] {
  if (!scoreResults) return [];
  
  // If it's already an array, return it
  if (Array.isArray(scoreResults)) {
    return scoreResults;
  }
  
  // If it has an items property that's an array, return that
  if (scoreResults && typeof scoreResults === 'object' && 'items' in scoreResults && Array.isArray(scoreResults.items)) {
    return scoreResults.items;
  }
  
  // If it's a string (JSON), try to parse it
  if (typeof scoreResults === 'string') {
    try {
      const parsed = JSON.parse(scoreResults);
      return Array.isArray(parsed) ? parsed : 
             (parsed && 'items' in parsed && Array.isArray(parsed.items)) ? parsed.items : [];
    } catch (e) {
      console.error('Error parsing score results:', e);
      return [];
    }
  }
  
  return [];
}

// Share link data type
type ShareLinkData = {
  token: string;
  resourceType: string;
  resourceId: string;
  viewOptions: Record<string, any>;
};

// Service class for evaluation operations
export class EvaluationService {
  constructor(
    private client = generateClient<Schema>()
  ) {}

  // Fetch evaluation by ID (for dashboard deep links)
  async fetchEvaluationById(id: string): Promise<Evaluation> {
    try {
      const response = await this.client.models.Evaluation.get({
        id
      });
      
      return response.data as Evaluation;
    } catch (error) {
      console.error('Error fetching evaluation by ID:', error);
      throw error;
    }
  }
  
  // Fetch evaluation by share token
  async fetchEvaluationByShareToken(token: string): Promise<Evaluation> {
    try {
      // First, get the share link data
      const shareLinkResponse = await this.client.models.ShareLink.get({
        id: token
      });
      
      if (!shareLinkResponse.data) {
        throw new Error('Share link not found');
      }
      
      const shareLink = shareLinkResponse.data;
      
      // Check if the share link has expired
      if (shareLink.expiresAt && new Date(shareLink.expiresAt) < new Date()) {
        throw new Error('Share link has expired');
      }
      
      // Check if the share link has been revoked
      if (shareLink.revoked) {
        throw new Error('Share link has been revoked');
      }
      
      // Check if the resource type is evaluation
      if (shareLink.resourceType !== 'EVALUATION') {
        throw new Error('Invalid resource type');
      }
      
      // Get the evaluation data
      const evaluationResponse = await this.client.models.Evaluation.get({
        id: shareLink.resourceId
      });
      
      if (!evaluationResponse.data) {
        throw new Error('Evaluation not found');
      }
      
      return evaluationResponse.data as Evaluation;
    } catch (error) {
      console.error('Error fetching evaluation by share token:', error);
      throw error;
    }
  }

  // Check if a string is a valid share token
  isValidToken(token: string): boolean {
    // Simple validation - share tokens are UUIDs (32 hex chars with optional hyphens)
    return /^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$/i.test(token);
  }
}

// Props interface for the component
interface PublicEvaluationProps {
  evaluationService?: EvaluationService;
  isDashboardView?: boolean;
}

export default function EvaluationPage() {
  // For share views, render the public evaluation component
  return <PublicEvaluation />;
}

export function PublicEvaluation({ 
  evaluationService = new EvaluationService(),
  isDashboardView = false
}: PublicEvaluationProps = {}) {
  const { id } = useParams() as { id: string };
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedScoreResultId, setSelectedScoreResultId] = useState<string | null>(null);
  
  // Memoize the service to prevent re-renders
  const memoizedService = React.useMemo(() => evaluationService, []);

  // Debug selected score result ID changes
  useEffect(() => {
    console.log('Selected score result ID changed in PublicEvaluation:', selectedScoreResultId);
  }, [selectedScoreResultId]);

  useEffect(() => {
    async function loadEvaluation() {
      try {
        if (!id) {
          throw new Error('No ID or token provided');
        }
        
        let data: Evaluation;
        
        // If this is a share token, fetch by token
        if (memoizedService.isValidToken(id) && !isDashboardView) {
          console.log('Loading evaluation with token:', id);
          data = await memoizedService.fetchEvaluationByShareToken(id);
        } else {
          // Otherwise, fetch by ID (for dashboard deep links)
          console.log('Loading evaluation with ID:', id);
          data = await memoizedService.fetchEvaluationById(id);
        }
        
        console.log('Successfully loaded evaluation:', {
          id: data.id,
          hasScoreResults: !!data.scoreResults,
          scoreResultsType: typeof data.scoreResults,
          scoreResultsIsArray: Array.isArray(data.scoreResults),
          scoreResultsHasItems: data.scoreResults && typeof data.scoreResults === 'object' && 'items' in data.scoreResults,
          scoreResultsItemsCount: data.scoreResults && typeof data.scoreResults === 'object' && 'items' in data.scoreResults ? data.scoreResults.items?.length : 0,
          scoreResultsRaw: data.scoreResults
        });
        setEvaluation(data);
      } catch (err) {
        console.error('Error fetching evaluation:', err);
        
        // Extract the error message
        let errorMessage = 'Failed to load evaluation';
        
        if (err instanceof Error) {
          console.error('Error details:', {
            message: err.message,
            stack: err.stack,
            name: err.name
          });
          errorMessage = err.message;
        } else if (typeof err === 'object' && err !== null) {
          // Handle case where err is a GraphQL error object
          if ('errors' in err && Array.isArray((err as any).errors) && (err as any).errors.length > 0) {
            errorMessage = (err as any).errors[0].message;
          }
        }
        
        // Check for specific error messages
        if (errorMessage.includes('Share link has expired')) {
          setError('This evaluation share link has expired.');
        } else if (errorMessage.includes('Share link has been revoked')) {
          setError('This evaluation share link has been revoked.');
        } else {
          setError(errorMessage);
        }
      } finally {
        setLoading(false);
      }
    }

    if (id) {
      loadEvaluation();
    }
  }, [id, memoizedService, isDashboardView]);

  // If this is a dashboard view, we don't need to render anything
  // The parent component (EvaluationsDashboard) will handle rendering
  if (isDashboardView) {
    return null;
  }

  return (
    <div className="w-full h-full px-6 pt-3 pb-6 overflow-auto">
      {loading ? (
        <div className="flex items-center justify-center h-full">
          <div 
            role="status"
            className="animate-spin rounded-full h-8 w-8 border-b-2 border-foreground"
            aria-label="Loading"
          >
            <span className="sr-only">Loading...</span>
          </div>
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center h-full text-center px-4">
          <div className="mb-4 text-destructive">
            <AlertCircle className="h-12 w-12 mx-auto" />
          </div>
          <h1 className="text-2xl font-bold mb-2">Unable to Load Evaluation</h1>
          <p className="text-muted-foreground max-w-md">{error}</p>
          {error === 'This evaluation share link has expired.' && (
            <p className="text-muted-foreground max-w-md mt-2">
              Share links have a limited validity period for security reasons. Please request a new share link from the evaluation owner.
            </p>
          )}
          {error === 'This evaluation share link has been revoked.' && (
            <p className="text-muted-foreground max-w-md mt-2">
              This share link has been manually revoked by the evaluation owner and is no longer valid.
            </p>
          )}
        </div>
      ) : evaluation ? (
        <div className="h-full flex flex-col">
          <h1 className="text-xl font-bold mb-2">Evaluation Results</h1>
          <div className="flex-1 overflow-auto">
            <EvaluationTask 
              variant="detail"
              isFullWidth={true}
              task={{
                id: evaluation.id,
                type: evaluation.type,
                scorecard: evaluation.scorecard?.name || '',
                score: evaluation.score?.name || '',
                time: evaluation.createdAt,
                data: {
                  id: evaluation.id,
                  title: evaluation.scorecard?.name || '',
                  accuracy: evaluation.accuracy || null,
                  metrics: evaluation.metrics || [],
                  processedItems: evaluation.processedItems || 0,
                  totalItems: evaluation.totalItems || 0,
                  progress: (evaluation.processedItems || 0) / (evaluation.totalItems || 1) * 100,
                  inferences: evaluation.inferences || 0,
                  cost: evaluation.cost || null,
                  status: evaluation.status || 'COMPLETED',
                  elapsedSeconds: evaluation.elapsedSeconds || null,
                  estimatedRemainingSeconds: evaluation.estimatedRemainingSeconds || null,
                  startedAt: evaluation.startedAt ? evaluation.startedAt : undefined,
                  errorMessage: evaluation.errorMessage ? evaluation.errorMessage : undefined,
                  errorDetails: evaluation.errorDetails ? evaluation.errorDetails : undefined,
                  confusionMatrix: evaluation.confusionMatrix ? {
                    matrix: typeof evaluation.confusionMatrix === 'string' ? 
                      JSON.parse(evaluation.confusionMatrix).matrix : 
                      evaluation.confusionMatrix.matrix,
                    labels: typeof evaluation.confusionMatrix === 'string' ? 
                      JSON.parse(evaluation.confusionMatrix).labels : 
                      evaluation.confusionMatrix.labels
                  } : undefined,
                  datasetClassDistribution: evaluation.datasetClassDistribution ? 
                    (typeof evaluation.datasetClassDistribution === 'string' ?
                      JSON.parse(evaluation.datasetClassDistribution) :
                      evaluation.datasetClassDistribution) : undefined,
                  isDatasetClassDistributionBalanced: evaluation.isDatasetClassDistributionBalanced === null ? 
                    undefined : evaluation.isDatasetClassDistributionBalanced,
                  predictedClassDistribution: evaluation.predictedClassDistribution ? 
                    (typeof evaluation.predictedClassDistribution === 'string' ?
                      JSON.parse(evaluation.predictedClassDistribution) :
                      evaluation.predictedClassDistribution) : undefined,
                  isPredictedClassDistributionBalanced: evaluation.isPredictedClassDistributionBalanced === null ? 
                    undefined : evaluation.isPredictedClassDistributionBalanced,
                  scoreResults: evaluation.scoreResults ? standardizeScoreResults(evaluation.scoreResults) : [],
                  task: evaluation.task ? {
                    id: evaluation.task.id,
                    accountId: (evaluation as any).accountId || '',
                    type: evaluation.task.type || 'EVALUATION',
                    status: evaluation.task.status,
                    target: evaluation.task.target,
                    command: evaluation.task.command,
                    description: evaluation.task.description || undefined,
                    metadata: evaluation.task.metadata || {},
                    createdAt: evaluation.task.createdAt || undefined,
                    startedAt: evaluation.task.startedAt || undefined,
                    completedAt: evaluation.task.completedAt || undefined,
                    estimatedCompletionAt: evaluation.task.estimatedCompletionAt || undefined,
                    errorMessage: evaluation.task.errorMessage || undefined,
                    errorDetails: evaluation.task.errorDetails || undefined,
                    currentStageId: evaluation.task.currentStageId || undefined,
                    stages: {
                      items: evaluation.task.stages ? getValueFromLazyLoader(evaluation.task.stages)?.data?.items || [] : [],
                      nextToken: null
                    }
                  } : null
                }
              }}
              selectedScoreResultId={selectedScoreResultId}
              onSelectScoreResult={setSelectedScoreResultId}
            />
          </div>
        </div>
      ) : null}
    </div>
  )
} 