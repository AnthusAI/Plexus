import React, { useEffect, useState } from 'react'
import type { AmplifyTask, ProcessedTask } from '@/utils/data-operations'
import { transformAmplifyTask } from '@/utils/data-operations'
import type { EvaluationTaskProps } from '@/types/tasks/evaluation'
import type { TaskStatus } from '@/types/shared'

interface TaskDisplayProps {
  task: AmplifyTask | null
  variant?: 'grid' | 'detail'
  isSelected?: boolean
  onClick?: () => void
  extra?: boolean
  evaluationData: {
    id: string
    type: string
    scorecard?: { name: string } | null
    score?: { name: string } | null
    createdAt: string
    metrics?: any
    metricsExplanation?: string | null
    accuracy?: number | null
    processedItems?: number | null
    totalItems?: number | null
    inferences?: number | null
    cost?: number | null
    status?: string | null
    elapsedSeconds?: number | null
    estimatedRemainingSeconds?: number | null
    startedAt?: string | null
    errorMessage?: string | null
    errorDetails?: any
    confusionMatrix?: any
    scoreGoal?: string | null
    datasetClassDistribution?: any
    isDatasetClassDistributionBalanced?: boolean | null
    predictedClassDistribution?: any
    isPredictedClassDistributionBalanced?: boolean | null
    scoreResults?: {
      items?: Array<{
        id: string
        value: string | number
        confidence: number | null
        metadata: any
        itemId: string | null
      }>
    } | null
  }
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
}

interface MetricInput {
  name?: string
  value?: number
  unit?: string
  maximum?: number
  priority?: boolean
}

function calculateProgress(processedItems: number | null | undefined, totalItems: number | null | undefined): number {
  if (!processedItems || !totalItems) return 0
  return Math.round((processedItems / totalItems) * 100)
}

function createLazyEvaluation(evaluationData: TaskDisplayProps['evaluationData']): () => Promise<any> {
  return () => Promise.resolve({
    id: evaluationData.id,
    type: evaluationData.type,
    metrics: evaluationData.metrics || [],
    metricsExplanation: evaluationData.metricsExplanation || undefined,
    inferences: Number(evaluationData.inferences || 0),
    accuracy: Number(evaluationData.accuracy || 0),
    cost: evaluationData.cost || null,
    status: evaluationData.status || 'PENDING',
    elapsedSeconds: evaluationData.elapsedSeconds || null,
    estimatedRemainingSeconds: evaluationData.estimatedRemainingSeconds || null,
    totalItems: Number(evaluationData.totalItems || 0),
    processedItems: Number(evaluationData.processedItems || 0),
    errorMessage: evaluationData.errorMessage || undefined,
    errorDetails: evaluationData.errorDetails || undefined,
    scoreGoal: evaluationData.scoreGoal || undefined,
    datasetClassDistribution: evaluationData.datasetClassDistribution,
    isDatasetClassDistributionBalanced: Boolean(evaluationData.isDatasetClassDistributionBalanced),
    predictedClassDistribution: evaluationData.predictedClassDistribution,
    isPredictedClassDistributionBalanced: Boolean(evaluationData.isPredictedClassDistributionBalanced),
    scoreResults: evaluationData.scoreResults || undefined
  })
}

export function TaskDisplay({ task, variant = 'grid', isSelected, onClick, extra = false, evaluationData, controlButtons, isFullWidth, onToggleFullWidth, onClose }: TaskDisplayProps) {
  const [processedTask, setProcessedTask] = useState<ProcessedTask | null>(null)

  useEffect(() => {
    async function processTask() {
      if (!task) {
        setProcessedTask(null)
        return
      }
      try {
        const result = await transformAmplifyTask(task)
        setProcessedTask(result)
      } catch (error) {
        console.error('Error processing task:', error)
        setProcessedTask(null)
      }
    }
    processTask()
  }, [task])

  const taskProps: EvaluationTaskProps = {
    id: evaluationData.id,
    type: evaluationData.type,
    scorecard: evaluationData.scorecard?.name || '-',
    score: evaluationData.score?.name || '-',
    time: evaluationData.createdAt,
    data: {
      id: evaluationData.id,
      title: `${evaluationData.scorecard?.name || '-'} - ${evaluationData.score?.name || '-'}`,
      metrics: typeof evaluationData.metrics === 'string' ? 
        JSON.parse(evaluationData.metrics).map((m: MetricInput) => ({
          name: m.name || 'Unknown',
          value: m.value || 0,
          unit: m.unit,
          maximum: m.maximum,
          priority: m.priority || false
        })) : (evaluationData.metrics || []).map((m: MetricInput) => ({
          name: m.name || 'Unknown',
          value: m.value || 0,
          unit: m.unit,
          maximum: m.maximum,
          priority: m.priority || false
        })),
      accuracy: evaluationData.accuracy || null,
      processedItems: Number(evaluationData.processedItems || 0),
      totalItems: Number(evaluationData.totalItems || 0),
      progress: calculateProgress(evaluationData.processedItems, evaluationData.totalItems),
      inferences: Number(evaluationData.inferences || 0),
      cost: evaluationData.cost ?? null,
      status: (evaluationData.status || 'PENDING') as TaskStatus,
      elapsedSeconds: evaluationData.elapsedSeconds ?? null,
      estimatedRemainingSeconds: evaluationData.estimatedRemainingSeconds ?? null,
      startedAt: evaluationData.startedAt || undefined,
      errorMessage: evaluationData.errorMessage || undefined,
      errorDetails: evaluationData.errorDetails || undefined,
      confusionMatrix: typeof evaluationData.confusionMatrix === 'string' ? 
        JSON.parse(evaluationData.confusionMatrix) : evaluationData.confusionMatrix,
      task: processedTask ? {
        ...processedTask,
        accountId: evaluationData.id,
        stages: {
          items: processedTask.stages?.map(stage => ({
            id: stage.id,
            name: stage.name,
            order: stage.order,
            status: stage.status,
            statusMessage: stage.statusMessage,
            startedAt: stage.startedAt,
            completedAt: stage.completedAt,
            estimatedCompletionAt: stage.estimatedCompletionAt,
            processedItems: stage.processedItems,
            totalItems: stage.totalItems
          })) || []
        },
        evaluation: createLazyEvaluation(evaluationData)
      } : null
    }
  }

  // Create stages data for rendering
  const stageElements = processedTask?.stages?.map(stage => ({
    key: stage.name,
    label: stage.name,
    color: stage.status === 'COMPLETED' ? 'bg-primary' :
           stage.status === 'RUNNING' ? 'bg-secondary' :
           stage.status === 'FAILED' ? 'bg-false' :
           'bg-neutral',
    name: stage.name,
    order: stage.order,
    status: stage.status,
    processedItems: stage.processedItems,
    totalItems: stage.totalItems,
    startedAt: stage.startedAt,
    completedAt: stage.completedAt,
    estimatedCompletionAt: stage.estimatedCompletionAt,
    statusMessage: stage.statusMessage
  })) || []

  return React.createElement('div', {
    className: 'evaluation-task',
    onClick,
    'data-selected': isSelected,
    'data-variant': variant,
    'data-extra': extra,
    'data-full-width': isFullWidth,
    children: [
      controlButtons,
      JSON.stringify(taskProps, null, 2),
      stageElements.length > 0 && React.createElement('div', {
        className: 'stages',
        children: JSON.stringify(stageElements, null, 2)
      })
    ].filter(Boolean)
  })
} 