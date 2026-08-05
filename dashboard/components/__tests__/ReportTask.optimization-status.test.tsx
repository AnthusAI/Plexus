import React from 'react'
import { TextDecoder } from 'util'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

jest.mock('react-markdown', () => {
  const React = require('react')
  return function ReactMarkdown({ children, components }: any) {
    const source = String(children)
    if (source.includes('class: OptimizationRunStatus')) {
      return React.createElement(
        React.Fragment,
        null,
        React.createElement(components.code, {
          node: { data: {} },
          inline: false,
          className: 'language-block',
          children: 'class: OptimizationRunStatus',
        }),
      )
    }
    if (source.startsWith('# ')) {
      const [heading, ...paragraphs] = source.split('\n\n')
      return React.createElement(
        React.Fragment,
        null,
        React.createElement(components.h1, {
          node: { data: {} },
          children: heading.slice(2),
        }),
        ...paragraphs.map((paragraph: string, index: number) => React.createElement(
          components.p,
          { key: index, node: { data: {} }, children: paragraph },
        )),
      )
    }
    return React.createElement(React.Fragment, null, children)
  }
})

jest.mock('@/components/ProcedureTask', () => ({
  __esModule: true,
  default: ({ procedure }: any) => (
    <div data-testid="linked-procedure-task-summary">
      {procedure.displayTitle} — {procedure.task?.status}
    </div>
  ),
}))

import ReportTask from '@/components/ReportTask'

Object.assign(global, { TextDecoder })

const descriptor = {
  logical_id: 'stakeholder_presentation',
  kind: 'stakeholder_presentation',
  display_name: 'Stakeholder presentation data',
  scope: 'run',
  content_type: 'application/json',
  size_bytes: 10,
  sha256: 'a'.repeat(64),
  task_id: 'task-1',
  object_key: 'tasks/task-1/optimization-presentation-r0001.json',
  source_revision: 1,
}

const statusBlock = {
  id: 'block-1',
  name: 'Run Status',
  position: 0,
  type: 'OptimizationRunStatus',
  output: {
    output_compacted: true,
    preview: {
      type: 'optimization_run_status',
      status: 'published',
      summary: { revision: 1, milestone: 'started', presentation: descriptor },
    },
  },
  attachedFiles: [],
}

jest.mock('@/utils/amplify-client', () => ({
  getClient: jest.fn(() => ({
    graphql: jest.fn().mockResolvedValue({
      data: { getReport: { reportBlocks: { items: [statusBlock] } } },
    }),
  })),
}))

jest.mock('@/lib/artifact-ticket-client', () => ({
  issueTaskArtifactReadTicket: jest.fn(),
}))

jest.mock('@/lib/report-artifacts', () => {
  const actual = jest.requireActual('@/lib/report-artifacts')
  return {
    ...actual,
    readTaskArtifact: jest.fn().mockResolvedValue(
      new Uint8Array(Buffer.from(JSON.stringify({
        overview: {
          lifecycle_status: 'running',
          coverage_status: 'pending',
          current_activity: 'Preparing the frozen portfolio.',
        },
        score_count: 0,
        scorecard_count: 0,
        primary_decision_mix: {},
        secondary_issue_counts: {},
        top_priorities: [],
        scorecards: [],
      }))),
    ),
  }
})

const readTaskArtifactMock = jest.requireMock('@/lib/report-artifacts').readTaskArtifact as jest.Mock

