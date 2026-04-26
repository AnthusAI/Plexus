import { generateClient } from 'aws-amplify/api'
import { downloadData } from 'aws-amplify/storage'
import { toast } from 'sonner'

const getAmplifyClient = (() => {
  let client: any = null
  return () => (client ??= generateClient())
})()

export type OptimizerMetricKey = 'alignment' | 'accuracy' | 'precision' | 'recall' | 'cost'
export type OptimizerDatasetKey = 'feedback' | 'regression'
export type OptimizerMetricValues = Partial<Record<OptimizerMetricKey, number | null>>

export const OPTIMIZER_METRICS: OptimizerMetricKey[] = ['alignment', 'accuracy', 'precision', 'recall', 'cost']
export const OPTIMIZER_DATASETS: OptimizerDatasetKey[] = ['feedback', 'regression']

export type OptimizerBestMetricResult = {
  dataset: OptimizerDatasetKey
  metric: OptimizerMetricKey
  value: number
  evaluationId: string
  versionId?: string | null
}

export type OptimizerManifest = {
  procedure?: {
    id?: string
    name?: string
    status?: string
    task_id?: string
  }
  baseline?: {
    version_id?: string | null
  }
  summary?: {
    completed_cycles?: number | null
    configured_max_iterations?: number | null
    stop_reason?: string | null
  }
  best?: {
    winning_version_id?: string | null
    last_accepted_version_id?: string | null
    best_feedback_evaluation_id?: string | null
    best_accuracy_evaluation_id?: string | null
    best_feedback_alignment?: number | null
    best_accuracy_alignment?: number | null
    winning_feedback_metrics?: OptimizerMetricValues | null
    winning_accuracy_metrics?: OptimizerMetricValues | null
  }
  cycles?: Array<Record<string, any>>
}

export type ProcedureRecord = {
  id: string
  name?: string | null
  description?: string | null
  status?: string | null
  updatedAt?: string | null
  metadata?: string | null
  scoreVersionId?: string | null
  task?: {
    id: string
    type?: string | null
    status?: string | null
    target?: string | null
    command?: string | null
    description?: string | null
    dispatchStatus?: string | null
    metadata?: unknown
    createdAt?: string | null
    startedAt?: string | null
    completedAt?: string | null
    estimatedCompletionAt?: string | null
    errorMessage?: string | null
    errorDetails?: unknown
    currentStageId?: string | null
    stages?: {
      items: Array<{
        id: string
        name: string
        order: number
        status: string
        statusMessage?: string | null
        startedAt?: string | null
        completedAt?: string | null
        estimatedCompletionAt?: string | null
        processedItems?: number | null
        totalItems?: number | null
      }>
    } | null
  } | null
}

export type OptimizerRunView = {
  procedureId: string
  name?: string | null
  procedureDescription?: string | null
  status?: string | null
  updatedAt?: string | null
  metadataText?: string | null
  task?: {
    id: string
    type?: string | null
    status?: string | null
    target?: string | null
    command?: string | null
    description?: string | null
    dispatchStatus?: string | null
    metadata?: unknown
    createdAt?: string | null
    startedAt?: string | null
    completedAt?: string | null
    estimatedCompletionAt?: string | null
    errorMessage?: string | null
    errorDetails?: unknown
    currentStageId?: string | null
    stages?: {
      items: Array<{
        id: string
        name: string
        order: number
        status: string
        statusMessage?: string | null
        startedAt?: string | null
        completedAt?: string | null
        estimatedCompletionAt?: string | null
        processedItems?: number | null
        totalItems?: number | null
      }>
    } | null
  } | null
  indexed: boolean
  manifestKey?: string | null
  artifactPointer?: {
    manifest?: string | null
    events?: string | null
    runtime_log?: string | null
  } | null
  manifest?: OptimizerManifest | null
  scoreVersionId?: string | null
}

export type ScoreVersionSummary = {
  id: string
  isFeatured: boolean
  note?: string
  branch?: string
  parentVersionId?: string
}

