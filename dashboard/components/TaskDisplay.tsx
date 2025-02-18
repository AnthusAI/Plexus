import React, { useEffect, useState } from 'react'
import type { AmplifyTask, ProcessedTask } from '@/utils/data-operations'
import { transformAmplifyTask } from '@/utils/data-operations'
import type { EvaluationTaskProps } from '@/types/tasks/evaluation'
import type { TaskStatus } from '@/types/shared'
import EvaluationTask from '@/components/EvaluationTask'
import { Task, TaskHeader, TaskContent } from '@/components/Task'

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
  selectedScoreResultId?: string | null
  onSelectScoreResult?: (id: string | null) => void
}

function calculateProgress(processedItems?: number | null, totalItems?: number | null): number {
  if (!processedItems || !totalItems || totalItems === 0) return 0
  return Math.round((processedItems / totalItems) * 100)
}

export function TaskDisplay({ task, variant = 'grid', isSelected, onClick, extra = false, evaluationData, controlButtons, isFullWidth, onToggleFullWidth, onClose, selectedScoreResultId, onSelectScoreResult }: TaskDisplayProps) {
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

  const taskProps = {
    task: {
      id: evaluationData.id,
      type: evaluationData.type,
      scorecard: evaluationData.scorecard?.name || '-',
      score: evaluationData.score?.name || '-',
      time: evaluationData.createdAt || new Date().toISOString(),
      data: {
        id: evaluationData.id,
        title: `${evaluationData.scorecard?.name || '-'} - ${evaluationData.score?.name || '-'}`,
        metrics: typeof evaluationData.metrics === 'string' ? 
          JSON.parse(evaluationData.metrics).map((m: any) => ({
            name: m.name || 'Unknown',
            value: m.value || 0,
            unit: m.unit,
            maximum: m.maximum,
            priority: m.priority || false
          })) : (evaluationData.metrics || []).map((m: any) => ({
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
        metricsExplanation: evaluationData.metricsExplanation || null,
        scoreGoal: evaluationData.scoreGoal || null,
        datasetClassDistribution: typeof evaluationData.datasetClassDistribution === 'string' ? 
          JSON.parse(evaluationData.datasetClassDistribution) : evaluationData.datasetClassDistribution,
        isDatasetClassDistributionBalanced: evaluationData.isDatasetClassDistributionBalanced ?? null,
        predictedClassDistribution: typeof evaluationData.predictedClassDistribution === 'string' ? 
          JSON.parse(evaluationData.predictedClassDistribution) : evaluationData.predictedClassDistribution,
        isPredictedClassDistributionBalanced: evaluationData.isPredictedClassDistributionBalanced ?? null,
        scoreResults: evaluationData.scoreResults?.items?.map(result => {
          // Parse metadata if it's a string
          const metadata = (() => {
            try {
              if (typeof result.metadata === 'string') {
                const parsed = JSON.parse(result.metadata);
                // Handle double-stringified JSON
                if (typeof parsed === 'string') {
                  return JSON.parse(parsed);
                }
                return parsed;
              }
              return result.metadata || {};
            } catch (e) {
              console.error('Error parsing score result metadata:', e);
              return {};
            }
          })();

          // Extract results from nested structure if present
          const firstResultKey = metadata?.results ? Object.keys(metadata.results)[0] : null;
          const scoreResult = firstResultKey && metadata.results ? metadata.results[firstResultKey] : null;

          return {
            id: result.id,
            value: result.value,
            confidence: result.confidence ?? null,
            explanation: scoreResult?.explanation ?? metadata.explanation ?? null,
            metadata: {
              human_label: scoreResult?.metadata?.human_label ?? metadata.human_label ?? null,
              correct: Boolean(scoreResult?.metadata?.correct ?? metadata.correct),
              human_explanation: scoreResult?.metadata?.human_explanation ?? metadata.human_explanation ?? null,
              text: scoreResult?.metadata?.text ?? metadata.text ?? null
            },
            itemId: result.itemId
          };
        }) || [],
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
          }
        } : null
      }
    },
    onClick,
    controlButtons,
    isFullWidth,
    onToggleFullWidth,
    onClose,
    isSelected,
    extra,
    selectedScoreResultId,
    onSelectScoreResult
  } as EvaluationTaskProps

  return <EvaluationTask {...taskProps} variant={variant} />
} 