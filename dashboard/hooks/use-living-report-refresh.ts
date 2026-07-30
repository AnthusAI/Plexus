import { useEffect } from 'react'

import { observeTaskStageUpdates, observeTaskUpdates } from '@/utils/subscriptions'

export const LIVING_REPORT_REFRESH_INTERVAL_MS = 15_000

const TERMINAL_TASK_STATUSES = new Set(['COMPLETED', 'FAILED', 'STALLED', 'CANCELLED'])

export const isTerminalLivingReportTask = (status?: string | null): boolean =>
  TERMINAL_TASK_STATUSES.has(String(status || '').toUpperCase())

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
    if (!reportId || !taskId) return

    const refreshSelectedReport = () => {
      void refresh(reportId)
    }

    const taskSubscription = observeTaskUpdates().subscribe({
      next: (event: any) => {
        if (event?.data?.id === taskId) refreshSelectedReport()
      },
      error: (error: unknown) => {
        console.error('Living Report task subscription error:', error)
      },
    })
    const stageSubscription = observeTaskStageUpdates().subscribe({
      next: (event: any) => {
        if (event?.data?.taskId === taskId) refreshSelectedReport()
      },
      error: (error: unknown) => {
        console.error('Living Report task-stage subscription error:', error)
      },
    })

    const interval = isTerminalLivingReportTask(taskStatus)
      ? null
      : window.setInterval(refreshSelectedReport, LIVING_REPORT_REFRESH_INTERVAL_MS)

    return () => {
      if (interval !== null) window.clearInterval(interval)
      taskSubscription.unsubscribe()
      stageSubscription.unsubscribe()
    }
  }, [refresh, reportId, taskId, taskStatus])
}