export type ScoreEvaluationView = {
  id: string
  type?: string | null
  parameters?: unknown
  status?: string | null
  updatedAt?: string | null
  createdAt?: string | null
  scoreVersionId?: string | null
  accuracy?: number | null
  alignment?: number | null
  precision?: number | null
  recall?: number | null
  cost?: number | null
  baselineEvaluationId?: string | null
  currentBaselineEvaluationId?: string | null
  processedItems?: number | null
  totalItems?: number | null
  elapsedSeconds?: number | null
  estimatedRemainingSeconds?: number | null
  task?: {
    id: string
    type?: string | null
    status?: string | null
    target?: string | null
    command?: string | null
    description?: string | null
    dispatchStatus?: string | null
    createdAt?: string | null
    startedAt?: string | null
    completedAt?: string | null
    estimatedCompletionAt?: string | null
    errorMessage?: string | null
    errorDetails?: unknown
    currentStageId?: string | null
    stages?: {
      items: Array<{
        id: string
        name: string
        order: number
        status: string
        statusMessage?: string | null
        startedAt?: string | null
        completedAt?: string | null
        estimatedCompletionAt?: string | null
        processedItems?: number | null
        totalItems?: number | null
      }>
    } | null
  } | null
}

function parseJsonMaybeDeep(value: unknown): unknown {
  let current = value
  for (let i = 0; i < 3; i += 1) {
    if (typeof current !== 'string') return current
    const trimmed = current.trim()
    if (!trimmed) return current
    try {
      current = JSON.parse(trimmed)
    } catch {
      return current
    }
  }
  return current
}

function extractBaselineIdsFromParameters(parameters: unknown): {
  baselineEvaluationId: string | null
  currentBaselineEvaluationId: string | null
} {
  const parsedParameters = parseJsonMaybeDeep(parameters)
  if (!parsedParameters || typeof parsedParameters !== 'object') {
    return {
      baselineEvaluationId: null,
      currentBaselineEvaluationId: null,
    }
  }

  const metadata = parseJsonMaybeDeep((parsedParameters as Record<string, unknown>).metadata)
  if (!metadata || typeof metadata !== 'object') {
    return {
      baselineEvaluationId: null,
      currentBaselineEvaluationId: null,
    }
  }

  const metadataObj = metadata as Record<string, unknown>
  const baselineEvaluationId =
    typeof metadataObj.baseline === 'string'
      ? metadataObj.baseline
      : typeof metadataObj.baseline_evaluation_id === 'string'
        ? metadataObj.baseline_evaluation_id
        : null
  const currentBaselineEvaluationId =
    typeof metadataObj.current_baseline === 'string'
      ? metadataObj.current_baseline
      : typeof metadataObj.current_baseline_evaluation_id === 'string'
        ? metadataObj.current_baseline_evaluation_id
        : null

  return {
    baselineEvaluationId,
    currentBaselineEvaluationId,
  }
}

export function safeJsonParse<T>(value: unknown): T | null {
  if (value == null) return null
  if (typeof value === 'object') return value as T
  if (typeof value !== 'string' || !value) return null
  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}

export function evaluationUrl(evaluationId?: string | null): string | null {
  return evaluationId ? `/lab/evaluations/${evaluationId}` : null
}

export function scoreVersionUrl(
  scorecardId: string | null | undefined,
  scoreId: string | null | undefined,
  versionId: string | null | undefined
): string | null {
  return scorecardId && scoreId && versionId
    ? `/lab/scorecards/${scorecardId}/scores/${scoreId}/versions/${versionId}`
    : null
}

export function optimizerMetricLabel(metric: OptimizerMetricKey): string {
  switch (metric) {
    case 'alignment':
      return 'alignment'
    case 'accuracy':
      return 'accuracy'
    case 'precision':
      return 'precision'
    case 'recall':
      return 'recall'
    case 'cost':
      return 'cost'
  }
}

export function optimizerDatasetLabel(dataset: OptimizerDatasetKey): string {
  return dataset === 'feedback' ? 'feedback' : 'regression'
}

export function compareOptimizerMetricValues(
  metric: OptimizerMetricKey,
  left: number | null | undefined,
  right: number | null | undefined
): number {
  const leftHasMetric = typeof left === 'number' && Number.isFinite(left)
  const rightHasMetric = typeof right === 'number' && Number.isFinite(right)
  if (leftHasMetric && rightHasMetric && left !== right) {
    return metric === 'cost' ? left! - right! : right! - left!
  }
  if (leftHasMetric !== rightHasMetric) return leftHasMetric ? -1 : 1
  return 0
}

