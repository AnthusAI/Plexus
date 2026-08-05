import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { TextDecoder } from 'util'

import ReportArtifactViewer from '../ReportArtifactViewer'

Object.assign(global, { TextDecoder })

const mockGetReport = jest.fn()
const mockReadTaskArtifact = jest.fn()

jest.mock('@/app/contexts/AccountContext', () => ({
  useAccount: () => ({ selectedAccount: { id: 'account-1' } }),
}))

jest.mock('@/utils/amplify-client', () => ({
  getClient: () => ({ models: { Report: { get: mockGetReport } } }),
  formatAmplifyError: (value: unknown) => String(value),
}))

jest.mock('@/lib/artifact-ticket-client', () => ({
  issueTaskArtifactReadTicket: jest.fn(),
}))

jest.mock('@/lib/report-artifacts', () => {
  const actual = jest.requireActual('@/lib/report-artifacts')
  return { ...actual, readTaskArtifact: (...args: unknown[]) => mockReadTaskArtifact(...args) }
})

const manifestReference = {
  task_id: 'task-1',
  object_key: 'tasks/task-1/manifest-r0002.json',
  content_type: 'application/json',
  size_bytes: 10,
  sha256: 'a'.repeat(64),
}

const descriptor = {
  logical_id: 'scorecard_summary:abc123',
  kind: 'scorecard_summary',
  display_name: 'Scorecard summary',
  scope: 'scorecard',
  content_type: 'text/markdown',
  size_bytes: 9,
  sha256: 'b'.repeat(64),
  task_id: 'task-1',
  object_key: 'tasks/task-1/summary-r0002.md',
  source_revision: 2,
  scorecard_name: 'Example Portfolio',
}

describe('ReportArtifactViewer', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockGetReport.mockResolvedValue({
      data: {
        id: 'report-1',
        name: 'Daily optimization portfolio',
        accountId: 'account-1',
        parameters: {
          optimization_run: {
            latest_revision: { number: 3 },
            revisions: [
              { number: 2, manifest: manifestReference },
              { number: 3, manifest: { ...manifestReference, object_key: 'tasks/task-1/manifest-r0003.json' } },
            ],
          },
        },
      },
    })
    mockReadTaskArtifact
      .mockResolvedValueOnce(new Uint8Array(Buffer.from(JSON.stringify({
        revision: 2,
        artifacts: [descriptor],
      }))))
      .mockResolvedValueOnce(new Uint8Array(Buffer.from('# Findings')))
  })

  it('renders the exact verified revision and a newer-revision link', async () => {
    render(
      <ReportArtifactViewer
        reportId="report-1"
        revision={2}
        logicalId={descriptor.logical_id}
      />,
    )

    expect(await screen.findByRole('heading', { name: 'Scorecard summary' })).toBeInTheDocument()
    expect(screen.getByText('Example Portfolio')).toBeInTheDocument()
    expect(screen.getByText('# Findings')).toBeInTheDocument()
    expect(screen.getByText(/Revision 3 is newer/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open newer revision' })).toHaveAttribute(
      'href',
      '/lab/reports/report-1?revision=3&artifact=scorecard_summary%3Aabc123',
    )
    expect(mockReadTaskArtifact).toHaveBeenNthCalledWith(1, manifestReference, expect.any(Object))
    expect(mockReadTaskArtifact).toHaveBeenNthCalledWith(2, descriptor, expect.any(Object))
  })

  it('fails closed before artifact access for a different account', async () => {
    mockGetReport.mockResolvedValueOnce({
      data: {
        accountId: 'account-2',
        parameters: {},
      },
    })

    render(
      <ReportArtifactViewer
        reportId="report-1"
        revision={2}
        logicalId={descriptor.logical_id}
      />,
    )

    expect(await screen.findByText('This Report belongs to a different account.')).toBeInTheDocument()
    await waitFor(() => expect(mockReadTaskArtifact).not.toHaveBeenCalled())
  })
})
