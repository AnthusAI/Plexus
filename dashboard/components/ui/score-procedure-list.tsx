'use client'

import * as React from 'react'
import { Copy, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import ProcedureTask, { type ProcedureTaskData } from '@/components/ProcedureTask'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import {
  copyText,
  evaluationUrl,
  loadOptimizerRuns,
  manifestTouchesVersion,
  openArtifactText,
  scorecardGuideRelativePath,
  type OptimizerRunView,
} from '@/components/ui/optimizer-results-utils'

type ProcedureScope = 'score' | 'version'
type ProcedureSort = 'updated' | 'status' | 'cycles' | 'feedback' | 'accuracy'

export interface ScoreProcedureListProps {
  scoreId: string
  scoreName: string
  scorecardName: string
  scope: ProcedureScope
  versionId?: string | null
  showHeader?: boolean
  className?: string
}

function sortProcedureRuns(runs: OptimizerRunView[], sortBy: ProcedureSort) {
  const updatedAtMs = (run: OptimizerRunView) => new Date(run.updatedAt ?? 0).getTime()
  const completedCycles = (run: OptimizerRunView) => run.manifest?.summary?.completed_cycles ?? -1
  const feedbackAlignment = (run: OptimizerRunView) =>
    run.manifest?.best?.winning_feedback_metrics?.alignment ??
    run.manifest?.best?.best_feedback_alignment ??
    null
  const accuracyAlignment = (run: OptimizerRunView) =>
    run.manifest?.best?.winning_accuracy_metrics?.alignment ??
    run.manifest?.best?.best_accuracy_alignment ??
    null

  const sortMetricDesc = (left: number | null, right: number | null, leftRun: OptimizerRunView, rightRun: OptimizerRunView) => {
    const leftHasMetric = typeof left === 'number'
    const rightHasMetric = typeof right === 'number'
    if (leftHasMetric && rightHasMetric && left !== right) return right! - left!
    if (leftHasMetric !== rightHasMetric) return leftHasMetric ? -1 : 1
    return updatedAtMs(rightRun) - updatedAtMs(leftRun)
  }

  return [...runs].sort((left, right) => {
    if (sortBy === 'status') {
      const statusCompare = String(left.status ?? '').localeCompare(String(right.status ?? ''))
      return statusCompare !== 0 ? statusCompare : updatedAtMs(right) - updatedAtMs(left)
    }
    if (sortBy === 'cycles') {
      const delta = completedCycles(right) - completedCycles(left)
      return delta !== 0 ? delta : updatedAtMs(right) - updatedAtMs(left)
    }
    if (sortBy === 'feedback') {
      return sortMetricDesc(feedbackAlignment(left), feedbackAlignment(right), left, right)
    }
    if (sortBy === 'accuracy') {
      return sortMetricDesc(accuracyAlignment(left), accuracyAlignment(right), left, right)
    }
    return updatedAtMs(right) - updatedAtMs(left)
  })
}

function toProcedureTaskData(
  run: OptimizerRunView,
  scorecardName: string,
  scoreName: string
): ProcedureTaskData {
  const summary = run.manifest?.summary
  const best = run.manifest?.best
  const descriptionParts = [
    summary?.completed_cycles != null || summary?.configured_max_iterations != null
      ? `Cycles: ${summary?.completed_cycles ?? '—'}/${summary?.configured_max_iterations ?? '—'}`
      : null,
    summary?.stop_reason ? `Stop: ${summary.stop_reason}` : null,
    best?.winning_version_id ? `Winning: ${best.winning_version_id}` : null,
  ].filter(Boolean)

  return {
    id: run.procedureId,
    title: run.name || run.procedureId,
    featured: false,
    createdAt: run.updatedAt || new Date().toISOString(),
    updatedAt: run.updatedAt || new Date().toISOString(),
    status: run.status || 'PENDING',
    scorecard: scorecardNameFromRun(scorecardName),
    score: scoreFromRun(scoreName),
    description: descriptionParts.join(' · '),
    taskId: run.procedureId,
    task: {
      id: run.procedureId,
      type: 'Procedure',
      status: run.status || 'PENDING',
      target: run.procedureId,
      command: '',
      description: descriptionParts.join(' · '),
      createdAt: run.updatedAt || new Date().toISOString(),
      stages: { items: [] },
    },
  }
}

function scorecardNameFromRun(scorecardName: string) {
  return scorecardName ? { id: '', name: scorecardName } : null
}

function scoreFromRun(scoreName: string) {
  return scoreName ? { id: '', name: scoreName } : null
}

export function ScoreProcedureList({
  scoreId,
  scoreName,
  scorecardName,
  scope,
  versionId = null,
  showHeader = true,
  className,
}: ScoreProcedureListProps) {
  const [runs, setRuns] = React.useState<OptimizerRunView[]>([])
  const [isLoading, setIsLoading] = React.useState(false)
  const [artifactViewer, setArtifactViewer] = React.useState<{
    title: string
    content: string
  } | null>(null)
  const [sortBy, setSortBy] = React.useState<ProcedureSort>('updated')

  React.useEffect(() => {
    let cancelled = false

    const loadRuns = async () => {
      setIsLoading(true)
      try {
        const loadedRuns = await loadOptimizerRuns(scoreId)
        if (!cancelled) {
          setRuns(loadedRuns)
        }
      } catch (error) {
        console.error('Failed to load procedures:', error)
        if (!cancelled) {
          toast.error('Failed to load procedures')
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    void loadRuns()
    return () => {
      cancelled = true
    }
  }, [scoreId])

  const visibleRuns = React.useMemo(() => {
    const filtered = scope === 'version' && versionId
      ? runs.filter((run) => {
          if (manifestTouchesVersion(run.manifest, versionId)) return true
          return run.scoreVersionId === versionId
        })
      : runs
    return sortProcedureRuns(filtered, sortBy)
  }, [runs, scope, sortBy, versionId])

  const title = scope === 'score' ? 'Procedures' : 'Version Procedures'
  const description =
    scope === 'score'
      ? 'All procedures for this score, newest first by default.'
      : 'Procedures that touched the selected version.'

  const openArtifactViewer = React.useCallback(async (artifactKey: string | null | undefined, title: string) => {
    if (!artifactKey) {
      toast.error(`${title} is not available for this run`)
      return
    }
    try {
      const content = await openArtifactText(artifactKey)
      setArtifactViewer({ title, content })
    } catch (error) {
      console.error(`Failed to load ${title}:`, error)
      toast.error(`Failed to load ${title}`)
    }
  }, [])

  if (scope === 'version' && !versionId) {
    return (
      <div className={cn('h-full min-h-0 rounded-md bg-muted/50 p-4', className)}>
        <div className="text-sm text-muted-foreground">Select a version to inspect its procedures.</div>
      </div>
    )
  }

  return (
    <div className={cn('flex h-full min-h-0 flex-col', className)}>
      <div className="flex-1 min-h-0 overflow-y-auto p-4">
        <div className="rounded-md bg-muted/40 p-4">
        {showHeader && (
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold">{title}</h3>
              <p className="text-sm text-muted-foreground">{description}</p>
            </div>
            {isLoading && <span className="text-sm text-muted-foreground">Loading…</span>}
          </div>
        )}

        <div className="mb-4 flex items-center gap-3">
          <label className="text-sm text-muted-foreground" htmlFor={`procedure-sort-${scope}`}>
            Sort
          </label>
          <select
            id={`procedure-sort-${scope}`}
            className="rounded-md border-0 bg-background px-3 py-1.5 text-sm focus:outline-none"
            value={sortBy}
            onChange={(event) => setSortBy(event.target.value as ProcedureSort)}
          >
            <option value="updated">Updated</option>
            <option value="status">Status</option>
            <option value="cycles">Completed cycles</option>
            <option value="feedback">Best feedback alignment</option>
            <option value="accuracy">Best accuracy alignment</option>
          </select>
        </div>

        <div className="space-y-3">
          {!isLoading && visibleRuns.length === 0 && (
            <div className="text-sm text-muted-foreground">No procedures found for this scope yet.</div>
          )}
          {visibleRuns.map((run, index) => {
            const summary = run.manifest?.summary
            const best = run.manifest?.best
            const winningVersionId = best?.winning_version_id ?? null

            return (
              <div
                key={run.procedureId}
                className={`rounded-md ${index % 2 === 0 ? 'bg-background' : 'bg-muted/60'}`}
              >
                <ProcedureTask
                  variant="grid"
                  procedure={toProcedureTaskData(run, scorecardName, scoreName)}
                  controlButtons={
                    <div className="flex flex-wrap items-center justify-end gap-2">
                      <Button variant="secondary" size="sm" asChild>
                        <a href={`/lab/procedures/${run.procedureId}`} target="_blank" rel="noreferrer">
                          <ExternalLink className="mr-2 h-3.5 w-3.5" />
                          Open
                        </a>
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => void copyText(run.procedureId, 'Procedure ID copied')}
                      >
                        <Copy className="mr-2 h-3.5 w-3.5" />
                        ID
                      </Button>
                      {!run.indexed && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() =>
                            void copyText(
                              `plexus procedure index-optimizer-run ${run.procedureId}`,
                              'Index command copied'
                            )
                          }
                        >
                          <Copy className="mr-2 h-3.5 w-3.5" />
                          Index
                        </Button>
                      )}
                      {winningVersionId && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() =>
                            void copyText(
                              JSON.stringify(
                                {
                                  score: scoreName,
                                  version_id: winningVersionId,
                                  feedback_evaluation_url: evaluationUrl(best?.best_feedback_evaluation_id),
                                  accuracy_evaluation_url: evaluationUrl(best?.best_accuracy_evaluation_id),
                                  guidelines_relative_path: scorecardGuideRelativePath(scorecardName, scoreName),
                                },
                                null,
                                2
                              ),
                              'Promotion packet copied'
                            )
                          }
                        >
                          <Copy className="mr-2 h-3.5 w-3.5" />
                          Packet
                        </Button>
                      )}
                      {run.artifactPointer?.runtime_log && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => void openArtifactViewer(run.artifactPointer?.runtime_log, 'Runtime log')}
                        >
                          Log
                        </Button>
                      )}
                      {run.artifactPointer?.events && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => void openArtifactViewer(run.artifactPointer?.events, 'Event stream')}
                        >
                          Events
                        </Button>
                      )}
                      {best?.best_feedback_evaluation_id && (
                        <Button variant="secondary" size="sm" asChild>
                          <a href={evaluationUrl(best.best_feedback_evaluation_id) ?? '#'} target="_blank" rel="noreferrer">
                            <ExternalLink className="mr-2 h-3.5 w-3.5" />
                            FB
                          </a>
                        </Button>
                      )}
                      {best?.best_accuracy_evaluation_id && (
                        <Button variant="secondary" size="sm" asChild>
                          <a href={evaluationUrl(best.best_accuracy_evaluation_id) ?? '#'} target="_blank" rel="noreferrer">
                            <ExternalLink className="mr-2 h-3.5 w-3.5" />
                            Acc
                          </a>
                        </Button>
                      )}
                    </div>
                  }
                />
              </div>
            )
          })}
        </div>
        </div>
      </div>

      <Dialog open={Boolean(artifactViewer)} onOpenChange={(open) => !open && setArtifactViewer(null)}>
        <DialogContent className="max-w-5xl max-h-[80vh] overflow-hidden">
          <DialogHeader>
            <DialogTitle>{artifactViewer?.title ?? 'Artifact'}</DialogTitle>
          </DialogHeader>
          <div className="overflow-auto rounded-md bg-muted/50 p-3">
            <pre className="whitespace-pre-wrap break-words text-xs leading-5">
              {artifactViewer?.content ?? ''}
            </pre>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
