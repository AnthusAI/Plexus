'use client'

import React from 'react'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { Layout } from '@/components/landing/Layout'
import { Footer } from '@/components/landing/Footer'
import EvaluationTask from '@/components/EvaluationTask'
import { generateClient } from 'aws-amplify/api'
import { GraphQLResult } from '@aws-amplify/api-graphql'
import { type Schema } from '@/amplify/data/resource'
import { transformEvaluation } from '@/components/evaluations-dashboard'
import { type Evaluation } from '@/utils/data-operations'
import { getValueFromLazyLoader } from '@/utils/data-operations'
import type { LazyLoader } from '@/utils/types'
import { fetchAuthSession } from 'aws-amplify/auth'

// GraphQL query
const GET_EVALUATION = `
  query GetEvaluation($id: ID!) {
    getEvaluation(id: $id) {
      id
      type
      parameters
      metrics
      metricsExplanation
      inferences
      accuracy
      cost
      createdAt
      updatedAt
      status
      startedAt
      elapsedSeconds
      estimatedRemainingSeconds
      totalItems
      processedItems
      errorMessage
      errorDetails
      accountId
      scorecardId
      scorecard {
        id
        name
      }
      scoreId
      score {
        id
        name
      }
      confusionMatrix
      scoreGoal
      datasetClassDistribution
      isDatasetClassDistributionBalanced
      predictedClassDistribution
      isPredictedClassDistributionBalanced
      taskId
      task {
        id
        type
        status
        target
        command
        description
        dispatchStatus
        metadata
        createdAt
        startedAt
        completedAt
        estimatedCompletionAt
        errorMessage
        errorDetails
        currentStageId
        stages {
          items {
            id
            name
            order
            status
            statusMessage
            startedAt
            completedAt
            estimatedCompletionAt
            processedItems
            totalItems
          }
        }
      }
      scoreResults {
        items {
          id
          value
          confidence
          metadata
          explanation
          itemId
          createdAt
        }
      }
    }
  }
`

// Create a service for data fetching that can be easily mocked in tests
export class EvaluationService {
  constructor(
    private client = generateClient<Schema>(),
    private authService = { fetchAuthSession }
  ) {}

  async fetchEvaluation(id: string): Promise<Evaluation> {
    // Try to get the auth session
    let authMode: 'apiKey' | 'userPool' = 'apiKey';
    try {
      const session = await this.authService.fetchAuthSession();
      if (session.tokens?.idToken) {
        authMode = 'userPool';
      }
    } catch {
      console.log('No auth session, using apiKey');
    }

    // Use direct GraphQL query
    const response = await this.client.graphql({
      query: GET_EVALUATION,
      variables: { id },
      authMode
    }) as GraphQLResult<{
      getEvaluation: Schema['Evaluation']['type']
    }>;
    
    const result = response.data?.getEvaluation;
    if (!result) {
      throw new Error('No evaluation found');
    }
    
    return transformEvaluation(result) as Evaluation;
  }
}

// Props interface for the component
interface PublicEvaluationProps {
  evaluationService?: EvaluationService;
}

