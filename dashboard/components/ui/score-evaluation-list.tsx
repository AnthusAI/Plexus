'use client'

import * as React from 'react'
import { generateClient } from 'aws-amplify/api'
import { Copy, Link as LinkIcon, MoreHorizontal } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import EvaluationTask, { type EvaluationTaskData } from '@/components/EvaluationTask'
import { cn } from '@/lib/utils'
import {
  copyText,
  EVALUATION_CREATE_SUBSCRIPTION_FOR_CARDS,
  EVALUATION_DELETE_SUBSCRIPTION_FOR_CARDS,
  EVALUATION_UPDATE_SUBSCRIPTION_FOR_CARDS,
  evaluationToScoreEvaluationView,
  loadScoreEvaluations,
  mergeTaskIntoEvaluation,
  mergeTaskStageIntoEvaluation,
  taskMatchesEvaluation,
  TASK_CREATE_SUBSCRIPTION_FOR_CARDS,
  TASK_STAGE_CREATE_SUBSCRIPTION_FOR_CARDS,
  TASK_STAGE_UPDATE_SUBSCRIPTION_FOR_CARDS,
  TASK_UPDATE_SUBSCRIPTION_FOR_CARDS,
  type ScoreEvaluationView,
} from '@/components/ui/optimizer-results-utils'

type EvaluationScope = 'score' | 'version'
type EvaluationSort = 'updated' | 'alignment' | 'accuracy' | 'precision' | 'recall' | 'cost'
type EvaluationTaskStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'STALLED'

const getAmplifyClient = (() => {
  let client: any = null
  return () => (client ??= generateClient())
})()

export interface ScoreEvaluationListProps {
  scoreId: string
  scope: EvaluationScope
  versionId?: string | null
  showHeader?: boolean
  surface?: 'plain' | 'slot'
  className?: string
}

