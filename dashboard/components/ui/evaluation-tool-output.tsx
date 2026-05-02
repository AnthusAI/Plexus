"use client"

import React, { useState, useMemo, useEffect } from 'react'
import Link from 'next/link'
import { MessageSquareCode, Copy, AlertCircle } from 'lucide-react'
import { generateClient } from 'aws-amplify/api'
import { Button } from '@/components/ui/button'
import { CardButton } from '@/components/CardButton'
import { TaskDisplay } from '@/components/TaskDisplay'
import { toast } from 'sonner'
import type { Schema } from '@/amplify/data/resource'
import { transformEvaluation } from '@/utils/data-operations'
import type { Evaluation } from '@/utils/data-operations'

interface EvaluationToolOutputProps {
  toolOutput: unknown
}

const GET_EVALUATION_LIGHT_QUERY = `
  query GetEvaluationLight($id: ID!) {
    getEvaluation(id: $id) {
      id
      type
      accuracy
      metrics
      metricsExplanation
      processedItems
      totalItems
      inferences
      cost
      status
      elapsedSeconds
      estimatedRemainingSeconds
      startedAt
      createdAt
      updatedAt
      errorMessage
      errorDetails
      confusionMatrix
      scoreGoal
      datasetClassDistribution
      isDatasetClassDistributionBalanced
      predictedClassDistribution
      isPredictedClassDistributionBalanced
      scorecardId
      scoreId
      scoreVersionId
      parameters
      taskId
      task {
        id
        accountId
        type
        status
        target
        command
        completedAt
        startedAt
        dispatchStatus
        celeryTaskId
        workerNodeId
        description
        metadata
        createdAt
        estimatedCompletionAt
        errorMessage
        errorDetails
        currentStageId
        stages {
          items {
            id
            taskId
            name
            order
            status
            statusMessage
            startedAt
            completedAt
            estimatedCompletionAt
            processedItems
            totalItems
            createdAt
            updatedAt
          }
        }
      }
      scorecard {
        id
        name
      }
      score {
        id
        name
      }
    }
  }
`

const LIST_SCORE_RESULTS_QUERY = `
  query ListScoreResults($evaluationId: String!, $limit: Int, $nextToken: String) {
    listScoreResultByEvaluationId(
      evaluationId: $evaluationId
      limit: $limit
      nextToken: $nextToken
    ) {
      items {
        id
        value
        explanation
        confidence
        metadata
        trace
        itemId
        createdAt
        feedbackItem {
          id
          editCommentValue
          initialAnswerValue
          initialCommentValue
          finalAnswerValue
          editorName
          editedAt
          createdAt
          scoreResults {
            items {
              id
              value
              explanation
              type
            }
          }
        }
        item {
          id
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
`

const EVALUATION_CACHE = new Map<string, Evaluation>()
const HYDRATED_EVALUATION_IDS = new Set<string>()

function parseToolOutput(output: unknown): unknown {
  if (!output) return null
  if (typeof output === 'string') {
    try {
      return JSON.parse(output)
    } catch {
      const responseMatch = output.match(/\n\nResponse:\n([\s\S]+)$/)
      if (responseMatch) {
        try {
          return JSON.parse(responseMatch[1].trim())
        } catch {
          return null
        }
      }
      return null
    }
  }
  return output
}

function extractEvaluationIds(parsed: unknown): string[] {
  if (Array.isArray(parsed)) {
    return parsed
      .map((item: any) => item?.evaluation_id || item?.id)
      .filter((id): id is string => typeof id === 'string' && id.trim().length > 0)
      .map(id => id.trim())
  }
  if (parsed && typeof parsed === 'object') {
    const id = (parsed as any).evaluation_id || (parsed as any).id
    if (typeof id === 'string' && id.trim()) return [id.trim()]
    const value = (parsed as any).value
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      const valueId = (value as any).evaluation_id || (value as any).id
      if (typeof valueId === 'string' && valueId.trim()) return [valueId.trim()]
    }
  }
  return []
}

function formatJson(obj: unknown): string {
  if (typeof obj === 'string') return obj
  try {
    const jsonString = JSON.stringify(obj, null, 2)
    return jsonString.replace(/\\n/g, '\n')
  } catch {
    return String(obj)
  }
}

