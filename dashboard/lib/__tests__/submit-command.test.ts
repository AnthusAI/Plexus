import { submitCommand, submitCommandAndNotify } from '@/lib/submit-command'
import { graphqlRequest } from '@/utils/amplify-client'

jest.mock('@/utils/amplify-client', () => ({ graphqlRequest: jest.fn() }))

const mockGraphqlRequest = graphqlRequest as jest.MockedFunction<typeof graphqlRequest>

describe('submitCommand', () => {
  it('resolves and returns the persisted authoritative Task after submission', async () => {
    const task = {
      id: 'task-1',
      accountId: 'account-1',
      type: 'Prediction Test',
      status: 'PENDING',
      target: 'prediction',
      command: 'predict --scorecard Card',
      dispatchStatus: 'READY',
      lifecycleStatus: 'ANNOUNCED',
      commandPayload: { argv: ['predict'] },
      createdAt: '2026-08-06T00:00:00Z',
      updatedAt: '2026-08-06T00:00:00Z',
    }
    mockGraphqlRequest.mockResolvedValueOnce({ data: { submitCommand: { taskId: 'task-1', ...task } } } as any)

    await expect(submitCommand('account-1', 'prediction.run', { itemId: 'item-1' })).resolves.toEqual(task)
    expect(mockGraphqlRequest).toHaveBeenCalledTimes(1)
    expect(mockGraphqlRequest).toHaveBeenCalledWith(expect.stringContaining('commandPayload createdAt updatedAt'), expect.any(Object))
  })

  it('fails visibly instead of returning incomplete callback data', async () => {
    mockGraphqlRequest.mockResolvedValueOnce({ data: { submitCommand: { taskId: 'task-1' } } } as any)

    await expect(submitCommand('account-1', 'prediction.run', {})).rejects.toThrow(
      'Accepted command Task could not be loaded',
    )
  })

  it('invokes onTaskCreated with the resolved authoritative Task', async () => {
    const task = { id: 'task-2', accountId: 'account-1', type: 'Evaluation', status: 'PENDING' }
    const onTaskCreated = jest.fn()
    mockGraphqlRequest.mockResolvedValueOnce({ data: { submitCommand: { taskId: 'task-2', ...task } } } as any)

    await submitCommandAndNotify('account-1', 'evaluation.accuracy', {}, onTaskCreated)

    expect(onTaskCreated).toHaveBeenCalledWith(task)
  })
})
