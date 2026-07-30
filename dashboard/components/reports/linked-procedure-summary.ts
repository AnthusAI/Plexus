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

export const linkedProcedureSubtitle = (procedure: ProcedureTaskData): string => {
  const type = procedure.procedureType || procedure.task?.type || 'Procedure'
  const rawStatus = procedure.task?.status || procedure.status || 'PENDING'
  const status = rawStatus.charAt(0).toUpperCase() + rawStatus.slice(1).toLowerCase()
  return `${type} • ${status}`
}

export const buildLinkedProcedureSummary = ({
  reportName,
  reportCreatedAt,
  reportUpdatedAt,
  reportCreatedByUserId,
  task,
}: LinkedProcedureSummaryInput): ProcedureTaskData | null => {
  if (!task) return null
  const metadata = record(task.metadata)
  const id = procedureId(task, metadata)
  if (!id) return null

  const identity = record(metadata.operator_identity)
  const procedureType = (
    typeof metadata.procedure_type === 'string' && metadata.procedure_type.trim()
      ? metadata.procedure_type.trim()
      : String(task.type || 'Procedure')
  )
  const displayTitle = (
    typeof identity.display_title === 'string' && identity.display_title.trim()
      ? identity.display_title.trim()
      : reportName
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
    status: task.status || undefined,
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
