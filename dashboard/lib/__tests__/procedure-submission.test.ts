import { branchProcedureRun, continueProcedureRun } from '@/lib/procedure-submission'
import { submitCommand } from '@/lib/submit-command'

jest.mock('@/lib/submit-command', () => ({ submitCommand: jest.fn() }))

const mockSubmitCommand = submitCommand as jest.MockedFunction<typeof submitCommand>

describe('procedure submission workflows', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockSubmitCommand.mockResolvedValue({ id: 'task-1', accountId: 'account-1', type: 'Procedure', status: 'PENDING' })
  })

  it('updates continuation configuration before submitting account-bound parameters', async () => {
    const order: string[] = []
    const updateConfiguration = jest.fn(async () => { order.push('update') })
    mockSubmitCommand.mockImplementation(async () => { order.push('submit'); return { id: 'task-1', accountId: 'account-1', type: 'Procedure', status: 'PENDING' } })

    await expect(continueProcedureRun({
      accountId: 'account-1',
      procedureId: 'procedure-1',
      parameters: { max_iterations: 8, hint: 'try this' },
      updateConfiguration,
    })).resolves.toBe('task-1')

    expect(order).toEqual(['update', 'submit'])
    expect(mockSubmitCommand).toHaveBeenCalledWith('account-1', 'procedure.run', {
      procedureId: 'procedure-1',
      parameters: { max_iterations: 8, hint: 'try this' },
    })
  })

  it('does not submit a continuation when the configuration update fails', async () => {
    await expect(continueProcedureRun({
      accountId: 'account-1',
      procedureId: 'procedure-1',
      parameters: {},
      updateConfiguration: async () => { throw new Error('update failed') },
    })).rejects.toThrow('update failed')
    expect(mockSubmitCommand).not.toHaveBeenCalled()
  })

  it('creates and clones a branch before submitting the new procedure identity', async () => {
    const order: string[] = []
    const createBranch = jest.fn(async () => { order.push('create'); return 'procedure-branch' })
    const cloneState = jest.fn(async () => { order.push('clone') })
    mockSubmitCommand.mockImplementation(async () => { order.push('submit'); return { id: 'task-branch', accountId: 'account-1', type: 'Procedure', status: 'PENDING' } })

    await expect(branchProcedureRun({
      accountId: 'account-1',
      sourceProcedureId: 'procedure-1',
      truncateToCycle: 4,
      parameters: { max_iterations: 7 },
      createBranch,
      cloneState,
    })).resolves.toBe('procedure-branch')

    expect(order).toEqual(['create', 'clone', 'submit'])
    expect(cloneState).toHaveBeenCalledWith({
      sourceProcedureId: 'procedure-1',
      targetProcedureId: 'procedure-branch',
      truncateToCycle: 4,
    })
    expect(mockSubmitCommand).toHaveBeenCalledWith('account-1', 'procedure.run', {
      procedureId: 'procedure-branch',
      parameters: { max_iterations: 7 },
    })
  })

  it('does not submit a branch when state cloning fails', async () => {
    await expect(branchProcedureRun({
      accountId: 'account-1',
      sourceProcedureId: 'procedure-1',
      truncateToCycle: 2,
      parameters: {},
      createBranch: async () => 'procedure-branch',
      cloneState: async () => { throw new Error('clone failed') },
    })).rejects.toThrow('clone failed')
    expect(mockSubmitCommand).not.toHaveBeenCalled()
  })
})
