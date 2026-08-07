import { graphqlRequest } from '@/utils/amplify-client'

export type RegisteredCommandAction =
  | 'evaluation.accuracy'
  | 'evaluation.feedback'
  | 'prediction.run'
  | 'report.run'
  | 'procedure.run'
  | 'feedback.report'

export interface SubmittedCommandTask {
  id: string
  accountId: string
  type: string
  status: string
  target?: string | null
  command?: string | null
  dispatchStatus?: string | null
  lifecycleStatus?: string | null
  commandPayload?: unknown
  createdAt?: string | null
  updatedAt?: string | null
}

export async function submitCommand(
  accountId: string,
  action: RegisteredCommandAction,
  arguments_: Record<string, unknown>,
): Promise<SubmittedCommandTask> {
  const result = await graphqlRequest<{ submitCommand: SubmittedCommandTask & { taskId: string } }>(
    `mutation SubmitCommand($accountId: ID!, $action: String!, $arguments: AWSJSON!, $idempotencyKey: String) {
      submitCommand(accountId: $accountId, action: $action, arguments: $arguments, idempotencyKey: $idempotencyKey) {
        taskId id accountId type status target command dispatchStatus lifecycleStatus
        commandPayload createdAt updatedAt
      }
    }`,
    { accountId, action, arguments: JSON.stringify(arguments_), idempotencyKey: crypto.randomUUID() },
  )
  const submitted = result.data?.submitCommand
  if (!submitted?.taskId) throw new Error('Command was not accepted')
  const { taskId, ...task } = submitted
  if (!task.id || task.id !== taskId || task.accountId !== accountId || !task.type || !task.status) {
    throw new Error('Accepted command Task could not be loaded')
  }
  return task as SubmittedCommandTask
}

export async function submitCommandAndNotify(
  accountId: string,
  action: RegisteredCommandAction,
  arguments_: Record<string, unknown>,
  onTaskCreated?: (task: SubmittedCommandTask) => void,
): Promise<SubmittedCommandTask> {
  const task = await submitCommand(accountId, action, arguments_)
  onTaskCreated?.(task)
  return task
}
