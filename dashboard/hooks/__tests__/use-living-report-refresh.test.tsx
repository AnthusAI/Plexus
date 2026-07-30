import React from 'react'
import { render } from '@testing-library/react'

import {
  LIVING_REPORT_REFRESH_INTERVAL_MS,
  resolveLivingReportTaskId,
  useLivingReportRefresh,
} from '@/hooks/use-living-report-refresh'
import { observeTaskStageUpdates, observeTaskUpdates } from '@/utils/subscriptions'

jest.mock('@/utils/subscriptions', () => ({
  observeTaskUpdates: jest.fn(),
  observeTaskStageUpdates: jest.fn(),
}))

type Handlers = { next: (value: any) => void; error: (error: unknown) => void }

describe('useLivingReportRefresh', () => {
  let taskHandlers: Handlers
  let stageHandlers: Handlers
  let unsubscribeTask: jest.Mock
  let unsubscribeStage: jest.Mock

  beforeEach(() => {
    jest.useFakeTimers()
    unsubscribeTask = jest.fn()
    unsubscribeStage = jest.fn()
    ;(observeTaskUpdates as jest.Mock).mockReturnValue({
      subscribe: (handlers: Handlers) => {
        taskHandlers = handlers
        return { unsubscribe: unsubscribeTask }
      },
    })
    ;(observeTaskStageUpdates as jest.Mock).mockReturnValue({
      subscribe: (handlers: Handlers) => {
        stageHandlers = handlers
        return { unsubscribe: unsubscribeStage }
      },
    })
  })

  afterEach(() => {
    jest.useRealTimers()
    jest.clearAllMocks()
  })

  function Harness({ status, refresh }: { status: string; refresh: jest.Mock }) {
    useLivingReportRefresh({
      reportId: 'report-1',
      taskId: 'task-1',
      taskStatus: status,
      refresh,
    })
    return null
  }

  it('refreshes for matching task and stage events and ignores unrelated events', () => {
    const refresh = jest.fn()
    render(<Harness status="RUNNING" refresh={refresh} />)

    taskHandlers.next({ data: { id: 'other-task' } })
    stageHandlers.next({ data: { taskId: 'other-task' } })
    expect(refresh).not.toHaveBeenCalled()

    taskHandlers.next({ data: { id: 'task-1' } })
    stageHandlers.next({ data: { taskId: 'task-1' } })
    expect(refresh).toHaveBeenNthCalledWith(1, 'report-1')
    expect(refresh).toHaveBeenNthCalledWith(2, 'report-1')
  })

  it('polls active reports and stops polling when the linked task becomes terminal', () => {
    const refresh = jest.fn()
    const { rerender } = render(<Harness status="RUNNING" refresh={refresh} />)

    jest.advanceTimersByTime(LIVING_REPORT_REFRESH_INTERVAL_MS)
    expect(refresh).toHaveBeenCalledWith('report-1')

    refresh.mockClear()
    rerender(<Harness status="COMPLETED" refresh={refresh} />)
    expect(refresh).toHaveBeenCalledTimes(1)
    refresh.mockClear()
    jest.advanceTimersByTime(LIVING_REPORT_REFRESH_INTERVAL_MS * 2)
    expect(refresh).not.toHaveBeenCalled()
  })

  it('retains the report task id while the nested task relation is still hydrating', () => {
    expect(resolveLivingReportTaskId({ taskId: 'task-1', task: null })).toBe('task-1')
    expect(resolveLivingReportTaskId({ taskId: 'task-1', task: { id: 'task-2' } })).toBe('task-2')
  })

  it('performs one final reconciliation when the linked task becomes terminal', () => {
    const refresh = jest.fn()
    const { rerender } = render(<Harness status="RUNNING" refresh={refresh} />)
    refresh.mockClear()

    rerender(<Harness status="COMPLETED" refresh={refresh} />)

    expect(refresh).toHaveBeenCalledTimes(1)
    expect(refresh).toHaveBeenCalledWith('report-1')
    refresh.mockClear()
    jest.advanceTimersByTime(LIVING_REPORT_REFRESH_INTERVAL_MS * 2)
    expect(refresh).not.toHaveBeenCalled()
  })

  it('cleans up both subscriptions and the active interval', () => {
    const refresh = jest.fn()
    const { unmount } = render(<Harness status="RUNNING" refresh={refresh} />)

    unmount()
    jest.advanceTimersByTime(LIVING_REPORT_REFRESH_INTERVAL_MS)

    expect(refresh).not.toHaveBeenCalled()
    expect(unsubscribeTask).toHaveBeenCalledTimes(1)
    expect(unsubscribeStage).toHaveBeenCalledTimes(1)
  })
})
