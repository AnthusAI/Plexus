type JsonRecord = Record<string, unknown>

const record = (value: unknown): JsonRecord | null =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonRecord
    : null

const relationItems = (value: unknown): unknown[] => {
  const relation = record(value)
  return Array.isArray(relation?.items) ? relation.items : []
}

const identity = (value: unknown): string => {
  const item = record(value)
  const order = typeof item?.order === 'number' ? String(item.order).padStart(12, '0') : ''
  return `${order}:${String(item?.id || '')}`
}

const canonicalize = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(canonicalize)
  const item = record(value)
  if (!item) return value
  return Object.fromEntries(
    Object.keys(item).sort().map(key => [key, canonicalize(item[key])]),
  )
}

/**
 * Fingerprint the data that can change a mounted living Report presentation.
 * GraphQL relation order is not a visible revision, so blocks and stages are
 * sorted by their durable identities before canonical serialization.
 */
export function livingReportSnapshotKey(reportValue: unknown): string {
  const report = record(reportValue) || {}
  const task = record(report.task)
  const reportBlocks = relationItems(report.reportBlocks)
    .slice()
    .sort((left, right) => identity(left).localeCompare(identity(right)))
  const stages = relationItems(task?.stages)
    .slice()
    .sort((left, right) => identity(left).localeCompare(identity(right)))

  const snapshot = {
    ...report,
    reportBlocks: { items: reportBlocks },
    task: task ? { ...task, stages: { items: stages } } : null,
  }
  return JSON.stringify(canonicalize(snapshot))
}
