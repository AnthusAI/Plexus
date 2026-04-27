import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'

import { TaskOutputDisplay } from '../TaskOutputDisplay'

jest.mock('aws-amplify/storage', () => ({
  downloadData: jest.fn(),
  getUrl: jest.fn(),
}))

jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}))

const { downloadData } = jest.requireMock('aws-amplify/storage') as {
  downloadData: jest.Mock
}

describe('TaskOutputDisplay', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('loads compacted task output from task attachments', async () => {
    downloadData.mockReturnValue({
      result: Promise.resolve({
        body: {
          text: async () => 'full task output payload',
        },
      }),
    })

    render(
      <TaskOutputDisplay
        output={JSON.stringify({
          status: 'completed',
          output_compacted: true,
          preview: { message: 'preview only' },
          output_attachment: 'tasks/task-123/output.json',
        })}
        attachedFiles={['tasks/task-123/output.json']}
        command="procedure run proc-123"
        taskType="Procedure"
      />
    )

    expect(screen.getByText('Task Output')).toBeInTheDocument()
    expect(screen.getByText('Attachment: tasks/task-123/output.json')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('full task output payload')).toBeInTheDocument()
    })

    expect(downloadData).toHaveBeenCalledWith({
      path: 'tasks/task-123/output.json',
      options: { bucket: 'taskAttachments' },
    })
  })
})