function metricFromObject(source: unknown, metric: OptimizerMetricKey): number | null {
  if (!source || typeof source !== 'object') return null
  const record = source as Record<string, unknown>
  if (metric === 'alignment') {
    return toFiniteNumber(record.alignment) ?? toFiniteNumber(record.ac1) ?? toFiniteNumber(record.agreement)
  }
  if (metric === 'cost') {
    return (
      toFiniteNumber(record.cost) ??
      toFiniteNumber(record.total_cost) ??
      toFiniteNumber(record.totalCost) ??
      toFiniteNumber(record.cost_per_item) ??
      toFiniteNumber(record.costPerItem)
    )
  }
  return toFiniteNumber(record[metric])
}

function evaluationIdForDataset(source: Record<string, any>, dataset: OptimizerDatasetKey): string | null {
  const value =
    dataset === 'feedback'
      ? source.feedback_evaluation_id ?? source.best_feedback_evaluation_id
      : source.accuracy_evaluation_id ?? source.regression_evaluation_id ?? source.best_accuracy_evaluation_id
  return typeof value === 'string' && value ? value : null
}

function metricsForDataset(source: Record<string, any>, dataset: OptimizerDatasetKey): unknown {
  return dataset === 'feedback'
    ? source.feedback_metrics ?? source.winning_feedback_metrics
    : source.accuracy_metrics ?? source.regression_metrics ?? source.winning_accuracy_metrics
}

function versionIdFromSource(source: Record<string, any>): string | null {
  const value = source.version_id ?? source.score_version_id ?? source.winning_version_id
  return typeof value === 'string' && value ? value : null
}

export function optimizerMetricValueFromSource(
  source: Record<string, any> | null | undefined,
  dataset: OptimizerDatasetKey,
  metric: OptimizerMetricKey
): number | null {
  if (!source) return null
  const metricsValue = metricFromObject(metricsForDataset(source, dataset), metric)
  if (metricsValue != null) return metricsValue
  if (dataset === 'feedback' && metric === 'alignment') {
    return toFiniteNumber(source.best_feedback_alignment)
  }
  if (dataset === 'regression' && metric === 'alignment') {
    return toFiniteNumber(source.best_accuracy_alignment)
  }
  return null
}

export function findBestOptimizerEvaluation(
  manifest: OptimizerManifest | null | undefined,
  dataset: OptimizerDatasetKey,
  metric: OptimizerMetricKey
): OptimizerBestMetricResult | null {
  if (!manifest) return null
  let bestResult: OptimizerBestMetricResult | null = null

  const consider = (source: Record<string, any> | null | undefined) => {
    if (!source) return
    const evaluationId = evaluationIdForDataset(source, dataset)
    const value = optimizerMetricValueFromSource(source, dataset, metric)
    if (!evaluationId || value == null) return
    const candidate: OptimizerBestMetricResult = {
      dataset,
      metric,
      value,
      evaluationId,
      versionId: versionIdFromSource(source),
    }
    if (!bestResult || compareOptimizerMetricValues(metric, candidate.value, bestResult.value) < 0) {
      bestResult = candidate
    }
  }

  if (manifest.best) consider(manifest.best as Record<string, any>)
  for (const cycle of manifest.cycles ?? []) {
    consider(cycle)
    for (const candidate of cycle?.candidates ?? []) consider(candidate)
    for (const candidate of cycle?.no_version_candidates ?? []) consider(candidate)
  }

  return bestResult
}

export async function copyText(text: string, successMessage: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(successMessage)
  } catch (error) {
    console.error('Failed to copy text:', error)
    toast.error('Failed to copy to clipboard')
  }
}

export function scorecardGuideRelativePath(scorecardName: string, scoreName: string) {
  return `scorecards/${scorecardName}/guidelines/${scoreName}.md`
}

function toFiniteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function parseEvaluationMetrics(rawMetrics: unknown): {
  accuracy: number | null
  alignment: number | null
  precision: number | null
  recall: number | null
  cost: number | null
} {
  const metrics = safeJsonParse<any>(rawMetrics)
  if (!metrics) {
    return { accuracy: null, alignment: null, precision: null, recall: null, cost: null }
  }

  if (Array.isArray(metrics)) {
    let accuracy: number | null = null
    let alignment: number | null = null
    let precision: number | null = null
    let recall: number | null = null
    let cost: number | null = null
    for (const metric of metrics) {
      if (!metric || typeof metric !== 'object') continue
      const name = String(metric.name ?? metric.label ?? '').toLowerCase()
      const value = toFiniteNumber(metric.value)
      if (value == null) continue
      if (accuracy == null && name.includes('accuracy')) accuracy = value
      if (alignment == null && (name.includes('alignment') || name.includes('ac1'))) alignment = value
      if (precision == null && name.includes('precision')) precision = value
      if (recall == null && name.includes('recall')) recall = value
      if (cost == null && name.includes('cost')) cost = value
    }
    return { accuracy, alignment, precision, recall, cost }
  }

  if (typeof metrics === 'object') {
    return {
      accuracy: toFiniteNumber((metrics as any).accuracy),
      alignment:
        toFiniteNumber((metrics as any).alignment) ??
        toFiniteNumber((metrics as any).ac1) ??
        toFiniteNumber((metrics as any).agreement),
      precision: toFiniteNumber((metrics as any).precision),
      recall: toFiniteNumber((metrics as any).recall),
      cost:
        toFiniteNumber((metrics as any).cost) ??
        toFiniteNumber((metrics as any).total_cost) ??
        toFiniteNumber((metrics as any).totalCost) ??
        toFiniteNumber((metrics as any).cost_per_item) ??
        toFiniteNumber((metrics as any).costPerItem),
    }
  }

  return { accuracy: null, alignment: null, precision: null, recall: null, cost: null }
}

export function manifestTouchesVersion(
  manifest: OptimizerManifest | null | undefined,
  versionId: string | null | undefined
): boolean {
  if (!manifest || !versionId) return false
  if (manifest.baseline?.version_id === versionId) return true
  if (manifest.best?.winning_version_id === versionId) return true
  if (manifest.best?.last_accepted_version_id === versionId) return true

  for (const cycle of manifest.cycles ?? []) {
    if (cycle?.version_id === versionId) return true
    for (const candidate of cycle?.candidates ?? []) {
      if (candidate?.version_id === versionId) return true
    }
    for (const candidate of cycle?.no_version_candidates ?? []) {
      if (candidate?.version_id === versionId) return true
    }
  }

  return false
}

export async function openArtifactText(artifactKey: string | null | undefined) {
  if (!artifactKey) {
    throw new Error('Artifact key is required')
  }
  const downloadResult = await downloadData({
    path: artifactKey,
    options: { bucket: 'taskAttachments' },
  }).result
  return downloadResult.body.text()
}

