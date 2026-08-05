import { issueTaskArtifactReadTicket } from '../artifact-ticket-client'
import type { ArtifactTransferReadRequest } from '../report-artifacts'

const request: ArtifactTransferReadRequest = {
  operation: 'READ',
  resourceType: 'TASK',
  resourceId: 'task-1',
  artifactType: 'TASK_ATTACHMENT',
  filename: 'summary.md',
  contentType: 'text/markdown',
  sizeBytes: 12,
  sha256: 'a'.repeat(64),
}

describe('artifact ticket client', () => {
  it('requests exactly one existing GraphQL read ticket', async () => {
    const mutation = jest.fn().mockResolvedValue({
      data: [{
        method: 'GET',
        url: 'https://storage.example.com/temporary',
        requiredHeaders: '{}',
      }],
    })

    await expect(issueTaskArtifactReadTicket(request, {
      mutations: { createArtifactTransferTickets: mutation },
    })).resolves.toEqual({
      method: 'GET',
      url: 'https://storage.example.com/temporary',
      requiredHeaders: {},
    })
    expect(mutation).toHaveBeenCalledWith({ requests: [request] })
  })

  it('rejects mutation failures and unsafe tickets', async () => {
    await expect(issueTaskArtifactReadTicket(request, {
      mutations: {
        createArtifactTransferTickets: async () => ({
          errors: [{ message: 'not authorized' }],
        }),
      },
    })).rejects.toThrow('not authorized')

    await expect(issueTaskArtifactReadTicket(request, {
      mutations: {
        createArtifactTransferTickets: async () => ({
          data: [{ method: 'GET', url: 'http://storage.example.com/file', requiredHeaders: {} }],
        }),
      },
    })).rejects.toThrow('unsafe read URL')
  })
})
