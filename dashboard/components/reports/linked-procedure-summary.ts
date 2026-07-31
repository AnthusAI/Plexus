import type { ProcedureTaskData } from '@/components/ProcedureTask'

type LinkedTask = {
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
  stages?: { items?: any[] | null } | null
}

type LinkedProcedureSummaryInput = {
  reportId: string
  reportName: string
  reportCreatedAt: string
  reportUpdatedAt?: string | null
  reportCreatedByUserId?: string | null
  task?: LinkedTask | null
  optimizationFinalStatus?: string | null
}

type OptimizationReportIdentityInput = {
  id: string
  taskId?: string | null
  updatedAt?: string | null
  parameters?: unknown
}

export type OptimizationReportSupersession = {
  reportId: string
  latestRevision: number
}

const record = (value: unknown): Record<string, any> => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, any>
  }
  if (typeof value !== 'string' || !value.trim()) return {}
  try {
    const parsed = JSON.parse(value)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
  } catch {
    return {}
  }
}

export const optimizationReportSupersessionMap = (
  reports: OptimizationReportIdentityInput[],
): Map<string, OptimizationReportSupersession> => {
  const groups = new Map<string, Array<{
    id: string
    latestRevision: number
    updatedAt: number
  }>>()

  for (const report of reports) {
    const taskId = typeof report.taskId === 'string' ? report.taskId.trim() : ''
    const optimizationRun = record(record(report.parameters).optimization_run)
    const runKey = typeof optimizationRun.run_key === 'string'
      ? optimizationRun.run_key.trim()
      : ''
    if (!taskId || !runKey) continue
    const revisionValue = record(optimizationRun.latest_revision).number
    const latestRevision = typeof revisionValue === 'number' && Number.isFinite(revisionValue)
      ? Math.max(0, Math.trunc(revisionValue))
      : 0
    const parsedUpdatedAt = Date.parse(String(report.updatedAt || ''))
    const groupKey = `${taskId}\u0000${runKey}`
    const group = groups.get(groupKey) || []
    group.push({
      id: report.id,
      latestRevision,
      updatedAt: Number.isFinite(parsedUpdatedAt) ? parsedUpdatedAt : 0,
    })
    groups.set(groupKey, group)
  }

  const result = new Map<string, OptimizationReportSupersession>()
  for (const group of groups.values()) {
    if (group.length < 2) continue
    const ordered = [...group].sort((left, right) => (
      right.latestRevision - left.latestRevision
      || right.updatedAt - left.updatedAt
      || right.id.localeCompare(left.id)
    ))
    const canonical = ordered[0]
    for (const duplicate of ordered.slice(1)) {
      result.set(duplicate.id, {
        reportId: canonical.id,
        latestRevision: canonical.latestRevision,
      })
    }
  }
  return result
}

const procedureId = (task: LinkedTask, metadata: Record<string, any>): string | null => {
  const fromMetadata = metadata.procedure_id || metadata.procedureId
  if (typeof fromMetadata === 'string' && fromMetadata.trim()) return fromMetadata.trim()

  const target = String(task.target || '').trim()
  const match = target.match(/^procedure(?:\/run)?\/([^/]+)$/)
  return match?.[1] || null
}

const conciseScope = (identity: Record<string, any>): string | undefined => {
  if (identity.kind === 'account_wide_portfolio') return 'All scorecards'
  if (identity.kind === 'scorecard_scoped_portfolio') return 'Focused scorecard portfolio'
  if (identity.kind === 'single_score') {
    return typeof identity.display_scope === 'string' ? identity.display_scope : 'One score'
  }
  return undefined
}