export default function PublicEvaluation({ 
  evaluationService = new EvaluationService() 
}: PublicEvaluationProps = {}) {
  const { id } = useParams() as { id: string };
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Memoize the service to prevent re-renders
  const memoizedService = React.useMemo(() => evaluationService, []);

  useEffect(() => {
    async function loadEvaluation() {
      try {
        const data = await memoizedService.fetchEvaluation(id);
        setEvaluation(data);
      } catch (err) {
        console.error('Error fetching evaluation:', err);
        setError('Failed to load evaluation');
      } finally {
        setLoading(false);
      }
    }

    if (id) {
      loadEvaluation();
    }
  }, [id, memoizedService]);

  return (
    <Layout>
      <div className="min-h-screen bg-background">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto py-8">
          {loading ? (
            <div className="flex items-center justify-center min-h-[50vh]">
              <div 
                role="status"
                className="animate-spin rounded-full h-8 w-8 border-b-2 border-foreground"
                aria-label="Loading"
              >
                <span className="sr-only">Loading...</span>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center min-h-[50vh] text-destructive">
              {error}
            </div>
          ) : evaluation ? (
            <div className="space-y-4">
              <h1 className="text-2xl font-semibold">Evaluation Results</h1>
              <EvaluationTask
                variant="detail"
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
                    metrics: [
                      {
                        name: 'Accuracy',
                        value: evaluation.accuracy || 0,
                        unit: '%',
                        maximum: 100,
                        priority: true
                      },
                      {
                        name: 'Precision',
                        value: Array.isArray(evaluation.metrics) ? 
                          (evaluation.metrics.find(m => m.name === 'Precision')?.value || 0) : 0,
                        unit: '%',
                        maximum: 100,
                        priority: true
                      },
                      {
                        name: 'Sensitivity',
                        value: Array.isArray(evaluation.metrics) ? 
                          (evaluation.metrics.find(m => m.name === 'Sensitivity')?.value || 0) : 0,
                        unit: '%',
                        maximum: 100,
                        priority: true
                      },
                      {
                        name: 'Specificity',
                        value: Array.isArray(evaluation.metrics) ? 
                          (evaluation.metrics.find(m => m.name === 'Specificity')?.value || 0) : 0,
                        unit: '%',
                        maximum: 100,
                        priority: true
                      }
                    ],
                    processedItems: evaluation.processedItems || 0,
                    totalItems: evaluation.totalItems || 0,
                    progress: (evaluation.processedItems || 0) / (evaluation.totalItems || 1) * 100,
                    inferences: evaluation.inferences || 0,
                    cost: evaluation.cost || null,
                    status: evaluation.status || 'COMPLETED',
                    elapsedSeconds: evaluation.elapsedSeconds || null,
                    estimatedRemainingSeconds: evaluation.estimatedRemainingSeconds || null,
                    startedAt: evaluation.startedAt || undefined,
                    errorMessage: evaluation.errorMessage || undefined,
                    errorDetails: evaluation.errorDetails || null,
                    confusionMatrix: evaluation.confusionMatrix ? {
                      matrix: typeof evaluation.confusionMatrix === 'string' ? 
                        JSON.parse(evaluation.confusionMatrix).matrix : 
                        evaluation.confusionMatrix.matrix,
                      labels: typeof evaluation.confusionMatrix === 'string' ? 
                        JSON.parse(evaluation.confusionMatrix).labels : 
                        evaluation.confusionMatrix.labels
                    } : null,
                    datasetClassDistribution: typeof evaluation.datasetClassDistribution === 'string' ?
                      JSON.parse(evaluation.datasetClassDistribution) :
                      evaluation.datasetClassDistribution,
                    isDatasetClassDistributionBalanced: evaluation.isDatasetClassDistributionBalanced,
                    predictedClassDistribution: typeof evaluation.predictedClassDistribution === 'string' ?
                      JSON.parse(evaluation.predictedClassDistribution) :
                      evaluation.predictedClassDistribution,
                    isPredictedClassDistributionBalanced: evaluation.isPredictedClassDistributionBalanced,
                    task: evaluation.task ? {
                      id: evaluation.task.id,
                      accountId: (evaluation as any).accountId || '',
                      type: evaluation.task.type || 'No',
                      status: evaluation.task.status,
                      target: evaluation.task.target,
                      command: evaluation.task.command,
                      description: evaluation.task.description || undefined,
                      metadata: evaluation.task.metadata,
                      createdAt: evaluation.task.createdAt || undefined,
                      startedAt: evaluation.task.startedAt || undefined,
                      completedAt: evaluation.task.completedAt || undefined,
                      estimatedCompletionAt: evaluation.task.estimatedCompletionAt || undefined,
                      errorMessage: evaluation.task.errorMessage || undefined,
                      errorDetails: evaluation.task.errorDetails || undefined,
                      currentStageId: evaluation.task.currentStageId || undefined,
                      stages: {
                        items: getValueFromLazyLoader(evaluation.task.stages)?.data?.items || [],
                        nextToken: null
                      }
                    } : null
                  }
                }}
              />
            </div>
          ) : (
            <div className="flex items-center justify-center min-h-[50vh] text-muted-foreground">
              No evaluation found
            </div>
          )}
        </div>
        <Footer />
      </div>
    </Layout>
  )
} 