export async function loadOptimizerRuns(scoreId: string, limit: number = 50): Promise<OptimizerRunView[]> {
  const client = getAmplifyClient()
  const response = await client.graphql({
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
            description
            status
            metadata
            updatedAt
            scoreVersionId
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
          }
        }
      }
    `,
    variables: {
      scoreId,
      sortDirection: 'DESC',
      limit,
    },
  }) as any

  const procedures: ProcedureRecord[] = response.data?.listProcedureByScoreIdAndUpdatedAt?.items ?? []

  return Promise.all(
    procedures.map(async (procedure) => {
      const metadata = safeJsonParse<Record<string, any>>(procedure.metadata)
      const artifactPointer = metadata?.optimizer_artifacts ?? null
      const manifestKey = artifactPointer?.manifest as string | undefined
      let manifest: OptimizerManifest | null = null

      if (manifestKey) {
        try {
          const manifestText = await openArtifactText(manifestKey)
          manifest = JSON.parse(manifestText) as OptimizerManifest
        } catch (error) {
          console.error('Failed to load optimizer manifest for procedure', procedure.id, error)
        }
      }

      return {
        procedureId: procedure.id,
        name: procedure.name,
        procedureDescription: procedure.description ?? null,
        status: procedure.status,
        updatedAt: procedure.updatedAt,
        metadataText:
          typeof procedure.metadata === 'string'
            ? procedure.metadata
            : procedure.metadata != null
              ? JSON.stringify(procedure.metadata)
              : null,
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
        scoreVersionId: procedure.scoreVersionId ?? null,
        task: procedure.task
          ? {
              id: procedure.task.id,
              type: procedure.task.type ?? null,
              status: procedure.task.status ?? null,
              target: procedure.task.target ?? null,
              command: procedure.task.command ?? null,
              description: procedure.task.description ?? null,
              dispatchStatus: procedure.task.dispatchStatus ?? null,
              metadata: procedure.task.metadata ?? null,
              createdAt: procedure.task.createdAt ?? null,
              startedAt: procedure.task.startedAt ?? null,
              completedAt: procedure.task.completedAt ?? null,
              estimatedCompletionAt: procedure.task.estimatedCompletionAt ?? null,
              errorMessage: procedure.task.errorMessage ?? null,
              errorDetails: procedure.task.errorDetails ?? null,
              currentStageId: procedure.task.currentStageId ?? null,
              stages: procedure.task.stages
                ? {
                    items: (procedure.task.stages.items ?? []).map((stage: any) => ({
                      id: String(stage.id ?? ''),
                      name: String(stage.name ?? ''),
                      order: typeof stage.order === 'number' ? stage.order : 0,
                      status: String(stage.status ?? 'PENDING'),
                      statusMessage: stage.statusMessage ?? null,
                      startedAt: stage.startedAt ?? null,
                      completedAt: stage.completedAt ?? null,
                      estimatedCompletionAt: stage.estimatedCompletionAt ?? null,
                      processedItems: toFiniteNumber(stage.processedItems),
                      totalItems: toFiniteNumber(stage.totalItems),
                    })),
                  }
                : null,
            }
          : null,
      } satisfies OptimizerRunView
    })
  )
}

export async function loadScoreEvaluations(scoreId: string, limit: number = 100): Promise<ScoreEvaluationView[]> {
  const response = await getAmplifyClient().graphql({
    query: `
      query ListEvaluationByScoreIdAndUpdatedAtForWorkbench(
        $scoreId: String!
        $sortDirection: ModelSortDirection!
        $limit: Int
      ) {
        listEvaluationByScoreIdAndUpdatedAt(
          scoreId: $scoreId
          sortDirection: $sortDirection
          limit: $limit
        ) {
          items {
            id
            type
            status
            updatedAt
            createdAt
            parameters
            scoreVersionId
            accuracy
            processedItems
            totalItems
            elapsedSeconds
            estimatedRemainingSeconds
            metrics
            cost
            task {
              id
              type
              status
              target
              command
              description
              dispatchStatus
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
          }
        }
      }
    `,
    variables: {
      scoreId,
      sortDirection: 'DESC',
      limit,
    },
  }) as any

  const items = response.data?.listEvaluationByScoreIdAndUpdatedAt?.items ?? []
  return items.map((item: any) => {
    const parsed = parseEvaluationMetrics(item.metrics)
    const { baselineEvaluationId, currentBaselineEvaluationId } =
      extractBaselineIdsFromParameters(item.parameters)
    return {
      id: item.id,
      type: item.type ?? null,
      parameters: item.parameters ?? null,
      status: item.status ?? null,
      updatedAt: item.updatedAt ?? null,
      createdAt: item.createdAt ?? null,
      scoreVersionId: item.scoreVersionId ?? null,
      accuracy: toFiniteNumber(item.accuracy) ?? parsed.accuracy,
      alignment: parsed.alignment,
      precision: parsed.precision,
      recall: parsed.recall,
      cost: toFiniteNumber(item.cost) ?? parsed.cost,
      baselineEvaluationId,
      currentBaselineEvaluationId,
      processedItems: toFiniteNumber(item.processedItems),
      totalItems: toFiniteNumber(item.totalItems),
      elapsedSeconds: toFiniteNumber(item.elapsedSeconds),
      estimatedRemainingSeconds: toFiniteNumber(item.estimatedRemainingSeconds),
      task: item.task
        ? {
            id: item.task.id,
            type: item.task.type ?? null,
            status: item.task.status ?? null,
            target: item.task.target ?? null,
            command: item.task.command ?? null,
            description: item.task.description ?? null,
            dispatchStatus: item.task.dispatchStatus ?? null,
            createdAt: item.task.createdAt ?? null,
            startedAt: item.task.startedAt ?? null,
            completedAt: item.task.completedAt ?? null,
            estimatedCompletionAt: item.task.estimatedCompletionAt ?? null,
            errorMessage: item.task.errorMessage ?? null,
            errorDetails: item.task.errorDetails ?? null,
            currentStageId: item.task.currentStageId ?? null,
            stages: item.task.stages
              ? {
                  items: (item.task.stages.items ?? []).map((stage: any) => ({
                    id: String(stage.id ?? ''),
                    name: String(stage.name ?? ''),
                    order: typeof stage.order === 'number' ? stage.order : 0,
                    status: String(stage.status ?? 'PENDING'),
                    statusMessage: stage.statusMessage ?? null,
                    startedAt: stage.startedAt ?? null,
                    completedAt: stage.completedAt ?? null,
                    estimatedCompletionAt: stage.estimatedCompletionAt ?? null,
                    processedItems: toFiniteNumber(stage.processedItems),
                    totalItems: toFiniteNumber(stage.totalItems),
                  })),
                }
              : null,
          }
        : null,
    } satisfies ScoreEvaluationView
  })
}