const optimizationLifecycleStatus = (
  metadata: Record<string, any>,
  fallback?: string | null,
  reportStatus?: string | null,
): string | undefined => {
  const raw = typeof reportStatus === 'string' && reportStatus.trim()
    ? reportStatus.trim().toUpperCase()
    : typeof metadata.optimization_run_final_status === 'string'
      ? metadata.optimization_run_final_status.trim().toUpperCase()
      : ''
  const normalized = raw === 'COMPLETE'
    ? 'COMPLETED'
    : raw === 'COMPLETE_WITH_UNRESOLVED_ACTIONS'
      ? 'COMPLETED_WITH_UNRESOLVED_ACTIONS'
      : raw
  return normalized || fallback || undefined
}

export const optimizationFinalStatusFromReportBlocks = (
  blocks: Array<{ type?: string | null; output?: unknown }> | null | undefined,
): string | undefined => {
  const statusBlock = blocks?.find(block => block.type === 'OptimizationRunStatus')
  if (!statusBlock) return undefined
  const output = record(statusBlock.output)
  const preview = record(output.preview)
  const summary = record(preview.summary)
  const overview = record(summary.overview)
  const raw = overview.lifecycle_status
  return typeof raw === 'string' && raw.trim() ? raw.trim().toUpperCase() : undefined
}

export const linkedProcedureSubtitle = (procedure: ProcedureTaskData): string => {
  const type = procedure.procedureType || procedure.task?.type || 'Procedure'
  const rawStatus = procedure.status || procedure.task?.status || 'PENDING'
  const status = rawStatus.charAt(0).toUpperCase() + rawStatus.slice(1).toLowerCase()
  return `${type} • ${status}`
}

export const buildLinkedProcedureSummary = ({
  reportName,
  reportCreatedAt,
  reportUpdatedAt,
  reportCreatedByUserId,
  task,
  optimizationFinalStatus,
}: LinkedProcedureSummaryInput): ProcedureTaskData | null => {
  if (!task) return null
  const metadata = record(task.metadata)
  const id = procedureId(task, metadata)
  if (!id) return null

  const identity = record(metadata.operator_identity)
  const storedProcedureType = (
    typeof metadata.procedure_type === 'string' && metadata.procedure_type.trim()
      ? metadata.procedure_type.trim()
      : String(task.type || 'Procedure')
  )
  const procedureType = (
    /portfolio/i.test(storedProcedureType)
    || /portfolio/i.test(String(identity.kind || ''))
  )
    ? 'Optimization opportunity survey'
    : storedProcedureType
  const displayTitle = (
    typeof identity.display_title === 'string' && identity.display_title.trim()
      ? identity.display_title.trim()
      : reportName
  )
  const lifecycleStatus = optimizationLifecycleStatus(
    metadata,
    task.status,
    optimizationFinalStatus,
  )

  return {
    id,
    title: displayTitle,
    featured: false,
    createdAt: task.createdAt || reportCreatedAt,
    updatedAt: reportUpdatedAt || task.completedAt || task.startedAt || reportCreatedAt,
    procedureType,
    displayTitle,
    displayScope: conciseScope(identity),
    status: lifecycleStatus,
    taskId: task.id,
    createdByUserId: reportCreatedByUserId || null,
    task: {
      id: task.id,
      type: procedureType,
      status: task.status || 'PENDING',
      target: task.target || '',
      command: task.command || '',
      description: task.description || undefined,
      dispatchStatus: task.dispatchStatus || undefined,
      metadata: typeof task.metadata === 'string' ? task.metadata : JSON.stringify(task.metadata || {}),
      createdAt: task.createdAt || undefined,
      startedAt: task.startedAt || undefined,
      completedAt: task.completedAt || undefined,
      estimatedCompletionAt: task.estimatedCompletionAt || undefined,
      errorMessage: task.errorMessage || undefined,
      errorDetails: typeof task.errorDetails === 'string'
        ? task.errorDetails
        : task.errorDetails != null
          ? JSON.stringify(task.errorDetails)
          : undefined,
      currentStageId: task.currentStageId || undefined,
      stages: { items: task.stages?.items || [] },
    },
  }
}
