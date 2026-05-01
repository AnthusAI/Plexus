import { generateClient } from 'aws-amplify/api'
import { downloadData } from 'aws-amplify/storage'
import { toast } from 'sonner'

const getAmplifyClient = (() => {
  let client: any = null
  return () => (client ??= generateClient())
})()

export const TASK_STAGE_CARD_FIELDS = `
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
`

export const TASK_CARD_FIELDS = `
  id
  type
  status
  target
  command
  description
  dispatchStatus
  workerNodeId
  celeryTaskId
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
      ${TASK_STAGE_CARD_FIELDS}
    }
  }
`

export const PROCEDURE_CARD_FIELDS = `
  id
  name
  description
  featured
  isTemplate
  parentProcedureId
  code
  category
  version
  isDefault
  status
  waitingOnMessageId
  metadata
  createdAt
  updatedAt
  accountId
  scorecardId
  scorecard {
    id
    name
  }
  scoreId
  score {
    id
    name
  }
  scoreVersionId
`

export const EVALUATION_CARD_FIELDS = `
  id
  type
  status
  updatedAt
  createdAt
  parameters
  scoreId
  scoreVersionId
  accuracy
  processedItems
  totalItems
  elapsedSeconds
  estimatedRemainingSeconds
  metrics
  cost
  taskId
  task {
    ${TASK_CARD_FIELDS}
  }
`

export const TASK_UPDATE_SUBSCRIPTION_FOR_CARDS = `
  subscription OnUpdateTaskForCards {
    onUpdateTask {
      ${TASK_CARD_FIELDS}
    }
  }
`

export const TASK_CREATE_SUBSCRIPTION_FOR_CARDS = `
  subscription OnCreateTaskForCards {
    onCreateTask {
      ${TASK_CARD_FIELDS}
    }
  }
`

export const TASK_STAGE_UPDATE_SUBSCRIPTION_FOR_CARDS = `
  subscription OnUpdateTaskStageForCards {
    onUpdateTaskStage {
      ${TASK_STAGE_CARD_FIELDS}
    }
  }
`

export const TASK_STAGE_CREATE_SUBSCRIPTION_FOR_CARDS = `
  subscription OnCreateTaskStageForCards {
    onCreateTaskStage {
      ${TASK_STAGE_CARD_FIELDS}
    }
  }
`

export const PROCEDURE_CREATE_SUBSCRIPTION_FOR_CARDS = `
  subscription OnCreateProcedureForCards {
    onCreateProcedure {
      ${PROCEDURE_CARD_FIELDS}
    }
  }
`

export const PROCEDURE_UPDATE_SUBSCRIPTION_FOR_CARDS = `
  subscription OnUpdateProcedureForCards {
    onUpdateProcedure {
      ${PROCEDURE_CARD_FIELDS}
    }
  }
`

export const PROCEDURE_DELETE_SUBSCRIPTION_FOR_CARDS = `
  subscription OnDeleteProcedureForCards {
    onDeleteProcedure {
      id
      scoreId
      scoreVersionId
      accountId
    }
  }
`

export const PROCEDURE_SCORE_VERSION_CREATE_SUBSCRIPTION_FOR_CARDS = `
  subscription OnCreateProcedureScoreVersionForCards {
    onCreateProcedureScoreVersion {
      id
      scoreVersionId
      procedure {
        ${PROCEDURE_CARD_FIELDS}
      }
    }
  }
`

export const PROCEDURE_SCORE_VERSION_UPDATE_SUBSCRIPTION_FOR_CARDS = `
  subscription OnUpdateProcedureScoreVersionForCards {
    onUpdateProcedureScoreVersion {
      id
      scoreVersionId
      procedure {
        ${PROCEDURE_CARD_FIELDS}
      }
    }
  }
`

export const PROCEDURE_SCORE_VERSION_DELETE_SUBSCRIPTION_FOR_CARDS = `
  subscription OnDeleteProcedureScoreVersionForCards {
    onDeleteProcedureScoreVersion {
      id
      procedureId
      scoreVersionId
    }
  }
`

