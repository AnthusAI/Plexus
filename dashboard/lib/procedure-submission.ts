import { submitCommand } from '@/lib/submit-command'

export type ProcedureParameters = Record<string, unknown>

export async function continueProcedureRun(input: {
  accountId: string
  procedureId: string
  parameters: ProcedureParameters
  updateConfiguration: () => Promise<void>
}): Promise<string> {
  await input.updateConfiguration()
  const task = await submitCommand(input.accountId, 'procedure.run', {
    procedureId: input.procedureId,
    parameters: input.parameters,
  })
  return task.id
}

export async function branchProcedureRun(input: {
  accountId: string
  sourceProcedureId: string
  truncateToCycle: number
  parameters: ProcedureParameters
  createBranch: () => Promise<string>
  cloneState: (request: {
    sourceProcedureId: string
    targetProcedureId: string
    truncateToCycle: number
  }) => Promise<void>
}): Promise<string> {
  const procedureId = await input.createBranch()
  await input.cloneState({
    sourceProcedureId: input.sourceProcedureId,
    targetProcedureId: procedureId,
    truncateToCycle: input.truncateToCycle,
  })
  await submitCommand(input.accountId, 'procedure.run', {
    procedureId,
    parameters: input.parameters,
  })
  return procedureId
}
