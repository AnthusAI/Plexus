'use client'

import * as React from 'react'
import { generateClient } from 'aws-amplify/api'
import { downloadData } from 'aws-amplify/storage'
import { Copy, ExternalLink, Pin, PinOff, Star } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Timestamp } from '@/components/ui/timestamp'
import {
  compareOptimizerMetricValues,
  OPTIMIZER_DATASETS,
  OPTIMIZER_METRICS,
  optimizerDatasetLabel,
  optimizerMetricLabel,
  optimizerMetricValueFromSource,
  type OptimizerDatasetKey,
  type OptimizerMetricKey,
} from '@/components/ui/optimizer-results-utils'

const getAmplifyClient = (() => {
  let client: any = null
  return () => (client ??= generateClient())
})()

type OptimizerManifest = {
  procedure?: {
    id?: string
    name?: string
    status?: string
    task_id?: string
  }
  summary?: {
    completed_cycles?: number | null
    configured_max_iterations?: number | null
    stop_reason?: string | null
  }
  best?: {
    winning_version_id?: string | null
    best_feedback_evaluation_id?: string | null
    best_accuracy_evaluation_id?: string | null
    best_feedback_alignment?: number | null
    best_accuracy_alignment?: number | null
    winning_feedback_metrics?: Partial<Record<OptimizerMetricKey, number | null>> | null
    winning_accuracy_metrics?: Partial<Record<OptimizerMetricKey, number | null>> | null
  }
  cycles?: Array<Record<string, any>>
}

type VersionMetricSort = `${OptimizerDatasetKey}_${OptimizerMetricKey}`
type VersionMetricResult = {
  evaluationId?: string | null
  value: number | null
}

type ProcedureRecord = {
  id: string
  name?: string | null
  status?: string | null
  updatedAt?: string | null
  metadata?: string | null
  scoreVersionId?: string | null
}

type OptimizerRunView = {
  procedureId: string
  name?: string | null
  status?: string | null
  updatedAt?: string | null
  indexed: boolean
  manifestKey?: string | null
  artifactPointer?: {
    manifest?: string | null
    events?: string | null
    runtime_log?: string | null
  } | null
  manifest?: OptimizerManifest | null
}

type CandidateVersionSummary = {
  versionId: string
  pinned: boolean
  isChampion: boolean
  note?: string | null
  branch?: string | null
  parentVersionId?: string | null
  bestFeedbackEvaluationId?: string | null
  bestAccuracyEvaluationId?: string | null
  bestFeedbackAlignment?: number | null
  bestAccuracyAlignment?: number | null
  bestByMetric: Partial<Record<VersionMetricSort, VersionMetricResult>>
  sourceProcedureIds: string[]
}

type WorkbenchScoreVersion = {
  id: string
  isFeatured: boolean
  note?: string
  branch?: string
  parentVersionId?: string
}

function safeJsonParse<T>(value: string | null | undefined): T | null {
  if (!value) return null
  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}

function evaluationUrl(evaluationId?: string | null): string | null {
  return evaluationId ? `/lab/evaluations/${evaluationId}` : null
}

async function copyText(text: string, successMessage: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(successMessage)
  } catch (error) {
    console.error('Failed to copy text:', error)
    toast.error('Failed to copy to clipboard')
  }
}

function scorecardGuideRelativePath(scorecardName: string, scoreName: string) {
  return `scorecards/${scorecardName}/guidelines/${scoreName}.md`
}

