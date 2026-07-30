import {
  buildLinkedProcedureSummary,
  linkedProcedureSubtitle,
  optimizationFinalStatusFromReportBlocks,
} from '@/components/reports/linked-procedure-summary'

const linkedTask = {
  id: 'task-1',
  type: 'Portfolio Optimization',
  status: 'RUNNING',
  target: 'procedure/procedure-1',
  command: 'procedure run',
  description: 'Internal selector description',
  metadata: JSON.stringify({
    procedure_id: 'procedure-1',
    operator_identity: {
      kind: 'scorecard_scoped_portfolio',
      display_title: 'Scorecard-scoped optimization portfolio',
      display_scope: 'scorecard names beginning with "Internal selector"',
    },
  }),
  createdAt: '2026-07-30T12:00:00.000Z',
  startedAt: '2026-07-30T12:00:01.000Z',
  currentStageId: 'stage-1',
  stages: {
    items: [
      {
        id: 'stage-1',
        name: 'Analysis',
        order: 2,
        status: 'RUNNING',
        statusMessage: 'Ranking feedback opportunities',
      },
    ],
  },
}

describe('buildLinkedProcedureSummary', () => {
  it('projects the linked Procedure Task without promoting raw selectors into the heading', () => {
    const summary = buildLinkedProcedureSummary({
      reportId: 'report-1',
      reportName: 'Scorecard-scoped optimization portfolio',
      reportCreatedAt: '2026-07-30T12:00:02.000Z',
      reportUpdatedAt: '2026-07-30T12:00:03.000Z',
      reportCreatedByUserId: 'user-1',
      task: linkedTask as any,
    })

    expect(summary).toMatchObject({
      id: 'procedure-1',
      procedureType: 'Portfolio Optimization',
      displayTitle: 'Scorecard-scoped optimization portfolio',
      displayScope: 'Focused scorecard portfolio',
      createdByUserId: 'user-1',
      task: {
        id: 'task-1',
        status: 'RUNNING',
        currentStageId: 'stage-1',
        stages: { items: [{ name: 'Analysis', status: 'RUNNING' }] },
      },
    })
    expect(summary?.displayScope).not.toContain('beginning with')
  })

  it('does not invent a Procedure summary for an unrelated or missing Task', () => {
    expect(buildLinkedProcedureSummary({
      reportId: 'report-1',
      reportName: 'Ordinary report',
      reportCreatedAt: '2026-07-30T12:00:02.000Z',
      task: null,
    })).toBeNull()

    expect(buildLinkedProcedureSummary({
      reportId: 'report-1',
      reportName: 'Ordinary report',
      reportCreatedAt: '2026-07-30T12:00:02.000Z',
      task: { ...linkedTask, target: 'report/report-1', metadata: '{}' } as any,
    })).toBeNull()
  })

  it('projects the precise incomplete outcome without changing the coarse Task status', () => {
    const summary = buildLinkedProcedureSummary({
      reportId: 'report-1',
      reportName: 'Scorecard-scoped optimization portfolio',
      reportCreatedAt: '2026-07-30T12:00:02.000Z',
      task: {
        ...linkedTask,
        status: 'COMPLETED',
        metadata: JSON.stringify({
          ...JSON.parse(linkedTask.metadata),
          optimization_run_final_status: 'incomplete',
        }),
      } as any,
    })

    expect(summary?.status).toBe('INCOMPLETE')
    expect(summary?.task?.status).toBe('COMPLETED')
    expect(linkedProcedureSubtitle(summary!)).toBe('Portfolio Optimization • Incomplete')
  })

  it('uses the living Report revision when its terminal outcome arrives before Task metadata refreshes', () => {
    const reportOutcome = optimizationFinalStatusFromReportBlocks([{
      type: 'OptimizationRunStatus',
      output: {
        preview: {
          summary: {
            overview: { lifecycle_status: 'incomplete' },
          },
        },
      },
    }])
    const summary = buildLinkedProcedureSummary({
      reportId: 'report-1',
      reportName: 'Scorecard-scoped optimization portfolio',
      reportCreatedAt: '2026-07-30T12:00:02.000Z',
      task: {
        ...linkedTask,
        status: 'COMPLETED',
      } as any,
      optimizationFinalStatus: reportOutcome,
    })

    expect(reportOutcome).toBe('INCOMPLETE')
    expect(summary?.status).toBe('INCOMPLETE')
    expect(summary?.task?.status).toBe('COMPLETED')
  })
})
