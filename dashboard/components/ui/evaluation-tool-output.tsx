"use client"

import React, { useState, useMemo } from 'react'
import Link from 'next/link'
import { MessageSquareCode, Copy, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CardButton } from '@/components/CardButton'
import { TaskDisplay } from '@/components/TaskDisplay'
import { useEvaluationById } from '@/hooks/useEvaluationById'
import { toast } from 'sonner'
import type { Evaluation } from '@/utils/data-operations'

interface EvaluationToolOutputProps {
  toolOutput: unknown
}

function parseToolOutput(output: unknown): unknown {
  if (!output) return null
  if (typeof output === 'string') {
    // Try direct JSON parse first
    try {
      return JSON.parse(output)
    } catch {
      // The tool response may be stored as a content string with format:
      // "Response from tool: <name>\n\nResponse:\n<json>"
      // Extract the JSON portion after the "Response:\n" separator
      const responseMatch = output.match(/\n\nResponse:\n([\s\S]+)$/)
      if (responseMatch) {
        try {
          return JSON.parse(responseMatch[1].trim())
        } catch {
          // Not valid JSON
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
  }
}

function EvaluationEntry({ evaluationId }: { evaluationId: string }) {
  const { evaluation, isLoading, error } = useEvaluationById(evaluationId)

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-3 text-sm text-muted-foreground">
        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-foreground" />
        Loading evaluation...
      </div>
    )
  }

  if (error || !evaluation) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground p-2">
        <AlertCircle className="h-3 w-3" />
        Could not load evaluation {evaluationId}
      </div>
    )
  }

  return (
    <Link href={`/lab/evaluations/${evaluationId}`} className="block hover:opacity-90 transition-opacity">
      <TaskDisplay
        variant="grid"
        task={evaluation.task}
        evaluationData={buildEvaluationData(evaluation)}
      />
    </Link>
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

  // No evaluation IDs found — show raw output
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