export const EVALUATION_CREATE_SUBSCRIPTION_FOR_CARDS = `
  subscription OnCreateEvaluationForCards {
    onCreateEvaluation {
      ${EVALUATION_CARD_FIELDS}
    }
  }
`

export const EVALUATION_UPDATE_SUBSCRIPTION_FOR_CARDS = `
  subscription OnUpdateEvaluationForCards {
    onUpdateEvaluation {
      ${EVALUATION_CARD_FIELDS}
    }
  }
`

export const EVALUATION_DELETE_SUBSCRIPTION_FOR_CARDS = `
  subscription OnDeleteEvaluationForCards {
    onDeleteEvaluation {
      id
      scoreId
      scoreVersionId
      taskId
    }
  }
`

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

export type ProcedureFeedbackEvaluationSummary = {
  id: string
  status?: string | null
  accuracy?: number | null
  processedItems?: number | null
  totalItems?: number | null
  baselineEvaluationId?: string | null
  currentBaselineEvaluationId?: string | null
  updatedAt?: string | null
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
    current_feedback_evaluation_id?: string | null
    original_feedback_evaluation_id?: string | null
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
  createdAt?: string | null
  updatedAt?: string | null
  metadata?: string | null
  scoreVersionId?: string | null
  accountId?: string | null
}

export type ProcedureTaskRecord = NonNullable<OptimizerRunView['task']>

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
    celeryTaskId?: string | null
    workerNodeId?: string | null
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
  feedbackEvaluationSummary?: ProcedureFeedbackEvaluationSummary | null
}