describe('ReportTask optimization status integration', () => {
  beforeEach(() => {
    readTaskArtifactMock.mockReset().mockResolvedValue(
      new Uint8Array(Buffer.from(JSON.stringify({
        overview: {
          lifecycle_status: 'running',
          coverage_status: 'pending',
          current_activity: 'Preparing the frozen portfolio.',
        },
        score_count: 0,
        scorecard_count: 0,
        primary_decision_mix: {},
        secondary_issue_counts: {},
        top_priorities: [],
        scorecards: [],
      }))),
    )
  })

  it('renders the aggregate presentation referenced by the report cover', async () => {
    render(
      <ReportTask
        variant="detail"
        task={{
          id: 'report-1',
          type: 'Report',
          name: '',
          description: '',
          scorecard: '',
          score: '',
          time: '2026-07-30T00:00:00.000Z',
          status: 'RUNNING',
          data: {
            id: 'report-1',
            title: 'Optimization portfolio',
            name: 'Optimization portfolio',
            configName: 'Optimization portfolio',
            output: '# Optimization portfolio\n\n```block\nclass: OptimizationRunStatus\n```',
            reportBlocks: [statusBlock],
          },
        } as any}
      />,
    )

    expect(await screen.findByText('Preparing the frozen portfolio.')).toBeInTheDocument()
    expect(screen.queryByText('Optimization opportunity survey')).not.toBeInTheDocument()
    expect(screen.getByText('Preparing the frozen portfolio.')).toBeInTheDocument()
  })

  it('embeds the standard linked Procedure Task summary ahead of report findings', async () => {
    const linkedProcedure = {
      id: 'procedure-1',
      title: 'Feedback survey: Example',
      displayTitle: 'Feedback survey: Example',
      displayScope: 'Focused scorecard portfolio',
      procedureType: 'Feedback survey',
      featured: false,
      createdAt: '2026-07-30T00:00:00.000Z',
      updatedAt: '2026-07-30T00:01:00.000Z',
      task: {
        id: 'task-1',
        type: 'Portfolio Optimization',
        status: 'RUNNING',
        target: 'procedure/procedure-1',
        command: 'procedure run',
        stages: { items: [] },
      },
    }

    render(
      <ReportTask
        variant="detail"
        linkedProcedure={linkedProcedure as any}
        task={{
          id: 'report-1',
          type: 'Report',
          name: '',
          description: '',
          scorecard: '',
          score: '',
          time: '2026-07-30T00:00:00.000Z',
          status: 'RUNNING',
          data: {
            id: 'report-1',
            title: 'Scorecard-scoped optimization portfolio',
            configName: 'Scorecard-scoped optimization portfolio',
            output: '# Scorecard-scoped optimization portfolio\n\n18 candidates were deferred by the safety cap.',
            reportBlocks: [],
          },
        } as any}
      />,
    )

    expect(screen.getByTestId('linked-procedure-task-summary')).toHaveTextContent(
      'Feedback survey: Example — RUNNING',
    )
    expect(screen.getByRole('heading', { name: 'Feedback survey: Example' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Scorecard-scoped optimization portfolio' })).not.toBeInTheDocument()
    expect(screen.getByText('18 candidates were not examined because of the configured diagnosis limit.')).toBeInTheDocument()
    expect(screen.queryByText(/safety cap/i)).not.toBeInTheDocument()
    expect(screen.getByTestId('report-detail-content')).not.toHaveClass('h-full')
    expect(screen.getByTestId('report-cover-content')).not.toHaveClass('overflow-y-auto')
    expect(screen.getByTestId('report-cover-content')).not.toHaveClass('flex-1')
  })

  it('normalizes only the two legacy cover sentences when object metadata proves a configured diagnosis limit', () => {
    const linkedProcedure = {
      id: 'procedure-1', displayTitle: 'Feedback survey: Example', featured: false,
      createdAt: '2026-07-30T00:00:00.000Z', updatedAt: '2026-07-30T00:01:00.000Z',
      task: {
        id: 'task-1', type: 'Portfolio Optimization', status: 'COMPLETED', target: 'procedure/procedure-1', command: 'procedure run', stages: { items: [] },
        metadata: { latest_revision: { overview: {
          inventory_coverage_status: 'complete', analysis_coverage_status: 'incomplete',
          diagnosis_scheduled_count: 2, diagnosis_completed_count: 2, diagnosis_deferred_count: 8,
          diagnosis_incomplete_count: 0, semantic_budget_failure_count: 0,
          diagnosis_prerequisite_failure_count: 0, semantic_budget_exhausted_count: 0,
          semantic_budget_deferred_count: 0,
        } } },
      },
    }

    render(
      <ReportTask
        variant="detail"
        linkedProcedure={linkedProcedure as any}
        task={{
          id: 'report-1', type: 'Report', name: '', description: '', scorecard: '', score: '',
          time: '2026-07-30T00:00:00.000Z', status: 'COMPLETED',
          data: {
            id: 'report-1', title: 'Optimization portfolio', configName: 'Optimization portfolio', reportBlocks: [],
            output: '# Optimization portfolio\n\nThe run ended with incomplete evidence.\n\nNext checkpoint: Review the documented coverage failures before relying on its conclusions.',
          },
        } as any}
      />,
    )

    expect(screen.getByText('The configured diagnosis limit was reached after all scheduled diagnoses completed.')).toBeInTheDocument()
    expect(screen.getByText('Next checkpoint: Increase the diagnosis limit or review deferred candidates in a follow-up run.')).toBeInTheDocument()
    expect(screen.queryByText('The run ended with incomplete evidence.')).not.toBeInTheDocument()
    expect(screen.queryByText(/Review the documented coverage failures/)).not.toBeInTheDocument()
  })

  it('preserves legacy cover sentences when string metadata records an execution or budget failure', () => {
    const linkedProcedure = {
      id: 'procedure-1', displayTitle: 'Feedback survey: Example', featured: false,
      createdAt: '2026-07-30T00:00:00.000Z', updatedAt: '2026-07-30T00:01:00.000Z',
      task: {
        id: 'task-1', type: 'Portfolio Optimization', status: 'COMPLETED', target: 'procedure/procedure-1', command: 'procedure run', stages: { items: [] },
        metadata: JSON.stringify({ latest_revision: { overview: {
          inventory_coverage_status: 'complete', analysis_coverage_status: 'incomplete',
          diagnosis_scheduled_count: 2, diagnosis_completed_count: 2, diagnosis_deferred_count: 8,
          diagnosis_incomplete_count: 0, semantic_budget_failure_count: 1,
          diagnosis_prerequisite_failure_count: 0, semantic_budget_exhausted_count: 1,
          semantic_budget_deferred_count: 0,
        } } }),
      },
    }

    render(
      <ReportTask
        variant="detail"
        linkedProcedure={linkedProcedure as any}
        task={{
          id: 'report-1', type: 'Report', name: '', description: '', scorecard: '', score: '',
          time: '2026-07-30T00:00:00.000Z', status: 'COMPLETED',
          data: {
            id: 'report-1', title: 'Optimization portfolio', configName: 'Optimization portfolio', reportBlocks: [],
            output: '# Optimization portfolio\n\nThe run ended with incomplete evidence.\n\nNext checkpoint: Review the documented coverage failures before relying on its conclusions.',
          },
        } as any}
      />,
    )

    expect(screen.getByText('The run ended with incomplete evidence.')).toBeInTheDocument()
    expect(screen.getByText('Next checkpoint: Review the documented coverage failures before relying on its conclusions.')).toBeInTheDocument()
    expect(screen.queryByText(/configured diagnosis limit was reached/i)).not.toBeInTheDocument()
  })

  it('preserves expanded scorecard drill-in state when live progress refreshes', async () => {
    const user = userEvent.setup()
    const scorecardDescriptor = {
      ...descriptor,
      logical_id: 'scorecard_presentation:fixture',
      kind: 'scorecard_presentation',
      display_name: 'Interactive score details',
      scope: 'scorecard',
      object_key: 'tasks/task-1/scorecard-presentation-r0001.json',
      scorecard_name: 'Example scorecard',
    }
    const presentationBytes = new Uint8Array(Buffer.from(JSON.stringify({
        overview: { lifecycle_status: 'running', coverage_status: 'complete' },
        score_count: 1,
        scorecard_count: 1,
        primary_decision_mix: { optimize: 1 },
        secondary_issue_counts: {},
        top_priorities: [],
        scorecards: [{
          scorecard_ref: 'scorecard-fixture',
          scorecard_name: 'Example scorecard',
          score_count: 1,
          reviewed_error_opportunity: 3,
          artifacts: [scorecardDescriptor],
        }],
      })))
    const scorecardBytes = new Uint8Array(Buffer.from(JSON.stringify({
        scorecard_name: 'Example scorecard',
        questions_and_issues: [],
        scores: [{ score_name: 'Example score', artifacts: [] }],
      })))
    readTaskArtifactMock.mockReset().mockImplementation((artifact: { kind?: string }) =>
      Promise.resolve(artifact.kind === 'scorecard_presentation' ? scorecardBytes : presentationBytes),
    )

    const taskForBlock = (block: typeof statusBlock) => ({
      id: 'report-1',
      type: 'Report',
      name: '',
      description: '',
      scorecard: '',
      score: '',
      time: '2026-07-30T00:00:00.000Z',
      status: 'RUNNING' as const,
      data: {
        id: 'report-1',
        title: 'Optimization portfolio',
        name: 'Optimization portfolio',
        configName: 'Optimization portfolio',
        output: '# Optimization portfolio\n\n```block\nclass: OptimizationRunStatus\n```',
        reportBlocks: [block],
      },
    })

    const { rerender } = render(
      <ReportTask variant="detail" task={taskForBlock(statusBlock) as any} />,
    )

    const scorecardButton = await screen.findByRole('button', { name: /Example scorecard/ })
    await user.click(scorecardButton)
    expect(await screen.findByText('Example score')).toBeInTheDocument()
    expect(scorecardButton).toHaveAttribute('aria-expanded', 'true')

    const progressOnlyBlock = {
      ...statusBlock,
      output: {
        ...statusBlock.output,
        preview: {
          ...statusBlock.output.preview,
          summary: {
            ...statusBlock.output.preview.summary,
            live_progress: {
              phase: 'assessment',
              current: 1,
              total: 10,
              message: 'Assessing the portfolio.',
            },
          },
        },
      },
    }
    rerender(<ReportTask variant="detail" task={taskForBlock(progressOnlyBlock) as any} />)

    expect(await screen.findByText('1 of 10 scores assessed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Example scorecard/ })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Example score')).toBeInTheDocument()
  })
})
