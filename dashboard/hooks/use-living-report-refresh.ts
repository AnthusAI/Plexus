import { useEffect } from 'react'

import { observeTaskStageUpdates, observeTaskUpdates } from '@/utils/subscriptions'

export const LIVING_REPORT_REFRESH_INTERVAL_MS = 15_000

const TERMINAL_TASK_STATUSES = new Set(['COMPLETED', 'FAILED', 'STALLED', 'CANCELLED'])

export const isTerminalLivingReportTask = (status?: string | null): boolean =>
  TERMINAL_TASK_STATUSES.has(String(status || '').toUpperCase())

type LivingReportTaskReference = {
  taskId?: string | null
  task?: { id?: string | null } | null
}

/** Preserve the direct foreign key while the nested Task relation hydrates. */
export const resolveLivingReportTaskId = (report?: LivingReportTaskReference | null): string | null =>
  report?.task?.id || report?.taskId || null

type LivingReportRefreshOptions = {
  reportId: string | null
  taskId?: string | null
  taskStatus?: string | null
  refresh: (reportId: string) => Promise<void> | void
}

/** Keep a selected living Report synchronized with its linked Task lifecycle. */
export function useLivingReportRefresh({
  reportId,
  taskId,
  taskStatus,
  refresh,
}: LivingReportRefreshOptions): void {
  useEffect(() => {
    if (!reportId) return

    const refreshSelectedReport = () => {
      void refresh(reportId)
    }

    // A newly-created Report can become visible before its Task relation (or
    // even the direct taskId) reaches this query. Reconcile immediately and
    // keep polling during that bootstrap window so a missed linking event
    // cannot leave the mounted page stale until navigation or reload.
    if (!taskId) refreshSelectedReport()

    // The terminal Task event can arrive just ahead of the final ReportBlock
    // invalidation. Reconcile once more before disabling background polling.
    if (isTerminalLivingReportTask(taskStatus)) refreshSelectedReport()

    const taskSubscription = taskId
      ? observeTaskUpdates().subscribe({
          next: (event: any) => {
            if (event?.data?.id === taskId) refreshSelectedReport()
          },
          error: (error: unknown) => {
            console.error('Living Report task subscription error:', error)
          },
        })
      : null
    const stageSubscription = taskId
      ? observeTaskStageUpdates().subscribe({
          next: (event: any) => {
            if (event?.data?.taskId === taskId) refreshSelectedReport()
          },
          error: (error: unknown) => {
            console.error('Living Report task-stage subscription error:', error)
          },
        })
      : null

    // Subscriptions provide the low-latency path, while this reconciliation
    // timer protects against missed or reordered Report/Task/TaskStage/
    // ReportBlock events. Keep it active for the selected terminal report too:
    // final presentation publication can legitimately trail the Task event.
    const interval = window.setInterval(
      refreshSelectedReport,
      LIVING_REPORT_REFRESH_INTERVAL_MS,
    )

    return () => {
      window.clearInterval(interval)
      taskSubscription?.unsubscribe()
      stageSubscription?.unsubscribe()
    }
  }, [refresh, reportId, taskId, taskStatus])
}