export type ScoreVersionSummary = {
  id: string
  isFeatured?: string | null
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
  scoreId?: string | null
  scoreVersionId?: string | null
  taskId?: string | null
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

function currentFeedbackEvaluationIdFromCycle(cycle: Record<string, any> | null | undefined): string | null {
  if (!cycle) return null
  if (cycle.accepted !== true && cycle.status !== 'accepted' && cycle.status !== 'carried') return null
  const value = cycle.feedback_evaluation_id ?? cycle.recent_evaluation_id
  return typeof value === 'string' && value ? value : null
}

export function currentProcedureFeedbackEvaluationId(
  manifest: OptimizerManifest | null | undefined
): string | null {
  if (!manifest) return null

  for (const cycle of [...(manifest.cycles ?? [])].reverse()) {
    const cycleEvaluationId = currentFeedbackEvaluationIdFromCycle(cycle)
    if (cycleEvaluationId) return cycleEvaluationId
  }

  const bestEvaluationId = manifest.best?.best_feedback_evaluation_id
  if (typeof bestEvaluationId === 'string' && bestEvaluationId) return bestEvaluationId

  const currentBaselineEvaluationId = manifest.baseline?.current_feedback_evaluation_id
  if (typeof currentBaselineEvaluationId === 'string' && currentBaselineEvaluationId) return currentBaselineEvaluationId

  const originalBaselineEvaluationId = manifest.baseline?.original_feedback_evaluation_id
  return typeof originalBaselineEvaluationId === 'string' && originalBaselineEvaluationId
    ? originalBaselineEvaluationId
    : null
}

export function feedbackEvaluationSummaryFromView(
  evaluation: ScoreEvaluationView | null | undefined
): ProcedureFeedbackEvaluationSummary | null {
  if (!evaluation?.id) return null
  return {
    id: evaluation.id,
    status: evaluation.status ?? null,
    accuracy: evaluation.accuracy ?? null,
    processedItems: evaluation.processedItems ?? null,
    totalItems: evaluation.totalItems ?? null,
    baselineEvaluationId: evaluation.baselineEvaluationId ?? null,
    currentBaselineEvaluationId: evaluation.currentBaselineEvaluationId ?? null,
    updatedAt: evaluation.updatedAt ?? evaluation.createdAt ?? null,
  }
}

export function procedureRunReferencesFeedbackEvaluation(
  run: OptimizerRunView,
  evaluationId: string | null | undefined
): boolean {
  return Boolean(evaluationId && currentProcedureFeedbackEvaluationId(run.manifest) === evaluationId)
}

export function mergeFeedbackEvaluationIntoProcedureRun(
  run: OptimizerRunView,
  evaluation: ScoreEvaluationView
): OptimizerRunView {
  if (!procedureRunReferencesFeedbackEvaluation(run, evaluation.id)) return run
  return {
    ...run,
    feedbackEvaluationSummary: feedbackEvaluationSummaryFromView(evaluation),
  }
}

export async function loadScoreEvaluationById(evaluationId: string): Promise<ScoreEvaluationView | null> {
  const response = await getAmplifyClient().graphql({
    query: `
      query GetEvaluationForProcedurePerformance($id: ID!) {
        getEvaluation(id: $id) {
          ${EVALUATION_CARD_FIELDS}
        }
      }
    `,
    variables: { id: evaluationId },
  }) as any

  const evaluation = response.data?.getEvaluation
  return evaluation ? evaluationToScoreEvaluationView(evaluation) : null
}

export async function hydrateProcedureRunFeedbackEvaluation(
  run: OptimizerRunView
): Promise<OptimizerRunView> {
  const evaluationId = currentProcedureFeedbackEvaluationId(run.manifest)
  if (!evaluationId) {
    return { ...run, feedbackEvaluationSummary: null }
  }

  try {
    const evaluation = await loadScoreEvaluationById(evaluationId)
    return {
      ...run,
      feedbackEvaluationSummary: feedbackEvaluationSummaryFromView(evaluation),
    }
  } catch (error) {
    console.error('Failed to load procedure feedback evaluation', evaluationId, error)
    return run
  }
}

export async function hydrateProcedureRunsFeedbackEvaluations(
  runs: OptimizerRunView[]
): Promise<OptimizerRunView[]> {
  const evaluationIds = [
    ...new Set(runs.map((run) => currentProcedureFeedbackEvaluationId(run.manifest)).filter(Boolean)),
  ] as string[]

  if (evaluationIds.length === 0) {
    return runs.map((run) => ({ ...run, feedbackEvaluationSummary: null }))
  }

  const evaluations = await Promise.all(
    evaluationIds.map(async (evaluationId) => {
      try {
        return await loadScoreEvaluationById(evaluationId)
      } catch (error) {
        console.error('Failed to load procedure feedback evaluation', evaluationId, error)
        return null
      }
    })
  )
  const evaluationsById = new Map(
    evaluations
      .filter((evaluation): evaluation is ScoreEvaluationView => Boolean(evaluation?.id))
      .map((evaluation) => [evaluation.id, evaluation])
  )

  return runs.map((run) => {
    const evaluationId = currentProcedureFeedbackEvaluationId(run.manifest)
    const evaluation = evaluationId ? evaluationsById.get(evaluationId) : null
    return {
      ...run,
      feedbackEvaluationSummary: feedbackEvaluationSummaryFromView(evaluation),
    }
  })
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

  return manifestValueReferencesVersion(manifest, versionId)
}

function manifestValueReferencesVersion(value: unknown, versionId: string): boolean {
  if (value == null) return false
  if (typeof value === 'string') return value === versionId
  if (typeof value !== 'object') return false
  if (Array.isArray(value)) {
    return value.some((item) => manifestValueReferencesVersion(item, versionId))
  }
  return Object.values(value as Record<string, unknown>).some((item) =>
    manifestValueReferencesVersion(item, versionId)
  )
}

export function procedureIdFromTaskTarget(target: unknown): string | null {
  const text = String(target ?? '')
  if (text.startsWith('procedure/run/')) return text.slice('procedure/run/'.length)
  if (text.startsWith('procedure/')) return text.slice('procedure/'.length)
  return null
}

function normalizeTaskRecord(task: any): ProcedureTaskRecord | null {
  if (!task?.id) return null
  return {
    id: String(task.id),
    type: task.type ?? null,
    status: task.status ?? null,
    target: task.target ?? null,
    command: task.command ?? null,
    description: task.description ?? null,
    dispatchStatus: task.dispatchStatus ?? null,
    celeryTaskId: task.celeryTaskId ?? null,
    workerNodeId: task.workerNodeId ?? null,
    metadata: task.metadata ?? null,
    createdAt: task.createdAt ?? null,
    startedAt: task.startedAt ?? null,
    completedAt: task.completedAt ?? null,
    estimatedCompletionAt: task.estimatedCompletionAt ?? null,
    errorMessage: task.errorMessage ?? null,
    errorDetails: task.errorDetails ?? null,
    currentStageId: task.currentStageId ?? null,
    stages: task.stages
      ? {
          items: (task.stages.items ?? []).map((stage: any) => ({
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
}

export function taskMatchesEvaluation(task: any, evaluation: ScoreEvaluationView): boolean {
  if (!task?.id) return false
  if (evaluation.task?.id === task.id) return true
  if (evaluation.taskId === task.id) return true
  return false
}

export function mergeTaskIntoEvaluation(
  evaluation: ScoreEvaluationView,
  task: any
): ScoreEvaluationView {
  const normalizedTask = normalizeTaskRecord(task)
  if (!normalizedTask) return evaluation
  return {
    ...evaluation,
    taskId: evaluation.taskId ?? normalizedTask.id,
    task: {
      ...evaluation.task,
      ...normalizedTask,
      stages: evaluation.task?.stages ?? normalizedTask.stages,
    },
    status: normalizedTask.status ?? evaluation.status,
    updatedAt: normalizedTask.completedAt ?? normalizedTask.startedAt ?? evaluation.updatedAt,
  }
}

export function mergeTaskStageIntoEvaluation(
  evaluation: ScoreEvaluationView,
  stage: any
): ScoreEvaluationView {
  if (!stage?.taskId || !taskMatchesEvaluation({ id: stage.taskId }, evaluation)) return evaluation
  const currentItems = evaluation.task?.stages?.items ?? []
  const nextItems = [...currentItems]
  const existingIndex = nextItems.findIndex((item) => item.id === stage.id)
  const normalizedStage = {
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
  }
  if (existingIndex >= 0) {
    nextItems[existingIndex] = { ...nextItems[existingIndex], ...normalizedStage }
  } else {
    nextItems.push(normalizedStage)
  }
  nextItems.sort((left, right) => left.order - right.order)
  return {
    ...evaluation,
    task: {
      ...(evaluation.task ?? { id: String(stage.taskId) }),
      id: String(stage.taskId),
      currentStageId: normalizedStage.status === 'RUNNING' ? normalizedStage.name : evaluation.task?.currentStageId,
      stages: { items: nextItems },
    },
  }
}

export function procedureRunMatchesTask(run: OptimizerRunView, task: any): boolean {
  const procedureId = procedureIdFromTaskTarget(task?.target)
  return Boolean(procedureId && procedureId === run.procedureId)
}

export function mergeTaskIntoProcedureRun(run: OptimizerRunView, task: any): OptimizerRunView {
  const normalizedTask = normalizeTaskRecord(task)
  if (!normalizedTask) return run
  return {
    ...run,
    task: {
      ...run.task,
      ...normalizedTask,
      stages: run.task?.stages ?? normalizedTask.stages,
    },
    status: normalizedTask.status ?? run.status,
    updatedAt: normalizedTask.completedAt ?? normalizedTask.startedAt ?? run.updatedAt,
  }
}

export function mergeTaskStageIntoProcedureRun(run: OptimizerRunView, stage: any): OptimizerRunView {
  if (!stage?.taskId || run.task?.id !== stage.taskId) return run
  const currentItems = run.task?.stages?.items ?? []
  const nextItems = [...currentItems]
  const existingIndex = nextItems.findIndex((item) => item.id === stage.id)
  const normalizedStage = {
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
  }
  if (existingIndex >= 0) {
    nextItems[existingIndex] = { ...nextItems[existingIndex], ...normalizedStage }
  } else {
    nextItems.push(normalizedStage)
  }
  nextItems.sort((left, right) => left.order - right.order)
  return {
    ...run,
    task: {
      ...(run.task ?? { id: String(stage.taskId) }),
      id: String(stage.taskId),
      currentStageId: normalizedStage.status === 'RUNNING' ? normalizedStage.name : run.task?.currentStageId,
      stages: { items: nextItems },
    },
  }
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

async function loadManifestFromProcedureMetadata(procedure: any): Promise<{
  indexed: boolean
  manifestKey: string | null
  artifactPointer: OptimizerRunView['artifactPointer']
  manifest: OptimizerManifest | null
}> {
  const metadata = safeJsonParse<Record<string, any>>(procedure.metadata)
  const artifactPointer = safeJsonParse<Record<string, any>>(metadata?.optimizer_artifacts)
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
  }
}

export async function procedureToOptimizerRunView(
  procedure: any,
  task?: any | null
): Promise<OptimizerRunView> {
  const manifestData = await loadManifestFromProcedureMetadata(procedure)
  return {
    procedureId: procedure.id,
    name: procedure.name,
    procedureDescription: procedure.description ?? null,
    status: procedure.status,
    updatedAt: procedure.updatedAt ?? procedure.createdAt ?? null,
    metadataText:
      typeof procedure.metadata === 'string'
        ? procedure.metadata
        : procedure.metadata != null
          ? JSON.stringify(procedure.metadata)
          : null,
    ...manifestData,
    scoreVersionId: procedure.scoreVersionId ?? null,
    task: normalizeTaskRecord(task),
  } satisfies OptimizerRunView
}

export async function refreshOptimizerRunManifest(run: OptimizerRunView): Promise<OptimizerRunView> {
  if (!run.manifestKey) return run
  try {
    const manifestText = await openArtifactText(run.manifestKey)
    const manifest = JSON.parse(manifestText) as OptimizerManifest
    return {
      ...run,
      indexed: true,
      manifest,
    }
  } catch (error) {
    console.error('Failed to refresh optimizer manifest for procedure', run.procedureId, error)
    return run
  }
}

async function loadProcedureRecordsByScoreId(scoreId: string, pageSize: number): Promise<ProcedureRecord[]> {
  const client = getAmplifyClient()
  const procedures: ProcedureRecord[] = []
  let nextToken: string | null | undefined = null

  do {
    const procedureResponse = await client.graphql({
      query: `
        query ListProcedureByScoreIdAndUpdatedAtWorkbench(
          $scoreId: String!
          $sortDirection: ModelSortDirection
          $limit: Int
          $nextToken: String
        ) {
          listProcedureByScoreIdAndUpdatedAt(
            scoreId: $scoreId
            sortDirection: $sortDirection
            limit: $limit
            nextToken: $nextToken
          ) {
            items {
              ${PROCEDURE_CARD_FIELDS}
            }
            nextToken
          }
        }
      `,
      variables: {
        scoreId,
        sortDirection: 'DESC',
        limit: pageSize,
        nextToken,
      },
    }) as any

    const page = procedureResponse.data?.listProcedureByScoreIdAndUpdatedAt
    procedures.push(...(page?.items ?? []))
    nextToken = page?.nextToken ?? null
  } while (nextToken)

  return procedures
}

async function loadProcedureRecordsByScoreVersionId(
  scoreVersionId: string,
  pageSize: number
): Promise<ProcedureRecord[]> {
  const client = getAmplifyClient()
  const procedures: ProcedureRecord[] = []
  let nextToken: string | null | undefined = null

  do {
    const procedureResponse = await client.graphql({
      query: `
        query ListProcedureScoreVersionByScoreVersionIdAndUpdatedAtWorkbench(
          $scoreVersionId: String!
          $sortDirection: ModelSortDirection
          $limit: Int
          $nextToken: String
        ) {
          listProcedureScoreVersionByScoreVersionIdAndUpdatedAt(
            scoreVersionId: $scoreVersionId
            sortDirection: $sortDirection
            limit: $limit
            nextToken: $nextToken
          ) {
            items {
              procedure {
                ${PROCEDURE_CARD_FIELDS}
              }
            }
            nextToken
          }
        }
      `,
      variables: {
        scoreVersionId,
        sortDirection: 'DESC',
        limit: pageSize,
        nextToken,
      },
    }) as any

    const page = procedureResponse.data?.listProcedureScoreVersionByScoreVersionIdAndUpdatedAt
    procedures.push(...(page?.items ?? []).map((item: any) => item?.procedure).filter(Boolean))
    nextToken = page?.nextToken ?? null
  } while (nextToken)

  return procedures
}

async function procedureRecordsToOptimizerRunViews(
  procedures: ProcedureRecord[]
): Promise<OptimizerRunView[]> {
  const client = getAmplifyClient()
  const accountIds = [...new Set(procedures.map((procedure) => procedure.accountId).filter(Boolean))]
  const taskResponses = await Promise.all(
    accountIds.map((accountId) =>
      client.graphql({
        query: `
          query ListTaskByAccountIdAndUpdatedAtForProcedureWorkbench(
            $accountId: String!
            $sortDirection: ModelSortDirection
            $limit: Int
          ) {
            listTaskByAccountIdAndUpdatedAt(
              accountId: $accountId
              sortDirection: $sortDirection
              limit: $limit
            ) {
                items {
                  ${TASK_CARD_FIELDS}
                }
              }
            }
        `,
        variables: {
          accountId,
          sortDirection: 'DESC',
          limit: 1000,
        },
      }) as any
    )
  )

  const taskItems: ProcedureTaskRecord[] = taskResponses.flatMap(
    (response) => response.data?.listTaskByAccountIdAndUpdatedAt?.items ?? []
  )
  const tasksByProcedureId = new Map<string, ProcedureTaskRecord>()
  for (const task of taskItems) {
    const procedureId = procedureIdFromTaskTarget(task.target)
    if (procedureId) tasksByProcedureId.set(procedureId, task)
  }

  return Promise.all(
    procedures.map(async (procedure) => {
      const task = tasksByProcedureId.get(procedure.id)
      return procedureToOptimizerRunView(procedure, task)
    })
  )
}

export async function loadOptimizerRuns(scoreId: string, pageSize: number = 100): Promise<OptimizerRunView[]> {
  const procedures = await loadProcedureRecordsByScoreId(scoreId, pageSize)
  return procedureRecordsToOptimizerRunViews(procedures)
}

export async function loadScoreVersionOptimizerRuns(
  scoreVersionId: string,
  pageSize: number = 100
): Promise<OptimizerRunView[]> {
  const procedures = await loadProcedureRecordsByScoreVersionId(scoreVersionId, pageSize)
  return procedureRecordsToOptimizerRunViews(procedures)
}

export function evaluationToScoreEvaluationView(item: any): ScoreEvaluationView {
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
    scoreId: item.scoreId ?? null,
    scoreVersionId: item.scoreVersionId ?? null,
    taskId: item.taskId ?? item.task?.id ?? null,
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
    task: normalizeTaskRecord(item.task),
  } satisfies ScoreEvaluationView
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
            ${EVALUATION_CARD_FIELDS}
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
  return items.map(evaluationToScoreEvaluationView)
}

export async function loadScoreVersionEvaluations(
  scoreVersionId: string,
  limit: number = 100
): Promise<ScoreEvaluationView[]> {
  const response = await getAmplifyClient().graphql({
    query: `
      query ListEvaluationByScoreVersionIdAndCreatedAtForWorkbench(
        $scoreVersionId: String!
        $sortDirection: ModelSortDirection!
        $limit: Int
      ) {
        listEvaluationByScoreVersionIdAndCreatedAt(
          scoreVersionId: $scoreVersionId
          sortDirection: $sortDirection
          limit: $limit
        ) {
          items {
            ${EVALUATION_CARD_FIELDS}
          }
        }
      }
    `,
    variables: {
      scoreVersionId,
      sortDirection: 'DESC',
      limit,
    },
  }) as any

  const items = response.data?.listEvaluationByScoreVersionIdAndCreatedAt?.items ?? []
  return items.map(evaluationToScoreEvaluationView)
}