function aggregateCandidatesFromRuns(
  runs: OptimizerRunView[],
  versions: WorkbenchScoreVersion[],
  championVersionId?: string | null
): CandidateVersionSummary[] {
  const byVersionId = new Map<string, CandidateVersionSummary>()
  const versionsById = new Map(versions.map((version) => [version.id, version]))

  const touch = (
    versionId: string | undefined | null,
    sourceProcedureId: string,
    feedbackEvalId?: string | null,
    accuracyEvalId?: string | null,
    feedbackMetrics?: Record<string, any> | null,
    accuracyMetrics?: Record<string, any> | null
  ) => {
    if (!versionId) return
    const version = versionsById.get(versionId)
    const existing: CandidateVersionSummary = byVersionId.get(versionId) ?? {
      versionId,
      pinned: Boolean(version?.isFeatured),
      isChampion: championVersionId === versionId,
      note: version?.note ?? null,
      branch: (version as any)?.branch ?? null,
      parentVersionId: (version as any)?.parentVersionId ?? null,
      bestFeedbackEvaluationId: null,
      bestAccuracyEvaluationId: null,
      bestFeedbackAlignment: null,
      bestAccuracyAlignment: null,
      bestByMetric: {},
      sourceProcedureIds: [],
    }

    if (!existing.sourceProcedureIds.includes(sourceProcedureId)) {
      existing.sourceProcedureIds.push(sourceProcedureId)
    }
    const source = {
      feedback_evaluation_id: feedbackEvalId,
      accuracy_evaluation_id: accuracyEvalId,
      feedback_metrics: feedbackMetrics,
      accuracy_metrics: accuracyMetrics,
    }

    for (const dataset of OPTIMIZER_DATASETS) {
      for (const metric of OPTIMIZER_METRICS) {
        const value = optimizerMetricValueFromSource(source, dataset, metric)
        if (value == null) continue
        const key = `${dataset}_${metric}` as VersionMetricSort
        const current = existing.bestByMetric[key]
        if (!current || compareOptimizerMetricValues(metric, value, current.value) < 0) {
          existing.bestByMetric[key] = {
            value,
            evaluationId: dataset === 'feedback' ? feedbackEvalId : accuracyEvalId,
          }
        }
      }
    }

    existing.bestFeedbackAlignment = existing.bestByMetric.feedback_alignment?.value ?? existing.bestFeedbackAlignment
    existing.bestFeedbackEvaluationId = existing.bestByMetric.feedback_alignment?.evaluationId ?? existing.bestFeedbackEvaluationId
    existing.bestAccuracyAlignment = existing.bestByMetric.regression_alignment?.value ?? existing.bestAccuracyAlignment
    existing.bestAccuracyEvaluationId = existing.bestByMetric.regression_alignment?.evaluationId ?? existing.bestAccuracyEvaluationId
    byVersionId.set(versionId, existing)
  }

  for (const run of runs) {
    const procedureId = run.procedureId
    const best = run.manifest?.best
    touch(
      best?.winning_version_id,
      procedureId,
      best?.best_feedback_evaluation_id,
      best?.best_accuracy_evaluation_id,
      {
        ...(best?.winning_feedback_metrics ?? {}),
        alignment: best?.winning_feedback_metrics?.alignment ?? best?.best_feedback_alignment ?? null,
      },
      {
        ...(best?.winning_accuracy_metrics ?? {}),
        alignment: best?.winning_accuracy_metrics?.alignment ?? best?.best_accuracy_alignment ?? null,
      }
    )
    for (const cycle of run.manifest?.cycles ?? []) {
      touch(
        cycle.version_id,
        procedureId,
        cycle.feedback_evaluation_id ?? null,
        cycle.accuracy_evaluation_id ?? null,
        cycle.feedback_metrics ?? null,
        cycle.accuracy_metrics ?? cycle.regression_metrics ?? null
      )
      for (const candidate of cycle.candidates ?? []) {
        touch(
          candidate.version_id,
          procedureId,
          candidate.feedback_evaluation_id ?? null,
          candidate.accuracy_evaluation_id ?? null,
          candidate.feedback_metrics ?? null,
          candidate.accuracy_metrics ?? candidate.regression_metrics ?? null
        )
      }
    }
  }

  return [...byVersionId.values()].sort((a, b) => {
    const fb = (b.bestFeedbackAlignment ?? -1) - (a.bestFeedbackAlignment ?? -1)
    if (fb !== 0) return fb
    return (b.bestAccuracyAlignment ?? -1) - (a.bestAccuracyAlignment ?? -1)
  })
}

export interface ScoreOptimizerWorkbenchProps {
  scoreId: string
  scoreName: string
  scorecardName: string
  championVersionId?: string | null
  versions: WorkbenchScoreVersion[]
  onPromoteToChampion?: (versionId: string) => void
  onToggleFeature?: (versionId: string) => void
}

