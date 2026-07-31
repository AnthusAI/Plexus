import { livingReportSnapshotKey } from '@/lib/living-report-snapshot'

const reportSnapshot = () => ({
  id: 'report-1',
  name: 'Optimization portfolio',
  updatedAt: '2026-07-31T10:00:00Z',
  output: '# Portfolio',
  taskId: 'task-1',
  task: {
    id: 'task-1',
    status: 'RUNNING',
    currentStageId: 'stage-1',
    stages: {
      items: [{
        id: 'stage-1',
        order: 1,
        status: 'RUNNING',
        processedItems: 2,
        totalItems: 10,
        statusMessage: 'Assessing scores',
      }],
    },
  },
  reportBlocks: {
    items: [{
      id: 'block-1',
      position: 0,
      type: 'OptimizationRunStatus',
      output: { preview: { summary: { live_progress: { current: 2, total: 10 } } } },
      log: null,
      attachedFiles: ['workbook.xlsx'],
    }],
  },
})

describe('livingReportSnapshotKey', () => {
  it('treats a refetched but unchanged report as the same visible snapshot', () => {
    const first = reportSnapshot()
    const refetched = JSON.parse(JSON.stringify(first))

    expect(livingReportSnapshotKey(refetched)).toBe(livingReportSnapshotKey(first))
  })

  it('changes when live progress or the visible task stage changes', () => {
    const original = reportSnapshot()
    const progressed = reportSnapshot()
    ;(progressed.reportBlocks.items[0].output as any).preview.summary.live_progress.current = 3
    const stageChanged = reportSnapshot()
    stageChanged.task.stages.items[0].processedItems = 3

    expect(livingReportSnapshotKey(progressed)).not.toBe(livingReportSnapshotKey(original))
    expect(livingReportSnapshotKey(stageChanged)).not.toBe(livingReportSnapshotKey(original))
  })

  it('does not change merely because blocks or stages arrive in a different relation order', () => {
    const first = reportSnapshot()
    first.reportBlocks.items.push({
      id: 'block-2', position: 1, type: 'Other', output: {}, log: null, attachedFiles: [],
    })
    first.task.stages.items.push({
      id: 'stage-2', order: 2, status: 'PENDING', processedItems: 0, totalItems: 0,
      statusMessage: 'Waiting',
    })
    const reordered = JSON.parse(JSON.stringify(first))
    reordered.reportBlocks.items.reverse()
    reordered.task.stages.items.reverse()

    expect(livingReportSnapshotKey(reordered)).toBe(livingReportSnapshotKey(first))
  })
})
