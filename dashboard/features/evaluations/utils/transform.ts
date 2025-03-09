import { Schema } from '@/amplify/data/resource'
import { getClient } from '@/utils/amplify-client'

export const transformEvaluation = (rawEvaluation: any): Schema['Evaluation']['type'] => {
  if (!rawEvaluation) {
    // Return a properly typed empty evaluation
    return {
      id: '',
      type: '',
      accuracy: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      status: 'PENDING',
      accountId: '',
      task: async () => ({ data: null }),
      scoreResults: async () => ({ data: [], nextToken: null }),
      scoringJobs: async () => ({ data: [], nextToken: null }),
      account: async () => ({ data: null }),
      scorecard: async () => ({ data: null }),
      score: async () => ({ data: null }),
      scoreVersion: async () => ({ data: null })
    }
  }

  // Create a safe copy of the evaluation with all required fields
  const safeEvaluation = {
    ...rawEvaluation,
    id: rawEvaluation.id || '',
    type: rawEvaluation.type || '',
    parameters: rawEvaluation.parameters || {},
    metrics: rawEvaluation.metrics || {},
    metricsExplanation: rawEvaluation.metricsExplanation || '',
    inferences: rawEvaluation.inferences || 0,
    accuracy: rawEvaluation.accuracy || 0,
    cost: rawEvaluation.cost || 0,
    createdAt: rawEvaluation.createdAt || new Date().toISOString(),
    updatedAt: rawEvaluation.updatedAt || new Date().toISOString(),
    status: rawEvaluation.status || 'PENDING',
    startedAt: rawEvaluation.startedAt || undefined,
    elapsedSeconds: rawEvaluation.elapsedSeconds || 0,
    estimatedRemainingSeconds: rawEvaluation.estimatedRemainingSeconds || 0,
    totalItems: rawEvaluation.totalItems || 0,
    processedItems: rawEvaluation.processedItems || 0,
    errorMessage: rawEvaluation.errorMessage || undefined,
    errorDetails: rawEvaluation.errorDetails || {},
    accountId: rawEvaluation.accountId || '',
    scorecardId: rawEvaluation.scorecardId || '',
    scoreId: rawEvaluation.scoreId || '',
    task: rawEvaluation.task ? (() => {
      const taskFn = async () => {
        const taskData = convertRawTaskToResponse(rawEvaluation.task)
        return { data: taskData }
      }
      return taskFn
    })() : async () => ({ data: null }),
    scoreResults: async () => ({ data: [], nextToken: null }),
    scoringJobs: async () => ({ data: [], nextToken: null }),
    account: async () => ({
      data: {
        id: rawEvaluation.account?.id || '',
        name: rawEvaluation.account?.name || '',
        key: rawEvaluation.account?.key || '',
        scorecards: async () => ({ data: [], nextToken: null }),
        evaluations: async () => ({ data: [], nextToken: null }),
        batchJobs: async () => ({ data: [], nextToken: null }),
        scoringJobs: async () => ({ data: [], nextToken: null }),
        scoreResults: async () => ({ data: [], nextToken: null }),
        actions: async () => ({ data: [], nextToken: null }),
        tasks: async () => ({ data: [], nextToken: null }),
        createdAt: rawEvaluation.account?.createdAt || new Date().toISOString(),
        updatedAt: rawEvaluation.account?.updatedAt || new Date().toISOString(),
        description: rawEvaluation.account?.description || ''
      }
    }),
    scorecard: async () => {
      if (rawEvaluation.scorecard?.data) {
        return { data: rawEvaluation.scorecard.data }
      }
      return { data: null }
    },
    score: async () => {
      if (rawEvaluation.score?.data) {
        return { data: rawEvaluation.score.data }
      }
      return { data: null }
    },
    scoreVersion: async () => ({ data: null })
  }

  return safeEvaluation as Schema['Evaluation']['type']
}

function convertRawTaskToResponse(rawTask: any) {
  return {
    id: rawTask.id || '',
    accountId: rawTask.accountId || '',
    type: rawTask.type || '',
    status: rawTask.status || '',
    target: rawTask.target || '',
    command: rawTask.command || '',
    description: rawTask.description,
    dispatchStatus: rawTask.dispatchStatus as 'DISPATCHED' | undefined,
    metadata: rawTask.metadata,
    createdAt: rawTask.createdAt,
    startedAt: rawTask.startedAt || undefined,
    completedAt: rawTask.completedAt || undefined,
    estimatedCompletionAt: rawTask.estimatedCompletionAt || undefined,
    errorMessage: rawTask.errorMessage || undefined,
    errorDetails: rawTask.errorDetails,
    currentStageId: rawTask.currentStageId,
    stages: rawTask.stages ? {
      items: rawTask.stages.items?.map((stage: any) => ({
        id: stage.id || '',
        name: stage.name || '',
        order: stage.order || 0,
        status: stage.status || '',
        statusMessage: stage.statusMessage,
        startedAt: stage.startedAt || undefined,
        completedAt: stage.completedAt || undefined,
        estimatedCompletionAt: stage.estimatedCompletionAt || undefined,
        processedItems: stage.processedItems,
        totalItems: stage.totalItems
      })) || [],
      nextToken: rawTask.stages.nextToken
    } : undefined
  }
} 