export function ScoreOptimizerWorkbench({
  scoreId,
  scoreName,
  scorecardName,
  championVersionId,
  versions,
  onPromoteToChampion,
  onToggleFeature,
}: ScoreOptimizerWorkbenchProps) {
  const [runs, setRuns] = React.useState<OptimizerRunView[]>([])
  const [isLoading, setIsLoading] = React.useState(false)
  const [artifactViewer, setArtifactViewer] = React.useState<{
    title: string
    content: string
  } | null>(null)
  const [versionSort, setVersionSort] = React.useState<VersionMetricSort>('feedback_alignment')

  const openArtifactViewer = React.useCallback(
    async (artifactKey: string | null | undefined, title: string) => {
      if (!artifactKey) {
        toast.error(`${title} is not available for this run`)
        return
      }
      try {
        const downloadResult = await downloadData({
          path: artifactKey,
          options: { bucket: 'taskAttachments' },
        }).result
        setArtifactViewer({
          title,
          content: await downloadResult.body.text(),
        })
      } catch (error) {
        console.error(`Failed to load ${title}:`, error)
        toast.error(`Failed to load ${title}`)
      }
    },
    []
  )

  React.useEffect(() => {
    let cancelled = false

    const loadRuns = async () => {
      setIsLoading(true)
      try {
        const response = await getAmplifyClient().graphql({
          query: `
            query ListProcedureByScoreIdAndUpdatedAtWorkbench(
              $scoreId: String!
              $sortDirection: ModelSortDirection
              $limit: Int
            ) {
              listProcedureByScoreIdAndUpdatedAt(
                scoreId: $scoreId
                sortDirection: $sortDirection
                limit: $limit
              ) {
                items {
                  id
                  name
                  status
                  metadata
                  updatedAt
                  scoreVersionId
                }
              }
            }
          `,
          variables: {
            scoreId,
            sortDirection: 'DESC',
            limit: 50,
          },
        }) as any

        const procedures: ProcedureRecord[] = response.data?.listProcedureByScoreIdAndUpdatedAt?.items ?? []
        const loadedRuns = await Promise.all(
          procedures.map(async (procedure) => {
            const metadata = safeJsonParse<Record<string, any>>(procedure.metadata)
            const artifactPointer = metadata?.optimizer_artifacts ?? null
            const manifestKey = artifactPointer?.manifest as string | undefined
            let manifest: OptimizerManifest | null = null

            if (manifestKey) {
              try {
                const downloadResult = await downloadData({
                  path: manifestKey,
                  options: { bucket: 'taskAttachments' },
                }).result
                manifest = JSON.parse(await downloadResult.body.text()) as OptimizerManifest
              } catch (error) {
                console.error('Failed to load optimizer manifest for procedure', procedure.id, error)
              }
            }

            return {
              procedureId: procedure.id,
              name: procedure.name,
              status: procedure.status,
              updatedAt: procedure.updatedAt,
              indexed: Boolean(manifestKey && manifest),
              manifestKey: manifestKey ?? null,
              artifactPointer: artifactPointer
                ? {
                    manifest: artifactPointer.manifest ?? null,
                    events: artifactPointer.events ?? null,
                    runtime_log: artifactPointer.runtime_log ?? null,
                  }
                : null,
              manifest,
            } satisfies OptimizerRunView
          })
        )

        if (!cancelled) {
          setRuns(loadedRuns)
        }
      } catch (error) {
        console.error('Failed to load optimizer runs:', error)
        if (!cancelled) {
          toast.error('Failed to load optimizer runs')
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

  const versionSortOptions = React.useMemo(
    () =>
      OPTIMIZER_DATASETS.flatMap((dataset) =>
        OPTIMIZER_METRICS.map((metric) => ({
          value: `${dataset}_${metric}` as VersionMetricSort,
          label: `Best ${optimizerDatasetLabel(dataset)} ${optimizerMetricLabel(metric)}`,
        }))
      ),
    []
  )

  const candidateVersions = React.useMemo(() => {
    const [, metric] = versionSort.split('_') as [OptimizerDatasetKey, OptimizerMetricKey]
    return aggregateCandidatesFromRuns(runs, versions, championVersionId).sort((left, right) => {
      const metricCompare = compareOptimizerMetricValues(
        metric,
        left.bestByMetric[versionSort]?.value,
        right.bestByMetric[versionSort]?.value
      )
      if (metricCompare !== 0) return metricCompare
      return left.versionId.localeCompare(right.versionId)
    })
  }, [runs, versions, championVersionId, versionSort])

  return (
    <div className="flex flex-col gap-4 p-4 overflow-y-auto">
      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="font-semibold">Optimizer Runs</h3>
              <p className="text-sm text-muted-foreground">Indexed runs and their best visible evaluations.</p>
            </div>
            {isLoading && <span className="text-sm text-muted-foreground">Loading…</span>}
          </div>

          <div className="space-y-3">
            {runs.length === 0 && (
              <div className="text-sm text-muted-foreground">No optimizer runs found for this score yet.</div>
            )}
            {runs.map((run) => {
              const summary = run.manifest?.summary
              const best = run.manifest?.best
              return (
                <div key={run.procedureId} className="rounded-md border border-border p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-medium truncate">{run.name || run.procedureId}</div>
                      <div className="text-xs text-muted-foreground">{run.procedureId}</div>
                    </div>
                    <div className="text-right text-xs text-muted-foreground">
                      <div>{run.status || 'unknown'}</div>
                      {run.updatedAt && <Timestamp time={run.updatedAt} variant="relative" />}
                    </div>
                  </div>

                  <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
                    <div>Cycles: {summary?.completed_cycles ?? '—'}/{summary?.configured_max_iterations ?? '—'}</div>
                    <div>Stop: {summary?.stop_reason || '—'}</div>
                    <div>Winning version: {best?.winning_version_id || '—'}</div>
                    <div>Indexed: {run.indexed ? 'yes' : 'no'}</div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      asChild
                    >
                      <a href={`/lab/procedures/${run.procedureId}`} target="_blank" rel="noreferrer">
                        <ExternalLink className="mr-2 h-3.5 w-3.5" />
                        Open procedure
                      </a>
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void copyText(run.procedureId, 'Procedure ID copied')}
                    >
                      <Copy className="mr-2 h-3.5 w-3.5" />
                      Copy run ID
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        void copyText(
                          `plexus procedure index-optimizer-run ${run.procedureId}`,
                          'Index command copied'
                        )
                      }
                    >
                      <Copy className="mr-2 h-3.5 w-3.5" />
                      Copy index command
                    </Button>
                    {run.artifactPointer?.runtime_log && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void openArtifactViewer(run.artifactPointer?.runtime_log, 'Runtime log')}
                      >
                        Runtime log
                      </Button>
                    )}
                    {run.artifactPointer?.events && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void openArtifactViewer(run.artifactPointer?.events, 'Event stream')}
                      >
                        Event stream
                      </Button>
                    )}
                    {best?.best_feedback_evaluation_id && (
                      <Button variant="outline" size="sm" asChild>
                        <a href={evaluationUrl(best.best_feedback_evaluation_id) ?? '#'} target="_blank" rel="noreferrer">
                          <ExternalLink className="mr-2 h-3.5 w-3.5" />
                          Feedback evaluation
                        </a>
                      </Button>
                    )}
                    {best?.best_accuracy_evaluation_id && (
                      <Button variant="outline" size="sm" asChild>
                        <a href={evaluationUrl(best.best_accuracy_evaluation_id) ?? '#'} target="_blank" rel="noreferrer">
                          <ExternalLink className="mr-2 h-3.5 w-3.5" />
                          Regression alignment evaluation
                        </a>
                      </Button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="font-semibold">Versions</h3>
              <p className="text-sm text-muted-foreground">Candidate versions with their best visible evaluations.</p>
            </div>
            <select
              className="rounded-md border-0 bg-background px-3 py-1.5 text-sm focus:outline-none"
              value={versionSort}
              aria-label="Version sort"
              onChange={(event) => setVersionSort(event.target.value as VersionMetricSort)}
            >
              {versionSortOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-3">
            {candidateVersions.length === 0 && (
              <div className="text-sm text-muted-foreground">No indexed candidate versions yet.</div>
            )}
            {candidateVersions.map((candidate) => {
              const [selectedDataset, selectedMetric] = versionSort.split('_') as [OptimizerDatasetKey, OptimizerMetricKey]
              const selectedMetricResult = candidate.bestByMetric[versionSort]
              return (
              <div key={candidate.versionId} className="rounded-md border border-border p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium break-all">{candidate.versionId}</span>
                      {candidate.isChampion && (
                        <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                          <Star className="h-3 w-3" />
                          Champion
                        </span>
                      )}
                      {candidate.pinned && (
                        <span className="inline-flex items-center gap-1 rounded bg-sky-100 px-2 py-0.5 text-xs text-sky-800 dark:bg-sky-900/30 dark:text-sky-200">
                          <Pin className="h-3 w-3" />
                          Pinned
                        </span>
                      )}
                    </div>
                    {candidate.note && <div className="text-xs text-muted-foreground mt-1">{candidate.note}</div>}
                  </div>
                </div>

                <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
                  <div>
                    Best {optimizerDatasetLabel(selectedDataset)} {optimizerMetricLabel(selectedMetric)}:{' '}
                    {selectedMetricResult?.value?.toFixed(4) ?? '—'}
                  </div>
                  <div>Feedback AC1: {candidate.bestFeedbackAlignment?.toFixed(4) ?? '—'}</div>
                  <div>Regression AC1: {candidate.bestAccuracyAlignment?.toFixed(4) ?? '—'}</div>
                  <div>Feedback evaluation: {candidate.bestFeedbackEvaluationId || '—'}</div>
                  <div>Regression alignment evaluation: {candidate.bestAccuracyEvaluationId || '—'}</div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void copyText(candidate.versionId, 'Version ID copied')}
                  >
                    <Copy className="mr-2 h-3.5 w-3.5" />
                    Copy version
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      void copyText(
                        JSON.stringify(
                          {
                            score: scoreName,
                            version_id: candidate.versionId,
                            feedback_evaluation_url: evaluationUrl(candidate.bestFeedbackEvaluationId),
                            accuracy_evaluation_url: evaluationUrl(candidate.bestAccuracyEvaluationId),
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
                    Copy promotion packet
                  </Button>
                  {candidate.bestFeedbackEvaluationId && (
                    <Button variant="outline" size="sm" asChild>
                      <a href={evaluationUrl(candidate.bestFeedbackEvaluationId) ?? '#'} target="_blank" rel="noreferrer">
                        <ExternalLink className="mr-2 h-3.5 w-3.5" />
                        Feedback evaluation
                      </a>
                    </Button>
                  )}
                  {selectedMetricResult?.evaluationId && (
                    <Button variant="outline" size="sm" asChild>
                      <a href={evaluationUrl(selectedMetricResult.evaluationId) ?? '#'} target="_blank" rel="noreferrer">
                        <ExternalLink className="mr-2 h-3.5 w-3.5" />
                        Selected metric evaluation
                      </a>
                    </Button>
                  )}
                  {candidate.bestAccuracyEvaluationId && (
                    <Button variant="outline" size="sm" asChild>
                      <a href={evaluationUrl(candidate.bestAccuracyEvaluationId) ?? '#'} target="_blank" rel="noreferrer">
                        <ExternalLink className="mr-2 h-3.5 w-3.5" />
                        Regression alignment evaluation
                      </a>
                    </Button>
                  )}
                  {onPromoteToChampion && !candidate.isChampion && (
                    <Button variant="default" size="sm" onClick={() => onPromoteToChampion(candidate.versionId)}>
                      Promote
                    </Button>
                  )}
                  {onToggleFeature && (
                    <Button variant="outline" size="sm" onClick={() => onToggleFeature(candidate.versionId)}>
                      {candidate.pinned ? (
                        <>
                          <PinOff className="mr-2 h-3.5 w-3.5" />
                          Unpin
                        </>
                      ) : (
                        <>
                          <Pin className="mr-2 h-3.5 w-3.5" />
                          Pin
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </div>
              )
            })}
          </div>
        </Card>
      </div>

      <Dialog open={Boolean(artifactViewer)} onOpenChange={(open) => !open && setArtifactViewer(null)}>
        <DialogContent className="max-w-5xl max-h-[80vh] overflow-hidden">
          <DialogHeader>
            <DialogTitle>{artifactViewer?.title ?? 'Artifact'}</DialogTitle>
          </DialogHeader>
          <div className="overflow-auto rounded-md border border-border bg-muted/20 p-3">
            <pre className="whitespace-pre-wrap break-words text-xs leading-5">
              {artifactViewer?.content ?? ''}
            </pre>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