function buildEvaluationData(evaluation: Evaluation) {
  return {
    id: evaluation.id,
    type: evaluation.type,
    scorecard: evaluation.scorecard,
    score: evaluation.score,
    createdAt: evaluation.createdAt,
    metrics: evaluation.metrics,
    metricsExplanation: evaluation.metricsExplanation,
    accuracy: evaluation.accuracy,
    processedItems: evaluation.processedItems,
    totalItems: evaluation.totalItems,
    inferences: evaluation.inferences,
    cost: evaluation.cost,
    status: evaluation.status,
    elapsedSeconds: evaluation.elapsedSeconds,
    estimatedRemainingSeconds: evaluation.estimatedRemainingSeconds,
    startedAt: evaluation.startedAt,
    errorMessage: evaluation.errorMessage,
    errorDetails: evaluation.errorDetails,
    confusionMatrix: evaluation.confusionMatrix,
    scoreGoal: evaluation.scoreGoal,
    datasetClassDistribution: evaluation.datasetClassDistribution,
    isDatasetClassDistributionBalanced: evaluation.isDatasetClassDistributionBalanced,
    predictedClassDistribution: evaluation.predictedClassDistribution,
    isPredictedClassDistributionBalanced: evaluation.isPredictedClassDistributionBalanced,
    scoreResults: evaluation.scoreResults,
    scorecardId: evaluation.scorecardId,
    scoreId: evaluation.scoreId,
    scoreVersionId: evaluation.scoreVersionId,
    parameters: evaluation.parameters,
    baseline_evaluation_id: (evaluation as any).baseline_evaluation_id ?? null,
    current_baseline_evaluation_id: (evaluation as any).current_baseline_evaluation_id ?? null,
  }
}

async function fetchEvaluationLight(evaluationId: string): Promise<{ evaluation: Evaluation; raw: any }> {
  const client = generateClient<Schema>()
  const result = await client.graphql({
    query: GET_EVALUATION_LIGHT_QUERY,
    variables: { id: evaluationId },
  }) as any

  const raw = result?.data?.getEvaluation
  if (!raw) {
    throw new Error('Evaluation not found')
  }

  const transformed = transformEvaluation(raw)
  if (!transformed) {
    throw new Error('Failed to transform evaluation')
  }

  return {
    evaluation: transformed as Evaluation,
    raw,
  }
}

async function fetchScoreResultsForEvaluation(evaluationId: string): Promise<any[]> {
  const client = generateClient<Schema>()
  let nextToken: string | null = null
  let scoreResultItems: any[] = []

  do {
    const result = await client.graphql({
      query: LIST_SCORE_RESULTS_QUERY,
      variables: {
        evaluationId,
        limit: 1000,
        nextToken,
      },
    }) as any

    const data = result?.data?.listScoreResultByEvaluationId
    scoreResultItems = scoreResultItems.concat(Array.isArray(data?.items) ? data.items : [])
    nextToken = data?.nextToken || null
  } while (nextToken)

  return scoreResultItems
}

function EvaluationEntrySkeleton() {
  return (
    <div className="rounded-md bg-card p-3" data-testid="evaluation-entry-skeleton">
      <div className="h-4 w-40 animate-pulse rounded bg-muted mb-2" />
      <div className="h-3 w-full animate-pulse rounded bg-muted/80" />
    </div>
  )
}

