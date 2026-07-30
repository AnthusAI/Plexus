import React from 'react'
import { TextDecoder } from 'util'
import { render, screen } from '@testing-library/react'

jest.mock('react-markdown', () => {
  const React = require('react')
  return function ReactMarkdown({ children, components }: any) {
    const source = String(children)
    if (source.includes('class: OptimizationRunStatus')) {
      return React.createElement(
        React.Fragment,
        null,
        components.code({
          node: { data: {} },
          inline: false,
          className: 'language-block',
          children: 'class: OptimizationRunStatus',
        }),
      )
    }
    return React.createElement(React.Fragment, null, children)
  }
})

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

describe('ReportTask optimization status integration', () => {
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

    expect(await screen.findByText('Optimization portfolio overview')).toBeInTheDocument()
    expect(screen.getByText('Preparing the frozen portfolio.')).toBeInTheDocument()
  })
})