function sortEvaluations(items: ScoreEvaluationView[], sortBy: EvaluationSort) {
  const updatedAtMs = (item: ScoreEvaluationView) => new Date(item.updatedAt ?? item.createdAt ?? 0).getTime()
  const sortMetric = (
    left: ScoreEvaluationView,
    right: ScoreEvaluationView,
    metric: Exclude<EvaluationSort, 'updated'>,
    direction: 'asc' | 'desc' = 'desc'
  ) => {
    const leftValue = left[metric]
    const rightValue = right[metric]
    const leftHasMetric = typeof leftValue === 'number'
    const rightHasMetric = typeof rightValue === 'number'
    if (leftHasMetric && rightHasMetric && leftValue !== rightValue) {
      return direction === 'asc' ? leftValue! - rightValue! : rightValue! - leftValue!
    }
    if (leftHasMetric !== rightHasMetric) return leftHasMetric ? -1 : 1
    return updatedAtMs(right) - updatedAtMs(left)
  }

  return [...items].sort((left, right) => {
    if (sortBy !== 'updated') {
      return sortMetric(left, right, sortBy, sortBy === 'cost' ? 'asc' : 'desc')
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

function EvaluationListSkeleton() {
  return (
    <div className="space-y-3" aria-label="Loading evaluations">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="rounded-lg bg-card p-4">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div className="space-y-2">
              <div className="h-4 w-48 rounded bg-muted animate-pulse" />
              <div className="h-3 w-72 rounded bg-muted animate-pulse" />
            </div>
            <div className="h-8 w-20 rounded bg-muted animate-pulse" />
          </div>
          <div className="space-y-2">
            <div className="h-3 w-full rounded bg-muted animate-pulse" />
            <div className="h-3 w-3/4 rounded bg-muted animate-pulse" />
          </div>
        </div>
      ))}
    </div>
  )
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
    typeof evaluation.precision === 'number'
      ? { name: 'Precision', value: evaluation.precision, priority: false, maximum: 1 }
      : null,
    typeof evaluation.recall === 'number'
      ? { name: 'Recall', value: evaluation.recall, priority: false, maximum: 1 }
      : null,
    typeof evaluation.cost === 'number'
      ? { name: 'Cost', value: evaluation.cost, priority: false, unit: '$' }
      : null,
  ].filter((metric): metric is NonNullable<typeof metric> => metric !== null)
  const parameters =
    evaluation.parameters == null
      ? null
      : typeof evaluation.parameters === 'string'
        ? evaluation.parameters
        : JSON.stringify(evaluation.parameters)

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
    parameters,
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
  surface = 'plain',
  className,
}: ScoreEvaluationListProps) {
  const [evaluations, setEvaluations] = React.useState<ScoreEvaluationView[]>([])
  const [isLoading, setIsLoading] = React.useState(false)
  const [isApplyingControls, setIsApplyingControls] = React.useState(false)
  const [sortBy, setSortBy] = React.useState<EvaluationSort>('updated')
  const [statusFilter, setStatusFilter] = React.useState('all')
  const [typeFilter, setTypeFilter] = React.useState('all')
  const controlLoadingTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  React.useEffect(() => {
    return () => {
      if (controlLoadingTimeoutRef.current) {
        clearTimeout(controlLoadingTimeoutRef.current)
      }
    }
  }, [])

  React.useEffect(() => {
    let cancelled = false

    const loadEvaluations = async () => {
      setEvaluations([])
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

  React.useEffect(() => {
    if (!scoreId) return

    const subscriptions: Array<{ unsubscribe: () => void }> = []
    const subscribe = (query: string, onNext: (data: any) => void, label: string) => {
      try {
        const result = getAmplifyClient().graphql({ query }) as any
        if (!result || typeof result.subscribe !== 'function') return
        const subscription = result.subscribe({
          next: ({ data }: { data?: any }) => onNext(data),
          error: (error: Error) => {
            console.error(`${label} subscription error:`, error)
          },
        })
        subscriptions.push(subscription)
      } catch (error) {
        console.error(`Failed to set up ${label} subscription:`, error)
      }
    }

    const upsertEvaluation = (rawEvaluation: any) => {
      if (!rawEvaluation?.id) return
      if (rawEvaluation.scoreId && rawEvaluation.scoreId !== scoreId) return
      const nextEvaluation = evaluationToScoreEvaluationView(rawEvaluation)
      setEvaluations((previous) => {
        const existingIndex = previous.findIndex((evaluation) => evaluation.id === nextEvaluation.id)
        if (existingIndex < 0) return [nextEvaluation, ...previous]
        const next = [...previous]
        next[existingIndex] = {
          ...previous[existingIndex],
          ...nextEvaluation,
          task: nextEvaluation.task ?? previous[existingIndex].task,
        }
        return next
      })
    }

    subscribe(
      EVALUATION_CREATE_SUBSCRIPTION_FOR_CARDS,
      (data) => upsertEvaluation(data?.onCreateEvaluation),
      'create evaluation'
    )
    subscribe(
      EVALUATION_UPDATE_SUBSCRIPTION_FOR_CARDS,
      (data) => upsertEvaluation(data?.onUpdateEvaluation),
      'update evaluation'
    )
    subscribe(
      EVALUATION_DELETE_SUBSCRIPTION_FOR_CARDS,
      (data) => {
        const deleted = data?.onDeleteEvaluation
        if (!deleted?.id) return
        if (deleted.scoreId && deleted.scoreId !== scoreId) return
        setEvaluations((previous) => previous.filter((evaluation) => evaluation.id !== deleted.id))
      },
      'delete evaluation'
    )
    subscribe(
      TASK_CREATE_SUBSCRIPTION_FOR_CARDS,
      (data) => {
        const task = data?.onCreateTask
        if (!task?.id) return
        setEvaluations((previous) =>
          previous.map((evaluation) =>
            taskMatchesEvaluation(task, evaluation) ? mergeTaskIntoEvaluation(evaluation, task) : evaluation
          )
        )
      },
      'task create'
    )
    subscribe(
      TASK_UPDATE_SUBSCRIPTION_FOR_CARDS,
      (data) => {
        const task = data?.onUpdateTask
        if (!task?.id) return
        setEvaluations((previous) =>
          previous.map((evaluation) =>
            taskMatchesEvaluation(task, evaluation) ? mergeTaskIntoEvaluation(evaluation, task) : evaluation
          )
        )
      },
      'task update'
    )
    subscribe(
      TASK_STAGE_CREATE_SUBSCRIPTION_FOR_CARDS,
      (data) => {
        const stage = data?.onCreateTaskStage
        if (!stage?.taskId) return
        setEvaluations((previous) =>
          previous.map((evaluation) => mergeTaskStageIntoEvaluation(evaluation, stage))
        )
      },
      'task stage create'
    )
    subscribe(
      TASK_STAGE_UPDATE_SUBSCRIPTION_FOR_CARDS,
      (data) => {
        const stage = data?.onUpdateTaskStage
        if (!stage?.taskId) return
        setEvaluations((previous) =>
          previous.map((evaluation) => mergeTaskStageIntoEvaluation(evaluation, stage))
        )
      },
      'task stage update'
    )

    return () => {
      subscriptions.forEach((subscription) => {
        try {
          subscription.unsubscribe()
        } catch {
          // Ignore unsubscribe errors from already-closed observables.
        }
      })
    }
  }, [scoreId])

  const applyControlChange = React.useCallback((apply: () => void) => {
    if (controlLoadingTimeoutRef.current) {
      clearTimeout(controlLoadingTimeoutRef.current)
    }
    setIsApplyingControls(true)
    apply()
    controlLoadingTimeoutRef.current = setTimeout(() => {
      setIsApplyingControls(false)
      controlLoadingTimeoutRef.current = null
    }, 120)
  }, [])

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
  const usesSlotSurface = surface === 'slot'
  const shouldShowListSkeleton = isLoading || isApplyingControls

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
        <div className={cn(usesSlotSurface ? 'h-full' : 'px-4 pb-4')}>
        <div className={cn(usesSlotSurface && 'min-h-full bg-background p-3')}>
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
            onChange={(event) => applyControlChange(() => setSortBy(event.target.value as EvaluationSort))}
          >
            <option value="updated">Updated</option>
            <option value="alignment">Alignment</option>
            <option value="accuracy">Accuracy</option>
            <option value="precision">Precision</option>
            <option value="recall">Recall</option>
            <option value="cost">Cost</option>
          </select>

          <label className="text-sm text-muted-foreground" htmlFor={`evaluation-status-${scope}`}>
            Status
          </label>
          <select
            id={`evaluation-status-${scope}`}
            className="rounded-md border-0 bg-background px-3 py-1.5 text-sm focus:outline-none"
            value={statusFilter}
            onChange={(event) => applyControlChange(() => setStatusFilter(event.target.value))}
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
            onChange={(event) => applyControlChange(() => setTypeFilter(event.target.value))}
          >
            {types.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>

        {shouldShowListSkeleton ? (
          <EvaluationListSkeleton />
        ) : (
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
              className={!usesSlotSurface && index % 2 !== 0 ? 'bg-muted/60' : ''}
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
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 rounded-md bg-border"
                        aria-label="More options"
                      >
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem asChild>
                        <a href={`/lab/evaluations/${evaluation.id}`} target="_blank" rel="noreferrer">
                          <LinkIcon className="mr-2 h-3.5 w-3.5" />
                          Open evaluation
                        </a>
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onSelect={() => void copyText(`/lab/evaluations/${evaluation.id}`, 'Evaluation path copied')}
                      >
                        <Copy className="mr-2 h-3.5 w-3.5" />
                        Copy evaluation path
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onSelect={() => void copyText(evaluation.id, 'Evaluation ID copied')}
                      >
                        <Copy className="mr-2 h-3.5 w-3.5" />
                        Copy evaluation ID
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                }
              />
            </div>
            )
          })}
        </div>
        )}
        </div>
        </div>
      </div>
    </div>
  )
}
