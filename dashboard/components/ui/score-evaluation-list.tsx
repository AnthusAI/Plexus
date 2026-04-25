'use client'

import * as React from 'react'
import { Copy, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import EvaluationTask, { type EvaluationTaskData } from '@/components/EvaluationTask'
import { cn } from '@/lib/utils'
import {
  copyText,
  loadScoreEvaluations,
  type ScoreEvaluationView,
} from '@/components/ui/optimizer-results-utils'

type EvaluationScope = 'score' | 'version'
type EvaluationSort = 'updated' | 'accuracy' | 'alignment'
type EvaluationTaskStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'STALLED'

export interface ScoreEvaluationListProps {
  scoreId: string
  scope: EvaluationScope
  versionId?: string | null
  showHeader?: boolean
  className?: string
}

function sortEvaluations(items: ScoreEvaluationView[], sortBy: EvaluationSort) {
  const updatedAtMs = (item: ScoreEvaluationView) => new Date(item.updatedAt ?? item.createdAt ?? 0).getTime()

  return [...items].sort((left, right) => {
    if (sortBy === 'accuracy') {
      const leftAccuracy = typeof left.accuracy === 'number'
      const rightAccuracy = typeof right.accuracy === 'number'
      if (leftAccuracy && rightAccuracy && left.accuracy !== right.accuracy) return right.accuracy! - left.accuracy!
      if (leftAccuracy !== rightAccuracy) return leftAccuracy ? -1 : 1
      return updatedAtMs(right) - updatedAtMs(left)
    }

    if (sortBy === 'alignment') {
      const leftAlignment = typeof left.alignment === 'number'
      const rightAlignment = typeof right.alignment === 'number'
      if (leftAlignment && rightAlignment && left.alignment !== right.alignment) return right.alignment! - left.alignment!
      if (leftAlignment !== rightAlignment) return leftAlignment ? -1 : 1
      return updatedAtMs(right) - updatedAtMs(left)
    }

    return updatedAtMs(right) - updatedAtMs(left)
  })
}

function titleCase(value: string) {
  if (!value) return value
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function normalizeTaskStatus(status: string | null | undefined): EvaluationTaskStatus {
  const normalized = String(status ?? '').toUpperCase()
  if (normalized === 'RUNNING') return 'RUNNING'
  if (normalized === 'COMPLETED') return 'COMPLETED'
  if (normalized === 'FAILED') return 'FAILED'
  if (normalized === 'STALLED') return 'STALLED'
  return 'PENDING'
}

function toEvaluationTaskData(evaluation: ScoreEvaluationView): EvaluationTaskData {
  const type = evaluation.type ?? 'unknown'
  const status = normalizeTaskStatus(evaluation.task?.status ?? evaluation.status)
  const timestamp = evaluation.updatedAt ?? evaluation.createdAt ?? new Date().toISOString()
  const processedItems = typeof evaluation.processedItems === 'number' ? evaluation.processedItems : 0
  const totalItems = typeof evaluation.totalItems === 'number' ? evaluation.totalItems : 0
  const progress = totalItems > 0 ? Math.round((processedItems / totalItems) * 100) : 0
  const metrics = [
    typeof evaluation.accuracy === 'number'
      ? { name: 'Accuracy', value: evaluation.accuracy, priority: true, maximum: 1, unit: '%' }
      : null,
    typeof evaluation.alignment === 'number'
      ? { name: 'Alignment', value: evaluation.alignment, priority: true, maximum: 1 }
      : null,
  ].filter((metric): metric is NonNullable<typeof metric> => metric !== null)

  return {
    id: evaluation.id,
    title: `${titleCase(type)} Evaluation`,
    accuracy: evaluation.accuracy ?? null,
    metrics,
    processedItems,
    totalItems,
    progress,
    inferences: 0,
    cost: null,
    status,
    elapsedSeconds: evaluation.elapsedSeconds ?? null,
    estimatedRemainingSeconds: evaluation.estimatedRemainingSeconds ?? null,
    baseline_evaluation_id: evaluation.baselineEvaluationId ?? null,
    current_baseline_evaluation_id: evaluation.currentBaselineEvaluationId ?? null,
    task: {
      id: evaluation.task?.id ?? `task-${evaluation.id}`,
      accountId: '',
      type: evaluation.task?.type ?? `${titleCase(type)} Evaluation`,
      status,
      target: evaluation.task?.target ?? evaluation.id,
      command: evaluation.task?.command ?? '',
      description: evaluation.task?.description ?? undefined,
      dispatchStatus: evaluation.task?.dispatchStatus === 'DISPATCHED' ? 'DISPATCHED' : undefined,
      createdAt: evaluation.task?.createdAt ?? timestamp,
      startedAt: evaluation.task?.startedAt ?? undefined,
      completedAt: evaluation.task?.completedAt ?? undefined,
      estimatedCompletionAt: evaluation.task?.estimatedCompletionAt ?? undefined,
      errorMessage: evaluation.task?.errorMessage ?? undefined,
      errorDetails:
        typeof evaluation.task?.errorDetails === 'string'
          ? evaluation.task.errorDetails
          : evaluation.task?.errorDetails != null
            ? JSON.stringify(evaluation.task.errorDetails)
            : undefined,
      currentStageId: evaluation.task?.currentStageId ?? undefined,
      stages: {
        items:
          evaluation.task?.stages?.items?.map((stage) => ({
            id: stage.id,
            name: stage.name,
            order: stage.order,
            status: stage.status,
            statusMessage: stage.statusMessage ?? undefined,
            startedAt: stage.startedAt ?? undefined,
            completedAt: stage.completedAt ?? undefined,
            estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
            processedItems: stage.processedItems ?? undefined,
            totalItems: stage.totalItems ?? undefined,
          })) ?? [],
      },
    },
  }
}

export function ScoreEvaluationList({
  scoreId,
  scope,
  versionId = null,
  showHeader = true,
  className,
}: ScoreEvaluationListProps) {
  const [evaluations, setEvaluations] = React.useState<ScoreEvaluationView[]>([])
  const [isLoading, setIsLoading] = React.useState(false)
  const [sortBy, setSortBy] = React.useState<EvaluationSort>('updated')
  const [statusFilter, setStatusFilter] = React.useState('all')
  const [typeFilter, setTypeFilter] = React.useState('all')

  React.useEffect(() => {
    let cancelled = false

    const loadEvaluations = async () => {
      setIsLoading(true)
      try {
        const loadedEvaluations = await loadScoreEvaluations(scoreId)
        if (!cancelled) {
          setEvaluations(loadedEvaluations)
        }
      } catch (error) {
        console.error('Failed to load evaluations:', error)
        if (!cancelled) {
          toast.error('Failed to load evaluations')
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    void loadEvaluations()
    return () => {
      cancelled = true
    }
  }, [scoreId])

  const visibleEvaluations = React.useMemo(() => {
    const filteredByScope =
      scope === 'version' && versionId
        ? evaluations.filter((evaluation) => evaluation.scoreVersionId === versionId)
        : evaluations

    const filtered = filteredByScope.filter((evaluation) => {
      if (statusFilter !== 'all' && (evaluation.status ?? 'unknown') !== statusFilter) return false
      if (typeFilter !== 'all' && (evaluation.type ?? 'unknown') !== typeFilter) return false
      return true
    })

    return sortEvaluations(filtered, sortBy)
  }, [evaluations, scope, sortBy, statusFilter, typeFilter, versionId])

  const statuses = React.useMemo(
    () => ['all', ...new Set(evaluations.map((evaluation) => evaluation.status ?? 'unknown'))],
    [evaluations]
  )
  const types = React.useMemo(
    () => ['all', ...new Set(evaluations.map((evaluation) => evaluation.type ?? 'unknown'))],
    [evaluations]
  )

  const title = scope === 'score' ? 'Evaluations' : 'Version Evaluations'
  const description =
    scope === 'score'
      ? 'All evaluations for this score, newest first by default.'
      : 'Evaluations created for the selected version.'

  if (scope === 'version' && !versionId) {
    return (
      <div className={cn('h-full min-h-0 rounded-md bg-muted/50 p-4', className)}>
        <div className="text-sm text-muted-foreground">Select a version to inspect its evaluations.</div>
      </div>
    )
  }

  return (
    <div className={cn('flex h-full min-h-0 flex-col', className)}>
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="px-4 pb-4">
        {showHeader && (
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold">{title}</h3>
              <p className="text-sm text-muted-foreground">{description}</p>
            </div>
            {isLoading && <span className="text-sm text-muted-foreground">Loading…</span>}
          </div>
        )}

        <div className="mb-4 flex flex-wrap items-center gap-3">
          <label className="text-sm text-muted-foreground" htmlFor={`evaluation-sort-${scope}`}>
            Sort
          </label>
          <select
            id={`evaluation-sort-${scope}`}
            className="rounded-md border-0 bg-background px-3 py-1.5 text-sm focus:outline-none"
            value={sortBy}
            onChange={(event) => setSortBy(event.target.value as EvaluationSort)}
          >
            <option value="updated">Updated</option>
            <option value="accuracy">Accuracy</option>
            <option value="alignment">Alignment</option>
          </select>

          <label className="text-sm text-muted-foreground" htmlFor={`evaluation-status-${scope}`}>
            Status
          </label>
          <select
            id={`evaluation-status-${scope}`}
            className="rounded-md border-0 bg-background px-3 py-1.5 text-sm focus:outline-none"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            {statuses.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>

          <label className="text-sm text-muted-foreground" htmlFor={`evaluation-type-${scope}`}>
            Type
          </label>
          <select
            id={`evaluation-type-${scope}`}
            className="rounded-md border-0 bg-background px-3 py-1.5 text-sm focus:outline-none"
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
          >
            {types.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-3">
          {!isLoading && visibleEvaluations.length === 0 && (
            <div className="text-sm text-muted-foreground">No evaluations found for this scope yet.</div>
          )}
          {visibleEvaluations.map((evaluation, index) => {
            const type = titleCase(evaluation.type ?? 'unknown')
            const status = normalizeTaskStatus(evaluation.task?.status ?? evaluation.status)
            const timestamp = evaluation.updatedAt ?? evaluation.createdAt ?? new Date().toISOString()
            const description = [
              `${type} · ${status}`,
              `Version: ${evaluation.scoreVersionId || '—'}`,
            ].join(' · ')

            return (
            <div
              key={evaluation.id}
              className={index % 2 === 0 ? '' : 'bg-muted/60'}
            >
              <EvaluationTask
                variant="grid"
                extra
                task={{
                  id: evaluation.id,
                  type: `${type} Evaluation`,
                  scorecard: '',
                  score: '',
                  time: timestamp,
                  description,
                  status,
                  scoreVersionId: evaluation.scoreVersionId ?? undefined,
                  data: toEvaluationTaskData(evaluation),
                }}
                controlButtons={
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <Button variant="secondary" size="sm" asChild>
                      <a href={`/lab/evaluations/${evaluation.id}`} target="_blank" rel="noreferrer">
                        <ExternalLink className="mr-2 h-3.5 w-3.5" />
                        Open
                      </a>
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => void copyText(`/lab/evaluations/${evaluation.id}`, 'Evaluation path copied')}
                    >
                      <Copy className="mr-2 h-3.5 w-3.5" />
                      Path
                    </Button>
                  </div>
                }
              />
            </div>
            )
          })}
        </div>
        </div>
      </div>
    </div>
  )
}