function EvaluationEntry({ evaluationId }: { evaluationId: string }) {
  const [evaluation, setEvaluation] = useState<Evaluation | null>(() => EVALUATION_CACHE.get(evaluationId) ?? null)
  const [isInitialLoading, setIsInitialLoading] = useState<boolean>(() => !EVALUATION_CACHE.has(evaluationId))
  const [isHydrating, setIsHydrating] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      try {
        const cached = EVALUATION_CACHE.get(evaluationId)
        let baseEvaluation = cached
        let baseRaw: any = null

        if (!cached) {
          setIsInitialLoading(true)
          const light = await fetchEvaluationLight(evaluationId)
          if (cancelled) return
          baseEvaluation = light.evaluation
          baseRaw = light.raw
          EVALUATION_CACHE.set(evaluationId, light.evaluation)
          setEvaluation(light.evaluation)
          setIsInitialLoading(false)
        } else {
          setEvaluation(cached)
          setIsInitialLoading(false)
        }

        if (HYDRATED_EVALUATION_IDS.has(evaluationId)) {
          return
        }

        setIsHydrating(true)

        if (!baseRaw) {
          const light = await fetchEvaluationLight(evaluationId)
          if (cancelled) return
          baseRaw = light.raw
          baseEvaluation = light.evaluation
        }

        const scoreResults = await fetchScoreResultsForEvaluation(evaluationId)
        if (cancelled) return

        const hydratedRaw = {
          ...baseRaw,
          scoreResults: { items: scoreResults },
        }
        const hydratedEvaluation = transformEvaluation(hydratedRaw) as Evaluation | null
        if (hydratedEvaluation) {
          EVALUATION_CACHE.set(evaluationId, hydratedEvaluation)
          HYDRATED_EVALUATION_IDS.add(evaluationId)
          setEvaluation(hydratedEvaluation)
        } else if (baseEvaluation) {
          EVALUATION_CACHE.set(evaluationId, baseEvaluation)
          setEvaluation(baseEvaluation)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : `Could not load evaluation ${evaluationId}`)
          setIsInitialLoading(false)
        }
      } finally {
        if (!cancelled) {
          setIsHydrating(false)
        }
      }
    }

    run()
    return () => {
      cancelled = true
    }
  }, [evaluationId])

  if (isInitialLoading && !evaluation) {
    return <EvaluationEntrySkeleton />
  }

  if (error || !evaluation) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground p-2">
        <AlertCircle className="h-3 w-3" />
        {error || `Could not load evaluation ${evaluationId}`}
      </div>
    )
  }

  return (
    <div className="space-y-1" data-testid="evaluation-entry">
      <Link href={`/lab/evaluations/${evaluationId}`} className="block hover:opacity-90 transition-opacity">
        <TaskDisplay
          variant="grid"
          task={evaluation.task}
          evaluationData={buildEvaluationData(evaluation)}
          extra
        />
      </Link>
      {isHydrating && (
        <div className="text-[11px] text-muted-foreground px-1">Hydrating score results…</div>
      )}
    </div>
  )
}

export default function EvaluationToolOutput({ toolOutput }: EvaluationToolOutputProps) {
  const [showRawOutput, setShowRawOutput] = useState(false)

  const parsed = useMemo(() => parseToolOutput(toolOutput), [toolOutput])
  const evaluationIds = useMemo(() => extractEvaluationIds(parsed), [parsed])

  const rawOutputText = useMemo(() => formatJson(toolOutput), [toolOutput])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(rawOutputText)
      toast.success("Copied to clipboard")
    } catch {
      toast.error("Failed to copy to clipboard")
    }
  }

  if (evaluationIds.length === 0) {
    return (
      <div className="font-mono whitespace-pre-wrap break-words text-sm">
        {rawOutputText}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="space-y-4">
        {evaluationIds.map(id => (
          <EvaluationEntry key={id} evaluationId={id} />
        ))}
      </div>

      <div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setShowRawOutput(!showRawOutput)}
          className="h-8 bg-card hover:bg-card/90 border-0"
        >
          <MessageSquareCode className="mr-2 h-4 w-4" />
          {showRawOutput ? "Hide Code" : "Code"}
        </Button>
      </div>

      {showRawOutput && (
        <div className="bg-card p-3 overflow-hidden rounded-lg">
          <div className="flex flex-row justify-between items-center mb-3">
            <h4 className="text-sm font-medium">Tool Output (JSON)</h4>
            <CardButton
              icon={Copy}
              onClick={handleCopy}
              label="Copy"
              aria-label="Copy to clipboard"
            />
          </div>
          <pre className="whitespace-pre-wrap text-xs bg-card text-foreground overflow-y-auto overflow-x-auto font-mono max-h-[400px] px-2 py-2 max-w-full rounded">
            {rawOutputText}
          </pre>
        </div>
      )}
    </div>
  )
}
